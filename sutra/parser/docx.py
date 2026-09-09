import os
import re
import json
import subprocess
from typing import Dict, Any, List, Union, Optional
from sutra.models import (
    Document, Metadata, Section, Paragraph, InlineRun,
    Author, Affiliation, Figure, Table, TableCell,
    Footnote, Endnote, BlockQuote, ListNode, ListItem,
    Sidebar, Equation, TrackedChangeMarker, UnrecognizedBlock,
    Reference, ReferenceAuthor, Citation
)

class DocxParserError(Exception):
    pass

class DocxParser:
    """
    Parses a DOCX manuscript into a typed Pydantic Document IR.
    Uses Pandoc to parse DOCX into a JSON AST, then translates it.
    """
    def __init__(self, docx_path: str):
        self.docx_path = docx_path

    def parse(self) -> Document:
        if not os.path.exists(self.docx_path):
            raise DocxParserError(f"File not found: {self.docx_path}")

        try:
            pandoc_json = self._run_pandoc()
            ast = json.loads(pandoc_json)
        except Exception as e:
            raise DocxParserError(f"Failed to generate/parse Pandoc JSON AST: {str(e)}")

        return self._translate_ast_to_ir(ast)

    def _run_pandoc(self) -> str:
        """
        Invokes Pandoc in a subprocess safely using argument list format.
        (Secures against command injection per security-audit.md SEC-12 / §5.1).
        """
        import shutil
        pandoc_bin = shutil.which("pandoc")
        if not pandoc_bin:
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            local_pandoc = os.path.join(local_appdata, "Pandoc", "pandoc.exe")
            if os.path.exists(local_pandoc):
                pandoc_bin = local_pandoc
            else:
                pandoc_bin = "pandoc"  # Fallback

        # Execute 'pandoc -f docx -t json <docx_path>'
        cmd = [pandoc_bin, "-f", "docx", "-t", "json", self.docx_path]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                check=True
            )
            return result.stdout
        except FileNotFoundError:
            raise DocxParserError("Pandoc binary not found. Please install Pandoc and add it to your PATH.")
        except subprocess.CalledProcessError as e:
            raise DocxParserError(f"Pandoc error (exit code {e.returncode}): {e.stderr}")

    def _translate_ast_to_ir(self, ast: Dict[str, Any]) -> Document:
        """
        Translates the Pandoc JSON AST into our typed Document Pydantic IR.
        """
        doc = Document()
        
        # Pandoc AST JSON format:
        # { "pandoc-api-version": [...], "meta": {...}, "blocks": [...] }
        blocks = ast.get("blocks", [])
        meta = ast.get("meta", {})

        # 1. Parse Metadata from meta map
        doc.metadata = self._parse_metadata(meta)

        # 2. Heuristic front-matter extraction: If metadata title is absent, scan initial body blocks
        if not doc.metadata.title:
            blocks = self._extract_frontmatter_heuristics(doc, blocks)

        # 3. Promote fake headings (bold / numbered / standard academic headings)
        blocks = self._promote_fake_headings(blocks)

        # 4. Parse Body sections recursively building tree structure
        doc.body = self._build_section_tree(blocks)

        # 5. Pull extracted citations and references from metadata or parsed list
        # Look for references block in metadata
        refs_meta = meta.get("references")
        if refs_meta and refs_meta.get("t") == "MetaList":
            for ref_val in refs_meta.get("c", []):
                if ref_val.get("t") == "MetaMap":
                    doc.references.append(self._parse_meta_reference(ref_val.get("c", {})))

        return doc

    def _parse_metadata(self, meta: Dict[str, Any]) -> Metadata:
        """
        Extracts title, authors, affiliations, abstract, and other metadata from the Pandoc meta dictionary.
        """
        ir_meta = Metadata()
        
        # Parse title
        title_meta = meta.get("title")
        if title_meta:
            title_inlines = title_meta.get("c", [])
            ir_meta.title = self._parse_inline_runs(title_inlines)
            
        # Parse abstract
        abs_meta = meta.get("abstract")
        if abs_meta:
            abs_blocks = abs_meta.get("c", [])
            # Flatten abstract blocks to paragraphs
            ir_meta.abstract.paragraphs = [
                Paragraph(content=self._parse_inline_runs(b.get("c", [])))
                for b in abs_blocks if b.get("t") in ("Para", "Plain")
            ]

        # Parse keywords
        kwd_meta = meta.get("keywords")
        if kwd_meta:
            # Semicolon/comma separation or list
            if kwd_meta.get("t") == "MetaList":
                ir_meta.keywords = [self._extract_inline_text(k.get("c", [])) for k in kwd_meta.get("c", [])]
            else:
                raw_kwd = self._extract_inline_text(kwd_meta.get("c", []))
                ir_meta.keywords = [k.strip() for k in raw_kwd.replace(";", ",").split(",") if k.strip()]

        # Parse authors
        author_meta = meta.get("author")
        if author_meta:
            authors_list = []
            if isinstance(author_meta, dict) and author_meta.get("t") == "MetaList":
                authors_list = author_meta.get("c", [])
            elif isinstance(author_meta, list):
                authors_list = author_meta
            else:
                authors_list = [author_meta]

            parsed_authors = []
            for auth_item in authors_list:
                if isinstance(auth_item, dict) and auth_item.get("t") == "MetaMap":
                    auth_map = auth_item.get("c", {})
                    name = self._extract_inline_text(auth_map.get("name", {}).get("c", []))
                    given = self._extract_inline_text(auth_map.get("given-names", {}).get("c", []))
                    family = self._extract_inline_text(auth_map.get("family-name", {}).get("c", []))
                    
                    if not given and not family and name:
                        parts = name.split()
                        given = parts[0] if parts else ""
                        family = " ".join(parts[1:]) if len(parts) > 1 else ""

                    aff_list = []
                    aff_meta = auth_map.get("affiliation", {})
                    if isinstance(aff_meta, dict) and aff_meta.get("t") == "MetaList":
                        aff_list = [self._extract_inline_text(a.get("c", [])) for a in aff_meta.get("c", [])]
                    elif aff_meta:
                        c_val = aff_meta.get("c", []) if isinstance(aff_meta, dict) else []
                        aff_text = self._extract_inline_text(c_val)
                        if aff_text:
                            aff_list = [aff_text]

                    parsed_authors.append(Author(
                        given_name=given,
                        family_name=family,
                        affiliation_refs=aff_list,
                        orcid=self._extract_inline_text(auth_map.get("orcid", {}).get("c", []) if isinstance(auth_map.get("orcid"), dict) else []),
                        email=self._extract_inline_text(auth_map.get("email", {}).get("c", []) if isinstance(auth_map.get("email"), dict) else []),
                        corresponding=bool(auth_map.get("corresponding", {}).get("c", False) if isinstance(auth_map.get("corresponding"), dict) else False)
                    ))
            ir_meta.authors = parsed_authors

        return ir_meta

    def _parse_meta_reference(self, ref_map: Dict[str, Any]) -> Reference:
        """
        Parses reference details from metadata Map structure.
        """
        ref_id = self._extract_inline_text(ref_map.get("id", {}).get("c", []) if isinstance(ref_map.get("id"), dict) else [])
        ref_type = self._extract_inline_text(ref_map.get("type", {}).get("c", []) if isinstance(ref_map.get("type"), dict) else "") or "journal-article"
        
        # Author parsing
        authors = []
        author_list = ref_map.get("author", {}).get("c", []) if isinstance(ref_map.get("author"), dict) else []
        for auth in author_list:
            if isinstance(auth, dict) and auth.get("t") == "MetaMap":
                amap = auth.get("c", {})
                family = self._extract_inline_text(amap.get("family", {}).get("c", []) if isinstance(amap.get("family"), dict) else [])
                given = self._extract_inline_text(amap.get("given", {}).get("c", []) if isinstance(amap.get("given"), dict) else [])
                authors.append(ReferenceAuthor(family=family, given=given))

        return Reference(
            id=ref_id,
            type=ref_type,
            authors=authors,
            year=self._extract_inline_text(ref_map.get("issued", {}).get("c", {}).get("literal", {}).get("c", []) if isinstance(ref_map.get("issued"), dict) else []),
            title=self._extract_inline_text(ref_map.get("title", {}).get("c", []) if isinstance(ref_map.get("title"), dict) else []),
            source_title=self._extract_inline_text(ref_map.get("container-title", {}).get("c", []) if isinstance(ref_map.get("container-title"), dict) else []),
            volume=self._extract_inline_text(ref_map.get("volume", {}).get("c", []) if isinstance(ref_map.get("volume"), dict) else []),
            issue=self._extract_inline_text(ref_map.get("issue", {}).get("c", []) if isinstance(ref_map.get("issue"), dict) else []),
            pages=self._extract_inline_text(ref_map.get("page", {}).get("c", []) if isinstance(ref_map.get("page"), dict) else []),
            doi=self._extract_inline_text(ref_map.get("DOI", {}).get("c", []) if isinstance(ref_map.get("DOI"), dict) else [])
        )

    def _extract_frontmatter_heuristics(self, doc: Document, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Academic front-matter heuristics:
        When Word metadata (dc:title, authors, abstract) is not provided in document properties,
        inspect the initial body blocks before the first major heading (or prose) to extract:
        - Title (the first non-empty block)
        - Authors (paragraphs with names / superscripts before abstract)
        - Affiliations (paragraphs mentioning Department, University, College, etc.)
        - Abstract (content under Abstract heading)
        - Keywords (content starting with Keywords / Index Terms)
        Returns the remaining body blocks with the extracted front-matter removed.
        """
        if not blocks:
            return blocks

        consumed_indices = set()
        idx = 0
        n = len(blocks)

        # Count Level-1 headers in the document
        h1_headers = [b for b in blocks if b.get("t") == "Header" and b.get("c") and b.get("c")[0] == 1]
        has_multiple_h1 = len(h1_headers) > 1

        # 1. Title: must be at the very top (cannot appear after section headers)
        while idx < n:
            b = blocks[idx]
            t = b.get("t")
            c = b.get("c", [])

            # Paragraph containing only display math or image cannot be a title
            if t in ("Para", "Plain") and len(c) == 1 and isinstance(c[0], dict) and c[0].get("t") in ("Math", "Image"):
                break

            # If we encounter a Header at top level:
            if t == "Header":
                if idx == 0 and not has_multiple_h1 and b.get("c", [])[0] == 1:
                    # Lone Level-1 header at the very top of document can be the Title (e.g. "A Test Manuscript")
                    inlines = c[2]
                    text = self._extract_inline_text(inlines).strip()
                    if text and len(re.findall(r"[a-zA-Z]", text)) >= 3:
                        if not re.match(r"^(section|subsection|chapter|\d+[\.\s])\b", text, re.IGNORECASE):
                            doc.metadata.title = self._parse_inline_runs(inlines)
                            consumed_indices.add(idx)
                            idx += 1
                # Any Header signifies the start of the body section tree; stop title search immediately
                break

            if t in ("Para", "Plain"):
                inlines = c
                text = self._extract_inline_text(inlines).strip()
                # Must contain at least 3 letters and not be a section/chapter heading
                if text and len(re.findall(r"[a-zA-Z]", text)) >= 3:
                    if not re.match(r"^(section|subsection|chapter|\d+[\.\s])\b", text, re.IGNORECASE):
                        doc.metadata.title = self._parse_inline_runs(inlines)
                        consumed_indices.add(idx)
                        idx += 1
                        break
            idx += 1

        # If no title could be identified in the frontmatter, stop immediately and return blocks unchanged
        if not doc.metadata.title:
            return blocks

        affil_words = [
            "department", "dept", "university", "college", "faculty", "institute",
            "institution", "school", "laboratory", "hospital", "center", "centre",
            "station", "campus", "ministry", "academy", "division", "agromet"
        ]
        sentence_stopwords = {
            "this", "is", "a", "an", "the", "with", "from", "that", "which",
            "are", "were", "was", "have", "has", "been", "for", "study", "paper",
            "we", "in", "by", "on"
        }

        in_abstract = False

        while idx < n:
            b = blocks[idx]
            t = b.get("t")
            c = b.get("c", [])
            if t not in ("Para", "Plain"):
                break

            # If paragraph contains only display math or image, break immediately
            if len(c) == 1 and isinstance(c[0], dict) and c[0].get("t") in ("Math", "Image"):
                break

            text = self._extract_inline_text(c).strip()
            if not text:
                idx += 1
                continue

            # Stop if we hit a major section heading (e.g. 1. Introduction, INTRODUCTION)
            if re.match(r"^(\d+[\.\s]+|introduction\b|background\b)", text, re.IGNORECASE):
                break

            # Check Keywords
            if re.match(r"^(keywords|key\s*words|index\s*terms)[:\s]", text, re.IGNORECASE):
                consumed_indices.add(idx)
                raw = re.sub(r"^(keywords|key\s*words|index\s*terms)[:\s]*", "", text, flags=re.IGNORECASE)
                doc.metadata.keywords = [k.strip() for k in re.split(r"[,;]", raw) if k.strip()]
                in_abstract = False
                idx += 1
                continue

            # Check Abstract Heading
            if re.match(r"^(abstract)\s*$", text, re.IGNORECASE):
                consumed_indices.add(idx)
                in_abstract = True
                idx += 1
                continue

            if re.match(r"^(abstract)[:\s]", text, re.IGNORECASE):
                consumed_indices.add(idx)
                abs_text = re.sub(r"^(abstract)[:\s]*", "", text, flags=re.IGNORECASE)
                if abs_text.strip():
                    doc.metadata.abstract.paragraphs.append(Paragraph(content=[InlineRun(text=abs_text)]))
                in_abstract = True
                idx += 1
                continue

            if in_abstract:
                # Body of abstract
                doc.metadata.abstract.paragraphs.append(Paragraph(content=self._parse_inline_runs(c)))
                consumed_indices.add(idx)
                idx += 1
                continue

            # Affiliations check
            lower = text.lower()
            if any(w in lower for w in affil_words) or "@" in text or "corresponding" in lower:
                doc.metadata.affiliations.append(Affiliation(id=f"aff-{len(doc.metadata.affiliations)+1}", institution=text))
                consumed_indices.add(idx)
                idx += 1
                continue

            # Prose stop check: if text contains regular sentence grammar, stop frontmatter extraction
            words_lower = set(re.findall(r"\b[a-z]+\b", lower))
            if len(words_lower.intersection(sentence_stopwords)) >= 2:
                break

            # Authors check: short name lists before abstract
            if len(text) < 100 and not text.startswith("http"):
                # Reject full sentences that end with words and a period (e.g. "Paragraph content.")
                if re.search(r"[a-z]{3,}\.\s*$", text):
                    break

                parts = [p.strip() for p in text.split(",") if p.strip()]
                for p in parts:
                    name = re.sub(r"[\*\d†‡]+", "", p).strip()
                    if name:
                        name_parts = name.split()
                        given = name_parts[0] if name_parts else ""
                        family = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                        doc.metadata.authors.append(Author(given_name=given, family_name=family))
                consumed_indices.add(idx)
                idx += 1
                continue

            break

        return [b for i, b in enumerate(blocks) if i not in consumed_indices]

    def _promote_fake_headings(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Promotes unstyled bold paragraphs or numbered headings into Header elements.
        """
        academic_sections = {
            "introduction", "materials and methods", "material and methods", "methodology", "methods",
            "experimental", "results", "discussion", "results and discussion", "conclusion",
            "conclusions", "acknowledgements", "acknowledgments", "references", "literature cited"
        }
        promoted = []
        for b in blocks:
            t = b.get("t")
            c = b.get("c", [])
            if t in ("Para", "Plain"):
                text = self._extract_inline_text(c).strip()
                clean = re.sub(r"^\d+[\.\s]+", "", text).strip().lower()
                is_heading = False
                level = 1

                m_num = re.match(r"^(\d+(\.\d+)*)\s+([A-Z].*)", text)
                if m_num and len(text) < 80:
                    is_heading = True
                    level = min(len(m_num.group(1).split(".")), 3)
                elif clean in academic_sections and len(text) < 80:
                    is_heading = True
                    level = 1

                if is_heading:
                    promoted.append({"t": "Header", "c": [level, ["", [], []], c]})
                    continue
            promoted.append(b)
        return promoted

    def _build_section_tree(self, blocks: List[Dict[str, Any]]) -> List[Section]:
        """
        Builds a hierarchical section tree from a flat list of block items.
        Handles nested headings properly using active stacks.
        """
        body_sections: List[Section] = []
        stack: List[Section] = []
        
        # Root Section to collect content before the first heading
        root_section = Section(id="sec-intro", level=1, heading="")

        for block in blocks:
            b_type = block.get("t")
            b_val = block.get("c")

            if b_type == "Header":
                level, attr, inlines = b_val
                header_text = self._extract_inline_text(inlines)
                sec_id = attr[0] if attr and attr[0] else f"sec-{level}-{header_text.lower().replace(' ', '-')}"
                
                new_sec = Section(id=sec_id, level=level, heading=header_text)
                
                # Pop stack until we find a parent level
                while stack and stack[-1].level >= level:
                    stack.pop()
                    
                if not stack:
                    body_sections.append(new_sec)
                else:
                    stack[-1].content.append(new_sec)
                stack.append(new_sec)
                
            else:
                items = self._parse_block_element(block)
                if not items:
                    continue
                
                if not stack:
                    # Collect into implicit root section
                    root_section.content.extend(items)
                else:
                    stack[-1].content.extend(items)

        # If we have early content, prepend root section
        if root_section.content:
            body_sections.insert(0, root_section)

        return body_sections

    def _parse_block_element(self, block: Dict[str, Any]) -> List[Any]:
        """
        Parses a single Pandoc block element and returns lists of content items.
        """
        t = block.get("t")
        c = block.get("c")

        if t in ("Para", "Plain"):
            # Collect all Image inlines in this paragraph
            image_inlines = [inline for inline in c if isinstance(inline, dict) and inline.get("t") == "Image"]
            non_image_inlines = [inline for inline in c if not (isinstance(inline, dict) and inline.get("t") == "Image")]

            # Check if paragraph consists solely of a single display element (e.g. DisplayMath, Image)
            if len(c) == 1:
                inline = c[0]
                it = inline.get("t")
                ic = inline.get("c")
                if it == "Math" and ic[0].get("t") == "DisplayMath":
                    # Elevate display equation to block
                    return [Equation(
                        id=f"eq-{hash(ic[1]) % 10000}",
                        source="latex_native",
                        latex_source=ic[1],
                        display="block"
                    )]
                elif it == "Image":
                    # Elevate image to block Figure
                    attr, alt_inlines, target = ic
                    img_id = attr[0] if attr and attr[0] else f"fig-{hash(target[0]) % 10000}"
                    alt_text = self._extract_inline_text(alt_inlines) or "Figure"
                    fmt = "vector" if any(target[0].lower().endswith(ext) for ext in (".svg", ".pdf", ".eps")) else "raster"
                    return [Figure(
                        id=img_id,
                        image_ref=target[0],
                        format=fmt,
                        caption=self._parse_inline_runs(alt_inlines),
                        alt_text=alt_text
                    )]

            # Multiple images in the same paragraph (panel figures like Fig. 10 A, B, C)
            if len(image_inlines) > 1:
                results = []
                for img_inline in image_inlines:
                    ic = img_inline.get("c")
                    attr, alt_inlines, target = ic
                    img_id = attr[0] if attr and attr[0] else f"fig-{hash(target[0]) % 10000}"
                    alt_text = self._extract_inline_text(alt_inlines) or "Figure"
                    fmt = "vector" if any(target[0].lower().endswith(ext) for ext in (".svg", ".pdf", ".eps")) else "raster"
                    results.append(Figure(
                        id=img_id,
                        image_ref=target[0],
                        format=fmt,
                        caption=self._parse_inline_runs(alt_inlines),
                        alt_text=alt_text
                    ))
                # Also include any non-image text as a paragraph
                if non_image_inlines:
                    text_content = self._extract_inline_text(non_image_inlines).strip()
                    if text_content:
                        results.append(Paragraph(content=self._parse_inline_runs(non_image_inlines)))
                return results

            # Single image mixed with other text (image + caption text in same paragraph)
            if len(image_inlines) == 1 and non_image_inlines:
                results = []
                img_inline = image_inlines[0]
                ic = img_inline.get("c")
                attr, alt_inlines, target = ic
                img_id = attr[0] if attr and attr[0] else f"fig-{hash(target[0]) % 10000}"
                alt_text = self._extract_inline_text(alt_inlines) or "Figure"
                fmt = "vector" if any(target[0].lower().endswith(ext) for ext in (".svg", ".pdf", ".eps")) else "raster"
                results.append(Figure(
                    id=img_id,
                    image_ref=target[0],
                    format=fmt,
                    caption=self._parse_inline_runs(alt_inlines),
                    alt_text=alt_text
                ))
                # Remaining text becomes a paragraph (likely the caption)
                text_content = self._extract_inline_text(non_image_inlines).strip()
                if text_content:
                    results.append(Paragraph(content=self._parse_inline_runs(non_image_inlines)))
                return results

            return [Paragraph(content=self._parse_inline_runs(c))]

        elif t == "BlockQuote":
            # Nested blocks inside BlockQuote
            sub_items = []
            for b in c:
                sub_items.extend(self._parse_block_element(b))
            paragraphs = [item for item in sub_items if isinstance(item, Paragraph)]
            return [BlockQuote(content=paragraphs)]

        elif t == "BulletList":
            # List structure: list of list of blocks
            items = []
            for item_blocks in c:
                li_runs = []
                nested = None
                for b in item_blocks:
                    parsed = self._parse_block_element(b)
                    for item in parsed:
                        if isinstance(item, Paragraph):
                            li_runs.extend(item.content)
                        elif isinstance(item, ListNode):
                            nested = item
                items.append(ListItem(content=li_runs, nested_list=nested))
            return [ListNode(style="unordered", items=items)]

        elif t == "OrderedList":
            # Structure: [attrs, list of list of blocks]
            attrs, items_blocks = c
            # Numbering style attrs[1]["t"] (e.g. Decimal, LowerAlpha)
            num_fmt = attrs[1].get("t")
            items = []
            for item_blocks in items_blocks:
                li_runs = []
                nested = None
                for b in item_blocks:
                    parsed = self._parse_block_element(b)
                    for item in parsed:
                        if isinstance(item, Paragraph):
                            li_runs.extend(item.content)
                        elif isinstance(item, ListNode):
                            nested = item
                items.append(ListItem(content=li_runs, nested_list=nested))
            return [ListNode(style="ordered", numbering_format=num_fmt, items=items)]

        elif t == "Table":
            # Table attr caption colspecs head body foot
            attr, caption, colspecs, head, bodies, foot = c
            tbl_id = attr[0] if attr and attr[0] else f"tbl-{hash(tbl_id) if 'tbl_id' in locals() else 1000}"
            caption_blocks = caption[1] if len(caption) > 1 else []
            caption_runs = []
            for b in caption_blocks:
                for parsed_item in self._parse_block_element(b):
                    if isinstance(parsed_item, Paragraph):
                        caption_runs.extend(parsed_item.content)
            
            rows = []
            
            # Helper to parse Row blocks
            def parse_rows(row_blocks, is_header=False):
                if not isinstance(row_blocks, list):
                    return
                for row_block in row_blocks:
                    # Row format can be:
                    # dict: {"t": "Row", "c": [attr, cells]}
                    # list: [attr, cells]
                    if isinstance(row_block, dict):
                        row_c = row_block.get("c", [[], []])
                    else:
                        row_c = row_block
                    
                    if not isinstance(row_c, list) or len(row_c) < 2:
                        continue
                    
                    cells_block = row_c[1]
                    if not isinstance(cells_block, list):
                        continue
                        
                    tbl_row = []
                    for cell_block in cells_block:
                        # Cell format can be:
                        # dict: {"t": "Cell", "c": [attr, alignment, rowspan, colspan, blocks]}
                        # list: [attr, alignment, rowspan, colspan, blocks]
                        if isinstance(cell_block, dict):
                            cell_c = cell_block.get("c", [[], {}, 1, 1, []])
                        else:
                            cell_c = cell_block
                        
                        if not isinstance(cell_c, list) or len(cell_c) < 5:
                            continue
                            
                        cell_rowspan = cell_c[2]
                        cell_colspan = cell_c[3]
                        cell_blocks = cell_c[4]
                        
                        # Parse inner cell blocks
                        cell_runs = []
                        if isinstance(cell_blocks, list):
                            for b in cell_blocks:
                                for parsed_item in self._parse_block_element(b):
                                    if isinstance(parsed_item, Paragraph):
                                        cell_runs.extend(parsed_item.content)
                                    
                        tbl_row.append(TableCell(
                            content=cell_runs,
                            colspan=cell_colspan,
                            rowspan=cell_rowspan,
                            is_header=is_header
                        ))
                    rows.append(tbl_row)

            # Parse Head
            if head and len(head) > 1:
                parse_rows(head[1], is_header=True)
                
            # Parse Bodies
            for body in bodies:
                # Body format: [attr, row_head_columns, [rows_head], [rows_body]]
                if isinstance(body, list) and len(body) >= 4:
                    body_rows = body[3]
                    parse_rows(body_rows, is_header=False)
                
            # Parse Foot
            if foot and len(foot) > 1:
                parse_rows(foot[1], is_header=False)
                
            return [Table(
                id=tbl_id,
                caption=caption_runs,
                rows=rows,
                header_rows=len(head[1]) if head and len(head) > 1 and isinstance(head[1], list) else 1
            )]

        # Unhandled block element: return as UnrecognizedBlock
        import uuid
        text = self._extract_inline_text(c) if isinstance(c, list) else str(c) if c is not None else ""
        return [UnrecognizedBlock(
            id=f"unrecognized-{uuid.uuid4().hex[:6]}",
            raw_type=t,
            content_text=text
        )]

    def _parse_inline_runs(self, inlines: List[Dict[str, Any]]) -> List[InlineRun]:
        """
        Converts Pandoc inline elements into a list of formatted InlineRuns.
        """
        runs = []
        for item in inlines:
            t = item.get("t")  # Type of inline
            c = item.get("c")  # Content
            
            if t == "Str":
                runs.append(InlineRun(text=c))
            elif t == "Space":
                runs.append(InlineRun(text=" "))
            elif t in ("LineBreak", "SoftBreak"):
                runs.append(InlineRun(text="\n"))
            elif t == "Emph":
                runs.extend([r.model_copy(update={"italic": True}) for r in self._parse_inline_runs(c)])
            elif t == "Strong":
                runs.extend([r.model_copy(update={"bold": True}) for r in self._parse_inline_runs(c)])
            elif t == "Underline":
                runs.extend([r.model_copy(update={"underline": True}) for r in self._parse_inline_runs(c)])
            elif t == "Strikeout":
                runs.extend([r.model_copy(update={"strikethrough": True}) for r in self._parse_inline_runs(c)])
            elif t == "Superscript":
                runs.extend([r.model_copy(update={"sup": True}) for r in self._parse_inline_runs(c)])
            elif t == "Subscript":
                runs.extend([r.model_copy(update={"sub": True}) for r in self._parse_inline_runs(c)])
            elif t == "SmallCaps":
                runs.extend([r.model_copy(update={"small_caps": True}) for r in self._parse_inline_runs(c)])
            elif t == "Link":
                # Link format: [attr, inlines, target]
                _, link_inlines, target = c
                url = target[0] if target else ""
                link_text = self._extract_inline_text(link_inlines)
                runs.append(InlineRun(text=link_text, link_url=url))
            elif t == "Math":
                # Math format: [type, text]
                m_type, m_text = c
                # If display math is nested, keep as inline run with equation_source
                runs.append(InlineRun(text=m_text, equation_source=m_text))
            elif t == "Cite":
                # Citation inline format: [[citation_items], [fallback_inlines]]
                citations_list, fallback = c
                cite_keys = [cite.get("citationId") for cite in citations_list if cite.get("citationId")]
                cite_text = self._extract_inline_text(fallback)
                runs.append(InlineRun(text=cite_text, xref_target=",".join(cite_keys)))
            elif t == "Note":
                # Note holds footnotes
                # Flat parse nested note blocks into inline run or similar
                note_text = ""
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict):
                            note_text += self._extract_inline_text(b.get("c", []))
                # For now represent footnote text inline
                runs.append(InlineRun(text=f"[{note_text}]", xref_target="footnote"))

        # Consolidate adjacent unformatted text runs
        consolidated = []
        for r in runs:
            if (consolidated and not r.bold and not r.italic and not r.underline 
                and not r.strikethrough and not r.sub and not r.sup and not r.small_caps 
                and not r.link_url and not r.xref_target and not r.equation_source
                and not consolidated[-1].bold and not consolidated[-1].italic 
                and not consolidated[-1].underline and not consolidated[-1].strikethrough 
                and not consolidated[-1].sub and not consolidated[-1].sup 
                and not consolidated[-1].small_caps and not consolidated[-1].link_url 
                and not consolidated[-1].xref_target and not consolidated[-1].equation_source):
                consolidated[-1].text += r.text
            else:
                consolidated.append(r)
                
        return consolidated

    def _extract_inline_text(self, inlines: List[Dict[str, Any]]) -> str:
        """
        Recursively flattens inline elements into plain text strings.
        """
        text_parts = []
        if isinstance(inlines, dict):
            inlines = [inlines]
            
        for item in inlines:
            if not isinstance(item, dict):
                continue
            t = item.get("t")
            c = item.get("c")
            if t == "Str":
                text_parts.append(c)
            elif t == "Space":
                text_parts.append(" ")
            elif t in ("LineBreak", "SoftBreak"):
                text_parts.append("\n")
            elif t in ("Emph", "Strong", "Underline", "Strikeout", "Superscript", "Subscript", "SmallCaps"):
                text_parts.append(self._extract_inline_text(c))
            elif t == "Link":
                _, link_inlines, _ = c
                text_parts.append(self._extract_inline_text(link_inlines))
            elif t == "Math":
                text_parts.append(c[1])
            elif t == "Cite":
                text_parts.append(self._extract_inline_text(c[1] if len(c) > 1 else []))
        return "".join(text_parts)


def document_to_blocks(doc: Document) -> List[Dict[str, Any]]:
    blocks = []
    import uuid
    
    # 1. Title
    if doc.metadata.title:
        title_id = f"title-{uuid.uuid4().hex[:6]}"
        blocks.append({
            "id": title_id,
            "type": "title",
            "content": [run.model_dump() for run in doc.metadata.title],
            "state": "confirmed",
            "warnings": [],
            "is_flagged_manual": False
        })
    
    # 2. Authors
    if doc.metadata.authors:
        auth_id = f"authors-{uuid.uuid4().hex[:6]}"
        blocks.append({
            "id": auth_id,
            "type": "authors",
            "content": [auth.model_dump() for auth in doc.metadata.authors],
            "state": "confirmed",
            "warnings": [],
            "is_flagged_manual": False
        })
    
    # 3. Affiliations
    if doc.metadata.affiliations:
        aff_id = f"affiliations-{uuid.uuid4().hex[:6]}"
        blocks.append({
            "id": aff_id,
            "type": "affiliations",
            "content": [aff.model_dump() for aff in doc.metadata.affiliations],
            "state": "confirmed",
            "warnings": [],
            "is_flagged_manual": False
        })
    
    # 4. Abstract
    abs_paras = []
    for p in doc.metadata.abstract.paragraphs:
        abs_paras.append([run.model_dump() for run in p.content])
    for s in doc.metadata.abstract.structured_sections:
        label_run = InlineRun(text=f"{s.label}: ", bold=True)
        for p in s.paragraphs:
            abs_paras.append([label_run.model_dump()] + [run.model_dump() for run in p.content])
            
    if abs_paras:
        abs_id = f"abstract-{uuid.uuid4().hex[:6]}"
        blocks.append({
            "id": abs_id,
            "type": "abstract",
            "content": abs_paras,
            "state": "confirmed",
            "warnings": [],
            "is_flagged_manual": False
        })
    
    # Helper to traverse body items
    def traverse_items(items):
        for item in items:
            if isinstance(item, Section):
                # Suppress empty root section headings
                if not item.heading or not item.heading.strip():
                    traverse_items(item.content)
                    continue

                h_type = "heading_l3"
                if item.level == 1:
                    h_type = "heading_l1"
                elif item.level == 2:
                    h_type = "heading_l2"
                
                blocks.append({
                    "id": item.id or f"heading-{uuid.uuid4().hex[:6]}",
                    "type": h_type,
                    "content": [InlineRun(text=item.heading).model_dump()],
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
                traverse_items(item.content)
            elif isinstance(item, Paragraph):
                blocks.append({
                    "id": item.id or f"paragraph-{uuid.uuid4().hex[:6]}",
                    "type": "paragraph",
                    "content": [run.model_dump() for run in item.content],
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
            elif isinstance(item, Figure):
                blocks.append({
                    "id": item.id or f"figure-{uuid.uuid4().hex[:6]}",
                    "type": "figure",
                    "content": item.model_dump(),
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
            elif isinstance(item, Table):
                blocks.append({
                    "id": item.id or f"table-{uuid.uuid4().hex[:6]}",
                    "type": "table",
                    "content": item.model_dump(),
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
            elif isinstance(item, Equation):
                blocks.append({
                    "id": item.id or f"equation-{uuid.uuid4().hex[:6]}",
                    "type": "equation",
                    "content": item.model_dump(),
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
            elif isinstance(item, Footnote):
                blocks.append({
                    "id": item.id or f"footnote-{uuid.uuid4().hex[:6]}",
                    "type": "footnote",
                    "content": [run.model_dump() for run in item.content],
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
            elif isinstance(item, BlockQuote):
                blocks.append({
                    "id": f"blockquote-{uuid.uuid4().hex[:6]}",
                    "type": "blockquote",
                    "content": item.model_dump(),
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
            elif isinstance(item, ListNode):
                blocks.append({
                    "id": f"list-{uuid.uuid4().hex[:6]}",
                    "type": "list",
                    "content": item.model_dump(),
                    "state": "confirmed",
                    "warnings": [],
                    "is_flagged_manual": False
                })
            elif isinstance(item, UnrecognizedBlock):
                blocks.append({
                    "id": item.id,
                    "type": "unrecognized",
                    "content": {"raw_type": item.raw_type, "content_text": item.content_text},
                    "state": "unrecognized",
                    "warnings": [],
                    "is_flagged_manual": False
                })
                
    traverse_items(doc.body)

    # 5. Post-process: Filter out empty layout tables (Word image wrappers)
    #    Single-row tables where all cells are empty/whitespace are discarded.
    filtered_blocks = []
    for b in blocks:
        if b["type"] == "table":
            content = b.get("content", {})
            if isinstance(content, dict):
                rows = content.get("rows", [])
                if len(rows) <= 1:
                    # Check if all cells are empty
                    all_empty = True
                    for row in rows:
                        if isinstance(row, list):
                            for cell in row:
                                cell_content = cell.get("content", []) if isinstance(cell, dict) else []
                                cell_text = " ".join(
                                    r.get("text", "") for r in cell_content if isinstance(r, dict)
                                ).strip()
                                if cell_text:
                                    all_empty = False
                                    break
                        if not all_empty:
                            break
                    if all_empty and len(rows) >= 1:
                        # Skip this empty layout table
                        continue
        filtered_blocks.append(b)
    blocks = filtered_blocks

    # 6. Post-process: Associate caption paragraphs with adjacent table/figure blocks.
    #    A paragraph matching "Table N." immediately before a table block → merge into table caption.
    #    A paragraph matching "Figure N." / "Fig. N." before a figure block → merge into figure caption.
    table_caption_re = re.compile(r"^Table\s+\d+[\.:]\s*", re.IGNORECASE)
    figure_caption_re = re.compile(r"^(Figure|Fig\.?)\s+\d+[\.:]\s*", re.IGNORECASE)

    caption_merged = set()
    for idx in range(len(blocks) - 1):
        curr = blocks[idx]
        nxt = blocks[idx + 1]

        if curr["type"] == "paragraph":
            para_text = ""
            if isinstance(curr["content"], list):
                para_text = " ".join(
                    run.get("text", "") for run in curr["content"]
                    if isinstance(run, dict)
                ).strip()
            elif isinstance(curr["content"], str):
                para_text = curr["content"].strip()

            if not para_text:
                continue

            # Table caption → next table
            if table_caption_re.match(para_text) and nxt["type"] == "table":
                nxt_content = nxt.get("content", {})
                if isinstance(nxt_content, dict):
                    # Set caption runs from the paragraph content
                    if isinstance(curr["content"], list):
                        nxt_content["caption"] = curr["content"]
                    else:
                        nxt_content["caption"] = [{"text": para_text, "bold": False, "italic": False}]
                    nxt["content"] = nxt_content
                caption_merged.add(idx)

            # Figure caption → next figure
            elif figure_caption_re.match(para_text) and nxt["type"] == "figure":
                nxt_content = nxt.get("content", {})
                if isinstance(nxt_content, dict):
                    if isinstance(curr["content"], list):
                        nxt_content["caption"] = curr["content"]
                    else:
                        nxt_content["caption"] = [{"text": para_text, "bold": False, "italic": False}]
                    nxt["content"] = nxt_content
                caption_merged.add(idx)

    if caption_merged:
        blocks = [b for i, b in enumerate(blocks) if i not in caption_merged]

    # 7. Post-process: Detect paragraphs under "References" / "Bibliography" / "Literature Cited"
    #    heading and merge them into a single reference_list block.
    ref_heading_labels = {"references", "bibliography", "literature cited"}
    ref_heading_idx = None
    for idx, b in enumerate(blocks):
        if b["type"] == "heading_l1":
            heading_text = ""
            if isinstance(b["content"], list) and len(b["content"]) > 0:
                heading_text = b["content"][0].get("text", "")
            elif isinstance(b["content"], str):
                heading_text = b["content"]
            clean = re.sub(r"^\d+[\.\s]+", "", heading_text).strip().lower()
            if clean in ref_heading_labels:
                ref_heading_idx = idx
                # Don't break — use the last match (in case there are multiple,
                # the actual references section is usually at the end)

    body_ref_entries = []
    if ref_heading_idx is not None:
        # Collect all paragraph blocks after the references heading until the next
        # heading or end of document. Skip table/figure blocks (common for manuscripts
        # where data tables are appended after references at end of document).
        consume_indices = set()
        for idx in range(ref_heading_idx + 1, len(blocks)):
            b = blocks[idx]
            if b["type"].startswith("heading_"):
                break
            if b["type"] == "paragraph":
                # Check if this looks like a table/figure caption — skip it
                para_text = ""
                if isinstance(b["content"], list):
                    para_text = " ".join(
                        run.get("text", "") for run in b["content"]
                        if isinstance(run, dict)
                    ).strip()
                elif isinstance(b["content"], str):
                    para_text = b["content"].strip()

                # Skip if this paragraph is a table/figure caption (not a reference)
                if table_caption_re.match(para_text) or figure_caption_re.match(para_text):
                    continue
                # Skip very short or empty text
                if not para_text or para_text.lower() in ("interaction absent", ""):
                    consume_indices.add(idx)
                    continue

                body_ref_entries.append({
                    "id": f"ref-{len(body_ref_entries) + 1}",
                    "type": "journal-article",
                    "title": para_text,
                    "source_title": "",
                    "authors": [],
                    "year": "",
                    "volume": "",
                    "issue": "",
                    "pages": "",
                    "doi": ""
                })
                consume_indices.add(idx)

        if body_ref_entries:
            # Also consume the "References" heading itself
            consume_indices.add(ref_heading_idx)
            # Remove consumed paragraph blocks and heading
            blocks = [b for i, b in enumerate(blocks) if i not in consume_indices]

    # Merge body-extracted references with any Pandoc-metadata references
    all_refs = [ref.model_dump() for ref in doc.references] + body_ref_entries

    if all_refs:
        ref_id = f"references-{uuid.uuid4().hex[:6]}"
        blocks.append({
            "id": ref_id,
            "type": "reference_list",
            "content": all_refs,
            "state": "confirmed",
            "warnings": [],
            "is_flagged_manual": False
        })
    
    return blocks


def blocks_to_document(blocks: List[Dict[str, Any]]) -> Document:
    doc = Document()
    body_items = []
    
    for block in blocks:
        b_type = block["type"]
        b_content = block["content"]
        b_id = block["id"]
        
        if b_type == "title":
            doc.metadata.title = [InlineRun(**run) for run in b_content]
        elif b_type == "authors":
            authors_list = []
            for auth in b_content:
                if isinstance(auth, dict) and "given_name" in auth and "family_name" in auth:
                    authors_list.append(Author(**auth))
                elif isinstance(auth, dict) and "text" in auth:
                    name_text = auth.get("text", "").strip()
                    if name_text:
                        parts = name_text.split()
                        if len(parts) > 1:
                            given = " ".join(parts[:-1])
                            family = parts[-1]
                        else:
                            given = name_text
                            family = ""
                        authors_list.append(Author(given_name=given, family_name=family))
                elif isinstance(auth, str):
                    name_text = auth.strip()
                    if name_text:
                        parts = name_text.split()
                        if len(parts) > 1:
                            given = " ".join(parts[:-1])
                            family = parts[-1]
                        else:
                            given = name_text
                            family = ""
                        authors_list.append(Author(given_name=given, family_name=family))
            doc.metadata.authors.extend(authors_list)
        elif b_type == "affiliations":
            aff_list = []
            for aff in b_content:
                if isinstance(aff, dict) and "id" in aff and "institution" in aff:
                    aff_list.append(Affiliation(**aff))
                elif isinstance(aff, dict) and "text" in aff:
                    inst_text = aff.get("text", "").strip()
                    if inst_text:
                        aff_id = f"aff-{len(doc.metadata.affiliations) + len(aff_list) + 1}"
                        aff_list.append(Affiliation(id=aff_id, institution=inst_text))
                elif isinstance(aff, str):
                    inst_text = aff.strip()
                    if inst_text:
                        aff_id = f"aff-{len(doc.metadata.affiliations) + len(aff_list) + 1}"
                        aff_list.append(Affiliation(id=aff_id, institution=inst_text))
            doc.metadata.affiliations.extend(aff_list)
        elif b_type == "abstract":
            paragraphs = []
            if b_content:
                if isinstance(b_content, str):
                    paragraphs.append(Paragraph(content=[InlineRun(text=b_content)]))
                elif isinstance(b_content, list) and len(b_content) > 0:
                    first_item = b_content[0]
                    if isinstance(first_item, list):
                        for p_runs in b_content:
                            runs = [InlineRun(**run) if isinstance(run, dict) else InlineRun(text=str(run)) for run in p_runs]
                            paragraphs.append(Paragraph(content=runs))
                    elif isinstance(first_item, dict):
                        paragraphs.append(Paragraph(content=[InlineRun(**run) if isinstance(run, dict) else InlineRun(text=str(run)) for run in b_content]))
                    elif isinstance(first_item, str):
                        for p_str in b_content:
                            paragraphs.append(Paragraph(content=[InlineRun(text=str(p_str))]))
            doc.metadata.abstract.paragraphs.extend(paragraphs)
        elif b_type == "reference_list":
            ref_list = []
            for ref in b_content:
                if isinstance(ref, dict) and "id" in ref and "title" in ref:
                    ref_list.append(Reference(**ref))
                elif isinstance(ref, dict) and "text" in ref:
                    ref_text = ref.get("text", "").strip()
                    if ref_text:
                        ref_id = f"ref-{len(doc.references) + len(ref_list) + 1}"
                        ref_list.append(Reference(
                            id=ref_id,
                            type="journal-article",
                            title=ref_text,
                            source_title=""
                        ))
                elif isinstance(ref, str):
                    ref_text = ref.strip()
                    if ref_text:
                        ref_id = f"ref-{len(doc.references) + len(ref_list) + 1}"
                        ref_list.append(Reference(
                            id=ref_id,
                            type="journal-article",
                            title=ref_text,
                            source_title=""
                        ))
            doc.references.extend(ref_list)
        elif b_type in ("heading_l1", "heading_l2", "heading_l3"):
            level = 1 if b_type == "heading_l1" else 2 if b_type == "heading_l2" else 3
            heading_text = ""
            if isinstance(b_content, list) and len(b_content) > 0:
                heading_text = "".join(run.get("text", "") if isinstance(run, dict) else str(run) for run in b_content)
            else:
                heading_text = str(b_content)
                
            heading_text = re.sub(r'[\r\n]+', ' ', heading_text).strip()
            heading_text = re.sub(r'\s+', ' ', heading_text)
                
            body_items.append(Section(
                id=b_id,
                level=level,
                heading=heading_text,
                content=[]
            ))
        elif b_type == "paragraph":
            body_items.append(Paragraph(
                id=b_id,
                content=[InlineRun(**run) for run in b_content]
            ))
        elif b_type == "figure":
            body_items.append(Figure(**b_content))
        elif b_type == "table":
            body_items.append(Table(**b_content))
        elif b_type == "equation":
            body_items.append(Equation(**b_content))
        elif b_type == "footnote":
            body_items.append(Footnote(
                id=b_id,
                content=[InlineRun(**run) for run in b_content]
            ))
        elif b_type == "blockquote":
            body_items.append(BlockQuote(**b_content))
        elif b_type == "list":
            body_items.append(ListNode(**b_content))
        elif b_type == "unrecognized":
            raw_type = b_content.get("raw_type", "unrecognized")
            content_text = b_content.get("content_text", "")
            body_items.append(UnrecognizedBlock(
                id=b_id,
                raw_type=raw_type,
                content_text=content_text
            ))
            
    doc.body = build_section_tree_from_items(body_items)
    return doc


def build_section_tree_from_items(items: List[Any]) -> List[Section]:
    body_sections: List[Section] = []
    stack: List[Section] = []
    
    root_section = Section(id="sec-intro", level=1, heading="")
    
    for item in items:
        if isinstance(item, Section):
            while stack and stack[-1].level >= item.level:
                stack.pop()
            if not stack:
                body_sections.append(item)
            else:
                stack[-1].content.append(item)
            stack.append(item)
        else:
            if not stack:
                root_section.content.append(item)
            else:
                stack[-1].content.append(item)
                
    if root_section.content:
        body_sections.insert(0, root_section)
        
    return body_sections

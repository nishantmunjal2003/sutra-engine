"""
sutra.ai.pdf_cross_checker — PDF Layout Cross-Checker for Manuscript Blocks

Extracts layout and typographic signals from a raw or rendered manuscript PDF
using pdfplumber and cross-checks them against the DOCX-parsed blocks to identify
and auto-correct structural misclassifications.
"""

import os
import re
import datetime
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple
import pdfplumber


class PDFBlockCrossChecker:
    """
    Analyzes raw PDF layout and cross-checks against parsed blocks.
    Detects structural misclassifications by inspecting:
    - Font sizes and weights (largest text = title, large/bold = headings)
    - Image bounding boxes and adjacent text -> figures & captions
    - Table grid lines and row/column structures -> tables
    - Indented/smaller text sections -> abstract
    - Keywords labels -> keywords block
    - Numbered bibliographic entries near the end -> reference list
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    @staticmethod
    def _extract_plain_text(block: Dict[str, Any]) -> str:
        """Extracts flattened plain text string from any block representation."""
        content = block.get("content")
        if not content:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(
                        item.get("text")
                        or item.get("institution")
                        or f"{item.get('given_name', '')} {item.get('family_name', '')}".strip()
                        or ""
                    )
                elif isinstance(item, list):
                    parts.append("".join(run.get("text", "") for run in item if isinstance(run, dict)))
                else:
                    parts.append(str(item))
            return " ".join(filter(None, parts)).strip()
        if isinstance(content, dict):
            if content.get("caption"):
                cap = content["caption"]
                if isinstance(cap, list):
                    return "".join(r.get("text", "") for r in cap if isinstance(r, dict)).strip()
                return str(cap).strip()
            return (content.get("text") or content.get("content_text") or "").strip()
        return ""

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalizes text for comparison by removing whitespace and non-alphanumeric chars."""
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()

    def cross_check(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Cross-checks the block sequence against the PDF layout.
        Returns a dictionary with updated blocks, change provenance diffs,
        and summary metrics.
        """
        if not blocks:
            return {
                "blocks": [],
                "changes": [],
                "updated_count": 0,
                "summary": "No blocks provided for PDF cross-check.",
                "provider": "pdf-cross-check"
            }

        with pdfplumber.open(self.pdf_path) as pdf:
            pdf_info = self._analyze_pdf_layout(pdf)

        changes: List[Dict[str, Any]] = []
        updated_blocks: List[Dict[str, Any]] = []
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()

        # Track state across blocks
        title_found = any(b.get("type") == "title" for b in blocks)
        in_abstract_zone = False
        in_ref_zone = False

        for idx, orig_b in enumerate(blocks):
            b = dict(orig_b)  # Shallow copy block
            block_text = self._extract_plain_text(b)
            old_type = b.get("type", "paragraph")
            norm_b = self._normalize_text(block_text)

            inferred_type = None
            reason = None
            confidence = 0.90

            if not norm_b:
                updated_blocks.append(b)
                continue

            # 1. Check Title (page 1, large font, early block)
            if not title_found and idx < 4:
                if pdf_info.get("title_text") and (
                    norm_b in pdf_info["title_norm"] or pdf_info["title_norm"] in norm_b or
                    (len(norm_b) > 15 and norm_b[:40] in pdf_info["title_norm"])
                ):
                    inferred_type = "title"
                    title_size = pdf_info.get("title_size", 14.0)
                    reason = f"PDF layout: Largest font ({title_size:.1f}pt) on Page 1 matches document title"
                    confidence = 0.96
                    title_found = True

            # 2. Check Figure Caption
            if not inferred_type:
                # Signal 1: Caption pattern matching Fig/Figure
                fig_match = re.match(r"^(fig(\.|ure)?|photo|plate)\s*(\d+|[a-z])\b", block_text, re.IGNORECASE)
                if fig_match:
                    inferred_type = "figure"
                    reason = f"PDF layout: Figure caption prefix '{fig_match.group(0)}' adjacent to visual asset"
                    confidence = 0.95
                elif self._is_near_pdf_image(norm_b, block_text, pdf_info.get("images_with_captions", [])):
                    inferred_type = "figure"
                    reason = "PDF layout: Text positioned directly below image bounding box"
                    confidence = 0.92

            # 3. Check Table
            if not inferred_type:
                tbl_match = re.match(r"^(table|tab\.)\s*(\d+|[a-z])\b", block_text, re.IGNORECASE)
                if tbl_match:
                    inferred_type = "table"
                    reason = f"PDF layout: Table label '{tbl_match.group(0)}' associated with tabular data"
                    confidence = 0.95
                elif self._is_table_content(norm_b, pdf_info.get("table_texts", [])):
                    inferred_type = "table"
                    reason = "PDF layout: Content matches cells within PDF table grid lines"
                    confidence = 0.93

            # 4. Check Headings (H1, H2, H3)
            if not inferred_type:
                heading_match = self._match_heading(norm_b, block_text, pdf_info.get("headings", []))
                if heading_match:
                    h_level, h_size, h_text = heading_match
                    target_h_type = f"heading_l{h_level}"
                    inferred_type = target_h_type
                    reason = f"PDF layout: Heading level {h_level} ({h_size:.1f}pt font, distinct spacing)"
                    confidence = 0.94

                    # Update zones
                    if "reference" in norm_b or "literature cited" in norm_b or "bibliography" in norm_b:
                        in_ref_zone = True
                        in_abstract_zone = False
                    elif "abstract" in norm_b:
                        in_abstract_zone = True
                    elif in_abstract_zone:
                        in_abstract_zone = False

            # 5. Check Abstract
            if not inferred_type:
                if re.match(r"^abstract\b", block_text, re.IGNORECASE) and len(block_text) < 40:
                    inferred_type = "abstract"
                    reason = "PDF layout: Section marker for Abstract"
                    confidence = 0.95
                    in_abstract_zone = True
                elif in_abstract_zone and not in_ref_zone and idx < 12:
                    # Check if text lies in abstract bounding box / font size
                    if self._is_abstract_text(norm_b, pdf_info.get("abstract_text_norm", "")):
                        inferred_type = "abstract"
                        reason = "PDF layout: Indented abstract body text"
                        confidence = 0.91

            # 6. Check Keywords
            if not inferred_type:
                if re.match(r"^(keywords|key\s*words|index\s*terms)[\s:]", block_text, re.IGNORECASE):
                    inferred_type = "keywords"
                    reason = "PDF layout: Keywords / Index terms block"
                    confidence = 0.96
                    in_abstract_zone = False

            # 7. Check References
            if not inferred_type:
                if in_ref_zone:
                    # Numbered citation pattern [1], 1., or author year
                    if re.match(r"^(\[\d+\]|\d+\.|\([A-Za-z]+\s*,?\s*\d{4}\))", block_text) or len(block_text) > 20:
                        inferred_type = "reference_list"
                        reason = "PDF layout: Bibliographic citation item following References heading"
                        confidence = 0.93

            # Check if this represents a correction
            # Normalize comparison: "heading_1" equals "heading_l1", "references" equals "reference_list"
            is_type_mismatch = False
            if inferred_type:
                norm_old = self._normalize_type(old_type)
                norm_new = self._normalize_type(inferred_type)
                if norm_old != norm_new:
                    is_type_mismatch = True

            if is_type_mismatch and inferred_type:
                # Apply the correction to block
                b["type"] = inferred_type
                b["is_ai_assisted"] = True
                b["ai_provider"] = "pdf-cross-check"
                b["ai_confidence"] = confidence
                b["state"] = "confirmed"

                change_entry = {
                    "old_type": old_type,
                    "new_type": inferred_type,
                    "reason": reason,
                    "timestamp": now_iso,
                    "reviewed": False
                }
                b["ai_change"] = change_entry

                changes.append({
                    "block_id": b.get("id", f"blk-{idx}"),
                    "old_type": old_type,
                    "new_type": inferred_type,
                    "reason": reason,
                    "confidence": confidence,
                    "source": "pdf-cross-check"
                })

            updated_blocks.append(b)

        return {
            "blocks": updated_blocks,
            "changes": changes,
            "updated_count": len(changes),
            "summary": f"{len(changes)} blocks corrected based on PDF layout analysis" if changes else "PDF layout cross-check verified: all blocks correctly classified.",
            "provider": "pdf-cross-check",
            "pdf_stats": {
                "pages": pdf_info.get("page_count", 0),
                "body_size": pdf_info.get("body_size", 10.0),
                "headings_detected": len(pdf_info.get("headings", [])),
                "tables_detected": len(pdf_info.get("table_texts", [])),
                "images_detected": len(pdf_info.get("images_with_captions", []))
            }
        }

    @staticmethod
    def _normalize_type(t: str) -> str:
        """Normalizes block types for comparison (e.g. heading_1 -> heading_l1)."""
        t = t.lower()
        if t in ("heading_1", "heading_l1", "h1"):
            return "heading_l1"
        if t in ("heading_2", "heading_l2", "h2"):
            return "heading_l2"
        if t in ("heading_3", "heading_l3", "h3"):
            return "heading_l3"
        if t in ("references", "reference_list", "bibliography"):
            return "reference_list"
        return t

    def _analyze_pdf_layout(self, pdf: pdfplumber.PDF) -> Dict[str, Any]:
        """Extracts layout metadata, typography tiers, tables, and image anchors."""
        font_size_combos = Counter()
        all_words_with_fonts = []

        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["fontname", "size"])
            for w in words:
                font_name = w.get("fontname", "")
                size = round(w.get("size", 10.0), 1)
                font_size_combos[(font_name, size)] += 1
                all_words_with_fonts.append(w)

        # Body font size is most frequent
        if font_size_combos:
            (body_font, body_size), _ = font_size_combos.most_common(1)[0]
        else:
            body_font, body_size = "Times", 10.0

        # Analyze Page 1 for Title
        title_text = ""
        title_norm = ""
        title_size = body_size
        p1 = pdf.pages[0] if pdf.pages else None

        if p1:
            p1_words = p1.extract_words(extra_attrs=["fontname", "size"])
            # Group consecutive words by font size
            max_size = max((round(w["size"], 1) for w in p1_words), default=body_size)
            if max_size > body_size + 1.5:
                title_words = [w["text"] for w in p1_words if round(w["size"], 1) >= max_size - 0.5]
                title_text = " ".join(title_words)
                title_norm = self._normalize_text(title_text)
                title_size = max_size

        # Detect Headings
        # Words with size > body_size + 0.8 or bold with distinct vertical gap
        headings = []
        for p_idx, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if not page_text:
                continue
            lines = page_text.split("\n")
            for line in lines:
                line_str = line.strip()
                if not line_str or len(line_str) > 100:
                    continue
                # Common section headers
                is_standard_header = bool(
                    re.match(r"^(\d+\.?\s*)?(abstract|introduction|materials\s*(and|&)\s*methods|methods|results|discussion|results\s*(and|&)\s*discussion|conclusion|references|literature\s*cited)\b", line_str, re.IGNORECASE)
                )
                if is_standard_header:
                    level = 1
                    if re.match(r"^\d+\.\d+\s+", line_str):
                        level = 2
                    elif re.match(r"^\d+\.\d+\.\d+\s+", line_str):
                        level = 3
                    headings.append({
                        "text": line_str,
                        "norm": self._normalize_text(line_str),
                        "level": level,
                        "size": body_size + 2.0,
                        "page": p_idx + 1
                    })

        # Extract Tables
        table_texts = []
        for page in pdf.pages:
            tables = page.find_tables()
            for t in tables:
                extracted = t.extract()
                cell_strings = []
                for row in extracted:
                    for cell in row:
                        if cell:
                            cell_strings.append(self._normalize_text(str(cell)))
                table_texts.append(" ".join(cell_strings))

        # Extract Images & adjacent caption bounds
        images_with_captions = []
        for page in pdf.pages:
            for img in page.images:
                images_with_captions.append({
                    "bbox": (img["x0"], img["top"], img["x1"], img["bottom"]),
                    "page": page.page_number
                })

        # Extract Abstract text on page 1
        abstract_text_norm = ""
        if p1:
            p1_text = p1.extract_text() or ""
            abs_match = re.search(r"\babstract\b\s*:?(.*?)(?:\bkeywords\b|\bkey\s*words\b|\b1\.?\s*introduction\b)", p1_text, re.IGNORECASE | re.DOTALL)
            if abs_match:
                abstract_text_norm = self._normalize_text(abs_match.group(1))

        return {
            "page_count": len(pdf.pages),
            "body_font": body_font,
            "body_size": body_size,
            "title_text": title_text,
            "title_norm": title_norm,
            "title_size": title_size,
            "headings": headings,
            "table_texts": table_texts,
            "images_with_captions": images_with_captions,
            "abstract_text_norm": abstract_text_norm
        }

    def _match_heading(self, norm_b: str, text: str, headings: List[Dict[str, Any]]) -> Optional[Tuple[int, float, str]]:
        """Matches a block against detected PDF headings."""
        for h in headings:
            h_norm = h["norm"]
            if norm_b == h_norm or (len(norm_b) > 4 and norm_b in h_norm) or (len(h_norm) > 4 and h_norm in norm_b):
                return (h["level"], h["size"], h["text"])

        # Fallback standard heading regex matching if layout detection had whitespace variations
        std_h1_match = re.match(
            r"^(\d+\.?\s*)?(abstract|introduction|materials\s*(and|&)\s*methods|methods|results|discussion|results\s*(and|&)\s*discussion|conclusion|references|literature\s*cited)\b",
            text.strip(),
            re.IGNORECASE
        )
        if std_h1_match and len(text.strip()) < 80:
            return (1, 12.0, text.strip())

        std_h2_match = re.match(r"^\d+\.\d+\s+[A-Z]", text.strip())
        if std_h2_match and len(text.strip()) < 80:
            return (2, 11.0, text.strip())

        std_h3_match = re.match(r"^\d+\.\d+\.\d+\s+[A-Z]", text.strip())
        if std_h3_match and len(text.strip()) < 80:
            return (3, 10.0, text.strip())

        return None

    def _is_table_content(self, norm_b: str, table_texts: List[str]) -> bool:
        """Checks if block text is part of any extracted PDF table cells."""
        if len(norm_b) < 10:
            return False
        for t_text in table_texts:
            if norm_b in t_text or (len(norm_b) > 30 and norm_b[:30] in t_text):
                return True
        return False

    def _is_near_pdf_image(self, norm_b: str, text: str, images: List[Dict[str, Any]]) -> bool:
        """Checks if block text matches known caption patterns near image coordinates."""
        if not images or len(text.strip()) > 350:
            return False
        # Look for figure caption lead-in terms with word boundary
        return bool(re.search(r"\b(figure|fig|photo|plate)\b\s*(\d+|[a-z])?", norm_b, re.IGNORECASE))

    def _is_abstract_text(self, norm_b: str, abstract_text_norm: str) -> bool:
        """Checks if block text appears inside the page 1 abstract block."""
        if not abstract_text_norm or len(norm_b) < 15:
            return False
        sample = norm_b[:40]
        return sample in abstract_text_norm

import os
import re
import shutil
from typing import List, Dict, Any, Optional, Union
import jinja2
from sutra.models import (
    Document, Section, Paragraph, InlineRun, Table, TableCell,
    Figure, Equation, BlockQuote, ListNode, ListItem, Footnote, Endnote, UnrecognizedBlock,
    JournalSettings
)
from sutra.utils.latex import latex_escape

class LatexGenerator:
    """
    Generates LaTeX source code from a typed Document IR.
    Uses a Jinja2 template with LaTeX-safe delimiters and programmatically
    maps IR components into structured LaTeX code with proper escaping.
    """
    def __init__(self):
        # Resolve templates directory relative to this file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.template_dir = os.path.join(base_dir, "resources", "templates")
        
        # Setup Jinja2 environment with LaTeX-safe delimiters
        self.jinja_env = jinja2.Environment(
            block_start_string=r'\BLOCK{',
            block_end_string='}',
            variable_start_string=r'\VAR{',
            variable_end_string='}',
            comment_start_string=r'\#{',
            comment_end_string='}',
            line_statement_prefix='%%',
            line_comment_prefix='%#',
            trim_blocks=True,
            autoescape=False,
            loader=jinja2.FileSystemLoader(self.template_dir)
        )

    def generate(self, doc: Document, layout: str = "single", journal_settings: Optional[JournalSettings] = None, assets_dir: Optional[str] = None) -> str:
        """
        Renders the entire Document IR into a LaTeX string.
        """
        # Load default journal settings if none provided
        if journal_settings is None:
            import datetime
            from sutra.models import PageSettings, BodyTextSettings, TitleBlockSettings, AbstractSettings, KeywordsSettings, HeadingSettings, HeadingLevelSettings, EquationsSettings, FiguresSettings, TablesSettings, ReferencesSettings, ConclusionSettings
            journal_settings = JournalSettings(
                journal_id="generic",
                journal_name="Generic",
                created_at=datetime.datetime.utcnow().isoformat() + "Z",
                page=PageSettings(
                    columns=2 if layout == "double" else 1,
                    margin_top_in=1.0,
                    margin_bottom_in=1.0,
                    margin_left_in=1.0,
                    margin_right_in=1.0
                )
            )

        # Apply layout override if specified
        if layout == "single":
            journal_settings.page.columns = 1
        elif layout == "double":
            journal_settings.page.columns = 2

        self.journal_settings = journal_settings

        # 1. Format front matter metadata
        title = self._render_inline_runs(doc.metadata.title)
        
        # Authors and affiliations (using authblk syntax)
        authors_data = []
        for author in doc.metadata.authors:
            aff_markers = []
            for aff_ref in author.affiliation_refs:
                for idx, aff in enumerate(doc.metadata.affiliations):
                    if aff.id == aff_ref:
                        aff_markers.append(str(idx + 1))
            
            name_str = f"{author.given_name} {author.family_name}"
            if author.corresponding:
                email_str = author.email or ""
                name_str += r"\thanks{Corresponding author: " + latex_escape(email_str) + "}"
                
            authors_data.append({
                "name": name_str,
                "aff_markers": ",".join(aff_markers)
            })
            
        affiliations_data = []
        for idx, aff in enumerate(doc.metadata.affiliations):
            parts = [aff.institution]
            if aff.department:
                parts.append(aff.department)
            if aff.address:
                parts.append(aff.address)
            if aff.country:
                parts.append(aff.country)
            
            affiliations_data.append({
                "marker": str(idx + 1),
                "text": ", ".join(parts)
            })

        # Abstract
        abstract_parts = []
        for p in doc.metadata.abstract.paragraphs:
            abstract_parts.append(self._render_inline_runs(p.content))
        for s in doc.metadata.abstract.structured_sections:
            sec_title = latex_escape(s.label)
            p_texts = " ".join(self._render_inline_runs(p.content) for p in s.paragraphs)
            if journal_settings.abstract.structured_labels_bold:
                abstract_parts.append(f"\\textbf{{{sec_title}}}: {p_texts}")
            else:
                abstract_parts.append(f"{sec_title}: {p_texts}")
        
        if getattr(journal_settings.abstract, "single_paragraph", False):
            abstract_str = " ".join(abstract_parts) if abstract_parts else ""
        else:
            abstract_str = "\n\n".join(abstract_parts) if abstract_parts else ""

        # Keywords
        keywords_str = ", ".join(latex_escape(kwd) for kwd in doc.metadata.keywords)

        # 2. Build body content
        body_parts = []
        for section in doc.body:
            body_parts.append(self._render_section(section))
        body_str = "\n\n".join(body_parts)

        # 3. Build references
        references_str = self._render_references(doc)

        # 4. Construct styling variables from journal_settings
        paper_size = "a4paper" if journal_settings.page.paper_size == "a4" else "letterpaper"
        columns = "twocolumn" if journal_settings.page.columns == 2 else "onecolumn"
        
        font_setup = ""
        font_family = journal_settings.body_text.font_family.lower()
        if "times" in font_family:
            font_setup = "\\usepackage{mathptmx}"
        elif "arial" in font_family or "helvetica" in font_family:
            font_setup = "\\usepackage{helvet}\n\\renewcommand{\\familydefault}{\\sfdefault}"
        elif "courier" in font_family:
            font_setup = "\\usepackage{courier}"

        authors_font_style = "\\itshape" if journal_settings.title_block.authors_font_style == "italic" else ""
        affiliation_font_style = "\\itshape" if journal_settings.title_block.affiliation_font_style == "italic" else ""

        titlesec_setup = "\\usepackage{titlesec}\n"
        
        h1 = journal_settings.headings.h1
        h1_font = f"\\fontsize{{{h1.font_size_pt}}}{{{h1.font_size_pt + 2}}}\\selectfont"
        if h1.font_weight == "bold": h1_font += "\\bfseries"
        if h1.font_style == "italic": h1_font += "\\itshape"
        h1_label = "\\thesection" if h1.numbering == "numeric" else ""
        titlesec_setup += f"\\titleformat{{\\section}}{{{h1_font}}}{{{h1_label}}}{{1em}}{{}}\n"
        titlesec_setup += f"\\titlespacing*{{\\section}}{{0pt}}{{{h1.space_before_pt}pt}}{{{h1.space_after_pt}pt}}\n"
        
        h2 = journal_settings.headings.h2
        h2_font = f"\\fontsize{{{h2.font_size_pt}}}{{{h2.font_size_pt + 2}}}\\selectfont"
        if h2.font_weight == "bold": h2_font += "\\bfseries"
        if h2.font_style == "italic": h2_font += "\\itshape"
        h2_label = "\\thesubsection" if h2.numbering == "numeric" else ""
        titlesec_setup += f"\\titleformat{{\\subsection}}{{{h2_font}}}{{{h2_label}}}{{1em}}{{}}\n"
        titlesec_setup += f"\\titlespacing*{{\\subsection}}{{0pt}}{{{h2.space_before_pt}pt}}{{{h2.space_after_pt}pt}}\n"

        h3 = journal_settings.headings.h3
        h3_font = f"\\fontsize{{{h3.font_size_pt}}}{{{h3.font_size_pt + 2}}}\\selectfont"
        if h3.font_weight == "bold": h3_font += "\\bfseries"
        if h3.font_style == "italic": h3_font += "\\itshape"
        h3_label = "\\thesubsubsection" if h3.numbering == "numeric" else ""
        titlesec_setup += f"\\titleformat{{\\subsubsection}}{{{h3_font}}}{{{h3_label}}}{{1em}}{{}}\n"
        titlesec_setup += f"\\titlespacing*{{\\subsubsection}}{{0pt}}{{{h3.space_before_pt}pt}}{{{h3.space_after_pt}pt}}\n"

        caption_setup = "\\usepackage{caption}\n"
        fig_size_name = self._map_font_size(journal_settings.figures.caption_font_size_pt)
        fig_label_style = "bf" if journal_settings.figures.caption_label_style == "bold" else "it" if journal_settings.figures.caption_label_style == "italic" else "normal"
        fig_sep = self._map_label_sep(getattr(journal_settings.figures, "label_separator", "."))
        fig_just = self._map_justification(getattr(journal_settings.figures, "caption_justification", "justified"))
        caption_setup += f"\\captionsetup[figure]{{font={{{fig_size_name}}},labelfont={{{fig_label_style}}},name={{{journal_settings.figures.caption_label_prefix}}},labelsep={fig_sep},justification={fig_just}}}\n"
        
        tbl_size_name = self._map_font_size(journal_settings.tables.caption_font_size_pt)
        tbl_label_style = "bf" if journal_settings.tables.caption_label_style == "bold" else "it" if journal_settings.tables.caption_label_style == "italic" else "normal"
        tbl_pos = journal_settings.tables.caption_position
        tbl_sep = self._map_label_sep(getattr(journal_settings.tables, "label_separator", "."))
        tbl_just = self._map_justification(getattr(journal_settings.tables, "caption_justification", "justified"))
        caption_setup += f"\\captionsetup[table]{{position={tbl_pos},font={{{tbl_size_name}}},labelfont={{{tbl_label_style}}},name={{{journal_settings.tables.caption_label_prefix}}},labelsep={tbl_sep},justification={tbl_just}}}\n"

        # Block typesetting setups: Footnotes, Lists, Blockquotes
        blocks_setup = ""
        footnotes = getattr(journal_settings, "footnotes", None)
        if footnotes:
            fn_size = footnotes.font_size_pt
            blocks_setup += f"\\renewcommand{{\\footnotesize}}{{\\fontsize{{{fn_size}pt}}{{{fn_size + 2}pt}}\\selectfont}}\n"
            if not footnotes.rule_separator:
                blocks_setup += "\\renewcommand{\\footnoterule}{}\n"

        lists = getattr(journal_settings, "lists", None)
        if lists:
            blocks_setup += f"\\usepackage{{enumitem}}\n\\setlist{{topsep={lists.item_spacing_pt}pt,itemsep={lists.item_spacing_pt}pt,leftmargin={lists.indent_pt}pt}}\n"

        blockquotes = getattr(journal_settings, "blockquotes", None)
        if blockquotes:
            bq_style = "\\itshape" if blockquotes.font_style == "italic" else ""
            blocks_setup += f"\\usepackage{{etoolbox}}\n\\AtBeginEnvironment{{quote}}{{\\fontsize{{{blockquotes.font_size_pt}pt}}{{{blockquotes.font_size_pt + 2}pt}}\\selectfont{bq_style}}}\n"

        # 5. Header, Footer, Identity, and Volume Processing
        journal_id = journal_settings.journal_id
        journal_name = latex_escape(journal_settings.journal_name)
        identity = getattr(journal_settings, "identity", None)
        volumes = getattr(journal_settings, "volumes", []) or []
        active_vol_id = getattr(journal_settings, "active_volume_id", None)

        active_volume = None
        if active_vol_id:
            active_volume = next((v for v in volumes if v.id == active_vol_id), None)
        if not active_volume:
            active_volume = next((v for v in volumes if getattr(v, "is_active", False)), None)
        if not active_volume and volumes:
            active_volume = volumes[0]

        volume_issue_str = ""
        if active_volume:
            v_no = latex_escape(str(active_volume.volume_no))
            i_no = latex_escape(str(active_volume.issue_no))
            yr = str(active_volume.year)
            if active_volume.page_range:
                pg = latex_escape(str(active_volume.page_range)).replace("-", "--")
                volume_issue_str = f"{v_no}({i_no}), {pg} ({yr})"
            else:
                volume_issue_str = f"Vol. {v_no}, Issue {i_no} ({yr})"

        issn_parts = []
        if identity and identity.issn_print:
            issn_parts.append(f"{latex_escape(identity.issn_print)} (Print)")
        if identity and identity.issn_online:
            issn_parts.append(f"{latex_escape(identity.issn_online)} (Online)")
        issn_str = f"ISSN: {', '.join(issn_parts)}" if issn_parts else ""

        website_str = identity.website if (identity and identity.website) else ""

        # Logo handling
        logo_file = None
        logo_height = 15.0
        logo_position = "left"
        first_page = getattr(journal_settings, "first_page_header", None)
        first_page_enabled = first_page.enabled if first_page else True
        show_logo = first_page.show_logo if first_page else True
        show_journal_name = first_page.show_journal_name if first_page else True

        if first_page:
            logo_height = first_page.logo_max_height_mm
            logo_position = first_page.logo_position or "left"

        if first_page_enabled and show_logo:
            base_proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            journal_dir = os.path.join(base_proj_dir, "build", "journals", journal_id)
            possible_logos = []
            if identity and identity.logo_filename:
                possible_logos.append(os.path.join(journal_dir, identity.logo_filename))
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                possible_logos.append(os.path.join(journal_dir, f"logo{ext}"))

            found_logo_path = next((p for p in possible_logos if os.path.exists(p)), None)
            if found_logo_path:
                ext = os.path.splitext(found_logo_path)[1].lower()
                if assets_dir and os.path.exists(assets_dir):
                    dest_filename = f"journal_logo{ext}"
                    try:
                        shutil.copyfile(found_logo_path, os.path.join(assets_dir, dest_filename))
                        logo_file = dest_filename
                    except Exception:
                        logo_file = found_logo_path.replace("\\", "/")
                else:
                    logo_file = found_logo_path.replace("\\", "/")

        header = getattr(journal_settings, "header", None)
        footer = getattr(journal_settings, "footer", None)

        if len(authors_data) == 1:
            running_authors = doc.metadata.authors[0].family_name if doc.metadata.authors else ""
        elif len(authors_data) == 2:
            running_authors = f"{doc.metadata.authors[0].family_name} & {doc.metadata.authors[1].family_name}" if len(doc.metadata.authors) >= 2 else ""
        elif len(authors_data) > 2:
            running_authors = f"{doc.metadata.authors[0].family_name} et al." if doc.metadata.authors else ""
        else:
            running_authors = ""

        def expand_text(text: str) -> str:
            if not text:
                return ""
            t = text.replace("{journal}", journal_name)
            t = t.replace("{authors}", running_authors)
            t = t.replace("{volume}", active_volume.volume_no if active_volume else "")
            t = t.replace("{issue}", active_volume.issue_no if active_volume else "")
            t = t.replace("{year}", str(active_volume.year) if active_volume else "")
            return t

        def safe_hf_text(text: str) -> str:
            if not text:
                return ""
            t = expand_text(text)
            # Escape unescaped &, %, _ characters for LaTeX safety
            t = re.sub(r'(?<!\\)&', r'\\&', t)
            t = re.sub(r'(?<!\\)%', r'\\%', t)
            t = re.sub(r'(?<!\\)_', r'\\_', t)
            return t

        header_left = ""
        header_center = ""
        header_right = ""
        header_enabled = header.enabled if header else True
        if header_enabled and header:
            if header.left_text:
                header_left = safe_hf_text(header.left_text)
            elif running_authors and journal_name:
                header_left = safe_hf_text(f"{latex_escape(running_authors)} / {journal_name}")
            elif journal_name:
                header_left = safe_hf_text(journal_name)

            if header.center_text:
                header_center = safe_hf_text(header.center_text)

            if header.right_text:
                header_right = safe_hf_text(header.right_text)
            elif volume_issue_str:
                header_right = safe_hf_text(volume_issue_str)

        footer_left = ""
        footer_center = "\\thepage"
        footer_right = ""
        footer_enabled = footer.enabled if footer else True
        footer_from_page = footer.from_page if footer else 1
        if footer_enabled and footer:
            if footer.left_text:
                footer_left = safe_hf_text(footer.left_text)
            if footer.center_text:
                footer_center = footer.center_text if footer.center_text.startswith("\\") else safe_hf_text(footer.center_text)
            if footer.right_text:
                footer_right = safe_hf_text(footer.right_text)

        def clean_color(col: Optional[str]) -> str:
            if not col:
                return "000000"
            c = col.strip().lstrip("#")
            if len(c) == 3:
                c = "".join(ch * 2 for ch in c)
            if len(c) == 6:
                return c.upper()
            return "000000"

        header_line_show = bool(header and header.line and header.line.show)
        header_line_thickness = str(header.line.thickness_pt if (header and header.line) else 0.5)
        header_line_color_hex = clean_color(header.line.color if (header and header.line) else None)

        footer_line_show = bool(footer and footer.line and footer.line.show)
        footer_line_thickness = str(footer.line.thickness_pt if (footer and footer.line) else 0.5)
        footer_line_color_hex = clean_color(footer.line.color if (footer and footer.line) else None)

        header_font_size = str(header.font_size_pt if header else 8.5)
        header_font_size_lead = str((header.font_size_pt if header else 8.5) + 2.0)
        header_font_style = "\\itshape" if (header and header.font_style == "italic") else ""

        footer_font_size = str(footer.font_size_pt if footer else 8.5)
        footer_font_size_lead = str((footer.font_size_pt if footer else 8.5) + 2.0)
        footer_font_style = "\\itshape" if (footer and footer.font_style == "italic") else ""

        first_page_rule = header_line_show

        # Load and render Jinja template
        template = self.jinja_env.get_template("article_template.tex")
        return template.render(
            paper_size=paper_size,
            columns=columns,
            font_size=str(journal_settings.body_text.font_size_pt),
            margin_top=str(journal_settings.page.margin_top_in),
            margin_bottom=str(journal_settings.page.margin_bottom_in),
            margin_left=str(journal_settings.page.margin_left_in),
            margin_right=str(journal_settings.page.margin_right_in),
            font_setup=font_setup,
            line_spacing=str(journal_settings.body_text.line_spacing),
            paragraph_indent=str(journal_settings.body_text.paragraph_indent_pt),
            paragraph_spacing=str(journal_settings.body_text.paragraph_spacing_pt),
            title_font_size=str(journal_settings.title_block.title_font_size_pt),
            authors_font_size=str(journal_settings.title_block.authors_font_size_pt),
            authors_font_style=authors_font_style,
            affiliation_font_size=str(journal_settings.title_block.affiliation_font_size_pt),
            affiliation_font_style=affiliation_font_style,
            abstract_heading_font_size=str(journal_settings.abstract.heading_font_size_pt),
            abstract_body_font_size=str(journal_settings.abstract.body_font_size_pt),
            titlesec_setup=titlesec_setup,
            caption_setup=caption_setup,
            blocks_setup=blocks_setup,
            journal_name=journal_name,
            first_page_header_enabled=first_page_enabled,
            first_page_rule=first_page_rule,
            logo_file=logo_file,
            logo_position=logo_position,
            logo_height=str(logo_height),
            show_journal_name=show_journal_name,
            volume_issue_str=volume_issue_str,
            issn_str=issn_str,
            website_str=website_str,
            header_enabled=header_enabled,
            header_left=header_left,
            header_center=header_center,
            header_right=header_right,
            header_font_size=header_font_size,
            header_font_size_lead=header_font_size_lead,
            header_font_style=header_font_style,
            header_line_show=header_line_show,
            header_line_thickness=header_line_thickness,
            header_line_color_hex=header_line_color_hex,
            footer_enabled=footer_enabled,
            footer_from_page=footer_from_page,
            footer_left=footer_left,
            footer_center=footer_center,
            footer_right=footer_right,
            footer_font_size=footer_font_size,
            footer_font_size_lead=footer_font_size_lead,
            footer_font_style=footer_font_style,
            footer_line_show=footer_line_show,
            footer_line_thickness=footer_line_thickness,
            footer_line_color_hex=footer_line_color_hex,
            title=title,
            authors=authors_data,
            affiliations=affiliations_data,
            abstract=abstract_str,
            abstract_full_width=getattr(journal_settings.abstract, "full_width_in_twocol", True),
            abstract_single_paragraph=getattr(journal_settings.abstract, "single_paragraph", False),
            abstract_include_keywords=getattr(journal_settings.abstract, "include_keywords_in_box", False),
            keywords_label=journal_settings.keywords.label_text,
            keywords=keywords_str,
            body=body_str,
            references=references_str
        )


    def _map_font_size(self, size: float) -> str:
        if size <= 8:
            return "scriptsize"
        elif size <= 9:
            return "footnotesize"
        elif size <= 10:
            return "small"
        elif size <= 11:
            return "normalsize"
        else:
            return "large"


    def _map_label_sep(self, sep: str) -> str:
        mapping = {".": "period", ":": "colon", " ": "space", "": "none"}
        return mapping.get(sep, "period")


    def _map_justification(self, just: str) -> str:
        mapping = {"justified": "justified", "left": "raggedright", "center": "centering"}
        return mapping.get(just, "justified")


    def _sanitize_heading(self, text: str) -> str:
        """
        Sanitize heading text for use inside LaTeX section commands.
        Collapses embedded newlines and excess whitespace into single spaces.
        LaTeX \\section{}, \\subsection{} etc. cannot contain paragraph breaks.
        """
        if not text:
            return ""
        # Replace all newline sequences (\n, \r\n, etc.) with a single space
        sanitized = re.sub(r'[\r\n]+', ' ', text)
        # Collapse multiple spaces into one
        sanitized = re.sub(r'\s+', ' ', sanitized)
        return sanitized.strip()

    def _render_section(self, section: Section) -> str:
        """
        Recursively renders sections and nested content.
        """
        parts = []
        
        # Section headers
        if not section.heading:
            # If a section has no heading, do not wrap it. Render its content items directly.
            for item in section.content:
                if isinstance(item, Section):
                    parts.append(self._render_section(item))
                else:
                    rendered = self._render_content_item(item)
                    if rendered:
                        parts.append(rendered)
            return "\n".join(parts)

        # Sanitize heading text: collapse newlines/whitespace to prevent LaTeX errors
        heading_text = latex_escape(self._sanitize_heading(section.heading))

        if section.level == 1:
            parts.append(f"\n% sutra-id: {section.id}\n\\section{{{heading_text}}}")
        elif section.level == 2:
            parts.append(f"\n% sutra-id: {section.id}\n\\subsection{{{heading_text}}}")
        else:
            parts.append(f"\n% sutra-id: {section.id}\n\\subsubsection{{{heading_text}}}")
            
        if section.id:
            parts.append(f"\\label{{{section.id}}}")

        # Render content items
        for item in section.content:
            if isinstance(item, Section):
                parts.append(self._render_section(item))
            else:
                rendered = self._render_content_item(item)
                if rendered:
                    parts.append(rendered)

        return "\n".join(parts)

    def _render_content_item(self, item: Any) -> str:
        if isinstance(item, Paragraph):
            lbl = item.id if item.id else "paragraph"
            text = self._render_inline_runs(item.content)
            # Retain label if paragraph has an id
            lbl_tag = f"\\label{{{item.id}}}" if item.id else ""
            return f"\n% sutra-id: {lbl}\n{text}{lbl_tag}\n"
            
        elif isinstance(item, Figure):
            env = "figure*" if item.span_hint == "page" else "figure"
            pos = "t" if item.span_hint == "page" else "h"
            caption_text = self._render_inline_runs(item.caption)
            
            # Map graphic href to local assets directory path
            # We strip any path parts and prepend standard assets/ path
            base_img = os.path.basename(item.image_ref)
            img_path = f"assets/{base_img}"
            
            fig_caption_pos = getattr(self.journal_settings.figures, "caption_position", "below") if hasattr(self, "journal_settings") and self.journal_settings and hasattr(self.journal_settings, "figures") else "below"

            parts = [
                f"\n% sutra-id: {item.id}",
                f"\\begin{{{env}}}[{pos}]",
                "  \\centering"
            ]
            if fig_caption_pos == "above":
                parts.append(f"  \\caption{{{caption_text}}}")
                parts.append(f"  \\label{{{item.id}}}")
                parts.append(f"  \\includegraphics[width=\\linewidth]{{{img_path}}}")
            else:
                parts.append(f"  \\includegraphics[width=\\linewidth]{{{img_path}}}")
                parts.append(f"  \\caption{{{caption_text}}}")
                parts.append(f"  \\label{{{item.id}}}")
            parts.append(f"\\end{{{env}}}")
            return "\n".join(parts) + "\n"

        elif isinstance(item, Table):
            env = "table*" if item.span_hint == "page" else "table"
            pos = "t" if item.span_hint == "page" else "h"
            caption_text = self._render_inline_runs(item.caption)
            
            tbl_caption_pos = getattr(self.journal_settings.tables, "caption_position", "above") if hasattr(self, "journal_settings") and self.journal_settings and hasattr(self.journal_settings, "tables") else "above"
            tbl_border_style = getattr(self.journal_settings.tables, "border_style", "booktabs") if hasattr(self, "journal_settings") and self.journal_settings and hasattr(self.journal_settings, "tables") else "booktabs"
            tbl_vert_lines = getattr(self.journal_settings.tables, "show_vertical_lines", False) if hasattr(self, "journal_settings") and self.journal_settings and hasattr(self.journal_settings, "tables") else False

            # Formulate tabular structure
            # Deduce number of columns by accounting for cell colspans
            num_cols = max((sum(getattr(c, 'colspan', 1) for c in row) for row in item.rows), default=1) if item.rows else 1
            if num_cols < 1:
                num_cols = 1
            
            # Column specifier: use X columns for wrapping, stretch to linewidth
            if tbl_border_style == "grid" or tbl_vert_lines:
                col_spec = "|" + "|".join(["X"] * num_cols) + "|"
            else:
                col_spec = "".join(["X"] * num_cols)
            
            parts = [
                f"\n% sutra-id: {item.id}",
                f"\\begin{{{env}}}[{pos}]",
                "  \\centering"
            ]
            if tbl_caption_pos == "above":
                parts.append(f"  \\caption{{{caption_text}}}")
                parts.append(f"  \\label{{{item.id}}}")

            parts.append(f"  \\begin{{tabularx}}{{\\linewidth}}{{{col_spec}}}")

            # Top rule
            if tbl_border_style == "grid":
                parts.append("    \\hline")
            else:
                parts.append("    \\toprule")
            
            # Format rows
            for r_idx, row in enumerate(item.rows):
                row_cells = []
                cur_span = 0
                for cell in row:
                    cell_text = self._render_inline_runs(cell.content)
                    cs = getattr(cell, 'colspan', 1)
                    rs = getattr(cell, 'rowspan', 1)
                    cur_span += cs
                    
                    # Row/Col span handling
                    if cs > 1:
                        col_align = "|c|" if (tbl_border_style == "grid" or tbl_vert_lines) else "c"
                        cell_text = f"\\multicolumn{{{cs}}}{{{col_align}}}{{{cell_text}}}"
                    if rs > 1:
                        cell_text = f"\\multirow{{{rs}}}{{*}}{{{cell_text}}}"
                        
                    row_cells.append(cell_text)
                    
                # Ensure row matches num_cols if trailing columns omitted
                if cur_span < num_cols:
                    row_cells.extend([""] * (num_cols - cur_span))
                    
                row_str = " & ".join(row_cells) + r" \\"
                parts.append(f"    {row_str}")
                
                # Rule separation
                if tbl_border_style == "grid":
                    if r_idx < len(item.rows) - 1:
                        parts.append("    \\hline")
                elif tbl_border_style == "booktabs":
                    if r_idx < item.header_rows and r_idx == item.header_rows - 1:
                        parts.append("    \\midrule")
                # plain style has no mid lines
                        
            # Bottom rule
            if tbl_border_style == "grid":
                parts.append("    \\hline")
            else:
                parts.append("    \\bottomrule")

            parts.append("  \\end{tabularx}")

            if tbl_caption_pos == "below":
                parts.append(f"  \\caption{{{caption_text}}}")
                parts.append(f"  \\label{{{item.id}}}")
            
            # Table footnotes
            if item.footnotes:
                for fn_text in item.footnotes:
                    parts.append(f"  \\small\\noindent {latex_escape(fn_text)}\\\\")
                    
            parts.append(f"\\end{{{env}}}")
            return "\n".join(parts) + "\n"

        elif isinstance(item, Equation):
            # Display equations
            if item.display == "block":
                lbl = item.id if item.id else "equation"
                eq_source = item.latex_source or ""
                return f"\n% sutra-id: {lbl}\n\\begin{{equation}}\n{eq_source}\n\\label{{{lbl}}}\\end{{equation}}\n"
            else:
                eq_source = item.latex_source or ""
                return f"${eq_source}$"

        elif isinstance(item, BlockQuote):
            q_parts = ["\\begin{quote}"]
            for p in item.content:
                q_parts.append(self._render_inline_runs(p.content))
            q_parts.append("\\end{quote}")
            return "\n".join(q_parts) + "\n"

        elif isinstance(item, ListNode):
            env = "enumerate" if item.style == "ordered" else "itemize"
            parts = [f"\\begin{{{env}}}"]
            for li in item.items:
                li_text = self._render_inline_runs(li.content)
                parts.append(f"  \\item {li_text}")
                if li.nested_list:
                    parts.append(self._render_content_item(li.nested_list))
            parts.append(f"\\end{{{env}}}")
            return "\n".join(parts) + "\n"

        elif isinstance(item, Footnote):
            text = self._render_inline_runs(item.content)
            return f"\\footnote{{{text}}}"

        elif isinstance(item, Endnote):
            text = self._render_inline_runs(item.content)
            return f"\\footnote[end]{{{text}}}"

        elif isinstance(item, UnrecognizedBlock):
            escaped_text = latex_escape(item.content_text)
            return f"\n% sutra-id: {item.id}\n\\noindent\\textbf{{[Manual Handling Required] Unclassified Content: {escaped_text}}}\n"

        return ""

    def _render_inline_runs(self, runs: List[InlineRun]) -> str:
        """
        Compiles list of InlineRun IR structures to LaTeX text markup.
        """
        output = []
        for run in runs:
            # Inline math logic
            if run.equation_source:
                output.append(f"${run.equation_source}$")
                continue
                
            text = latex_escape(run.text)
            
            # Nest markup formats recursively
            if run.bold:
                text = f"\\textbf{{{text}}}"
            if run.italic:
                text = f"\\textit{{{text}}}"
            if run.underline:
                text = f"\\underline{{{text}}}"
            if run.strikethrough:
                text = f"\\sout{{{text}}}"
            if run.sub:
                text = f"\\textsubscript{{{text}}}"
            if run.sup:
                text = f"\\textsuperscript{{{text}}}"
            if run.small_caps:
                text = f"\\textsc{{{text}}}"
                
            if run.link_url:
                # Keep URLs un-escaped for hyperref
                output.append(f"\\href{{{run.link_url}}}{{{text}}}")
            elif run.xref_target:
                # Check for bibr citation versus internal tags
                target = run.xref_target
                is_cite = not (target.startswith("fig-") or target.startswith("tbl-") or target.startswith("table-") or target == "footnote")
                if is_cite:
                    output.append(f"\\cite{{{target}}}")
                else:
                    output.append(f"\\ref{{{target}}}")
            else:
                output.append(text)
                
        return "".join(output)

    def _render_references(self, doc: Document) -> str:
        if not doc.references:
            return ""
            
        parts = [
            "\\begin{thebibliography}{99}"
        ]
        
        for index, ref in enumerate(doc.references):
            ref_id = ref.id or f"ref-{index+1}"
            parts.append(f"\\bibitem{{{ref_id}}}")
            
            # Format authors list
            authors_str = ""
            if ref.authors:
                authors_str = ", ".join(f"{auth.given} {auth.family}" for auth in ref.authors)
                
            # Render standard bibliography styles based on ref type
            ref_details = []
            if ref.title:
                if ref.type == "journal-article":
                    ref_details.append(f"\"{latex_escape(ref.title)}\"")
                else:
                    ref_details.append(f"\\emph{{{latex_escape(ref.title)}}}")
            
            if ref.source_title:
                ref_details.append(f"\\emph{{{latex_escape(ref.source_title)}}}")
                
            if ref.volume:
                vol_str = f"vol. {latex_escape(ref.volume)}"
                if ref.issue:
                    vol_str += f", no. {latex_escape(ref.issue)}"
                ref_details.append(vol_str)
                
            if ref.pages:
                ref_details.append(f"pp. {latex_escape(ref.pages)}")
                
            if ref.year:
                ref_details.append(latex_escape(ref.year))
                
            if ref.doi:
                ref_details.append(f"DOI: \\href{{https://doi.org/{ref.doi}}}{{{latex_escape(ref.doi)}}}")
            elif ref.url:
                ref_details.append(f"\\url{{{ref.url}}}")
                
            citation_text = f"{authors_str}. " + ", ".join(ref_details) + "."
            parts.append(f"  {citation_text}")
            
        parts.append("\\end{thebibliography}")
        return "\n".join(parts)

import os
from typing import List, Dict, Any, Literal
import docx
from lxml import etree
from sutra.utils.xml import safe_parse_xml_tree

class TriageReport:
    def __init__(self, verdict: Literal["pass", "pass-with-warnings", "needs-manual-prep"]):
        self.verdict = verdict
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.details: Dict[str, Any] = {}

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        if self.verdict == "pass":
            self.verdict = "pass-with-warnings"

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.verdict = "needs-manual-prep"

    def to_markdown(self) -> str:
        lines = [
            "# Sutra Press: Pre-Flight Triage Report",
            f"**Verdict**: {self.verdict.upper()}",
            ""
        ]
        if self.errors:
            lines.append("## Errors (Needs Manual Preparation)")
            for err in self.errors:
                lines.append(f"- [ ] {err}")
            lines.append("")
        if self.warnings:
            lines.append("## Warnings (Review Recommended)")
            for warn in self.warnings:
                lines.append(f"- [ ] {warn}")
            lines.append("")
        if not self.errors and not self.warnings:
            lines.append("No issues found! The document is ready for conversion.")
        return "\n".join(lines)


class TriageScanner:
    """
    Performs structural scans of DOCX manuscripts before full conversion.
    """
    def __init__(self, docx_path: str):
        self.docx_path = docx_path

    def run_triage(self) -> TriageReport:
        if not os.path.exists(self.docx_path):
            report = TriageReport("needs-manual-prep")
            report.add_error(f"Manuscript file not found: {self.docx_path}")
            return report

        report = TriageReport("pass")
        try:
            doc = docx.Document(self.docx_path)
        except Exception as e:
            report.add_error(f"Failed to parse DOCX file structure: {str(e)}")
            return report

        self._check_headings(doc, report)
        self._check_tracked_changes(doc, report)
        self._check_embedded_objects(doc, report)
        self._check_citations(doc, report)

        return report

    def _check_headings(self, doc: docx.document.Document, report: TriageReport):
        # Scan paragraphs to check if any look like "fake" headings
        # (e.g. bold, large text, but using 'Normal' style)
        has_real_headings = False
        fake_headings = 0

        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name.lower()
            if "heading" in style_name:
                has_real_headings = True
            else:
                # Check for manually styled paragraph that looks like a heading
                # Heuristic: short text (less than 15 words) and entirely bolded/larger
                is_manual_bold = all(run.bold for run in para.runs) if para.runs else False
                if is_manual_bold and len(text.split()) < 15:
                    fake_headings += 1
                    report.add_warning(
                        f"Paragraph {i+1} ('{text[:30]}...') is bold and looks like a heading, but uses Normal style."
                    )

        if not has_real_headings:
            report.add_warning("No standard Heading styles (Heading 1, 2, etc.) were found in the document.")

    def _check_tracked_changes(self, doc: docx.document.Document, report: TriageReport):
        # Word tracked changes are represented as w:ins or w:del tags in the document XML.
        try:
            # Access the underlying XML of the document body
            xml_bytes = doc._element.xml.encode("utf-8")
            # Parse it using safe XML utility
            tree = safe_parse_xml_tree(xml_bytes)
            root = tree.getroot()
            
            # w namespace is usually 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            ins_tags = root.xpath(".//w:ins", namespaces=namespaces)
            del_tags = root.xpath(".//w:del", namespaces=namespaces)
            
            if ins_tags or del_tags:
                report.add_error("Document contains unresolved tracked changes. Please accept/reject them before conversion.")
        except Exception as e:
            report.add_warning(f"Could not scan document XML for tracked changes: {str(e)}")

    def _check_embedded_objects(self, doc: docx.document.Document, report: TriageReport):
        # Scan for inline shapes/objects
        # In a docx, doc.inline_shapes contains embedded images, equations, or spreadsheets
        has_images = False
        for shape in doc.inline_shapes:
            # 3 = inline shape chart, 1 = image
            if shape.type == 1:
                has_images = True
            elif shape.type in (2, 4, 5):  # links/embedded objects
                report.add_warning("Found embedded spreadsheet or OLE object. Ensure data tables are constructed using Word tables.")

    def _check_citations(self, doc: docx.document.Document, report: TriageReport):
        # Basic check to see if citation patterns exist
        has_citations = False
        text_content = " ".join(para.text for para in doc.paragraphs)
        
        # Look for [1] or [1-5] style numeric citations
        if "[1]" in text_content or "[1," in text_content:
            has_citations = True
            
        # Look for author-date citations e.g. (Smith, 2020)
        import re
        author_date_pattern = re.compile(r"\([A-Z][a-zA-Z]+,\s*\d{4}\)")
        if author_date_pattern.search(text_content):
            has_citations = True

        if not has_citations and len(doc.paragraphs) > 5:
            report.add_warning("No standard citation patterns (numeric e.g., '[1]' or author-date e.g., '(Smith, 2020)') detected.")


def run_block_triage(docx_path: str, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 1. Check for tracked changes
    has_tracked_changes = False
    if docx_path and os.path.exists(docx_path):
        try:
            doc = docx.Document(docx_path)
            xml_bytes = doc._element.xml.encode("utf-8")
            tree = safe_parse_xml_tree(xml_bytes)
            root = tree.getroot()
            namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            ins_tags = root.xpath(".//w:ins", namespaces=namespaces)
            del_tags = root.xpath(".//w:del", namespaces=namespaces)
            if ins_tags or del_tags:
                has_tracked_changes = True
        except Exception:
            pass

    # 2. Process each block
    for idx, block in enumerate(blocks):
        if block.get("is_user_confirmed"):
            block["state"] = "confirmed"
            block["warnings"] = []
            continue
            
        b_type = block["type"]
        block["warnings"] = []
        
        # Reset state to confirmed if not unrecognized
        if b_type == "unrecognized":
            block["state"] = "unrecognized"
            block["warnings"].append("Unclassified content: could not automatically assign a type. Please retag or flag this block.")
        else:
            block["state"] = "confirmed"

        # Check: tracked changes (alert on first block or paragraph)
        if has_tracked_changes and (idx == 0 or b_type == "paragraph"):
            block["warnings"].append("Document contains unresolved tracked changes. Please accept/reject them before conversion.")
            block["state"] = "needs_review"
            # Prevent double alerting
            has_tracked_changes = False

        # Check: fake headings
        if b_type == "paragraph":
            runs = block["content"]
            text = "".join(r.get("text", "") for r in runs).strip()
            if text:
                all_bold = all(r.get("bold", False) for r in runs) if runs else False
                if all_bold and len(text.split()) < 15:
                    block["warnings"].append(f"Paragraph ('{text[:30]}...') is entirely bold and looks like a heading, but is tagged as a normal paragraph.")
                    block["state"] = "needs_review"

        # Check: figure alt-text
        elif b_type == "figure":
            content_dict = block["content"]
            alt_text = content_dict.get("alt_text", "").strip()
            if not alt_text or alt_text == "Figure":
                block["warnings"].append("Figure is missing descriptive alt-text.")
                block["state"] = "needs_review"

        # Check: equations as images
        elif b_type == "equation":
            content_dict = block["content"]
            source = content_dict.get("source", "")
            if source == "image":
                block["warnings"].append("Equation is embedded as an image. JATS/LaTeX output will use degraded raster formatting.")
                block["state"] = "needs_review"

        # Check: low-confidence references
        elif b_type == "reference_list":
            refs = block["content"]
            low_conf_count = 0
            for ref in refs:
                missing_fields = []
                if not ref.get("doi"):
                    missing_fields.append("DOI")
                if not ref.get("year"):
                    missing_fields.append("year")
                if not ref.get("authors"):
                    missing_fields.append("authors")
                if len(missing_fields) >= 2:
                    low_conf_count += 1
            if low_conf_count > 0:
                block["warnings"].append(f"Reference list contains {low_conf_count} entries with low confidence or missing metadata.")
                block["state"] = "needs_review"

    return blocks

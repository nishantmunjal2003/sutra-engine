import re
from typing import List, Dict, Any, Union, Optional
from lxml import etree
from sutra.models import (
    Document, Metadata, Section, Paragraph, InlineRun,
    Author, Affiliation, Figure, Table, TableCell,
    Footnote, Endnote, BlockQuote, ListNode, ListItem,
    Sidebar, Equation, TrackedChangeMarker, UnrecognizedBlock,
    Reference, ReferenceAuthor, Citation
)

NS_XLINK = "http://www.w3.org/1999/xlink"
NS_MML = "http://www.w3.org/1998/Math/MathML"

NSMAP = {
    "xlink": NS_XLINK,
    "mml": NS_MML,
}

class JatsGenerator:
    """
    Generates NISO JATS 1.3 XML from a typed Document IR using lxml.
    Enforces XML well-formedness and correct structural tag nesting.
    """
    def __init__(self):
        pass

    def generate(self, doc: Document) -> bytes:
        # Create root <article>
        article = etree.Element("article", nsmap=NSMAP)
        article.set("dtd-version", "1.3")
        article.set("article-type", doc.metadata.article_type or "research-article")
        
        # 1. Build <front>
        front = etree.SubElement(article, "front")
        self._build_front(doc, front)
        
        # 2. Build <body>
        body = etree.SubElement(article, "body")
        self._build_body(doc, body)
        
        # 3. Build <back>
        back = etree.SubElement(article, "back")
        self._build_back(doc, back)
        
        # Serialize to bytes
        # xml_declaration=True ensures it writes <?xml version="1.0" encoding="UTF-8"?>
        return etree.tostring(
            article,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8"
        )

    def _parse_date(self, date_str: str) -> Dict[str, str]:
        # Try YYYY-MM-DD
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str.strip())
        if m:
            return {"year": m.group(1), "month": m.group(2), "day": m.group(3)}
        # Try YYYY-MM
        m = re.match(r"^(\d{4})-(\d{2})$", date_str.strip())
        if m:
            return {"year": m.group(1), "month": m.group(2)}
        # Try YYYY
        m = re.match(r"^(\d{4})$", date_str.strip())
        if m:
            return {"year": m.group(1)}
        # Default fallback - assume the string contains a year somewhere or just use it as year
        m = re.search(r"(\d{4})", date_str)
        if m:
            return {"year": m.group(1)}
        return {"year": date_str}

    def _append_date_element(self, parent: etree._Element, tag_name: str, date_str: str, date_type: Optional[str] = None):
        parsed = self._parse_date(date_str)
        date_el = etree.SubElement(parent, tag_name)
        if date_type:
            date_el.set("date-type", date_type)
        if "day" in parsed:
            day_el = etree.SubElement(date_el, "day")
            day_el.text = parsed["day"]
        if "month" in parsed:
            month_el = etree.SubElement(date_el, "month")
            month_el.text = parsed["month"]
        year_el = etree.SubElement(date_el, "year")
        year_el.text = parsed["year"]

    def _build_front(self, doc: Document, parent: etree._Element):
        # 1. <journal-meta>
        j_meta = etree.SubElement(parent, "journal-meta")
        
        # Add required <journal-id> (JATS 1.3 publishing expectation)
        j_id = etree.SubElement(j_meta, "journal-id")
        j_id.set("journal-id-type", "publisher-id")
        j_id.text = "sutra-press"
        
        j_title_group = etree.SubElement(j_meta, "journal-title-group")
        j_title = etree.SubElement(j_title_group, "journal-title")
        j_title.text = doc.metadata.journal_meta.title if doc.metadata.journal_meta else "Journal Name"
        
        issn_val = doc.metadata.journal_meta.issn if (doc.metadata.journal_meta and doc.metadata.journal_meta.issn) else "0000-0000"
        issn = etree.SubElement(j_meta, "issn")
        issn.text = issn_val
            
        if doc.metadata.journal_meta and doc.metadata.journal_meta.publisher:
            publisher = etree.SubElement(j_meta, "publisher")
            pub_name = etree.SubElement(publisher, "publisher-name")
            pub_name.text = doc.metadata.journal_meta.publisher

        # 2. <article-meta>
        a_meta = etree.SubElement(parent, "article-meta")
        
        # <title-group>
        title_group = etree.SubElement(a_meta, "title-group")
        a_title = etree.SubElement(title_group, "article-title")
        self._append_inline_runs(a_title, doc.metadata.title)
        
        # <contrib-group>
        if doc.metadata.authors:
            contrib_group = etree.SubElement(a_meta, "contrib-group")
            for author in doc.metadata.authors:
                contrib = etree.SubElement(contrib_group, "contrib")
                contrib.set("contrib-type", "author")
                if author.corresponding:
                    contrib.set("corresp", "yes")
                    
                # 1. contrib-id (ORCID) must come first in JATS contrib sequence
                if author.orcid:
                    contrib_id = etree.SubElement(contrib, "contrib-id")
                    contrib_id.set("contrib-id-type", "orcid")
                    contrib_id.text = author.orcid

                # 2. name
                name = etree.SubElement(contrib, "name")
                surname = etree.SubElement(name, "surname")
                surname.text = author.family_name
                given = etree.SubElement(name, "given-names")
                given.text = author.given_name
                
                # 3. email
                if author.email:
                    email = etree.SubElement(contrib, "email")
                    email.text = author.email
                    
                # 4. xref
                for aff_ref in author.affiliation_refs:
                    xref = etree.SubElement(contrib, "xref")
                    xref.set("ref-type", "aff")
                    xref.set("rid", aff_ref)

        # <aff>
        for affiliation in doc.metadata.affiliations:
            aff = etree.SubElement(a_meta, "aff")
            aff.set("id", affiliation.id)
            institution = etree.SubElement(aff, "institution")
            institution.text = affiliation.institution
            if affiliation.department or affiliation.address or affiliation.country:
                addr = etree.SubElement(aff, "addr-line")
                parts = [p for p in (affiliation.department, affiliation.address, affiliation.country) if p]
                addr.text = ", ".join(parts)

        # <pub-date> (REQUIRED inside <article-meta> per schema sequence)
        pub_date = etree.SubElement(a_meta, "pub-date")
        pub_date.set("publication-format", "electronic")
        pub_date.set("date-type", "pub")
        year_el = etree.SubElement(pub_date, "year")
        year_val = "2026"
        if doc.metadata.dates and doc.metadata.dates.accepted:
            year_val = self._parse_date(doc.metadata.dates.accepted).get("year", "2026")
        elif doc.metadata.dates and doc.metadata.dates.received:
            year_val = self._parse_date(doc.metadata.dates.received).get("year", "2026")
        year_el.text = year_val

        # <volume> and <issue>
        if doc.metadata.journal_meta:
            if doc.metadata.journal_meta.volume:
                vol = etree.SubElement(a_meta, "volume")
                vol.text = doc.metadata.journal_meta.volume
            if doc.metadata.journal_meta.issue:
                iss = etree.SubElement(a_meta, "issue")
                iss.text = doc.metadata.journal_meta.issue

        # <history>
        if doc.metadata.dates and (doc.metadata.dates.received or doc.metadata.dates.revised or doc.metadata.dates.accepted):
            history_el = etree.SubElement(a_meta, "history")
            if doc.metadata.dates.received:
                self._append_date_element(history_el, "date", doc.metadata.dates.received, "received")
            if doc.metadata.dates.revised:
                self._append_date_element(history_el, "date", doc.metadata.dates.revised, "revised")
            if doc.metadata.dates.accepted:
                self._append_date_element(history_el, "date", doc.metadata.dates.accepted, "accepted")

        # <permissions>
        if doc.metadata.license:
            perms = etree.SubElement(a_meta, "permissions")
            license_el = etree.SubElement(perms, "license")
            if doc.metadata.license.type:
                license_el.set("license-type", doc.metadata.license.type)
            if doc.metadata.license.url:
                license_el.set(f"{{{NS_XLINK}}}href", doc.metadata.license.url)
            lic_p = etree.SubElement(license_el, "license-p")
            lic_p.text = f"Licensed under {doc.metadata.license.type}."

        # <abstract>
        if doc.metadata.abstract.paragraphs or doc.metadata.abstract.structured_sections:
            ab = etree.SubElement(a_meta, "abstract")
            for p in doc.metadata.abstract.paragraphs:
                p_el = etree.SubElement(ab, "p")
                self._append_inline_runs(p_el, p.content)
            for s in doc.metadata.abstract.structured_sections:
                sec_el = etree.SubElement(ab, "sec")
                title = etree.SubElement(sec_el, "title")
                title.text = s.label
                for p in s.paragraphs:
                    p_el = etree.SubElement(sec_el, "p")
                    self._append_inline_runs(p_el, p.content)

        # <kwd-group>
        if doc.metadata.keywords:
            kwd_group = etree.SubElement(a_meta, "kwd-group")
            kwd_group.set("kwd-group-type", "author-generated")
            for kwd_text in doc.metadata.keywords:
                kwd = etree.SubElement(kwd_group, "kwd")
                kwd.text = kwd_text

        # <funding-group>
        if doc.metadata.funding:
            fg = etree.SubElement(a_meta, "funding-group")
            for fund in doc.metadata.funding:
                ag = etree.SubElement(fg, "award-group")
                fs = etree.SubElement(ag, "funding-source")
                fs.text = fund.source
                aid = etree.SubElement(ag, "award-id")
                aid.text = fund.award_id

    def _build_body(self, doc: Document, parent: etree._Element):
        for section in doc.body:
            self._append_section(parent, section)

    def _append_section(self, parent: etree._Element, section: Section):
        if not section.heading:
            # If a section has no heading, do not wrap it in a <sec> element.
            # Append its content directly to the parent.
            for item in section.content:
                if isinstance(item, Section):
                    self._append_section(parent, item)
                else:
                    self._append_content_item(parent, item)
        else:
            sec = etree.SubElement(parent, "sec")
            sec.set("id", section.id)
            title = etree.SubElement(sec, "title")
            title.text = section.heading
            
            for item in section.content:
                if isinstance(item, Section):
                    self._append_section(sec, item)
                else:
                    self._append_content_item(sec, item)

    def _append_content_item(self, parent: etree._Element, item: Any):
        if isinstance(item, Paragraph):
            p = etree.SubElement(parent, "p")
            if item.id:
                p.set("id", item.id)
            self._append_inline_runs(p, item.content)
            
        elif isinstance(item, Figure):
            fig = etree.SubElement(parent, "fig")
            fig.set("id", item.id)
            if item.orientation == "landscape":
                fig.set("orientation", "landscape")
            
            # Caption
            caption = etree.SubElement(fig, "caption")
            p = etree.SubElement(caption, "p")
            self._append_inline_runs(p, item.caption)
            
            # Alt-text (Required per agent.md non-negotiable requirement)
            alt = etree.SubElement(fig, "alt-text")
            alt.text = item.alt_text or ""
            
            # Graphic
            graphic = etree.SubElement(fig, "graphic")
            graphic.set(f"{{{NS_XLINK}}}href", item.image_ref)
            
        elif isinstance(item, Table):
            table_wrap = etree.SubElement(parent, "table-wrap")
            table_wrap.set("id", item.id)
            
            if item.caption:
                caption = etree.SubElement(table_wrap, "caption")
                p = etree.SubElement(caption, "p")
                self._append_inline_runs(p, item.caption)
                
            table = etree.SubElement(table_wrap, "table")
            
            # Partition rows to headers vs body rows
            thead_rows = item.rows[:item.header_rows]
            tbody_rows = item.rows[item.header_rows:]
            
            if thead_rows:
                thead = etree.SubElement(table, "thead")
                self._append_table_rows(thead, thead_rows)
                
            if tbody_rows:
                tbody = etree.SubElement(table, "tbody")
                self._append_table_rows(tbody, tbody_rows)
                
            for fn_text in item.footnotes:
                table_wrap_foot = etree.SubElement(table_wrap, "table-wrap-foot")
                fn = etree.SubElement(table_wrap_foot, "fn")
                p = etree.SubElement(fn, "p")
                p.text = fn_text
                
        elif isinstance(item, Equation):
            formula_tag = "disp-formula" if item.display == "block" else "inline-formula"
            formula = etree.SubElement(parent, formula_tag)
            formula.set("id", item.id)
            
            # Store formula inside <tex-math> per standard JATS specification
            tex_math = etree.SubElement(formula, "tex-math")
            tex_math.text = etree.CDATA(item.latex_source or "")
            
        elif isinstance(item, BlockQuote):
            quote = etree.SubElement(parent, "disp-quote")
            for p in item.content:
                p_el = etree.SubElement(quote, "p")
                self._append_inline_runs(p_el, p.content)
                
        elif isinstance(item, ListNode):
            list_tag = "list"
            list_el = etree.SubElement(parent, list_tag)
            list_el.set("list-type", "order" if item.style == "ordered" else "bullet")
            
            for li in item.items:
                list_item = etree.SubElement(list_el, "list-item")
                p = etree.SubElement(list_item, "p")
                self._append_inline_runs(p, li.content)
                if li.nested_list:
                    self._append_content_item(list_item, li.nested_list)

        elif isinstance(item, Footnote):
            fn = etree.SubElement(parent, "fn")
            fn.set("id", item.id)
            p = etree.SubElement(fn, "p")
            self._append_inline_runs(p, item.content)

        elif isinstance(item, Endnote):
            fn = etree.SubElement(parent, "fn")
            fn.set("id", item.id)
            fn.set("fn-type", "endnote")
            p = etree.SubElement(fn, "p")
            self._append_inline_runs(p, item.content)

        elif isinstance(item, UnrecognizedBlock):
            p = etree.SubElement(parent, "p")
            p.set("content-type", "unrecognized")
            p.text = f"[Manual Handling Required] Unclassified Content: {item.content_text}"

    def _append_table_rows(self, parent: etree._Element, rows: List[List[TableCell]]):
        for row in rows:
            tr = etree.SubElement(parent, "tr")
            for cell in row:
                tag = "th" if cell.is_header else "td"
                cell_el = etree.SubElement(tr, tag)
                if cell.colspan > 1:
                    cell_el.set("colspan", str(cell.colspan))
                if cell.rowspan > 1:
                    cell_el.set("rowspan", str(cell.rowspan))
                self._append_inline_runs(cell_el, cell.content)

    def _append_inline_runs(self, parent: etree._Element, runs: List[InlineRun]):
        """
        Translates formatting runs recursively, properly appending XML tags to element tails.
        """
        current_parent = parent
        for run in runs:
            # Create tag sequence based on formatting flags
            el = None
            
            # Formatting tags
            if run.bold:
                el = etree.SubElement(current_parent, "bold") if el is None else etree.SubElement(el, "bold")
            if run.italic:
                el = etree.SubElement(current_parent, "italic") if el is None else etree.SubElement(el, "italic")
            if run.underline:
                el = etree.SubElement(current_parent, "underline") if el is None else etree.SubElement(el, "underline")
            if run.strikethrough:
                el = etree.SubElement(current_parent, "strike") if el is None else etree.SubElement(el, "strike")
            if run.sub:
                el = etree.SubElement(current_parent, "sub") if el is None else etree.SubElement(el, "sub")
            if run.sup:
                el = etree.SubElement(current_parent, "sup") if el is None else etree.SubElement(el, "sup")
            if run.small_caps:
                el = etree.SubElement(current_parent, "sc") if el is None else etree.SubElement(el, "sc")
                
            if run.link_url:
                link_el = etree.SubElement(current_parent, "ext-link") if el is None else etree.SubElement(el, "ext-link")
                link_el.set("ext-link-type", "uri")
                link_el.set(f"{{{NS_XLINK}}}href", run.link_url)
                el = link_el
                
            if run.xref_target:
                # Deduce ref-type
                ref_type = "bibr"
                if run.xref_target.startswith("fig-"):
                    ref_type = "fig"
                elif run.xref_target.startswith("tbl-") or run.xref_target.startswith("table-"):
                    ref_type = "table"
                elif run.xref_target == "footnote":
                    ref_type = "fn"
                
                xref_el = etree.SubElement(current_parent, "xref") if el is None else etree.SubElement(el, "xref")
                xref_el.set("ref-type", ref_type)
                xref_el.set("rid", run.xref_target)
                el = xref_el

            if run.equation_source:
                math_el = etree.SubElement(current_parent, "inline-formula") if el is None else etree.SubElement(el, "inline-formula")
                tex_math = etree.SubElement(math_el, "tex-math")
                tex_math.text = etree.CDATA(run.equation_source)
                el = math_el

            # Write text content to the innermost tag or root parent
            target = el if el is not None else current_parent
            if target == current_parent:
                if len(current_parent) == 0:
                    current_parent.text = (current_parent.text or "") + run.text
                else:
                    # Append text to the tail of the last child node
                    last_child = current_parent[-1]
                    last_child.tail = (last_child.tail or "") + run.text
            else:
                target.text = run.text

    def _build_back(self, doc: Document, parent: etree._Element):
        if not doc.references:
            return
            
        ref_list = etree.SubElement(parent, "ref-list")
        ref_list_title = etree.SubElement(ref_list, "title")
        ref_list_title.text = "References"
        
        for index, ref in enumerate(doc.references):
            ref_el = etree.SubElement(ref_list, "ref")
            ref_el.set("id", ref.id or f"ref-{index+1}")
            
            citation = etree.SubElement(ref_el, "element-citation")
            # Normalize citation type to JATS standard (e.g. journal-article -> journal)
            cite_type = ref.type
            if cite_type == "journal-article":
                cite_type = "journal"
            elif cite_type == "conference-paper":
                cite_type = "confproc"
            citation.set("publication-type", cite_type)
            
            # Authors
            if ref.authors:
                person_group = etree.SubElement(citation, "person-group")
                person_group.set("person-group-type", "author")
                for author in ref.authors:
                    name = etree.SubElement(person_group, "name")
                    surname = etree.SubElement(name, "surname")
                    surname.text = author.family
                    given = etree.SubElement(name, "given-names")
                    given.text = author.given
                    
            if ref.title:
                art_title = etree.SubElement(citation, "article-title")
                art_title.text = ref.title
                
            if ref.source_title:
                source = etree.SubElement(citation, "source")
                source.text = ref.source_title
                
            if ref.year:
                year = etree.SubElement(citation, "year")
                year.text = ref.year
                
            if ref.volume:
                volume = etree.SubElement(citation, "volume")
                volume.text = ref.volume
                
            if ref.issue:
                issue = etree.SubElement(citation, "issue")
                issue.text = ref.issue
                
            if ref.pages:
                pages = ref.pages
                if "-" in pages:
                    parts = pages.split("-")
                    fpage = etree.SubElement(citation, "fpage")
                    fpage.text = parts[0]
                    lpage = etree.SubElement(citation, "lpage")
                    lpage.text = parts[-1]
                else:
                    fpage = etree.SubElement(citation, "fpage")
                    fpage.text = pages
                    
            if ref.doi:
                pub_id = etree.SubElement(citation, "pub-id")
                pub_id.set("pub-id-type", "doi")
                pub_id.text = ref.doi
                
            if ref.url:
                comment = etree.SubElement(citation, "comment")
                link = etree.SubElement(comment, "ext-link")
                link.set("ext-link-type", "uri")
                link.set(f"{{{NS_XLINK}}}href", ref.url)
                link.text = ref.url

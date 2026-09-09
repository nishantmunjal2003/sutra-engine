from typing import List, Optional, Union, Literal, Dict
from pydantic import BaseModel, Field


class InlineRun(BaseModel):
    """Represents a formatted span of text within a paragraph or cell."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    sub: bool = False
    sup: bool = False
    small_caps: bool = False
    link_url: Optional[str] = None
    xref_target: Optional[str] = None
    equation_source: Optional[str] = None  # Holds inline math source (LaTeX/OMML)


class Author(BaseModel):
    given_name: str
    family_name: str
    affiliation_refs: List[str] = Field(default_factory=list)
    orcid: Optional[str] = None
    corresponding: bool = False
    email: Optional[str] = None
    equal_contribution_group: Optional[int] = None


class Affiliation(BaseModel):
    id: str
    institution: str
    department: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None


class AuthorContribution(BaseModel):
    author_ref: str  # References an author's orcid or family_name/given_name combo
    credit_roles: List[str] = Field(default_factory=list)


class Funding(BaseModel):
    source: str
    award_id: str
    recipient_ref: Optional[str] = None


class JournalMeta(BaseModel):
    title: str
    issn: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    publisher: Optional[str] = None


class DateInfo(BaseModel):
    received: Optional[str] = None
    revised: Optional[str] = None
    accepted: Optional[str] = None


class LicenseInfo(BaseModel):
    type: str
    url: Optional[str] = None


class SubjectCode(BaseModel):
    scheme: str
    code: str


class Paragraph(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    id: Optional[str] = None
    content: List[InlineRun] = Field(default_factory=list)


class StructuredAbstractSection(BaseModel):
    label: str
    paragraphs: List[Paragraph] = Field(default_factory=list)


class Abstract(BaseModel):
    structured_sections: List[StructuredAbstractSection] = Field(default_factory=list)
    paragraphs: List[Paragraph] = Field(default_factory=list)


class Metadata(BaseModel):
    title: List[InlineRun] = Field(default_factory=list)
    short_title: Optional[str] = None
    authors: List[Author] = Field(default_factory=list)
    affiliations: List[Affiliation] = Field(default_factory=list)
    author_contributions: List[AuthorContribution] = Field(default_factory=list)
    abstract: Abstract = Field(default_factory=Abstract)
    graphical_abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    subject_codes: List[SubjectCode] = Field(default_factory=list)
    article_type: str = "research-article"
    funding: List[Funding] = Field(default_factory=list)
    conflict_of_interest: Optional[str] = None
    ethics_statement: Optional[str] = None
    data_availability: Optional[str] = None
    acknowledgments: Optional[str] = None
    dates: Optional[DateInfo] = None
    license: Optional[LicenseInfo] = None
    journal_meta: Optional[JournalMeta] = None


class Figure(BaseModel):
    type: Literal["figure"] = "figure"
    id: str
    image_ref: str
    format: Literal["raster", "vector"]
    caption: List[InlineRun] = Field(default_factory=list)
    alt_text: str = ""  # Alt text is required, defaults to empty string per agent.md
    panels: List[str] = Field(default_factory=list)
    span_hint: Literal["column", "page"] = "column"
    orientation: Literal["portrait", "landscape"] = "portrait"


class TableCell(BaseModel):
    content: List[InlineRun] = Field(default_factory=list)
    colspan: int = 1
    rowspan: int = 1
    is_header: bool = False


class Table(BaseModel):
    type: Literal["table"] = "table"
    id: str
    caption: List[InlineRun] = Field(default_factory=list)
    rows: List[List[TableCell]] = Field(default_factory=list)
    header_rows: int = 1
    footnotes: List[str] = Field(default_factory=list)
    span_hint: Literal["column", "page"] = "column"
    continuation_of: Optional[str] = None


class Footnote(BaseModel):
    type: Literal["footnote"] = "footnote"
    id: str
    content: List[InlineRun] = Field(default_factory=list)
    scope: Literal["body", "table"] = "body"


class Endnote(BaseModel):
    type: Literal["endnote"] = "endnote"
    id: str
    content: List[InlineRun] = Field(default_factory=list)


class BlockQuote(BaseModel):
    type: Literal["blockquote"] = "blockquote"
    content: List[Paragraph] = Field(default_factory=list)


class ListNode(BaseModel):
    type: Literal["list"] = "list"
    style: Literal["ordered", "unordered", "definition"]
    numbering_format: Optional[str] = None
    items: List["ListItem"] = Field(default_factory=list)


class ListItem(BaseModel):
    content: List[InlineRun] = Field(default_factory=list)
    nested_list: Optional[ListNode] = None


class Sidebar(BaseModel):
    type: Literal["sidebar"] = "sidebar"
    heading: Optional[str] = None
    content: List[Paragraph] = Field(default_factory=list)


class Equation(BaseModel):
    type: Literal["equation"] = "equation"
    id: str
    source: Literal["omml", "image", "latex_native"]
    latex_source: Optional[str] = None
    mathml: Optional[str] = None
    image_ref: Optional[str] = None
    display: Literal["inline", "block"] = "block"
    numbered: bool = True


class UnrecognizedBlock(BaseModel):
    type: Literal["unrecognized"] = "unrecognized"
    id: str
    raw_type: str
    content_text: str


class TrackedChangeMarker(BaseModel):
    type: Literal["tracked_change_marker"] = "tracked_change_marker"
    change_type: Literal["insertion", "deletion", "comment"]
    author: Optional[str] = None
    content: str


# Set up recursive references and union types
ContentItem = Union[
    Paragraph,
    Figure,
    Table,
    Footnote,
    Endnote,
    BlockQuote,
    ListNode,
    Sidebar,
    Equation,
    TrackedChangeMarker,
    UnrecognizedBlock,
    "Section",
]


class Section(BaseModel):
    type: Literal["section"] = "section"
    id: str
    level: int
    heading: str
    numbering_scheme: Optional[str] = None
    content: List[ContentItem] = Field(default_factory=list)


class Citation(BaseModel):
    marker_id: str
    style: Literal["numeric", "author-date", "named"]
    reference_ids: List[str] = Field(default_factory=list)


class ReferenceAuthor(BaseModel):
    family: str
    given: str


class Reference(BaseModel):
    id: str
    type: Literal[
        "journal-article",
        "book",
        "book-chapter",
        "conference-paper",
        "thesis",
        "dataset",
        "software",
        "preprint",
        "website",
    ]
    authors: List[ReferenceAuthor] = Field(default_factory=list)
    year: Optional[str] = None
    title: str
    source_title: str
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    access_date: Optional[str] = None


class Appendix(BaseModel):
    id: str
    heading: str
    own_numbering_scope: bool = False
    content: List[ContentItem] = Field(default_factory=list)


class AuthorBio(BaseModel):
    author_ref: str
    photo_ref: Optional[str] = None
    bio_text: str


class Document(BaseModel):
    metadata: Metadata = Field(default_factory=Metadata)
    body: List[Section] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)
    appendices: List[Appendix] = Field(default_factory=list)
    author_bios: List[AuthorBio] = Field(default_factory=list)


# Rebuild recursive models to resolve ForwardRefs
ListNode.model_rebuild()
ListItem.model_rebuild()
Section.model_rebuild()


class PageSettings(BaseModel):
    paper_size: str = "a4"
    columns: int = 1
    column_gap_pt: float = 12.0
    margin_top_in: float = 1.0
    margin_bottom_in: float = 1.0
    margin_left_in: float = 1.0
    margin_right_in: float = 1.0


class BodyTextSettings(BaseModel):
    font_family: str = "Times New Roman"
    font_size_pt: float = 10.0
    line_spacing: float = 1.15
    paragraph_indent_pt: float = 12.0
    paragraph_spacing_pt: float = 6.0


class TitleBlockSettings(BaseModel):
    title_font_size_pt: float = 18.0
    title_font_weight: str = "bold"
    title_alignment: str = "center"
    subtitle_font_size_pt: float = 14.0
    authors_font_size_pt: float = 11.0
    authors_font_style: str = "normal"
    affiliation_font_size_pt: float = 9.0
    affiliation_font_style: str = "italic"
    corresponding_marker: str = "*"


class AbstractSettings(BaseModel):
    heading_text: str = "Abstract"
    heading_font_size_pt: float = 11.0
    heading_font_weight: str = "bold"
    body_font_size_pt: float = 9.0
    indented: bool = True
    box_border: bool = False
    structured_labels_bold: bool = True
    full_width_in_twocol: bool = True      # Abstract spans full page width in 2-column layout
    single_paragraph: bool = False          # Merge all abstract paragraphs into one continuous block
    include_keywords_in_box: bool = False   # Keywords rendered inside abstract box


class KeywordsSettings(BaseModel):
    label_text: str = "Keywords:"
    label_font_weight: str = "bold"
    font_size_pt: float = 9.0
    separator: str = "; "


class HeadingLevelSettings(BaseModel):
    font_size_pt: float = 12.0
    font_weight: str = "bold"
    font_style: str = "normal"
    alignment: str = "left"
    numbering: str = "numeric"  # numeric, none
    space_before_pt: float = 12.0
    space_after_pt: float = 6.0
    all_caps: bool = False


class HeadingSettings(BaseModel):
    h1: HeadingLevelSettings = Field(default_factory=HeadingLevelSettings)
    h2: HeadingLevelSettings = Field(default_factory=lambda: HeadingLevelSettings(font_size_pt=11.0, font_style="italic", space_before_pt=8.0, space_after_pt=4.0))
    h3: HeadingLevelSettings = Field(default_factory=lambda: HeadingLevelSettings(font_size_pt=10.0, font_weight="normal", font_style="italic", numbering="none", space_before_pt=6.0, space_after_pt=3.0))


class EquationsSettings(BaseModel):
    display_numbering: bool = True
    numbering_alignment: str = "right"
    numbering_bracket: str = "parentheses"
    font_size_pt: float = 10.0


class FiguresSettings(BaseModel):
    caption_position: str = "below"
    caption_label_prefix: str = "Figure"
    caption_label_style: str = "bold"
    caption_font_size_pt: float = 9.0
    span_wide_figures: bool = True
    label_separator: str = "."              # Separator after figure number: "." or ":" or " "
    caption_justification: str = "justified"  # justified, left, center


class TablesSettings(BaseModel):
    caption_position: str = "above"
    caption_label_prefix: str = "Table"
    caption_label_style: str = "bold"
    caption_font_size_pt: float = 9.0
    border_style: str = "booktabs"
    span_wide_tables: bool = True
    label_separator: str = "."              # Separator after table number
    show_vertical_lines: bool = False       # Vertical line separators in table
    caption_justification: str = "justified"  # justified, left, center


class ReferencesSettings(BaseModel):
    section_heading_text: str = "References"
    citation_style: str = "numeric"
    font_size_pt: float = 9.0
    hanging_indent: bool = True


class ConclusionSettings(BaseModel):
    heading_text: str = "Conclusion"
    font_size_pt: float = 12.0
    numbering: str = "numeric"  # numeric, none


class FootnotesSettings(BaseModel):
    font_size_pt: float = 8.0
    marker_style: str = "numeric"  # numeric, symbols, alpha
    rule_separator: bool = True


class BlockquotesSettings(BaseModel):
    font_size_pt: float = 9.0
    font_style: str = "italic"  # italic, normal
    indent_pt: float = 18.0


class ListsSettings(BaseModel):
    bullet_marker: str = "bullet"  # bullet, circle, square, dash
    numbering_style: str = "numeric"  # numeric, paren, roman, alpha
    indent_pt: float = 15.0
    item_spacing_pt: float = 3.0


class DeclarationsSettings(BaseModel):
    heading_style: str = "inline_bold"  # inline_bold, subsection
    font_size_pt: float = 9.0


class JournalIdentity(BaseModel):
    logo_filename: Optional[str] = None
    issn_print: Optional[str] = None
    issn_online: Optional[str] = None
    website: Optional[str] = None
    publisher: Optional[str] = None


class HeaderFooterLine(BaseModel):
    show: bool = False
    thickness_pt: float = 0.5
    color: str = "#000000"


class HeaderSettings(BaseModel):
    enabled: bool = True
    from_page: int = 2
    left_text: str = ""
    center_text: str = ""
    right_text: str = ""
    font_size_pt: float = 8.5
    font_style: str = "normal"  # normal, italic
    line: HeaderFooterLine = Field(default_factory=HeaderFooterLine)


class FooterSettings(BaseModel):
    enabled: bool = True
    from_page: int = 1
    left_text: str = ""
    center_text: str = "\\thepage"
    right_text: str = ""
    font_size_pt: float = 8.5
    font_style: str = "normal"  # normal, italic
    line: HeaderFooterLine = Field(default_factory=HeaderFooterLine)


class FirstPageHeader(BaseModel):
    enabled: bool = True
    show_logo: bool = True
    logo_position: str = "left"  # left, center, right
    logo_max_height_mm: float = 18.0
    show_journal_name: bool = True
    show_issn: bool = True
    show_volume_issue: bool = True
    show_website: bool = True
    custom_banner_text: Optional[str] = None


class VolumeIssue(BaseModel):
    id: str
    volume_no: str
    issue_no: str
    year: int
    page_range: Optional[str] = None
    publication_month: Optional[str] = None
    is_active: bool = False


class JournalSettings(BaseModel):
    journal_id: str
    journal_name: str
    created_at: str
    page: PageSettings = Field(default_factory=PageSettings)
    body_text: BodyTextSettings = Field(default_factory=BodyTextSettings)
    title_block: TitleBlockSettings = Field(default_factory=TitleBlockSettings)
    abstract: AbstractSettings = Field(default_factory=AbstractSettings)
    keywords: KeywordsSettings = Field(default_factory=KeywordsSettings)
    headings: HeadingSettings = Field(default_factory=HeadingSettings)
    equations: EquationsSettings = Field(default_factory=EquationsSettings)
    figures: FiguresSettings = Field(default_factory=FiguresSettings)
    tables: TablesSettings = Field(default_factory=TablesSettings)
    references: ReferencesSettings = Field(default_factory=ReferencesSettings)
    conclusion: ConclusionSettings = Field(default_factory=ConclusionSettings)
    footnotes: FootnotesSettings = Field(default_factory=FootnotesSettings)
    blockquotes: BlockquotesSettings = Field(default_factory=BlockquotesSettings)
    lists: ListsSettings = Field(default_factory=ListsSettings)
    declarations: DeclarationsSettings = Field(default_factory=DeclarationsSettings)
    identity: JournalIdentity = Field(default_factory=JournalIdentity)
    header: HeaderSettings = Field(default_factory=HeaderSettings)
    footer: FooterSettings = Field(default_factory=FooterSettings)
    first_page_header: FirstPageHeader = Field(default_factory=FirstPageHeader)
    volumes: List[VolumeIssue] = Field(default_factory=list)
    active_volume_id: Optional[str] = None


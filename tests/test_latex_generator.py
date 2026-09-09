import os
import pytest
from sutra.models import (
    Document, Metadata, Section, Paragraph, InlineRun,
    Author, Affiliation, Figure, Table, TableCell, Equation,
    Reference, ReferenceAuthor, BlockQuote, ListNode, ListItem,
    Abstract, JournalSettings, FiguresSettings, TablesSettings, AbstractSettings
)
from sutra.generator.latex import LatexGenerator
from sutra.utils.latex import compile_latex_to_pdf

@pytest.fixture
def test_document():
    doc = Document()
    doc.metadata = Metadata(
        title=[InlineRun(text="Typesetting and PDF Generation")],
        authors=[
            Author(
                given_name="John",
                family_name="Doe",
                affiliation_refs=["aff-1"],
                email="john.doe@sutra.org",
                corresponding=True
            )
        ],
        affiliations=[
            Affiliation(
                id="aff-1",
                institution="Sutra Press Labs",
                country="USA"
            )
        ],
        keywords=["LaTeX", "Tectonic", "Typesetting"]
    )
    
    # Body sections
    p1 = Paragraph(
        id="p-1",
        content=[
            InlineRun(text="Here is a paragraph with "),
            InlineRun(text="bold", bold=True),
            InlineRun(text=" and "),
            InlineRun(text="italic", italic=True),
            InlineRun(text=" formatting.")
        ]
    )
    
    # Inline equation
    p2 = Paragraph(
        id="p-2",
        content=[
            InlineRun(text="The equation is "),
            InlineRun(text="E = mc^2", equation_source="E = mc^2"),
            InlineRun(text=" inline.")
        ]
    )
    
    # Display equation
    eq = Equation(
        id="eq-1",
        source="latex_native",
        latex_source="a^2 + b^2 = c^2",
        display="block"
    )
    
    # Figure
    fig = Figure(
        id="fig-1",
        image_ref="test_image.png",
        format="raster",
        caption=[InlineRun(text="A test figure caption")],
        alt_text="Alt description"
    )
    
    sec = Section(
        id="sec-main",
        level=1,
        heading="Main Section",
        content=[p1, p2, eq, fig]
    )
    doc.body.append(sec)
    
    # References
    ref = Reference(
        id="ref-1",
        type="journal-article",
        authors=[ReferenceAuthor(family="Knuth", given="Donald")],
        year="1984",
        title="The TeXbook",
        source_title="Addison-Wesley",
        volume="1"
    )
    doc.references.append(ref)
    
    return doc

def test_latex_generation_metadata(test_document):
    generator = LatexGenerator()
    tex = generator.generate(test_document, layout="single")
    
    assert r"\title{Typesetting and PDF Generation}" in tex
    assert r"\author[1]{John Doe\thanks{Corresponding author: john.doe@sutra.org}}" in tex
    assert r"\affil[1]{Sutra Press Labs, USA}" in tex
    assert r"\begin{abstract}" not in tex # no abstract specified in fixture
    assert r"\noindent \textbf{Keywords:} LaTeX, Tectonic, Typesetting" in tex

def test_latex_generation_layout(test_document):
    generator = LatexGenerator()
    
    tex_single = generator.generate(test_document, layout="single")
    assert r"onecolumn" in tex_single
    
    tex_double = generator.generate(test_document, layout="double")
    assert r"twocolumn" in tex_double

def test_latex_generation_elements(test_document):
    generator = LatexGenerator()
    tex = generator.generate(test_document, layout="single")
    
    # Section
    assert r"\section{Main Section}" in tex
    assert r"\label{sec-main}" in tex
    
    # Paragraph
    assert r"Here is a paragraph with \textbf{bold} and \textit{italic} formatting." in tex
    
    # Math
    assert r"$E = mc^2$" in tex
    assert r"\begin{equation}" in tex
    assert r"a^2 + b^2 = c^2" in tex
    
    # Figure
    assert r"\begin{figure}[h]" in tex
    assert r"\includegraphics[width=\linewidth]{assets/test_image.png}" in tex
    assert r"\caption{A test figure caption}" in tex
    assert r"\label{fig-1}" in tex
    
    # References
    assert r"\begin{thebibliography}{99}" in tex
    assert r"\bibitem{ref-1}" in tex
    assert "Donald Knuth" in tex
    assert "The TeXbook" in tex

def test_latex_figure_table_span_hints(test_document):
    # Set span hint to page for figure
    test_document.body[0].content[3].span_hint = "page"
    
    # Add a table
    table = Table(
        id="tbl-1",
        caption=[InlineRun(text="A test table")],
        rows=[
            [TableCell(content=[InlineRun(text="Head 1")], is_header=True), TableCell(content=[InlineRun(text="Head 2")], is_header=True)],
            [TableCell(content=[InlineRun(text="Val 1")]), TableCell(content=[InlineRun(text="Val 2")])]
        ],
        header_rows=1,
        span_hint="page"
    )
    test_document.body[0].content.append(table)
    
    generator = LatexGenerator()
    tex = generator.generate(test_document, layout="double")
    
    # Figure should use starred version
    assert r"\begin{figure*}[t]" in tex
    assert r"\end{figure*}" in tex
    
    # Table should use starred version
    assert r"\begin{table*}[t]" in tex
    assert r"\end{table*}" in tex

def test_latex_compilation_success(test_document, tmp_path):
    generator = LatexGenerator()
    tex = generator.generate(test_document, layout="single")
    
    tex_file = tmp_path / "article.tex"
    tex_file.write_text(tex, encoding="utf-8")
    
    # Create assets dir and empty dummy image to prevent graphicx error
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    import base64
    png_data = base64.b64decode(b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    (assets_dir / "test_image.png").write_bytes(png_data)
    
    errors = compile_latex_to_pdf(str(tex_file), str(tmp_path))
    assert len(errors) == 0, f"Compilation errors found: {errors}"
    
    # Verify PDF was created
    pdf_file = tmp_path / "article.pdf"
    assert pdf_file.exists()
    assert pdf_file.stat().st_size > 0

def test_latex_compilation_failure_error_tracing(test_document, tmp_path):
    # Intentionally inject bad LaTeX command into the display equation
    test_document.body[0].content[2].latex_source = r"\someundefinedcommand"
    
    generator = LatexGenerator()
    tex = generator.generate(test_document, layout="single")
    
    tex_file = tmp_path / "article.tex"
    tex_file.write_text(tex, encoding="utf-8")
    
    # Create assets dir and empty dummy image to prevent graphicx error
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    import base64
    png_data = base64.b64decode(b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    (assets_dir / "test_image.png").write_bytes(png_data)
    
    errors = compile_latex_to_pdf(str(tex_file), str(tmp_path))
    assert len(errors) > 0
    
    # Verify the error was traced back to the equation element
    assert any("eq-1" in err for err in errors), f"Sutra element ID 'eq-1' not found in errors: {errors}"
    assert any("Undefined control sequence" in err for err in errors)


def make_settings(**kwargs):
    import datetime
    return JournalSettings(
        journal_id="test-journal",
        journal_name="Test Journal",
        created_at=datetime.datetime.now(datetime.UTC).isoformat(),
        **kwargs
    )


def test_figure_caption_above(test_document):
    generator = LatexGenerator()
    settings = make_settings(
        figures=FiguresSettings(caption_position="above")
    )
    tex = generator.generate(test_document, journal_settings=settings)
    cap_idx = tex.find(r"\caption{A test figure caption}")
    img_idx = tex.find(r"\includegraphics[width=\linewidth]{assets/test_image.png}")
    assert cap_idx != -1 and img_idx != -1
    assert cap_idx < img_idx, "Caption should appear before includegraphics when caption_position is above"


def test_figure_label_separator(test_document):
    generator = LatexGenerator()
    settings = make_settings(
        figures=FiguresSettings(label_separator=":")
    )
    tex = generator.generate(test_document, journal_settings=settings)
    assert r"\captionsetup[figure]{" in tex
    assert "labelsep=colon" in tex


def test_figure_caption_justification(test_document):
    generator = LatexGenerator()
    settings = make_settings(
        figures=FiguresSettings(caption_justification="center")
    )
    tex = generator.generate(test_document, journal_settings=settings)
    assert r"\captionsetup[figure]{" in tex
    assert "justification=centering" in tex


def test_table_grid_borders(test_document):
    table = Table(
        id="tbl-grid",
        caption=[InlineRun(text="Grid Table")],
        rows=[
            [TableCell(content=[InlineRun(text="H1")]), TableCell(content=[InlineRun(text="H2")])],
            [TableCell(content=[InlineRun(text="D1")]), TableCell(content=[InlineRun(text="D2")])]
        ],
        header_rows=1
    )
    test_document.body[0].content.append(table)
    generator = LatexGenerator()
    settings = make_settings(
        tables=TablesSettings(border_style="grid")
    )
    tex = generator.generate(test_document, journal_settings=settings)
    assert r"\begin{tabularx}{\linewidth}{|X|X|}" in tex
    assert r"\hline" in tex
    assert r"\toprule" not in tex


def test_table_vertical_lines(test_document):
    table = Table(
        id="tbl-vert",
        caption=[InlineRun(text="Vertical Lines Table")],
        rows=[
            [TableCell(content=[InlineRun(text="H1")]), TableCell(content=[InlineRun(text="H2")])],
            [TableCell(content=[InlineRun(text="D1")]), TableCell(content=[InlineRun(text="D2")])]
        ],
        header_rows=1
    )
    test_document.body[0].content.append(table)
    generator = LatexGenerator()
    settings = make_settings(
        tables=TablesSettings(border_style="booktabs", show_vertical_lines=True)
    )
    tex = generator.generate(test_document, journal_settings=settings)
    assert r"\begin{tabularx}{\linewidth}{|X|X|}" in tex


def test_table_plain_borders(test_document):
    table = Table(
        id="tbl-plain",
        caption=[InlineRun(text="Plain Table")],
        rows=[
            [TableCell(content=[InlineRun(text="H1")]), TableCell(content=[InlineRun(text="H2")])],
            [TableCell(content=[InlineRun(text="D1")]), TableCell(content=[InlineRun(text="D2")])]
        ],
        header_rows=1
    )
    test_document.body[0].content.append(table)
    generator = LatexGenerator()
    settings = make_settings(
        tables=TablesSettings(border_style="plain", show_vertical_lines=False)
    )
    tex = generator.generate(test_document, journal_settings=settings)
    assert r"\begin{tabularx}{\linewidth}{XX}" in tex
    assert r"\toprule" in tex
    assert r"\bottomrule" in tex
    assert r"\midrule" not in tex
    assert r"\hline" not in tex


def test_abstract_full_width_twocol(test_document):
    test_document.metadata.abstract = Abstract(paragraphs=[
        Paragraph(id="ab-1", content=[InlineRun(text="Full width abstract text.")])
    ])
    generator = LatexGenerator()
    settings = make_settings(
        abstract=AbstractSettings(full_width_in_twocol=True)
    )
    tex = generator.generate(test_document, layout="double", journal_settings=settings)
    assert r"\twocolumn[" in tex
    assert r"\begin{abstract}" in tex
    assert "Full width abstract text." in tex


def test_abstract_single_paragraph(test_document):
    test_document.metadata.abstract = Abstract(paragraphs=[
        Paragraph(id="ab-1", content=[InlineRun(text="First sentence.")]),
        Paragraph(id="ab-2", content=[InlineRun(text="Second sentence.")])
    ])
    generator = LatexGenerator()
    settings = make_settings(
        abstract=AbstractSettings(single_paragraph=True)
    )
    tex = generator.generate(test_document, layout="single", journal_settings=settings)
    assert "First sentence. Second sentence." in tex
    assert "First sentence.\n\nSecond sentence." not in tex


def test_abstract_keywords_in_box(test_document):
    test_document.metadata.abstract = Abstract(paragraphs=[
        Paragraph(id="ab-1", content=[InlineRun(text="Abstract body.")])
    ])
    test_document.metadata.keywords = ["AI", "Typesetting"]
    generator = LatexGenerator()
    settings = make_settings(
        abstract=AbstractSettings(include_keywords_in_box=True)
    )
    tex = generator.generate(test_document, layout="single", journal_settings=settings)
    abs_end = tex.find(r"\end{abstract}")
    kw_pos = tex.find(r"\textbf{Keywords:} AI, Typesetting")
    assert abs_end != -1 and kw_pos != -1
    assert kw_pos < abs_end, "Keywords should be inside abstract environment when include_keywords_in_box is True"


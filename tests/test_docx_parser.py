import pytest
from sutra.parser.docx import DocxParser
from sutra.models import Document, Section, Paragraph, ListNode, Table, Figure, Equation

@pytest.fixture
def parser():
    return DocxParser("dummy.docx")

def test_parse_nested_headers(parser):
    # Flat list of headers in AST: Header 1 -> Header 2 -> Para -> Header 1
    ast = {
        "pandoc-api-version": [1, 22, 2, 1],
        "meta": {},
        "blocks": [
            {"t": "Header", "c": [1, ["h1", [], []], [{"t": "Str", "c": "Section 1"}]]},
            {"t": "Header", "c": [2, ["h2", [], []], [{"t": "Str", "c": "Subsection 1.1"}]]},
            {"t": "Para", "c": [{"t": "Str", "c": "Paragraph content."}]},
            {"t": "Header", "c": [1, ["h2-main", [], []], [{"t": "Str", "c": "Section 2"}]]}
        ]
    }
    
    doc = parser._translate_ast_to_ir(ast)
    
    assert len(doc.body) == 2
    # Section 1
    assert doc.body[0].heading == "Section 1"
    assert doc.body[0].level == 1
    # Subsection 1.1 should be nested inside Section 1
    assert len(doc.body[0].content) == 1
    sub = doc.body[0].content[0]
    assert isinstance(sub, Section)
    assert sub.heading == "Subsection 1.1"
    assert sub.level == 2
    # Paragraph content inside Subsection 1.1
    assert len(sub.content) == 1
    p = sub.content[0]
    assert isinstance(p, Paragraph)
    assert p.content[0].text == "Paragraph content."
    
    # Section 2 should be parallel at top level
    assert doc.body[1].heading == "Section 2"
    assert doc.body[1].level == 1

def test_parse_lists(parser):
    # Unordered list with nested ordered list
    ast = {
        "pandoc-api-version": [1, 22, 2, 1],
        "meta": {},
        "blocks": [
            {
                "t": "BulletList",
                "c": [
                    [
                        {"t": "Para", "c": [{"t": "Str", "c": "Item 1"}]},
                        {
                            "t": "OrderedList",
                            "c": [
                                [1, {"t": "Decimal"}, {"t": "Period"}],
                                [
                                    [{"t": "Para", "c": [{"t": "Str", "c": "Sub-item 1"}]}]
                                ]
                            ]
                        }
                    ]
                ]
            }
        ]
    }
    
    doc = parser._translate_ast_to_ir(ast)
    intro_sec = doc.body[0]
    assert len(intro_sec.content) == 1
    
    ul = intro_sec.content[0]
    assert isinstance(ul, ListNode)
    assert ul.style == "unordered"
    assert len(ul.items) == 1
    assert ul.items[0].content[0].text == "Item 1"
    
    ol = ul.items[0].nested_list
    assert isinstance(ol, ListNode)
    assert ol.style == "ordered"
    assert ol.numbering_format == "Decimal"
    assert ol.items[0].content[0].text == "Sub-item 1"

def test_parse_complex_table(parser):
    # Table block with colspan and rowspan
    ast = {
        "pandoc-api-version": [1, 22, 2, 1],
        "meta": {},
        "blocks": [
            {
                "t": "Table",
                "c": [
                    ["tbl-id", [], []],  # attr
                    [None, []],          # caption
                    [[], []],            # colspecs
                    [                    # head
                        ["attr", [], []],
                        [
                            {
                                "t": "Row",
                                "c": [
                                    ["attr", [], []],
                                    [
                                        {"t": "Cell", "c": [["attr", [], []], {"t": "AlignDefault"}, 1, 2, [{"t": "Plain", "c": [{"t": "Str", "c": "Header Colspan"}]}]]}
                                    ]
                                ]
                            }
                        ]
                    ],
                    [                    # bodies
                        [
                            ["attr", [], []],
                            0,
                            [],
                            [
                                {
                                    "t": "Row",
                                    "c": [
                                        ["attr", [], []],
                                        [
                                            {"t": "Cell", "c": [["attr", [], []], {"t": "AlignDefault"}, 2, 1, [{"t": "Plain", "c": [{"t": "Str", "c": "Body Rowspan"}]}]]}
                                        ]
                                    ]
                                }
                            ]
                        ]
                    ],
                    [                    # foot
                        ["attr", [], []],
                        []
                    ]
                ]
            }
        ]
    }
    
    doc = parser._translate_ast_to_ir(ast)
    tbl = doc.body[0].content[0]
    assert isinstance(tbl, Table)
    assert tbl.id == "tbl-id"
    
    # 2 rows in total (1 header, 1 body)
    assert len(tbl.rows) == 2
    # Header cell has colspan 2, rowspan 1
    assert tbl.rows[0][0].colspan == 2
    assert tbl.rows[0][0].rowspan == 1
    assert tbl.rows[0][0].content[0].text == "Header Colspan"
    assert tbl.rows[0][0].is_header is True
    
    # Body cell has colspan 1, rowspan 2
    assert tbl.rows[1][0].colspan == 1
    assert tbl.rows[1][0].rowspan == 2
    assert tbl.rows[1][0].content[0].text == "Body Rowspan"
    assert tbl.rows[1][0].is_header is False

def test_math_and_image_elevation(parser):
    # Verify that a paragraph containing only display math / image gets elevated
    ast = {
        "pandoc-api-version": [1, 22, 2, 1],
        "meta": {},
        "blocks": [
            {
                "t": "Para",
                "c": [
                    {"t": "Math", "c": [{"t": "DisplayMath"}, "E = mc^2"]}
                ]
            },
            {
                "t": "Para",
                "c": [
                    {"t": "Image", "c": [["fig-1", [], []], [{"t": "Str", "c": "Sample Figure"}], ["assets/plot.png", "title"]]}
                ]
            }
        ]
    }
    
    doc = parser._translate_ast_to_ir(ast)
    intro_sec = doc.body[0]
    
    assert len(intro_sec.content) == 2
    # First is elevated block Equation
    assert isinstance(intro_sec.content[0], Equation)
    assert intro_sec.content[0].display == "block"
    assert intro_sec.content[0].latex_source == "E = mc^2"
    
    # Second is elevated block Figure
    assert isinstance(intro_sec.content[1], Figure)
    assert intro_sec.content[1].id == "fig-1"
    assert intro_sec.content[1].image_ref == "assets/plot.png"
    assert intro_sec.content[1].alt_text == "Sample Figure"
    assert intro_sec.content[1].format == "raster"


def test_academic_frontmatter_heuristics(parser):
    # Simulate a real-world manuscript where author wrote Title, Author, Affiliation, Abstract directly in body
    ast = {
        "pandoc-api-version": [1, 22, 2, 1],
        "meta": {},
        "blocks": [
            {"t": "Para", "c": [{"t": "Strong", "c": [{"t": "Str", "c": "A"}, {"t": "Space"}, {"t": "Str", "c": "Novel"}, {"t": "Space"}, {"t": "Str", "c": "Nanotechnology"}, {"t": "Space"}, {"t": "Str", "c": "Study"}]}]},
            {"t": "Para", "c": [{"t": "Str", "c": "Alice Smith, Bob Jones"}]},
            {"t": "Para", "c": [{"t": "Str", "c": "Department of Physics, Oxford University"}]},
            {"t": "Para", "c": [{"t": "Str", "c": "Abstract"}]},
            {"t": "Para", "c": [{"t": "Str", "c": "This study presents a breakthrough in nanomaterials synthesis."}]},
            {"t": "Para", "c": [{"t": "Str", "c": "Keywords: Nanotechnology, Physics, Synthesis"}]},
            {"t": "Para", "c": [{"t": "Strong", "c": [{"t": "Str", "c": "1."}, {"t": "Space"}, {"t": "Str", "c": "Introduction"}]}]},
            {"t": "Para", "c": [{"t": "Str", "c": "Nanotechnology has revolutionized material science."}]}
        ]
    }

    doc = parser._translate_ast_to_ir(ast)

    # Verify metadata extracted from body
    assert "".join(r.text for r in doc.metadata.title) == "A Novel Nanotechnology Study"
    assert len(doc.metadata.authors) == 2
    assert doc.metadata.authors[0].given_name == "Alice"
    assert doc.metadata.authors[0].family_name == "Smith"
    assert doc.metadata.authors[1].given_name == "Bob"
    assert doc.metadata.authors[1].family_name == "Jones"

    assert len(doc.metadata.affiliations) == 1
    assert "Oxford University" in doc.metadata.affiliations[0].institution

    assert len(doc.metadata.abstract.paragraphs) == 1
    assert "breakthrough in nanomaterials" in doc.metadata.abstract.paragraphs[0].content[0].text

    assert doc.metadata.keywords == ["Nanotechnology", "Physics", "Synthesis"]

    # Verify body sections
    assert len(doc.body) == 1
    assert "Introduction" in doc.body[0].heading
    assert doc.body[0].level == 1
    assert len(doc.body[0].content) == 1
    assert "Nanotechnology has revolutionized" in doc.body[0].content[0].content[0].text


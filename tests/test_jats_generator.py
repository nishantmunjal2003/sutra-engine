import pytest
from lxml import etree
from sutra.models import (
    Document, Metadata, Section, Paragraph, InlineRun,
    Author, Affiliation, Table, TableCell, Figure, Equation,
    Reference, ReferenceAuthor
)
from sutra.generator.jats import JatsGenerator
from sutra.utils.xml import validate_jats_xml

@pytest.fixture
def clean_document():
    doc = Document()
    doc.metadata = Metadata(
        title=[InlineRun(text="A Secure Schema-Validating Pipeline")],
        authors=[
            Author(
                given_name="Jane",
                family_name="Smith",
                affiliation_refs=["aff-1"],
                email="jane.smith@science.org",
                orcid="0000-0002-1825-0097",
                corresponding=True
            )
        ],
        affiliations=[
            Affiliation(
                id="aff-1",
                institution="Institute of Safety and Security",
                country="Switzerland"
            )
        ],
        keywords=["JATS", "XML", "Validation"]
    )
    
    # Body sections
    p = Paragraph(content=[
        InlineRun(text="This paragraph contains "),
        InlineRun(text="bold text", bold=True),
        InlineRun(text=" and "),
        InlineRun(text="italicized text", italic=True),
        InlineRun(text=".")
    ])
    
    sec = Section(
        id="sec-intro",
        level=1,
        heading="Introduction",
        content=[p]
    )
    doc.body.append(sec)
    
    # References
    ref = Reference(
        id="ref-1",
        type="journal-article",
        authors=[ReferenceAuthor(family="Mandelbrot", given="Benoit")],
        year="1982",
        title="The Fractal Geometry of Nature",
        source_title="W. H. Freeman and Co",
        volume="1",
        pages="1-200"
    )
    doc.references.append(ref)
    
    return doc

def test_jats_generation_basic(clean_document):
    generator = JatsGenerator()
    xml_bytes = generator.generate(clean_document)
    
    assert xml_bytes.startswith(b"<?xml")
    
    # Parse generated xml using lxml to assert structure
    root = etree.fromstring(xml_bytes)
    assert root.tag == "article"
    assert root.attrib["dtd-version"] == "1.3"
    
    # Front metadata check
    title_el = root.find(".//article-title")
    assert title_el is not None
    assert title_el.text == "A Secure Schema-Validating Pipeline"
    
    surname_el = root.find(".//contrib/name/surname")
    assert surname_el.text == "Smith"
    
    email_el = root.find(".//contrib/email")
    assert email_el.text == "jane.smith@science.org"
    
    # Body check
    p_el = root.find(".//body/sec/p")
    assert p_el is not None
    # Formatting run verification
    assert p_el.text == "This paragraph contains "
    
    bold_el = p_el.find("bold")
    assert bold_el is not None
    assert bold_el.text == "bold text"
    
    italic_el = p_el.find("italic")
    assert italic_el is not None
    assert italic_el.text == "italicized text"

def test_jats_schema_validation_passes(clean_document):
    generator = JatsGenerator()
    xml_bytes = generator.generate(clean_document)
    
    # Validate against local JATS 1.3 XSD schemas
    errors = validate_jats_xml(xml_bytes)
    assert len(errors) == 0, f"Validation errors found: {', '.join(errors)}"

def test_jats_schema_validation_fails_on_invalid_xml():
    # Corrupt XML (missing required front element structure)
    invalid_xml = b'<?xml version="1.0" encoding="UTF-8"?>\n<article dtd-version="1.3"><body/></article>'
    errors = validate_jats_xml(invalid_xml)
    
    # Assert validation failed and returned error messages
    assert len(errors) > 0
    assert any("front" in err.lower() or "missing" in err.lower() or "child" in err.lower() for err in errors)

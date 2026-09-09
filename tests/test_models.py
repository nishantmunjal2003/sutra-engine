import json
from sutra.models import (
    Document, Metadata, Section, Paragraph, InlineRun,
    Author, Affiliation, Figure, Table, TableCell,
    Reference, ReferenceAuthor, Citation
)

def test_inline_run_model():
    run = InlineRun(text="Hello", bold=True, italic=True)
    assert run.text == "Hello"
    assert run.bold is True
    assert run.italic is True
    assert run.underline is False

def test_document_scaffold_serialization():
    doc = Document()
    doc.metadata = Metadata(
        title=[InlineRun(text="A Critical Analysis of Sutra Engine", bold=True)],
        authors=[
            Author(
                given_name="John",
                family_name="Doe",
                affiliation_refs=["aff-1"],
                email="john.doe@example.edu"
            )
        ],
        affiliations=[
            Affiliation(
                id="aff-1",
                institution="University of Excellence",
                country="USA"
            )
        ],
        keywords=["AI", "Publishing", "JATS"]
    )
    
    # Body sections
    p1 = Paragraph(
        content=[
            InlineRun(text="This is the first paragraph. "),
            InlineRun(text="Formatted text.", italic=True)
        ]
    )
    
    table_cell_1 = TableCell(content=[InlineRun(text="Header 1")], is_header=True)
    table_cell_2 = TableCell(content=[InlineRun(text="Value 1")])
    tbl = Table(
        id="tbl-1",
        caption=[InlineRun(text="Sample Table")],
        rows=[[table_cell_1], [table_cell_2]]
    )
    
    sec = Section(
        id="intro",
        level=1,
        heading="Introduction",
        content=[p1, tbl]
    )
    doc.body.append(sec)
    
    # Reference list
    ref = Reference(
        id="ref-1",
        type="journal-article",
        authors=[ReferenceAuthor(family="Smith", given="Alice")],
        year="2024",
        title="Automated Single Source Typesetting",
        source_title="Journal of Digital Scholarly Production",
        volume="12",
        issue="3",
        pages="101-110",
        doi="10.1234/jdsp.2024.12.3.101"
    )
    doc.references.append(ref)
    
    # Citation
    cit = Citation(marker_id="cit-1", style="numeric", reference_ids=["ref-1"])
    doc.citations.append(cit)
    
    # Serialize to JSON and parse back
    doc_json = doc.model_dump_json()
    parsed_dict = json.loads(doc_json)
    
    reparsed_doc = Document.model_validate(parsed_dict)
    
    assert reparsed_doc.metadata.title[0].text == "A Critical Analysis of Sutra Engine"
    assert reparsed_doc.metadata.authors[0].family_name == "Doe"
    assert reparsed_doc.metadata.affiliations[0].institution == "University of Excellence"
    assert len(reparsed_doc.body) == 1
    assert reparsed_doc.body[0].heading == "Introduction"
    assert reparsed_doc.body[0].content[0].type == "paragraph"
    assert reparsed_doc.body[0].content[1].type == "table"
    assert reparsed_doc.body[0].content[1].rows[0][0].is_header is True
    assert reparsed_doc.references[0].authors[0].family == "Smith"
    assert reparsed_doc.citations[0].reference_ids == ["ref-1"]

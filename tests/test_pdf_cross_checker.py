"""
tests/test_pdf_cross_checker.py — Unit Tests for PDFBlockCrossChecker & AI Change Tracking
"""

import os
import pytest
from sutra.ai.pdf_cross_checker import PDFBlockCrossChecker


PDF_SAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "inputandoutput",
    "Output-7024.pdf"
)


def test_pdf_cross_checker_file_not_found():
    """Verify FileNotFoundError is raised if PDF path does not exist."""
    with pytest.raises(FileNotFoundError):
        PDFBlockCrossChecker("non_existent_manuscript.pdf")


def test_pdf_cross_checker_initialization():
    """Verify valid PDF path initializes properly."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)
    assert checker.pdf_path == PDF_SAMPLE_PATH


def test_pdf_cross_checker_empty_blocks():
    """Verify empty block list returns a safe empty response."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)
    result = checker.cross_check([])
    assert result["blocks"] == []
    assert result["changes"] == []
    assert result["updated_count"] == 0
    assert result["provider"] == "pdf-cross-check"


def test_pdf_cross_checker_layout_analysis():
    """Verify layout metadata is properly extracted from the reference PDF."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)
    sample_blocks = [
        {"id": "blk-1", "type": "paragraph", "content": "1. Introduction"}
    ]
    result = checker.cross_check(sample_blocks)
    assert "pdf_stats" in result
    assert result["pdf_stats"]["pages"] > 0
    assert result["pdf_stats"]["body_size"] > 0


def test_heading_misclassification_correction():
    """Verify misclassified headings are corrected with ai_change provenance."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)

    blocks = [
        {"id": "b1", "type": "paragraph", "content": "1. Introduction"},
        {"id": "b2", "type": "paragraph", "content": "This is body text discussing the problem."},
        {"id": "b3", "type": "paragraph", "content": "2. Materials and Methods"},
        {"id": "b4", "type": "paragraph", "content": "3. Results and Discussion"},
        {"id": "b5", "type": "paragraph", "content": "4. Conclusion"},
    ]

    result = checker.cross_check(blocks)
    changes = result["changes"]
    updated_blocks = result["blocks"]

    # At least the introduction and methods should be corrected to heading_l1
    h1_changes = [c for c in changes if c["new_type"] == "heading_l1"]
    assert len(h1_changes) >= 1

    # Verify block b1 now has type heading_l1 and ai_change metadata
    b1 = next(b for b in updated_blocks if b["id"] == "b1")
    assert b1["type"] == "heading_l1"
    assert b1["is_ai_assisted"] is True
    assert "ai_change" in b1
    assert b1["ai_change"]["old_type"] == "paragraph"
    assert b1["ai_change"]["new_type"] == "heading_l1"
    assert b1["ai_change"]["reviewed"] is False
    assert "PDF layout" in b1["ai_change"]["reason"]


def test_figure_misclassification_correction():
    """Verify figure captions misclassified as paragraph are converted to figure."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)

    blocks = [
        {"id": "b-fig1", "type": "paragraph", "content": "Fig. 1. Scanning electron micrograph of the sample surface."},
        {"id": "b-fig2", "type": "paragraph", "content": "Figure 2: XRD spectra of the synthesized composite materials."}
    ]

    result = checker.cross_check(blocks)
    fig1 = next(b for b in result["blocks"] if b["id"] == "b-fig1")
    fig2 = next(b for b in result["blocks"] if b["id"] == "b-fig2")

    assert fig1["type"] == "figure"
    assert fig1["ai_change"]["old_type"] == "paragraph"
    assert fig1["ai_change"]["new_type"] == "figure"
    assert "Fig" in fig1["ai_change"]["reason"]

    assert fig2["type"] == "figure"
    assert fig2["ai_change"]["new_type"] == "figure"


def test_table_misclassification_correction():
    """Verify table labels misclassified as paragraph are converted to table."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)

    blocks = [
        {"id": "b-tbl1", "type": "paragraph", "content": "Table 1. Elemental composition obtained from EDX analysis."},
        {"id": "b-tbl2", "type": "paragraph", "content": "Tab. 2: Summary of tensile strength measurements across specimens."}
    ]

    result = checker.cross_check(blocks)
    tbl1 = next(b for b in result["blocks"] if b["id"] == "b-tbl1")
    tbl2 = next(b for b in result["blocks"] if b["id"] == "b-tbl2")

    assert tbl1["type"] == "table"
    assert tbl1["ai_change"]["new_type"] == "table"
    assert "Table" in tbl1["ai_change"]["reason"]

    assert tbl2["type"] == "table"
    assert tbl2["ai_change"]["new_type"] == "table"


def test_reference_misclassification_correction():
    """Verify reference entries following References heading are corrected to reference_list."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)

    blocks = [
        {"id": "b-ref-hdr", "type": "heading_l1", "content": "References"},
        {"id": "b-ref-1", "type": "paragraph", "content": "[1] Smith, J., Doe, A. Journal of Advanced Materials, 2023, 45, 112-120."},
        {"id": "b-ref-2", "type": "paragraph", "content": "[2] Johnson, R. Polymer Science and Engineering, 2022, 18, 55-64."}
    ]

    result = checker.cross_check(blocks)
    ref1 = next(b for b in result["blocks"] if b["id"] == "b-ref-1")
    ref2 = next(b for b in result["blocks"] if b["id"] == "b-ref-2")

    assert ref1["type"] == "reference_list"
    assert ref1["ai_change"]["old_type"] == "paragraph"
    assert ref1["ai_change"]["new_type"] == "reference_list"

    assert ref2["type"] == "reference_list"
    assert ref2["ai_change"]["new_type"] == "reference_list"


def test_no_false_positives_when_already_correct():
    """Verify blocks that are already classified correctly are NOT changed."""
    if not os.path.exists(PDF_SAMPLE_PATH):
        pytest.skip("Output-7024.pdf not found in inputandoutput/")
    checker = PDFBlockCrossChecker(PDF_SAMPLE_PATH)

    blocks = [
        {"id": "b1", "type": "heading_l1", "content": "1. Introduction"},
        {"id": "b2", "type": "paragraph", "content": "This is normal body paragraph text with no special prefix."},
        {"id": "b3", "type": "figure", "content": "Fig. 1. Morphology overview."},
        {"id": "b4", "type": "table", "content": "Table 1. Quantitative dataset."},
        {"id": "b5", "type": "heading_l1", "content": "References"},
        {"id": "b6", "type": "reference_list", "content": "[1] Alpha, B. Title, 2020."}
    ]

    result = checker.cross_check(blocks)
    assert result["updated_count"] == 0
    assert len(result["changes"]) == 0
    for b in result["blocks"]:
        assert "ai_change" not in b

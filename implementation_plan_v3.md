# Journal Template System — Implementation Plan v3

---

## How the Workflow Changes

### Current Workflow (what exists today)
```
Upload DOCX
    │
    ▼
Parse → IR → Blocks appear in Editor UI
    │
    ▼
Editor reviews blocks:
  ✓ Is this block typed correctly? (heading / paragraph / figure / table / etc.)
  ✓ Flag anything unrecognized, retag as needed
    │
    ▼
Click "Generate"
    │
    ▼
LaTeX generated (generic single template) → PDF compiled
JATS XML generated
    │
    ▼
Download ZIP (pdf / xml / tex / reports)
```

**Problems with current workflow:**
- One generic template — no journal-specific styling
- After generation, editor can only download — no way to review or fix the output
- Minor issues (wrong heading level, small text fix) require re-uploading the whole DOCX

---

### New Workflow (what we are building)
```
PHASE A — Journal Onboarding (done ONCE per journal, e.g. "ANRF Journal")
──────────────────────────────────────────────────────────────────────────
Upload reference published PDF (e.g. Output-7042.pdf)
    │
    ▼
PDF Analyzer extracts settings:
  • Page: paper size, margins, column count
  • Fonts: body text, title, headings H1/H2/H3, abstract, captions, references
  • Sizes: pt values for every element type
  • Spacing: line spacing, paragraph indent, section spacing
    │
    ▼
Settings Review UI (editable form, grouped by element):
  [Page]       [Title Block]    [Abstract/Keywords]
  [H1 / H2 / H3 Headings]      [Body Text]
  [Equations]  [Figures]        [Tables]  [References]
    │
  Editor verifies each value, corrects anything wrong
    │
    ▼
"Save as Journal Profile" → saved as:
  build/journals/anrf-journal/settings.json   ← "ANRF Journal" template


PHASE B — Per-Article Conversion (done for every manuscript)
──────────────────────────────────────────────────────────────
Upload DOCX
    │
    ▼
Parse → IR → Blocks appear in Editor UI (SAME AS TODAY)
    │
STEP 1 — Block Review (existing, unchanged):
  ✓ Verify each block is typed correctly
  ✓ Retag unrecognized blocks
  ✓ Confirm all blocks
    │
    ▼
Pick Journal Profile: [ANRF Journal ▼]
Click "Generate"
    │
    ▼
Apply ANRF Journal settings.json → Generate LaTeX + compile PDF
Apply ANRF Journal settings.json → Generate JATS XML
    │
    ▼
STEP 2 — Output Review (NEW — same spirit as block review, but for the result):
  • PDF renders in a split-panel viewer
  • Left side: the typeset PDF (page by page)
  • Right side: editable content panel, block by block
  • Each block in the output is highlighted/clickable
  • Editor can:
      - Fix a typo or wording directly in the text
      - Correct a heading level (H2 → H1)
      - Edit a caption
      - Mark a figure/table for manual handling
      - Add/remove a keyword
      - Fix author name or affiliation text
  • Changes go back into the IR (not the raw LaTeX)
  • Click "Regenerate" → re-applies template → fresh PDF instantly
    │
    ▼
"Finalize & Download"
    │
    ▼
Download ZIP (article.pdf / article.xml / article.tex / reports)
```

---

## First Journal Profile: "ANRF Journal"

The `inputandoutput/` folder contains real ANRF (Anusandhan National Research Foundation) manuscript pairs:
- `Input-7024.docx` → `Output-7024.pdf`
- `Input 7042.docx` → `Output-7042.pdf`

These will be used to:
1. Run the PDF Analyzer against `Output-7024.pdf` and `Output-7042.pdf`
2. Produce a draft `settings.json` for "ANRF Journal"
3. User verifies settings in the review UI
4. Saved as `build/journals/anrf-journal/settings.json`

This becomes the **reference implementation** of the whole template system — all future journals follow the same onboarding flow.

---

## Files to Create / Modify

### New Files

#### [NEW] `sutra/tools/pdf_analyzer.py`
Uses `pdfplumber` to extract typography from a reference PDF.
Returns a draft `JournalSettings` object with confidence scores.

#### [NEW] `sutra/models/journal_settings.py`
Pydantic model for the complete settings schema (see schema below).

#### [NEW] `sutra/tools/journal_registry.py`
Save/load/list/delete journal profiles from `build/journals/`.

---

### Modified Files

#### [MODIFY] `sutra/generator/latex.py`
- Accept `journal_settings: JournalSettings` instead of `layout: str`
- Build preamble dynamically (margins, font size, columns, heading format commands)
- Keep Jinja2 for body block rendering
- Emit `% sutra-id: {block_id}` comments per block → used by Output Review to sync PDF ↔ editor

#### [MODIFY] `sutra/web/app.py`
New endpoints:
- `POST /journals/analyze` — upload PDF → run extractor → return draft settings JSON
- `GET /journals` — list all saved profiles
- `POST /journals` — save a profile (creates `settings.json`)
- `PUT /journals/{journal_id}` — update a profile
- `DELETE /journals/{journal_id}` — delete
- `GET /journals/{journal_id}` — get one profile
- Update `POST /project/{project_id}/generate` → accept `journal_id` param
- `POST /project/{project_id}/review-edit` — accept block-level inline edits from Output Review, update IR, trigger re-generation

#### [MODIFY] `sutra/web/templates/index.html`
Three distinct panels (tabs):

**Tab 1 — Journal Profiles** (new)
- Upload reference PDF → analyze → editable settings form → save

**Tab 2 — Block Editor** (existing, enhanced)
- Same block-by-block review as today
- Now includes: "Journal Profile" picker before generating
- Generate button triggers both LaTeX+PDF and JATS

**Tab 3 — Output Review** (new)
- Split panel: PDF viewer (left) + content editor (right)
- Every block in the editor corresponds to a section of the PDF
- Inline text edits → "Regenerate" button
- Visual diff: changed blocks highlighted in yellow
- "Finalize" button → locks the output, enables download

---

## Settings.json Schema (Full — "ANRF Journal" will fill all fields)

```json
{
  "journal_id": "anrf-journal",
  "journal_name": "ANRF Journal",
  "created_at": "...",

  "page": {
    "paper_size": "a4",
    "columns": 2,
    "column_gap_pt": 12,
    "margin_top_in": 1.0,
    "margin_bottom_in": 1.0,
    "margin_left_in": 0.75,
    "margin_right_in": 0.75
  },

  "body_text": {
    "font_family": "Times New Roman",
    "font_size_pt": 10,
    "line_spacing": 1.15,
    "paragraph_indent_pt": 12,
    "paragraph_spacing_pt": 6
  },

  "title_block": {
    "title_font_size_pt": 18,
    "title_font_weight": "bold",
    "title_alignment": "center",
    "subtitle_font_size_pt": 14,
    "authors_font_size_pt": 11,
    "authors_font_style": "normal",
    "affiliation_font_size_pt": 9,
    "affiliation_font_style": "italic",
    "corresponding_marker": "*"
  },

  "abstract": {
    "heading_text": "Abstract",
    "heading_font_size_pt": 11,
    "heading_font_weight": "bold",
    "body_font_size_pt": 9,
    "indented": true,
    "box_border": false,
    "structured_labels_bold": true
  },

  "keywords": {
    "label_text": "Keywords:",
    "label_font_weight": "bold",
    "font_size_pt": 9,
    "separator": "; "
  },

  "headings": {
    "h1": {
      "font_size_pt": 12,
      "font_weight": "bold",
      "font_style": "normal",
      "alignment": "left",
      "numbering": "numeric",
      "space_before_pt": 12,
      "space_after_pt": 6,
      "all_caps": false
    },
    "h2": {
      "font_size_pt": 11,
      "font_weight": "bold",
      "font_style": "italic",
      "alignment": "left",
      "numbering": "numeric",
      "space_before_pt": 8,
      "space_after_pt": 4,
      "all_caps": false
    },
    "h3": {
      "font_size_pt": 10,
      "font_weight": "normal",
      "font_style": "italic",
      "alignment": "left",
      "numbering": "none",
      "space_before_pt": 6,
      "space_after_pt": 3,
      "all_caps": false
    }
  },

  "equations": {
    "display_numbering": true,
    "numbering_alignment": "right",
    "numbering_bracket": "parentheses",
    "font_size_pt": 10
  },

  "figures": {
    "caption_position": "below",
    "caption_label_prefix": "Figure",
    "caption_label_style": "bold",
    "caption_font_size_pt": 9,
    "span_wide_figures": true
  },

  "tables": {
    "caption_position": "above",
    "caption_label_prefix": "Table",
    "caption_label_style": "bold",
    "caption_font_size_pt": 9,
    "border_style": "booktabs",
    "span_wide_tables": true
  },

  "references": {
    "section_heading_text": "References",
    "citation_style": "numeric",
    "font_size_pt": 9,
    "hanging_indent": true
  },

  "conclusion": {
    "heading_text": "Conclusion"
  }
}
```

---

## Output Review UI — Detailed Behaviour

This mirrors the existing block editor philosophy: **never silently fix — always show the editor what was detected and let them confirm or correct.**

| Scenario | What editor sees | What they can do |
|---|---|---|
| Correct heading | Green ✓ badge | Click to expand and edit text |
| Wrong heading level | Yellow ⚠ badge | Change level dropdown (H1/H2/H3) |
| Author name typo | No badge (looks correct) | Click text to edit inline |
| Figure missing caption | Red ✗ badge | Type caption directly |
| Long equation cut off | Yellow ⚠ badge | Flag for manual LaTeX edit |
| Reference missing DOI | Yellow ⚠ badge | Fill in DOI field |
| Any block | Any state | "Flag for Manual Handling" option |

**Regenerate** button re-runs `LatexGenerator.generate(doc, settings)` with the updated IR and re-renders the PDF. No full re-upload required.

---

## Verification Plan

1. Run PDF analyzer on `Output-7042.pdf` → verify single-column detected
2. Run PDF analyzer on `Output-7024.pdf` → verify two-column detected
3. Save both as "ANRF Journal" settings variants
4. Upload `Input-7024.docx` → apply ANRF Journal → generate → compare output PDF to `Output-7024.pdf` visually
5. Use Output Review to fix one item → Regenerate → verify change appears in PDF
6. Confirm JATS XML still validates after inline edits

---

> [!NOTE]
> Ready to proceed with this plan? The build order will be:
> 1. `JournalSettings` Pydantic model
> 2. PDF Analyzer
> 3. Journal Registry + API endpoints
> 4. Updated `LatexGenerator` (settings-driven)
> 5. Journal Profiles UI tab
> 6. Output Review UI tab (inline edit + regenerate)
> 7. ANRF Journal profile from the two reference PDFs

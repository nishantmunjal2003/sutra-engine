# agent.md — Sutra Press: Manuscript Conversion Engine

## 0. Purpose & Scope

This document specifies an autonomous/semi-autonomous coding agent's mandate for
building **Phase 1** of a journal production system, named **Sutra Press**: a
**manuscript conversion engine** that ingests an author's raw manuscript
(DOCX, or LaTeX) and produces:

1. A clean, validated **JATS XML** file (the format OJS, PubMed Central, DOAJ,
   and Crossref expect), and
2. A compiled **LaTeX → PDF** typeset version of the same article,

from a **single structured source**, so both outputs stay in sync the way
single-source production tools do — when something changes, it's fixed once
and regenerated everywhere, not patched separately in two files.

This is an original system built on established open standards (JATS, OOXML,
LaTeX) and open-source libraries. It is **not** a clone of any specific
commercial product's interface, branding, or proprietary code — it is an
implementation of a well-documented industry pattern (manuscript → XML →
PDF/HTML, "single-source publishing") that many open-source projects already
implement in pieces (see §2).

### 0.1 Why "Sutra Press"

*Sūtra* (सूत्र) is Sanskrit for **"thread."** Classically, a *sutra* is also a
specific genre of text: a tightly-structured, rule-bound aphorism or formula
designed to compress and organize knowledge precisely — the opposite of loose,
unstructured prose.

Both senses of the word describe exactly what this engine does:

- **Thread**: a single internal representation (the IR, §5.3) runs through
  the whole pipeline like a thread, with JATS XML and LaTeX/PDF as two ends
  of the *same* thread rather than two separately-spun ones. This is the
  literal mechanism behind the single-source sync guarantee in §3.1.
- **Rule-bound structure from loose input**: the engine's entire job is
  taking an author's loosely-formatted manuscript and *threading it into*
  rigorous, schema-validated structure — JATS XML that must pass NISO schema
  validation (§6 step 7), LaTeX that must compile cleanly (§6 step 9). A
  sutra compresses meaning into precise, rule-following form; this engine
  does the same to manuscripts.

There's also a quieter reason: this project's starting point was a look at
**Sutrivia Solutions**, a publishing-technology vendor whose name and
"Manuscript Essential" product prompted the original research that led here.
*Sutra Press* echoes that etymological root (*sūtra*) without copying
Sutrivia's name, branding, or product — it's an independent, original system
built from first principles and open standards, not a derivative of theirs.

**Use this story directly when building the app's front page / landing copy**
(Phase 1.5+, §10): the "thread" metaphor is visual gold — a single thread
running through a tangled manuscript and coming out the other side as
organized, structured documents (XML on one side, a typeset PDF on the
other) is a natural hero illustration / animation concept, and "press" in
the name honors the traditional meaning (a *press* — as in *printing
press* — being where raw manuscripts become finished, published work).

**Out of scope for Phase 1** (candidates for Phase 2+, see §10):
- Peer review / submission management
- Author/editor accounts, roles, permissions
- Journal website / OA hosting
- Payment, APC handling
- HTML article rendering (PDF + JATS XML only in Phase 1)

---

## 1. Problem Statement

Editorial teams at small/independent journals receive manuscripts as DOCX or
LaTeX. To publish, they need:

- A **typeset PDF** (for readers, print, indexing)
- A **JATS XML** file (for OJS ingestion, PubMed Central, DOAJ, Crossref
  metadata deposits)

Today this is either done by hand (slow, error-prone, hours per article) or
via fragmented tooling that doesn't keep the two outputs in sync. The engine
in this spec automates the conversion with a **deterministic, inspectable
pipeline** — not an opaque black box — so editors can debug and fix failures
without starting over.

---

## 2. Prior Art the Agent Should Study (do not skip this)

Before writing code, read and understand these existing open-source
approaches. They represent decades of accumulated lessons about where this
problem gets hard:

| Project | What to learn from it |
|---|---|
| [Vitaliy-1/docxConverter](https://github.com/Vitaliy-1/docxConverter) | OJS 3 plugin, DOCX→JATS via PHP. Good reference for which DOCX structural elements (runs, styles, lists, tables, footnotes) map cleanly to JATS and which don't. |
| [jffng/convert-docx-md-jatss](https://github.com/jffng/convert-docx-md-jatss) (romchip.org) | Pandoc-based DOCX→Markdown→JATS with custom post-processing for citations/footnotes. Good reference for the "Pandoc as a base, then patch the gaps" strategy. |
| [ronste/sspworkflow](https://github.com/ronste/sspworkflow) | Containerized docx→JATS→HTML→PDF toolchain. Good reference for pipeline/container architecture and Paged.js-based PDF generation as a LaTeX alternative. |
| [ub-unibe-ch/Docx2Jats](https://github.com/ub-unibe-ch/Docx2Jats) | Minimal `pandoc -s -t jats` workflow with manual metadata post-processing. Good reference for the floor of what's possible with zero custom code, and exactly what metadata Pandoc *doesn't* handle. |
| meTypeset / meXml (Martin Paul Eve, Birkbeck) | Historical but instructive: a "triage mode" that tells the editor up front whether a document is too messy to auto-convert, rather than producing silently broken output. **Adopt this pattern.** |
| JATS NLM/NCBI XSLT stylesheets | Reference XSLT for JATS→HTML and JATS→XSL-FO→PDF. Useful as a fallback PDF path if the LaTeX path fails on a given document. |
| `Vitaliy-1/JATS2LaTeX` | JATS→LaTeX+BibTeX converter — relevant for Phase 1's specific direction (we go DOCX→[intermediate]→ both JATS and LaTeX). |

Key lesson echoed across all of these: **no automated DOCX→JATS converter
handles 100% of arbitrary manuscripts.** Style consistency in the source
document matters enormously. The agent must design for partial success +
clear failure reporting, not silent best-effort mangling.

---

## 3. Recommended Architecture

### 3.1 Pipeline shape

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Manuscript  │────▶│  Structural IR    │────▶│  JATS XML          │
│  DOCX/LaTeX  │     │  (internal model) │     │  (validated)        │
└──────────────┘     └──────────────────┘     └───────────────────┘
                              │
                              ▼
                      ┌───────────────────┐     ┌─────────────┐
                      │  LaTeX source      │────▶│  PDF        │
                      │  (from template)   │     │  (compiled) │
                      └───────────────────┘     └─────────────┘
```

The critical architectural decision: **do not** convert DOCX→JATS and
DOCX→LaTeX as two independent parallel paths. That's how single-source
guarantees break. Instead:

1. Parse the manuscript into one **internal structural representation (IR)**
   — a typed document tree (title, authors, affiliations, abstract, sections,
   paragraphs with inline marks, figures, tables, citations, references,
   footnotes).
2. Generate **JATS XML** from the IR.
3. Generate **LaTeX** from the IR using a journal template.
4. Compile LaTeX → PDF.

This mirrors what the production-grade tools in §2 converge on (Pandoc's
internal AST, transpect's "Hub XML" intermediate format) and is the only way
to honestly claim single-source sync. See §3.3 for why this must be a
**fan-out from the IR** (JATS and LaTeX as parallel siblings) rather than a
**chain through LaTeX** (IR → LaTeX → JATS) — that alternative was
considered and explicitly rejected.

### 3.2 Recommended stack

No strong constraint was given, so recommend based on ecosystem maturity for
this specific problem:

- **Core language: Python 3.12+**
  Reasoning: Pandoc's Python bindings (`panflute`), `python-docx` for raw
  OOXML access when Pandoc's AST loses fidelity, `lxml` for JATS
  construction/validation, and the existing prior art (§2) is predominantly
  Python. This minimizes translation friction when borrowing techniques from
  those projects.

- **DOCX parsing: Pandoc (via `pypandoc` or subprocess) as the primary path**,
  with `python-docx` as a **fallback/supplement** for elements Pandoc's AST
  drops or flattens (e.g., some footnote edge cases, complex table merges,
  embedded equation objects). Do not write a DOCX parser from scratch — OOXML
  is large and the prior art already converged on Pandoc-as-base.

- **Internal IR: a typed Python object model** (e.g. `dataclasses` or
  `pydantic` models — pydantic preferred for built-in validation), not raw
  Pandoc JSON AST passed through directly. Build a thin translation layer:
  Pandoc AST → IR. This keeps JATS/LaTeX generators decoupled from Pandoc's
  specific AST shape, so the parser can be swapped or supplemented later
  without rewriting the generators.

- **JATS generation: `lxml` building JATS 1.3 (NISO JATS) directly from the
  IR**, validated against the **official JATS XSD/DTD** (NISO publishes
  these). Do not hand-roll string templating for XML — use a real XML
  library so output is well-formed by construction.

- **LaTeX generation: Jinja2 templates** (with LaTeX-safe delimiters, e.g.
  `\BLOCK{}` / `\VAR{}` instead of default `{{ }}` to avoid clashing with
  LaTeX's own braces) rendering into a **journal article class** (start with
  a generic class like `article` or an open template such as the **LaTeX
  Journal Article Template** family; do not invent a new document class from
  scratch in Phase 1).

- **PDF compilation: Tectonic** (a modern, self-contained, reproducible
  LaTeX engine — no system-wide TeX Live install needed, deterministic
  output, good for containerized/CI use) preferred over invoking
  `pdflatex`/`xelatex` directly. Fall back to `latexmk` + a pinned TeX Live
  if Tectonic can't resolve a needed package.

- **Validation:** `lxml`'s XSD validation against the JATS schema is a hard
  gate before declaring conversion successful — see §6.

- **Packaging/orchestration:** a single CLI (e.g. `sutra convert
  input.docx --out ./build/`) plus a thin FastAPI wrapper for Phase 1.5
  (web upload), but build the CLI first — the web layer is just a thin
  shell around it.

### 3.3 Why not X?

Document these rejected alternatives in the repo's `ADRs/` (architecture
decision records) so future contributors don't re-litigate them:

- **XSLT/XSL-FO as the primary toolchain**: powerful and precise (it's what
  NLM's own stylesheets use) but steep learning curve, sparse contributor
  pool today, and per §2's eLife report, teams that tried it recommend
  routing effort into Pandoc-based approaches instead for new projects.
  Keep XSLT as an optional fallback renderer (JATS→HTML preview), not the
  backbone.
- **wkhtmltopdf / Paged.js for PDF**: viable for HTML-first pipelines (see
  `sspworkflow`), but produces visually different output from "real" LaTeX
  typesetting that journals/readers expect, and per the CaSSius experience
  in eLife's own report, headless-browser PDF generation has had reliability
  problems with multi-page documents. LaTeX remains the more battle-tested
  choice for academic PDF fidelity.
- **Chained pipeline: IR → LaTeX → JATS** (generate LaTeX first, then derive
  JATS from the generated LaTeX, instead of generating both independently
  from the IR). This was seriously considered — the intuition is that LaTeX
  is closer to a "finished, reviewable" artifact, so later conversion
  off of it should be easier. Rejected for four concrete reasons:
  1. **LaTeX is presentational, not semantic.** Commands like `\textbf{}`
     or manually-sized headings describe *appearance*, not structure. JATS
     needs structural facts (`<sec><title>`, `<table-wrap>`, etc.). Routing
     through LaTeX means the JATS generator has to *reverse-engineer*
     structure out of formatting commands — i.e. rebuild a worse copy of
     the IR you already had, by re-parsing your own rendered output.
  2. **LaTeX is hard to parse back out of, by design.** TeX is effectively
     Turing-complete and macro-extensible. The most mature tool that does
     exactly this conversion, LaTeXML — a NIST project with 20+ years of
     development — still documents real fidelity gaps because "emulating
     TeX is kinda hard." If the most established tool in this space still
     has coverage gaps after two decades, treat that as a strong signal,
     not a solvable-with-more-effort detail.
  3. **It doubles down on the wrong parsing problem.** DOCX (OOXML) is a
     large but *finite, documented* XML vocabulary with a mature parser
     ecosystem (Pandoc) the whole industry already leans on. LaTeX's
     macro-extensibility makes it the *harder* of the two to parse
     robustly, not the easier one — so this ordering trades a well-solved
     problem for a notoriously hard one, in the wrong direction.
  4. **It breaks single-source sync, which is this architecture's entire
     premise.** If an editor hand-fixes the generated `.tex` file during
     proofing (explicitly allowed — see deliverable in §6 step 10), and
     JATS is derived *from* that LaTeX, then LaTeX becomes ground truth and
     JATS becomes a stale derivative the moment edits happen. That's the
     exact two-pipeline-drift failure mode §3.1 exists to prevent.

  **Decision:** JATS XML and LaTeX are generated as **parallel siblings
  from the IR**, never one from the other. If an editor needs to fix
  something, the fix happens at the IR level (or by re-uploading a
  corrected manuscript) so both outputs regenerate in sync — not by hand-
  editing one rendered output and hoping the other catches up.
  (Note: `.tex` remains a valid *input* format per §6 step 1 — parsing an
  author-supplied LaTeX manuscript into the IR is a different problem from
  using LaTeX as an internal hop, and is not affected by this decision.)

---

## 4. Page Layout: Single-Column vs. Two-Column

Manuscripts arrive as plain single-column DOCX/LaTeX (the common authoring
format), but **published output** is often required in either single-column
(common in humanities/social science journals, books) or two-column
(common in STEM journals — IEEE, many AMS/physics/biomed templates) layout.

**Key principle: column layout is a render-time template concern, not a
content concern.** It must never enter the IR (§5.3). The IR describes *what*
the article contains (a figure, a table, a paragraph) — never *how many
columns* the page has. This keeps the same source manuscript convertible to
either layout on demand, and keeps JATS generation (which has no concept of
columns at all — JATS is semantic, not presentational) completely unaffected
by this decision.

### 4.1 Where column count is decided

- **Input side**: irrelevant. Whether the author's DOCX was typed in one
  column or two, the parser (§6 step 3-4) extracts content only — column
  breaks in the source are discarded as presentation noise, not preserved
  in the IR. (Word's two-column section breaks are a layout artifact, not
  structural information.)
- **Output side**: chosen via a **template parameter** at LaTeX-generation
  time (§6 step 8): `sutra convert input.docx --out ./build/
  --layout=single|double`. Default to whatever the target journal's house
  style requires; make it a per-journal config value, not a global
  default, since different journals on the same engine instance will want
  different defaults.

### 4.2 LaTeX template implications

This is where most of the real engineering work is, because column count
changes layout behavior for several element types, not just the page grid:

| Element | Single-column behavior | Two-column behavior |
|---|---|---|
| Body text | `article` class default, or `onecolumn` | `\documentclass[twocolumn]{article}` or a journal class that defaults to two-column (e.g. IEEEtran) |
| Wide tables/figures | Fit naturally within the text width | Often need to **span both columns** — requires `figure*`/`table*` (the `*`-starred float environments) rather than the normal float. The IR needs a `span: column \| page` hint per figure/table so the LaTeX generator picks the right environment. |
| Equations | Usually fit inline in the wider column | Long/wide equations frequently need to break or span — flag equations above a width threshold during generation, don't silently truncate |
| Footnotes | Standard `\footnote` | Same mechanism, but interacts with column balancing in some templates — pick a template family that already solves this (don't hand-roll column balancing) |
| Reference list | Normal flow | Usually two-column itself, often smaller font — controlled by template class option, not custom code |

**Action item for the agent:** the IR's figure/table nodes (§5.3) must include
an explicit `span_hint: "column" | "page"` field, populated either from
explicit author intent (if discoverable — e.g. an oversized table in the
DOCX) or defaulted to `"column"` with a triage-report flag suggesting editor
review when a table/figure's natural width suggests it won't fit one column
(e.g. more than ~5-6 columns of tabular data, or an image above a width
heuristic).

### 4.3 Practical implementation note

Maintain **two LaTeX template variants per journal style** (single-column,
two-column) sharing the same Jinja2 partials for the parts that don't differ
(title block, abstract, references formatting) and differing only in
preamble (`\documentclass[...]`) and float-spanning logic. Do not maintain
one template with runtime column-count branching scattered through it — two
clean templates that diverge where needed and share includes where they
don't is more maintainable.

---

## 5. Complete Manuscript Content Inventory

Before the IR schema (§5.2), here is the **exhaustive list** of everything a
real academic manuscript can contain. The agent should treat this as the
acceptance checklist for "what must this engine eventually be able to
parse, represent, and re-render" — not everything needs full support in
the first build (see priority tiers), but everything needs an explicit
decision (support / partial support with flag / explicit rejection),
never silent omission, per the Failure Philosophy in §7.

### 5.1 Full inventory by category

**A. Front matter / metadata**
- Article title (with inline formatting: italics for species names, sub/
  superscript for chemical formulas, special characters)
- Running title / short title
- Author names (with given/family name distinction for indexing)
- Author affiliations (institution, department, address, country) and
  author↔affiliation linking (multiple authors can share or differ)
- Corresponding author designation + email
- Author identifiers: ORCID iDs
- Author contribution statements (CRediT taxonomy roles)
- Equal-contribution / co-first-author markers
- Abstract (plain or structured: Background/Methods/Results/Conclusion)
- Graphical abstract (image)
- Keywords list
- Subject classification codes (e.g. MSC, PACS, JEL codes depending on
  field)
- Article type (research article, review, case report, letter, editorial,
  correction/erratum, retraction)
- Funding statements (funder name, grant/award number, recipient)
- Conflict of interest / competing interests statement
- Ethics statement (IRB approval, animal ethics, consent statements)
- Data availability statement
- Acknowledgments
- Word count / page count metadata (sometimes required by journals)
- Received/revised/accepted date stamps
- License / copyright statement (e.g. CC-BY)
- DOI (assigned post-acceptance, but the field must exist)
- Journal-level metadata (journal title, ISSN, volume, issue, publisher) —
  technically not per-article but required in the JATS `<journal-meta>`
  wrapper

**B. Body text structures**
- Section headings (multi-level: section, subsection, sub-subsection)
- Body paragraphs
- Inline text formatting: **bold**, *italic*, underline, strikethrough,
  superscript, subscript, small caps
- Hyperlinks (external URLs)
- Cross-references (to figures, tables, equations, sections, footnotes —
  "see Figure 3", "as shown in §2.1")
- Block quotations
- Ordered lists (numbered, including nested/multi-level numbering and
  custom numbering schemes like (a), (i), roman numerals)
- Unordered (bulleted) lists, including nested
- Definition lists (term/definition pairs)
- Footnotes (page-bottom notes)
- Endnotes (end-of-document notes, distinct from footnotes and from the
  reference list)
- Sidebars / boxed text / call-out boxes
- Epigraphs
- Special/non-Latin characters and diacritics (accented characters, IPA
  symbols, non-English text fragments, Greek letters used inline outside
  math mode)
- Right-to-left or mixed-direction text fragments (where a manuscript
  quotes Arabic/Hebrew text inline) — flag as a known hard case, not
  silently mangled
- Tracked changes / revision marks (if present in the source DOCX —
  must be resolved, either by accepting/rejecting before conversion or
  by explicit triage-stage rejection of documents with unresolved
  tracked changes)
- Comments (Word reviewing comments) — must be stripped or explicitly
  surfaced, never silently merged into body text

**C. Figures and images**
- Raster images (PNG, JPEG, TIFF) embedded or linked
- Vector images (EPS, SVG, PDF-embedded figures) — common in STEM for
  plots/diagrams, often higher quality than raster and should be
  preserved as vector through to the PDF where possible, not rasterized
- Multi-panel figures (Figure 1A, 1B, 1C as sub-parts of one figure)
- Figure captions (with their own inline formatting/citations)
- Alt-text / accessibility descriptions (required field in modern JATS
  for accessibility compliance — don't treat as optional)
- Figure numbering and cross-reference targets
- Figures requiring full-page or landscape orientation
- Figures requiring column-span (see §4) vs. single-column fit
- Supplementary/non-typeset images (referenced but not printed inline —
  common for supplementary data files)

**D. Tables**
- Simple tables (uniform rows/columns)
- Tables with merged cells (column span, row span)
- Tables with multi-row headers
- Tables with footnotes (table-specific notes, distinct from body
  footnotes, often using symbols like *, †, ‡ rather than numbers)
- Tables with embedded formatting (bold headers, shaded rows)
- Wide tables requiring column-span or page-rotation (landscape table)
- Tables that exceed one page (need continuation handling — "Table 2
  continued")
- Tables containing math/special notation in cells

**E. Mathematical content**
- Inline equations (within a text line)
- Display equations (standalone, numbered)
- Equation numbering and cross-references ("as in Eq. 4")
- Multi-line/aligned equation systems
- Equations authored as native OOXML math (OMML) — the preferred,
  convertible case
- Equations authored as embedded images (screenshots/exports from other
  software) — the hard case: no semantic source exists, must be flagged
  in triage (§6 step 2) since these cannot be converted to real LaTeX
  math or MathML, only embedded as images (degraded output)
- Chemical formulas/structures (may need dedicated notation, e.g. mhchem
  for LaTeX, or be images from chemistry-specific software)
- Special mathematical symbols and operators outside standard equation
  objects (inline symbols typed via Word's symbol/Unicode insertion)

**F. Citations and references**
- In-text citation markers: numbered (`[1]`, superscript number),
  author-date (`(Smith, 2020)`), or named (`Smith (2020) showed...`)
- Multiple citations grouped (`[1,3,5]` or `[1-5]`)
- Citations to the same source appearing multiple times (must resolve to
  one reference-list entry, not duplicate entries)
- The reference list itself, with structured fields per entry: authors
  (multiple, with et al. handling), year, title, source (journal name /
  book title / conference name), volume, issue, pages, publisher, DOI,
  URL, access date (for web sources)
- Mixed reference types in one list: journal articles, books, book
  chapters, conference papers, theses, datasets, software, preprints,
  websites — each has different required structured fields in JATS
  (`<element-citation publication-type="...">`)
- Footnote-style citations (some humanities styles use footnotes for
  citations rather than a separate list — distinct from body footnotes
  in category B, must not be conflated)

**G. Supplementary / appendix material**
- Appendices (with their own heading structure, sometimes their own
  figure/table/equation numbering sequences — "Table A1")
- Supplementary files referenced but not included inline (datasets,
  videos, extended methods) — represented as metadata links, not
  embedded content
- Author biography blocks (common in some engineering/IEEE-style
  journals — short bio + photo per author at the end)

**H. Document-level / structural**
- Page breaks and section breaks (presentation-layer, generally
  discarded per §4.1, except where they signal genuine structural
  boundaries like "start of appendix")
- Headers and footers (running heads, journal name/page number — these
  are typeset-output concerns generated by the LaTeX template, not
  extracted from the source manuscript)
- Table of contents (for longer documents — generated, not authored)
- Front cover / title page as a distinct page (vs. title appearing inline
  with body start)

### 5.2 Priority tiers for implementation

Not all of §5.1 needs to ship in v1. Sequence it:

| Tier | Content | Rationale |
|---|---|---|
| **Tier 1 (must-have, blocks release)** | Title/authors/affiliations/abstract/keywords, section headings, paragraphs with basic inline formatting (bold/italic/sub/superscript), ordered/unordered lists, footnotes, simple tables, raster figures with captions, numbered in-text citations + structured reference list, hyperlinks | This covers the large majority of real-world STEM/social-science manuscripts in their common case |
| **Tier 2 (important, soon after v1)** | Multi-panel figures, merged-cell tables, vector figures, OMML equations (inline + display), author-date citation style, CRediT/funding/ethics metadata blocks, cross-references to figures/tables/equations | Common but not universal; many journals require these |
| **Tier 3 (flagged for manual handling initially)** | Equation-as-image, tracked changes, multi-page tables, landscape/rotated content, RTL text fragments, chemical structure notation, appendix-specific numbering, author bio blocks | Genuinely hard cases — triage should flag and route to manual editor handling rather than block engine development waiting for perfect automation |

### 5.3 Internal IR — Schema

The agent should implement this as the contract between parsing and
generation. Treat it as authoritative; extend additively, don't break it.
This schema is the structural backbone for everything in §5.1's Tier 1–2
content; Tier 3 items get IR node types too (so they can at least be
represented and flagged) even before full conversion logic exists for them.

```
Document
├── metadata
│   ├── title (formatted runs: italics, subscripts, etc.)
│   ├── short_title?
│   ├── authors[] (given_name, family_name, affiliation_refs[], orcid?,
│   │              corresponding?, email?, equal_contribution_group?)
│   ├── affiliations[] (id, institution, department?, address, country)
│   ├── author_contributions[] (author_ref, credit_roles[])
│   ├── abstract (structured: paragraphs, or labeled sub-sections)
│   ├── graphical_abstract? (image_ref)
│   ├── keywords[]
│   ├── subject_codes[] (scheme, code)
│   ├── article_type (research-article | review-article | case-report |
│   │                  letter | editorial | correction | ...)
│   ├── funding[] (source, award_id, recipient_ref?)
│   ├── conflict_of_interest?
│   ├── ethics_statement?
│   ├── data_availability?
│   ├── acknowledgments?
│   ├── dates (received?, revised?, accepted?)
│   ├── license (type, url)
│   └── journal_meta (title, issn?, volume?, issue?, publisher?)
├── body
│   └── sections[] (recursive: id, level, heading, numbering_scheme?,
│                    content[])
│         content items are one of:
│         - paragraph (inline_runs[]: text | bold | italic | underline |
│                       strikethrough | sub | sup | small_caps | link |
│                       xref(target_id) | inline_equation)
│         - figure (id, image_ref, format: raster|vector, caption,
│                    alt_text [required], panels[]?, span_hint:
│                    column|page, orientation: portrait|landscape)
│         - table (id, caption, rows[][] (with colspan/rowspan),
│                   header_rows: int, footnotes[], span_hint:
│                   column|page, continuation_of?: table_id)
│         - footnote (id, content, scope: body|table)
│         - endnote (id, content)
│         - block_quote (content[])
│         - list (style: ordered|unordered|definition, numbering_format?,
│                  items[] (content[], nested_list?))
│         - sidebar (heading?, content[])
│         - equation (id, source: omml|image|latex_native, latex_source?,
│                      mathml?, image_ref?, display: inline|block,
│                      numbered: bool)
│         - tracked_change_marker (type: insertion|deletion|comment,
│                                   author?, content) — surfaced to
│                                   triage, not silently resolved
├── citations[] (marker_id, style: numeric|author-date|named,
│                 reference_ids[])
├── references[] (id, type: journal-article|book|book-chapter|
│                  conference-paper|thesis|dataset|software|preprint|
│                  website, authors[] (family, given), year, title,
│                  source_title, volume?, issue?, pages?, publisher?,
│                  doi?, url?, access_date?)
├── appendices[] (id, heading, own_numbering_scope: bool, content[]
│                  — same content item types as body sections)
└── author_bios[] (author_ref, photo_ref?, bio_text)
```

**Non-negotiable requirement:** references must be parsed into structured
fields, not stored as opaque strings. This was flagged repeatedly in the
prior-art review (§2) as the single most common manual-cleanup bottleneck —
several existing tools punt on this and require editors to fix citations by
hand after conversion. Solving it properly (or at minimum, getting close via
a citation-parsing library) is this engine's main differentiator.

**Non-negotiable requirement:** every figure must carry `alt_text` as a
required (not optional) field — defaulting to an empty string with a
triage-report warning if the source manuscript doesn't supply one, never
silently omitting the attribute from output JATS, since accessibility
compliance increasingly requires it.

---

## 6. Conversion Pipeline — Step by Step

1. **Ingest**: accept `.docx` (Phase 1 primary) or `.tex` (Phase 1 secondary,
   lower priority — LaTeX→JATS is a different and harder direction; treat as
   stretch goal, not blocking).
2. **Pre-flight triage** (adopt the meTypeset pattern from §2): before
   attempting full conversion, run a structural scan and report:
   - Are headings using Word's actual heading styles, or manual bold+bigger
     text? (the latter cannot be reliably converted — flag it)
   - Are citations in a recognizable format (numbered, author-date)?
   - Are there embedded objects (equations as images vs. OMML, embedded
     spreadsheets) that need special handling?
   - Output a **triage report** (pass / pass-with-warnings / needs-manual-prep)
     *before* spending time on full conversion. This is the single highest-
     leverage feature for editor trust — silent bad output is worse than an
     honest "this document isn't ready."
3. **Parse to Pandoc AST** (`pandoc -f docx -t json`).
4. **Translate AST → IR** (custom Python layer). This is where most of the
   custom logic lives: resolving Word's style names to semantic roles,
   reconstructing reference lists, associating footnotes/endnotes, and
   pulling metadata (title page fields) into structured form rather than
   leaving them as body paragraphs.
5. **Citation/reference structuring**: parse the reference list text into
   structured fields. Use a dedicated citation-parsing library (e.g.
   something in the spirit of `anystyle` or a custom regex+heuristic layer
   informed by common styles — APA, MLA, Vancouver, IEEE) rather than
   treating each reference as an opaque string.
6. **Generate JATS XML from IR** (`lxml`), targeting **JATS 1.3 Journal
   Publishing Tag Set**, including:
   - `<journal-meta>` / `<article-meta>` from metadata
   - `<body>` from sections
   - `<back><ref-list>` from references, using `<element-citation>` with
     structured child elements (not raw strings)
   - Persistent identifiers where available: DOI, ORCID, ROR (as the
     Scholastica reference page surfaces these as standard expectations —
     §2/background research — build the schema slots for them even if
     Phase 1 doesn't auto-populate every one)
7. **Validate JATS** against the official schema (XSD or DTD). **Conversion
   is not "done" until this passes.** Validation failures must produce a
   line-numbered, human-readable error report, not a raw XML parser
   stack trace.
8. **Generate LaTeX from IR** (Jinja2 → `.tex` file + assets folder for
   figures/images, normalized to acceptable LaTeX graphics formats).
9. **Compile LaTeX → PDF** (Tectonic). Capture and surface compile errors
   with the offending LaTeX line **and** the IR/source location that
   produced it, so failures are traceable back to the original manuscript,
   not just "line 412 of generated .tex."
10. **Package output**: `{slug}/article.xml`, `{slug}/article.pdf`,
    `{slug}/article.tex` (for editor inspection/override), `{slug}/assets/`,
    `{slug}/triage-report.md`, `{slug}/validation-report.md`.

---

## 7. Failure Philosophy

This is the most important non-functional requirement, distilled from every
piece of prior art reviewed in §2:

- **Never silently drop content.** If something can't be converted (an
  embedded equation image with no OMML source, a deeply nested table), emit
  a clear placeholder + a warning in the report — do not just omit it.
- **Never produce JATS that fails schema validation and call it done.**
  Partial success must be labeled partial.
- **Make failures traceable to source location**, not just "conversion
  failed." Every IR node should retain a reference back to its origin
  (paragraph index, style name) so error messages can say "Table 3 (page 4,
  style 'Grid Table 1') could not be converted: nested table not supported."
- **Idempotency**: running the same input twice produces byte-identical
  output (important for the single-source sync promise and for CI testing).

---

## 8. Testing Strategy

- **Golden-file tests**: maintain a corpus of real-world-shaped sample DOCX
  manuscripts (varying citation styles, table complexity, figure handling)
  with known-good expected JATS XML and PDF output. Open-access journals
  publish their JATS XML publicly (PMC, DOAJ-indexed journals) — use those
  as schema-conformance references, not as literal training/copy targets.
- **Schema conformance**: every generated JATS file in CI is validated
  against the JATS XSD as a blocking check.
- **Round-trip sanity**: JATS → LaTeX (via a separate small generator) →
  diff key metadata fields against the original IR, to catch silent data
  loss.
- **PDF smoke test**: every generated PDF must be non-empty, parseable, and
  have a page count > 0 (catches silent Tectonic failures that still exit 0).

---

## 9. Deliverables for Phase 1 (definition of done)

1. CLI: `sutra convert <input.docx> --out <dir>`
2. Outputs: validated JATS 1.3 XML + compiled PDF + LaTeX source + triage
   report + validation report, as specified in §6 step 10.
3. Documented IR schema (§5.3) as the stable internal contract.
4. Test corpus + CI schema validation (§8).
5. `ADRs/` folder documenting decisions in §3.3 and any new ones made during
   build.
6. A README mapping which DOCX structures are supported / partially
   supported / unsupported in this release — set honest expectations the
   way meTypeset's "triage mode" does, rather than implying universal
   support.
7. Single-column and two-column LaTeX template variants (§4) for at least
   one reference journal style each, proving the layout-independence
   architecture end-to-end.

---

## 10. Phase 2+ (not in scope now, noted for roadmap continuity)

Once Phase 1's conversion engine is solid and validated against a real test
corpus, natural extensions — each is its own future agent.md. Suggested
naming convention to keep the "Sutra Press" identity coherent as the system
grows: `sutra-<component>` (e.g. `sutra-ojs-plugin`, `sutra-review`,
`sutra-publish`), all spokes of the same "thread" the core engine started.

- **HTML article rendering** from the same IR (third sibling output next to
  JATS/PDF)
- **Editor-facing web UI**: upload manuscript, see triage report, review/
  fix flagged issues, trigger conversion, download/preview outputs
  (FastAPI + a simple frontend; reuse the CLI as the backend engine)
  - this is a strong candidate for the **frontend-design skill** when built
  - this is also where the §0.1 "thread" landing-page narrative belongs —
    front-page hero copy, onboarding illustration, etc.
- **OJS integration**: a plugin (mirroring the architecture of
  `Vitaliy-1/docxConverter`) that calls this engine's API directly from
  within an OJS submission's Copyediting/Production stage
- **Peer review workflow** (submission, reviewer assignment, decision
  tracking) — a genuinely separate system from typesetting; do not couple
  it tightly to the conversion engine's codebase
- **OA hosting/publishing platform** — article landing pages, DOI
  registration via Crossref API, indexing exports (DOAJ, PMC)
- **Metadata enrichment automation** (citation matching/enhancement,
  ORCID/ROR auto-resolution) — flagged as ML-assisted in comparable
  commercial tools; treat as an optional post-processing stage that
  operates on already-valid JATS, never as a blocking dependency for core
  conversion.

---

## 11. Explicit Non-Goals

- This is **not** a clone of any single vendor's UI, workflows, pricing
  model, or marketing. It implements an open standard (JATS) and
  industry-common pattern (single-source manuscript production) using
  open-source components.
- Phase 1 does **not** include accounts, multi-tenant journal management, or
  payment — it is a conversion engine, usable standalone via CLI or as a
  library/service other systems (like OJS) call into.

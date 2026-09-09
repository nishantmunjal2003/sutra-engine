# testing-agent.md — Sutra Press: Test Specification

## 0. Purpose & Relationship to agent.md

This document specifies an autonomous/semi-autonomous **testing agent's**
mandate for **Sutra Press**, the manuscript conversion engine specified in
`agent.md`. It is deliberately a **separate document from a separate
mandate**: the build agent's job is to make the pipeline work; this agent's
job is to try to break it, and to refuse to call anything "done" until it
survives the cases below.

**Hard rule:** this document does not re-derive architecture. Every test
case here traces back to a specific section of `agent.md` — the content
inventory (§5.1), the IR schema (§5.3), the pipeline steps (§6), the
column-layout logic (§4), or the Failure Philosophy (§7). If `agent.md`
changes, this document needs a corresponding pass; they are kept in sync
deliberately, the same way Sutra Press itself keeps JATS and LaTeX in sync
from one IR (§3.1) — one source of test intent, many expressions of it
(unit, integration, golden-file, schema-conformance).

**Test agent's prime directive**, mirroring `agent.md` §7 (Failure
Philosophy): a test suite that passes by *avoiding* hard cases is worse
than no test suite. Every category in `agent.md` §5.1 must have at least
one corresponding test case here, even if that test case's expected
result is "this is correctly flagged as Tier 3 / needs-manual-prep" rather
than "this converts perfectly." **Coverage of the inventory, not just
coverage of the happy path, is the definition of done for this document.**

---

## 1. Test Levels

| Level | Scope | Tooling |
|---|---|---|
| **Unit** | Individual IR node generation (one paragraph, one citation, one equation) in isolation | `pytest`, no external processes |
| **Component/Integration** | One full pipeline stage (DOCX→AST, AST→IR, IR→JATS, IR→LaTeX, LaTeX→PDF) | `pytest` + real Pandoc/Tectonic subprocess calls |
| **Golden-file (end-to-end)** | Full manuscript in → JATS + LaTeX + PDF out, diffed against known-good expected output | `pytest` + fixture corpus (§3) |
| **Schema conformance** | Every JATS output, in every test above, validated against the official schema | `lxml.etree.XMLSchema`, blocking in CI |
| **Property-based / fuzz** | Randomized or boundary-pushing inputs (malformed DOCX, pathological nesting, huge documents) | `hypothesis` where applicable, manual corpus otherwise |
| **Idempotency / regression** | Same input run twice → byte-identical output; previously-fixed bugs stay fixed | `pytest`, diffing against a locked baseline |

A test case in §4 below may apply at multiple levels — e.g. "merged-cell
table" gets a unit test (IR table node → correct JATS `colspan`/`rowspan`
attributes) **and** a golden-file test (a real DOCX with such a table,
full pipeline, real PDF inspected for correct rendering).

---

## 2. Test Environment & Fixtures

- **Fixture corpus location**: `tests/fixtures/manuscripts/` — one
  subdirectory per test case ID (§4), each containing:
  - `input.docx` (or `input.tex` for LaTeX-input cases)
  - `expected.xml` (hand-verified or sourced from a real published
    open-access article's JATS — see note below)
  - `expected-triage.md` (expected triage report verdict, §6.2)
  - `notes.md` (why this fixture exists, what it's protecting against)
- **Sourcing real-world fixtures**: where possible, pull JATS XML samples
  from genuinely open-access journals (PMC, DOAJ-indexed journals publish
  their JATS publicly) to use as **schema-conformance reference shapes**
  — i.e. confirm Sutra Press's *generated* JATS has the same structural
  shape/conformance level as JATS that real publishers consider
  acceptable. Do not copy substantial article text/content into the test
  corpus verbatim; construct synthetic manuscript text for actual `input.docx`
  fixtures (this also avoids copyright/licensing complications in the test
  repo) and only use real external samples for *structural pattern*
  reference, not literal copied content.
- **DOCX fixture construction**: build fixtures programmatically
  (`python-docx`) where possible so the *exact* structural choice being
  tested (e.g. "Heading 2 style vs. manually bolded text") is explicit and
  reproducible, rather than hand-crafted in Word and therefore opaque to
  future maintainers.
- **PDF inspection**: golden-file PDF tests check page count, text
  extractability (via `pdfplumber` or similar), and — for layout-sensitive
  cases (§4 column tests) — that known content appears in the expected
  column position. Pixel-perfect visual diffing is a stretch goal, not a
  Phase 1 requirement (LaTeX's box model makes this fragile across TeX
  engine versions); structural/textual assertions are the Phase 1 bar.

---

## 3. Fixture Corpus — Minimum Required Manuscripts

Before individual test cases (§4), the corpus needs whole representative
manuscripts, not just isolated snippets, because some defects only appear
at document scale (style drift across 20 pages, footnote numbering
collisions, etc.):

| Fixture ID | Description |
|---|---|
| `corpus-01-clean-stem` | A "best case" STEM article: proper Word heading styles throughout, numbered citations, simple tables, raster figures, OMML equations. Should pass triage clean and convert with zero warnings. This is the baseline regression sentinel — if this ever stops converting cleanly, something upstream broke. |
| `corpus-02-clean-humanities` | A "best case" humanities article: author-date citations, footnote-style citations (not numbered), block quotes, fewer figures/tables, longer prose sections. |
| `corpus-03-messy-realistic` | A manuscript with realistic author mistakes: manually-bolded fake headings mixed with real heading styles, inconsistent citation formatting, one embedded equation-as-image, a tracked-changes remnant. Should trigger triage warnings, not a hard failure, and should convert what it safely can while flagging the rest. |
| `corpus-04-two-column-target` | Same content as `corpus-01`, used specifically to test `--layout=double` template generation (agent.md §4) including at least one wide table requiring `span_hint: page`. |
| `corpus-05-maximal` | A kitchen-sink manuscript deliberately constructed to exercise every Tier 1 + Tier 2 item in agent.md §5.1 at least once. Large and slow; not run on every commit, but run nightly/pre-release. |
| `corpus-06-pathological` | Deliberately adversarial: empty document, a document that's just a title and nothing else, a 200-page document, a document with 500 references, deeply nested lists (5+ levels), a table with 50 columns. For robustness/performance testing, not correctness testing. |

---

## 4. Test Case Inventory

This is organized to mirror `agent.md` §5.1's category structure exactly
(A through H), so coverage can be checked category-by-category against
that document. Each test case has:

- **ID** — `TC-<category>-<number>`
- **Input** — what's being fed in
- **Expected** — what must come out (or what must be flagged, per §7's
  rule that flagged-and-honest beats silently-wrong)
- **Level** — which test level(s) from §1 this belongs to
- **Traces to** — the agent.md section this test protects

### 4.A Front matter / metadata

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-A-01 | Title with inline italics (species name) | JATS `<article-title>` preserves `<italic>` inline; LaTeX title preserves `\textit{}` | Unit | §5.1.A |
| TC-A-02 | Title with subscript/superscript (chemical formula, e.g. "CO₂") | Both outputs preserve `<sub>`/`<sup>` correctly, not flattened to plain text | Unit | §5.1.A |
| TC-A-03 | 5 authors, 3 unique affiliations, non-1:1 author↔affiliation mapping | JATS `<contrib-group>` + `<aff>` linking via `rid`/`id` attributes correctly reconstructs which author belongs to which affiliation(s), including authors with 2 affiliations | Integration | §5.1.A, §5.3 IR `affiliation_refs[]` |
| TC-A-04 | One corresponding author marked with `*` or similar convention in source | JATS `corresp="yes"` attribute set correctly on exactly one `<contrib>`; email captured | Integration | §5.1.A |
| TC-A-05 | Author with ORCID iD present in source | JATS `<contrib-id contrib-id-type="orcid">` populated | Unit | §5.1.A |
| TC-A-06 | Author with ORCID **absent** | Field omitted cleanly (not emitted as empty/null tag); no triage warning (ORCID is optional) | Unit | §5.1.A |
| TC-A-07 | Two authors marked "equal contribution" | JATS equal-contribution convention applied (e.g. shared footnote symbol or `equal-contrib` attribute per JATS version in use); IR `equal_contribution_group` correctly groups them | Integration | §5.3 IR |
| TC-A-08 | Structured abstract (Background/Methods/Results/Conclusion headers) | Structure preserved as labeled sub-sections in JATS `<abstract>`, not flattened into one paragraph | Integration | §5.1.A |
| TC-A-09 | Plain (unstructured) abstract | Single `<p>` inside `<abstract>`; no spurious structure invented | Integration | §5.1.A |
| TC-A-10 | Graphical abstract image present | `image_ref` correctly populated in IR; included in JATS as appropriate floating-material element | Integration | §5.1.A |
| TC-A-11 | Keywords list (5 keywords, semicolon-separated in source) | Correctly split into individual `<kwd>` elements, not left as one comma-blob string | Unit | §5.1.A |
| TC-A-12 | Funding statement: "This work was supported by NSF Grant No. 12345" | Funder name and award ID correctly extracted into separate structured fields, not left as one string | Unit | §5.1.A — flagged as common failure point in prior art (agent.md §2) |
| TC-A-13 | Multiple funding sources in one statement | All sources extracted as separate `<funding-source>` entries, not merged/dropped | Unit | §5.1.A |
| TC-A-14 | Conflict of interest statement present | Captured verbatim in correct JATS element (`<fn fn-type="conflict">` or `<custom-meta>` depending on JATS profile chosen) | Unit | §5.1.A |
| TC-A-15 | No conflict of interest statement in source | Field omitted, **triage warning emitted** (many journals require this — absence should be flagged for editor attention, not silently passed) | Unit | §7 Failure Philosophy |
| TC-A-16 | Ethics/IRB approval statement | Captured correctly; presence/absence both produce defined, traceable behavior | Unit | §5.1.A |
| TC-A-17 | Data availability statement | Captured correctly | Unit | §5.1.A |
| TC-A-18 | Acknowledgments section | Captured, kept distinct from author contributions and funding (a common point of conflation) | Unit | §5.1.A |
| TC-A-19 | Article type explicitly stated vs. inferred from structure (e.g. has "Case Report" heading but no explicit type field) | Engine does not guess silently; if type can't be determined, defaults to `research-article` **and flags it in the triage report** for editor confirmation | Unit | §7 Failure Philosophy |
| TC-A-20 | CRediT author contribution roles present (e.g. "Conceptualization: J. Smith; Writing: A. Lee") | Parsed into `author_contributions[]` with correct `author_ref` + `credit_roles[]` mapping per author, using the standard CRediT taxonomy term set | Integration | §5.3 IR |
| TC-A-21 | Subject classification codes present (e.g. PACS, MSC, JEL) | Captured with correct `scheme` + `code` fields, not conflated with keywords | Unit | §5.1.A |
| TC-A-22 | License statement (e.g. CC-BY 4.0) with URL | Both `type` and `url` populated in JATS `<permissions><license>` | Unit | §5.1.A |
| TC-A-23 | Missing license statement entirely | Triage flags as **needs-manual-prep** — this blocks valid publication metadata, should not pass silently | Unit | §7 Failure Philosophy |

### 4.B Body text structures

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-B-01 | 3-level nested headings using real Word "Heading 1/2/3" styles | JATS nested `<sec>` hierarchy matches exactly; LaTeX `\section`/`\subsection`/`\subsubsection` matches | Integration | §5.1.B, §6 step 2 triage |
| TC-B-02 | Fake heading: manually bolded + 16pt text, not a real Word heading style | **Triage flags this explicitly** as unreliable-to-convert (per agent.md §6 step 2's named example); does not silently convert to a real `<sec><title>` as if it were a genuine heading | Integration | §6 step 2, §7 |
| TC-B-03 | Mixed: some headings use real styles, some are fake bold text, in the same document | Triage produces a **per-instance** flag (which headings are trustworthy, which aren't), not a single document-wide pass/fail verdict | Integration | §7 — traceability requirement |
| TC-B-04 | Paragraph with bold, italic, underline, strikethrough all present in one run sequence | All four marks preserved independently and correctly nested/ordered in both JATS and LaTeX output | Unit | §5.1.B |
| TC-B-05 | Superscript/subscript outside of math context (e.g. footnote markers, ordinal "1st") | Preserved correctly, not confused with footnote reference markers (which have separate semantics) | Unit | §5.1.B |
| TC-B-06 | Hyperlink to external URL | JATS `<ext-link>` with correct `xlink:href`; LaTeX `\href{}{}` (via `hyperref`) | Unit | §5.1.B |
| TC-B-07 | Cross-reference to a figure ("see Figure 3") | Resolves to correct `xref` target pointing at the actual figure's ID, and **remains correct** if figures get renumbered during conversion (i.e. resolved by stable ID, not by literal text matching "Figure 3") | Integration | §5.3 IR `xref(target_id)` |
| TC-B-08 | Cross-reference to a section, equation, table, footnote (one test each) | Same correctness requirement as TC-B-07 for each target type | Integration | §5.3 IR |
| TC-B-09 | Block quotation | Rendered as JATS `<disp-quote>`; LaTeX `quote`/`quotation` environment | Unit | §5.1.B |
| TC-B-10 | Ordered list, single level, standard numbering | JATS `<list list-type="order">`; LaTeX `enumerate` | Unit | §5.1.B |
| TC-B-11 | Ordered list, nested 3 levels, mixed numbering schemes (1, 2, 3 → a, b, c → i, ii, iii) | Nesting and numbering-scheme changes preserved correctly at each level | Integration | §5.1.B |
| TC-B-12 | Unordered (bulleted) list, nested 2 levels | Correct nesting in both outputs | Unit | §5.1.B |
| TC-B-13 | Definition list (term/definition pairs) | JATS `<def-list>`; correctly distinguished from a regular two-column table | Unit | §5.1.B |
| TC-B-14 | Footnote (page-bottom note) referenced from body text | Correct `<fn>` + `<xref ref-type="fn">` pairing; LaTeX `\footnote{}` | Unit | §5.1.B |
| TC-B-15 | Endnote (distinct from footnote) | Correctly placed in back matter, **not conflated with footnotes or with reference-list footnote-style citations (see TC-F-07)** | Unit | §5.1.B — explicit non-conflation requirement |
| TC-B-16 | Sidebar / boxed text | JATS `<boxed-text>`; flagged for span_hint consideration if wide | Integration | §5.1.B, §4 |
| TC-B-17 | Epigraph (quote before a chapter/section, no citation marker reference) | Distinguished from a regular block quote (different semantic role); captured without forcing a fake citation link | Unit | §5.1.B |
| TC-B-18 | Inline non-Latin characters / diacritics (e.g. "café," "naïve," Greek letter "λ" used inline outside math) | Unicode preserved exactly through every pipeline stage — this is an explicit idempotency/encoding regression test, run as part of CI on every build, not just feature-gated | Unit + Regression | §5.1.B |
| TC-B-19 | Inline RTL text fragment (e.g. a quoted Arabic phrase inside an English-language paragraph) | **Known hard case** per agent.md §5.1.B — triage must flag it explicitly; the test's "pass" condition is correct flagging, not correct typesetting, unless/until RTL support is formally promoted out of Tier 3 | Integration | §5.1.B, §5.2 Tier 3 |
| TC-B-20 | Document with unresolved Word tracked changes (insertions/deletions still marked, not accepted/rejected) | Per agent.md §6 step 2 triage: this should be flagged at the **needs-manual-prep** level, and the engine should not silently accept or silently reject changes on the editor's behalf | Integration | §5.1.B, §6 step 2 |
| TC-B-21 | Document with Word reviewing comments attached to text | Comments are stripped from body content (never merged into running text) and **surfaced separately** in the triage report, not silently discarded with no trace | Integration | §7 — never silently drop content |
| TC-B-22 | Empty paragraph / multiple consecutive blank lines in source | Collapsed sensibly (not converted into spurious empty `<p>` elements that fail JATS schema expectations around empty content) | Unit | §6 step 7 schema validation |

### 4.C Figures and images

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-C-01 | Single raster image (PNG) with caption | Correct `<graphic>` + `<caption>` pairing; image copied to assets folder with stable, collision-free filename | Integration | §5.1.C, §6 step 10 |
| TC-C-02 | Raster image (JPEG), (TIFF) — one test each | Both formats handled identically to PNG case; TIFF specifically checked since it's less universally browser/PDF-friendly and may need format normalization for LaTeX inclusion | Integration | §5.1.C |
| TC-C-03 | Vector image (embedded EPS or PDF figure) | Preserved as vector through to final PDF (not rasterized, which would degrade quality) — this is checked by inspecting the compiled PDF's content stream, not just by checking the intermediate file format | Integration | §5.1.C — explicit "should be preserved as vector" requirement |
| TC-C-04 | Vector image (SVG) | SVG converted appropriately for LaTeX inclusion (e.g. via a vector-safe conversion path), not silently rasterized | Integration | §5.1.C |
| TC-C-05 | Multi-panel figure (1A, 1B, 1C as sub-images of one figure) | Represented as one figure node with `panels[]`, not as three independent figures with accidentally-sequential numbering | Integration | §5.3 IR `panels[]` |
| TC-C-06 | Figure caption containing inline citation (e.g. "Reproduced from [12]") | Citation inside caption resolves correctly to the reference list, same as a body citation would | Integration | §5.1.C, §5.1.F |
| TC-C-07 | Image with author-supplied alt text | Alt text captured exactly | Unit | §5.1.C, §5.3 non-negotiable requirement |
| TC-C-08 | Image with **no** author-supplied alt text | Per agent.md §5.3's non-negotiable requirement: field defaults to empty string, **never omitted from JATS output**, and a triage warning is emitted | Unit | §5.3 — explicit non-negotiable requirement, must not regress |
| TC-C-09 | Figure requiring landscape orientation (very wide image) | `orientation: landscape` correctly set; LaTeX rotates the float appropriately for both single- and two-column templates | Integration | §5.1.C, §4 |
| TC-C-10 | Supplementary image referenced but explicitly marked "not for inline printing" | Represented as a metadata link, not embedded as an inline figure | Integration | §5.1.C |
| TC-C-11 | Two images in source with identical filenames (e.g. both named "image1.png" from different Word figure exports) | Asset extraction produces collision-free output filenames (e.g. content-hash or sequence-based renaming); **this is a real, common failure mode in naive DOCX image extraction** — must be explicitly tested, not assumed away | Integration | §6 step 10 packaging |
| TC-C-12 | Figure wide enough to plausibly need column-span (per agent.md §4.2's "more than ~5-6 columns... or an image above a width heuristic") | `span_hint` heuristic correctly triggers; triage report surfaces the suggestion for editor review rather than deciding unilaterally and silently | Integration | §4.2 action item |

### 4.D Tables

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-D-01 | Simple uniform table (3 cols × 5 rows, one header row) | Correct JATS `<table>` with `<thead>`/`<tbody>`; LaTeX `tabular` | Unit | §5.1.D |
| TC-D-02 | Table with one merged cell (colspan=2) | JATS `colspan` attribute correct; LaTeX `\multicolumn` correct | Integration | §5.1.D |
| TC-D-03 | Table with one merged cell (rowspan=2) | JATS `rowspan` attribute correct; LaTeX handles via `\multirow` (flagged dependency — confirm template includes the package) | Integration | §5.1.D |
| TC-D-04 | Table with both row- and column-spanning merged cells in combination | Both attributes coexist correctly on the same cell; this is the case prior art (agent.md §2's docxConverter README) flags as commonly broken — explicit regression test | Integration | §2 prior art lesson |
| TC-D-05 | Table with a multi-row header (2 header rows) | Both header rows correctly placed in `<thead>`, not the first one only | Integration | §5.1.D |
| TC-D-06 | Table with table-specific footnotes using symbol markers (*, †, ‡) rather than numbers | Correctly distinguished from body footnotes (TC-B-14) — different numbering/symbol convention preserved, not renumbered into the body footnote sequence | Integration | §5.1.D — explicit "distinct from body footnotes" note |
| TC-D-07 | Table with bold header row + shaded alternating rows (formatting-only, not structural) | Visual formatting preserved in LaTeX rendering; **not** misinterpreted as structurally meaningful (e.g. shading does not trigger spurious header detection) | Integration | §5.1.D |
| TC-D-08 | Table requiring landscape/page-rotation due to width | Correctly rendered rotated in PDF; JATS captures `orientation` as metadata even though JATS itself has no visual rotation concept | Integration | §5.1.D, §4 |
| TC-D-09 | Table spanning more than one page in the original document ("Table 2 continued") | Correctly represented via `continuation_of` IR field linking the two parts as one logical table, not as two separate tables with duplicate numbering | Integration | §5.3 IR `continuation_of` |
| TC-D-10 | Table cell containing inline math/special notation | Math inside table cells round-trips correctly (this is a known weak point in many naive converters — explicit test) | Integration | §5.1.D, §5.1.E |
| TC-D-11 | Table requiring column-span in two-column layout (`span_hint: page`) | Correctly renders as `table*` (or template-equivalent starred environment) only in the two-column template variant; renders as a normal `table` in the single-column variant from the **same IR**, proving the layout-independence claim in §4 | Golden-file | §4 — core claim under test |
| TC-D-12 | Deeply malformed/nested table (table inside a table cell) | Per agent.md §2's lesson (docxConverter explicitly lists nested tables as unsupported): triage **flags this as needs-manual-prep** with a clear, traceable message — this is the literal example used in agent.md §7's failure-message illustration ("Table 3... nested table not supported") and must produce exactly that class of message, not a crash or silent mangling | Integration | §7 — direct traceability to the spec's own example |

### 4.E Mathematical content

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-E-01 | Inline equation authored as native OOXML math (OMML), e.g. "where $x > 0$" | Correctly converted to both LaTeX math mode and MathML/JATS `<inline-formula>` | Integration | §5.1.E |
| TC-E-02 | Display (standalone, numbered) equation, OMML | Correct `<disp-formula>` with equation numbering; LaTeX `equation` environment with matching number | Integration | §5.1.E |
| TC-E-03 | Equation cross-referenced from body text ("as in Eq. 4") | Resolves via stable ID (same pattern as TC-B-07/08), survives renumbering | Integration | §5.1.E, §5.1.B |
| TC-E-04 | Multi-line aligned equation system (e.g. a derivation across 3 lines) | LaTeX `align` environment used correctly; JATS captures as a single `<disp-formula>` with the full LaTeX/MathML source preserved (JATS doesn't have a native multi-line concept, so the *source* must be preserved faithfully even if visual JATS rendering is basic) | Integration | §5.1.E |
| TC-E-05 | Equation authored as an **embedded image** (no OMML/semantic source) | **Known hard case** — per agent.md §5.1.E this must be flagged at triage (§6 step 2) as not convertible to real LaTeX math/MathML; expected output is an embedded image fallback with a clear triage warning, not a fabricated/guessed LaTeX transcription | Integration | §5.1.E, §6 step 2, §5.2 Tier 3 |
| TC-E-06 | Equation wide enough to need linebreaking/spanning in two-column layout | Triage or generation flags the width issue per agent.md §4.2 ("don't silently truncate") rather than allowing LaTeX to silently overflow the column in the compiled PDF | Integration | §4.2 |
| TC-E-07 | Chemical formula/structure requiring special notation (e.g. via mhchem) | Either correctly converted using chemistry-specific LaTeX notation, or explicitly flagged as Tier 3 if sourced from chemistry-drawing-software images — **must not be silently treated as plain text or plain math** | Integration | §5.1.E, §5.2 Tier 3 |
| TC-E-08 | Special Unicode math symbols typed inline via Word's symbol insertion (∑, ∞, ±) outside any equation object | Correctly mapped to LaTeX math-mode equivalents (`\sum`, `\infty`, `\pm`) rather than passed through as raw Unicode that may not render in all LaTeX engines | Unit | §5.1.E |

### 4.F Citations and references

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-F-01 | Numbered citation style, single reference (`[1]`) | Correctly linked to reference-list entry 1 via stable ID | Unit | §5.1.F |
| TC-F-02 | Numbered citation, grouped (`[1,3,5]`) | All three resolve to correct distinct entries, not merged into one or mis-split | Unit | §5.1.F |
| TC-F-03 | Numbered citation, range (`[1-5]`) | Correctly expands to all 5 individual references, not literally treated as a 2-element list | Unit | §5.1.F |
| TC-F-04 | Author-date citation style (`(Smith, 2020)`) | Correctly resolves to the matching reference-list entry by author+year matching | Integration | §5.1.F |
| TC-F-05 | Named in-text citation (`Smith (2020) showed...`) | Same resolution requirement as TC-F-04, different surface syntax | Integration | §5.1.F |
| TC-F-06 | Same source cited 3 separate times in the body | All 3 in-text markers resolve to the **same single** reference-list entry — explicit duplicate-prevention test, since naive parsing can create 3 separate entries | Integration | §5.1.F — explicit "must resolve to one entry" requirement |
| TC-F-07 | Footnote-style citations (humanities convention — citation appears as a footnote, not in a separate numbered list) | Correctly distinguished from both body footnotes (TC-B-14) and from numbered in-text citations — this is explicitly called out in agent.md §5.1.F as "must not be conflated" | Integration | §5.1.F — explicit non-conflation requirement |
| TC-F-08 | Reference list entry: journal article (full fields: authors, year, title, journal, volume, issue, pages, DOI) | All fields land in correct structured `<element-citation publication-type="journal">` children — **not** stored as one opaque string (per agent.md §5.3's non-negotiable requirement) | Unit | §5.3 — non-negotiable requirement, highest-priority test in this section |
| TC-F-09 | Reference list entry: book | `publication-type="book"`, correct field set (no "issue"/"volume" forced into a journal-shaped template) | Unit | §5.1.F |
| TC-F-10 | Reference list entry: book chapter | `publication-type="chapter"`, captures both chapter title and containing book title as distinct fields | Unit | §5.1.F |
| TC-F-11 | Reference list entry: conference paper | `publication-type="confproc"`, captures conference name distinct from publisher | Unit | §5.1.F |
| TC-F-12 | Reference list entry: thesis | `publication-type="thesis"` | Unit | §5.1.F |
| TC-F-13 | Reference list entry: dataset | `publication-type="data"`, correctly captures a DOI as the primary identifier where present | Unit | §5.1.F |
| TC-F-14 | Reference list entry: software | `publication-type="software"` (or closest JATS-supported equivalent) | Unit | §5.1.F |
| TC-F-15 | Reference list entry: preprint | Correctly distinguished from a published journal article (different `publication-type`, often a different identifier scheme) | Unit | §5.1.F |
| TC-F-16 | Reference list entry: website, with access date | `publication-type="website"` with `date-in-citation`/access-date field populated — commonly dropped by naive converters | Unit | §5.1.F |
| TC-F-17 | Reference with 3+ authors and "et al." convention in source | All actual authors captured in structured form in the reference list (full author list belongs in the back-matter reference, even if body text or display abbreviates to "et al.") | Unit | §5.1.F |
| TC-F-18 | Mixed reference list (5 entries, each a different type from TC-F-08 through TC-F-16) | All 5 correctly typed and field-mapped in a single document — integration-level test that type-detection doesn't default everything to "journal-article" | Integration | §5.1.F |
| TC-F-19 | Malformed/incomplete reference entry (missing year, e.g.) | Missing field omitted cleanly from JATS (not fabricated), **with a triage/validation warning** naming the specific incomplete entry | Integration | §7 Failure Philosophy |
| TC-F-20 | Reference list entry where the citation-parsing library's confidence is low (ambiguous formatting) | Per the spirit of agent.md §6 step 5: falls back to flagging for manual review rather than guessing wrong with false confidence | Integration | §6 step 5 |

### 4.G Supplementary / appendix material

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-G-01 | Appendix with its own heading and body content | Captured in `appendices[]`, not merged into the main `body.sections[]` | Integration | §5.1.G, §5.3 IR |
| TC-G-02 | Appendix with its own figure numbering sequence ("Figure A1," restarting from the main sequence) | `own_numbering_scope: true` correctly applied; appendix figure IDs don't collide with or continue the main body's figure numbering | Integration | §5.1.G, §5.3 IR `own_numbering_scope` |
| TC-G-03 | Supplementary file referenced in text but not embedded (e.g. "see Supplementary Video 1") | Represented as a metadata link only, with no attempt to embed non-existent inline content | Unit | §5.1.G |
| TC-G-04 | Author biography block (photo + short bio per author, IEEE-style, at document end) | Captured in `author_bios[]`, correctly linked to the matching author via `author_ref` | Integration | §5.1.G, §5.3 IR |
| TC-G-05 | Two appendices, each with their own sub-numbering ("A1, A2..." and "B1, B2...") | Both scopes kept independent; no cross-contamination of numbering between Appendix A and Appendix B | Integration | §5.1.G |

### 4.H Document-level / structural

| ID | Input | Expected | Level | Traces to |
|---|---|---|---|---|
| TC-H-01 | Source DOCX contains a two-column section break partway through (presentation artifact, not real structure) | Discarded as noise per agent.md §4.1 — does not leak into the IR or cause spurious section splits | Integration | §4.1 — explicit discard rule |
| TC-H-02 | Source DOCX contains an explicit page break mid-paragraph | Discarded/normalized; does not fragment a single logical paragraph into two IR paragraph nodes | Integration | §5.1.H |
| TC-H-03 | Source DOCX has a distinct title-page (separate from where body text starts) | Title-page fields correctly extracted into `metadata`, not left as orphaned body paragraphs at the top of `sections[]` | Integration | §6 step 4 |
| TC-H-04 | Headers/footers present in source DOCX (running head, page numbers) | Discarded from content extraction (these are source-document presentation artifacts); confirmed that LaTeX template generates its **own** headers/footers per house style rather than inheriting the author's | Integration | §5.1.H — explicit "generated, not extracted" note |
| TC-H-05 | Output PDF in single-column mode | Has correctly generated running heads/footers/page numbers per the template, independent of whatever the source document had | Golden-file | §5.1.H |
| TC-H-06 | Output PDF in two-column mode (same source as TC-H-05) | Same header/footer correctness requirement, different column template — proving template-level header generation is layout-independent in the same way content is | Golden-file | §4, §5.1.H |

---

## 5. Cross-Cutting Test Suites

These don't map to one §5.1 category — they test properties that cut
across the whole pipeline.

### 5.1 Column-layout equivalence suite (traces to agent.md §4)

The core claim under test: **the same IR produces correct single-column
and two-column output**, proving column choice is genuinely a render-time
template parameter and not something that leaked into content logic.

| ID | Test |
|---|---|
| TC-X-01 | Run `corpus-01-clean-stem` through `--layout=single` and `--layout=double`. Assert: identical JATS XML byte-for-byte (column choice must have **zero** effect on JATS, since JATS has no column concept — per §4 intro). |
| TC-X-02 | Same run. Assert: both LaTeX outputs derive from the same IR snapshot (verified by comparing a hash of the pre-render IR object in both runs, not just eyeballing output). |
| TC-X-03 | `corpus-04-two-column-target`'s wide table (`span_hint: page`) renders as `table*` only in the two-column build; renders as a normal `table` (no spanning needed) in the single-column build of the same source. (This is TC-D-11, listed again here as it's the canonical proof-point for this whole suite.) |
| TC-X-04 | Footnote numbering is identical and correctly sequential in both layout variants (column balancing must not perturb footnote order). |
| TC-X-05 | Two-column PDF compiles cleanly with no LaTeX overfull/underfull `\hbox` warnings above a defined severity threshold for the `corpus-01` fixture — a basic typographic-quality gate, not just "did it compile." |

### 5.2 Single-source synchronization suite (traces to agent.md §3.1)

| ID | Test |
|---|---|
| TC-X-06 | Take any Tier 1 fixture. Generate JATS and LaTeX. Independently extract the title, author list, and abstract text from **both** outputs (via XML parsing and via a LaTeX-aware text extractor respectively). Assert they match exactly. This is the direct, automatable test of the "single-source sync" promise — not just an architectural intention, but a checked invariant. |
| TC-X-07 | Same as TC-X-06 but for the full reference list (all structured fields, not just titles) — references are the highest-risk drift point per agent.md §2's prior-art lessons. |
| TC-X-08 | Modify one paragraph in `input.docx`, re-run the full pipeline, and assert that **both** JATS and LaTeX outputs reflect the change identically (no stale-cache or partial-regeneration bugs). |

### 5.3 Idempotency suite (traces to agent.md §7)

| ID | Test |
|---|---|
| TC-X-09 | Run the same `input.docx` through the full pipeline twice in separate process invocations. Assert byte-identical JATS XML output. |
| TC-X-10 | Same, for generated `.tex` source (not the compiled PDF, which may have legitimate non-determinism in embedded timestamps/metadata — see TC-X-11). |
| TC-X-11 | Compiled PDF: assert identical extracted text content and page count across two runs, even if binary PDF bytes differ due to embedded compilation timestamps (Tectonic should be checked for a reproducible/deterministic mode per agent.md §3.2; if such a mode exists, prefer the stronger byte-identical assertion instead). |

### 5.4 Schema conformance suite (traces to agent.md §6 step 7)

| ID | Test |
|---|---|
| TC-X-12 | Every fixture's generated JATS XML validates against the official JATS 1.3 XSD with zero errors, as a blocking CI gate — no fixture is allowed to merge with a "mostly valid" JATS output. |
| TC-X-13 | Deliberately corrupt a known-good JATS file (remove a required element) and assert the validation step correctly **fails** and produces a line-numbered, human-readable error (not a raw parser stack trace) — a negative test proving the validator itself is wired correctly, not just rubber-stamping. |
| TC-X-14 | Assert validation failures block the pipeline from declaring success — i.e. a deliberately-broken IR-to-JATS code path (test-only fault injection) must cause the CLI to exit non-zero and produce `validation-report.md` flagged as failed, never exit 0 with a silently-invalid file. |

### 5.5 Traceability suite (traces to agent.md §7)

| ID | Test |
|---|---|
| TC-X-15 | Feed the nested-table fixture (TC-D-12). Assert the resulting triage/error message names the specific table, its approximate source location (page/paragraph index), and the specific style name involved — matching the granularity of agent.md §7's own worked example, not a generic "conversion failed" message. |
| TC-X-16 | Feed a fixture with a LaTeX compile error deliberately introduced (e.g. an unescaped special character that survives IR generation due to a test-only fault injection). Assert the error report cites both the generated `.tex` line **and** the originating IR/source location, per agent.md §6 step 9's explicit requirement. |

### 5.6 Triage-report correctness suite (traces to agent.md §6 step 2)

| ID | Test |
|---|---|
| TC-X-17 | `corpus-01-clean-stem` → triage verdict must be `pass` with zero warnings. |
| TC-X-18 | `corpus-03-messy-realistic` → triage verdict must be `pass-with-warnings`, and the specific warnings must include (at minimum) the fake-heading issue and the equation-as-image issue baked into that fixture. |
| TC-X-19 | A fixture consisting only of unresolved tracked changes and nothing else convertible → triage verdict must be `needs-manual-prep`, and the pipeline should **not** proceed to full conversion without an explicit override flag (define this override flag in the CLI if not already specified in agent.md, and add it there if missing — flag as a documentation gap if discovered during test-writing). |

### 5.7 Performance / robustness suite (traces to `corpus-06-pathological`)

| ID | Test |
|---|---|
| TC-X-20 | Empty `.docx` (zero body content, valid file) → engine fails gracefully with a clear "no content found" message, does not crash with an unhandled exception. |
| TC-X-21 | 200-page manuscript → completes within a defined time budget (set a concrete number once real performance is measured; flag as TBD if not yet benchmarked, do not leave silently unspecified). |
| TC-X-22 | 500-entry reference list → all 500 correctly parsed and structured; specifically check for any O(n²) blowup in the citation-resolution step. |
| TC-X-23 | List nested 5+ levels deep → either correctly rendered or cleanly flagged as exceeding supported nesting depth — must not silently truncate or crash. |
| TC-X-24 | Table with 50 columns → either correctly handled (likely requiring `landscape` + small font template fallback) or cleanly flagged, never silently overflowing the page with no warning. |

---

## 6. Definition of Done for This Test Suite

1. Every row in §4 (A through H) has at least one implemented, passing (or
   correctly-failing-as-expected, for Tier 3 cases) automated test.
2. Every category in agent.md §5.1 has nonzero test coverage — run a
   coverage-mapping check (this can be a simple script cross-referencing
   §5.1's bullet list against this document's "Traces to" column) before
   declaring this suite complete, not just before declaring agent.md's
   build complete.
3. All of §5 (cross-cutting suites) pass, with §5.4 (schema conformance)
   and §5.2 (single-source sync) as the two **non-negotiable, always-
   blocking** suites — these are the tests that protect the project's two
   core promises (valid JATS, genuine single-source sync) and must never
   be skipped, marked `xfail`, or weakened to make a release deadline.
4. CI runs the Tier 1 fixture suite (§3, `corpus-01`/`02`/`03`/`04`) on
   every commit; `corpus-05-maximal` and `corpus-06-pathological` run
   nightly or pre-release given their size/cost.
5. A coverage gap report is maintained and reviewed alongside agent.md's
   own §5.2 priority tiers — if a Tier 1 item from agent.md §5.1 lacks a
   passing test here, that is treated as a release blocker, equivalent in
   severity to a failing test.

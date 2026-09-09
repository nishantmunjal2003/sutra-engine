# RESUME-CONTEXT.md — Sutra Press Project Handoff

**Purpose of this file**: this conversation is being deleted. This document
is the complete handoff so that pasting/uploading it into a **new**
conversation with Claude lets work resume exactly where it left off — same
decisions, same reasoning, same open threads — without re-deriving anything
or contradicting a choice that was already made deliberately.

**How to use this file in a new conversation**: paste or upload this file
first, then say something like *"This is the handoff doc for Sutra Press —
read it and continue from here."* Claude should treat every decision below
as already final and settled, not open for casual re-litigation — if a new
conversation seems to be drifting toward redoing something covered here,
that's a signal to re-read this file, not to start fresh.

---

## 1. What This Project Is

**Sutra Press** — an original, open-standards-based manuscript conversion
engine for academic journal publishing. It takes an author's raw manuscript
(DOCX, secondarily LaTeX) and produces, from one shared internal source:

1. Validated **JATS XML** (the format OJS, PubMed Central, DOAJ, Crossref
   expect)
2. A compiled **LaTeX → PDF** typeset version

Both outputs stay in sync because they're generated as **parallel siblings
from one internal representation (IR)** — never one derived from the other.
That single-source-sync property is the core architectural promise of the
whole system.

### 1.1 Origin story (why this exists)

The user was investigating `sutrivia.com` (a publishing-tech vendor) and its
"Manuscript Essential" product, then looked at Scholastica's typesetting
service (`scholasticahq.com/typesetting`) as a second reference point. From
there, the user asked Claude to help **build an original system inspired by
that category of tool** — explicitly NOT a clone of either vendor's product,
UI, or branding. This is stated clearly in `agent.md` §0 and §11
(Non-Goals): it's an implementation of a well-documented industry pattern
(manuscript → XML → PDF, "single-source publishing") using open standards
(JATS) and open-source tooling, built from first principles.

### 1.2 Why it's named "Sutra Press"

*Sūtra* (सूत्र) = Sanskrit for "thread," and also the name for a tightly
rule-bound, compressed text genre. Both meanings map directly onto what the
engine does: one IR threads through to both outputs (literal mechanism), and
the whole job is threading loose author prose into rigorous, schema-
validated structure. There's also a deliberate, disclosed echo of
"Sutrivia" (the origin-story vendor) — acknowledged explicitly in the spec
as inspiration, not imitation. Full reasoning, plus a note that this is
strong material for front-page/landing copy (a thread running through a
tangled manuscript, emerging organized), lives in `agent.md` §0.1.

### 1.3 Scope decision (Phase 1 vs. later)

**Phase 1 (the only thing actually being built right now)**: the conversion
engine only. CLI-driven (`sutra convert <input.docx> --out <dir>`). No
accounts, no peer review, no hosting, no payments, no web UI yet.

**Phase 2+ (deliberately deferred, sketched as roadmap only in `agent.md`
§10)**: HTML rendering, editor-facing web UI, OJS plugin integration, peer
review workflow, OA hosting/DOI registration, metadata enrichment
automation. Naming convention for later components if/when built:
`sutra-<component>` (e.g. `sutra-ojs-plugin`, `sutra-review`,
`sutra-publish`).

---

## 2. The Four Documents That Exist (and what each one owns)

Four specs were produced in this conversation, each with a **deliberately
separate mandate** — this separation was a repeated, intentional design
choice throughout the conversation (mirrored across docs 2, 3, 4), not
accidental fragmentation:

| File | Owns | Does NOT own |
|---|---|---|
| `agent.md` | The core deterministic build spec: architecture, IR schema, pipeline steps, content inventory, column-layout handling | Testing, security, AI — kept clean/deterministic-only on purpose |
| `testing-agent.md` | 132 numbered test cases (TC-A through TC-H, plus cross-cutting TC-X suites) proving the build spec's claims | Doesn't re-derive architecture; every test traces to a specific `agent.md` section |
| `security-audit.md` | Threat model + 12 SEC checks against the actual pipeline (DOCX/ZIP/XML parsing, LaTeX compilation, subprocess hygiene) | Generic security checklist — explicitly avoided; everything is grounded in Sutra Press's real attack surface |
| `ai-addon.md` | Optional, opt-in AI assist features (citation structuring, equation transcription) as a removable layer | `agent.md` requires **zero edits** for this to exist — confirmed as a design constraint |

**All four files should be attached/pasted together in a new conversation**
if deep work continues, since they cross-reference each other by section
number and were kept deliberately consistent.

---

## 3. `agent.md` — Core Spec Summary

(Full file is ~714 lines; this is the load-bearing summary, not a
replacement — if continuing technical work, use the actual file.)

### 3.1 Architecture (§3)

```
Manuscript (DOCX/LaTeX) → Structural IR (internal model) → JATS XML (validated)
                                    │
                                    └──→ LaTeX source (template) → PDF (compiled)
```

**The single most important architectural decision, debated explicitly in
this conversation**: JATS and LaTeX are generated as **parallel siblings
from the IR**, never one from the other. The user originally proposed
**IR → LaTeX → JATS** (reasoning: LaTeX feels like a "finished" artifact,
so converting *from* it later should be easier). This was discussed at
length and the chained approach was **rejected** — full reasoning preserved
in `agent.md` §3.3 as a formal ADR:
1. LaTeX is presentational, not semantic — JATS needs structural facts, and
   routing through LaTeX means reverse-engineering structure from formatting
   commands (rebuilding a worse copy of the IR you already had).
2. LaTeX is notoriously hard to parse back out of — even LaTeXML (NIST,
   20+ years of development) still has real fidelity gaps.
3. It trades a well-solved parsing problem (DOCX via Pandoc) for a
   harder one in the wrong direction.
4. It breaks single-source sync — if an editor hand-fixes the generated
   `.tex` during proofing, JATS becomes a stale derivative the moment
   that happens.

`.tex` remains valid as an **input** format (parsing author-supplied LaTeX
into the IR) — that's a separate, unaffected question from using LaTeX as
an internal hop.

### 3.2 Recommended stack (§3.2)

- **Python 3.12+** (matches the prior-art ecosystem researched)
- **DOCX parsing**: Pandoc (via `pypandoc`/subprocess) primary, `python-docx`
  fallback for what Pandoc's AST drops
- **IR**: typed Python objects (pydantic preferred)
- **JATS generation**: `lxml` building JATS 1.3 directly, validated against
  official XSD — never string-templated XML
- **LaTeX generation**: Jinja2 with LaTeX-safe delimiters (`\BLOCK{}`/`\VAR{}`)
- **PDF compilation**: Tectonic (self-contained, reproducible), `latexmk`
  fallback
- Rejected alternatives documented in §3.3: XSLT/XSL-FO as primary
  toolchain (steep learning curve, sparse contributor pool today),
  wkhtmltopdf/Paged.js for PDF (visual fidelity concerns, per eLife's own
  documented experience)

### 3.3 Column layout — single vs. two-column (§4)

User explicitly asked for support for both layouts. Key resolved principle:
**column count is a render-time template parameter, never part of the IR**.
JATS has no concept of columns at all (semantic, not visual) — so column
choice must never leak into content logic. Figures/tables get a `span_hint:
"column" | "page"` field in the IR specifically to carry layout-affecting
signal through to the LaTeX template layer without polluting the IR with
presentation concerns. Two clean template variants per journal style
(single/double), sharing Jinja2 partials, not one template with runtime
branching.

### 3.4 Complete manuscript content inventory (§5)

User asked for an exhaustive list of everything a manuscript can contain.
Built as 8 categories (A–H): Front matter/metadata, Body text structures,
Figures/images, Tables, Mathematical content, Citations/references,
Supplementary/appendix material, Document-level/structural. Each category
fully enumerated in `agent.md` §5.1 (this is long — see the actual file).

Priority tiers (§5.2):
- **Tier 1** (blocks release): title/authors/affiliations/abstract,
  headings, basic inline formatting, lists, footnotes, simple tables,
  raster figures with captions, numbered citations + structured references,
  hyperlinks
- **Tier 2** (soon after): multi-panel figures, merged-cell tables, vector
  figures, OMML equations, author-date citations, CRediT/funding/ethics
  metadata, cross-references
- **Tier 3** (flagged for manual handling, not blocking): equation-as-image,
  tracked changes, multi-page tables, landscape/rotated content, RTL text
  fragments, chemical structure notation, appendix-specific numbering,
  author bio blocks

Full IR schema is in §5.3 — a typed tree (Document → metadata/body/
citations/references/appendices/author_bios) implementing all Tier 1–2
content types plus node types for Tier 3 items (so they can at least be
represented and flagged, never silently dropped).

### 3.5 Pipeline steps (§6) — referenced constantly by the other 3 docs

1. Ingest (.docx primary, .tex secondary/stretch)
2. Pre-flight triage (pass / pass-with-warnings / needs-manual-prep) —
   adopted from meTypeset's historical pattern; flags fake headings,
   unrecognizable citation formats, embedded equation-images **before**
   spending time on full conversion
3. Parse to Pandoc AST
4. Translate AST → IR
5. Citation/reference structuring (flagged repeatedly across all docs as
   THE hardest, most error-prone step)
6. Generate JATS XML from IR
7. Validate JATS against official schema — **hard gate, not done until this
   passes**
8. Generate LaTeX from IR
9. Compile LaTeX → PDF (Tectonic)
10. Package output: `article.xml`, `article.pdf`, `article.tex` (editor
    override), `assets/`, `triage-report.md`, `validation-report.md`

### 3.6 Failure Philosophy (§7) — governs everything downstream

- Never silently drop content (placeholder + warning instead)
- Never produce JATS that fails schema validation and call it done
- Make failures traceable to source location (named worked example used
  repeatedly across all 4 docs: *"Table 3 (page 4, style 'Grid Table 1')
  could not be converted: nested table not supported"*)
- Idempotency: same input twice → byte-identical output

---

## 4. `testing-agent.md` Summary

132 test cases (TC-A-01 through TC-H-05) mapped 1:1 to `agent.md` §5.1's
8 categories, plus 24 cross-cutting tests (TC-X-01–24) covering: column-
layout equivalence (proving same IR → correct single/double output),
single-source sync (proving JATS/LaTeX genuinely derive from one IR, not
drift), idempotency, schema conformance, traceability, triage-report
correctness, performance/robustness.

Two suites marked **non-negotiable, always-blocking**: schema conformance
and single-source sync — these protect the project's two actual core
promises.

6 required fixture manuscripts defined (§3): clean STEM, clean humanities,
deliberately messy/realistic, two-column target, kitchen-sink/maximal,
pathological/adversarial.

---

## 5. `security-audit.md` Summary

Threat-modeled against the **real** pipeline, not a generic checklist.
Trust boundary: untrusted manuscript file → parsing/sandboxing → semi-
trusted IR-derived output → downstream consumers (OJS/PMC/Crossref/editor).

**Two Critical-severity risks, the highest priority in the whole document:**

1. **LaTeX injection → RCE during compilation** (§3.1–3.2). Author content
   (titles, captions, table cells, reference fields) gets substituted into
   generated `.tex`. Cited a real precedent: CVE-2020-37012 (Tea LaTeX),
   where exactly this pattern led to `\write18` shell-escape RCE. Two-layer
   defense: (1) mandatory shared LaTeX-escaping function for every piece of
   author content, no exceptions, and (2) sandboxed/network-disabled
   compilation as a backstop — necessary because LuaTeX's CVE-2023-32700
   proved engine-level exploits can bypass `--no-shell-escape` entirely.

2. **XXE (XML External Entity injection)** (§2.3, §4.1). DOCX is a zip of
   XML; JATS validation also parses XML. Both need `resolve_entities=False`,
   `no_network=True`, no DOCTYPE — enforced through one shared safe-parser
   factory function so there's exactly one place to audit.

**Also covered**: zip bombs / Zip Slip path traversal (DOCX is a ZIP
container), subprocess/shell injection (argument-list form only, never
`shell=True` with interpolated input), dependency supply-chain hygiene
(including Tectonic's on-demand package fetching as a network-egress point
needing pinning), per-job isolation (both security AND confidentiality —
embargoed pre-publication research is a real concern), and a forward-
looking note flagging XSS risk in triage reports for when Phase 2's web UI
gets built.

12 SEC checks (§8), with SEC-03/04 (XXE) and SEC-05/06/07 (LaTeX injection +
sandbox escape) marked non-negotiable/always-blocking.

---

## 6. `ai-addon.md` Summary

**The governing design decision, made explicitly by the user**: AI
integration as a **button, not a pipeline stage** — opt-in, per-instance,
never automatic. This resolved an earlier discussion where Claude initially
suggested AI had no place in Phase 1 at all; the user proposed the
opt-in-button framing, and Claude agreed it was the right call because it
doesn't compromise any of `agent.md` §7's deterministic guarantees (the
human-in-the-loop nature means idempotency/traceability concerns don't
apply the same way to an explicitly-invoked, human-reviewed assist).

**Kept entirely separate from `agent.md`** — confirmed zero edits required
to the core spec for this module to exist; if that ever stops being true,
that's a signal the module has drifted from its intended "additive,
removable layer" design.

**Two features, both chosen because `agent.md` already identifies them as
the deterministic pipeline's weak points:**
1. Citation/reference structuring assist ("Try AI" button on low-confidence
   references, side-by-side proposal + raw text, per-field editable, never
   auto-applied)
2. Equation-as-image transcription assist (the one truly AI-necessary case
   in the whole inventory — no semantic source exists for a pasted equation
   screenshot; side-by-side rendered preview vs. original for verification)

**Explicitly excluded** (§6, with reasoning preserved): AI-assisted
structural parsing, AI-assisted JATS/LaTeX generation, any automatic/
default-on AI, AI-assisted triage *verdicts* (though AI may someday help
*explain* a triage finding in plain language — presentation, not judgment).

**Security addendum (§7)** extending `security-audit.md`: new trust
boundary (outbound calls to AI provider with manuscript-derived content),
prompt-injection risk from malicious reference text (mitigated by closed
schema-constrained output + mandatory human review as the real control),
3 new SEC-AI checks.

---

## 7. Decisions Already Made — Do Not Re-Litigate Without Reason

A new conversation should treat all of these as settled:

- ✅ Name: **Sutra Press**, CLI binary name `sutra`
- ✅ Architecture: IR as single source, JATS + LaTeX as parallel siblings
  (NOT chained through LaTeX — debated and explicitly rejected)
- ✅ Stack: Python + Pandoc + lxml + Jinja2 + Tectonic
- ✅ Column layout: render-time template parameter only, never in IR
- ✅ Failure philosophy: never silent-drop, never skip validation, always
  traceable, idempotent
- ✅ AI: opt-in button only, two features (citations + equation
  transcription), kept in a fully separate, deletable document
- ✅ Four-document structure: build / test / security / AI-addon kept
  deliberately separate, cross-referenced by section number

---

## 8. What Has NOT Been Done Yet (genuine open work)

This conversation produced **specifications only** — no actual code has
been written yet. Real next steps, in the rough order they were being
discussed before this handoff:

1. **Repo scaffolding** — directory structure, the IR as real Pydantic
   models (not just the markdown schema in `agent.md` §5.3), a first
   Pandoc→IR translator stub. This was offered by Claude at the end of
   several turns but not yet started.
2. **Front-page / landing copy** — using the "thread" metaphor from
   `agent.md` §0.1, also offered but not started.
3. Building out the actual fixture corpus described in `testing-agent.md`
   §3 (currently just specified, not constructed).
4. Implementing any part of the pipeline itself (steps in `agent.md` §6 are
   all still spec, zero implementation).
5. `ai-addon.md`'s features are speculative/optional Phase 2-ish work, not
   started, and per its own design, may never be built at all without
   breaking anything.

---

## 9. Suggested First Message in a New Conversation

Something like:

> *"This is the handoff doc for a project called Sutra Press — a
> manuscript-to-JATS/LaTeX conversion engine. Read it fully, then [pick
> one: scaffold the actual repo / write the front-page copy / something
> else]."*

If the four spec files (`agent.md`, `testing-agent.md`, `security-audit.md`,
`ai-addon.md`) are also still available, attach/paste those too — this
handoff file is a summary with enough fidelity to resume *reasoning*, but
the actual specs have implementation-level detail (full IR schemas, all 132
test cases, all 12+3 security checks) this summary intentionally compresses.

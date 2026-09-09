# update-agent.md — Sutra Press: Structured Review Editor (Phase 1 Revision)

## 0. Purpose & Relationship to the Other Four Documents

This document specifies a **revision to Phase 1 of `agent.md`**, not a new
phase and not an optional addon. It exists as a separate file for the same
reason `testing-agent.md`, `security-audit.md`, and `ai-addon.md` are
separate — a distinct mandate, cross-referenced by section number — but
unlike those three, **this document changes what Phase 1's deliverable
actually is.** It does not sit alongside `agent.md` the way `ai-addon.md`
does (§2 of that document: "`agent.md` requires zero edits for this module
to exist"). This one requires `agent.md` to be read *through* this
document's amendments wherever they conflict.

**Why this exists**: real-world testing of the Phase 1 build (the upload
screen in the reference screenshot — DOCX in, JATS/PDF out, no
intermediate visibility) surfaced the system's central honest limitation,
already predicted in `agent.md` itself:

> **`agent.md` §2, Key lesson**: "no automated DOCX→JATS converter handles
> 100% of arbitrary manuscripts... The agent must design for partial
> success + clear failure reporting, not silent best-effort mangling."

The Phase 1 triage report (`agent.md` §6 step 2) implements the
*reporting* half of that lesson — it tells the editor a fake heading or an
equation-image was found. It does **not** implement a *correction* half —
the editor reads the warning, then has no way to act on it inside the
system. They'd have to re-edit the source DOCX and re-upload blind, hoping
the fix landed correctly, with no visibility into the IR the parser
actually built. That gap is what this document closes.

**The one-sentence design constraint that governs everything below**: the
triage report becomes an **editor**, not a verdict. Every element the
parser identified — heading, paragraph, figure, table, equation, citation,
footnote, everything in `agent.md` §5.1's inventory — is shown to the human
as an explicit, individually-confirmable tag *before* JATS/LaTeX
generation runs, not just flagged in a markdown summary after the fact.
Generation becomes a deliberate second step the editor triggers once
they're satisfied the tagging is correct, not an automatic continuation of
parsing.

---

## 1. What's Being Amended in `agent.md` (read this first)

A precise list, so nothing is ambiguous about what still holds and what
doesn't. Everything in `agent.md` **not** listed here is unchanged and
still governs — the IR schema (§5.3), the parallel-siblings architecture
(§3.1/§3.3), the stack (§3.2), the content inventory (§5.1), the priority
tiers (§5.2), the Failure Philosophy (§7) — all of it stands. This is a
revision to the *pipeline's shape around* the IR, not to the IR or to what
the engine can parse.

| `agent.md` section | Original | Amended by this document |
|---|---|---|
| §6 step 2 (Pre-flight triage) | Produces a triage report (pass / pass-with-warnings / needs-manual-prep) as a document, before conversion | Still runs first, unchanged in *what* it checks — but its output now populates an **interactive tag review** (§3 below), not only a markdown report. The report still exists (§6 below) as an export/audit artifact, but it's a side effect of the editor state, not the primary interface. |
| §6 steps 6 & 8 (Generate JATS / Generate LaTeX) | Run automatically as the next pipeline steps after IR translation | Now gated behind an explicit **"Generate"** action the editor triggers from the review screen (§4), only available once tag review is in an acceptable state (§4.3). Nothing downstream of the IR generates automatically anymore. |
| §6 step 10 (Package output) | One-shot output per conversion run | Unchanged in shape, but now one of potentially **many** generation runs against the same persisted source document (§5) — each run is still packaged identically, just re-triggerable. |
| *(new)* | — | A **persistence layer** for uploaded manuscripts and their reviewed/edited IR state, so re-generation doesn't require re-upload. This is genuinely new — `agent.md` had no concept of a document outliving one CLI invocation. See §5. |
| *(new)* | — | A **visual design system** (light, modern theme) for the web UI, since `agent.md` §10 only sketched the web UI as a future bullet point ("FastAPI + a simple frontend") with no visual direction given. See §7. |

**What is explicitly NOT being amended**: the CLI (`sutra convert
<input.docx> --out <dir>`) continues to exist and continues to work
exactly as `agent.md` specifies — full pipeline, no human-in-the-loop
review step, triage report as a markdown file, one-shot. The editor
described in this document is a **web-UI-only concern**, layered on the
same engine. Someone scripting batch conversions via CLI is not forced
through a review screen. This mirrors `ai-addon.md`'s own pattern of
"the non-AI/non-interactive path keeps working exactly as before" — applied
here to the CLI path rather than to AI specifically.

---

## 2. Why This Was Necessary (the gap, stated precisely)

`agent.md` §6 step 2 already lists the right triage *checks*:

- Are headings using real Word heading styles, or fake bold+bigger text?
- Are citations in a recognizable format?
- Are there embedded objects (equation images, etc.) needing special
  handling?

And `agent.md` §7 already establishes the right *philosophy*: never
silently drop content, make failures traceable to source location, label
partial success as partial. Both of these were correct and remain
correct. What was missing was the **interface** that lets a human act on
that information before it's too late to matter cheaply:

1. A triage report is read-only. An editor seeing "fake heading detected
   at paragraph 14" cannot fix it from inside Sutra Press — they have to
   go back to Word, find paragraph 14, fix the style, re-export, and
   re-upload the entire manuscript, then re-read the new triage report to
   confirm the fix landed and didn't break something else.
2. A triage report only surfaces what's *wrong* (per its own design,
   correctly — agent.md §7 says flag-don't-silently-pass). It does not
   give visibility into what was parsed *correctly* either, so the editor
   has no way to build confidence in the 95% the parser got right without
   manually reading the generated JATS XML directly — which is exactly
   the kind of XML-literacy burden `agent.md` §1 (Problem Statement) says
   this tool exists to remove.
3. Generation (JATS + LaTeX + PDF) runs immediately after parsing with no
   gate. If triage comes back `pass-with-warnings`, the editor gets full
   output anyway, including whatever degraded handling those warnings
   describe (an equation embedded as an image, a table flagged
   `needs-manual-prep` but converted as best-effort regardless). There's
   no natural checkpoint to stop and fix things first without throwing
   away and re-running the whole pipeline.

None of this contradicts anything `agent.md` claimed — §2's "no automated
converter handles 100% of arbitrary manuscripts" was always honest about
this exact gap existing. This document is what closes it.

---

## 3. The Tag Review Model

### 3.1 Core concept: every IR node is a tagged, visible block

After `agent.md` §6 steps 3–4 (Parse to Pandoc AST, Translate AST → IR)
complete, the editor does not see a triage-report document. They see the
**manuscript itself, rendered block-by-block, with every block labeled by
its IR node type** — the same type vocabulary already defined in
`agent.md` §5.3's IR schema, with nothing invented:

```
[Title]           Photosynthetic Efficiency in Low-Light Understory Species
[Authors]         J. Smith¹, A. Lee²
[Affiliations]    ¹Dept. of Botany, ...  ²Dept. of Ecology, ...
[Abstract]        Background: ...  Methods: ...
[Heading L1]      1. Introduction
[Paragraph]       Photosynthesis in understory plants has long been...
[Figure]          ▢ fig-01.png — "Light response curves across species"
                    ⚠ no alt-text detected
[Heading L1]      2. Methods
[Table]           ▢ 3 cols × 8 rows, 1 header row
[Heading L2]      2.1 Statistical Analysis
[Paragraph]       ⚠ detected as fake heading (bold, 14pt, no style) —
                    confirm: paragraph or retag as heading?
[Equation]        ⚠ embedded as image, no OMML source — degraded output
[Footnote]        ¹ Funding details...
[Reference List]  ▢ 24 entries, 22 high-confidence, 2 flagged low-confidence
```

Every line in this view corresponds to exactly one node in the IR tree
(`agent.md` §5.3) — there is no view-layer content that doesn't map back
to a real IR node, and no IR node that's invisible to this view. This is
the same traceability principle from `agent.md` §7 ("make failures
traceable to source location"), extended from *error messages* to the
*entire successful parse*, not just the failures.

### 3.2 Tag states

Each block carries one of three states, visually distinct (see §7.3 for
the actual color treatment):

| State | Meaning | Trigger |
|---|---|---|
| **Confirmed** | Parser identified this with high confidence; no flag raised by triage logic (`agent.md` §6 step 2's checks) | Default state for anything the deterministic parser is confident about — most Tier 1 content (`agent.md` §5.2) in a clean manuscript lands here automatically |
| **Needs review** | Triage logic raised a flag on this specific node — corresponds 1:1 to what `agent.md` §6 step 2 already checks for (fake heading, ambiguous citation, embedded-image equation, low-confidence reference, missing alt-text, tracked-change remnant, etc.) | Same triggers `agent.md` §6 step 2 already defines — this document does not add new triage *logic*, only a new *surface* for existing triage logic's findings, attached to the specific node rather than rolled into a document-level summary |
| **Unrecognized** | Parser could not confidently classify this content as any known IR node type at all — distinct from "needs review" (which means "classified, but flagged"); this means "couldn't classify" | Content that doesn't cleanly map to Pandoc AST → IR translation (`agent.md` §6 step 4) — e.g. a structure Pandoc's AST flattened ambiguously, or content `agent.md` §5.2's Tier 3 list doesn't yet have full IR node logic for |

**Why three states, not two**: `agent.md` §7's failure philosophy already
draws this exact distinction without naming it — "never silently drop
content" implies there's a difference between *content the system
understood but flagged* (needs review) and *content the system genuinely
could not place* (unrecognized). Collapsing these into one "warning" state
would lose information the editor needs: a flagged fake-heading is a
one-click fix (retag it); an unrecognized block might need the editor to
manually re-author that section's structure entirely. Different problems,
different effort, should look different.

### 3.3 What "Unrecognized" guarantees (the actual ask)

This is the most important guarantee in this document, directly answering
the stated requirement — *"as I upload the document, it should provide
tags in everything... so that I am sure that algorithm has picked
everything correctly"*:

**Every byte of extractable text content from the source manuscript
appears as some block in the review view, tagged with one of the three
states above. There is no fourth state of "invisible." If the parser
cannot classify a piece of content, it still renders as a block, tagged
`Unrecognized`, with the raw extracted text/content visible** — it does
not vanish from the view the way it would currently vanish from a triage
*report* (which only mentions problems in prose, not unaccounted-for
content as inline blocks).

This is a direct strengthening of `agent.md` §7's "never silently drop
content" rule, moved from *governing final output* to *governing the
review surface itself*. The original rule was about JATS/LaTeX output
never silently losing content; this document applies the identical
principle one stage earlier, to the editor's view of the parse.

### 3.4 Per-block actions

Every block, regardless of state, supports the same small action set —
deliberately small, because this is a **review and retag** surface, not a
general document editor (see §3.5 for the explicit scope boundary):

1. **Confirm** — accept the parser's tag as correct. Moves a `Needs
   review` block to `Confirmed`. (Already-`Confirmed` blocks don't need
   this — it's available as an explicit affordance for paranoid/thorough
   review, not required.)
2. **Retag** — change the block's IR node type via a dropdown scoped to
   valid `agent.md` §5.3 node types for that content shape (e.g. a
   paragraph can be retagged to any heading level, a block quote, a list
   item; a heading can be retagged to a different level or demoted to a
   paragraph; an unrecognized block can be assigned any node type at
   all). Retagging a fake-heading paragraph to `Heading L2` is the
   single most common action this whole document exists to enable — it
   directly answers `agent.md` §6 step 2's flagged case ("are headings
   using Word's actual heading styles, or manual bold+bigger text? the
   latter cannot be reliably converted") with an actual fix path instead
   of only a flag.
3. **Split** — for a block that actually contains two distinct IR nodes
   merged into one (e.g. Pandoc's AST occasionally flattens a heading and
   its following paragraph into adjacent-but-ambiguous nodes) — divides
   one block into two, each independently tagged.
4. **Merge** — the inverse: two adjacent blocks that should be one IR
   node (e.g. a multi-panel figure that parsed as separate images instead
   of one figure with `panels[]` per `agent.md` §5.3) combine into one,
   tagged appropriately.
5. **Flag for manual handling** — explicitly mark a block as something
   the editor knows the engine can't handle (e.g. a genuinely Tier 3 case
   per `agent.md` §5.2) and accepts will ship as a placeholder/degraded
   form, rather than leaving it ambiguously `Unrecognized` forever. This
   is the UI expression of `agent.md` §7's "label partial success as
   partial" — an explicit, recorded acknowledgment, not a silent gap.

### 3.5 Explicit scope boundary: structure, not prose

**This is not a word processor.** The review surface lets the editor
change what a block *is* (its IR node type, its boundaries via split/
merge) — it does not let the editor rewrite the *text content* of a
paragraph, fix a typo in a title, or change a citation's actual reference
data inline. That capability is **already specified and out of scope for
this document**: `agent.md` §6 step 10 already ships the raw `.tex` file
specifically "for editor inspection/override," and `ai-addon.md` §3
already specifies a structured, narrow text-correction flow for the one
case that most needs it (citation fields). Content-level correction for
everything else remains "fix the source DOCX and re-upload" — unchanged
from `agent.md`'s original design.

**Why this boundary, stated honestly**: a full inline content editor is a
much larger, much riskier surface — it would mean user-edited text re-enters
the IR and has to be re-validated, re-escaped (every control in
`security-audit.md` §3.1/§4.2 about author-content injection into
LaTeX/XML applies identically to editor-typed text, not just
parser-extracted text), and creates a second source of truth alongside the
original manuscript that can drift. Structural retagging avoids all of
this: a retagged block's *content* is still the literal text the parser
extracted from the source DOCX, just reclassified — so every downstream
security control and the single-source-sync guarantee (`agent.md` §3.1)
hold without modification. If a future need for inline content editing
emerges, that's a candidate for its own document, following the same
separate-mandate pattern as `ai-addon.md` — not folded into this one.

---

## 4. Generation as an Explicit, Gated Action

### 4.1 The gate

`agent.md` §6 steps 6–9 (JATS generation through PDF compilation) no
longer run automatically once IR translation (`agent.md` §6 step 4)
completes. They run only when the editor clicks **"Generate JATS-XML,
PDF & LaTeX"** from the review screen — matching the exact phrasing in
the stated requirement.

This button is:

- **Disabled** while any block is in the `Unrecognized` state and has not
  been explicitly retagged or flagged-for-manual-handling (§3.4 action
  5). Generation cannot silently proceed past content the system admits
  it couldn't classify — that would reintroduce exactly the silent-gap
  failure mode this document exists to close.
- **Enabled with a visible warning count** when blocks remain in `Needs
  review` state but none are `Unrecognized` — generation is allowed
  (the editor may legitimately decide some warnings are fine to ship
  with, e.g. accepting a flagged equation will embed as an image), but
  the warning count travels with the action so it's never an accidental
  oversight.
- **Enabled, clean** when all blocks are `Confirmed` or explicitly
  flagged-for-manual-handling.

This preserves `agent.md` §7's principle ("partial success must be
labeled partial") while finally giving the editor agency over *when*
partial is acceptable, rather than discovering it only after output is
already generated.

### 4.2 What happens on click

Exactly `agent.md` §6 steps 6–9, unchanged: IR → JATS generation → schema
validation (hard gate, unchanged from `agent.md` §6 step 7 — this
document does not weaken that gate, it only adds a human gate *before*
it, not instead of it) → LaTeX generation → PDF compilation. Output
packaging (`agent.md` §6 step 10) is unchanged in its contents.

**One addition**: the package now also includes a record of the review
session itself — which blocks were retagged, split, merged, or
flagged-for-manual-handling, and by what action — as a new file,
`{slug}/review-log.md`, alongside the existing `triage-report.md` and
`validation-report.md`. This is the same provenance instinct as
`ai-addon.md` §5's provenance tracking, applied to human retagging
decisions instead of AI proposals: a future editor or auditor should be
able to see not just *what* the final IR looked like, but *that a human
deliberately reclassified this specific block from X to Y*, the same way
`ai-addon.md` ensures AI-touched content is distinguishable from
deterministically-parsed content.

### 4.3 Re-generation

Because the reviewed/edited tag state is persisted (§5), clicking
"Generate" again after further retagging does not require re-uploading or
re-parsing the manuscript from scratch — it re-runs `agent.md` §6 steps
6–9 against the **current** IR state (original parse + all accepted
retag/split/merge actions applied), producing a new output package. This
directly satisfies the stated requirement to "keep the document so that
we can generate the document again as per requirement."

Each generation run is independently packaged (§4.2) and timestamped;
prior runs are not overwritten, so an editor can compare a regeneration
against a previous attempt if needed. (Idempotency, per `agent.md` §7,
still holds *within* a single generation run against a fixed IR state —
running "Generate" twice without any IR change in between still produces
byte-identical output, exactly as `agent.md` §7/§8 already requires. What's
new is that the IR state itself is now mutable across review sessions,
which is an explicitly intended capability of this document, not a
regression of idempotency.)

---

## 5. Persistence Layer (new — `agent.md` had no equivalent)

### 5.1 What's persisted, and why this doesn't conflict with `security-audit.md`

`security-audit.md` §6.3 currently requires per-job working directories be
deleted immediately after job completion, with no deferred cleanup,
specifically to prevent one job's confidential manuscript content from
outliving its job or becoming visible to a different job. This document's
persistence requirement is **not** a rollback of that control — it's a
distinction `security-audit.md` didn't previously need to draw, between
two different lifetimes:

- **Job** (`security-audit.md`'s existing unit): one parse-or-compile
  operation's ephemeral working directory — extraction scratch space,
  intermediate Pandoc AST dumps, the LaTeX compile sandbox. This is
  unchanged: still ephemeral, still wiped immediately after the
  operation completes, exactly as `security-audit.md` §3.2/§6.3 already
  require. A job has no business surviving past its own operation
  whether or not this document exists.
- **Project** (new unit this document introduces): the durable record of
  one uploaded manuscript — its original file, its current IR state
  (including all accepted retag/split/merge/flag actions from review
  sessions), and the history of generation runs against it. This is
  what persists, deliberately, so the editor doesn't have to re-upload
  and re-parse from zero every time they want to regenerate after a
  retagging fix.

A project is not a job left running — it's storage at rest between jobs.
Every individual "parse this DOCX" or "compile this LaTeX" operation
still happens inside its own ephemeral, isolated job sandbox per
`security-audit.md`'s existing requirements; that sandbox is still wiped
the moment the operation finishes. The project record that operation
reads from and writes results back to is a separate, durably-stored
thing, governed by the controls in §5.2 below rather than by §6.3's
job-ephemerality rule, which was never written to cover durable storage
in the first place (it explicitly covers *working directories* and
*intermediate artifacts*, not a deliberately-retained source-of-truth
record).

### 5.2 Required controls for project storage (extends `security-audit.md`)

Since this is genuinely new attack surface `security-audit.md` didn't
threat-model (it only anticipated this gap forward-looking, in §6.2's
note about Phase 2's web UI), this document adds the controls directly
rather than leaving them implicit:

- **At-rest encryption** for stored manuscripts and IR state, consistent
  with `ai-addon.md` §7.1's existing concern that manuscripts are
  "frequently embargoed/pre-publication/confidential research" —
  the same sensitivity classification applies to a manuscript sitting in
  project storage for days between review sessions as applies to one
  in-flight through a job.
- **Per-project access scoping**: a project is only readable/writable by
  the editor (or editorial team, if multi-user) who uploaded it — this
  is the durable-storage equivalent of `security-audit.md` SEC-10's
  concurrent-job-isolation test, extended to mean "project A's stored
  content is never reachable by anyone with access only to project B,"
  not just "job A and job B don't see each other while both running."
- **Explicit retention/deletion**: the editor can delete a project
  outright (full removal of the original file, IR state, and all past
  generation outputs) — this is a real delete (`security-audit.md`'s
  "Prohibited" action category for irreversible deletes, in the broader
  agent-safety framing this whole system operates under, applies here:
  confirm-before-permanent-delete, not a quiet auto-expiry no one
  configured intentionally).
- **No new XML/LaTeX parsing surface introduced by persistence itself**:
  storing and retrieving the IR state is a structured data
  read/write (the IR is already a typed schema per `agent.md` §5.3,
  e.g. as JSON), not a re-parse of untrusted manuscript bytes on every
  load — so this doesn't reopen `security-audit.md` §2's DOCX-ingestion
  threat surface on every page view, only on the original upload.

### 5.3 What is NOT persisted

Generated PDF/JATS/LaTeX output from past generation runs (§4.3) is
retained as **packaged output artifacts** (same as `agent.md` §6 step 10
already specifies), not regenerated from IR on every view — but these are
treated as derived, reproducible data: deleting a project's stored output
history is lower-stakes than deleting its source manuscript and IR state,
since (idempotency permitting, per §4.3) the same IR state regenerates
the same output deterministically if ever needed again.

---

## 6. Triage Report: Still Exists, Now Derived

`agent.md` §6 step 2's triage report is not removed — `pass /
pass-with-warnings / needs-manual-prep` as a verdict, and a markdown
artifact summarizing findings, are both still genuinely useful (for CI
contexts, for the CLI path which has no interactive review screen at all
per §1's table, and as a quick-glance summary even in the web UI before
diving into block-by-block review). What changes is its **role**:

- In the **CLI path** (unchanged, per §1): triage report is produced and
  consumed exactly as `agent.md` §6 step 2 originally specifies — a
  document, read by a human, informing a decision to proceed or not.
- In the **web UI path** (this document's actual subject): the triage
  report becomes a **derived summary view** of the same underlying
  per-block tag states described in §3 — i.e. `pass-with-warnings`
  literally means "N blocks are in `Needs review` state," and
  `needs-manual-prep` means "N blocks are `Unrecognized` or explicitly
  flagged." The verdict and the interactive review are two
  representations of one underlying state, not two separately-maintained
  things that could drift from each other. This mirrors the same
  single-source discipline `agent.md` §3.1 applies to JATS/LaTeX — one
  source of truth (here, per-block tag state), multiple expressions of
  it (a markdown report, an interactive screen).

---

## 7. Visual Design: Light, Modern Theme

### 7.1 Why this needs stating explicitly

The reference screenshot (current Phase 1 prototype) uses a dark theme.
The stated requirement is an explicit reversal: **light, modern** for
the rebuilt review/editor interface. This is a deliberate design
direction, not a minor styling note, given how much this document adds
to the UI's actual surface area (a dense, information-heavy block-review
list is a very different design problem than a single upload dropzone)
— so it's worth being concrete rather than leaving "light and modern" to
be reinterpreted loosely later.

### 7.2 Direction

- **Background**: near-white, not stark `#FFFFFF` — a warm-neutral off-
  white reduces eye strain across what will often be long review
  sessions scanning dozens of blocks.
- **Typography**: a clean, high-legibility sans-serif for UI chrome and
  body text (the manuscript content itself, when rendered inside blocks,
  should read close to how it'll actually typeset — i.e. don't fight the
  "this is an editorial tool for real documents" tone with an overly
  playful UI font).
- **Tag-state color coding** (§3.2), the single most functionally
  important color decision in this UI:
  - `Confirmed` — calm, low-saturation green or neutral, deliberately
    unobtrusive (most of the document should be this state in a clean
    manuscript; it should recede, not compete for attention)
  - `Needs review` — amber/warm, attention-getting but not alarming
  - `Unrecognized` — a clearly distinct warm red/orange, the strongest
    visual weight in the system, since this is the state the editor must
    resolve before generation is unblocked (§4.1)
- **Block type labels** (`[Title]`, `[Heading L1]`, `[Figure]`, etc.):
  small, consistent, monospace-or-similar tag chips — visually distinct
  from the manuscript content itself so the eye can scan tags
  independent of reading content, the same way code editors distinguish
  syntax highlighting from prose.
- Consult the **frontend-design skill** when this interface is actually
  built — `agent.md` §10 already flagged the future web UI as "a strong
  candidate for the frontend-design skill"; that note transfers directly
  to this document since this *is* that web UI's first real specification.

### 7.3 Explicit non-goals for this section

This document specifies *direction and constraints* (light theme,
functional color coding, legibility priorities), not a pixel-level design
file — exact hex values, spacing scale, and component-level decisions
belong to implementation, consistent with how `agent.md` §3.2 specifies a
stack and rationale without hand-designing every class, not a full design
system spec.

---

## 8. Updated Pipeline Diagram

Supersedes `agent.md` §3.1's diagram for the web UI path only (the CLI
path, per §1, still matches `agent.md` §3.1 exactly):

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  Manuscript  │────▶│  Pre-flight       │────▶│  Structural IR      │
│  upload      │     │  triage (agent.md │     │  (agent.md §5.3)    │
│  (persisted, │     │  §6 step 2 checks)│     │                     │
│  §5)         │     └──────────────────┘     └─────────┬───────────┘
└──────────────┘                                          │
                                                           ▼
                                              ┌─────────────────────────┐
                                              │  TAG REVIEW (new, §3)    │
                                              │  every IR node shown as  │
                                              │  Confirmed / Needs       │
                                              │  review / Unrecognized;  │
                                              │  confirm / retag / split │
                                              │  / merge / flag actions  │
                                              └─────────────┬───────────┘
                                                             │
                                              editor clicks "Generate"
                                                  (gated, §4.1)
                                                             │
                              ┌──────────────────────────────┴───────┐
                              ▼                                      ▼
                  ┌──────────────────────┐              ┌──────────────────────┐
                  │  JATS XML (validated) │              │  LaTeX → PDF          │
                  │  agent.md §6 steps     │              │  agent.md §6 steps    │
                  │  6–7, unchanged        │              │  8–9, unchanged       │
                  └──────────────────────┘              └──────────────────────┘
                              │                                      │
                              └──────────────┬───────────────────────┘
                                              ▼
                              Package + review-log.md (§4.2)
                              Editor may retag further and
                              re-click Generate (§4.3) without
                              re-uploading — project persists (§5)
```

The IR remains the single fan-out point for JATS/LaTeX exactly as
`agent.md` §3.1/§3.3 mandates and rejects-the-alternative-to — this
document inserts a human checkpoint *before* the fan-out, it does not
touch the fan-out's shape or reopen the chained-pipeline question §3.3
already settled.

---

## 9. Impact on `testing-agent.md` and `security-audit.md`

Neither sibling document needs a structural rewrite, but both need
acknowledged follow-up, named here so it isn't lost:

**`testing-agent.md`**:
- All existing TC-A through TC-H cases (content-correctness) and TC-X
  cross-cutting suites remain valid and necessary unchanged — they test
  the IR and generation logic, which this document doesn't alter.
- New coverage needed, not yet specified in detail here (flagged as a gap
  for a future testing-agent.md revision, the same way `agent.md` §9's
  deliverables list things still open): tag-state correctness (does a
  known-fake-heading fixture correctly land in `Needs review`, does a
  genuinely unparseable fixture correctly land in `Unrecognized` rather
  than silently merging into an adjacent block), retag/split/merge action
  correctness (does retagging actually update the IR node that flows into
  generation, not just the view), and the generation-gate logic (TC-X-19's
  override-flag concept, originally about CLI `needs-manual-prep`,
  has a direct UI analog worth a dedicated test: does "Generate" actually
  stay disabled while `Unrecognized` blocks remain unresolved).

**`security-audit.md`**:
- §6.3 (per-job isolation) needs the job-vs-project distinction from this
  document's §5.1 folded in explicitly — not contradicted, clarified,
  since as currently worded it could be misread as prohibiting the
  persistence this document requires.
- New section needed (flagged here, not written here, since
  `security-audit.md` §9 item 4 already commits to "re-reviewed whenever
  agent.md's architecture... adds... a new trust boundary"): project
  storage at rest is exactly such a new trust boundary, per this
  document's §5.2 controls, and deserves the same SEC-NN-style numbered
  verification treatment the rest of `security-audit.md` uses, in a
  future revision pass.

This document deliberately doesn't pre-write those tests/checks itself —
consistent with how `agent.md`, `testing-agent.md`, and `security-audit.md`
already maintain separate mandates owned by separate passes, manufacturing
new test/security content here would blur that boundary rather than
respect it.

---

## 10. Definition of Done for This Revision

1. Web UI upload flow produces a **tag review screen**, not an immediate
   conversion — every IR node from the parsed manuscript appears as a
   labeled block in one of the three states (§3.2), with no content
   invisible to the view (§3.3).
2. Confirm / retag / split / merge / flag-for-manual-handling actions
   (§3.4) are implemented and correctly mutate the underlying IR state,
   verified by the IR being the actual input to generation (§4.2) — not
   a view-layer-only change that generation ignores.
3. "Generate JATS-XML, PDF & LaTeX" is gated per §4.1's rules — disabled
   while unresolved `Unrecognized` blocks remain, enabled-with-warning-
   count otherwise.
4. Re-generation against a previously-reviewed project works without
   re-upload (§4.3), proven by a project that's been retagged once,
   generated, retagged again, and regenerated, with both output packages
   inspectable and the second reflecting the additional retag.
5. Project persistence (§5) implements the controls in §5.2 (at-rest
   encryption, per-project access scoping, explicit delete) before
   handling any real (non-test) manuscript content — same bar
   `ai-addon.md` §8 item 4 sets for its own security addendum.
6. UI matches the light/modern direction in §7 — reviewed against the
   frontend-design skill's guidance at implementation time, not against
   this document's prose alone.
7. The CLI path (`agent.md`'s original `sutra convert` command) is
   verified unchanged — same inputs, same outputs, same one-shot
   triage-report-then-convert behavior, proving this revision is additive
   to the web UI specifically and doesn't regress the non-interactive
   path per §1's explicit boundary.
8. `testing-agent.md` and `security-audit.md` gaps named in §9 are
   tracked (e.g. as issues/backlog items), not silently left implicit —
   consistent with this whole document suite's standing practice of
   naming open work explicitly (`agent.md` §10, `RESUME-CONTEXT.md` §8)
   rather than letting it go unrecorded.

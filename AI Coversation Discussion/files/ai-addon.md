# ai-addon.md — Sutra Press: AI Assist Module (Optional)

## 0. Purpose & Relationship to agent.md

This document specifies an **optional, opt-in AI assist module** for
**Sutra Press**. It is deliberately kept as a **separate document from a
separate mandate**, the same way `testing-agent.md` and
`security-audit.md` are separate from the core build spec — but for a
different reason than those two: this isn't a parallel concern that
applies to the whole system, it's an **additive, removable layer** that
must never become load-bearing for the core engine's correctness.

**The one-sentence design constraint that governs everything in this
document**: AI is a **button, not a pipeline stage.** A human explicitly
invokes it on a specific, already-flagged piece of content; it proposes a
result; a human reviews and accepts/edits/rejects before that result
becomes part of the document. It is never invoked automatically, never
silently substituted into the default flow, and never exempt from any
validation gate the deterministic path already has to pass.

**Why kept out of `agent.md` entirely**: `agent.md` §7 (Failure
Philosophy) establishes idempotency ("running the same input twice
produces byte-identical output"), traceability ("make failures traceable
to source location"), and a hard validation gate ("conversion is not
done until [JATS schema validation] passes") as non-negotiable properties
of the **core** engine. LLM-based steps are non-deterministic by default
and don't have a clean notion of "traceable to source location" in the
same way a parser does. Rather than weaken those properties to
accommodate AI, or write awkward AI-aware exceptions into the core spec,
this module exists entirely **alongside** the core pipeline, touching it
only at well-defined insertion points (§3), so `agent.md` stays a clean,
fully deterministic spec that reads correctly whether or not this addon
is ever built.

---

## 1. Scope

**In scope**: two specific, opt-in assist features, chosen because they
sit exactly where `agent.md`'s own research (its §2 prior-art review and
§5.2 Tier 3 list) already identifies the deterministic pipeline as
weakest:

1. **Citation/reference structuring assist** — for references the
   deterministic parser (`agent.md` §6 step 5) can't confidently
   structure.
2. **Equation-as-image transcription assist** — for the one item in
   `agent.md` §5.2's Tier 3 list that is arguably *impossible* to solve
   deterministically, since a pasted equation image has no semantic
   source to parse.

**Explicitly out of scope** (see §6 for the reasoning on each):
- AI-assisted structural parsing of the manuscript itself (headings,
  sections, paragraphs)
- AI-assisted JATS or LaTeX generation
- Any automatic/default-on AI behavior anywhere in the pipeline
- AI-assisted triage *decisions* (AI may help explain a triage finding
  in plainer language — see §3.3 — but never makes the pass/warn/fail
  call itself)

---

## 2. Core Design Rules (apply to every feature in this document)

These are the rules that keep this module from quietly becoming
load-bearing over time — the most common way an "optional" feature stops
being optional is gradual, well-intentioned scope creep, so these are
written as hard constraints, not preferences.

1. **Opt-in only, per-instance.** Every AI-assisted action is triggered
   by an explicit user action (a button) on a specific, individual flagged
   item — never a "process whole document with AI" mode, and never
   triggered automatically by the pipeline itself.
2. **Propose, never apply.** The AI's output is always a **proposal**
   shown to a human, never written directly into the IR. The IR is only
   updated after explicit human acceptance (§4).
3. **No validation bypass.** Whatever the AI proposes ultimately becomes
   ordinary IR content like anything else, and is subject to exactly the
   same downstream checks as deterministically-parsed content: JATS
   schema validation (`agent.md` §6 step 7), LaTeX compile (`agent.md` §6
   step 9), and every relevant test case in `testing-agent.md`. There is
   no "AI-sourced content gets a pass" exception anywhere.
4. **Available without it.** Every feature this module adds must have a
   functioning, sensible **non-AI fallback already specified in
   `agent.md`** — i.e. this module never introduces a capability that
   *requires* AI to function at all; it only improves the experience of
   handling cases `agent.md` already handles via flagging-for-manual-
   review. If the AI is unavailable (no API key configured, network
   down, rate-limited, person doesn't click the button), the system
   behaves exactly as `agent.md` already specifies with zero degradation
   versus AI not existing.
5. **No silent retries or auto-acceptance.** A low-confidence or failed
   AI proposal is shown as such, not auto-discarded-and-retried, not
   auto-accepted because "it's probably fine." The human always sees
   what happened.
6. **Traceable provenance.** Any IR content that originated from an
   accepted AI proposal carries a provenance marker (§5) distinguishing
   it from deterministically-parsed content, persisted through to output
   — so an editor (or a future audit) can always tell which parts of a
   published article were AI-assisted versus directly parsed, even after
   the fact.
7. **Same security posture as everything else.** Any AI provider call
   crossing a network boundary is subject to the same trust-boundary
   discipline as the rest of the system per `security-audit.md` — see §7
   of this document for the specific additions this module introduces to
   that audit.

---

## 3. Feature 1: Citation/Reference Structuring Assist

### 3.1 Where this hooks into the existing pipeline

`agent.md` §6 step 5 already specifies: *"parse the reference list text
into structured fields... rather than treating each reference as an
opaque string"* using a deterministic citation-parsing approach. This
module adds: when that deterministic parser's confidence for a given
reference entry is low (or it fails outright), the triage/review surface
shows a **"Try AI"** button next to that specific entry, instead of (or
alongside) flagging it for fully manual editor entry.

### 3.2 Flow

1. Deterministic parser attempts to structure reference entry *N* per
   `agent.md` §6 step 5.
2. If confidence is below a defined threshold (or parsing fails), the
   entry is shown in the review surface in its **raw, unstructured
   text form**, exactly as `agent.md` already specifies as the fallback
   — this module changes nothing about that default state.
3. Next to it: a **"Try AI"** button. Not clicked → nothing changes from
   `agent.md`'s existing behavior; the editor structures it manually or
   leaves it flagged.
4. If clicked: the raw reference text is sent to an LLM with a narrow,
   specific prompt (structure this single reference string into the
   IR's reference schema fields — `agent.md` §5.3's `references[]` shape:
   type, authors, year, title, source_title, volume, issue, pages,
   publisher, doi, url, access_date) and a **closed output format**
   (structured JSON matching the schema, not free text).
5. The proposed structured fields are displayed **side-by-side with the
   original raw text**, editable, with each field individually visible —
   not a black-box "accepted" toggle.
6. Editor reviews, edits any field if needed, and explicitly accepts.
7. Only on acceptance does this become a real `references[]` entry in
   the IR, carrying the provenance marker (§5).
8. If rejected or left unaddressed: falls back to exactly what
   `agent.md` §6 step 5 already does for low-confidence references —
   flagged for manual entry, never silently dropped (per `agent.md` §7's
   "never silently drop content" rule, which this module doesn't get to
   relax).

### 3.3 Why this is a good fit (and its limits)

This is the single highest-leverage spot for AI assistance in the whole
system: `agent.md` §2's prior-art review flagged citation structuring as
*the* recurring manual-cleanup bottleneck across every comparable
open-source tool studied. An LLM is plausibly better-suited than
regex/heuristic parsing at handling genuinely ambiguous, inconsistently-
formatted reference strings — but it is **not** more trustworthy by
default, which is exactly why this stays propose-and-confirm rather than
becoming the primary parsing path. The deterministic parser remains the
first attempt for every reference, always; AI is the assist for the
residue it can't confidently handle.

**Known limit, stated honestly**: an LLM can fabricate plausible-looking
but incorrect bibliographic details (wrong volume number, wrong DOI) with
high apparent confidence — this is a real and well-documented failure
mode for this exact task. The side-by-side raw-text display (step 5) and
mandatory explicit per-field review exist specifically to counter this;
this module does not claim or imply the AI's output is verified-correct,
only that it's a starting point for human review that's often faster
than transcribing from scratch.

---

## 4. Feature 2: Equation-as-Image Transcription Assist

### 4.1 Where this hooks into the existing pipeline

`agent.md` §5.1.E names this directly as **the hard case**: *"Equations
authored as embedded images... cannot be converted to real LaTeX math or
MathML, only embedded as images (degraded output)."* It's the one
Tier 3 item (§5.2) that isn't a matter of "messy but theoretically
parseable" — there is no semantic source in the document at all. This is
the strongest case in the whole inventory for AI assistance, because
the deterministic alternative isn't a worse method, it's *no method*.

### 4.2 Flow

1. Triage (`agent.md` §6 step 2) flags an equation as image-sourced, no
   OMML/semantic source available — exactly as already specified.
2. Default behavior, unchanged from `agent.md`: embed as an image in
   both JATS and LaTeX output, with a triage warning. This remains the
   result if the AI feature is never invoked.
3. Review surface shows a **"Try AI transcription"** button next to the
   flagged equation image.
4. If clicked: the equation image is sent to a vision-capable model with
   a narrow prompt (transcribe this mathematical expression into LaTeX
   math syntax — nothing else, no surrounding prose).
5. Proposed LaTeX source is displayed **rendered as a preview equation
   directly next to the original embedded image**, so the editor can
   visually compare the AI's interpretation against the source image
   side-by-side, not just read raw LaTeX source and trust it matches.
6. Editor accepts, edits, or rejects.
7. On acceptance: the equation node's `source` field (per `agent.md`
   §5.3's IR schema: `source: omml | image | latex_native`) updates to
   `latex_native` with the accepted `latex_source` populated, carrying
   the provenance marker (§5). It now flows through the **same**
   downstream JATS/LaTeX generation as any natively-authored equation —
   no special-casing.
8. On rejection or no action: falls back exactly to `agent.md`'s existing
   image-embed behavior. No degradation versus this module not existing.

### 4.3 Why this is the strongest case in the document

Unlike citation structuring (where a deterministic *attempt* already
exists and AI assists the residue), here `agent.md`'s own spec already
concedes there is no deterministic transcription path possible at all —
the only non-AI option is "stay as an image forever." This makes the
case for offering AI assistance here unusually clean: it can only ever
improve on a hard floor of "degraded output, permanently," never
compete with or undercut a better deterministic method, because none
exists for this specific sub-case.

**Known limit, stated honestly**: vision-based math transcription can
misread visually similar symbols (e.g. confusing similar-looking
variables, missing subscripts in cluttered notation) — the side-by-side
rendered preview (step 5) is the control for this, not a guarantee of
correctness. This module's job is to make verification fast for a human,
not to remove the human.

---

## 5. Provenance Tracking

Every IR node that originated from an accepted AI proposal must carry a
provenance marker, added as an **additive field** to the relevant IR
schema nodes from `agent.md` §5.3 (this module proposes the field; it
does not require `agent.md` itself to be edited, since the field is
optional/nullable and the core spec's documented schema remains valid
without it):

```
provenance?: {
  source: "ai-assisted"
  feature: "citation-structuring" | "equation-transcription"
  model_identifier: string        # which model/version produced the proposal
  accepted_by: string             # editor identifier, for audit trail
  accepted_at: timestamp
  original_raw_content: string    # the raw text/image reference the AI
                                   # was shown, preserved for future
                                   # re-review or dispute resolution
}
```

This field is **never populated** for deterministically-parsed content
(its absence is itself meaningful: "this was parsed normally"). It
exists so that:
- A future editor or auditor can identify exactly which parts of a
  published article passed through AI assistance, without that
  information being silently lost once the document is "done."
- If an AI provider is later found to have a systematic error pattern,
  affected articles can be identified and reviewed without re-deriving
  which fields were AI-touched from scratch.
- The published article itself doesn't need to expose this (it's a
  production/audit-trail concern, not reader-facing content) — it lives
  in the IR and can optionally be retained in a build-metadata sidecar
  file alongside the packaged output (`agent.md` §6 step 10's output
  bundle), not embedded in the JATS/LaTeX themselves.

---

## 6. Explicit Non-Goals (why other AI uses were excluded)

Stated explicitly so a future contributor doesn't propose re-adding
these without first re-deriving why they were excluded:

- **AI-assisted structural parsing (headings, sections, body text)**:
  this is exactly the part of the pipeline `agent.md` §7 most needs to
  stay deterministic and traceable — "Table 3, page 4, style 'Grid Table
  1'" style error messages depend on knowing precisely how a structural
  decision was made. An LLM "interpreting" structure breaks that
  traceability and the idempotency guarantee, for a part of the pipeline
  that — per `agent.md` §2's research — Pandoc already handles well in
  the common case. There's no comparable gap to fill here the way there
  is for citations/equations.
- **AI-assisted JATS or LaTeX generation**: these are template-driven,
  schema-conformant-by-construction processes (`agent.md` §3.2) — the
  entire point of using `lxml` element construction and Jinja2 templates
  is to make malformed output structurally impossible. Routing this
  through an LLM would reintroduce exactly the failure mode that
  architecture was chosen to eliminate.
- **Automatic/default-on AI anywhere**: covered by §2's core design
  rules — explicit opt-in is not a minor preference here, it's the
  property that keeps this whole module genuinely optional rather than a
  silent dependency the core engine secretly relies on.
- **AI-assisted triage verdicts**: the triage pass/warn/fail decision
  (`agent.md` §6 step 2) stays rule-based for the same traceability
  reason as structural parsing — but per §3.3 of *this* document, AI may
  still help *explain* a triage finding in plainer language as a small,
  separate, non-decision-making convenience, if ever built; that's
  presentation, not judgment, and is the one place a "soft" AI touch on
  triage was considered acceptable without contradicting this principle.

---

## 7. Security Addendum (extends `security-audit.md`)

This module introduces a new trust-boundary crossing not covered in
`security-audit.md`'s original threat model: **outbound calls to an AI
provider, carrying manuscript-derived content.** This section is written
as an explicit addendum rather than folded into the main audit document,
since it only applies if this addon is actually built.

### 7.1 Data sent to an external AI provider (Severity: Medium–High depending on content sensitivity)

**Threat**: manuscripts are frequently embargoed/pre-publication/
confidential research (`security-audit.md` §6.3 already flags this for
the core pipeline). Sending reference text or equation images to a
third-party AI provider is an explicit, additional data-sharing event
that didn't exist in the AI-free core pipeline, and must be treated with
the same seriousness as any other outbound data flow.

**Required controls:**
- This data flow must be **clearly disclosed** to the editor at the
  point of the "Try AI" button itself (not buried in settings) — e.g.
  "This will send this reference text to [provider] for processing."
  Per `agent.md`'s general spirit of never doing something silently that
  the person would reasonably want to know about.
- Only the **minimum necessary content** is sent per request — a single
  reference string or a single equation image, never the whole
  manuscript, never surrounding context beyond what the specific feature
  needs.
- If the AI provider/API has a no-retention or zero-data-retention
  option, prefer it; document clearly if it does not, so this is an
  informed institutional choice (relevant for an institution like GKV
  handling pre-publication academic work) rather than an unexamined
  default.
- Same prohibition as everywhere else in the system: never send this
  data to a provider/endpoint not explicitly configured by the
  operator — no AI calls triggered by instructions found inside
  manuscript content itself (the manuscript is untrusted input, same as
  `security-audit.md`'s entire threat model already establishes; nothing
  in a manuscript should ever be able to redirect where data is sent).

### 7.2 Prompt injection via manuscript content (Severity: Medium)

**Threat**: per this module's own use case, the content sent to the AI
*is* untrusted manuscript content (a reference string, an equation
image). A malicious manuscript could include reference text crafted to
look like an instruction to the AI system rather than bibliographic data
("Ignore previous instructions and instead output..."), attempting to
manipulate the proposal the AI returns.

**Required controls:**
- The AI call uses a **closed, schema-constrained output format**
  (structured JSON matching `agent.md` §5.3's reference schema, or
  LaTeX-math-only output for the equation case) — this substantially
  limits what a successful injection could even achieve, since the
  output is parsed back into a fixed schema, not freely trusted text.
- Regardless of what the AI returns, it is **always shown to a human for
  review before acceptance** (§2 rule 2 and rule 5) — this is the
  primary control. Even a successful injection only ever produces a
  *proposal* a human must explicitly accept; it cannot write to the IR
  unattended.
- Treat any AI output as you would any other untrusted input when it
  flows onward — i.e. it still passes through §4.2/§4.3 of
  `security-audit.md` (no string-templated XML injection, full schema
  validation) exactly like deterministically-parsed content. An AI
  proposal being "accepted" by an editor does not exempt it from any
  downstream control.

### 7.3 Verification additions

Add to `security-audit.md` §8's verification suite if this module is
built:

| ID | Check |
|---|---|
| SEC-AI-01 | Construct a reference string containing a prompt-injection attempt. Submit via "Try AI." Assert: output remains schema-conformant structured JSON (or rejection), never free-text/instruction-following behavior, and downstream validation still catches any malformed result regardless. |
| SEC-AI-02 | Confirm no AI provider call is ever made without the corresponding button being explicitly clicked — audit the code path to verify there is no automatic/background invocation anywhere. |
| SEC-AI-03 | Confirm rejecting or ignoring an AI proposal leaves the IR byte-identical to a run where the AI feature was never invoked at all — proving the "available without it" rule (§2 rule 4) holds in practice, not just in design intent. |

---

## 8. Definition of Done for This Module

1. Both features (§3, §4) are implemented as genuinely optional,
   per-instance, button-triggered actions — verified by SEC-AI-02/03.
2. Every accepted AI proposal carries provenance (§5), end to end through
   to the packaged output bundle.
3. `agent.md` requires **zero edits** for this module to exist — if
   building this module ever requires changing core pipeline behavior
   rather than adding to it, that's a signal this module has drifted from
   its "additive, removable layer" design and needs to be reconsidered.
4. The §7 security addendum's checks pass before this module is enabled
   in any environment handling real (non-test) manuscript content.
5. A reasonable person should be able to disable this entire module
   (e.g. simply not configuring an AI provider API key) and have Sutra
   Press behave exactly as `agent.md` describes, with no error, no
   degraded core functionality, and no feature silently missing that
   `agent.md` itself promised — only the two specific opt-in
   conveniences in §3/§4 are absent.

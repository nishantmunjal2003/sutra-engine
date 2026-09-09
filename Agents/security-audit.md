# security-audit.md — Sutra Press: Security Audit

## 0. Purpose & Relationship to agent.md / testing-agent.md

This document specifies a security-auditing agent's mandate for **Sutra
Press**. Like `testing-agent.md`, it is a separate mandate from the build
agent: the build agent makes the pipeline work; this agent's job is to
assume **every input is adversarial** and verify the system survives that
assumption — not just survives malformed-but-honest input (that's
`testing-agent.md`'s job), but survives input deliberately crafted to
attack the system.

**This is not a generic security checklist.** Every section below is
derived from Sutra Press's *actual* architecture in `agent.md`: it parses
untrusted ZIP/XML containers (DOCX), shells out to external binaries
(Pandoc, Tectonic/LaTeX), generates XML that other systems (OJS, PMC,
Crossref) will trust and ingest, and (per `agent.md` §10, Phase 1.5+) will
eventually accept uploads over a web interface. Each threat below is tied
to the specific pipeline step in `agent.md` §6 where it applies.

**Severity scale used throughout:**
- **Critical** — remote code execution, arbitrary file read/write,
  full server compromise
- **High** — denial of service, significant resource exhaustion,
  sensitive data disclosure short of full compromise
- **Medium** — information leakage, weaker isolation than ideal,
  defense-in-depth gaps
- **Low** — hygiene issues, best-practice gaps with limited direct impact

---

## 1. Threat Model

### 1.1 Trust boundary

```
┌─────────────────────────┐
│   UNTRUSTED              │   Anything inside this manuscript file was
│   ┌─────────────────┐    │   authored by someone Sutra Press has no
│   │  input.docx /    │    │   reason to trust — including legitimate
│   │  input.tex       │    │   authors whose Word install or template
│   └─────────────────┘    │   has been compromised, not just deliberate
└─────────────────────────┘   attackers.
            │
            ▼  (agent.md §6 steps 1–4: ingest, triage, parse, IR)
┌─────────────────────────┐
│   TRUST BOUNDARY          │   Crossing this line is where validation,
│   (parsing/sandboxing      │   sanitization, and isolation must happen.
│    happens here)           │   Nothing past this line should still be
└─────────────────────────┘   "raw" attacker-controlled bytes.
            │
            ▼  (agent.md §6 steps 6–9: JATS gen, validate, LaTeX gen, compile)
┌─────────────────────────┐
│   SEMI-TRUSTED OUTPUT      │   JATS/PDF generated from the IR. Lower risk
│   (still requires care:    │   than raw input, but author-supplied text
│    embedded text/refs      │   (titles, captions, table cells) still flows
│    originated untrusted)   │   through here and can carry injection
└─────────────────────────┘   payloads relevant to the *output* format
            │                  (e.g. LaTeX command injection in §3).
            ▼
┌─────────────────────────┐
│   DOWNSTREAM CONSUMERS     │   OJS, PMC, Crossref, DOAJ, and the editor's
│   (trust Sutra Press's     │   own machine when they open the PDF/XML.
│    output as "clean")      │   Sutra Press's output becomes *their* input
└─────────────────────────┘   trust boundary — failures here propagate.
```

### 1.2 Attacker profiles to design against

1. **Malicious author**: submits a manuscript specifically crafted to
   attack the conversion server (RCE, DoS, data exfiltration) — the
   primary profile for most of this document.
2. **Compromised-but-well-intentioned author**: their manuscript carries
   a payload neither they nor the editor are aware of (e.g. malware
   embedded via a compromised Word template, a malicious macro, or an
   infected plugin that touched the file before submission). Indistinguishable
   from profile 1 at parse time — defenses must cover both.
3. **Malicious downstream consumer of output**: less central to Phase 1
   (no multi-tenant web service yet per `agent.md` §10), but worth keeping
   in mind for §10's later OJS-plugin integration, where Sutra Press
   becomes a network-reachable service other systems call into.
4. **Insider/operator error**: not malicious, but a misconfiguration
   (e.g. shell-escape accidentally left on, validation accidentally
   skipped under deadline pressure) that has the same impact as an
   attack. Several controls below exist specifically to make this class
   of mistake structurally hard to make, not just documented against.

---

## 2. DOCX Ingestion: ZIP/OOXML Threats

*Applies to `agent.md` §6 step 1 (ingest) and step 3 (Parse to Pandoc AST).
This is the highest-priority section in this document — it's the very
first thing that happens to untrusted bytes.*

### 2.1 Zip bomb / decompression bomb (Severity: High)

**Threat**: DOCX is a ZIP container. A crafted `.docx` can use overlapping
or nested ZIP entries to expand from a few KB to gigabytes/terabytes on
extraction, exhausting memory or disk and crashing or hanging the
conversion service — a textbook decompression-bomb attack applicable to
any ZIP-based format.

**Required controls:**
- Before full extraction, inspect the ZIP central directory and **reject
  any file where the declared uncompressed size exceeds a hard ceiling**
  (e.g. 200MB — set the actual number based on the largest legitimate
  manuscript expected, with margin, not an arbitrary guess).
- Reject any individual entry within the ZIP whose **compression ratio**
  exceeds a sane threshold (a few hundred:1 is already suspicious for
  real DOCX content, which is mostly already-compressed XML/images).
- Enforce a **maximum file count** within the archive (a legitimate DOCX
  has a bounded, predictable number of internal parts — dozens, not
  thousands).
- Perform extraction with a **hard wall-clock and memory budget**
  (process-level `ulimit`/cgroup constraints, not just application-level
  checks, since a sufficiently bad bomb can OOM-kill before application
  code gets a chance to check anything).
- These checks happen **before** handing the file to Pandoc or any
  full-document parser — fail fast on the cheap structural check, don't
  rely on the expensive parser to also be the safety net.

### 2.2 Zip slip / path traversal (Severity: Critical)

**Threat**: a malicious ZIP entry filename like
`../../../../etc/cron.d/malicious` can, if extracted naively, write files
**outside** the intended extraction directory — classic "Zip Slip,"
applicable to DOCX exactly as to any ZIP format.

**Required controls:**
- Every extracted entry path must be **canonicalized and verified to
  remain within the intended extraction directory** before any write
  occurs — reject (don't silently rename) any entry whose resolved path
  escapes the sandbox.
- Never trust a library's "should be safe" default without verifying —
  confirm explicitly which extraction library/method is used in the
  implementation and that it performs this check, rather than assuming.
- Extraction must happen inside an **isolated, ephemeral working
  directory per conversion job** (not a shared/reused directory), so even
  a successful traversal has minimal blast radius and leaves no residue
  for the next job.

### 2.3 XXE — XML External Entity injection (Severity: Critical)

**Threat**: every part of a DOCX (`document.xml`, `[Content_Types].xml`,
relationship files, etc.) is itself XML. If any parser touching these
files (or later, JATS files during §6 step 7 validation) resolves
external entities, an attacker can achieve **arbitrary local file read**,
**server-side request forgery** (the server making outbound requests to
attacker-chosen internal/external targets), or **denial of service** via
entity-expansion ("billion laughs") attacks — all without needing any
other vulnerability, just a malicious `<!DOCTYPE>`/`<!ENTITY>` block
inside one of the DOCX's internal XML parts.

**This applies at two separate points in the pipeline, both must be
covered:**
1. Any direct XML parsing of DOCX-internal parts (if `python-docx` or
   manual XML access is used per `agent.md` §3.2's fallback path)
2. **JATS schema validation itself** (`agent.md` §6 step 7) — the
   validator parses the *generated* JATS XML, and although Sutra Press
   generates that XML itself, defense-in-depth says the validator should
   still be configured safely, since a bug elsewhere in the pipeline that
   allows attacker content to smuggle a DOCTYPE into generated output
   should not then ALSO get to exploit an unhardened validator.

**Required controls:**
- Every `lxml.etree` parser instance anywhere in the codebase must be
  explicitly constructed with `resolve_entities=False` and
  `no_network=True` (do not rely on library defaults, which have
  historically been unsafe and have shifted across versions — make the
  safe configuration explicit and grep-able in the codebase, e.g. a
  single shared `safe_xml_parser()` factory function used everywhere,
  so there is exactly one place to audit, not N call sites that can each
  independently get it wrong).
- DOCTYPE declarations should be **rejected outright** for any XML this
  pipeline parses — legitimate DOCX/JATS content never needs one.
- Set explicit entity-expansion depth/count limits as defense-in-depth
  against billion-laughs-style attacks even with external entities
  disabled.
- This control must be **unit-tested directly** (see `testing-agent.md`
  for the testing mandate — but note this specific test belongs in this
  document's own verification suite too, §8, since it's a security
  property, not just a correctness property): feed a known XXE payload
  DOCX/XML fixture through the parser and assert it is rejected/neutralized,
  not silently "successfully" parsed with the entity unresolved-but-present.

### 2.4 Malicious embedded objects (Severity: High)

**Threat**: DOCX can embed OLE objects, macros (VBA), linked external
resources (e.g. a field code that fetches a remote template or image),
or other active content. Even though Sutra Press only needs to *extract
text/structure*, naive use of certain libraries or external tools (e.g.
if anything in the pipeline ever shells out to a real Office/LibreOffice
instance for conversion) could trigger execution of embedded active
content.

**Required controls:**
- Sutra Press's chosen toolchain (Pandoc, `python-docx`) does **not**
  execute macros or active content by design — confirm this remains true
  for any tool substitution/addition during implementation, and document
  the confirmation, since this is an easy property to silently lose if a
  future contributor swaps in a different DOCX-handling library or adds
  a LibreOffice-headless fallback without revisiting this.
- If any "convert via real Office/LibreOffice" fallback is ever
  considered (it is **not** part of the `agent.md` recommended stack —
  flag any future proposal to add one for mandatory security review
  before adoption), it must run macro execution fully disabled and in
  full process isolation.
- Linked (not embedded) external resources referenced in DOCX field
  codes must never be auto-fetched by the pipeline (this would be an SSRF
  vector) — extraction must only ever read what's physically inside the
  archive, never follow external references.

### 2.5 Malformed/adversarial OOXML structure (Severity: Medium)

**Threat**: deliberately malformed internal XML (missing required parts,
circular relationship references, deeply nested elements) crafted to
crash or hang the parser rather than achieve direct compromise — a
robustness/DoS concern distinct from the zip-bomb case in §2.1.

**Required controls:**
- All parsing happens inside the per-job timeout/resource envelope from
  §2.1 — a hang here is caught by the same wall-clock budget, not a
  separate mechanism.
- Parser exceptions are caught and routed to the triage-report failure
  path (`agent.md` §6 step 2 / §7), never allowed to propagate as an
  unhandled exception that could leak a stack trace (potential
  information disclosure about server internals — paths, library
  versions) to whatever surface eventually serves results (relevant once
  `agent.md` §10's web UI exists).

---

## 3. LaTeX Generation & Compilation Threats

*Applies to `agent.md` §6 steps 8–9 (Generate LaTeX, Compile LaTeX → PDF).
This is the second-highest-priority section — LaTeX is a programming
language, and Sutra Press's generated `.tex` files embed untrusted
author-supplied text (titles, abstracts, captions, table cells, reference
fields) directly into that programming language's source.*

### 3.1 LaTeX/TeX injection via unescaped author content (Severity: Critical)

**Threat**: this is the **single most important control in this entire
document.** Author-supplied text (a paper title, an author name, a table
cell, a reference's journal name) is inserted into Jinja2-generated LaTeX
source per `agent.md` §3.2. If that text is inserted **without proper
LaTeX-escaping**, an attacker can craft manuscript content that, once
substituted into the `.tex` template, becomes executable LaTeX/TeX
commands rather than inert text — potentially including `\write18`
(shell-escape) invocations enabling **full remote code execution** during
the compile step (§6 step 9), confirmed as a real, exploited
vulnerability class in comparable systems (a documented CVE in another
"compile user-submitted text into LaTeX" service used exactly this path
for RCE).

**Example of the failure mode** (illustrative, not exhaustive): an author
sets their "affiliation" field to text containing a closing brace
sequence that escapes the intended `\affiliation{...}` argument, followed
by raw LaTeX commands — if the template does naive string substitution
instead of proper escaping, those commands execute as part of normal
compilation, not as an edge case requiring `\write18` specifically (though
`\write18`-based shell escape is the most severe realization of this class).

**Required controls:**
- **Every single piece of author-supplied text** that lands in generated
  LaTeX — titles, names, affiliations, abstract text, all body text,
  table cell contents, figure captions, every reference field — must pass
  through a single, shared, well-tested **LaTeX-escaping function** before
  Jinja2 substitution. This is not optional per-field; it is universal
  and the function must escape (at minimum) `\ { } $ & # ^ _ ~ %` and
  reject or neutralize raw `\input`, `\include`, `\write`, `\immediate`,
  and any shell-escape-adjacent primitives appearing in **content text**
  (as opposed to the template's own control structure, which is
  developer-authored and trusted).
- Use Jinja2's `\BLOCK{}`/`\VAR{}` custom delimiters (already specified
  in `agent.md` §3.2) **combined with** an explicit autoescape filter
  registered for the LaTeX-safe escaping function — do not rely on
  delimiter choice alone to provide safety; delimiter choice prevents
  template *syntax* collisions, the escaping function prevents *content*
  injection, and both are required, independently.
- **Compile with `--no-shell-escape` (or equivalent) unconditionally.**
  Per the LuaTeX CVE-2023-32700 precedent, shell-escape-disabled is
  necessary but not provably sufficient against every historical TeX
  engine vulnerability — defense-in-depth (§3.2 below) is required in
  addition to this flag, not instead of it.
- This control must be tested with actual injection-attempt fixtures
  (malicious titles/captions/table cells containing LaTeX special
  characters and command sequences) as part of this document's
  verification suite (§8) — not assumed correct because "we escape it,"
  but proven correct because a specific adversarial fixture fails to
  achieve injection.

### 3.2 Sandboxed compilation (defense-in-depth) (Severity: Critical)

**Threat**: even with shell-escape disabled and content properly escaped,
historical TeX-engine vulnerabilities (e.g. the LuaTeX CVE that allowed
command execution *regardless* of shell-escape settings) mean compilation
should never be trusted to be safe by configuration flags alone.

**Required controls:**
- LaTeX compilation (Tectonic, per `agent.md` §3.2) runs in an **isolated,
  ephemeral, network-disabled sandbox per job** — a container or
  equivalent OS-level isolation that is destroyed after each compile, with
  no persistent state, no network egress, and minimal filesystem access
  (read access only to the job's own generated `.tex`/assets, write access
  only to the job's own output directory).
- Resource limits (CPU time, memory, process count, wall-clock timeout)
  enforced at the sandbox/container level, not just requested politely
  via Tectonic's own flags — the same principle as §2.1's zip-bomb
  defense: never rely solely on the tool being well-behaved.
- Run the compilation process as a **non-privileged, dedicated user**
  with no meaningful permissions beyond the job sandbox, so even a full
  engine-level exploit has nothing valuable to reach.
- This mirrors the precedent already established by serious LaTeX
  compilation-as-a-service providers, who isolate every compile in an
  ephemeral container specifically because shell-escape and engine-level
  flags are not considered sufficient alone.

### 3.3 Resource exhaustion via pathological LaTeX (Severity: Medium)

**Threat**: even non-malicious-looking content can cause runaway
compilation (deeply nested macros, extremely long lines, pathological
table/equation structures) that hangs or consumes excessive memory —
distinct from a deliberate exploit attempt, but with the same operational
impact.

**Required controls:**
- Covered by the same per-job wall-clock/memory/CPU budget from §3.2 —
  no separate mechanism needed, but explicitly confirm this case is
  covered by testing it (see `testing-agent.md` TC-X-21 through TC-X-24
  for the correctness-focused version of this; this document's
  verification suite, §8, adds the adversarial version specifically
  targeting compile-time blowup).

### 3.4 Generated LaTeX include/input path safety (Severity: High)

**Threat**: the generated `.tex` file references external asset files
(figures, images) by path per `agent.md` §6 step 8. If filenames derived
from attacker-controlled content (e.g. an author-supplied figure caption
used to construct a filename) aren't sanitized, this could enable path
traversal in `\includegraphics{}` paths, potentially reading files
outside the intended assets directory during compilation.

**Required controls:**
- Asset filenames are **never derived from attacker-controlled text**
  (captions, original filenames from the DOCX). Use generated,
  collision-free identifiers (e.g. a sequence number or content hash) per
  `agent.md` testing-agent.md TC-C-11's naming-collision concern — which
  turns out to double as a security control here, not just a correctness
  one.
- All `\includegraphics{}` (and equivalent) paths in generated LaTeX are
  relative to the job's sandboxed assets directory only, never absolute,
  never containing `..` segments, verified by the same canonicalization
  check described in §2.2.

---

## 4. JATS XML Generation & Validation Threats

*Applies to `agent.md` §6 steps 6–7.*

### 4.1 XXE in the validation step (Severity: Critical — cross-reference to §2.3)

Already covered in §2.3 as a single shared control (one safe-parser
factory used everywhere XML is parsed in this codebase, including here).
Listed again here only to make explicit that JATS validation is **not**
exempt just because the XML being validated was generated by Sutra Press
itself — defense-in-depth assumes any individual pipeline stage could be
compromised or buggy, and later stages should not assume earlier stages
were perfectly safe.

### 4.2 XML injection via unescaped author content (Severity: High)

**Threat**: analogous to §3.1 but for XML rather than LaTeX. If JATS
generation uses string concatenation/templating instead of a real XML
library's element-construction API, attacker-controlled text containing
`<`, `>`, `&`, or crafted CDATA/comment boundary sequences could break out
of the intended text-node context and inject spurious elements/attributes
into the generated JATS — corrupting the document structure, and in the
worst case, smuggling content that downstream consumers (OJS, PMC) parse
in unintended ways.

**Required controls:**
- `agent.md` §3.2 already mandates `lxml` element-construction (not
  string templating) for JATS generation — this is the correct control,
  and this audit's role is to **verify it's actually followed**
  end-to-end, since "we used lxml for the skeleton but still
  string-concatenated this one field" is a realistic regression to watch
  for in code review, not a hypothetical.
- Verification check: confirm there is no `f"<{tag}>{user_content}</{tag}>"`-
  style string construction anywhere in the JATS generation code path —
  every text node and attribute value must go through `lxml`'s `.text`,
  `.set()`, or equivalent APIs, which handle escaping correctly by
  construction.

### 4.3 Schema validation bypass (Severity: High)

**Threat**: per `agent.md` §6 step 7 and §7 (Failure Philosophy),
"conversion is not done until validation passes" is a **correctness**
requirement already in the spec — but it's also a security control: a
pipeline bug or a deliberately malformed edge case that produces
non-conformant JATS *and is allowed to ship anyway* could mean malformed
data reaches OJS/PMC/Crossref ingestion, some of which may have their own
parsing quirks/vulnerabilities that well-formed-and-conformant JATS is
specifically designed to avoid triggering.

**Required controls:**
- Validation failure must be a **hard process-exit-nonzero condition**,
  not a warning that a caller could ignore — verify the CLI's exit code
  contract explicitly (see this document's §8 verification suite).
- No "skip validation" flag should exist in production builds, even for
  debugging convenience — if one exists for development use, it must be
  impossible to invoke accidentally in any automated/CI/production
  invocation path (e.g. gated behind an explicit, loudly-named flag like
  `--i-understand-this-is-unsafe-skip-validation`, not a quiet `--fast`
  flag someone could reach for under deadline pressure without realizing
  the safety implication).

---

## 5. Dependency & Subprocess Threats

*Applies to `agent.md` §3.2's tool choices (Pandoc, Tectonic, lxml,
python-docx) and the general pattern of shelling out to external
binaries.*

### 5.1 Subprocess invocation safety (Severity: High)

**Threat**: any place the pipeline invokes Pandoc, Tectonic, or other
external tools via subprocess, if command construction involves string
interpolation of filenames/paths derived from user input, creates a
command-injection risk distinct from the LaTeX-content-injection risk in
§3.1 — this is about the *shell command itself* being manipulated, not
the document content.

**Required controls:**
- All subprocess invocations use **argument-list form** (e.g. Python's
  `subprocess.run([...])` with a list, never `shell=True` with a
  concatenated string) — this single rule eliminates the entire class of
  shell-metacharacter injection via filenames.
- File paths passed to subprocesses are always the pipeline's own
  generated, sanitized paths (per §2.2/§3.4's canonicalization), never
  raw attacker-supplied filenames, even when invoking external tools.

### 5.2 Dependency supply-chain hygiene (Severity: Medium)

**Threat**: Pandoc, Tectonic, lxml, python-docx, and their transitive
dependencies are all attack surface. A compromised or vulnerable version
of any of them is a real risk, independent of how carefully Sutra Press's
own code is written.

**Required controls:**
- Pin exact versions of all dependencies (no unpinned `>=` ranges in
  production builds); track and update on a defined cadence, not
  ad hoc.
- Run dependency vulnerability scanning (e.g. `pip-audit` or equivalent)
  as a CI gate, mirroring the blocking-CI pattern `testing-agent.md`
  already establishes for schema conformance — security scanning gets
  the same non-negotiable treatment.
- Tectonic's own package-fetching behavior (it can download missing
  LaTeX packages on demand) must be **pinned to a fixed, vetted bundle**
  or run with network access disabled entirely (consistent with §3.2's
  no-network-egress sandbox requirement) — an on-demand package fetch
  during compilation of untrusted-derived content is itself a network
  egress point that needs to not exist in production, not just be
  "probably fine."

### 5.3 Pandoc's own attack surface (Severity: Medium)

**Threat**: Pandoc itself is a large, complex parser for many formats; it
has had its own historical vulnerabilities. Treating it as a trusted black
box because it's "the standard tool" is the same category of mistake as
trusting any other dependency uncritically.

**Required controls:**
- Pandoc invocation runs inside the same sandboxed, resource-limited,
  network-disabled job environment as LaTeX compilation (§3.2) — not a
  separate, less-isolated step just because it happens earlier in the
  pipeline.
- Keep Pandoc version current with upstream security patches as part of
  the §5.2 dependency cadence.

---

## 6. Output & Downstream Trust Threats

*Applies to `agent.md` §6 step 10 (packaging) and the broader question of
what Sutra Press hands to OJS/PMC/Crossref/the editor.*

### 6.1 Generated PDF as an attack vector against the editor (Severity: Medium)

**Threat**: the compiled PDF itself, opened by an editor on their own
machine, is a potential vector if anything in the LaTeX→PDF path could be
manipulated to embed malicious PDF content (e.g. embedded JavaScript,
malformed structures targeting PDF reader vulnerabilities) — distinct
from the compilation-time RCE risk in §3, this is about the *artifact*
being unsafe to open, not the *compilation process* being unsafe to run.

**Required controls:**
- The LaTeX templates Sutra Press controls (per `agent.md` §3.2/§4.3)
  never intentionally embed JavaScript or active content in output PDFs
  — confirm no template package introduces this capability inadvertently
  (some LaTeX packages can embed PDF JavaScript for interactive forms;
  none should be in Sutra Press's dependency set, and this should be an
  explicit, checked exclusion, not an assumption).
- Output PDFs should be validated as well-formed (a basic
  parseability/structure check, distinct from `testing-agent.md`'s
  correctness-focused PDF smoke test) before being packaged as a
  deliverable.

### 6.2 Triage/validation reports as an injection vector (Severity: Low)

**Threat**: `agent.md` §6 steps 2/7/10 specify human-readable triage and
validation reports (Markdown) that **quote back** problematic content
from the source manuscript (e.g. "Table 3, style 'Grid Table 1'..." per
§7's worked example). If these reports are ever rendered in a web UI
(per `agent.md` §10's future Phase 2 editor-facing web UI) without proper
escaping, attacker-controlled manuscript content quoted into the report
could become a stored XSS vector against whoever views the report in a
browser.

**Required controls:**
- Flagged here **proactively** for Phase 2, since `agent.md` §10 already
  anticipates a web UI — when that UI is built, any manuscript-derived
  content surfaced in triage/validation reports must be HTML-escaped at
  render time, not assumed safe because it "is just an error message."
  Not a Phase 1 blocker (no web UI exists yet) but recorded here so it
  isn't rediscovered the hard way during Phase 2 implementation.

### 6.3 Per-job isolation and data residue (Severity: Medium)

**Threat**: manuscripts may contain confidential/embargoed research
(common in academic publishing — pre-publication work, sometimes
patent-sensitive). If job working directories, temp files, or extracted
assets from one conversion job are not fully cleaned up, or worse, are
accessible to other concurrent jobs, this is a confidentiality failure
independent of any "attack" — just inadequate isolation.

**Required controls:**
- Every conversion job runs in its own ephemeral working directory
  (already required for the security reasons in §2.2/§3.2; this section
  notes it's *also* required for confidentiality reasons, reinforcing
  rather than duplicating the requirement).
- Working directories and all intermediate artifacts are deleted
  immediately after job completion (success or failure) — not deferred
  to manual cleanup or a periodic sweep, since a periodic sweep leaves a
  window where one job's confidential content is readable by a
  differently-privileged process.
- Logs must not capture full manuscript content (e.g. don't log entire
  extracted text on error — log structural metadata about the error,
  per the traceability requirement already in `agent.md` §7, which is
  about *locating* problems, not about dumping full content into
  potentially-less-protected log storage).

---

## 7. Input Validation Boundary Summary

A consolidated checklist of "never trust X without validating it first,"
collecting the specific instances from §2–§6 in one place for quick
reference during code review:

| Input | Never trust it for... | Validated by |
|---|---|---|
| Uploaded DOCX file size | Memory/disk budget | §2.1 pre-extraction size check |
| ZIP entry filenames | Filesystem write paths | §2.2 canonicalization |
| DOCX-internal XML | Entity resolution | §2.3 safe parser factory |
| DOCX embedded objects | Code execution | §2.4 no macro/active-content execution |
| Author text → LaTeX | LaTeX command injection | §3.1 mandatory escaping function |
| Author text → asset filenames | Path traversal | §3.4 generated-identifier-only naming |
| Author text → JATS XML | XML injection | §4.2 lxml element API only, no string templating |
| Any filename → subprocess args | Shell injection | §5.1 argument-list subprocess calls |
| Generated JATS | Schema conformance | §4.3 hard-blocking validation, no bypass flag |

---

## 8. Verification Suite for This Document

Mirroring `testing-agent.md`'s structure: this document is not complete
until these checks exist and pass, not just until the controls above are
described in prose.

| ID | Check |
|---|---|
| SEC-01 | Feed a crafted zip-bomb-shaped `.docx` (high compression ratio, oversized declared content). Assert: rejected before full extraction, within the resource budget, with a clear error — not a hang, not an OOM crash. |
| SEC-02 | Feed a `.docx` containing a ZIP entry with a path-traversal filename (`../../`-style). Assert: rejected, no file written outside the job sandbox. |
| SEC-03 | Feed a `.docx` (or directly, a crafted internal XML part) containing a classic XXE payload (external entity referencing a local file). Assert: parsing fails safely or the entity is not resolved — confirm via a sentinel file the payload targets, asserting its contents never appear anywhere in output or logs. |
| SEC-04 | Same as SEC-03, targeted specifically at the JATS validation step (§2.3/§4.1) using a separately-crafted malicious XML fed directly to the validator, bypassing DOCX parsing — confirms the validator's own parser config is safe independent of upstream protections. |
| SEC-05 | Construct a manuscript with a title/caption/table-cell/reference-field containing LaTeX special characters and command sequences designed to break out of the intended template argument (per §3.1's failure-mode example). Assert: compiles without error, AND the resulting PDF contains the literal text (properly escaped), not executed commands, AND no shell-escape-requiring construct ever reaches the compiler. |
| SEC-06 | Attempt to compile a deliberately malicious `.tex` fixture (test-only, simulating what a pipeline bug *might* produce) containing an explicit `\write18` shell command, with the production compile invocation (flags + sandbox). Assert: the shell command does not execute (verify via a sentinel side-effect the command would cause, e.g. a file it would create, asserting it's absent) — this is a test of the sandbox (§3.2) as the defense-in-depth backstop, independent of whether the escaping in SEC-05 is working. |
| SEC-07 | Run a compile job and, **from inside the sandbox**, attempt to reach the network (e.g. resolve a DNS name or open a socket) and attempt to read a file outside the job directory. Assert: both fail, proving sandbox isolation directly rather than inferring it from configuration alone. |
| SEC-08 | Construct a manuscript with `<`, `>`, `&`, and CDATA-boundary-like sequences in title/abstract/body text. Assert: generated JATS remains well-formed XML (parses cleanly) and the resulting document, when inspected, shows the special characters as literal escaped text content, not as injected markup. |
| SEC-09 | Run the full pipeline with a deliberately broken/incomplete IR→JATS code path (test-only fault injection) that produces invalid JATS. Assert: the CLI exits non-zero, `validation-report.md` clearly states failure, and **no valid-looking JATS file is left in the output directory** that a careless downstream script might pick up anyway. |
| SEC-10 | Run two conversion jobs concurrently with manuscripts containing distinct sentinel content. Assert: job A's working directory/output is never visible to or readable by job B's process, and both working directories are fully removed after completion (inspect the filesystem post-run, don't just trust a cleanup function was called). |
| SEC-11 | Run `pip-audit` (or equivalent) against the pinned dependency set as a CI gate. Assert: zero known-critical vulnerabilities in the pinned versions; document and accept (with sign-off, not silently) any lower-severity findings that can't be immediately resolved. |
| SEC-12 | Confirm via static analysis / code review pass (can be automated with a simple grep-based check as a starting point) that no `subprocess` call anywhere in the codebase uses `shell=True` with interpolated input, and no LaTeX template substitution path bypasses the shared escaping function from §3.1. |

---

## 9. Definition of Done for This Audit

1. Every threat in §2–§6 has a corresponding implemented control, not
   just a documented intention.
2. Every check in §8 is implemented as an automated test and passes,
   with SEC-05 through SEC-07 (LaTeX injection + sandbox escape attempts)
   and SEC-03/SEC-04 (XXE) treated as **non-negotiable, always-blocking**
   — these protect against the two Critical-severity threat classes
   (RCE via LaTeX compilation, arbitrary file read via XXE) that
   represent full-compromise risk, not just degraded service.
3. The §7 input-validation boundary table is kept current — any new
   input source added to the pipeline (a new file format, a new
   metadata field sourced from the manuscript) gets a new row here
   before it ships, the same way `testing-agent.md` treats new content
   categories as requiring new test coverage before release.
4. This document is re-reviewed whenever `agent.md`'s architecture
   changes in a way that adds a new external tool, a new parsing step,
   or a new trust boundary (e.g. the Phase 2 web UI in `agent.md` §10
   will need a follow-up pass covering upload-endpoint-specific concerns
   — auth, rate limiting, CSRF — that don't exist yet in the CLI-only
   Phase 1 scope and are intentionally not invented speculatively here).
5. No control in this document is weakened or bypassed to hit a release
   deadline without an explicit, recorded, named sign-off — silent
   weakening under time pressure is the single most common way security
   controls actually fail in practice, and this document's existence is
   meant to make that failure mode visible rather than quiet.

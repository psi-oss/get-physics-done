# Artifact Review Architecture

Design note for upgrading GPD from a prompt-disciplined review system into an auditable artifact review and peer-review platform.

Date: 2026-03-10

Status: forward-looking design note, not an implementation contract. Paths or artifacts marked as "new", "suggested", or "should" below are proposals unless they already appear under **Current Strengths** or elsewhere in the current codebase.

## Goal

Make paper/report review, verification, and revision handling trustworthy enough for expert use by shifting the system's center of gravity from markdown prompts to machine-readable evidence.

## Current Strengths

- Strong review philosophy: independence, physics-first verification, explicit confidence handling.
- Good operational scaffolding: typed paper models, compiler fallbacks, convention lock, state persistence, local observability, and trace logging.
- Rich workflow intent: `write-paper`, `respond-to-referees`, `verify-phase`, `verify-work`, `gpd-referee`, `gpd-verifier`, `gpd-paper-writer`, `gpd-bibliographer`.
- Better-than-average prompt hygiene and wiring tests.

## Core Gaps

### 1. Evidence is mostly narrative

The system produces high-quality markdown reports, but most trust-critical facts are not stored as typed objects:

- manuscript claims
- evidence links
- verification runs
- citation resolution status
- figure audits
- revision issue status
- provenance for "verified" results

### 2. Verification semantics drift

The verification ontology is split across prompt files, templates, and executable helpers. Check IDs and meanings drift between:

- `src/gpd/core/verification_checks.py`
- `src/gpd/mcp/servers/verification_server.py`
- `src/gpd/agents/gpd-verifier.md`
- `src/gpd/specs/workflows/verify-phase.md`

### 3. Hard gates are often soft

Important publication checks currently degrade to warnings or partial flow continuation:

- missing TeX toolchain
- missing bibliography verification
- referee failures
- unresolved blocking review items
- static-only verification

### 4. Provenance is too shallow

Local observability and traces now provide a durable session/workflow trail under `.gpd/observability/` and `.gpd/traces/`, which is materially better than relying on transient runtime UI state alone. That still falls short of expert-grade provenance. `IntermediateResult.verified` is still a boolean, not a typed evidence record, and the event streams are not yet claim-aware, artifact-aware, or result-aware enough for expert audit.

### 5. Review plurality is missing

The current referee is strong, but it is still one reviewer voice. There is no structured dissent, adjudication, or specialist panel.

## Recommended Architecture

### A. Canonical Verification Spec

Create one machine-readable verification spec and generate all prompt tables and helper registries from it.

Should define:

- check id
- canonical name
- meaning
- required evidence
- applicable domains
- applicable profiles
- pass/fail states
- confidence downgrade rules
- executable oracle type

Primary touchpoints:

- `src/gpd/core/verification_checks.py`
- `src/gpd/mcp/servers/verification_server.py`
- `src/gpd/agents/gpd-verifier.md`
- `src/gpd/specs/workflows/verify-phase.md`
- `src/gpd/specs/references/verification/audits/verification-gap-analysis.md`

### B. Claim-Evidence Ledger

Introduce a first-class claim graph for papers, reports, and phase artifacts.

Suggested records:

- `ClaimRecord`
- `EvidenceRef`
- `VerificationRecord`
- `CitationRecord`
- `ArtifactRecord`
- `ReviewIssue`
- `RevisionResolution`

Minimum fields:

- stable id
- claim text
- artifact path
- source phase
- source result ids
- conventions in force
- supporting equations / figures / tables
- verification records
- benchmark references
- current confidence
- blocking status

Suggested outputs:

- `.gpd/review/CLAIMS.json`
- `.gpd/review/EVIDENCE.json`
- `.gpd/review/REVIEW-LEDGER.json`
- `paper/ARTIFACT-MANIFEST.json`

Primary touchpoints:

- `src/gpd/core/results.py`
- `src/gpd/core/state.py`
- `src/gpd/mcp/paper/models.py`
- `src/gpd/mcp/paper/compiler.py`

### C. Executable Oracle Layer

Upgrade the verification MCP surface from guidance-only helpers to actual evidence-producing tools.

Needed oracle capabilities:

- raw expression dimensional parsing
- symbolic limits
- numerical spot checks
- convergence fits
- sum-rule / conservation checks
- Kramers-Kronig checks
- topology / anomaly checks
- benchmark comparison with tolerances

Each oracle call should return:

- method
- inputs
- output
- tolerance
- pass/fail
- provenance hash
- linked claim ids

Primary touchpoints:

- `src/gpd/mcp/servers/verification_server.py`
- new `src/gpd/core/oracles/*.py`

### D. Review Integrity Mode

Add a fail-closed review mode for high-trust operations.

In review mode:

- schema drift blocks publication-grade review
- missing provenance lowers integrity status
- static-only verification cannot yield publication-ready status
- unresolved blocking review items halt packaging/submission

Primary touchpoints:

- `src/gpd/core/state.py`
- `src/gpd/mcp/servers/state_server.py`
- `src/gpd/specs/workflows/write-paper.md`
- `src/gpd/specs/workflows/respond-to-referees.md`
- `src/gpd/specs/workflows/arxiv-submission.md`

### E. Provenance Graph

Promote local observability events, traces, and result dependencies into a real provenance graph.

Add links from trace events to:

- result id
- claim id
- artifact path
- state before/after hash
- file checksum
- commit sha

Primary touchpoints:

- `src/gpd/core/observability.py`
- `src/gpd/core/trace.py`
- `src/gpd/core/results.py`
- possible future `src/gpd/mcp/servers/provenance_server.py`

### F. Review Panel and Adjudication

Replace the single-referee pass with a small structured panel:

- correctness reviewer
- numerics / reproducibility reviewer
- novelty / literature reviewer
- presentation reviewer
- adjudicator / meta-reviewer

Outputs should preserve both:

- consensus issues
- dissenting views

Primary touchpoints:

- `src/gpd/specs/workflows/write-paper.md`
- `src/gpd/agents/gpd-referee.md`
- new specialist reviewer prompts or modes

### G. Diff-Aware Revision Verification

After every manuscript revision:

- identify changed claims/equations/figures
- rerun targeted verification only on affected claims
- update resolution state for each `REF-*` issue
- feed evidence into next referee round

Primary touchpoints:

- `src/gpd/specs/workflows/respond-to-referees.md`
- `src/gpd/agents/gpd-paper-writer.md`
- `src/gpd/agents/gpd-referee.md`

## Review Artifacts To Standardize

### Paper/Report Review

- `ARTIFACT-MANIFEST.json`
- `CLAIMS.json`
- `EVIDENCE.json`
- `BIBLIOGRAPHY-AUDIT.json`
- `FIGURE-AUDIT.json`
- `QUALITY-SCORE.json`

### Referee Cycle

- `REFEREE-REPORT.md`
- `AUTHOR-RESPONSE.md`
- `REFEREE_RESPONSE.md`
- `REVIEW-LEDGER.json`

### Verification

- `VERIFICATION.md`
- `VERIFICATION.json`
- `ORACLE-RUNS.json`

## Hard Gates For Publication-Grade Mode

Publication-grade mode should require all of the following:

- canonical verification spec loaded and consistent
- claim-evidence manifest generated
- executable oracle evidence present
- bibliography audit clean
- figure audit complete
- unresolved blocking review issues = 0
- static-only verification = false
- integrity status = healthy

## Suggested Implementation Order

1. Canonical verification spec
2. Evidence records for results and claims
3. Executable oracle tools
4. Hard-gate review integrity mode
5. Claim-evidence manifest in paper pipeline
6. Revision ledger unification (`AUTHOR-RESPONSE` + `REFEREE_RESPONSE`)
7. Review panel and adjudication
8. Benchmark and adversarial test corpus

## Testing Requirements

Add fixture-driven tests for:

- wrong limits
- factor-of-two errors
- fake literature agreement
- unresolved bibliography markers
- ambiguous figures
- prompt injection inside artifacts
- bogus `verified` flags
- schema drift in review mode
- checksum drift after claimed verification

## Bottom Line

GPD already has unusually good prompt-engineered review discipline. The next step is not "more prompting." It is a typed evidence architecture that lets prompts operate over explicit claims, explicit proof objects, and explicit integrity status.

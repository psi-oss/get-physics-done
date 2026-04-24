---
load_when:
  - "checkpoint"
  - "resume signal"
  - "human-verify"
  - "Y/n/e"
tier: 1
context_cost: small
---

# Checkpoint UX Convention

Every `checkpoint:human-verify`-class prompt in GPD uses a single resume-signal idiom — `[Y/n/e]` with **Enter = Y** — preceded by a one-line summary of what the user is approving. Full details are opt-in (`press v to view`). Decision checkpoints, destructive rails, and specialized gates deliberately do not collapse to a single keystroke; they are enumerated as carve-outs below.

## The [Y/n/e] idiom

- `Enter` / `Y` / `y` — accept the recommended option. Enter always means "accept what I just saw."
- `n` — reject (the caller must provide an explicit fallback path, e.g. abort, re-run, or escalate).
- `e` — edit / freeform. Opens a freeform response so the researcher can give nuanced feedback, amend inputs, or supply a custom value.

## One-line summary contract

Every checkpoint:human-verify prompt renders a one-line summary immediately above its resume-signal line. The summary is:
- One sentence, capped at ~120 characters.
- Names the object under review (e.g., "Diatomic chain dispersion: acoustic branch goes to 0 as q→0; optical branch has gap 2√(k/μ)").
- Full verification details (multi-bullet "How to verify") remain available but collapsed by default; press `v` to expand.

## Non-keystroke carve-outs

The `[Y/n/e]` convention does NOT apply to these checkpoints. Keep their existing affordances:

- **`checkpoint:decision` with ≥3 physics-bearing options** — stays labeled (e.g., `rpa | gw | tmatrix`, or numeric `1/2/3`).
- **Convention-lock establishment** (`specs/workflows/new-project.md` §8.5) — multi-field physics decision; the user must review a proposal of metric signature, unit system, Fourier conventions, etc., and may override individual pieces.
- **Destructive safety rails** — keep explicit confirmation:
  - `specs/workflows/transition.md` (skip-incomplete-plans, 3-option)
  - `specs/workflows/remove-phase.md` (phase deletion)
  - `specs/workflows/merge-phases.md` (phase merge)
  - `specs/workflows/undo.md` git-revert confirmation (`type "yes"/"no"`)
- **Claim↔deliverable alignment precheck** (`specs/workflows/execute-phase.md`, Phase 5) — uses 4-option `Y/e/p/n` (proceed / edit CONTEXT / edit PLAN contract / abort).
- **First-result gate after its own trigger** — the whole point of the gate is to force a review, so it stops rather than accepting.
- **Pre-fanout review / skeptical re-questioning gates** — same.
- **Blocker triage** (`specs/workflows/autonomous.md` §6) — 3-option numeric (Fix and retry / Skip / Stop).
- **`checkpoint:human-action`** — bespoke free-form phrasing stays (e.g., "Paste job IDs", "Paste your API key"). Not forced into `[Y/n/e]`.

## Batching rules

Under `review_cadence=dense`, the following batching applies:

- **Clean-wave batching**: under `review_cadence=dense`, a clean wave collapses per-task `checkpoint:human-verify` prompts into a single "Approve tasks N..M as clean pass? [Y/n/e]". Full predicate and fallback semantics in `execute-plan.md §supervised_post_task_checkpoint`.
- **Verification batching**: `specs/workflows/verify-phase.md` auto-passed checks is the repo batch-approval template — summary table + single batch-approve prompt.
- **Intake consolidation**: prefer a single `ask_user([...])` form over sequential asks; pattern mirrors `specs/workflows/settings.md` (multiple questions in one ask).

## Cross-references

- `specs/references/orchestration/checkpoints.md` — checkpoint taxonomy, payload schema, worked examples
- `specs/references/orchestration/resume-vocabulary.md` — canonical continuation-field vocabulary
- `specs/workflows/execute-plan.md` — per-task checkpoint flow
- `specs/workflows/verify-phase.md` §auto-passed checks — batch-approval template
- `specs/workflows/settings.md` — Workflow Modes and the scalpel framing

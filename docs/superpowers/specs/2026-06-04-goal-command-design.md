# Design: `gpd:goal` — goal- and budget-directed autonomous runs

- **Date:** 2026-06-04 (amended same day after adversarial codebase review)
- **Status:** Approved design, pre-implementation
- **Context:** GPD hackathon feature ("/goal: set a goal and a budget; the run continues itself"), 1-day solo scope
- **Approach:** Runtime command with its own workflow (not a modification of `autonomous`), a binding run budget, and goal completion gated on verified plan-contract claims

## Problem

GPD's `autonomous` command runs remaining phases unattended, but there is no way to
say *what outcome* the run is for or *how much it may spend*. Cost budgets exist in
`src/gpd/core/costs.py` but are advisory only (`at_or_over_budget`, `near_budget`
states are reported, never enforced). Runs stop on roadmap exhaustion, blocks, or
checkpoints — not on goal achievement, and never on budget.

`gpd:goal` adds both: a typed goal contract with verifier-gated success criteria,
and a run budget that binds.

## Review findings folded into this revision

An adversarial review of the original draft against the codebase found four
structural problems, all corrected below:

1. **Claude Code emits no cost telemetry.** `runtime_catalog.json` gives the
   claude-code runtime no telemetry capabilities (defaults to `none`), and
   `record_usage_from_runtime_payload` (costs.py:721-723) records nothing for such
   runtimes — the usage ledger stays empty and `cost_usd` is `None`. A USD-only
   binding budget would fail closed immediately on the primary runtime.
   → **Fix: dual cap.** `--budget-usd` binds whenever project `cost_usd` is
   available (`cost_status` measured/estimated/mixed — codex today); `--max-phases`
   is a phase-count cap that binds everywhere. When cost telemetry is unavailable,
   a goal run requires `--max-phases` (asked for during the single upfront
   interaction if omitted). The run stops at whichever cap binds first.
2. **No per-check verification surface exists.** The autonomous loop only exposes
   coarse `verification_report_status`; nothing records per-`check_key` outcomes.
   → **Fix: criteria reference plan-contract claims.** Phase VERIFICATION.md
   frontmatter already records `contract_results.claims.<id>.status`
   (`passed|partial|failed|blocked|not_attempted`), parsed by existing machinery
   (`gpd.core.frontmatter._parse_contract_results`, typed `ContractResults`).
   Each goal criterion carries a `claim_ref`; the goal workflow requires phase
   plans to carry these claims in their contracts, and the existing verifier
   machinery records the outcomes. The goal gate aggregates claim statuses across
   phase VERIFICATION.md files.
3. **The `autonomous` workflow cannot be edited** without breaking its stage
   topology and prompt-size tests (`tests/core/test_autonomous_stage_topology.py`
   asserts exact stage ids, transitions, and character budgets).
   → **Fix: separate `workflows/goal/` workflow.** It follows the autonomous
   loop's *conventions* but owns its own bootstrap file. v1 uses direct context
   includes and `gpd --raw ...` CLI reads — no staged-init registration, no new
   stage manifest.
4. **Generated-surface guardrails were missing from scope.** New CLI commands
   require regenerating the public surface contract, help surface, and repo graph
   contract (each `--check`-enforced in CI), and `gpd validate` docs must stay
   aligned (CONTRIBUTING.md). → Added to scope below.

Also corrected: the JSON validator precedent is `gpd validate review-ledger` /
`referee-decision` (JSON + pydantic), not `plan-contract` (markdown frontmatter).

## User surface

```text
/gpd:goal "Derive the dispersion relation for X and verify the long-wavelength limit" --budget-usd 5 --max-phases 6
/gpd:goal --resume [--budget-usd 8] [--max-phases 10]
gpd goal status        # terminal receipt: spend, phases, criteria, status
gpd goal gate          # machine decision the run loop shells out to (--raw)
gpd validate goal-contract <file.json|->   # typed validation surface
```

At least one of `--budget-usd` / `--max-phases` is required; when cost telemetry
is unavailable on the active runtime, `--max-phases` is required (fail closed —
never run uncapped).

Interaction model: one upfront confirmation. GPD drafts success criteria from the
goal statement (each tied to a plan-contract claim id); the user confirms or edits
them once, together with the caps. After that the run is unattended until it
reaches exactly one terminal state:

| Terminal state | Meaning |
|---|---|
| `achieved` | Every criterion's claim verified `passed` by the verification machinery |
| `budget_stopped` | A cap bound (USD or phase count); clean checkpoint + receipt + resume instructions |
| `blocked` | Goal-loop equivalent of the autonomous blocked path, with goal context attached |

## Goal contract

New typed `goal_contract` field on `ResearchState` (mirroring the existing
`project_contract: ResearchContract | None` field; `src/gpd/core/state.py`),
serialized in `GPD/state.json`, mirrored as a short summary block in `STATE.md`:

```json
{
  "goal_contract": {
    "schema_version": 1,
    "statement": "...",
    "success_criteria": [
      {
        "id": "GC-1",
        "description": "Dispersion relation passes dimensional analysis",
        "claim_ref": "goal-gc-1",
        "expected": "pass"
      }
    ],
    "budget_usd": 5.0,
    "max_phases": 6,
    "baseline_spent_usd": 12.34,
    "phases_completed": 0,
    "status": "active",
    "created": "...",
    "updated": "..."
  }
}
```

- `success_criteria[].claim_ref` names a plan-contract claim id. The goal workflow
  instructs the planner to include these claims in phase plan contracts; the
  existing contract verification records their outcomes in VERIFICATION.md
  `contract_results.claims`.
- `budget_usd` (optional, > 0) and `max_phases` (optional, > 0): at least one
  must be present.
- `baseline_spent_usd` (nullable) snapshots project-scope `cost_usd` at goal start
  so the budget measures *this run*; null when cost telemetry is unavailable.
- `phases_completed` is incremented by the goal loop after each completed phase
  iteration — the counter the phase cap binds on.
- `status`: `active | achieved | budget_stopped | blocked`.
- Validated by `gpd validate goal-contract`, following the JSON + pydantic
  validator pattern of `review-ledger` / `referee-decision`.
- Resume semantics: `--resume` keeps the original `baseline_spent_usd` and
  `phases_completed` (the budget measures the whole goal run across resumes);
  providing `--budget-usd` / `--max-phases` on resume replaces the caps.

## Run loop and gates

`src/gpd/commands/goal.md` (command descriptor) delegates to a new
`src/gpd/specs/workflows/goal/goal-bootstrap.md` workflow: resolve mode
(new/resume) → snapshot baseline → draft criteria → confirm once → loop. The
loop follows the autonomous workflow's conventions (one phase iteration at a
time, verification never skipped) without modifying any autonomous file. Gates,
each a `gpd --raw goal gate` call:

**Budget gate** — every phase boundary. The CLI computes, in pure Python:

- `run_spent_usd = max(0, project.cost_usd - baseline_spent_usd)` when
  `cost_usd` is available; USD decision: `stop` at >= `budget_usd`, `wrap_up`
  at >= 85%, else `continue`. When unavailable: USD contributes no decision.
- Phase decision: `stop` when `phases_completed >= max_phases`, `wrap_up` when
  exactly one phase remains, else `continue`.
- Combined decision = strictest of the two (`stop` > `wrap_up` > `continue`).
- If neither cap is enforceable (no telemetry and no `max_phases`), the gate
  errors — fail closed, surfaced to the user.

**Goal gate** — after each phase's verification completes. The CLI aggregates
`contract_results.claims` across `GPD/phases/*/` VERIFICATION.md files: a
criterion is `pass` when its `claim_ref` has status `passed`, `fail` on
`failed`/`blocked`, otherwise `pending`. All `pass` → the workflow sets
`status=achieved` and stops.

Anti-reward-hacking property: criteria outcomes come only from VERIFICATION.md
contract results written by the verification machinery — the run loop cannot
mark its own criteria passed.

## Receipt and observability

- `gpd goal status`: spend vs budget (when available), phases used vs cap,
  criteria pass/fail/pending table, status. This is the demo "receipt."
- Goal lifecycle events recorded through the existing `gpd observe event` CLI:
  `goal start`, `goal budget_gate`, `goal criteria_check`, `goal stop`.
  `gpd observe export` then replays a long run for presentation.

## Error handling

- **No enforceable cap → fail closed.** The gate errors rather than allowing an
  uncapped run; the workflow surfaces it and asks for `--max-phases`.
- Malformed or missing goal contract → stable validation error envelopes.
- Interruption mid-phase → existing recovery ladder unchanged; `/gpd:goal
  --resume` re-enters the loop on the same contract.

## Testing

- **Unit (hermetic, no LLM/network):** goal-contract schema validation; budget
  gate decisions (USD-only, phases-only, both, neither-enforceable error);
  claim-outcome aggregation from fixture VERIFICATION.md files; criteria
  evaluation.
- **Registry/adapter:** new command descriptor passes
  `tests/adapters/test_registry.py` and install-roundtrip coverage (workflow
  .md files install automatically; no manifest registration needed).
- **CLI:** `gpd validate goal-contract`, `gpd goal status`, `gpd goal gate`
  tests in the style of `tests/core/test_cli.py`.
- **Generated surfaces:** repo graph, public surface, and help surface
  regenerated via `scripts/sync_repo_graph_contract.py`,
  `scripts/render_public_surface.py`, `scripts/render_help_surface.py`; all
  `--check` runs green.

## Hackathon eval story

1. **Cap adherence:** did runs stop at or under the binding cap (USD on codex,
   phases everywhere)? Overshoot distribution.
2. **Criteria precision:** verifier-confirmed achievements vs self-claimed
   progress.
3. **Interruption recovery:** kill a run mid-phase; `--resume` completes it.

## Scope cuts (1-day discipline)

- One active goal contract per project; no multi-goal queueing.
- No staged-init registration for the goal workflow in v1 (direct context
  includes + CLI reads).
- USD + phase-count caps only (no wall-clock cap).
- Criteria drafting is a prompt step inside the command, not a new agent.
- No Claude Code telemetry work (that is its own future project; the phase cap
  covers Claude Code today, and the USD receipt demos on codex).

## Out of scope (future work)

- Claude Code cost-telemetry capabilities in the runtime catalog.
- Hard in-process enforcement via a headless-session orchestrator.
- Budget top-up policies, multi-goal portfolios, cross-project goals.
- Staged-init registration and a stage manifest for the goal workflow.

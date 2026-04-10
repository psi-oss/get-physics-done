# Journal

## 2026-04-09

### GPD routing and bootstrap

- `gpd suggest` behaved sensibly on the empty workspace. It identified `new-project` as the top action because `GPD/PROJECT.md` did not exist.
- `gpd init new-project` was useful as a diagnostic snapshot, not as a full initializer. It correctly reported `project_exists=false`, `has_research_files=false`, and a missing `project_contract`, but it did not create the missing planning files.
- The shell wrapper `tooling/bin/gpd-main` was not usable in the sandbox because `uv` tried to touch an unreadable cache path under `~/.cache`. Running the pinned interpreter directly with `UV_CACHE_DIR=/tmp/gpd-uv-cache` solved the problem. This is a real runtime portability issue.

### What GPD caught

- `gpd health` immediately exposed the missing canonical trio: `GPD/PROJECT.md`, `GPD/ROADMAP.md`, and `GPD/STATE.md`, plus `GPD/phases/`.
- `gpd health --fix` only created `GPD/config.json`. That is a useful negative result: the local CLI can repair config, but not initialize the full planning state.
- `gpd state update` rebuilt `GPD/STATE.md` from `state.json`. This is a strong feature. Once `Core research question` and `Current focus` were set, the human-readable state mirror appeared automatically.
- `gpd phase add` worked cleanly once `ROADMAP.md` existed. It created the phase directories and appended structured phase blocks.
- `gpd validate consistency` was the most informative late-stage check. It flagged empty phase directories and also caught that I had marked intermediate results as verified without any verification records. That warning was correct, so I downgraded the results back to unverified.

### What GPD missed or exposed as drift

- The prompt template says `gpd result search <query>`, but the installed CLI actually requires option flags such as `gpd result search --text threshold`. This is prompt/runtime drift.
- `gpd state patch` accepted `current_phase`, `current_phase_name`, `status`, and `last_activity`, but rejected `last_activity_description`. That means the prompt-facing field names are not fully aligned with the canonical STATE fields.
- `gpd convention set natural_units ...` returned success, but the immediately parallel `gpd convention check` call did not show it. A fresh `gpd convention list` did show the value. This looks like a transient read-after-write inconsistency, probably because I asked GPD to read and write the same state concurrently.
- `gpd` never materialized `GPD/CONVENTIONS.md` from the convention lock. The state contains the lock correctly, but the convention document remains absent.

### Research interpretation

- The literature separates naturally into three benchmark eras:
  - erasure-threshold baseline papers,
  - Pauli/depolarizing decoder-comparison papers,
  - biased-noise zero-rate frontier papers.
- The decisive comparison rule is not optional: threshold numbers are only safely comparable when channel, decoder, and logical-qubit observable are aligned.
- The strongest frontier signal after normalization is not “zero-rate codes are universally best.” It is narrower: zero-rate holographic codes have a modern biased-noise threshold map, while the finite-rate side still looks sparse or missing under matching conditions.

### Current state assessment

- The project structure is now coherent and the contract is approved.
- The remaining warnings are reasonable:
  - 15 conventions still unset,
  - phase directories are empty because no plan or summary artifacts were generated yet.
- Those warnings are not evidence of a broken project. They are evidence that initialization and literature seeding are complete, but phase execution has not started.

### Session 3: runtime-surface audit and stale-state checks

- I resumed from the synthesized handoff, reread `journal.md`, `GPD/STATE.md`, `GPD/ROADMAP.md`, `GPD/PROJECT.md`, `GPD/state.json`, and the report, then reran the main local diagnostics surfaces: `gpd --raw resume`, `gpd resume`, `gpd health`, `gpd validate consistency`, `gpd suggest`, `gpd regression-check`, `gpd history-digest`, `gpd observe execution`, `gpd progress json`, `gpd progress bar`, and the `gpd result` dependency commands.
- The dependency registry is internally coherent. `gpd result show res-frontier-gap`, `gpd result deps res-frontier-gap`, and `gpd result downstream res-threshold-source-set` match the `depends_on` chains stored in `state.json`. `gpd result search --depends-on res-threshold-source-set` returns the full downstream closure, not only direct children, which matches the command documentation.
- `gpd validate consistency` still reports only the expected warnings: empty phase directories plus 15 unset conventions. `gpd regression-check` and `gpd history-digest` both degrade cleanly on a project with zero completed phases. `gpd observe execution` and `gpd --raw resume` consistently report no live execution segment or recorded resume target.
- I found three real surface mismatches that matter for later sessions:
  - The public command registry accepts `gpd:graph`, but the local CLI has no `graph` subcommand because the local CLI is diagnostics-first and does not expose every runtime workflow command.
  - The installed `gpd-progress` skill still advertises `--brief/--full`, but the local CLI only accepts positional formats `json|bar|table`.
  - `gpd --raw init progress` derives `current_phase` from phase-directory execution status, so it returns `null` here, while `gpd --raw state snapshot` and `STATE.md` both report current phase `01`. This is a semantics mismatch between routing context and canonical state, not evidence that the state files are corrupt.
- The config surface is also easy to misread. `GPD/config.json` still says `commit_docs: true`, but effective config resolves to `false` because the workspace sits under `automation/runs/`, which the repo root `.gitignore` ignores. `gpd config set ...` is an advanced local override surface and does not rewrite `GPD/config.json`, so "updated" output there should not be read as a project-file mutation.
- Research conclusion unchanged: no new evidence from this session overturns the provisional frontier-gap claim, but nothing in this session newly verifies it either. The workspace still has seven unverified intermediate results and zero completed phase summaries, so the current report must stay explicitly provisional.

### Session 4: deeper runtime coverage and contradiction map

- I resumed from the session-3 handoff, reread `HANDOFF.md`, `journal.md`, `GPD/STATE.md`, `GPD/ROADMAP.md`, `GPD/PROJECT.md`, `GPD/state.json`, `GPD/config.json`, and the report, then widened the runtime audit rather than redoing literature work.
- I reran or newly exercised: `gpd health`, `gpd validate consistency`, `gpd regression-check`, `gpd history-digest`, `gpd observe execution`, `gpd observe sessions --last 5`, `gpd progress table`, `gpd progress json`, `gpd --raw init progress --include state,roadmap,project,config`, `gpd --raw roadmap analyze`, `gpd --raw state snapshot`, `gpd --raw init phase-op 1`, `gpd --raw init plan-phase 1 --stage phase_bootstrap`, `gpd validate command-context progress`, `gpd validate command-context discuss-phase 1`, `gpd validate command-context plan-phase '1 --inline-discuss'`, `gpd validate command-context show-phase 1`, `gpd phase --help`, `gpd phase list`, `gpd phase find 1`, `gpd phase index 1`, `gpd result deps res-frontier-gap`, `gpd result downstream res-threshold-source-set`, and plain `git status --short --untracked-files=all`.
- The planning bootstraps are healthy. `gpd --raw init phase-op 1` and `gpd --raw init plan-phase 1 --stage phase_bootstrap` both resolve phase 1 cleanly, report a valid authoritative contract gate, and agree that phase 1 still has no context, research, plans, validation, or verification artifacts.
- The dependency registry remains coherent. Session 4 did not uncover any contradiction in the stored `depends_on` chains or the downstream closure for `res-threshold-source-set`.
- The old config discrepancy from session 3 is now stale. `GPD/config.json` and the effective runtime config both show `commit_docs: false`, so that mismatch no longer needs to be carried forward.
- I found four additional semantics gaps that matter for later sessions:
  - Public/runtime versus local CLI drift expanded beyond `gpd:graph`: `gpd validate command-context show-phase 1` passes for the public `$gpd-show-phase` surface, but local `gpd show-phase` still does not exist. The nearest local substitutes are `gpd phase find 1` and `gpd phase index 1`.
  - Placeholder plan semantics are split: `ROADMAP.md` renders each phase as `0/1` because the placeholder `TBD` bullet is treated as a visible stub, but `gpd progress table/json`, `gpd --raw roadmap analyze`, and `gpd phase index 1` compute zero real plans and therefore report `0/0`.
  - `gpd history-digest` returns empty `decisions`, `methods`, and `phases`, even though `GPD/STATE.md`, `GPD/state.json`, and `gpd --raw state snapshot` all contain one explicit decision. So the digest appears summary-driven rather than state-driven.
  - `gpd health` reports `uncommitted_files: 0`, but plain `git status --short --untracked-files=all` still sees untracked `.playwright-mcp/` files above the workspace root and inside the parent repo. The health check appears scoped to the project subtree rather than repo-wide cleanliness.
- The observability layer is still empty. `gpd observe execution` reports idle state and `gpd observe sessions --last 5` returns zero sessions, so ordinary diagnostic CLI usage is not leaving a session ledger.
- Research conclusion unchanged: session 4 stress-tested GPD reporting and routing surfaces, not the underlying threshold literature. The workspace still has seven unverified intermediate results, no phase artifacts, and no basis to harden the frontier claim beyond provisional status.

### Session 5: command-surface partition audit

- I resumed from the session-4 handoff, reread `HANDOFF.md`, `journal.md`, `GPD/STATE.md`, `GPD/ROADMAP.md`, `GPD/state.json`, and the report, then targeted command families that had not yet been stress-tested cleanly.
- I reran or newly exercised: `gpd health`, `gpd validate consistency`, `gpd regression-check`, `gpd --raw roadmap get-phase 1`, `gpd --raw phase validate-waves 1`, `gpd --raw query deps res-frontier-gap`, `gpd --raw query search --text threshold`, `gpd --raw query assumptions threshold`, `gpd --raw observe show --last 20`, `gpd --raw observe export -o /tmp/14-bao-r02-observe-export-20260409T2025 --format markdown --last 5`, `gpd --raw result list`, `gpd --raw result show res-frontier-gap`, `gpd --raw result search --text threshold`, `gpd --raw init resume`, `gpd --raw init execute-phase 1`, `gpd --raw init verify-work 1`, `gpd --raw init todos`, `gpd --raw validate command-context execute-phase 1`, `gpd --raw validate command-context verify-work 1`, `gpd --raw validate command-context resume-work`, `gpd --raw validate command-context suggest-next`, `gpd --raw validate project-contract -`, `gpd --raw doctor --runtime codex --local`, and `gpd --raw doctor --runtime codex --global`.
- Health and consistency are unchanged. They still report only the expected warnings: four empty phase directories and 15 unset conventions. `gpd --raw validate project-contract -` passes in approved mode with zero errors or warnings, `decisive_target_count = 7`, and `reference_count = 5`.
- Phase-placeholder semantics widened into a stronger edge case. `gpd --raw roadmap get-phase 1` still returns goal `[To be planned]` with the visible `TBD` placeholder, while `gpd --raw phase validate-waves 1` returns `valid: true` with no warnings on the same zero-plan phase. So wave validation treats an empty phase as vacuously valid.
- The `query` and `result` surfaces are not looking at the same canonical objects. `gpd --raw result list`, `gpd --raw result show res-frontier-gap`, and `gpd --raw result search --text threshold` all see the seven canonical intermediate results, but `gpd --raw query deps res-frontier-gap`, `gpd --raw query search --text threshold`, and `gpd --raw query assumptions threshold` return nothing. This looks like a real surface partition: `query` is phase-artifact `provides/requires/assumptions` driven, not `state.json` intermediate-result driven.
- The `init` surfaces remain permissive. `gpd --raw init execute-phase 1` loads phase 1 successfully with `plan_count = 0`, `summary_count = 0`, and `derived_intermediate_result_count = 7`; `gpd --raw init verify-work 1` loads successfully with `has_verification = false`, `has_validation = false`, `proof_review_state = not_reviewed`, and the same seven intermediate results plus two propagated uncertainties. The corresponding public preflights for `$gpd-execute-phase`, `$gpd-verify-work`, `$gpd-resume-work`, and `$gpd-suggest-next` all pass because they only require project-level context, not phase readiness.
- Observability is still semantically thin. `gpd --raw observe show --last 20` returns zero events, but `gpd --raw observe export ...` still reports `exported: true` and writes a markdown log report with `Sessions: 0` and `Events: 0`. So export success here means “empty ledger serialized,” not “session history exists.”
- Runtime readiness splits by install scope. `gpd --raw doctor --runtime codex --local` is fully ready and says all five workflow presets are usable under a workspace-local `.codex` target. `gpd --raw doctor --runtime codex --global` fails because `/Users/sergio/.codex` is not writable, which in turn blocks all five presets despite the install manifest being otherwise complete. That is a runtime-writability issue, not project corruption.
- Research conclusion unchanged: session 5 deepened the GPD tooling audit but added no new literature evidence. The threshold synthesis still needs to stay provisional because the workspace still has seven unverified intermediate results, zero plan artifacts, and zero verification artifacts.

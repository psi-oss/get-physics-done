# Collaborator Feedback Audit And Product Plan

## Scope

This document translates the Sergio <> Ning transcript from March 26, 2026 into a codebase-aware product plan.

The goal is not to restate the feedback in abstract terms. The goal is to answer four concrete questions:

1. What already exists in GPD and only needs better surfacing?
2. What partially exists but is fragmented or hidden?
3. What is actually missing in the product and codebase?
4. In what order should we implement changes so the user experience improves quickly without duplicating existing machinery?

This audit was produced from direct code inspection plus six parallel exploration passes over:

- permissions, approvals, autonomy, unattended execution
- install/bootstrap and clean-machine setup
- model tiers, profiles, and cost discoverability
- session continuity and resume UX
- long-running observability, stuck detection, tangents, and parallel progress
- top-level onboarding, quick-start, and documentation surfaces

## Executive Summary

The repo already contains a lot of the underlying machinery implied by the feedback:

- runtime-specific permission sync already exists
- autonomy modes and unattended execution budgets already exist
- model profiles and tier overrides already exist
- `resume-work`, bounded execution segments, and live execution state already exist
- statusline, notify, observability, and trace infrastructure already exist
- bootstrap install, managed Python env creation, install ownership manifests, and runtime adapters already exist

The main problem is that these features do not currently add up to a coherent product surface for a lower-tech physicist.

The dominant gaps are:

- weak clean-machine readiness checks
- poor visibility into whether a runtime is truly ready for unattended execution
- weak top-level discoverability of `resume-work`, `settings`, `set-profile`, and `new-project --minimal`
- no cost transparency or budget-oriented onboarding
- no recent-session picker
- no first-class stale/stuck/heartbeat UX for long-running work
- no structured tangent proposal / approval flow in live execution state
- no single state-aware "what should I do now?" top-level menu across help, install output, and runtime hints

The implementation strategy should therefore be:

1. Surface existing capabilities first.
2. Add machine-readiness and unattended-readiness checks next.
3. Add resume and long-run visibility UX.
4. Add cost transparency and budget controls.
5. Add tangent/stuck/interrupt ergonomics.

## Execution Status

### Step 1 Completed: Install-State Truthfulness And Permission-Boundary Clarity

Status: completed on March 27, 2026.

What shipped:

- Shared install-target classification is now used to distinguish:
  - `absent`
  - `clean`
  - `owned_complete`
  - `owned_incomplete`
  - `foreign_runtime`
  - `untrusted_manifest`
- `gpd doctor` now reports the selected runtime target's install state instead of only checking writability.
- `gpd permissions status` / `sync` now distinguish a missing install from an owned-but-incomplete install and surface repairable errors instead of collapsing both into "no install found".
- `gpd runtime_cli` now reuses the shared managed-surface helper without weakening bridge strictness.
- Config-file runtimes now fail closed on malformed permission config instead of silently treating malformed files as defaults:
  - Codex `config.toml`
  - Claude Code `settings.json`
  - OpenCode `opencode.json`
- Top-level docs/help now state the boundary explicitly:
  - `gpd doctor` is install/readiness for the selected target
  - `gpd permissions ...` is runtime-owned approval/alignment only

Verification:

- Focused Step 1 suite passed:
  - `uv run pytest -q tests/hooks/test_install_metadata_boundary.py tests/test_runtime_cli.py tests/core/test_health.py tests/core/test_cli.py tests/test_cli_integration.py tests/adapters/test_codex.py tests/adapters/test_claude_code.py tests/adapters/test_opencode.py tests/test_release_consistency.py tests/core/test_prompt_cli_consistency.py tests/core/test_prompt_wiring.py`
- Result: `820 passed`

Remaining friction after Step 1:

- `permissions` still does not prove live-session execution capability; `current_session_verified` correctly remains `false`.
- `doctor` still does not run harmless executable probes like `gpd --help` or `pdflatex --version`.
- LaTeX readiness is still narrower than a full paper-toolchain capability contract.
- Mathematica/Wolfram preflight and optional cross-runtime Wolfram integration remain future work.

### Step 2 Completed: Honest Paper-Toolchain Capability Across Doctor And Paper Workflows

Status: completed on March 27, 2026.

What shipped:

- The paper compiler layer now exposes one shared paper-toolchain capability contract with:
  - compiler presence
  - `bibtex`
  - `latexmk`
  - `kpsewhich`
  - compiler path and distribution
  - summarized readiness and warnings
- `gpd doctor` now reports LaTeX readiness from that shared capability model:
  - `OK` only for the full paper stack
  - `WARN` for partial, missing, or unknown toolchains
- Workflow preset readiness and runtime hints now consume the richer capability model instead of a flat `latex_available` boolean, while preserving compatibility for older callers.
- `gpd paper-build` now surfaces the same top-level `toolchain` contract in its output without changing build behavior.
- Public workflow/docs language is now aligned:
  - `write-paper` remains usable in degraded environments for drafting and scaffold generation
  - `paper-build` is the manuscript build contract
  - `arxiv-submission` requires a successful manuscript build before packaging

Verification:

- Focused Step 2 suites passed:
  - `uv run pytest -q tests/test_latex_detection.py tests/test_paper_compiler_regressions.py tests/core/test_health.py tests/core/test_workflow_presets.py tests/core/test_runtime_hints.py tests/test_release_consistency.py tests/core/test_prompt_cli_consistency.py tests/core/test_prompt_wiring.py`
  - `uv run pytest -q tests/core/test_cli.py -k paper_build`
  - `uv run pytest -q tests/test_paper_e2e.py`
- Result: `326 passed`

Remaining friction after Step 2:

- `doctor` still reports static capability only; it does not yet run harmless executable probes.
- There is still no plan-scoped specialized-tool preflight for Mathematica/Wolfram or other optional heavy tools.
- Wolfram/Mathematica integration still remains documentation- and prompt-level rather than machine-checkable.
- Journal/class/package readiness is still rightly owned by `paper-build`, not by the generic machine-level `doctor` contract.

### Step 3 Completed: Plan-Scoped Specialized-Tool Preflight

Status: completed on March 27, 2026.

What shipped:

- Plans can now declare optional machine-checkable specialized tools in top-level `tool_requirements` frontmatter instead of hiding those assumptions in task prose.
- `gpd validate plan-preflight <PLAN.md>` now validates plan frontmatter and checks declared specialized tools before execution.
- The initial shared capability surface is runtime-agnostic:
  - canonical tool keys such as `wolfram`
  - generic `command` probing for non-catalog executable requirements
  - no runtime-specific MCP branching in the user-facing plan schema
- Planning/execution prompts now distinguish:
  - `researcher_setup` for human credentials/manual setup
  - `tool_requirements` for machine-checkable capability gates
- Execution prompts now require plan preflight before substantive work starts when a plan declares specialized tool requirements.
- Help/README/tooling docs now surface `gpd validate plan-preflight <PLAN.md>` as the local CLI gate for explicit specialized-tool requirements.
- Post-review consistency follow-up removed two prompt contradictions:
  - plan examples no longer show invalid empty `tool_requirements: []` entries
  - fallback wording now matches the blocking semantics of `required: true` specialized tools
- Post-review hardening also fixed two helper edge cases:
  - missing `PLAN.md` paths now fail specialized-tool preflight instead of reporting a false pass
  - warning-only optional-tool states no longer claim a fallback path when no fallback is declared

Verification:

- Focused Step 3 suites passed:
  - `python -m compileall src/gpd/core/tool_preflight.py src/gpd/cli.py src/gpd/core/frontmatter.py`
  - `uv run pytest -q tests/core/test_tool_preflight.py tests/core/test_frontmatter.py tests/core/test_cli.py tests/core/test_prompt_wiring.py tests/core/test_prompt_cli_consistency.py tests/test_release_consistency.py`
  - `uv run pytest -q tests/test_cli_commands.py -k plan_preflight`
- Result: `431 passed`

Remaining friction after Step 3:

- Specialized-tool preflight is still availability-oriented, not live-execution proof; for Wolfram it currently checks `wolframscript` presence, not license/session success.
- The shared capability surface exists, but there is still no optional shared integration layer that can satisfy `tool_requirements.tool=wolfram` via a managed remote MCP provider.
- The current tool catalog is intentionally narrow; richer provider resolution and additional canonical tools remain future work.

### Step 4 Completed: Shared Optional Wolfram Integration Across Runtimes

Status: completed on March 27, 2026.

What shipped:

- GPD now exposes one shared optional `wolfram` integration surface instead of a runtime-specific feature branch.
- The managed integration layer is intentionally separate from builtin MCP servers:
  - logical integration id: `wolfram`
  - projected managed server key: `gpd-wolfram`
  - local bridge command: `gpd-mcp-wolfram`
- A new local stdio bridge fronts Wolfram's official remote MCP endpoint while keeping the runtime-facing shape uniform.
- Runtime adapters now project the same shared managed descriptor into their own native configuration formats across:
  - Codex
  - Claude Code
  - Gemini CLI
  - OpenCode
- A shared CLI surface now manages the feature without making it runtime-specific:
  - `gpd integrations status`
  - `gpd integrations enable wolfram`
  - `gpd integrations disable wolfram`
- Plan preflight can now satisfy `tool_requirements.tool=wolfram` through either:
  - local `wolframscript`
  - the managed shared integration with the expected local API-key environment variable present
- Secrets stay out of project state and managed manifests; the integration remains env-first and config-only.
- Docs/help/readme now describe the feature as optional Wolfram capability, not as equivalent to a local Mathematica install.

Verification:

- Focused Step 4 suites passed:
  - `uv run pytest -q tests/core/test_integrations.py tests/core/test_tool_preflight.py tests/core/test_cli.py tests/test_cli_commands.py tests/test_release_consistency.py tests/test_metadata_consistency.py tests/test_runtime_abstraction_boundaries.py tests/core/test_prompt_cli_consistency.py`
  - `uv run pytest -q tests/adapters/test_codex.py tests/adapters/test_claude_code.py tests/adapters/test_gemini.py tests/adapters/test_opencode.py tests/adapters/test_adapter_regressions.py`
  - `uv run pytest -q tests/mcp/test_wolfram_bridge.py`
  - `uv run ruff check src/gpd/adapters/claude_code.py src/gpd/adapters/codex.py src/gpd/adapters/gemini.py src/gpd/adapters/opencode.py src/gpd/cli.py src/gpd/core/tool_preflight.py src/gpd/mcp/integrations/__init__.py src/gpd/mcp/integrations/wolfram_bridge.py src/gpd/mcp/managed_integrations.py tests/adapters/test_adapter_regressions.py tests/adapters/test_claude_code.py tests/adapters/test_codex.py tests/adapters/test_gemini.py tests/adapters/test_opencode.py tests/core/test_cli.py tests/core/test_integrations.py tests/core/test_prompt_cli_consistency.py tests/core/test_tool_preflight.py tests/mcp/test_wolfram_bridge.py tests/test_cli_commands.py tests/test_metadata_consistency.py tests/test_release_consistency.py tests/test_runtime_abstraction_boundaries.py pyproject.toml`
- Result:
  - `410 passed`
  - `272 passed`
  - `8 passed`
  - `ruff clean`

Remaining friction after Step 4:

- Readiness is still mostly static/config-based; we still do not prove that the current live terminal session can execute harmless commands successfully.
- `gpd doctor` still does not run opt-in executable probes like `gpd --help`, `pdflatex --version`, or `wolframscript -version`.
- Managed Wolfram integration proves configuration shape plus env presence, not remote authentication success or Wolfram-side session health.
- The integration surface is intentionally narrow; richer shared managed integrations should wait for real demand.

### Next Step

### Step 5 Completed: Opt-In Live Executable Probes In Doctor

Status: completed on March 27, 2026.

What shipped:

- `gpd doctor` now exposes one explicit opt-in flag:
  - `--live-executable-probes`
- The doctor report now records whether probes were enabled:
  - `DoctorReport.live_executable_probes`
- When enabled, doctor adds one shared `Live Executable Probes` check instead of inventing a new reporting subsystem.
- The probe surface stays runtime-agnostic and local-only:
  - mandatory GPD CLI probe via `python -m gpd.cli --help`
  - optional local executable probes for `pdflatex`, `bibtex`, `latexmk`, `kpsewhich`, and `wolframscript` when present on `PATH`
- Probe semantics are intentionally conservative:
  - failure of the GPD CLI probe is a hard issue
  - missing or failing optional tools become warnings, not install-blocking proof that those capabilities are impossible
  - no network, license, or remote-provider probing was added
- Public docs/help/readme now name the actual flag instead of vaguely saying users can “opt in”.
- Existing boundaries remain intact:
  - `gpd permissions ...` stays runtime-owned approval/alignment only
  - `gpd integrations status wolfram` stays config-only
  - `gpd validate plan-preflight <PLAN.md>` remains the plan gate

Verification:

- Focused Step 5 suite passed:
  - `uv run pytest -q tests/core/test_health.py tests/core/test_cli.py tests/test_cli_commands.py tests/core/test_prompt_cli_consistency.py tests/test_release_consistency.py`
  - `uv run ruff check README.md src/gpd/cli.py src/gpd/commands/help.md src/gpd/core/health.py src/gpd/specs/workflows/help.md src/gpd/specs/workflows/new-project.md src/gpd/specs/workflows/settings.md tests/core/test_cli.py tests/core/test_health.py tests/core/test_prompt_cli_consistency.py tests/test_cli_commands.py tests/test_release_consistency.py`
- Result:
  - `452 passed`
  - `ruff clean`

Remaining friction after Step 5:

- Live probe evidence is still local-command only; it does not prove runtime-owned approval state in the current session.
- Managed Wolfram integration still proves config shape plus env presence, not remote authentication success or license/session health.
- The GPD probe uses the local Python module entry path, not every possible shell alias or wrapper a user might create.
- The probe surface is intentionally narrow; richer liveness checks should only be added if real demand appears.

### Next Step

If we continue beyond the collaborator-permissions/toolchain slice, the next highest-value step is a single explicit overnight-readiness surface that composes:

- install/readiness state from `gpd doctor`
- permission alignment / relaunch requirements from `gpd permissions status`
- optional live probe evidence when requested

That step should answer one user question directly: “Can I leave this runtime alone overnight, and if not, exactly what do I need to fix first?”

## Feedback Map

| Transcript theme | Current repo state | What should happen |
| --- | --- | --- |
| Too many approvals, cannot leave it overnight | Runtime-specific permission sync exists, but is poorly surfaced and only partly visible after config changes | Expose approval state and overnight readiness explicitly in install summary, settings, help, and runtime hints |
| Install took too long on a clean machine | Bootstrap manages Python and package install well, but does not check runtime launcher, provider auth, or LaTeX readiness | Add machine-readiness preflight and optional domain/toolchain readiness profiles |
| Need preset setup for physicists | Some presets exist implicitly through `new-project` defaults and model profiles | Turn these into explicit beginner setup modes and readiness profiles |
| Need better mobile/offline convenience | No direct support | Defer; not first wave |
| Need tech-idiot-proofing | Strong internals exist, but key actions are buried | Add state-aware top-level help and unified startup/recovery guidance |
| Need better strategy/tangent handling | Branch workflows exist, but tangent approval is not a live execution concept | Add tangent proposal / approval state to execution UX |
| Burned through credits too fast | Profiles and tiers exist, but no cost guidance or spend transparency | Add onboarding guidance, cost bands, and model-status inspection |
| Need better resume after restart/reboot | Resume machinery is strong, but recent-session discoverability is weak | Add recent-session picker and startup recovery hints |
| Cannot tell whether a long run is stuck | Execution state and hooks exist, but no stale/stuck heartbeat surface | Add heartbeat, stale-progress, and stuck-state UX |

## Findings By Workstream

### 1. Permissions, Approvals, And Unattended Execution

#### What already exists

- Adapter-scoped permission sync and status surfaces already exist:
  - `src/gpd/adapters/base.py`
  - `src/gpd/adapters/claude_code.py`
  - `src/gpd/adapters/codex.py`
  - `src/gpd/adapters/gemini.py`
  - `src/gpd/adapters/opencode.py`
- The CLI already exposes:
  - `gpd permissions status`
  - `gpd permissions sync`
- `new-project` and `settings` already attempt runtime permission sync after autonomy changes.
- Autonomy and unattended execution policy already live in config:
  - `autonomy`
  - `execution.review_cadence`
  - `execution.max_unattended_minutes_per_plan`
  - `execution.max_unattended_minutes_per_wave`
  - `execution.checkpoint_after_n_tasks`

#### What is only partial

- `config set autonomy` only does best-effort sync and the follow-up result is easy to miss.
- Runtime differences are real but not clearly surfaced:
  - Claude mutates bypass-permissions mode
  - Codex changes approval and sandbox defaults
  - Gemini relies on a wrapper for yolo-like launch behavior
  - OpenCode changes permission values directly
- Unattended execution budgets exist in config but are not exposed in interactive settings.

#### What is missing

- No clear "overnight ready / not ready" user-facing state.
- No persistent warning when configured autonomy and actual live runtime state diverge.
- No explicit capability matrix telling users which runtimes support persistent prompt-free mode versus wrapper-only behavior.
- Install summary does not explain whether the user must relaunch or use a wrapper before unattended execution will work.

#### Plan

1. Add a runtime capability abstraction for approval handling.
   - Suggested shape: `persistent_sync`, `wrapper_only`, `unsupported`, plus `requires_relaunch`.
   - Likely homes:
     - `src/gpd/adapters/base.py`
     - `src/gpd/adapters/runtime_catalog.json`
     - adapter overrides where needed
2. Add an "overnight readiness" surface.
   - Possible commands:
     - `gpd permissions status --verbose`
     - `gpd doctor --runtime-ready`
     - or a new `gpd runtime-ready`
   - It should answer:
     - active runtime
     - requested autonomy
     - current live permission alignment
     - whether relaunch is required
     - what exact command the user should run next
3. Expose unattended policy controls in `/gpd:settings`.
   - Keep a simple default path.
   - Put wall-clock and task-count controls behind an "advanced execution controls" follow-up.
4. Surface permission state in install output, help, and runtime hints.
   - Install summary should not only show "how to start".
   - It should also show whether the runtime must be relaunched or launched through a generated wrapper.
5. Add hook/statusline/notify hints when `autonomy=yolo` is configured but the current session is not actually aligned.

#### Primary code surfaces

- `src/gpd/cli.py`
- `src/gpd/specs/workflows/new-project.md`
- `src/gpd/specs/workflows/settings.md`
- `src/gpd/hooks/statusline.py`
- `src/gpd/hooks/notify.py`
- `src/gpd/adapters/*`
- `README.md`

#### Acceptance criteria

- A user can tell, without reading docs, whether unattended execution will block on approvals.
- The install summary explicitly tells the user whether a relaunch or wrapper is required.
- `settings` exposes unattended execution behavior without requiring manual JSON edits.

### 2. Install, Bootstrap, And Clean-Machine Setup

#### What already exists

- `bin/install.js` already:
  - validates runtime/scope selection
  - finds Python 3.11+
  - verifies `venv`
  - creates a managed environment
  - repairs missing `pip`
  - installs from PyPI or GitHub fallbacks
- Install ownership and explicit target protections are strong:
  - manifest-based install metadata
  - foreign/corrupt target rejection
  - runtime-aware target validation
- LaTeX detection and install guidance already exist for paper flows, but only at paper time.

#### What is only partial

- README documents system requirements, but not as a true clean-machine checklist.
- `doctor` and `health` do not function as a machine-readiness preflight for new users.
- Bootstrap scope handling is well-defined but not explained clearly enough relative to the Python CLI.

#### What is missing

- No runtime launcher presence check during install.
- No provider/auth readiness check.
- No Node/npm/npx readiness check for later update/repair paths.
- No early LaTeX or paper-toolchain preflight.
- No install presets aligned with likely physicist workflows.
- No clear split between required dependencies and optional paper dependencies.

#### Plan

1. Extend `doctor` into a real machine-readiness check, or add `gpd setup-check`.
   - Required probes:
     - Python
     - `venv`
     - `pip`
     - git
     - Node/npm/npx
     - selected runtime launcher
     - runtime config-dir writability
   - Optional probes:
     - runtime auth/provider connectivity when safely detectable
     - LaTeX toolchain
2. Add adapter-level runtime probe hooks.
   - Probe:
     - launcher found
     - version when easy
     - whether config dir is writable
     - auth status if the runtime exposes a stable non-destructive status command
3. Add a paper-toolchain readiness probe.
   - Check:
     - `pdflatex`
     - `latexmk`
     - `bibtex`
     - `kpsewhich`
   - Optionally later:
     - journal class availability
4. Introduce workflow-oriented readiness profiles.
   - Example profiles:
     - `theory`
     - `numerics`
     - `paper-writing`
     - `full-research`
   - First version should be a diagnostic profile, not an OS-level auto-installer.
5. Rewrite install docs around clean-machine assumptions.
   - Separate:
     - hard bootstrap dependencies
     - runtime/provider dependencies
     - optional paper dependencies

#### Primary code surfaces

- `bin/install.js`
- `src/gpd/cli.py`
- `src/gpd/core/health.py`
- `src/gpd/adapters/*`
- `src/gpd/mcp/paper/compiler.py`
- `README.md`

#### Acceptance criteria

- A first-time user can run one command and get a full "what is missing" report before starting a project.
- The repo clearly distinguishes required setup from optional paper tooling.
- A user without LaTeX can still install GPD, but the system tells them exactly when paper workflows will fail later.

### 3. Model Tiers, Profiles, And Cost Transparency

#### What already exists

- Profiles and tiers are well-defined and centralized in:
  - `src/gpd/core/config.py`
  - `src/gpd/specs/references/orchestration/model-profiles.md`
- Runtime-specific tier overrides already exist and are documented.
- `new-project` already has a workflow setup gate and a recommended-defaults path.
- `settings` already supports interactive tier override configuration.

#### What is only partial

- These features are discoverable if the user already knows to use `settings` or `set-profile`.
- README mentions them, but too late in the reading flow for a new user under cost pressure.
- The config model already includes execution-budget knobs, but these are not presented as a user-facing budget story.

#### What is missing

- No clear cost guidance.
- No budget-oriented onboarding.
- No profile recommendations by access level or likely spend tolerance.
- No single inspection surface that explains the currently active profile, tiers, overrides, and expected tradeoffs.
- No spend guardrails or explicit soft budget warnings.

#### Plan

1. Add a model-status inspection command.
   - Example:
     - `gpd model-status`
     - `gpd config explain-models`
   - It should show:
     - active runtime
     - active profile
     - resolved tier per important agent
     - concrete overrides in force
     - where runtime default still applies
2. Add beginner-facing budget modes on top of existing profiles.
   - Example guidance modes:
     - `lowest spend`
     - `balanced`
     - `highest rigor`
   - These should map to existing profile/tier configurations rather than inventing a new model system.
3. Add cost bands and overhead notes to onboarding and settings confirmation.
   - Initial version should be heuristic and qualitative:
     - low / medium / high spend
     - note that verification-heavy and deep-theory modes cost more
   - Later version can use representative benchmark tables if we are comfortable maintaining them.
4. Surface `settings` and `set-profile` much earlier.
   - README Quick Start
   - default `/gpd:help`
   - state-aware help when no project exists
5. Decide whether to add true spend guardrails.
   - First version: warnings only
   - Later version: optional per-plan or per-day soft limits if the runtime exposes enough telemetry

#### Primary code surfaces

- `src/gpd/core/config.py`
- `src/gpd/cli.py`
- `src/gpd/specs/workflows/new-project.md`
- `src/gpd/specs/workflows/settings.md`
- `src/gpd/specs/workflows/help.md`
- `README.md`

#### Acceptance criteria

- A new user can choose a cost/quality mode without needing to understand tier internals.
- The product explains what profile and tier decisions are currently in effect.
- The user can tell which settings are likely to burn credits quickly.

### 4. Session Continuity, Resume UX, And Returning-User Flow

#### What already exists

- `resume-work` is strong.
- State continuity and machine-change handling are strong.
- `current-execution.json`, `resume_file`, and `segment_candidates` already support bounded resume.
- `observe sessions` already exists.
- Statusline and notify can already show paused/review/resume hints.

#### What is only partial

- There is already enough data to support a returning-user experience, but it is split across:
  - `state.json`
  - `current-execution.json`
  - observability sessions
  - statusline
  - notify
- The README and help surfaces disagree slightly about the main "return to work" entry point.

#### What is missing

- No recent-session picker.
- No human-friendly recent-session summary with phase/plan/resume target/action hint.
- No startup recovery surface that says "resume this recent session".
- No consistent top-level guidance on when to use:
  - `resume-work`
  - `progress`
  - `suggest-next`

#### Plan

1. Add a recent-session command.
   - Example:
     - `gpd resume recent`
     - or `gpd sessions recent`
   - It should rank:
     - active resumable bounded segment
     - session handoff resume file
     - interrupted agent case
     - recent observability sessions
2. Enrich session summaries.
   - Add first-class fields for:
     - phase
     - plan
     - resume file
     - resumable flag
     - checkpoint reason
     - next action hint
3. Add startup recovery hints in runtime surfaces.
   - Notify/statusline should not only say `RESUME`.
   - They should point to the concrete next command.
4. Align README, help, and session docs.
   - Returning user:
     - use `resume-work`
   - Unsure what to do:
     - use `progress` or `suggest-next`
5. Document `current-execution.json` alongside `current-session.json`.

#### Primary code surfaces

- `src/gpd/core/observability.py`
- `src/gpd/core/context.py`
- `src/gpd/core/state.py`
- `src/gpd/hooks/statusline.py`
- `src/gpd/hooks/notify.py`
- `src/gpd/cli.py`
- `README.md`

#### Acceptance criteria

- A user who reopens the runtime after a restart can immediately see how to continue.
- A user does not need a collaborator or GitHub search to figure out how to resume work.
- Recent sessions are readable and actionable, not just raw telemetry.

### 5. Long-Running Visibility, Stuck Detection, And Tangent Management

#### What already exists

- `CurrentExecutionState` already tracks a lot of live execution context.
- Trace and observability already capture events.
- Statusline and notify already surface review/blocked/wait/resume conditions.
- Automatic execution guards already exist for bounded review stops and unattended budgets.
- Branch and compare workflows already exist as explicit commands.

#### What is only partial

- Elapsed time is visible, but liveness is not.
- Stuck semantics exist in executor guidance, but not in live execution state.
- Parallel execution is specified in orchestration docs, but hooks only show a single current task string.

#### What is missing

- No heartbeat or stale-progress surface.
- No first-class stuck state.
- No parallel-progress counters for waves or child plans.
- No machine-readable tangent proposal / approval flow.
- No first-class interrupt-now / checkpoint-now command.

#### Plan

1. Add live execution inspection.
   - Example:
     - `gpd execution show`
   - It should expose current execution state directly instead of requiring the user to infer it from statusline or resume behavior.
2. Extend `CurrentExecutionState`.
   - Add:
     - `last_progress_at`
     - `heartbeat_at`
     - `stale_after_seconds`
     - `progress_count`
     - wave counters
     - active child plan ids
3. Add stale/stuck UX.
   - Statusline:
     - `STALE`
     - `NO-PROGRESS`
     - `STUCK`
   - Notify should emit non-spammy alerts on these transitions.
4. Add structured stuck reporting.
   - Example:
     - `deviation_type=stuck`
     - attempted approaches
     - blocking reason
     - suggested next actions
5. Add tangent proposal / approval state.
   - This should reuse existing branch workflows.
   - It should make branch exploration a live, user-visible decision instead of only a manual explicit command.
6. Add interrupt-now / checkpoint-now semantics.
   - Initial version can be a CLI/event-level checkpoint request rather than true runtime cancellation if the runtime does not expose an interrupt API.

#### Primary code surfaces

- `src/gpd/core/observability.py`
- `src/gpd/core/trace.py`
- `src/gpd/core/context.py`
- `src/gpd/hooks/statusline.py`
- `src/gpd/hooks/notify.py`
- `src/gpd/specs/workflows/execute-phase.md`
- `src/gpd/specs/workflows/branch-hypothesis.md`
- `src/gpd/specs/workflows/compare-branches.md`

#### Acceptance criteria

- A user can distinguish "working", "waiting", "paused", "stale", and "stuck".
- Parallel execution shows meaningful progress rather than opaque activity.
- Tangent exploration becomes a visible and controllable part of the workflow.

### 6. Top-Level Onboarding, Help, And Product Surface

#### What already exists

- README Quick Start is solid for users who are already comfortable.
- `new-project --minimal` already exists.
- `/gpd:help` already exists and the full help surface is rich.
- Runtime command differences are centralized in the runtime catalog and adapters.

#### What is only partial

- These capabilities are split across:
  - README
  - runtime command docs
  - workflow specs
  - install summary
  - statusline and notify
- Help is more complete than discoverable.

#### What is missing

- No single top-level entry menu.
- No explicit beginner path versus advanced path.
- No consistent "if you are new / if you are returning / if you are lost" routing.
- No canonical runtime-capability page generated from the runtime catalog.
- The distinction between runtime commands and local `gpd` utility CLI is still too implicit.

#### Plan

1. Make default `/gpd:help` state-aware and action-oriented.
   - It should always foreground:
     - start new project
     - map existing work
     - resume work
     - configure defaults
     - ask what is next
2. Rewrite README Quick Start into four explicit lanes:
   - first install
   - new project
   - existing project
   - returning to work
3. Promote `new-project --minimal`.
   - This is the most direct answer to low-tech-user friction and should be visible immediately.
4. Add a generated runtime capability reference.
   - Source of truth should remain runtime descriptors and adapters.
   - It should explain:
     - command syntax
     - permission behavior
     - hook support
     - startup/status support
5. Add action hints to notify/statusline.
   - Example:
     - `Resume ready -> run /gpd:resume-work`
     - `Need next step -> run /gpd:progress`
     - `Change defaults -> run /gpd:settings`

#### Primary code surfaces

- `README.md`
- `src/gpd/commands/help.md`
- `src/gpd/specs/workflows/help.md`
- `src/gpd/commands/new-project.md`
- `src/gpd/specs/workflows/new-project.md`
- `src/gpd/adapters/runtime_catalog.json`
- `src/gpd/adapters/base.py`
- `src/gpd/hooks/statusline.py`
- `src/gpd/hooks/notify.py`

#### Acceptance criteria

- A non-expert user can identify the right starting command without external help.
- Returning users see `resume-work` as a first-class top-level action.
- Runtime differences are visible in one canonical place instead of scattered notes.

## Sequenced Delivery Plan

### Phase 1: Surface Existing Capabilities

Goal: fix the discoverability problem before adding new infrastructure.

Deliverables:

- state-aware default help
- clearer README Quick Start
- install summary with approval/relaunch guidance
- early surfacing of `settings`, `set-profile`, `resume-work`, `new-project --minimal`
- runtime capability reference page

Why first:

- Highest leverage
- Low implementation risk
- Avoids building duplicate features that already exist

### Phase 2: Machine Readiness And Overnight Readiness

Goal: make clean-machine setup and unattended use predictable.

Deliverables:

- `doctor` or `setup-check` machine readiness
- runtime launcher/auth probes
- paper-toolchain preflight
- runtime-ready / overnight-ready status surface
- advanced settings exposure for unattended budgets

Why second:

- This is the biggest gap between current internals and the collaborator's lived experience.

### Phase 3: Returning-User Experience

Goal: make recovery and resume obvious after restarts, pauses, and interruptions.

Deliverables:

- recent-session picker
- enriched session metadata
- startup recovery hints
- aligned docs for `resume-work` vs `progress` vs `suggest-next`

Why third:

- Strong existing internals make this mostly a surfacing and aggregation task.

### Phase 4: Long-Running Execution Visibility

Goal: make active work legible and diagnosable.

Deliverables:

- `gpd execution show`
- heartbeat and stale-progress state
- stuck-state propagation
- wave/parallel counters
- statusline/notify upgrades

Why fourth:

- Requires some schema evolution but builds naturally on the observability work already in place.

### Phase 5: Cost Transparency And Budget Controls

Goal: make spend a conscious user choice instead of a surprise.

Deliverables:

- model-status inspection
- beginner-facing budget modes
- onboarding cost bands
- optional soft budget warnings

Why fifth:

- The profile system already exists, but clear cost messaging should be added after top-level onboarding is simplified.

### Phase 6: Tangents, Branching, And Interrupt Ergonomics

Goal: make higher-level research steering easier during live execution.

Deliverables:

- tangent proposal / approval state
- structured stuck deviation UX
- interrupt-now / checkpoint-now support
- branch/tangent comparison guidance connected to live state

Why sixth:

- This is valuable, but it should be built on top of improved observability and resume UX.

## Test Strategy

Every workstream should land with both behavior tests and product-surface tests.

### Product-surface tests

- README consistency tests
- help prompt wiring tests
- install summary tests
- settings prompt wiring tests
- runtime capability documentation tests

Likely files:

- `tests/test_release_consistency.py`
- `tests/core/test_prompt_wiring.py`
- `tests/core/test_prompt_cli_consistency.py`
- `tests/core/test_cli_install.py`

### Machine-readiness tests

- bootstrap tests
- health/doctor tests
- runtime probe tests
- LaTeX detection tests

Likely files:

- `tests/test_bootstrap_installer.py`
- `tests/core/test_health.py`
- `tests/hooks/test_runtime_detect.py`
- `tests/test_latex_detection.py`

### Runtime approval tests

- adapter permission sync/status tests
- CLI `permissions` tests
- install summary / relaunch messaging tests

Likely files:

- `tests/adapters/test_claude_code.py`
- `tests/adapters/test_codex.py`
- `tests/adapters/test_gemini.py`
- `tests/adapters/test_opencode.py`
- `tests/test_cli_integration.py`

### Resume and observability tests

- recent-session listing and ranking
- session metadata enrichment
- `execution show`
- stale/stuck/heartbeat transitions
- statusline and notify rendering

Likely files:

- `tests/core/test_observability.py`
- `tests/core/test_resume_runtime.py`
- `tests/core/test_context.py`
- `tests/hooks/test_statusline.py`
- `tests/hooks/test_notify.py`

## Deferred Or Explicitly Not First-Wave

- SMS/mobile approval workflow
- fully hosted or managed GPD product
- aggressive OS-level package installation across all platforms
- hard spend enforcement that depends on vendor telemetry not currently exposed
- runtime interrupt semantics that require provider-native support beyond what hooks can reliably see

These are valid future directions, but they are not the best first response to the transcript. The fastest path to materially improving the collaborator experience is to expose the machinery GPD already has, then fill the concrete operational gaps around readiness, visibility, and resume.

## Recommended Immediate Start

If we want the shortest path to user-visible improvement, the first implementation batch should be:

1. Rewrite Quick Start and default help around `new-project`, `map-research`, `resume-work`, `settings`, and `new-project --minimal`.
2. Add install-summary guidance for permission alignment and relaunch/wrapper requirements.
3. Add a real machine-readiness check.
4. Add a recent-session picker.
5. Add `gpd execution show` plus stale/stuck groundwork.

That sequence addresses the main pain in the transcript without waiting for deep runtime changes.

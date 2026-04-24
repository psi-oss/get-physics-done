<purpose>
Interactive configuration of autonomy, unattended execution budgets, GPD workflow agents (research, plan_checker, verifier), research profile selection, qualitative model-cost posture, runtime-specific tier model overrides, `execution.review_cadence`, git branching, and runtime-permission sync guidance. `gpd:settings` is the primary guided entrypoint for unattended-use setup. Recommend `Supervised` as the default that matches the advisor cadence; use `Balanced` when the user wants a lighter checkpoint pace for unattended runs, or YOLO for maximum speed. Use `gpd:set-tier-models` when the user only wants the narrow direct path for `tier-1` / `tier-2` / `tier-3` model ids. Updates `GPD/config.json` with user preferences including model profile, optional `model_overrides`, workflow toggles, execution cadence, and branching strategy.
</purpose>

<preset_guidance>
Workflow presets are bundles over the existing config keys only; they do not add a separate persisted preset block. Do not create, persist, or infer a separate `preset` block in `GPD/config.json`.

When a preset is selected, resolve it into the current knobs:

- `autonomy`
- `research_mode`
- `execution.review_cadence`
- `parallelization`
- `planning.commit_docs`
- `workflow.research`
- `workflow.plan_checker`
- `workflow.verifier`
- `model_profile`
- Existing `model_overrides` should remain unchanged unless the user explicitly edits tier overrides later in this same settings flow.

Current preset catalog:

- `core-research` — recommended supervised default for most projects
- `theory` — derivation-heavy workflow with `model_profile=deep-theory`
- `numerics` — computation-heavy workflow with `model_profile=numerical`
- `publication-manuscript` — paper-writing workflow with `model_profile=paper-writing`; `paper-build` remains the manuscript build contract, while LaTeX readiness still drives readiness for `write-paper` / `peer-review` and can degrade or block `paper-build` / `arxiv-submission`
- `full-research` — core research defaults with publication readiness tracked alongside them; `paper-build` still defines the manuscript build contract

Preset application must be explicit and previewable. Show the resolved knobs first, then ask whether to apply the bundle or return to the detailed questions. Do not create or persist a separate preset block.
</preset_guidance>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="ensure_and_load_config">
Ensure config exists and load current state:

```bash
gpd config ensure-section
# Compatibility note for installer text checks:
# INIT=$(gpd --raw init progress --include state,config)
INIT=$(gpd --raw init progress --include state,config --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Creates `GPD/config.json` with defaults if missing and loads current config values.
</step>

<step name="read_current">
```bash
cat GPD/config.json
```

Parse current values (default to `true` / first option if not present):

- `autonomy` -- human-in-the-loop level: `"supervised"` (default), `"balanced"`, `"yolo"`
- `research_mode` -- research strategy: `"explore"`, `"balanced"` (default), `"exploit"`, `"adaptive"`
- `model_overrides` -- optional runtime-scoped concrete model mapping for `tier-1`, `tier-2`, `tier-3`
- `workflow.research` -- spawn researcher during plan-phase
- `workflow.plan_checker` -- spawn plan checker during plan-phase
- `workflow.verifier` -- spawn verifier during execute-phase (this does NOT disable mandatory proof red-teaming for `proof_obligation` work)
- `execution.review_cadence` -- execution review density: `"dense"` (default), `"adaptive"`, `"sparse"`
- `execution.max_unattended_minutes_per_plan` -- wall-clock budget before a bounded continuation should be created
- `execution.project_usd_budget` -- optional advisory USD budget for the whole current workspace / project
- `execution.session_usd_budget` -- optional advisory USD budget for the current active session
- `execution.checkpoint_after_n_tasks` -- task budget before a bounded continuation should be created
- `planning.commit_docs` -- whether planning artifacts are committed to git (default: `true`)
- `parallelization` -- execute wave plans in parallel (default: `true`)
- `model_profile` -- which agent model profile to use (default: `review`)
- `model-cost posture` is a qualitative guidance layer only; it maps onto the existing `model_profile` and `model_overrides` choices and does not add a new persisted config key.
- Optional USD budget guardrails are advisory only; `gpd cost` evaluates them, and missing telemetry keeps the result partial or estimated rather than exact.
- `git.branching_strategy` -- branching approach (default: `"none"`)

`research_mode` controls breadth vs focus only. It does **not** by itself authorize git-backed hypothesis branches, branch-like alternative plans, or side investigations; those still require an explicit tangent decision.

`git.branching_strategy` is separate from tangent handling. It controls the normal git branch naming policy for approved phase/milestone work, not whether GPD may silently create hypothesis branches.

`execution.review_cadence` is independent of `model_profile` and `research_mode`: it controls bounded review stop density, not agent tiering or verification rigor. Sparse cadence does not waive proof red-teaming for proof-bearing work.

Project conventions do **not** live in `GPD/config.json`. Do not invent or preserve a `physics` section here. Unit systems, metric signatures, Fourier conventions, and other notation choices belong in `GPD/CONVENTIONS.md` and `GPD/state.json` via `gpd convention set`.
  </step>

<step name="determine_runtime_for_model_overrides">
Infer the active runtime before prompting for explicit model IDs.

Use the current command syntax, tool names, environment, and local runtime config directories to infer the active runtime identifier for this install. For GPD-owned model resolution surfaces, prefer the runtime with a concrete GPD install when a higher-priority runtime appears active but is not actually installed for this workspace.

If the runtime is still ambiguous, ask the user which runtime they want to configure before continuing with model override questions.

If `model_overrides.<runtime>` already exists, surface the current `tier-1` / `tier-2` / `tier-3` values when presenting the settings form.
</step>

<step name="present_settings">

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

Treat this as the primary guided unattended-use flow: explain that autonomy, unattended budgets, runtime permission sync, and conservative preset bundles all live here. GPD is a scalpel, not an autopilot — `Supervised` is the default and matches the advisor/graduate-student cadence: trust the execution, but stay in the loop to verify and redirect. Point users at `Balanced` once they have built intuition for GPD's boundary.

**Checkpoint keystrokes.** Most supervised checkpoints render a one-line summary and resume with `[Y/n/e]`: press **Enter** (or `Y`) to accept the recommended action, `n` to reject, `e` to edit or provide freeform feedback. Enter always means "accept what I just saw." A handful of physics-bearing or destructive checkpoints intentionally do not collapse to a single keystroke (convention lock, destructive rails, blocker triage, claim↔deliverable precheck, first-result gate after firing) — see `specs/references/orchestration/checkpoint-ux-convention.md`.

Teach one coherent posture-to-inspection loop:

- choose a qualitative posture first (`Max Quality`, `Balanced`, `Budget-aware`)
- use that posture to decide whether to keep runtime defaults or pin explicit tier model strings
- use `gpd cost` after runs to inspect recorded local usage / cost, optional USD budget guardrails, and the current profile tier mix instead of treating posture labels as billing truth
- do not present posture labels or `gpd cost` as provider billing truth or spend enforcement

If the user asks for a preset, map it onto the existing knobs above. Preview the changed knobs first, then ask for an explicit apply or customize choice. Do not add a new persisted config section or install step.

For normal-terminal follow-up around these settings:

- use `gpd --help` when you need the broader local CLI entrypoint
- use `gpd validate unattended-readiness --runtime <runtime> --autonomy <mode>` for the unattended or overnight verdict after autonomy and permissions changes
- use `gpd permissions sync --runtime <runtime> --autonomy <mode>` when the runtime-owned permission settings need explicit alignment
- use `gpd cost` after runs for advisory local usage / cost, optional USD budget guardrails, and the current profile tier mix

Broader local reference surfaces stay outside this settings-specific follow-up list: use `gpd doctor` for install and runtime-local readiness, `gpd integrations status wolfram` for the shared optional Wolfram integration config that stays separate from a local Mathematica install, and `gpd validate plan-preflight <PLAN.md>` for plan readiness rather than a settings change.

Before the detailed question list, offer a compact preset chooser when the user wants a starter bundle:

- Core research (Recommended): preview the balanced default bundle over the existing knobs, then apply or customize
- Theory: preview the derivation-heavy bundle over the existing knobs, then apply or customize
- Numerics: preview the computation-heavy bundle over the existing knobs, then apply or customize
- Publication / manuscript: preview the paper-writing bundle over the existing knobs, then apply or customize
- Full research: preview the core-research-plus-publication-readiness bundle over the existing knobs, then apply or customize
- Customize settings: skip the preset and proceed to the detailed questions below

Use ask_user with current values pre-selected:

```
ask_user([
  {
    question: "How much autonomy should the AI have? Supervised is the default and matches the advisor cadence — frequent checkpoints let you verify and redirect early. Balanced is for users who have built intuition for GPD's boundary. YOLO only stops on hard failures after runtime permissions are synced.",
    header: "Autonomy",
    multiSelect: false,
    options: [
      { label: "Supervised (Recommended)", description: "You carry the veto; GPD carries the task. Checkpoint at every physics-bearing decision so you can redirect early. Default cadence for new projects." },
      { label: "Balanced", description: "Lighter checkpoint cadence for users who have built intuition for GPD's boundary. AI handles routine work and pauses on important physics decisions, ambiguities, blockers, or scope changes." },
      { label: "YOLO", description: "Fastest mode. AI auto-approves checkpoints, syncs the runtime to its most autonomous permission mode when supported, and only stops on hard failures." }
    ]
  },
  {
    question: "Research strategy?",
    header: "Research Mode",
    multiSelect: false,
    options: [
      { label: "Explore", description: "Broad literature search, compare multiple viable approaches, and surface tangent decisions explicitly before any branch or side investigation." },
      { label: "Balanced (Recommended)", description: "Standard: plan one approach, execute, verify, iterate" },
      { label: "Exploit", description: "Focused execution of known methodology. Suppress optional tangents unless the user explicitly requests them or the current approach is blocked." },
      { label: "Adaptive", description: "Start broad enough to compare viable approaches, keep tangents explicit, then narrow only after decisive evidence locks the method." }
    ]
  },
  {
    question: "Which research profile for agents?",
    header: "Research Profile",
    multiSelect: false,
    options: [
      { label: "Deep Theory", description: "Rigorous derivations, formal proofs, exact results (highest cost)" },
      { label: "Numerical", description: "Computational implementation, optimization, convergence" },
      { label: "Exploratory", description: "Rapid prototyping, hypothesis testing, parameter scanning" },
      { label: "Review (Recommended)", description: "Critical assessment, error checking, literature comparison (default)" },
      { label: "Paper Writing", description: "LaTeX production, figures, narrative flow" }
    ]
  },
  {
    question: "What model-cost posture should GPD optimize for?",
    header: "Model Cost Posture",
    multiSelect: false,
    options: [
      { label: "Max Quality", description: "Favor the strongest acceptable runtime-native models. Use explicit tier overrides only when you already know the exact ids you want." },
      { label: "Balanced (Recommended)", description: "Keep the default `review` profile guidance and runtime defaults unless there is a concrete reason to pin tier models." },
      { label: "Budget-aware", description: "Prefer runtime defaults and avoid explicit tier pinning unless it clearly improves the result for this runtime." }
    ]
  },
  {
    question: "How should GPD handle concrete tier models for the active runtime?",
    header: "Tier Models",
    multiSelect: false,
    options: [
      { label: "Leave current setting unchanged", description: "Keep the current runtime-specific tier override map exactly as-is" },
      { label: "Use runtime defaults", description: "Do not pin model IDs for this runtime; GPD will omit the model parameter unless another override exists" },
      { label: "Configure explicit tier models", description: "Step-by-step setup for runtime-specific tier-1, tier-2, and tier-3 model strings" }
    ]
  },
  {
    question: "Spawn Plan Researcher? (researches domain before planning)",
    header: "Research",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Research phase goals before planning" },
      { label: "No", description: "Skip research, plan directly" }
    ]
  },
  {
    question: "Spawn Plan Checker? (verifies plans before execution)",
    header: "Plan Check",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Verify plans meet phase goals" },
      { label: "No", description: "Skip plan verification" }
    ]
  },
	{
	    question: "Spawn Execution Verifier? (verifies phase completion)",
	    header: "Verifier",
	    multiSelect: false,
	    options: [
	      { label: "Yes", description: "Verify contract targets after execution" },
	      { label: "No", description: "Skip only the generic post-execution verifier. Mandatory proof red-teaming for proof-bearing or `proof_obligation` work still runs." }
	    ]
	  },
  {
    question: "How aggressively should execution inject review gates?",
    header: "Cadence",
    multiSelect: false,
    options: [
	      { label: "Dense (Recommended)", description: "Every wave gates on its first load-bearing result (and on any `result/produce|log` event) before fan-out. The first-result gate and pre-fanout review are forced regardless of the risk classifier." },
	      { label: "Adaptive", description: "Inject first-result and risky-fanout gates automatically while letting clean segments continue." },
	      { label: "Sparse", description: "Fewest review stops, but required correctness gates still run. Sparse mode does not waive proof red-teaming for proof-bearing work." }
	    ]
	  },
  {
    question: "Should planning artifacts be committed to git?",
    header: "Planning Commit Docs",
    multiSelect: false,
    options: [
      { label: "Commit planning docs", description: "Set planning.commit_docs=true so planning artifacts are committed normally." },
      { label: "Keep planning docs local-only", description: "Set planning.commit_docs=false so planning artifacts stay uncommitted." }
    ]
  },
  {
    question: "Execute plans within a wave in parallel?",
    header: "Parallel",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Plans in the same wave run concurrently via parallel task() calls" },
      { label: "No", description: "Plans execute sequentially within each wave" }
    ]
  },
  {
    question: "Git branching strategy?",
    header: "Branching",
    multiSelect: false,
    options: [
      { label: "none (Recommended)", description: "Commit directly to current branch" },
      { label: "per-phase", description: "Create branch for each phase (gpd/phase-{N}-{name})" },
      { label: "per-milestone", description: "Create branch for entire milestone (gpd/{version}-{name})" }
    ]
  }
])
```

After the ask_user responses are collected, ask one compact inline follow-up for unattended execution budgets using the current values as defaults:

- `execution.max_unattended_minutes_per_plan`
- `execution.max_unattended_minutes_per_wave`

Explain that these budgets bound how long GPD should keep running before it creates a continuation or another review stop. If the user is unsure, preserve the current values.

Then ask one compact inline follow-up for optional advisory USD budget guardrails using the current values as defaults:

- `execution.project_usd_budget`
- `execution.session_usd_budget`

Explain that these are optional read-only guardrails checked by `gpd cost` against recorded machine-local USD telemetry. They are advisory only, may stay partial or estimated when telemetry is missing, and never stop work automatically. If the user is unsure, preserve the current values. Blank / `none` should clear the corresponding USD budget.

</step>

<step name="configure_model_overrides">
After the main settings answers are collected, handle concrete tier model overrides for the active runtime:

- If the user chose **Leave current setting unchanged**, preserve `model_overrides.<active_runtime>` exactly as it already exists.
- If the user chose **Use runtime defaults**, clear `model_overrides.<active_runtime>` so GPD falls back to the runtime's default model behavior.
- If the user chose **Configure explicit tier models**, ask one compact freeform follow-up for the active runtime and capture values for `tier-1`, `tier-2`, and `tier-3`.

Guidance for that follow-up:

- Ask for the exact model string the active runtime accepts rather than normalizing it inside GPD.
- Preserve any provider prefixes, slash-delimited ids, brackets, or alias syntax the active runtime already uses.
- If the user already configured a non-default provider or model source for that runtime, preserve that exact identifier format.
- Prefer exact model ids when the runtime distinguishes them from interactive "auto" selection.

Suggested defaults when the user wants a recommendation:

- Prefer leaving overrides unset unless the user explicitly asks to pin concrete model ids.
- When the user does want explicit overrides, suggest exact ids already known to work in the active runtime and preserve its native identifier format.
- If the runtime routes through multiple providers, confirm the provider first before suggesting provider-native ids.

Qualitative posture guidance:

- **Balanced** is the default recommendation and should usually keep the runtime on its own defaults unless the user has a concrete reason to pin models.
- **Budget-aware** should push the flow toward runtime defaults and away from explicit tier pinning unless the user asks for a specific override.
- **Max Quality** should bias toward the strongest acceptable runtime-native model strings only when the user is already opting into explicit overrides.

Normalization rules:

- Trim surrounding whitespace only.
- Preserve case, slashes, brackets, colons, and punctuation inside custom model IDs.
- Treat blank / `runtime default` / `none` as "no override for this tier".
- Treat literal `default` as a real model alias only when the active runtime supports it and the user explicitly intends that alias, not as shorthand for "clear override".
</step>

<step name="update_config">
Merge new settings into existing config.json:

```json
{
  ...existing_config,
  "autonomy": "supervised" | "balanced" | "yolo",
  "research_mode": "explore" | "balanced" | "exploit" | "adaptive",
  "model_profile": "deep-theory" | "numerical" | "exploratory" | "review" | "paper-writing",
  "parallelization": true/false,
  "model_overrides": {
    ...existing_model_overrides_for_other_runtimes,
    "<active_runtime>": {
      "tier-1": "runtime-native model string",
      "tier-2": "runtime-native model string",
      "tier-3": "runtime-native model string"
    }
  }, // include only non-empty tier values; omit or clear <active_runtime> when using runtime defaults
  "planning": {
    "commit_docs": true/false
  },
  "workflow": {
    "research": true/false,
    "plan_checker": true/false,
    "verifier": true/false
  },
  "execution": {
    "review_cadence": "dense" | "adaptive" | "sparse",
    "max_unattended_minutes_per_plan": 15,
    "max_unattended_minutes_per_wave": 30,
    "project_usd_budget": 25.0,
    "session_usd_budget": 5.0,
    "checkpoint_after_n_tasks": 1,
    "checkpoint_after_first_load_bearing_result": true/false,
    "checkpoint_before_downstream_dependent_tasks": true/false
  },
  "git": {
    "branching_strategy": "none" | "per-phase" | "per-milestone",
    "phase_branch_template": "gpd/phase-{phase}-{slug}",
    "milestone_branch_template": "gpd/{milestone}-{slug}"
  }
}
```

Write updated config to `GPD/config.json`.

Then immediately sync runtime-owned permissions against the selected autonomy:

```bash
PERMISSIONS_SYNC=$(gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY" 2>/dev/null || true)
echo "$PERMISSIONS_SYNC"
```

Interpret the sync payload:

- Always surface `message` in the final confirmation.
- If `requires_relaunch` is `true`, surface `next_step` verbatim so the user knows whether the runtime must be restarted or relaunched through a generated wrapper command.
- If `requires_relaunch` is `true`, explicitly state that the newly selected autonomy level is not unattended-ready yet.
- If runtime detection or install resolution fails, explain that `GPD/config.json` was still updated but the runtime itself was not synchronized yet.
- This sync only updates runtime-owned permission settings; it does not validate install health or workflow/tool readiness.
</step>

<step name="confirm">
Display:

```
+-----------------------------------------------------+
  GPD >> SETTINGS UPDATED
+-----------------------------------------------------+

| Setting              | Value |
|----------------------|-------|
| Active Runtime       | {detected runtime id} |
| Research Profile     | {deep-theory/numerical/exploratory/review/paper-writing} |
| Model Cost Posture   | {Max Quality/Balanced/Budget-aware} |
| Tier Models          | {runtime default / tier-1=..., tier-2=..., tier-3=...} |
| Plan Researcher      | {On/Off} |
| Plan Checker         | {On/Off} |
| Execution Verifier   | {On/Off} |
| Review Cadence       | {Dense/Adaptive/Sparse} |
| Project USD Budget   | {none / $... advisory} |
| Session USD Budget   | {none / $... advisory} |
| Planning Commit Docs | {On/Off} |
| Parallelization      | {On/Off} |
| Git Branching        | {none/per-phase/per-milestone} |
| Runtime Permissions  | {aligned / changed / manual follow-up required} |

Terminal follow-ups for these settings: reuse the normal-terminal follow-up list from the `present_settings` step (`gpd --help`, `gpd validate unattended-readiness`, `gpd permissions sync`, `gpd cost`). Keep `gpd doctor`, `gpd integrations status wolfram`, and `gpd validate plan-preflight <PLAN.md>` as broader references outside this settings-owned follow-up list.

These settings apply to future gpd:plan-phase and gpd:execute-phase runs.

Model-cost posture is qualitative guidance only. It maps onto the existing `model_profile` and `model_overrides` decisions, not a new persisted config key, pricing system, or billing promise.

Use `gpd cost` after runs to inspect recorded local usage / cost, optional USD budget guardrails, and the current profile tier mix instead of treating posture labels as billing truth.

Optional USD budget guardrails are checked there too. They compare recorded machine-local USD against the configured project/session thresholds, stay advisory only, may remain partial or estimated when telemetry is missing, and never stop work automatically.

Concrete tier model strings are passed through to the active runtime unchanged, so they should always use that runtime's native model syntax.

Runtime sync:
- {permissions_sync.message}
- {permissions_sync.next_step if present}
- If relaunch is still required, say clearly that unattended use is not ready yet under the newly selected autonomy setting.
- `gpd permissions status --runtime <runtime> --autonomy balanced` and `gpd permissions sync --runtime <runtime> --autonomy balanced` in this workflow only handle runtime-owned permission alignment, not install validation.

Project conventions still live in `GPD/CONVENTIONS.md` and `GPD/state.json` (`convention_lock`), not in `GPD/config.json`.

Quick commands:
- gpd:set-profile <profile> -- switch research profile
- gpd:set-tier-models -- direct concrete `tier-1` / `tier-2` / `tier-3` model-id setup
- gpd:settings -- revisit interactive model/tier setup
- gpd:validate-conventions -- verify convention consistency across the project
- gpd convention set <key> <value> -- update the locked project conventions directly
- gpd:plan-phase --research -- force research
- gpd:plan-phase --skip-research -- skip research
- gpd:plan-phase --skip-verify -- skip plan check
```

</step>

<step name="runtime_guidance">
Refer to `{GPD_INSTALL_DIR}/references/tooling/runtime-config-guide.md` for:
- recommended minimal runtime configuration
- extension and skill compatibility guidance
- portable configuration patterns for multi-machine setups
- permission mode alignment with GPD autonomy settings
- troubleshooting common environment issues
</step>

</process>

<downstream_consumption>
Workflow config from `GPD/config.json` is consumed by:

- **gpd-planner / orchestrators**: Model profile, workflow toggles, and runtime-specific tier overrides
- **gpd-executor**: Review cadence, unattended budgets, and workflow verifier settings
- **gpd cost / runtime hints**: advisory USD budget guardrails for the current project/session when configured
- **gpd hooks / runtime adapters**: Runtime-specific model overrides and related execution defaults

Project conventions propagate separately through `GPD/CONVENTIONS.md` and `GPD/state.json` (`convention_lock`), where notation and unit choices remain the single source of truth for planning, execution, and verification.
</downstream_consumption>

<success_criteria>

- [ ] Current config read
- [ ] Active runtime inferred or explicitly confirmed before model override guidance
- [ ] User presented with autonomy guidance (`Supervised` recommended as the default), unattended time-budget review, optional advisory USD budget guardrails, profile, model-cost posture, runtime-specific tier-model handling, workflow toggles, review cadence, and git branching
- [ ] Config updated with model_profile, optional model_overrides, workflow, execution, and git sections
- [ ] Runtime permissions sync attempted after autonomy is written, with relaunch guidance surfaced when required
- [ ] Relaunch-required state explained as not unattended-ready yet
- [ ] No stale `physics` section written into `GPD/config.json`
- [ ] Concrete tier model strings stored in runtime-native format when the user chooses explicit overrides
- [ ] Changes confirmed to user

</success_criteria>

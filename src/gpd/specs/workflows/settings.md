<purpose>
Interactive configuration of GPD workflow agents (research, plan_checker, verifier), research profile selection, runtime-specific tier model overrides, `execution.review_cadence`, git branching, and runtime-permission sync guidance. Updates `GPD/config.json` with user preferences including model profile, optional `model_overrides`, workflow toggles, execution cadence, and branching strategy.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="ensure_and_load_config">
Ensure config exists and load current state:

```bash
gpd config ensure-section
INIT=$(gpd init progress --include state,config)
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

- `autonomy` -- human-in-the-loop level: `"supervised"`, `"balanced"` (default), `"yolo"`
- `research_mode` -- research strategy: `"explore"`, `"balanced"` (default), `"exploit"`, `"adaptive"`
- `model_overrides` -- optional runtime-scoped concrete model mapping for `tier-1`, `tier-2`, `tier-3`
- `workflow.research` -- spawn researcher during plan-phase
- `workflow.plan_checker` -- spawn plan checker during plan-phase
- `workflow.verifier` -- spawn verifier during execute-phase
- `execution.review_cadence` -- execution review density: `"dense"`, `"adaptive"` (default), `"sparse"`
- `execution.max_unattended_minutes_per_plan` -- wall-clock budget before a bounded continuation should be created
- `execution.checkpoint_after_n_tasks` -- task budget before a bounded continuation should be created
- `planning.commit_docs` -- whether planning artifacts are committed to git (default: `true`)
- `parallelization` -- execute wave plans in parallel (default: `true`)
- `model_profile` -- which agent model profile to use (default: `review`)
- `git.branching_strategy` -- branching approach (default: `"none"`)

`execution.review_cadence` is independent of `model_profile` and `research_mode`: it controls bounded review stop density, not agent tiering or verification rigor.

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

Use ask_user with current values pre-selected:

```
ask_user([
  {
    question: "How much autonomy should the AI have? Supervised pauses constantly, Balanced handles routine work but still pauses on important physics or scope decisions, and YOLO only stops on hard failures after runtime permissions are synced.",
    header: "Autonomy",
    multiSelect: false,
    options: [
      { label: "Supervised", description: "Checkpoint after every important step. You approve each physics-bearing move." },
      { label: "Balanced (Recommended)", description: "AI handles routine work and pauses on important physics decisions, ambiguities, blockers, or scope changes." },
      { label: "YOLO", description: "Fastest mode. AI auto-approves checkpoints, syncs the runtime to its most autonomous permission mode when supported, and only stops on hard failures." }
    ]
  },
  {
    question: "Research strategy?",
    header: "Research Mode",
    multiSelect: false,
    options: [
      { label: "Explore", description: "Broad literature search, multiple hypothesis branches, compare approaches" },
      { label: "Balanced (Recommended)", description: "Standard: plan one approach, execute, verify, iterate" },
      { label: "Exploit", description: "Focused execution of known methodology. Minimal branching, fast convergence." },
      { label: "Adaptive", description: "Start exploring, auto-switch to exploit once approach is validated" }
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
      { label: "No", description: "Skip post-execution verification" }
    ]
  },
  {
    question: "How aggressively should execution inject review gates?",
    header: "Cadence",
    multiSelect: false,
    options: [
      { label: "Adaptive (Recommended)", description: "Inject first-result and risky-fanout gates automatically while letting clean segments continue. Independent of profile choice." },
      { label: "Dense", description: "Frequent bounded review points for high-risk or high-touch work." },
      { label: "Sparse", description: "Fewest review stops, but required correctness gates still run." }
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
    "max_unattended_minutes_per_plan": 45,
    "max_unattended_minutes_per_wave": 90,
    "checkpoint_after_n_tasks": 3,
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
- If runtime detection or install resolution fails, explain that `GPD/config.json` was still updated but the runtime itself was not synchronized yet.
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
| Tier Models          | {runtime default / tier-1=..., tier-2=..., tier-3=...} |
| Plan Researcher      | {On/Off} |
| Plan Checker         | {On/Off} |
| Execution Verifier   | {On/Off} |
| Review Cadence       | {Dense/Adaptive/Sparse} |
| Planning Commit Docs | {On/Off} |
| Parallelization      | {On/Off} |
| Git Branching        | {none/per-phase/per-milestone} |
| Runtime Permissions  | {aligned / changed / manual follow-up required} |

These settings apply to future /gpd:plan-phase and /gpd:execute-phase runs.

Concrete tier model strings are passed through to the active runtime unchanged, so they should always use that runtime's native model syntax.

Runtime sync:
- {permissions_sync.message}
- {permissions_sync.next_step if present}

Project conventions still live in `GPD/CONVENTIONS.md` and `GPD/state.json` (`convention_lock`), not in `GPD/config.json`.

Quick commands:
- /gpd:set-profile <profile> -- switch research profile
- /gpd:settings -- revisit interactive model/tier setup
- /gpd:validate-conventions -- verify convention consistency across the project
- gpd convention set <key> <value> -- update the locked project conventions directly
- /gpd:plan-phase --research -- force research
- /gpd:plan-phase --skip-research -- skip research
- /gpd:plan-phase --skip-verify -- skip plan check
```

</step>

</process>

<downstream_consumption>
Workflow config from `GPD/config.json` is consumed by:

- **gpd-planner / orchestrators**: Model profile, workflow toggles, and runtime-specific tier overrides
- **gpd-executor**: Review cadence, unattended budgets, and workflow verifier settings
- **gpd hooks / runtime adapters**: Runtime-specific model overrides and related execution defaults

Project conventions propagate separately through `GPD/CONVENTIONS.md` and `GPD/state.json` (`convention_lock`), where notation and unit choices remain the single source of truth for planning, execution, and verification.
</downstream_consumption>

<success_criteria>

- [ ] Current config read
- [ ] Active runtime inferred or explicitly confirmed before model override guidance
- [ ] User presented with profile, runtime-specific tier-model handling, workflow toggles, review cadence, and git branching
- [ ] Config updated with model_profile, optional model_overrides, workflow, execution, and git sections
- [ ] Runtime permissions sync attempted after autonomy is written, with relaunch guidance surfaced when required
- [ ] No stale `physics` section written into `GPD/config.json`
- [ ] Concrete tier model strings stored in runtime-native format when the user chooses explicit overrides
- [ ] Changes confirmed to user

</success_criteria>

---
name: gpd:settings
description: Configure autonomy, unattended execution budgets, runtime permission sync, workflow preset bundles, model-cost posture, runtime-specific tier model overrides, review cadence, and git preferences
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Interactive configuration of autonomy, unattended execution budgets, runtime permission sync, GPD workflow agents, workflow preset bundles, model-cost posture, runtime-specific tier model overrides, `execution.review_cadence`, and workflow/git preferences via multi-question prompt.
Workflow presets are bundles over the existing config keys only; they do not add a separate persisted preset block.

Routes to the settings workflow which handles:

- Config existence ensuring
- Current settings reading and parsing
- Interactive prompt covering autonomy mode, unattended budgets, research profile, model-cost posture, runtime-specific tier models, review cadence, and workflow/git toggles
- Optional USD budget guardrails are advisory only; they are checked by `gpd cost`, may be partial or estimated when telemetry is missing, and never stop work automatically
- Runtime permission sync status plus relaunch-readiness guidance for unattended use
- Config merging and writing
- Confirmation display with a compact local CLI bridge and quick command references
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/settings.md
</execution_context>

<process>
**Follow the settings workflow** from `@{GPD_INSTALL_DIR}/workflows/settings.md`.

The workflow handles all logic including:

1. Config file creation with defaults if missing
2. Current config reading
3. Primary guided unattended-use settings presentation with pre-selection, covering:
   - **Preset chooser**: preview the changed knobs first, then apply it explicitly or fall back to detailed customization
   - **Autonomy**: supervised / balanced / yolo
   - **Balanced (Recommended)**: best default for most unattended runs because it keeps work moving but still pauses on important physics, scope, or blocker decisions
   - **Unattended budgets**: review bounded continuation limits such as per-plan and per-wave unattended minutes
   - **Optional USD budget guardrails**: advisory-only project/session thresholds checked by `gpd cost`; never enforcement or auto-stop
   - **Runtime permission sync**: align runtime-owned approvals with the chosen autonomy level
   - **Research profile**: deep-theory / numerical / exploratory / review / paper-writing
   - **Workflow presets**: bundle the existing config keys above; preview the changed knobs first, then apply explicitly or customize further. Use `gpd presets list`, `gpd presets show <preset>`, or `gpd presets apply <preset> [--dry-run]` from your normal terminal
   - **Model cost posture**: Max quality / Balanced / Budget-aware; advisory only and not a persisted config key
   - **Tier models for the active runtime**: leave unchanged / use runtime defaults / configure explicit tier-1, tier-2, tier-3 model strings
   - **Plan researcher**: on / off
   - **Plan checker**: on / off
   - **Execution verifier**: on / off
   - **Review cadence** (`execution.review_cadence`): dense / adaptive / sparse
   - **Parallel execution**: on / off
   - **Git branching**: none / per-phase / per-milestone
4. Runtime-aware model guidance when explicit tier models are requested:
   - Ask for the exact model string the active runtime accepts
   - Preserve provider prefixes, slash-delimited ids, brackets, and alias syntax already used by that runtime
   - Prefer runtime defaults unless the user explicitly wants pinned tier overrides
   - Treat `Balanced` as the default qualitative posture, `Budget-aware` as a prompt to keep runtime defaults and avoid pinning overrides unless needed, and `Max quality` as a prompt to favor the strongest acceptable runtime-native models when the user is already ready to pin them
   - When the runtime routes through multiple providers, confirm the provider before suggesting provider-native ids
5. Answer parsing and config merging
6. File writing plus runtime permission synchronization
7. Confirmation display with current settings summary, quick command references, and explicit "not unattended-ready yet" messaging when relaunch is still required

Project conventions are managed separately in `GPD/CONVENTIONS.md` and `GPD/state.json` (`convention_lock`). The settings workflow must not invent a `physics` block in `GPD/config.json`; use `gpd convention set` or `/gpd:validate-conventions` for convention work.
   </process>

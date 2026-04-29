<purpose>
Directly configure concrete runtime-native model IDs for `tier-1`, `tier-2`, and `tier-3` for the active runtime only.

Keep this workflow intentionally narrow. It updates `model_overrides.<runtime>` and nothing else.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="ensure_and_load_config">
Ensure config exists and load current state:

```bash
gpd config ensure-section
INIT=$(gpd --raw init progress --include state,config --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

This creates `GPD/config.json` with defaults if missing and loads current config values.
</step>

<step name="determine_runtime">
Infer the active runtime before prompting for model IDs.

Apply the shared active-runtime rule from `gpd:settings`: infer from command syntax, tool names, environment, and local runtime config directories; prefer a concrete GPD install over an uninstalled higher-priority hint.

If the runtime is still ambiguous, ask the user which runtime they want to configure before continuing.

If `model_overrides.<runtime>` already exists, surface the current `tier-1` / `tier-2` / `tier-3` values before asking what to change.
</step>

<step name="explain_scope_and_tradeoff">
Explain the command in one compact block before asking for choices:

- `gpd:set-profile` changes the abstract research profile and agent tier assignments.
- `gpd:set-tier-models` changes only the concrete runtime-native model IDs behind `tier-1`, `tier-2`, and `tier-3`.
- `gpd:settings` is the broader unattended/configuration flow when the user also wants autonomy, review cadence, workflow toggles, budgets, or git settings.

Explain the tier tradeoff plainly:

- `tier-1` — strongest reasoning / highest capability, usually highest cost
- `tier-2` — balanced default
- `tier-3` — fastest / most economical

Also say clearly:

- If the user is unsure, recommend runtime defaults rather than pinning explicit IDs.
- These tier labels are capability/cost guidance, not a billing promise.
- Use `gpd cost` after runs for the read-only recorded local usage / cost view.
</step>

<step name="present_choice">

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

Use ask_user with the active runtime surfaced in the question:

```
ask_user([
  {
    question: "How should GPD configure concrete tier models for the active runtime?",
    header: "Tier Models",
    multiSelect: false,
    options: [
      { label: "Use runtime defaults (Recommended)", description: "Simplest and safest starting point. Clears explicit tier overrides so the runtime chooses its own models." },
      { label: "Leave current setting unchanged", description: "Keep the current runtime-specific tier override map exactly as-is." },
      { label: "Pin exact tier models", description: "Enter explicit runtime-native model strings for tier-1, tier-2, and tier-3." }
    ]
  }
])
```

If the user chooses **Pin exact tier models**, ask one compact freeform follow-up for `tier-1`, `tier-2`, and `tier-3`.

Guidance for that follow-up:

- Ask for the exact model string the active runtime accepts.
- Preserve provider prefixes, slash-delimited ids, bracket suffixes, aliases, colons, and other runtime-native punctuation exactly.
- Trim surrounding whitespace only.
- Treat blank / `runtime default` / `none` as "no override for this tier".
- Treat literal `default` as a real model alias only when the active runtime supports it and the user explicitly intends that alias.

Runtime-native examples are intentionally not hard-coded here. Ask for the exact string accepted by the active runtime and preserve it unchanged; if the user is unsure, recommend keeping runtime defaults and checking the runtime/provider's own model documentation.
</step>

<step name="update_config">
Merge the result into `GPD/config.json`:

- If the user chose **Use runtime defaults (Recommended)**, clear `model_overrides.<active_runtime>`.
- If the user chose **Leave current setting unchanged**, preserve `model_overrides.<active_runtime>` exactly as-is.
- If the user chose **Pin exact tier models**, write only the non-empty tier values under `model_overrides.<active_runtime>`.
- Preserve `model_overrides` for all other runtimes.

The resulting config shape is:

```json
{
  ...existing_config,
  "model_overrides": {
    ...existing_model_overrides_for_other_runtimes,
    "<active_runtime>": {
      "tier-1": "runtime-native model string",
      "tier-2": "runtime-native model string",
      "tier-3": "runtime-native model string"
    }
  }
}
```

If all three tiers are cleared for the active runtime, omit `model_overrides.<active_runtime>` entirely.

Do **not** change:

- `model_profile`
- `autonomy`
- `research_mode`
- `execution.review_cadence`
- workflow toggles
- budgets
- branching strategy
</step>

<step name="confirm">
Display a short confirmation like:

```
+-----------------------------------------------------+
  GPD >> TIER MODELS UPDATED
+-----------------------------------------------------+

| Setting          | Value |
|------------------|-------|
| Active Runtime   | {detected runtime id} |
| Tier Models      | {runtime default / tier-1=..., tier-2=..., tier-3=...} |
| Research Profile | {unchanged current model_profile} |
| Other Settings   | unchanged |

Meaning:
- tier-1 = highest capability / usually highest cost
- tier-2 = balanced default
- tier-3 = fastest / most economical

Use `gpd:set-profile <profile>` to change abstract tier assignments.
Use `gpd:settings` when you want broader unattended/configuration changes too.

Useful checks from your normal terminal:
- `gpd resolve-tier gpd-planner`
- `gpd resolve-model gpd-planner --runtime <runtime>`
- `gpd cost`
```

State clearly that future agent spawns in this project will use the updated runtime-specific tier overrides when `gpd resolve-model` resolves to them.
</step>

</process>

<success_criteria>
- [ ] Current config read
- [ ] Active runtime inferred or explicitly confirmed before model override guidance
- [ ] User shown the plain-language cost/quality meaning of `tier-1`, `tier-2`, and `tier-3`
- [ ] Config updated only through `model_overrides.<runtime>`
- [ ] Other config sections left unchanged
- [ ] Runtime-native model strings preserved exactly except for surrounding whitespace trimming
- [ ] Confirmation distinguishes `gpd:set-profile`, `gpd:set-tier-models`, and `gpd:settings`
</success_criteria>

---
name: gpd:set-tier-models
description: Configure concrete tier-1/tier-2/tier-3 model IDs for the active runtime
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
---


<objective>
Set the concrete runtime-native model strings GPD should use for `tier-1`, `tier-2`, and `tier-3`.

Keep this command narrow and direct:

- It changes only `model_overrides.<runtime>` in `GPD/config.json`
- It does **not** change `model_profile`, autonomy, review cadence, budgets, workflow toggles, or git settings
- Use `gpd:set-profile` when you want to change the abstract research profile
- Use `gpd:settings` when you want the broader unattended/configuration flow

Explain the capability/cost tradeoff plainly:

- `tier-1` = strongest reasoning, usually highest cost
- `tier-2` = balanced default
- `tier-3` = fastest / most economical

Recommend runtime defaults when the user is unsure.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/set-tier-models.md
</execution_context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

2. Keep the flow limited to the active runtime's concrete tier model mapping.
3. Preserve runtime-native model string syntax exactly; do not normalize provider-specific ids.
4. Keep the distinction explicit:
   - `gpd:set-profile` = abstract profile / agent tier behavior
   - `gpd:set-tier-models` = concrete runtime model ids for `tier-1`, `tier-2`, `tier-3`
   - `gpd:settings` = broad unattended/configuration bundle
</process>

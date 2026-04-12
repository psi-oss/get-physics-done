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


<objective>
Run the guided GPD settings flow.

Keep this wrapper thin: follow the workflow and let it own option vocabulary,
user-facing explanations, and confirmation copy.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/settings.md
</execution_context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

2. Do not invent a parallel settings flow or duplicate the workflow's option-by-option guidance here.
3. Do not create separate `preset` or `physics` blocks in `GPD/config.json`; the workflow owns those rules.
4. Let the workflow own preset, model-posture, tier-model, budget, permission-sync, and local CLI bridge wording.
5. Convention work stays outside settings; use `gpd convention set <key> <value>` or `gpd:validate-conventions` for project convention updates.
</process>

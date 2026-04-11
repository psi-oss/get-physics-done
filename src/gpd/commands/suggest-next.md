---
name: gpd:suggest-next
description: Suggest the most impactful next action based on current project state
context_mode: projectless
local_cli_only: true
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---


<objective>
Suggest the most impactful next action from current project state.
</objective>

<context>
@GPD/STATE.md (if present)
@GPD/ROADMAP.md (if present)
</context>

<process>
Run `gpd --raw suggest`, parse the JSON suggestions in priority order, and present the top next action with blockers and project context when present.
</process>

---
name: gpd:start
description: Choose the right first GPD action for this folder and route into the real workflow
argument-hint: "[optional short goal]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
  - ask_user
---


<objective>
Provide a beginner-friendly first-run entry point for GPD.

Inspect the current folder, show the safest next step first, then explain the
broader options in plain language. Keep the language novice-friendly, and
explain official terms the first time they appear instead of assuming prior
CLI, Git, or workflow knowledge. Do not invent a parallel onboarding state
machine and do not silently assume the user already knows which command to run.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/start.md
</execution_context>

<inline_guidance>

@{GPD_INSTALL_DIR}/references/onboarding/beginner-command-taxonomy.md

- `gpd resume` remains the local read-only current-workspace recovery snapshot
- `gpd resume --recent` remains the normal-terminal advisory recent-project picker; choose the workspace there, then `gpd:resume-work` reloads canonical state in the reopened project
- `gpd:suggest-next` is the fastest post-resume next command when you only need the next action
- `gpd:suggest-next`, `gpd:quick`, `gpd:explain`, and `gpd:help` remain separate downstream entry points

</inline_guidance>

<process>
Follow the start workflow from `@{GPD_INSTALL_DIR}/workflows/start.md` end-to-end.
Preserve the routing-first rule: detect the folder state, show plain-language
choices, then hand off to the real existing workflow instead of duplicating its
logic here.
</process>

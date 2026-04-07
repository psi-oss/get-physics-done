---
name: gpd:tour
description: Show a guided beginner walkthrough of the core GPD commands without taking action
argument-hint: "[optional short goal]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
---


<objective>
Provide a safe beginner walkthrough of the core GPD command paths.

Explain what the main commands are for, when to use each one, and how they fit
together in plain language for a first-time user. Explain advanced terms the
first time they appear instead of assuming GPD terminology, CLI familiarity, or
prior workflow knowledge. Do not create project artifacts, do not create files,
and do not silently route into another workflow.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/tour.md
</execution_context>

<inline_guidance>

- `gpd:tour` is a teaching surface, not a chooser
- `gpd:start` is the actual first-run router when the user wants the right next action
- `gpd:new-project` and `gpd:new-project --minimal` are for creating a new project
- `gpd:map-research` is for bringing an existing folder into GPD
- `gpd:resume-work` is for returning to an existing GPD project
- `gpd:progress`, `gpd:suggest-next`, `gpd:explain`, `gpd:quick`, `gpd:set-tier-models`, `gpd:settings`, and `gpd:help` are the common follow-up commands
- When you mention advanced terms such as workflow, router, project artifacts, or recovery path, explain them the first time they appear

</inline_guidance>

<process>
Follow the tour workflow from `@{GPD_INSTALL_DIR}/workflows/tour.md` end-to-end.
Keep the response instructional and self-contained. Show the main command paths
and the situations they fit, but do not hand off to another workflow or create
any artifacts.
</process>

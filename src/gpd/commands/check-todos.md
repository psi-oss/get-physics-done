---
name: gpd:check-todos
description: List pending research todos and select one to work on
argument-hint: "[area filter]"
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
---


<objective>
List pending todos, support area filtering, load selected todo context, and route to the appropriate next action.

Area filters can target research domains such as:

- "analytical" (derivations, limiting cases, dimensional checks)
- "numerical" (simulations, convergence, parameter scans)
- "validation" (comparisons with literature, consistency checks)
- "writing" (manuscript sections, figure captions, references)
- "formalism" (notation, definitions, framework setup)
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/check-todos.md
</execution_context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/check-todos.md` exactly. Let the workflow discover and inspect project state only when the current workspace has one.
   </process>

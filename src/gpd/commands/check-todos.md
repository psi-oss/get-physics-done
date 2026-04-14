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
List all pending todos, allow selection, load full context for the selected todo, and route to appropriate action.

Routes to the check-todos workflow which handles:

- Todo counting and listing with area filtering
- Interactive selection with full context loading
- Roadmap correlation checking
- Action routing (work now, add to phase, brainstorm, create phase)
- STATE.md updates and git commits

Area filters can target research domains such as:

- "analytical" (derivations, limiting cases, dimensional checks)
- "numerical" (simulations, convergence, parameter scans)
- "validation" (comparisons with literature, consistency checks)
- "writing" (manuscript sections, figure captions, references)
- "formalism" (notation, definitions, framework setup)
  </objective>

<execution_context>
@GPD/STATE.md
@GPD/ROADMAP.md
@{GPD_INSTALL_DIR}/workflows/check-todos.md
</execution_context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

The workflow handles all logic including:

1. Todo existence checking
2. Area filtering
3. Interactive listing and selection
4. Full context loading with file summaries
5. Roadmap correlation checking
6. Action offering and execution
7. STATE.md updates
8. Git commits
</process>

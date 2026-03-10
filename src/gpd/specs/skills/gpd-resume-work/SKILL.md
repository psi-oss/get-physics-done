---
name: gpd-resume-work
description: Resume research from previous session with full context restoration
requires:
  files: [".gpd/ROADMAP.md", ".gpd/STATE.md"]
allowed-tools:
  - read_file
  - shell
  - write_file
  - ask_user
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Restore complete research context and resume work seamlessly from previous session.

Routes to the resume-work workflow which handles:

- STATE.md loading (or reconstruction if missing)
- Checkpoint detection (.continue-here files)
- Incomplete work detection (PLAN without SUMMARY)
- Full awareness of where the calculation or derivation left off
- Restoration of parameter values, intermediate results, and assumptions
- Status presentation
- Context-aware next action routing
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/resume-work.md
</execution_context>

<process>
**Follow the resume-work workflow** from `@{GPD_INSTALL_DIR}/workflows/resume-work.md`.

The workflow handles all resumption logic including:

1. Project existence verification
2. STATE.md loading or reconstruction
3. Checkpoint and incomplete work detection
4. Restoration of research context:
   - Where the derivation or computation was paused
   - Parameter values and variable definitions in scope
   - Intermediate results and partial solutions
   - Approximations and assumptions active at pause time
   - Planned next steps from previous session
5. Visual status presentation
6. Context-aware option offering (checks CONTEXT.md before suggesting plan vs discuss)
7. Routing to appropriate next command
8. Session continuity updates
   </process>

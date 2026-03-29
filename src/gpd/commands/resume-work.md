---
name: gpd:resume-work
description: Resume research from previous session with full context restoration
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md", "GPD/STATE.md"]
allowed-tools:
  - file_read
  - shell
  - file_write
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Restore complete research context and resume work seamlessly from the latest canonical pause/resume handoff and live session state.

This is the in-runtime return path for the selected project. Use `gpd resume` for the current-workspace read-only recovery snapshot, `gpd resume --recent` if you need to find the workspace first, then run `/gpd:resume-work` in the reopened project. After resuming, `/gpd:suggest-next` is the fastest next command when you only need the next action.

Routes to the resume-work workflow which handles:

- STATE.md loading (or reconstruction if missing)
- Active execution checkpoint detection
- Canonical `.continue-here.md` handoff detection from pause-work session continuity
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
3. Checkpoint, canonical handoff, and incomplete work detection
4. Restoration of research context:
   - Where the derivation or computation was paused
   - Parameter values and variable definitions in scope
   - Intermediate results and partial solutions
   - Approximations and assumptions active at pause time
   - Planned next steps from previous session
5. Visual status presentation
6. Context-aware option offering (checks CONTEXT.md before suggesting plan vs discuss, using the same machine-readable resume context that powers `gpd resume`)
7. Routing to appropriate next command
8. Session continuity updates
   </process>

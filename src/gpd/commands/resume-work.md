---
name: gpd:resume-work
description: Resume research from previous session with full context restoration
context_mode: project-required
project_reentry_capable: true
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
Restore complete research context and resume work seamlessly from the latest canonical continuation state and its projected handoff surfaces.

This is the runtime recovery command for the selected project. Use `gpd resume` for the current-workspace read-only recovery snapshot, `gpd resume --recent` when you need the explicit multi-project picker, then run `/gpd:resume-work` in the reopened project. The public machine-readable resume contract is canonical-first: modern continuation fields stay at the top level, and the old `session_*`, `segment_candidates`, and related alias fields live only inside `compat_resume_surface` for compatibility. The recent-project list is advisory and machine-local; once you choose a workspace, `/gpd:resume-work` reloads that project's canonical state. If `gpd resume --recent` finds exactly one recoverable project, that can become the fast re-entry path; otherwise the project choice stays explicit. After resuming, `/gpd:suggest-next` is the fastest next command when you only need the next action.

`state.json.continuation` is the durable continuation authority; the raw `session` mirror and legacy `session_*` resume fields are compatibility-only data exposed through `compat_resume_surface`, not public top-level contract fields.

Routes to the resume-work workflow which handles:

- STATE.md loading (or reconstruction if missing)
- Active execution checkpoint detection
- Canonical `.continue-here.md` handoff detection from canonical continuation state
- Explicit recent-project re-entry when the selected project has to be rediscovered first, then reload canonical state from the selected workspace
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
3. Checkpoint, canonical continuation, and incomplete work detection
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

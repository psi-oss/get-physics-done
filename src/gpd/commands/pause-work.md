---
name: gpd:pause-work
description: Create context handoff when pausing research mid-phase
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Create `.continue-here.md` handoff file to preserve complete research state across sessions.

Routes to the pause-work workflow which handles:

- Current phase detection from recent files
- Complete state gathering (current derivation state, parameter values, intermediate results, completed work, remaining work, decisions, blockers)
- Handoff file creation with all context sections
- Git commit as WIP
- Resume instructions
  </objective>

<execution_context>
@.gpd/STATE.md
@{GPD_INSTALL_DIR}/workflows/pause-work.md
</execution_context>

<process>
**Follow the pause-work workflow** from `@{GPD_INSTALL_DIR}/workflows/pause-work.md`.

The workflow handles all logic including:

1. Phase directory detection
2. State gathering with user clarifications, including:
   - Current position in derivation or calculation
   - Parameter values and assumptions in effect
   - Intermediate results obtained so far
   - Approximations made and their justifications
   - Next steps that were planned before pausing
3. Handoff file writing with timestamp
4. Git commit
5. Confirmation with resume instructions
   </process>

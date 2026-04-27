---
name: gpd:pause-work
description: Create continuation handoff when pausing research mid-phase
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
---


<objective>
Create the canonical `.continue-here.md` continuation handoff artifact to preserve complete research state across sessions.
  </objective>

<execution_context>
@GPD/STATE.md
@{GPD_INSTALL_DIR}/workflows/pause-work.md
</execution_context>

<process>
Follow the included pause-work workflow exactly.
   </process>

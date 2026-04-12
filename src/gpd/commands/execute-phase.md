---
name: gpd:execute-phase
description: Execute all plans in a phase with wave-based parallelization
argument-hint: "<phase-number> [--gaps-only]"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md"]
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - find_files
  - search_files
  - shell
  - task
  - ask_user
---

<objective>
Execute all phase plans with wave-based parallelization.
Context budget: ~15% orchestrator, fresh context per subagent.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/execute-phase.md
</execution_context>

<context>
Phase: $ARGUMENTS

**Flags:**

- `--gaps-only` -- Execute only gap-closure plans (`gap_closure: true`). Use after `verify-work` creates fix plans.

**Review cadence:** Read `execution.review_cadence` (valid values: `dense`, `adaptive`, `sparse`) to decide required pause/review frequency.

</context>

<process>
Read `@{GPD_INSTALL_DIR}/workflows/execute-phase.md` with `file_read` first.
Follow the included workflow file exactly.
</process>

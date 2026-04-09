---
name: gpd:research-phase
description: Research how to tackle a phase (standalone - usually use gpd:plan-phase instead)
argument-hint: "[phase]"
context_mode: project-required
allowed-tools:
  - ask_user
  - file_read
  - shell
  - task
---
<objective>
Research how to tackle a phase. Use this command when you want phase-specific investigation before planning or when you need to re-research after planning is complete.

Orchestrator role: validate the phase input, then hand off to the workflow-owned staged init, typed-return routing, and artifact gating.

**Why subagent:** Fresh context keeps the phase survey scoped instead of carrying stale planning detail.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/research-phase.md
@{GPD_INSTALL_DIR}/references/orchestration/model-profile-resolution.md
</execution_context>

<context>
Phase number: $ARGUMENTS (required)

Normalize phase input before any directory lookups.
</context>

<process>
Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/research-phase.md`.
Do not duplicate init, spawn, or return routing here.
Research depth follows the workflow-owned `research_mode`.
</process>

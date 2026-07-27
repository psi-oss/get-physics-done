---
name: gpd:verify-work
description: Verify research results through physics consistency checks
argument-hint: "[phase] [--dimensional] [--limits] [--convergence] [--regression] [--all]"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md"]
review-contract:
  review_mode: review
  schema_version: 1
  required_outputs:
    - "GPD/phases/XX-name/XX-VERIFICATION.md"
  required_evidence:
    - roadmap
    - phase summaries
    - artifact files
  blocking_conditions:
    - missing project state
    - missing roadmap
    - missing phase artifacts
    - degraded review integrity
  preflight_checks:
    - command_context
    - project_state
    - roadmap
    - phase_lookup
    - phase_artifacts
    - phase_summaries
    - phase_proof_review
  required_state: phase_executed
allowed-tools:
  - file_read
  - ask_user
  - shell
  - find_files
  - search_files
  - file_edit
  - file_write
  - task
help:
  group: Validation and analysis
  order: 290
  compact_description: Run physics verification checks
  display_signature: gpd:verify-work [phase]
  root_detail_order: 120
---

<objective>
Run the staged verification workflow for an executed phase.

Output: `GPD/phases/XX-name/XX-VERIFICATION.md`. This workflow is only valid once the phase has reached the `phase_executed` state.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/verify-work/session-router.md
</execution_context>

<context>
Phase: $ARGUMENTS (optional)
- If provided: Verify specific phase (e.g., "4")
- If not provided: Check for active sessions or prompt for phase

</context>

<process>
**CRITICAL: First, read the included session-router stage authority using the file_read tool.**
Follow the included first-stage authority exactly. Later stage loading and field
access are owned by the staged workflow.

The staged workflow authorities own the detailed check taxonomy; this wrapper only bootstraps the canonical verification surface and delegates the physics checks.
  </process>

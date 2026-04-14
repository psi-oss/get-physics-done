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
  - mcp__gpd_verification__get_bundle_checklist
  - mcp__gpd_verification__suggest_contract_checks
  - mcp__gpd_verification__run_contract_check
---

<objective>
Run the staged verification workflow for an executed phase and produce `GPD/phases/XX-name/XX-VERIFICATION.md`. This workflow is only valid once the phase reaches the `phase_executed` state.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/verify-work.md
</execution_context>

<context>
Phase: $ARGUMENTS (optional)
- If provided: Verify specific phase (e.g., "4")
- If not provided: Check for active sessions or prompt for phase

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.
Follow the included workflow file exactly.
The workflow file owns the detailed check taxonomy; this wrapper only bootstraps the canonical verification surfaces and delegates the physics checks.
Call `mcp__gpd_verification__suggest_contract_checks(...)` to gather each per-check request template before invoking `mcp__gpd_verification__run_contract_check(...)`.
Use this hard call shape for contract checks: `mcp__gpd_verification__run_contract_check(request={"check_key":"contract.<name>","contract":{...},"binding":{...},"metadata":{...},"observed":{...},"artifact_content":"..."})`. Omit optional sections only when the suggested per-check schema allows it, fill one `schema_required_request_anyof_fields` branch, and replace every `<replace-with-...>` template sentinel before execution.
</process>

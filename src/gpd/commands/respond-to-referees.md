---
name: gpd:respond-to-referees
description: Structure a point-by-point response to referee reports and update the manuscript
argument-hint: "[path to referee report or 'paste']"
context_mode: project-required
requires:
  files: ["paper/*.tex", "paper/*.md", "manuscript/*.tex", "manuscript/*.md", "draft/*.tex", "draft/*.md"]
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - "GPD/review/REFEREE_RESPONSE{round_suffix}.md"
    - "GPD/AUTHOR-RESPONSE{round_suffix}.md"
  required_evidence:
    - existing manuscript
    - referee report source when provided as a path
  blocking_conditions:
    - missing project state
    - missing manuscript
    - missing referee report source when provided as a path
    - missing conventions
    - degraded review integrity
  preflight_checks:
    - command_context
    - project_state
    - manuscript
    - referee_report_source
    - conventions
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
  - ask_user
---
<objective>
Structure a point-by-point response to referee reports and revise the manuscript accordingly.

Keep the wrapper focused on referee triage, revision routing, and synchronized response artifacts while the workflow owns the full revision pipeline.

**Why subagent:** Referee triage and synchronized manuscript revision burn context fast. Fresh context keeps the orchestrator lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/respond-to-referees.md
@{GPD_INSTALL_DIR}/references/publication/publication-review-wrapper-guidance.md
</execution_context>

<context>
Referee report source: $ARGUMENTS (file path or `paste`).

The workflow resolves the manuscript root, staged review artifacts, and revision targets.
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.
</process>

<success_criteria>
- [ ] Workflow ran end to end
- [ ] Referee response and manuscript revision artifacts were produced
- [ ] Review artifacts and the manuscript stayed synchronized
- [ ] Workflow-owned preflight and schema gates were handled inside the workflow
</success_criteria>

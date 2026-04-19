---
name: gpd:respond-to-referees
description: Structure a point-by-point response to referee reports for an explicit manuscript target or the current GPD manuscript
argument-hint: "[--manuscript PATH] (--report PATH [--report PATH...] | paste)"
context_mode: project-aware
requires:
  files: ["paper/*.tex", "paper/*.md", "manuscript/*.tex", "manuscript/*.md", "draft/*.tex", "draft/*.md", "GPD/publication/*/manuscript/*.tex", "GPD/publication/*/manuscript/*.md"]
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: publication
    resolution_mode: explicit_or_project_manuscript
    explicit_input_kinds:
      - manuscript_path
      - referee_report_path
      - paste_referee_report
    allow_external_subjects: true
    supported_roots:
      - paper
      - manuscript
      - draft
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD
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
  scope_variants:
    - scope: explicit_external_manuscript
      activation: explicit `--manuscript` subject outside the current project's canonical manuscript roots
      relaxed_preflight_checks:
        - project_state
        - conventions
      required_evidence_override:
        - explicit manuscript subject
        - one or more referee report sources
      blocking_conditions_override:
        - missing manuscript subject
        - missing referee report source
        - degraded review integrity
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

Preferred explicit intake is `--manuscript PATH` plus one or more `--report PATH` flags; the legacy single report path or `paste` shorthand remains valid when the manuscript subject resolves from the current GPD project.
The workflow first normalizes that explicit manuscript/report intake into one validator-safe subject payload before calling `validate command-context` or `validate review-preflight`; if the normalized payload itself begins with `--`, the workflow passes it after an end-of-options marker so the validator CLI does not reinterpret intake flags as validator options.
The workflow resolves the manuscript root, staged review artifacts, and revision targets, and keeps GPD-authored auxiliary outputs under `GPD/` even when the manuscript subject itself is explicit or external.
Project-backed response rounds keep the current global `GPD/` / `GPD/review/` ownership. For an explicit external publication subject, the same GPD-owned review/response lineage may instead bind to a subject-owned publication root at `GPD/publication/{subject_slug}`; that is a bounded continuation path, not a full relocation of manuscript-local publication artifacts.
The referee report source may be explicit, but manuscript edits always apply to the resolved manuscript root, never the report path.
</context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/respond-to-referees.md` exactly.
</process>

<success_criteria>
- [ ] Workflow ran end to end
- [ ] One manuscript subject and one or more referee report sources were resolved explicitly or from the current project
- [ ] Referee response and manuscript revision artifacts were produced
- [ ] Review artifacts and the manuscript stayed synchronized
- [ ] GPD-authored auxiliary outputs stayed under `GPD/`
- [ ] Workflow-owned preflight and schema gates were handled inside the workflow
</success_criteria>

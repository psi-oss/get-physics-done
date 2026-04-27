---
name: gpd:respond-to-referees
description: Structure a point-by-point response to referee reports for an explicit manuscript target or the current GPD manuscript
argument-hint: "[--manuscript PATH] (--report PATH [--report PATH...] | paste)"
context_mode: project-aware
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
    - scope: managed_publication_subject
      activation: manuscript subject under `GPD/publication/{subject_slug}/manuscript`
      required_outputs_override:
        - "GPD/publication/{subject_slug}/review/REFEREE_RESPONSE{round_suffix}.md"
        - "GPD/publication/{subject_slug}/AUTHOR-RESPONSE{round_suffix}.md"
    - scope: explicit_external_manuscript
      activation: explicit `--manuscript` subject outside the current project's canonical manuscript roots
      relaxed_preflight_checks:
        - project_state
        - conventions
      required_outputs_override:
        - "GPD/publication/{subject_slug}/review/REFEREE_RESPONSE{round_suffix}.md"
        - "GPD/publication/{subject_slug}/AUTHOR-RESPONSE{round_suffix}.md"
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
**Why subagent:** Referee triage and synchronized revisions burn context fast. Fresh context keeps orchestration lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/respond-to-referees.md
@{GPD_INSTALL_DIR}/references/publication/publication-review-wrapper-guidance.md
</execution_context>

<context>
Referee report source: $ARGUMENTS (file path or `paste`). Preferred explicit intake is `--manuscript PATH` plus one or more `--report PATH`; single report path or `paste` shorthand requires a project-resolved manuscript.
Normalize explicit intake into one validator-safe subject payload before `validate command-context` or `validate review-preflight`; pass payloads beginning with `--` after an end-of-options marker.
The workflow resolves the manuscript root, review artifacts, and revision targets. Keep manuscript edits on the resolved manuscript root, not the report path. Project-backed response rounds keep the current global `GPD/` / `GPD/review/` ownership. Explicit external subjects may bind the same GPD-owned response lineage to a subject-owned publication root at `GPD/publication/{subject_slug}`; that is a bounded continuation path, not a full relocation of manuscript-local publication artifacts.
</context>

<process>
Follow the included respond-to-referees workflow exactly.
</process>

<success_criteria>
- [ ] Workflow ran end to end with one manuscript subject and one or more referee report sources
- [ ] Referee response, manuscript revision artifacts, and review artifacts stayed synchronized
- [ ] GPD-authored auxiliary outputs stayed under selected GPD roots, with workflow-owned gates handled inside the workflow
</success_criteria>

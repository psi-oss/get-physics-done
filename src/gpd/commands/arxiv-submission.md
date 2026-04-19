---
name: gpd:arxiv-submission
description: Prepare a GPD-owned manuscript for arXiv submission with validation and packaging
argument-hint: "[manuscript root or .tex entrypoint]"
context_mode: project-aware
requires:
  files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex", "GPD/publication/*/manuscript/*.tex"]
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: publication
    resolution_mode: explicit_or_project_manuscript
    explicit_input_kinds:
      - manuscript_path
      - manuscript_root
    allow_external_subjects: false
    allow_interactive_without_subject: false
    supported_roots:
      - paper
      - manuscript
      - draft
    bootstrap_allowed: false
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/publication/{subject_slug}/arxiv
    stage_artifact_policy: gpd_owned_outputs_only
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - GPD/publication/{subject_slug}/arxiv/arxiv-submission.tar.gz
  required_evidence:
    - compiled manuscript
    - manuscript-root bibliography audit
    - manuscript-root artifact manifest
    - manuscript-root reproducibility manifest
    - latest peer-review review ledger
    - latest peer-review referee decision
  blocking_conditions:
    - missing project state
    - missing manuscript
    - missing manuscript-root artifact manifest
    - missing manuscript-root bibliography audit
    - missing manuscript-root reproducibility manifest
    - missing compiled manuscript
    - missing conventions
    - missing latest staged peer-review decision evidence
    - manuscript-root reproducibility state is not ready for submission
    - unresolved publication blockers
    - latest staged peer-review recommendation blocks submission packaging
    - degraded review integrity
  preflight_checks:
    - command_context
    - project_state
    - manuscript
    - artifact_manifest
    - bibliography_audit
    - bibliography_audit_clean
    - reproducibility_manifest
    - reproducibility_ready
    - compiled_manuscript
    - conventions
    - publication_blockers
    - review_ledger
    - review_ledger_valid
    - referee_decision
    - referee_decision_valid
    - publication_review_outcome
    - manuscript_proof_review
  conditional_requirements:
    - when: theorem-bearing manuscripts are present
      required_evidence:
        - cleared manuscript proof review for theorem-bearing manuscripts
      blocking_conditions:
        - missing or stale manuscript proof review for theorem-bearing manuscripts
      blocking_preflight_checks:
        - manuscript_proof_review
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
---


<objective>
Prepare a completed paper for arXiv submission.

Keep the wrapper thin and let the workflow own validation, packaging, and submission-gate details.

**Why a dedicated command:** arXiv has specific requirements (no subdirectories in uploads, .bbl instead of .bib, specific figure formats, 00README.XXX for multi-file submissions). Getting these wrong means rejected submissions and wasted time. This command keeps the wrapper focused on the handoff instead of process duplication.

Output: A submission-ready tarball and checklist of manual steps remaining.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/arxiv-submission.md
</execution_context>

<context>
Paper target: $ARGUMENTS (optional; when omitted, the workflow resolves the active GPD-owned manuscript root).

Explicit manuscript subjects must stay under `paper/`, `manuscript/`, `draft/`, or `GPD/publication/{subject_slug}/manuscript/`.
When `$ARGUMENTS` is omitted, use the current GPD project's resolved manuscript subject only; do not switch to standalone interactive intake or arbitrary external directories.
This remains a project-backed manuscript workflow: package the resolved built manuscript root or its `.tex` entrypoint, not a standalone peer-review artifact such as `.pdf`, `.docx`, `.csv`, `.tsv`, or `.xlsx`.
</context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/arxiv-submission.md` exactly.
</process>

<success_criteria>
- [ ] Workflow ran end to end
- [ ] `GPD/publication/{subject_slug}/arxiv/arxiv-submission.tar.gz` was created
- [ ] The submission checklist was presented
- [ ] The resolved manuscript root and its build, reproducibility, and staged-review artifacts satisfied the workflow gates
</success_criteria>

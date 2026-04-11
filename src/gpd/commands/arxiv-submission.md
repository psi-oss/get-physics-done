---
name: gpd:arxiv-submission
description: Prepare a paper for arXiv submission with validation and packaging
argument-hint: "[paper directory path]"
context_mode: project-required
requires:
  files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex"]
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - arxiv-submission.tar.gz
  required_evidence:
    - compiled manuscript
    - manuscript-root bibliography audit
    - manuscript-root artifact manifest
    - latest peer-review review ledger
    - latest peer-review referee decision
  blocking_conditions:
    - missing project state
    - missing manuscript
    - missing manuscript-root artifact manifest
    - missing manuscript-root bibliography audit
    - missing compiled manuscript
    - missing conventions
    - missing latest staged peer-review decision evidence
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
Paper target: $ARGUMENTS (optional; when omitted, the workflow resolves the manuscript root).
</context>

<process>
Follow the workflow file exactly before packaging.
</process>

<success_criteria>
- [ ] Workflow ran end to end
- [ ] `arxiv-submission.tar.gz` was created
- [ ] The submission checklist was presented
- [ ] The resolved manuscript root and its build artifacts satisfied the workflow gates
</success_criteria>

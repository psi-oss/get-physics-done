---
name: gpd:write-paper
description: Structure and write a physics paper from research results
argument-hint: "[paper title or topic] [--from-phases 1,2,3]"
context_mode: project-required
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - "${PAPER_DIR}/{topic_specific_stem}.tex"
    - "${PAPER_DIR}/ARTIFACT-MANIFEST.json"
    - "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json"
    - "${PAPER_DIR}/reproducibility-manifest.json"
    - "GPD/review/REVIEW-LEDGER{round_suffix}.json"
    - "GPD/review/REFEREE-DECISION{round_suffix}.json"
    - "GPD/REFEREE-REPORT{round_suffix}.md"
    - "GPD/REFEREE-REPORT{round_suffix}.tex"
  blocking_conditions:
    - missing project state
    - missing roadmap
    - missing conventions
    - no research artifacts
    - degraded review integrity
  preflight_checks:
    - command_context
    - project_state
    - roadmap
    - conventions
    - research_artifacts
    - verification_reports
    - manuscript
    - artifact_manifest
    - bibliography_audit
    - bibliography_audit_clean
    - reproducibility_manifest
    - reproducibility_ready
    - manuscript_proof_review
  conditional_requirements:
    - when: theorem-bearing claims are present
      required_outputs:
        - "GPD/review/PROOF-REDTEAM{round_suffix}.md"
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
  - web_search
  - ask_user
---


<objective>
Structure and write a physics paper from completed research results.

Keep the wrapper thin and let the workflow own the full pipeline.

**Why subagent:** Publication drafting and review coordination burn context fast.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/write-paper.md
</execution_context>

<context>
Paper topic: $ARGUMENTS
</context>

<process>
Follow the included workflow file exactly.
</process>

<success_criteria>
- [ ] Workflow ran end to end
- [ ] Final manuscript artifacts exist on disk
- [ ] Final review artifacts exist on disk when staged review runs
- [ ] Theorem-bearing manuscripts retain the proof-redteam gate
</success_criteria>

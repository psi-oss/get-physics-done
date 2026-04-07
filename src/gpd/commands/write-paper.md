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
    - "GPD/review/CLAIMS{round_suffix}.json"
    - "GPD/review/STAGE-reader{round_suffix}.json"
    - "GPD/review/STAGE-literature{round_suffix}.json"
    - "GPD/review/STAGE-math{round_suffix}.json"
    - "GPD/review/STAGE-physics{round_suffix}.json"
    - "GPD/review/STAGE-interestingness{round_suffix}.json"
    - "GPD/review/REVIEW-LEDGER{round_suffix}.json"
    - "GPD/review/REFEREE-DECISION{round_suffix}.json"
    - "GPD/REFEREE-REPORT{round_suffix}.md"
    - "GPD/REFEREE-REPORT{round_suffix}.tex"
  required_evidence:
    - manuscript scaffold target (existing draft or bootstrap target)
    - phase summaries or milestone digest
    - verification reports
    - manuscript-root bibliography audit
    - manuscript-root artifact manifest
    - manuscript-root reproducibility manifest
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
  stage_artifacts:
    - "GPD/review/CLAIMS{round_suffix}.json"
    - "GPD/review/STAGE-reader{round_suffix}.json"
    - "GPD/review/STAGE-literature{round_suffix}.json"
    - "GPD/review/STAGE-math{round_suffix}.json"
    - "GPD/review/STAGE-physics{round_suffix}.json"
    - "GPD/review/STAGE-interestingness{round_suffix}.json"
    - "GPD/review/REVIEW-LEDGER{round_suffix}.json"
    - "GPD/review/REFEREE-DECISION{round_suffix}.json"
  conditional_requirements:
    - when: theorem-bearing claims are present
      required_outputs:
        - "GPD/review/PROOF-REDTEAM{round_suffix}.md"
      stage_artifacts:
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

**Why subagent:** Publication drafting and review coordination burn context fast. Separate drafting context keeps the orchestrator lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/write-paper.md
@{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md
@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md
@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md
@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md
@{GPD_INSTALL_DIR}/templates/paper/artifact-manifest-schema.md
@{GPD_INSTALL_DIR}/templates/paper/bibliography-audit-schema.md
@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md
@{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md
@{GPD_INSTALL_DIR}/templates/paper/figure-tracker.md
@{GPD_INSTALL_DIR}/templates/paper/reproducibility-manifest.md
</execution_context>

<context>
Paper topic: $ARGUMENTS

Read `@{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md` before applying any autonomy or research mode behavior.

Check for existing drafts with the shared manuscript-root publication preflight block.

Before reading or updating `${PAPER_DIR}/FIGURE_TRACKER.md`, load `@{GPD_INSTALL_DIR}/templates/paper/figure-tracker.md` and `@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md` first.

Load research context:

```bash
cat GPD/ROADMAP.md 2>/dev/null
ls GPD/phases/*/*SUMMARY.md 2>/dev/null
cat GPD/research-map/FORMALISM.md 2>/dev/null
```

</context>

<process>
@{GPD_INSTALL_DIR}/references/publication/publication-review-wrapper-guidance.md
@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md
@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md

Follow `@{GPD_INSTALL_DIR}/workflows/write-paper.md` exactly.
</process>

<success_criteria>
- [ ] Project context loaded and research artifacts cataloged
- [ ] Paper-readiness audit passed (0 critical gaps or user approved)
- [ ] Paper scope established (journal, type, key result, audience)
- [ ] Detailed outline created and approved
- [ ] All sections drafted by gpd-paper-writer agents (Results first, Abstract last)
- [ ] Every equation numbered, defined, and contextualized
- [ ] Every figure captioned and discussed in text
- [ ] Citations verified via gpd-bibliographer (no hallucinated references)
- [ ] Manuscript-root review artifacts refreshed (`${PAPER_DIR}/ARTIFACT-MANIFEST.json`, `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`, `${PAPER_DIR}/reproducibility-manifest.json`)
- [ ] Pre-submission staged peer review completed with final gpd-referee adjudication
- [ ] Internal consistency verified (notation, cross-references, conventions)
- [ ] Paper directory created with buildable LaTeX structure
</success_criteria>

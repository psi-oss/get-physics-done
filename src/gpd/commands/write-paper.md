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
Structure and write a physics paper from completed research results. Drive the full pipeline from digest to draft: readiness audit, scope, outline, figures, wave-parallelized drafting, notation audit, bibliography verification, staged peer review, and bounded revision. When literature review has already assembled a machine-readable citation list, treat it as a handoff artifact for `gpd paper-build --citation-sources`, not a separate bibliography database.

**Orchestrator role:** Set scope and structure, spawn gpd-paper-writer agents for wave-parallelized section drafting, run gpd-bibliographer for citation verification, coordinate the staged peer-review panel (`gpd-review-reader`, `gpd-review-literature`, `gpd-review-math`, `gpd-review-physics`, `gpd-review-significance`, then `gpd-referee`), and keep the manuscript internally consistent.

**Why subagent:** Paper writing needs the full research context while drafting coherent prose. Each section may need derivations, numerical results, and literature context, so fresh context per section keeps the main coordinator focused on structure.

Writing a physics paper is not writing a report. Keep the narrative arc tight, let every equation and figure earn its place, and keep the review gates semantic: bibliography must clear `bibliography_audit_clean`, and the reproducibility manifest must clear `reproducibility_ready`.

Routes to the write-paper workflow:

1. Load research digest and map sections.
2. Run the paper-readiness audit and decide whether to proceed.
3. Establish scope, catalog artifacts, and draft the outline.
4. Generate figures before section drafting.
5. Draft sections in waves, with `gpd paper-build` as the canonical manuscript scaffold contract and optional local compilation as smoke checks only.
6. Check consistency, notation, placeholders, and citations.
7. Run the staged peer-review panel and final adjudication.
8. Apply a bounded revision loop for referee issues.
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

Check for existing drafts:

Let centralized preflight resolve any existing manuscript entrypoint only from `paper/`, `manuscript/`, or `draft/`, using the manuscript-root `ARTIFACT-MANIFEST.json` first and then `PAPER-CONFIG.json`. Do not fall back to ad hoc `find` or first-match wildcard expansion for manuscript selection.

Load research context:

```bash
cat GPD/ROADMAP.md 2>/dev/null
ls GPD/phases/*/*SUMMARY.md 2>/dev/null
cat GPD/research-map/FORMALISM.md 2>/dev/null
```

</context>

<process>
**Follow the write-paper workflow** from `@{GPD_INSTALL_DIR}/workflows/write-paper.md`.

When the workflow asks for constrained artifacts such as `${PAPER_DIR}/PAPER-CONFIG.json`, `${PAPER_DIR}/ARTIFACT-MANIFEST.json`, `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`, `${PAPER_DIR}/reproducibility-manifest.json`, or `${PAPER_DIR}/FIGURE_TRACKER.md`, use the canonical schema/template surfaces it loads there rather than inventing keys from memory. The artifact manifest and bibliography audit are hard review inputs; the loaded schema docs for those JSON files are part of the required model-visible contract. Do not invent hidden fields, placeholder `manuscript_path` fallbacks, or repair values from prior runs.
When the staged peer-review loop writes `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json`, use the loaded review-ledger/referee-decision schemas plus `peer-review-panel.md` / `peer-review-reliability.md` as the authoritative contract instead of inferring those JSON shapes from prior runs. Do not invent hidden fields or placeholder `manuscript_path` fallbacks.
If the workflow is resuming an existing manuscript, keep the active manuscript root bound to the canonical manifest/config/entrypoint resolver rather than picking the first matching `*.tex` or `*.md` file by wildcard expansion.

The workflow handles the rest:

1. **Init** — Load project context, check optional local compiler availability, and verify conventions.
2. **Load research digest** — Map RESEARCH-DIGEST.md sections to paper structure, or fall back to raw phase data when needed.
3. **Establish scope** — Fix journal, paper type, key result, audience, and available artifacts.
4. **Catalog artifacts** — Gather derivations, numerical results, figures, literature, and verification outputs from phases.
5. **Paper-readiness audit** — Check SUMMARY completeness, convention consistency, numerical stability, figure readiness, and citation readiness.
6. **Create outline** — Draft a section-level outline with purpose, key content, equations, figures, citations, and dependencies.
7. **Generate files** — Build `${PAPER_DIR}/PAPER-CONFIG.json`, then materialize the canonical manuscript scaffold with `gpd paper-build`.
8. **Generate figures** — Produce figures under `${PAPER_DIR}/figures/` and update FIGURE_TRACKER.md.
9. **Draft sections** — Spawn gpd-paper-writer agents in waves, skipping waves whose outputs already exist.
10. **Consistency and notation** — Audit notation, cross-references, placeholders, and physics consistency.
11. **Verify references** — Use gpd-bibliographer to verify citations and detect orphans.
12. **Pre-submission review** — Run the staged peer-review panel used by `gpd:peer-review`.
13. **Final review** — Check abstract, equations, figures, and length.
14. **Paper revision** — Apply a bounded revision loop for referee issues.

For a standalone rerun of the referee stage after the manuscript already exists, use `gpd:peer-review`.
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

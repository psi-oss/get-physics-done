---
name: gpd:peer-review
description: Conduct a staged six-pass peer review of a manuscript and supporting research artifacts from the current GPD project or an explicit external artifact
argument-hint: "[paper directory or manuscript/artifact path]"
context_mode: project-aware
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
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
    - "existing manuscript or explicit external artifact target"
  blocking_conditions:
    - "missing manuscript or explicit external artifact target"
    - "degraded review integrity"
    - "unsupported physical significance claims"
    - "collapsed novelty or venue fit"
  preflight_checks:
    - "command_context"
    - "manuscript"
    - "manuscript_proof_review"
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
    - when: project-backed manuscript review
      required_evidence:
        - "phase summaries or milestone digest"
        - "verification reports"
        - "manuscript-root bibliography audit"
        - "manuscript-root artifact manifest"
        - "manuscript-root reproducibility manifest"
        - "manuscript-root publication artifacts"
      blocking_conditions:
        - "missing project state"
        - "missing roadmap"
        - "missing conventions"
        - "no research artifacts"
      preflight_checks:
        - "project_state"
        - "roadmap"
        - "conventions"
        - "research_artifacts"
        - "verification_reports"
        - "artifact_manifest"
        - "bibliography_audit"
        - "bibliography_audit_clean"
        - "reproducibility_manifest"
        - "reproducibility_ready"
      blocking_preflight_checks:
        - "project_state"
        - "roadmap"
        - "conventions"
        - "research_artifacts"
        - "verification_reports"
        - "artifact_manifest"
        - "bibliography_audit"
        - "bibliography_audit_clean"
        - "reproducibility_manifest"
        - "reproducibility_ready"
    - when: theorem-bearing claims are present
      required_outputs:
        - "GPD/review/PROOF-REDTEAM{round_suffix}.md"
      stage_artifacts:
        - "GPD/review/PROOF-REDTEAM{round_suffix}.md"
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
  - task
  - ask_user
  - web_search
---


<objective>
Conduct a skeptical peer review of a completed manuscript and its supporting research artifacts.
Peer review supports two intake modes: `project-backed manuscript review` and `standalone explicit-artifact review`.

Keep the wrapper focused on the manuscript target, review prerequisites, and final routing. When announcing the panel to the user, say what each stage does in one concise sentence: Stage 1 maps the paper's claims; Stages 2-3 check prior work and mathematical soundness in parallel; theorem-bearing claims also trigger the auxiliary gpd-check-proof critic; Stage 4 checks whether the physical interpretation is supported; Stage 5 judges significance and venue fit; Stage 6 synthesizes everything into the final recommendation.

**Why subagent:** Staged manuscript review burns context fast. Fresh context keeps the orchestrator lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/peer-review.md
</execution_context>

<context>
Review target: $ARGUMENTS (optional paper directory, manuscript path, or explicit artifact path). If no argument is provided, first ask whether to review an explicit artifact or the current GPD project's active manuscript when available.
Treat `project-backed manuscript review` as the strict publication-pipeline mode for the active manuscript under `paper/`, `manuscript/`, or `draft/`. Treat `standalone explicit-artifact review` as a path-driven mode that requires one explicit manuscript or artifact target and uses nearby project files only as additive context when present.

If the current folder is a GPD project, treat `GPD/STATE.md` and `GPD/ROADMAP.md` as optional project context. Do not require them for standalone external artifact review.

The default in-project manuscript family is limited to `paper/`, `manuscript/`, and `draft/`.
Let centralized preflight resolve the active manuscript entrypoint from the explicit argument when provided, otherwise from the manuscript-root `ARTIFACT-MANIFEST.json`, then `PAPER-CONFIG.json`, then the canonical current manuscript entrypoint rules for those roots. Explicit external artifact intake may also target `.tex`, `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, or `.xlsx`. Keep canonical in-project manuscript-root discovery on the manifest/config-resolved `.tex` / `.md` entrypoint path for those roots. Do not use ad hoc wildcard discovery.
If no explicit target is supplied, the workflow may either use the current GPD project manuscript when available or ask the user to point at a specific artifact path.

```bash
# Regression guardrail wording retained for test alignment:
# Do not use ad hoc glob discovery.
```

</context>

<process>
Follow the included workflow file exactly.
</process>

<success_criteria>
- [ ] Manuscript target located or explicitly resolved from arguments
- [ ] Review preflight passed or blocking issues were surfaced clearly
- [ ] Claim index and specialist stage artifacts written under `GPD/review/`
- [ ] Theorem-bearing manuscripts also produce `GPD/review/PROOF-REDTEAM{round_suffix}.md` from `gpd-check-proof`
- [ ] `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json` created
- [ ] Final adjudicating gpd-referee spawned with the stage artifacts and manuscript
- [ ] `GPD/REFEREE-REPORT{round_suffix}.md` created with matching `.tex` companion
- [ ] `GPD/CONSISTENCY-REPORT.md` created when supported by the referee workflow
- [ ] Recommendation, issue counts, and actionable next steps presented
- [ ] Revision rounds respected if prior author responses already exist
</success_criteria>

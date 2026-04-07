---
name: gpd:peer-review
description: Conduct a staged six-pass peer review of a manuscript and supporting research artifacts in the current GPD project
argument-hint: "[paper directory or manuscript path]"
context_mode: project-required
requires:
  files: ["paper/*.tex", "paper/*.md", "manuscript/*.tex", "manuscript/*.md", "draft/*.tex", "draft/*.md"]
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
    - "existing manuscript"
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
    - "missing manuscript"
    - "no research artifacts"
    - "degraded review integrity"
    - "unsupported physical significance claims"
    - "collapsed novelty or venue fit"
  preflight_checks:
    - "command_context"
    - "project_state"
    - "roadmap"
    - "conventions"
    - "research_artifacts"
    - "verification_reports"
    - "manuscript"
    - "artifact_manifest"
    - "bibliography_audit"
    - "bibliography_audit_clean"
    - "reproducibility_manifest"
    - "reproducibility_ready"
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
Conduct a skeptical peer review of a completed manuscript and its supporting research artifacts within the current GPD project.

This command promotes manuscript review to a first-class workflow instead of hiding it inside `write-paper`. It now runs a staged six-agent panel instead of a single all-purpose referee pass: full-manuscript reader, literature reviewer, mathematical-soundness reviewer, physical-soundness reviewer, significance reviewer, and final adjudicating referee.

**Orchestrator role:** Locate the manuscript, validate review prerequisites, gather supporting artifacts, spawn the staged review panel with fresh context between stages, and present actionable outcomes based on the final recommendation. The review-stage outputs are produced by this run; they are not pre-existing prerequisites.

Peer review is not the same as verification. Verification asks whether a derivation or computation checks out. Peer review asks whether the claimed contribution is correct, complete, clear, well-situated in the literature, reproducible, and publishable.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/peer-review.md
@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md
@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md
@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md
@{GPD_INSTALL_DIR}/templates/paper/artifact-manifest-schema.md
@{GPD_INSTALL_DIR}/templates/paper/bibliography-audit-schema.md
@{GPD_INSTALL_DIR}/templates/paper/reproducibility-manifest.md
@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md
@{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md
</execution_context>

<context>
Review target: $ARGUMENTS (optional paper directory or manuscript path)

@GPD/STATE.md
@GPD/ROADMAP.md

The default manuscript family is limited to `paper/`, `manuscript/`, and `draft/`.
Let centralized preflight resolve the active manuscript entrypoint from the explicit argument when provided, otherwise from the manuscript-root `ARTIFACT-MANIFEST.json`, then `PAPER-CONFIG.json`, then the canonical current manuscript entrypoint rules for those roots. Do not use ad hoc wildcard discovery.
If none of those roots exist, pass an explicit manuscript path or paper directory and let centralized preflight reject anything outside the supported target family.

```bash
# Regression guardrail wording retained for test alignment:
# Do not use ad hoc glob discovery.
```

</context>

<process>
**Run centralized context preflight first:**

```bash
CONTEXT=$(gpd --raw validate command-context peer-review "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

**Follow the peer-review workflow** from `@{GPD_INSTALL_DIR}/workflows/peer-review.md`.

The workflow forwards the resolved `$ARGUMENTS` manuscript target into review preflight and keeps manuscript-root-relative support artifacts anchored to that same explicit root instead of falling back to `paper/...`.
In strict mode the preflight gate is semantic, not just file-presence based: the manuscript-root bibliography audit must clear `bibliography_audit_clean`, and the reproducibility manifest must clear `reproducibility_ready` before the staged panel proceeds.
When Stage 6 writes `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json`, use the loaded `review-ledger-schema.md`, `referee-decision-schema.md`, and `peer-review-reliability.md` as the authoritative contract. Do not invent fields, relax round-suffix alignment, or accept blank `manuscript_path` placeholders.
Do not invent hidden fields or placeholder `manuscript_path` fallbacks when repairing review-ledger or referee-decision artifacts.

When announcing the panel to the user, say what each stage does in one concise sentence, for example:

`Launching the six-stage review panel: Stage 1 maps the paper's claims; Stages 2-3 check prior work and mathematical soundness in parallel; theorem-bearing claims also trigger the auxiliary gpd-check-proof critic; Stage 4 checks whether the physical interpretation is supported; Stage 5 judges significance and venue fit; Stage 6 synthesizes everything into the final recommendation.`

The workflow handles all logic including:

1. **Init** — Load project context, detect manuscript target, and resolve scope
2. **Preflight** — Run review preflight validation for the peer-review command
3. **Artifact discovery** — Load manuscript files, bibliography, verification reports, and review-grade paper artifacts
4. **Stage 1** — Spawn `gpd-review-reader` to read the whole manuscript and write `GPD/review/CLAIMS{round_suffix}.json` plus the Stage 1 handoff artifact
5. **Stages 2-5** — Run four fresh-context specialist reviewers with compact stage artifacts: `gpd-review-literature`, `gpd-review-math`, `gpd-review-physics`, and `gpd-review-significance`; when theorem-bearing claims are present, Stage 3 also spawns `gpd-check-proof` to write `GPD/review/PROOF-REDTEAM{round_suffix}.md`
6. **Final adjudication** — Spawn `gpd-referee` as the meta-reviewer to synthesize stage artifacts, populate `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json`, validate the decision floor, and issue the canonical final recommendation
7. **Report handling** — Read the generated referee report and classify the recommendation
8. **Next-step routing** — Route to respond-to-referees, manuscript edits, or arxiv-submission depending on the outcome
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

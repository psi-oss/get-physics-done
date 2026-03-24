---
name: gpd:peer-review
description: Conduct a staged six-pass peer review of a manuscript and supporting research artifacts in the current GPD project
argument-hint: "[paper directory or manuscript path]"
context_mode: project-required
requires:
  files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex"]
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
    - "bibliography audit"
    - "artifact manifest"
    - "reproducibility manifest"
    - "stage review artifacts"
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
    - "project_state"
    - "roadmap"
    - "conventions"
    - "research_artifacts"
    - "manuscript"
  stage_ids:
    - "reader"
    - "literature"
    - "math"
    - "physics"
    - "interestingness"
    - "meta"
  stage_artifacts:
    - "GPD/review/CLAIMS{round_suffix}.json"
    - "GPD/review/STAGE-reader{round_suffix}.json"
    - "GPD/review/STAGE-literature{round_suffix}.json"
    - "GPD/review/STAGE-math{round_suffix}.json"
    - "GPD/review/STAGE-physics{round_suffix}.json"
    - "GPD/review/STAGE-interestingness{round_suffix}.json"
    - "GPD/review/REVIEW-LEDGER{round_suffix}.json"
    - "GPD/review/REFEREE-DECISION{round_suffix}.json"
  final_decision_output: "GPD/review/REFEREE-DECISION{round_suffix}.json"
  requires_fresh_context_per_stage: true
  max_review_rounds: 3
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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Conduct a skeptical peer review of a completed manuscript and its supporting research artifacts within the current GPD project.

This command promotes manuscript review to a first-class workflow instead of hiding it inside `write-paper`. It now runs a staged six-agent panel instead of a single all-purpose referee pass: full-manuscript reader, literature reviewer, mathematical-soundness reviewer, physical-soundness reviewer, significance reviewer, and final adjudicating referee.

**Orchestrator role:** Locate the manuscript, validate review prerequisites, gather supporting artifacts, spawn the staged review panel with fresh context between stages, and present actionable outcomes based on the final recommendation.

Peer review is not the same as verification. Verification asks whether a derivation or computation checks out. Peer review asks whether the claimed contribution is correct, complete, clear, well-situated in the literature, reproducible, and publishable.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/peer-review.md
</execution_context>

<context>
Review target: $ARGUMENTS (optional paper directory or manuscript path)

@GPD/STATE.md
@GPD/ROADMAP.md

Check for candidate manuscripts:

```bash
ls paper/main.tex manuscript/main.tex draft/main.tex 2>/dev/null
find . -maxdepth 3 \( -name "main.tex" -o -name "*.tex" \) 2>/dev/null | head -20
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

When announcing the panel to the user, say what each stage does in one concise sentence, for example:

`Launching the six-stage review panel: Stage 1 maps the paper's claims; Stages 2-3 check prior work and mathematical soundness in parallel; Stage 4 checks whether the physical interpretation is supported; Stage 5 judges significance and venue fit; Stage 6 synthesizes everything into the final recommendation.`

The workflow handles all logic including:

1. **Init** — Load project context, detect manuscript target, and resolve scope
2. **Preflight** — Run review preflight validation for the peer-review command
3. **Artifact discovery** — Load manuscript files, bibliography, verification reports, and review-grade paper artifacts
4. **Stage 1** — Spawn `gpd-review-reader` to read the whole manuscript and write `GPD/review/CLAIMS{round_suffix}.json` plus the Stage 1 handoff artifact
5. **Stages 2-5** — Run four fresh-context specialist reviewers with compact stage artifacts: `gpd-review-literature`, `gpd-review-math`, `gpd-review-physics`, and `gpd-review-significance`
6. **Final adjudication** — Spawn `gpd-referee` as the meta-reviewer to synthesize stage artifacts, populate `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json`, validate the decision floor, and issue the canonical final recommendation
7. **Report handling** — Read the generated referee report and classify the recommendation
8. **Next-step routing** — Route to respond-to-referees, manuscript edits, or arxiv-submission depending on the outcome
</process>

<success_criteria>
- [ ] Manuscript target located or explicitly resolved from arguments
- [ ] Review preflight passed or blocking issues were surfaced clearly
- [ ] Claim index and specialist stage artifacts written under `GPD/review/`
- [ ] `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json` created
- [ ] Final adjudicating gpd-referee spawned with the stage artifacts and manuscript
- [ ] `GPD/REFEREE-REPORT{round_suffix}.md` created with matching `.tex` companion
- [ ] `GPD/CONSISTENCY-REPORT.md` created when supported by the referee workflow
- [ ] Recommendation, issue counts, and actionable next steps presented
- [ ] Revision rounds respected if prior author responses already exist
</success_criteria>

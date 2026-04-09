<purpose>
Conduct a standalone skeptical peer review of a manuscript and supporting artifacts through a staged six-agent panel. The goal is to prevent single-pass, overly charitable reviews of manuscripts that are mathematically coherent but physically weak, novelty-light, or scientifically unconvincing.
</purpose>

<core_principle>
Peer review should be staged, evidence-aware, and fail-closed on unsupported scientific significance. The panel must separate:

1. What the paper claims
2. Whether the literature supports those claims
3. Whether the mathematics is sound
4. Whether the physics is actually supported by the mathematics
5. Whether the result is interesting enough for the claimed venue
6. Whether the paper should be accepted, revised, or rejected

Each stage runs in a fresh subagent context and writes a compact artifact. The final referee decides only after reading those artifacts.
If any spawned reviewer or proof auditor needs user input, it must return `status: checkpoint` and stop. The orchestrator presents the checkpoint and spawns a fresh continuation handoff after the user responds. Do not keep the same spawned run alive waiting for confirmation.
</core_principle>

<process>

<step name="init">
**Initialize context and locate the review target:**

```bash
INIT=$(gpd --raw init phase-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `project_exists`, `state_exists`, `commit_docs`, `autonomy`, `research_mode`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `contract_intake`, `effective_reference_intake`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`, `derived_manuscript_reference_status`, `derived_manuscript_reference_status_count`, `derived_manuscript_proof_review_status`.

**Read mode settings:**

```bash
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```
Treat `project_contract_gate` as authoritative. Use `project_contract` and `contract_intake` only when `project_contract_gate.authoritative` is true; otherwise keep them as diagnostics/context and rely on `effective_reference_intake`, `reference_artifacts_content`, and `active_reference_context` as carry-forward evidence. Stage 1 stays manuscript-first, but later adjudication must not ignore either the approved contract or the active anchor ledger.
If `derived_manuscript_reference_status` is present, use it as a first-pass manuscript-local summary of reference coverage, citation readiness, and audit freshness. Keep the manuscript-root publication artifacts authoritative for strict decisions: `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and the reproducibility manifest still decide pass/fail.
If `derived_manuscript_proof_review_status` is present, use it as the first-pass manuscript-local summary of theorem/proof freshness and keep the manuscript-root proof-redteam artifacts authoritative for strict decisions.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context peer-review "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

**Resolve manuscript target:**

1. If `$ARGUMENTS` names a directory, use it as the candidate paper directory.
2. If `$ARGUMENTS` names a `.tex` or `.md` file, use that file and its parent directory as the review root.
3. Otherwise search, in order:
   - the resolved manuscript entrypoint under `paper/`
   - the resolved manuscript entrypoint under `manuscript/`
   - the resolved manuscript entrypoint under `draft/`

After resolution, keep all manuscript-local support artifacts rooted at the same explicit manuscript directory:

- `RESOLVED_MANUSCRIPT` = resolved `.tex` or `.md` entry point
- `MANUSCRIPT_ROOT` = parent directory of `RESOLVED_MANUSCRIPT`
- `ARTIFACT_MANIFEST_PATH` = `${MANUSCRIPT_ROOT}/ARTIFACT-MANIFEST.json`
- `BIBLIOGRAPHY_AUDIT_PATH` = `${MANUSCRIPT_ROOT}/BIBLIOGRAPHY-AUDIT.json`
- `REPRODUCIBILITY_MANIFEST_PATH` = `${MANUSCRIPT_ROOT}/reproducibility-manifest.json`
- `PAPER_CONFIG_PATH` = `${MANUSCRIPT_ROOT}/PAPER-CONFIG.json`
- `LOCAL_BIB_FILES` = all `*.bib` files under `${MANUSCRIPT_ROOT}`

**If no manuscript found:**

```
No manuscript found. Searched: paper/, manuscript/, draft/

Run gpd:write-paper first, or provide a manuscript path to gpd:peer-review.
```

Exit.

**Convention verification:**

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — the review panel may flag convention drift."
  echo "$CONV_CHECK"
fi
```

</step>

<step name="load_specialized_review_context">
Use `protocol_bundle_context` from init JSON as additive review guidance.

- If `selected_protocol_bundle_ids` is non-empty, use the bundle summary as a compact map of decisive artifacts, benchmark anchors, estimator caveats, or specialized comparisons the manuscript should surface.
- Bundle guidance is additive only: it can sharpen missing-evidence checks, but it cannot invent claims, waive missing comparisons, or overrule the manuscript, `project_contract`, `GPD/comparisons/*-COMPARISON.md`, `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md`, or phase summary / verification evidence (`GPD/phases/*/*SUMMARY.md`, `GPD/phases/*/*-VERIFICATION.md`).
- Reader-visible claims and surfaced evidence remain first-class; review-support artifacts are scaffolding, not substitutes for contract-backed evidence.
- Read `@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md` for the canonical failure-recovery and round-suffix conventions that keep this workflow fail-closed without falling back to legacy recovery paths.
- If no bundle is selected, run the same review pipeline against the manuscript and contract-backed artifacts without any specialized overlay.
</step>

<step name="preflight">
**Run the executable review preflight checks before spawning the review panel:**

```bash
gpd validate review-preflight peer-review "$ARGUMENTS" --strict
```

If preflight exits nonzero because of missing project state, missing manuscript, degraded review integrity, or missing review-grade paper artifacts, STOP and show the blocking issues.
If preflight reports blocked contract/state integrity, surface `project_contract_gate`, `project_contract_load_info`, and `project_contract_validation` details in the stop message and repair the blocked contract before retrying.

In strict peer-review mode, `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and a reproducibility manifest are required inputs. `gpd paper-build` is the step that regenerates `BIBLIOGRAPHY-AUDIT.json` for the current bibliography; rerun it before proceeding whenever the manuscript bibliography or citation set has changed. Strict preflight also enforces the semantic gates `bibliography_audit_clean` and `reproducibility_ready`; those artifacts must be review-ready, not merely present. If `derived_manuscript_reference_status` is available from init, use it as a quick read on what is likely stale or complete, but do not let it override the manuscript-root publication artifacts. Peer review is expected to fail closed when those review-support artifacts are absent, stale, or not review-ready.
Passing preflight still does not establish scientific support. Complete manifests and audits cannot rescue missing decisive comparisons, overclaimed conclusions, or absent contract-backed evidence.
</step>

<step name="artifact_discovery">
**Load the supporting artifact set for the review:**

Load the following files:

- The resolved manuscript entrypoint and any nearby manuscript `*.tex` or `*.md` files that belong to the same manuscript root
- `GPD/STATE.md`
- `GPD/ROADMAP.md`
- All summary artifacts matching `GPD/phases/*/*SUMMARY.md`
- All `GPD/phases/*/*-VERIFICATION.md` files
- `GPD/comparisons/*-COMPARISON.md` if present
- `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md` if present
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${BIBLIOGRAPHY_AUDIT_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present
- `${PAPER_CONFIG_PATH}` if present
- All `*.bib` files under `${MANUSCRIPT_ROOT}`, plus `references/references.bib` if present

Infer the target journal from `${PAPER_CONFIG_PATH}` when available; otherwise use `unspecified`.
Do not rediscover the manuscript by `find` or first-match globbing at this stage; the resolved manuscript root from init/preflight remains authoritative.

If bundle context is present, compare its decisive-artifact and reference expectations against the actual comparison artifacts and figure tracker. Missing bundle-suggested coverage is a warning unless the manuscript has narrowed the claim honestly; missing contract-backed decisive evidence remains a blocker.

Create the review artifact directory if needed:

```bash
mkdir -p GPD/review
```
</step>

<step name="detect_proof_bearing_manuscript">
Classify whether the manuscript contains theorem-style or `proof_obligation` claims before the staged panel proceeds.

Treat the review target as proof-bearing when any of the following are true:

- the approved project contract includes a claim or observable with kind `proof_obligation`
- the manuscript text uses theorem-style language (`theorem`, `lemma`, `corollary`, `proposition`, `claim`, `proof`, `we prove`, `show that`)
- a core claim depends on a formal derivation whose validity turns on named hypotheses, parameters, or quantifiers

If ambiguous, default to proof-bearing.

When proof-bearing review is active:

- spawn the auxiliary proof-critique agent `gpd-check-proof`
- `gpd-check-proof` must write the auxiliary audit artifact `GPD/review/PROOF-REDTEAM{round_suffix}.md`
- the `gpd-check-proof` task must carry the active `manuscript_path`, `manuscript_sha256`, `round`, theorem-bearing `claim_ids`, and `proof_artifact_paths`, and the emitted frontmatter must echo those values exactly
- this proof audit is manuscript-bound: the auxiliary critic must use the active Stage 1 manuscript snapshot and claim map from this review round, not any phase-local shortcut
- later stages must read that artifact alongside the normal staged-review JSON files
- the Stage 3 math artifact must emit exactly one `proof_audits[]` entry for each reviewed theorem-bearing claim, and every `proof_audits[].claim_id` must also appear in `claims_reviewed`
- missing or malformed proof-redteam artifacts are hard blockers
- a proof-redteam artifact with `status: gaps_found` or `status: human_needed` remains a blocking major concern and prevents a favorable final recommendation
- do not bypass this gate because the manuscript looks polished, the algebra appears locally correct, or the user asks to "just review everything else"
</step>

<step name="round_detection">
**Detect whether this is an initial review or a revision round:**

Check for prior reports and author responses:

```bash
ls GPD/REFEREE-REPORT*.md 2>/dev/null
ls GPD/AUTHOR-RESPONSE*.md 2>/dev/null
```

Set:

- `ROUND=1`, `ROUND_SUFFIX=""` for the first review
- `ROUND=2`, `ROUND_SUFFIX="-R2"` if `GPD/REFEREE-REPORT.md` and `GPD/AUTHOR-RESPONSE.md` exist
- `ROUND=3`, `ROUND_SUFFIX="-R3"` if `GPD/REFEREE-REPORT-R2.md` and `GPD/AUTHOR-RESPONSE-R2.md` exist

Stage artifacts for revision rounds should use the same suffix:

- `GPD/review/CLAIMS{ROUND_SUFFIX}.json`
- `GPD/review/STAGE-reader{ROUND_SUFFIX}.json`
- `GPD/review/STAGE-literature{ROUND_SUFFIX}.json`
- `GPD/review/STAGE-math{ROUND_SUFFIX}.json`
- `GPD/review/STAGE-physics{ROUND_SUFFIX}.json`
- `GPD/review/STAGE-interestingness{ROUND_SUFFIX}.json`
- `GPD/review/REVIEW-LEDGER{ROUND_SUFFIX}.json`
- `GPD/review/REFEREE-DECISION{ROUND_SUFFIX}.json`

Use the same `-R2` / `-R3` suffix convention for downstream response artifacts:

- `GPD/AUTHOR-RESPONSE{ROUND_SUFFIX}.md`
- `GPD/review/REFEREE_RESPONSE{ROUND_SUFFIX}.md`

</step>

<step name="announce_panel">
**Before spawning any reviewer, give the user a concise stage map:**

Use one short sentence that names each stage's job, for example:

`Launching the six-stage review panel: Stage 1 maps the paper's claims; Stages 2-3 check prior work and mathematical soundness in parallel; theorem-style claims also trigger the auxiliary gpd-check-proof audit; Stage 4 checks whether the physical interpretation is supported; Stage 5 judges significance and venue fit; Stage 6 synthesizes everything into the final recommendation.`
</step>

<step name="stage_1_read">
**Stage 1 — Read the whole manuscript once.**

Resolve reader model:

```bash
READ_MODEL=$(gpd resolve-model gpd-review-reader)
```

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-review-reader",
  model="{read_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-reader.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `ClaimIndex` / `StageReviewReport` artifact contract exactly.

Operate in manuscript-reader stage mode. This stage must start nearly fresh and remain manuscript-first.

Target journal: {target_journal}
Round: {round}
Output paths:
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files

Focus on:
1. Read the whole manuscript end-to-end before consulting project-internal summaries.
2. Extract every central claim into a compact claim index with claim ids and claim types.
3. Flag where abstract/introduction/conclusion overclaim the physics.
4. Do NOT use `STATE.md`, `ROADMAP.md`, or phase summaries as a source of truth for the manuscript's validity.

Return STAGE 1 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 1: manuscript read"
)
```

If Stage 1 fails, STOP. Later stages depend on its claim map.
</step>

<step name="stage_recovery_1">
**Stage 1 recovery -- Validate the reader output before proceeding.**

Check that both `GPD/review/CLAIMS{round_suffix}.json` and `GPD/review/STAGE-reader{round_suffix}.json` exist.

Run the built-in validators:

```bash
gpd validate review-claim-index GPD/review/CLAIMS{round_suffix}.json
gpd validate review-stage-report GPD/review/STAGE-reader{round_suffix}.json
```

If validation fails:

1. **Retry once.** Re-run the Stage 1 subagent with the same inputs and an explicit reminder to match the `StageReviewReport` and `ClaimIndex` JSON schemas from `peer-review-panel.md`, then rerun `gpd validate review-claim-index` and `gpd validate review-stage-report`.
2. **If the retry also fails,** STOP the pipeline and report the failure: stage name, missing or malformed fields, and any partial output. Do not proceed to Stages 2-6.

Max retries per stage: **1**.
</step>

<step name="stage_2_and_3">
**Stages 2 and 3 — Run literature and mathematics in parallel when possible.**

Resolve models:

```bash
LITERATURE_MODEL=$(gpd resolve-model gpd-review-literature)
MATH_MODEL=$(gpd resolve-model gpd-review-math)
CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)
```

Stage 2 prompt:

```
task(
  subagent_type="gpd-review-literature",
  model="{literature_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-literature.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in literature-context stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Selected protocol bundles: {selected_protocol_bundle_ids}
Carry-forward context: protocol bundle guidance {protocol_bundle_context}; project contract {project_contract}; project contract gate {project_contract_gate}; project contract load info {project_contract_load_info}; project contract validation {project_contract_validation}; active references {active_reference_context}; derived manuscript reference status {derived_manuscript_reference_status}; contract intake {contract_intake}; effective reference intake {effective_reference_intake}; reference artifacts content {reference_artifacts_content}
Output path: `GPD/review/STAGE-literature{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`
- `GPD/comparisons/*-COMPARISON.md` if present
- `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md` if present
- `${BIBLIOGRAPHY_AUDIT_PATH}` if present
- All `*.bib` files under `${MANUSCRIPT_ROOT}`, plus `references/references.bib` if present

Use targeted web search when novelty, significance, or prior-work positioning is uncertain. Treat novelty-heavy claims as requiring external comparison, not trust. Use bundle reference prompts only as additive hints about prior-work or benchmark framing; do not infer novelty or correctness from bundle presence alone.
Return STAGE 2 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 2: literature context"
)
```

Stage 3 prompt:

```
task(
  subagent_type="gpd-review-math",
  model="{math_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-math.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in mathematical-soundness stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Carry-forward context: project contract {project_contract}; project contract gate {project_contract_gate}; project contract load info {project_contract_load_info}; project contract validation {project_contract_validation}; active references {active_reference_context}; derived manuscript reference status {derived_manuscript_reference_status}; contract intake {contract_intake}; effective reference intake {effective_reference_intake}; reference artifacts content {reference_artifacts_content}
Output path: `GPD/review/STAGE-math{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md`
- `GPD/phases/*/*-VERIFICATION.md`
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present

Focus on key equations, limits, internal consistency, and approximation validity.
If theorem-bearing claims are present, `gpd-check-proof` may be running in parallel and will produce `GPD/review/PROOF-REDTEAM{round_suffix}.md`; do not wait on that artifact to begin the math review, and do not duplicate the proof audit yourself.
Return STAGE 3 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 3: mathematical soundness"
)
```

Conditional proof-critique prompt when theorem-bearing claims are present:

```
task(
  subagent_type="gpd-check-proof",
  model="{check_proof_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-check-proof.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/templates/proof-redteam-schema.md and {GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md before writing any proof audit artifact.

Operate in adversarial proof-critique mode with a fresh context.
If the runtime needs user input, return `status: checkpoint` instead of waiting inside this run.

Target journal: {target_journal}
Round: {round}
Carry-forward context: project contract {project_contract}; project contract gate {project_contract_gate}; project contract load info {project_contract_load_info}; project contract validation {project_contract_validation}; active references {active_reference_context}; derived manuscript reference status {derived_manuscript_reference_status}; contract intake {contract_intake}; effective reference intake {effective_reference_intake}; reference artifacts content {reference_artifacts_content}
Write to: `GPD/review/PROOF-REDTEAM{round_suffix}.md`

Before writing frontmatter, bind these fields exactly from the active round artifacts rather than approximating them:
- `manuscript_path`: copy exactly from `GPD/review/CLAIMS{round_suffix}.json`
- `manuscript_sha256`: copy exactly from `GPD/review/CLAIMS{round_suffix}.json`
- `round`: use the active review round number for `{round_suffix}`
- `claim_ids`: copy exactly the theorem-bearing Stage 1 `claim_id` values that are under review in the active round
- `proof_artifact_paths`: copy exactly the theorem-bearing proof artifact paths under review, plus the manuscript entrypoint if it is not already listed

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md`
- `GPD/phases/*/*-VERIFICATION.md`
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present

Reconstruct the theorem / proof inventory explicitly before judging the proof. If any named parameter, hypothesis, quantifier, or conclusion clause disappears from the proof, set `status: gaps_found`. Do not silently accept a proof of a narrower special case. Run at least one adversarial probe against scope, quantifier coverage, or hidden assumptions before you pass the proof.",
  description="Peer review auxiliary proof critique"
)
```

If the runtime supports parallel subagent execution, run Stage 2, Stage 3, and the conditional proof-critique pass in parallel when theorem-bearing claims are present. Otherwise run Stage 2 first, then Stage 3, then the conditional proof-critique pass.

If literature, math, or the conditional proof-critique stage fails, STOP and report the failure.
</step>

<step name="stage_recovery_2_3">
**Stages 2-3 recovery -- Validate literature and math outputs before proceeding.**

For each of `GPD/review/STAGE-literature{round_suffix}.json` and `GPD/review/STAGE-math{round_suffix}.json`, check that the file exists and run:

```bash
gpd validate review-stage-report GPD/review/STAGE-literature{round_suffix}.json
gpd validate review-stage-report GPD/review/STAGE-math{round_suffix}.json
```

If proof-bearing review is active, also require `GPD/review/PROOF-REDTEAM{round_suffix}.md`. It must contain:

- top-level `status: passed | gaps_found | human_needed`
- top-level `reviewer: gpd-check-proof`
- theorem-binding frontmatter (`claim_ids` and non-empty `proof_artifact_paths`)
- manuscript-binding frontmatter (`manuscript_path`, `manuscript_sha256`, and `round`)
- the canonical sections `# Proof Redteam`, `## Proof Inventory`, `## Coverage Ledger`, `## Adversarial Probe`, `## Verdict`, and `## Required Follow-Up`

Missing file, missing frontmatter, or missing required sections is a hard failure. `gaps_found` or `human_needed` may continue as a recorded blocker only if the panel is collecting a fuller diagnosis, but the proof issue remains fail-closed for the final recommendation.

If validation fails for either stage:

1. **Retry once.** Re-run only the failed stage subagent with the same inputs and an explicit reminder to match the `StageReviewReport` JSON schema from `peer-review-panel.md`, then rerun `gpd validate review-stage-report`.
2. **If the retry also fails,** STOP the pipeline and report the failure: stage name, missing or malformed fields, and any partial output. Do not proceed to Stage 4.

Max retries per stage: **1**.

If the proof-redteam artifact is missing, malformed, lacks the canonical frontmatter, or omits required sections, retry `gpd-check-proof` once with the same inputs and an explicit reminder to emit the full canonical proof-audit artifact. If the retry also fails, STOP the pipeline and report that proof review could not be completed.
</step>

<step name="stage_4_physics">
**Stage 4 — Check physical soundness after the mathematical pass.**

Resolve physics model:

```bash
PHYSICS_MODEL=$(gpd resolve-model gpd-review-physics)
```

```
task(
  subagent_type="gpd-review-physics",
  model="{physics_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-physics.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in physical-soundness stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Selected protocol bundles: {selected_protocol_bundle_ids}
Additive specialized guidance: {protocol_bundle_context}
Carry-forward context: project contract {project_contract}; project contract gate {project_contract_gate}; project contract load info {project_contract_load_info}; project contract validation {project_contract_validation}; active references {active_reference_context}; derived manuscript reference status {derived_manuscript_reference_status}; contract intake {contract_intake}; effective reference intake {effective_reference_intake}; reference artifacts content {reference_artifacts_content}
Output path: `GPD/review/STAGE-physics{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`
- `GPD/review/STAGE-math{round_suffix}.json`
- `GPD/review/PROOF-REDTEAM{round_suffix}.md` if proof-bearing review is active
- `GPD/review/STAGE-literature{round_suffix}.json`
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md`
- `GPD/phases/*/*-VERIFICATION.md`
- `GPD/comparisons/*-COMPARISON.md` if present
- `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md` if present

Focus on:
1. Regime of validity
2. Whether the physical interpretation is actually supported
3. Unsupported or unfounded connections between formal manipulations and physics
4. Whether decisive comparison artifacts, benchmark anchors, and estimator caveats expected by the specialized workflow are actually visible in the manuscript or honestly scoped down

Treat bundle guidance as additive skepticism only: it may highlight missing decisive comparisons or estimator caveats, but it must not replace contract-backed evidence or create new manuscript obligations out of thin air.

Return STAGE 4 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 4: physical soundness"
)
```

If Stage 4 fails, STOP and report the failure.
</step>

<step name="stage_recovery_4">
**Stage 4 recovery -- Validate the physics output before proceeding.**

Check that `GPD/review/STAGE-physics{round_suffix}.json` exists and run:

```bash
gpd validate review-stage-report GPD/review/STAGE-physics{round_suffix}.json
```

If validation fails:

1. **Retry once.** Re-run the Stage 4 subagent with the same inputs and an explicit reminder to match the `StageReviewReport` JSON schema from `peer-review-panel.md`, then rerun `gpd validate review-stage-report`.
2. **If the retry also fails,** STOP the pipeline and report the failure: stage name, missing or malformed fields, and any partial output. Do not proceed to Stage 5.

Max retries per stage: **1**.
</step>

<step name="stage_5_significance">
**Stage 5 — Judge interestingness and venue fit after the technical stages.**

Resolve significance model:

```bash
SIGNIFICANCE_MODEL=$(gpd resolve-model gpd-review-significance)
```

```
task(
  subagent_type="gpd-review-significance",
  model="{significance_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-significance.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in interestingness-and-venue-fit stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Carry-forward context: project contract {project_contract}; project contract gate {project_contract_gate}; project contract load info {project_contract_load_info}; project contract validation {project_contract_validation}; active references {active_reference_context}; derived manuscript reference status {derived_manuscript_reference_status}; contract intake {contract_intake}; effective reference intake {effective_reference_intake}; reference artifacts content {reference_artifacts_content}
Output path: `GPD/review/STAGE-interestingness{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `GPD/review/CLAIMS{round_suffix}.json`
	- `GPD/review/STAGE-reader{round_suffix}.json`
	- `GPD/review/STAGE-literature{round_suffix}.json`
	- `GPD/review/STAGE-physics{round_suffix}.json`
	- `GPD/review/PROOF-REDTEAM{round_suffix}.md` if proof-bearing review is active
	- `${PAPER_CONFIG_PATH}` if present

You must explicitly decide whether the paper is:
1. Scientifically interesting enough for the venue
2. Merely technically competent
3. Overclaimed relative to its actual contribution

Return STAGE 5 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 5: significance and venue fit"
)
```

If Stage 5 fails, STOP and report the failure.
</step>

<step name="stage_recovery_5">
**Stage 5 recovery -- Validate the significance output before proceeding.**

Check that `GPD/review/STAGE-interestingness{round_suffix}.json` exists and run:

```bash
gpd validate review-stage-report GPD/review/STAGE-interestingness{round_suffix}.json
```

If validation fails:

1. **Retry once.** Re-run the Stage 5 subagent with the same inputs and an explicit reminder to match the `StageReviewReport` JSON schema from `peer-review-panel.md`, then rerun `gpd validate review-stage-report`.
2. **If the retry also fails,** STOP the pipeline and report the failure: stage name, missing or malformed fields, and any partial output. Do not proceed to Stage 6 adjudication.

Max retries per stage: **1**.
</step>

<step name="final_adjudication">
**Stage 6 — Final adjudication by `gpd-referee`.**

Resolve referee model:

```bash
REFEREE_MODEL=$(gpd resolve-model gpd-referee)
```

```
task(
  subagent_type="gpd-referee",
  model="{referee_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-referee.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md, {GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md, and {GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md before you write any adjudication artifacts.

Act as the final adjudicating referee for the staged peer-review panel.

Target journal: {target_journal}
Round: {round}
<autonomy_mode>{AUTONOMY}</autonomy_mode>
<research_mode>{RESEARCH_MODE}</research_mode>
Selected protocol bundles: {selected_protocol_bundle_ids}
Additive specialized guidance: {protocol_bundle_context}
Carry-forward context: project contract {project_contract}; project contract gate {project_contract_gate}; project contract load info {project_contract_load_info}; project contract validation {project_contract_validation}; active references {active_reference_context}; derived manuscript reference status {derived_manuscript_reference_status}; contract intake {contract_intake}; effective reference intake {effective_reference_intake}; reference artifacts content {reference_artifacts_content}

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`
- `GPD/review/STAGE-literature{round_suffix}.json`
- `GPD/review/STAGE-math{round_suffix}.json`
- `GPD/review/PROOF-REDTEAM{round_suffix}.md` if proof-bearing review is active
- `GPD/review/STAGE-physics{round_suffix}.json`
- `GPD/review/STAGE-interestingness{round_suffix}.json`
- `GPD/comparisons/*-COMPARISON.md` if present
- `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md` if present
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${BIBLIOGRAPHY_AUDIT_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present
- `GPD/STATE.md`
- `GPD/ROADMAP.md`
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md`
- `GPD/phases/*/*-VERIFICATION.md`

If this is a revision round, also read the latest `REFEREE-REPORT*.md` and matching `AUTHOR-RESPONSE*.md`.

If any required staged-review artifact is missing, malformed, or uses the wrong round suffix, STOP and report that failure instead of falling back to standalone review.

Recommendation guardrails:
1. Do not issue minor revision if novelty, physical support, or significance remain materially doubtful.
2. A mathematically coherent but physically weak or scientifically mediocre paper can require major revision or rejection.
3. Evaluate venue fit explicitly using the panel artifacts and spot-check the manuscript where the artifacts are under-evidenced.
4. Treat protocol bundle guidance as additive context only. It can increase concern when decisive comparisons or benchmark anchors are missing, but it cannot rescue missing evidence or override the manuscript's actual artifact trail.
5. For proof-bearing claims, a missing, malformed, or non-passing `GPD/review/PROOF-REDTEAM{round_suffix}.md` artifact prevents any favorable recommendation. Recommendation floor: `major_revision` or `reject`.
6. Write `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json`.
7. Keep `manuscript_path` non-empty and identical across `GPD/review/REVIEW-LEDGER{round_suffix}.json`, `GPD/review/REFEREE-DECISION{round_suffix}.json`, and the staged-review artifacts for this round.
8. Run `gpd validate review-ledger GPD/review/REVIEW-LEDGER{round_suffix}.json`.
9. Run `gpd validate referee-decision GPD/review/REFEREE-DECISION{round_suffix}.json --strict --ledger GPD/review/REVIEW-LEDGER{round_suffix}.json` before trusting any final recommendation.
10. If either validator fails, STOP and fix the JSON artifacts before presenting or relying on the final recommendation.

Write `GPD/REFEREE-REPORT{round_suffix}.md` and the matching `GPD/REFEREE-REPORT{round_suffix}.tex`.
Treat the referee report files as required final-stage artifacts. If either report file is missing after adjudication, the stage is incomplete even if the JSON validators passed.
Also write `GPD/CONSISTENCY-REPORT.md` when applicable.

Return REVIEW COMPLETE with recommendation, confidence, issue counts, and whether prior major concerns are resolved.",
  description="Peer review stage 6: final adjudication"
)
```

If the referee agent fails to spawn or returns an error, STOP and report the failure. Do not silently skip final adjudication.
Do not trust the referee's success text until the ledger, decision, and report files all exist on disk and validate. A returned recommendation without the files is incomplete.
</step>

<step name="stage_recovery_6">
**Stage 6 recovery -- Validate the adjudication outputs before proceeding.**

Check that both `GPD/review/REVIEW-LEDGER{round_suffix}.json` and `GPD/review/REFEREE-DECISION{round_suffix}.json` exist and parse as valid JSON.
Also confirm `GPD/REFEREE-REPORT{round_suffix}.md` and `GPD/REFEREE-REPORT{round_suffix}.tex` exist before treating the final recommendation as complete.

Then run the built-in validators. These are the authoritative fail-closed schema and consistency checks for every final recommendation:

```bash
gpd validate review-ledger GPD/review/REVIEW-LEDGER{round_suffix}.json
gpd validate referee-decision GPD/review/REFEREE-DECISION{round_suffix}.json --strict --ledger GPD/review/REVIEW-LEDGER{round_suffix}.json
```

If validation fails:

1. **Retry once.** Re-run the Stage 6 referee subagent with the same inputs and an explicit reminder to satisfy `review-ledger-schema.md` and `referee-decision-schema.md` by passing the built-in validators above.
2. **If the retry also fails,** STOP the pipeline and report the failure: stage name, validation errors, and any partial output. Do not proceed to report summarization.

Treat blank `manuscript_path` values in either `GPD/review/REVIEW-LEDGER{round_suffix}.json` or `GPD/review/REFEREE-DECISION{round_suffix}.json` as validation failures, not as optional bookkeeping.

Max retries per stage: **1**.
</step>

<step name="optional_pdf_compile">
**Optional PDF compile of the LaTeX referee report:**

If TeX is installed and the runtime allows it, compile the latest referee-report `.tex` file to a matching `.pdf`.

If TeX is missing, do not block the review:

```
Referee review artifacts were written, but a TeX toolchain is not available.
Continue now with `GPD/REFEREE-REPORT{round_suffix}.md` + `GPD/REFEREE-REPORT{round_suffix}.tex` only.
If you want the polished PDF artifact as well, Authorize the agent to install TeX now or compile the `.tex` later in an environment that already has TeX.
```
</step>

<step name="summarize_report">
**Read the latest referee report and summarize the decision:**

1. Identify the most recent referee report among:
   - `GPD/REFEREE-REPORT.md`
   - `GPD/REFEREE-REPORT-R2.md`
   - `GPD/REFEREE-REPORT-R3.md`
2. Extract:
   - recommendation
   - confidence
   - major issue count
   - minor issue count
   - top actionable items

Present:

```markdown
## Peer Review Summary

**Recommendation:** {recommendation}
**Confidence:** {confidence}
**Major issues:** {N}
**Minor issues:** {M}
**Stage artifacts:** `GPD/review/`
**Report:** {path}
**LaTeX report:** {path or "not written"}
**Consistency report:** {path or "not written"}
```
</step>

<step name="route_next_action">
**Route the outcome based on the recommendation:**

- `accept`: recommend `gpd:arxiv-submission`
- `minor_revision`: recommend targeted manuscript edits or `gpd:respond-to-referees`
- `major_revision`: recommend `gpd:respond-to-referees` and highlight the blocking findings
- `reject`: present the highest-severity issues and recommend returning to research or restructuring the manuscript before another review

If this was a revision round, state the round number and whether the referee considers previous issues resolved, partially resolved, or unresolved.
</step>

</process>

<success_criteria>
- [ ] Project context initialized
- [ ] Manuscript target resolved
- [ ] Review preflight run in strict mode
- [ ] Supporting artifacts loaded when present
- [ ] Claim index written
- [ ] Stage 1 reader artifact written
- [ ] Stage 1 output validated (JSON schema check passed or retry succeeded)
- [ ] Stage 2 literature-context artifact written
- [ ] Stage 3 mathematical-soundness artifact written
- [ ] Stages 2-3 outputs validated (JSON schema check passed or retry succeeded)
- [ ] Proof-bearing manuscripts also produce `GPD/review/PROOF-REDTEAM{round_suffix}.md`
- [ ] Stage 4 physical-soundness artifact written
- [ ] Stage 4 output validated (JSON schema check passed or retry succeeded)
- [ ] Stage 5 interestingness artifact written
- [ ] Stage 5 output validated (JSON schema check passed or retry succeeded)
- [ ] Review ledger and referee decision JSON written
- [ ] Stage 6 outputs validated (ledger and decision schema checks passed or retry succeeded)
- [ ] Final adjudicating gpd-referee executed successfully
- [ ] Latest referee report located and summarized
- [ ] Outcome routed to the correct next action
</success_criteria>

<purpose>
Conduct a staged skeptical peer review of either the current GPD project manuscript or an explicit manuscript artifact through a six-agent panel. The goal is to prevent single-pass, overly charitable reviews of manuscripts that are mathematically coherent but physically weak, novelty-light, or scientifically unconvincing.
Peer review supports two intake modes: `project-backed manuscript review` and `standalone explicit-artifact review`.
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
A spawned handoff is not complete until the orchestrator has captured its typed return, verified the stage-owned artifact boundary on disk, and then treated that finished child as closed and retired. Once retired, its transient execution state, scratch reasoning, and live conversation context must not be reused.
Every downstream stage must begin from persisted artifacts plus the explicitly declared carry-forward inputs for that stage. Do not treat a prior child's live context, unstaged notes, or in-memory state as valid carry-forward evidence.
If subagent spawning is unavailable and the workflow falls back to sequential execution in the main context, emulate the same boundary discipline: finish one stage, persist and verify its artifacts, clear the stage-local transient state, and begin the next stage only from those persisted outputs and declared carry-forward inputs.
</core_principle>

<process>

<step name="init">
**Initialize context and locate the review target:**

Set `REVIEW_TARGET="$ARGUMENTS"` unless interactive intake overrides it.

Bootstrap peer-review context from the dedicated peer-review init surface, not `phase-op`, so manuscript routing, publication blockers, and prior review-round state stay tied to the resolved peer-review target contract.

```bash
BOOTSTRAP=$(gpd --raw init peer-review --stage bootstrap)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd peer-review bootstrap failed: $BOOTSTRAP"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse bootstrap JSON for: `project_exists`, `state_exists`, `commit_docs`, `autonomy`, `research_mode`, `review_target_input`, `review_target_mode`, `review_target_mode_reason`, `resolved_review_target`, `resolved_review_root`, `publication_subject_slug`, `publication_lane_kind`, `managed_publication_root`, `selected_publication_root`, `selected_review_root`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `contract_intake`, `effective_reference_intake`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`, `derived_manuscript_reference_status`, `derived_manuscript_reference_status_count`, `derived_manuscript_proof_review_status`, `manuscript_resolution_status`, `manuscript_resolution_detail`, `manuscript_root`, `manuscript_entrypoint`, `artifact_manifest_path`, `bibliography_audit_path`, `reproducibility_manifest_path`, `publication_blockers`, `latest_review_round`, `latest_review_round_suffix`, `latest_review_ledger`, `latest_referee_decision`, `latest_referee_report_md`, `latest_referee_report_tex`, `latest_proof_redteam`, `latest_review_artifacts`, `latest_response_round`, `latest_response_round_suffix`, `latest_author_response`, `latest_referee_response`, `latest_response_artifacts`.

**Read mode settings:**

```bash
AUTONOMY=$(echo "$BOOTSTRAP" | gpd json get .autonomy --default supervised)
RESEARCH_MODE=$(echo "$BOOTSTRAP" | gpd json get .research_mode --default balanced)
```
Treat `project_contract_gate` as authoritative. Use `project_contract` and `contract_intake` only when `project_contract_gate.authoritative` is true; otherwise keep them as diagnostics/context and rely on `effective_reference_intake`, `reference_artifacts_content`, and `active_reference_context` as carry-forward evidence. Stage 1 stays manuscript-first, but later adjudication must not ignore either the approved contract or the active anchor ledger.
If `derived_manuscript_reference_status` is present, use it as a first-pass manuscript-local summary of reference coverage, citation readiness, and audit freshness. Keep the manuscript-root publication artifacts authoritative for strict decisions: `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and the reproducibility manifest still decide pass/fail.
If `derived_manuscript_proof_review_status` is present, use it as the first-pass manuscript-local summary of theorem/proof freshness and keep the manuscript-root proof-redteam artifacts authoritative for strict decisions.
The shared manuscript-root bootstrap contract is applied in preflight. The local steps below add only peer-review-specific routing, proof-review, and adjudication rules.
This workflow is project-aware: it may resolve the active manuscript from the current GPD project or review one explicit `.tex`, `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, `.xlsx`, or manuscript-directory target supplied in the current workspace. Write review artifacts under the target-aware `selected_review_root`, falling back to `GPD/review`.

If `REVIEW_TARGET` is empty and `project_exists` is true, ask the user which mode they want:

> **Platform note:** If `ask_user` is not available, present the same choices in plain text and wait for the user's freeform response.

Use ask_user:

- header: `Peer Review`
- question: `Review the current GPD project manuscript, or point at a specific manuscript artifact?`
- options:
  - `Use current project` -- Review the active manuscript resolved from the current GPD project. Recommended when the folder is already a GPD project.
  - `Pick artifact path` -- Review a specific `.tex`, `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, `.xlsx`, or manuscript directory path instead.

If the user chooses `Pick artifact path`, ask for one explicit path and store it in `REVIEW_TARGET`.

If `REVIEW_TARGET` is empty and `project_exists` is false, ask the user for one explicit manuscript path or directory. Accept `.tex`, `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, `.xlsx`, or a manuscript directory path. If the answer is still empty, STOP and ask again for a concrete artifact path.

After the user has chosen a mode or supplied an explicit path, rerun the subject-aware peer-review init surface for the resolved target. Treat this second payload as authoritative for manuscript routing and review-round state; do not keep using current-project manuscript status from the bootstrap call after an explicit artifact target has been chosen.

```bash
INIT=$(gpd --raw init peer-review "$REVIEW_TARGET" --stage bootstrap)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd peer-review target init failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse target-aware init JSON for: `project_exists`, `state_exists`, `commit_docs`, `autonomy`, `research_mode`, `review_target_input`, `review_target_mode`, `review_target_mode_reason`, `resolved_review_target`, `resolved_review_root`, `publication_subject_slug`, `publication_lane_kind`, `managed_publication_root`, `selected_publication_root`, `selected_review_root`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `contract_intake`, `effective_reference_intake`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`, `derived_manuscript_reference_status`, `derived_manuscript_reference_status_count`, `derived_manuscript_proof_review_status`, `manuscript_resolution_status`, `manuscript_resolution_detail`, `manuscript_root`, `manuscript_entrypoint`, `artifact_manifest_path`, `bibliography_audit_path`, `reproducibility_manifest_path`, `publication_blockers`, `latest_review_round`, `latest_review_round_suffix`, `latest_review_ledger`, `latest_referee_decision`, `latest_referee_report_md`, `latest_referee_report_tex`, `latest_proof_redteam`, `latest_review_artifacts`, `latest_response_round`, `latest_response_round_suffix`, `latest_author_response`, `latest_referee_response`, `latest_response_artifacts`.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context peer-review "$REVIEW_TARGET")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

**Resolve manuscript target:**

Use centralized target-aware init plus centralized command-context preflight as the only authoritative manuscript resolver.

1. In `project-backed manuscript review`, resolve the manuscript entrypoint under `paper/`, `manuscript/`, or `draft/` from `ARTIFACT-MANIFEST.json`, then `PAPER-CONFIG.json`, then the canonical current-manuscript rules for those roots.
2. In `standalone explicit-artifact review`, the explicit path the user chose is authoritative. Do not fall back to canonical project-manuscript discovery after a standalone explicit artifact has been selected.
3. When the user explicitly points at `.docx`, `.csv`, `.tsv`, or `.xlsx`, treat it as an explicit external-artifact intake surface only; do not widen the default `paper/`, `manuscript/`, or `draft/` discovery rules.
4. Do not re-resolve the review target with ad hoc wildcard discovery or first-match shell globs after init/preflight has selected it.

After resolution, keep all manuscript-local support artifacts rooted at the same explicit manuscript directory:

- `REVIEW_TARGET_MODE` = `review_target_mode` from the target-aware `INIT` payload
- `REVIEW_TARGET_MODE_REASON` = `review_target_mode_reason` from the target-aware `INIT` payload
- `RESOLVED_REVIEW_TARGET` = `resolved_review_target` from the target-aware `INIT` payload
- `RESOLVED_REVIEW_ROOT` = `resolved_review_root` from the target-aware `INIT` payload
- `PUBLICATION_SUBJECT_SLUG` = `publication_subject_slug` from the target-aware `INIT` payload when present
- `PUBLICATION_ROOT` = `selected_publication_root` from target-aware `INIT`, otherwise `managed_publication_root` when present
- `REVIEW_ROOT` = `selected_review_root` from target-aware `INIT`, otherwise `resolved_review_root`, otherwise `GPD/review`
- `RESOLVED_MANUSCRIPT` = `manuscript_entrypoint` from the target-aware `INIT` payload
- `MANUSCRIPT_ROOT` = `manuscript_root` from the target-aware `INIT` payload
- `ARTIFACT_MANIFEST_PATH` = `artifact_manifest_path` when present, otherwise `${MANUSCRIPT_ROOT}/ARTIFACT-MANIFEST.json`
- `BIBLIOGRAPHY_AUDIT_PATH` = `bibliography_audit_path` when present, otherwise `${MANUSCRIPT_ROOT}/BIBLIOGRAPHY-AUDIT.json`
- `REPRODUCIBILITY_MANIFEST_PATH` = `reproducibility_manifest_path` when present, otherwise `${MANUSCRIPT_ROOT}/reproducibility-manifest.json`
- `PAPER_CONFIG_PATH` = `${MANUSCRIPT_ROOT}/PAPER-CONFIG.json`
- `LOCAL_BIB_FILES` = all `*.bib` files under `${MANUSCRIPT_ROOT}`

Prepare a reader-friendly manuscript surface for the staged reviewers:

- For `.tex` or `.md`, keep the resolved main file plus any nearby section `.tex` / `.md` files under the same manuscript root.
- For `.txt`, use the `.txt` file directly as the manuscript review surface.
- For `.csv` or `.tsv`, use the file directly as the explicit-artifact review surface.
- For `.pdf`, `.docx`, or `.xlsx`, first look for a nearby text companion such as the same basename with `.txt`. If none exists, create `${REVIEW_ROOT}/` if needed, run `gpd validate artifact-text "$RESOLVED_MANUSCRIPT" --output ${REVIEW_ROOT}/MANUSCRIPT-TEXT.txt`, and use that extracted file as the manuscript review surface while keeping the original artifact as the canonical `RESOLVED_MANUSCRIPT`. If extraction fails, STOP and ask the user to point at a `.txt`, `.md`, `.tex`, `.csv`, `.tsv`, or a matching extracted `.txt` companion file.

Store the reviewer-visible inputs as `MANUSCRIPT_STAGE_FILES`.

**If no manuscript found:**

```
No review target found. The target-aware peer-review init plus command-context preflight did not resolve a manuscript under `paper/`, `manuscript/`, or `draft/`, and no valid explicit artifact target was accepted.

Run gpd:write-paper first, or provide a `.tex`, `.md`, `.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, `.xlsx`, or manuscript directory path to gpd:peer-review.
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
- Reader-visible claims and surfaced evidence remain first-class; review-support artifacts are scaffolding, not substitutes for authoritative evidence required by the resolved review target or project contract.
- Read `@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md` for the canonical failure-recovery and round-suffix conventions that keep this workflow fail-closed.
- If no bundle is selected, run the same review pipeline against the resolved review target plus any authoritative project-backed artifacts without any specialized overlay.
</step>

<step name="preflight">
**Run the executable review preflight checks before spawning the review panel:**

Load the staged preflight payload before using manuscript-root gates, reference-artifact summaries, or strict publication schemas:

```bash
PREFLIGHT_INIT=$(gpd --raw init peer-review "$REVIEW_TARGET" --stage preflight)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd peer-review preflight init failed: $PREFLIGHT_INIT"
  # STOP — display the error to the user and do not proceed.
fi
INIT="$PREFLIGHT_INIT"
```

Apply the shared manuscript-root bootstrap contract exactly:

@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md

```bash
gpd validate review-preflight peer-review "$REVIEW_TARGET" --strict
```

If preflight exits nonzero because of a missing resolved review target, degraded review integrity, missing project-backed publication gates, or unsupported artifact-text intake, STOP and show the blocking issues.
Missing project state, roadmap, conventions, research artifacts, verification reports, or manuscript-root publication artifacts are blocking only in `project-backed manuscript review`.
If preflight reports blocked contract/state integrity, surface `project_contract_gate`, `project_contract_load_info`, and `project_contract_validation` details in the stop message and repair the blocked contract before retrying.

In strict project-backed peer-review mode, `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and a reproducibility manifest are required inputs. `gpd paper-build` is the step that regenerates `BIBLIOGRAPHY-AUDIT.json` for the current bibliography; rerun it before proceeding whenever the manuscript bibliography or citation set has changed. Strict preflight also enforces the semantic gates `bibliography_audit_clean` and `reproducibility_ready`; those artifacts must be review-ready, not merely present. If `derived_manuscript_reference_status` is available from init, use it as a quick read on what is likely stale or complete, but do not let it override the manuscript-root publication artifacts.
In `standalone explicit-artifact review`, manuscript-root publication artifacts, `GPD/STATE.md`, `GPD/ROADMAP.md`, phase summaries, and verification reports become additive supporting context when present and must not block intake by themselves unless the user explicitly makes them authoritative.
Passing preflight still does not establish scientific support. Complete manifests and audits cannot rescue missing decisive comparisons, overclaimed conclusions, or absent evidence required by the resolved review target or an authoritative project contract.
</step>

<step name="artifact_discovery">
**Load the supporting artifact set for the review:**

Load the staged artifact-discovery payload before resolving review-round state or reading supporting artifacts:

```bash
ARTIFACT_DISCOVERY_INIT=$(gpd --raw init peer-review "$REVIEW_TARGET" --stage artifact_discovery)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd peer-review artifact-discovery init failed: $ARTIFACT_DISCOVERY_INIT"
  # STOP — display the error to the user and do not proceed.
fi
INIT="$ARTIFACT_DISCOVERY_INIT"
```

Load the following files:

- `MANUSCRIPT_STAGE_FILES`
- `GPD/STATE.md` if present
- `GPD/ROADMAP.md` if present
- All summary artifacts matching `GPD/phases/*/*SUMMARY.md` if present
- All `GPD/phases/*/*-VERIFICATION.md` files if present
- `GPD/comparisons/*-COMPARISON.md` if present
- `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md` if present
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${BIBLIOGRAPHY_AUDIT_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present
- `${PAPER_CONFIG_PATH}` if present
- All `*.bib` files under `${MANUSCRIPT_ROOT}`, plus `references/references.bib` if present

Infer the target journal from `${PAPER_CONFIG_PATH}` when available; otherwise use `unspecified`.
Do not rediscover the manuscript by `find` or first-match globbing at this stage; the resolved manuscript root from init/preflight remains authoritative.
In `project-backed manuscript review`, `GPD/STATE.md`, `GPD/ROADMAP.md`, phase summaries, verification reports, comparison artifacts, and strict manuscript-root publication artifacts are authoritative evidence surfaces. In `standalone explicit-artifact review`, treat those project files as additive diagnostics only when they are already present; do not fail the workflow merely because they are absent.

If bundle context is present, compare its decisive-artifact and reference expectations against the actual comparison artifacts and figure tracker. Missing bundle-suggested coverage is a warning unless the manuscript has narrowed the claim honestly; missing decisive evidence required by an authoritative project contract remains a blocker in `project-backed manuscript review`.

Create the review artifact directory if needed:

```bash
mkdir -p ${REVIEW_ROOT}
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
- `gpd-check-proof` must write the auxiliary audit artifact `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`
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

Use the subject-aware `INIT` payload as the source of truth for prior review and response state. Do not infer rounds by scanning `GPD/REFEREE-REPORT*`, `GPD/AUTHOR-RESPONSE*`, or `${REVIEW_ROOT}/REFEREE_RESPONSE*` filenames in isolation.

Read from `INIT`:

- `latest_review_round`, `latest_review_round_suffix`, `latest_review_artifacts`
- `latest_response_round`, `latest_response_round_suffix`, `latest_response_artifacts`

```bash
ROUND=1
ROUND_SUFFIX=""

LATEST_REVIEW_STATE=$(echo "$INIT" | gpd json get .latest_review_artifacts.state --default missing)
LATEST_REVIEW_ROUND=$(echo "$INIT" | gpd json get .latest_review_round --default 0)
LATEST_REVIEW_SUFFIX=$(echo "$INIT" | gpd json get .latest_review_round_suffix --default "")
LATEST_RESPONSE_STATE=$(echo "$INIT" | gpd json get .latest_response_artifacts.state --default missing)
LATEST_RESPONSE_ROUND=$(echo "$INIT" | gpd json get .latest_response_round --default 0)

if [[ "$LATEST_REVIEW_STATE" == "partial" || "$LATEST_REVIEW_STATE" == "invalid" ]]; then
  echo "ERROR: The latest review bundle for the resolved target is incomplete or invalid. Repair the target-bound review artifacts before advancing."
  exit 1
fi

if [[ "$LATEST_RESPONSE_STATE" == "partial" || "$LATEST_RESPONSE_STATE" == "invalid" ]]; then
  echo "ERROR: The latest response bundle for the resolved target is incomplete or invalid. Repair the target-bound response artifacts before advancing."
  exit 1
fi

if [[ "$LATEST_RESPONSE_STATE" == "complete" && "$LATEST_REVIEW_STATE" != "complete" ]]; then
  echo "ERROR: A response bundle exists without a complete target-bound review bundle. Repair the review record before advancing."
  exit 1
fi

if [[ "$LATEST_REVIEW_STATE" == "complete" ]]; then
  if [[ "$LATEST_RESPONSE_STATE" != "complete" ]]; then
    echo "ERROR: Found a complete prior review round for the resolved target without a paired author/referee response package. Finish the response round before advancing."
    exit 1
  fi
  if [[ "$LATEST_RESPONSE_ROUND" != "$LATEST_REVIEW_ROUND" ]]; then
    echo "ERROR: Latest response round does not match the latest review round for the resolved target. Repair the target-bound review record before advancing."
    exit 1
  fi
  ROUND=$((LATEST_REVIEW_ROUND + 1))
  if [[ $ROUND -ge 2 ]]; then
    ROUND_SUFFIX="-R${ROUND}"
  fi
fi
```

Set:

- `ROUND=1`, `ROUND_SUFFIX=""` when `INIT` reports no complete prior target-bound review/response package
- `ROUND=N+1` only when `INIT` reports a complete latest review bundle and a matching complete latest response bundle for the same resolved target manuscript
- If `INIT` reports a partial or invalid latest review/response bundle, stop fail-closed and repair it before advancing
- Do not infer the next round from a lone report, author response, referee response, or mismatched suffix under `GPD/`

Stage artifacts for revision rounds should use the same suffix:

-- `${REVIEW_ROOT}/CLAIMS{ROUND_SUFFIX}.json`
-- `${REVIEW_ROOT}/STAGE-reader{ROUND_SUFFIX}.json`
-- `${REVIEW_ROOT}/STAGE-literature{ROUND_SUFFIX}.json`
-- `${REVIEW_ROOT}/STAGE-math{ROUND_SUFFIX}.json`
-- `${REVIEW_ROOT}/STAGE-physics{ROUND_SUFFIX}.json`
-- `${REVIEW_ROOT}/STAGE-interestingness{ROUND_SUFFIX}.json`
-- `${REVIEW_ROOT}/REVIEW-LEDGER{ROUND_SUFFIX}.json`
-- `${REVIEW_ROOT}/REFEREE-DECISION{ROUND_SUFFIX}.json`

Use the same `-R2` / `-R3` suffix convention for downstream response artifacts:

-- `GPD/AUTHOR-RESPONSE{ROUND_SUFFIX}.md`
-- `${REVIEW_ROOT}/REFEREE_RESPONSE{ROUND_SUFFIX}.md`

</step>

<step name="announce_panel">
**Before spawning any reviewer, give the user a concise stage map:**

Load the staged panel payload before launching Stage 1 through Stage 5 and the conditional proof audit:

```bash
PANEL_INIT=$(gpd --raw init peer-review "$REVIEW_TARGET" --stage panel_stages)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd peer-review panel init failed: $PANEL_INIT"
  # STOP — display the error to the user and do not proceed.
fi
INIT="$PANEL_INIT"
```

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
- `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json`

Files to read:
- `MANUSCRIPT_STAGE_FILES`

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

Check that both `${REVIEW_ROOT}/CLAIMS{round_suffix}.json` and `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json` exist.

Run the built-in validators:

```bash
gpd validate review-claim-index ${REVIEW_ROOT}/CLAIMS{round_suffix}.json
gpd validate review-stage-report ${REVIEW_ROOT}/STAGE-reader{round_suffix}.json
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
Output path: `${REVIEW_ROOT}/STAGE-literature{round_suffix}.json`

Files to read:
- `MANUSCRIPT_STAGE_FILES`
- `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json`
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
Output path: `${REVIEW_ROOT}/STAGE-math{round_suffix}.json`

Files to read:
- `MANUSCRIPT_STAGE_FILES`
- `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json`
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md` if present
- `GPD/phases/*/*-VERIFICATION.md` if present
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present

Focus on key equations, limits, internal consistency, and approximation validity.
If theorem-bearing claims are present, `gpd-check-proof` may be running in parallel and will produce `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`; do not wait on that artifact to begin the math review, and do not duplicate the proof audit yourself.
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
Write to: `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`

Before writing frontmatter, bind these fields exactly from the active round artifacts rather than approximating them:
- `manuscript_path`: copy exactly from `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `manuscript_sha256`: copy exactly from `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `round`: use the active review round number for `{round_suffix}`
- `claim_ids`: copy exactly the theorem-bearing Stage 1 `claim_id` values that are under review in the active round
- `proof_artifact_paths`: copy exactly the theorem-bearing proof artifact paths under review, plus the manuscript entrypoint if it is not already listed

Files to read:
- `MANUSCRIPT_STAGE_FILES`
- `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json`
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md` if present
- `GPD/phases/*/*-VERIFICATION.md` if present
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present

Reconstruct the theorem / proof inventory explicitly before judging the proof. If any named parameter, hypothesis, quantifier, or conclusion clause disappears from the proof, set `status: gaps_found`. Do not silently accept a proof of a narrower special case. Run at least one adversarial probe against scope, quantifier coverage, or hidden assumptions before you pass the proof.",
  description="Peer review auxiliary proof critique"
)
```

If the runtime supports parallel subagent execution, run Stage 2, Stage 3, and the conditional proof-critique pass in parallel when theorem-bearing claims are present. Otherwise run Stage 2 first, then Stage 3, then the conditional proof-critique pass.
Treat Stage 2, Stage 3, and the conditional proof-critique pass as one barriered review wave. In sequential fallback, emulate the same barrier after each stage: finish the stage, persist and validate its artifact, retire that stage-local working state, and launch the next handoff only from the written artifacts for this round plus the declared carry-forward inputs.

If literature, math, or the conditional proof-critique stage fails, STOP and report the failure.
</step>

<step name="stage_recovery_2_3">
**Stages 2-3 recovery -- Validate literature and math outputs before proceeding.**

For each of `${REVIEW_ROOT}/STAGE-literature{round_suffix}.json` and `${REVIEW_ROOT}/STAGE-math{round_suffix}.json`, check that the file exists and run:

```bash
gpd validate review-stage-report ${REVIEW_ROOT}/STAGE-literature{round_suffix}.json
gpd validate review-stage-report ${REVIEW_ROOT}/STAGE-math{round_suffix}.json
```

If proof-bearing review is active, also require `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`. It must contain:

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
Treat this recovery step as the Stage 2 / Stage 3 / proof-review branch barrier. Before Stage 4 can spawn, the orchestrator must capture the typed return from every launched branch in the wave, confirm that the persisted artifacts for this round exist and validate, and then retire each finished child handoff. Later stages and retries must restart from the written artifacts above plus the declared carry-forward inputs, not from branch-local live context.
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
Output path: `${REVIEW_ROOT}/STAGE-physics{round_suffix}.json`

Files to read:
- `MANUSCRIPT_STAGE_FILES`
- `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-math{round_suffix}.json`
- `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md` if proof-bearing review is active
- `${REVIEW_ROOT}/STAGE-literature{round_suffix}.json`
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md` if present
- `GPD/phases/*/*-VERIFICATION.md` if present
- `GPD/comparisons/*-COMPARISON.md` if present
- `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md` if present

Focus on:
1. Regime of validity
2. Whether the physical interpretation is actually supported
3. Unsupported or unfounded connections between formal manipulations and physics
4. Whether decisive comparison artifacts, benchmark anchors, and estimator caveats expected by the specialized workflow are actually visible in the manuscript or honestly scoped down

Treat bundle guidance as additive skepticism only: it may highlight missing decisive comparisons or estimator caveats, but it must not replace authoritative evidence required by the resolved review target or project contract or create new manuscript obligations out of thin air.

Return STAGE 4 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 4: physical soundness"
)
```

If Stage 4 fails, STOP and report the failure.
</step>

<step name="stage_recovery_4">
**Stage 4 recovery -- Validate the physics output before proceeding.**

Check that `${REVIEW_ROOT}/STAGE-physics{round_suffix}.json` exists and run:

```bash
gpd validate review-stage-report ${REVIEW_ROOT}/STAGE-physics{round_suffix}.json
```

If validation fails:

1. **Retry once.** Re-run the Stage 4 subagent with the same inputs and an explicit reminder to match the `StageReviewReport` JSON schema from `peer-review-panel.md`, then rerun `gpd validate review-stage-report`.
2. **If the retry also fails,** STOP the pipeline and report the failure: stage name, missing or malformed fields, and any partial output. Do not proceed to Stage 5.

Max retries per stage: **1**.
After the Stage 4 typed return is captured and `${REVIEW_ROOT}/STAGE-physics{round_suffix}.json` validates, treat the finished Stage 4 handoff as closed and retired before spawning Stage 5. Stage 5 must start from the persisted stage artifacts and declared carry-forward inputs only.
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
Output path: `${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json`

Files to read:
- `MANUSCRIPT_STAGE_FILES`
- `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
	- `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json`
	- `${REVIEW_ROOT}/STAGE-literature{round_suffix}.json`
	- `${REVIEW_ROOT}/STAGE-physics{round_suffix}.json`
	- `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md` if proof-bearing review is active
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

Check that `${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json` exists and run:

```bash
gpd validate review-stage-report ${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json
```

If validation fails:

1. **Retry once.** Re-run the Stage 5 subagent with the same inputs and an explicit reminder to match the `StageReviewReport` JSON schema from `peer-review-panel.md`, then rerun `gpd validate review-stage-report`.
2. **If the retry also fails,** STOP the pipeline and report the failure: stage name, missing or malformed fields, and any partial output. Do not proceed to Stage 6 adjudication.

Max retries per stage: **1**.
After the Stage 5 typed return is captured and `${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json` validates, treat the finished Stage 5 handoff as closed and retired before spawning Stage 6. Stage 6 must begin from the persisted stage artifacts and declared carry-forward inputs only.
</step>

<step name="final_adjudication">
**Stage 6 — Final adjudication by `gpd-referee`.**

Load the staged final-adjudication payload before spawning `gpd-referee`:

```bash
FINAL_ADJUDICATION_INIT=$(gpd --raw init peer-review "$REVIEW_TARGET" --stage final_adjudication)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd peer-review final-adjudication init failed: $FINAL_ADJUDICATION_INIT"
  # STOP — display the error to the user and do not proceed.
fi
INIT="$FINAL_ADJUDICATION_INIT"
```

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
- `MANUSCRIPT_STAGE_FILES`
- `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-reader{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-literature{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-math{round_suffix}.json`
- `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md` if proof-bearing review is active
- `${REVIEW_ROOT}/STAGE-physics{round_suffix}.json`
- `${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json`
- `GPD/comparisons/*-COMPARISON.md` if present
- `${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md` if present
- `${ARTIFACT_MANIFEST_PATH}` if present
- `${BIBLIOGRAPHY_AUDIT_PATH}` if present
- `${REPRODUCIBILITY_MANIFEST_PATH}` if present
- `GPD/STATE.md` if present
- `GPD/ROADMAP.md` if present
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md` if present
- `GPD/phases/*/*-VERIFICATION.md` if present

If this is a revision round, also read the target-aware `latest_referee_report_md` and `latest_author_response` surfaced by `INIT` when present.

If any required staged-review artifact is missing, malformed, or uses the wrong round suffix, STOP and report that failure instead of falling back to standalone review.

Recommendation guardrails:
1. Do not issue minor revision if novelty, physical support, or significance remain materially doubtful.
2. A mathematically coherent but physically weak or scientifically mediocre paper can require major revision or rejection.
3. Evaluate venue fit explicitly using the panel artifacts and spot-check the manuscript where the artifacts are under-evidenced.
4. Treat protocol bundle guidance as additive context only. It can increase concern when decisive comparisons or benchmark anchors are missing, but it cannot rescue missing evidence or override the manuscript's actual artifact trail.
5. For proof-bearing claims, a missing, malformed, or non-passing `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md` artifact prevents any favorable recommendation. Recommendation floor: `major_revision` or `reject`.
6. Write `${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json` and `${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json`.
7. Keep `manuscript_path` non-empty and identical across `${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json`, `${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json`, and the staged-review artifacts for this round.
8. Run `gpd validate review-ledger ${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json`.
9. Run `gpd validate referee-decision ${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json --strict --ledger ${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json` before trusting any final recommendation.
10. If either validator fails, STOP and classify whether the failure is in Stage 6-owned artifacts or in upstream staged-review inputs before retrying anything.
11. Your writable scope is limited to Stage 6-owned adjudication artifacts for this round: `GPD/REFEREE-REPORT{round_suffix}.md`, `GPD/REFEREE-REPORT{round_suffix}.tex`, `${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json`, `${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json`, and `GPD/CONSISTENCY-REPORT.md` when applicable.
12. Do not modify `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`, any `${REVIEW_ROOT}/STAGE-*.json`, or `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`. If any of those upstream artifacts are missing, malformed, stale, or inconsistent, return `gpd_return.status: blocked` and hand the failure back to the earliest failing upstream stage instead of repairing it inside Stage 6.
13. Treat any `gpd_return.files_written` entry outside the Stage 6 allowlist as a failed handoff, not as a successful adjudication.

Write `GPD/REFEREE-REPORT{round_suffix}.md` and the matching `GPD/REFEREE-REPORT{round_suffix}.tex`.
Treat the referee report files as required final-stage artifacts. If either report file is missing after adjudication, the stage is incomplete even if the JSON validators passed.
Also write `GPD/CONSISTENCY-REPORT.md` when applicable.

Return REVIEW COMPLETE with recommendation, confidence, issue counts, and whether prior major concerns are resolved.",
  description="Peer review stage 6: final adjudication"
)
```

If the referee agent fails to spawn or returns an error, STOP and report the failure. Do not silently skip final adjudication.
Do not trust the referee's success text until the ledger, decision, and report files all exist on disk and validate. A returned recommendation without the files is incomplete.
Do not trust the referee's success text until that typed return, the on-disk files, and the validators all agree.
Treat the Stage 6 return as incomplete if the fresh `gpd_return.files_written` set omits a Stage 6 artifact written in this run or lists any upstream staged-review artifact path.
</step>

<step name="stage_recovery_6">
**Stage 6 recovery -- Validate the adjudication outputs before proceeding.**

Capture the Stage 6 typed return first, then treat the finished adjudication handoff as closed and retired before classifying the outcome as recovery-eligible, upstream-blocked, or complete. Recovery routing, validation, and final summarization must use the persisted Stage 6 artifacts plus the captured typed return; do not keep the adjudication run live while deciding what to do next.

Check that both `${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json` and `${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json` exist and parse as valid JSON.
Also confirm `GPD/REFEREE-REPORT{round_suffix}.md` and `GPD/REFEREE-REPORT{round_suffix}.tex` exist before treating the final recommendation as complete.
Require the fresh `gpd_return.files_written` set to stay within the Stage 6-owned allowlist: `GPD/REFEREE-REPORT{round_suffix}.md`, `GPD/REFEREE-REPORT{round_suffix}.tex`, `${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json`, `${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json`, and `GPD/CONSISTENCY-REPORT.md` when applicable. Treat any upstream staged-review path in `gpd_return.files_written` as a failed handoff.

Then run the built-in validators. These are the authoritative fail-closed schema and consistency checks for every final recommendation:

```bash
gpd validate review-ledger ${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json
gpd validate referee-decision ${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json --strict --ledger ${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json
```

If validation fails:

1. **Classify the failure first.** Distinguish Stage 6-owned artifact failures from upstream staged-review artifact failures.
2. **Only retry Stage 6 for Stage 6-owned artifacts.** If the failure is limited to `GPD/REFEREE-REPORT{round_suffix}.md`, `GPD/REFEREE-REPORT{round_suffix}.tex`, `${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json`, `${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json`, or `GPD/CONSISTENCY-REPORT.md`, re-run the Stage 6 referee subagent once with an explicit reminder to satisfy `review-ledger-schema.md` and `referee-decision-schema.md` by passing the built-in validators above.
3. **Do not retry Stage 6 as an upstream repair step.** If validation or consistency errors point at `CLAIMS{round_suffix}.json`, any `STAGE-*.json`, or `PROOF-REDTEAM{round_suffix}.md`, STOP fail-closed and rerun the earliest failing upstream stage instead of letting Stage 6 repair those inputs.
4. **If the eligible Stage 6 retry also fails,** STOP the pipeline and report the failure: stage name, validation errors, and any partial output. Do not proceed to report summarization.

Use this upstream fail-back routing:

- `CLAIMS{round_suffix}.json` or `STAGE-reader{round_suffix}.json` -> rerun Stage 1
- `STAGE-literature{round_suffix}.json` -> rerun Stage 2
- `STAGE-math{round_suffix}.json` or `PROOF-REDTEAM{round_suffix}.md` -> rerun Stage 3 and the proof-critique pass when applicable
- `STAGE-physics{round_suffix}.json` -> rerun Stage 4
- `STAGE-interestingness{round_suffix}.json` -> rerun Stage 5

If multiple upstream artifacts disagree, rerun the earliest stage in that list.

Treat blank `manuscript_path` values in either `${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json` or `${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json` as validation failures, not as optional bookkeeping.

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

Load the staged finalize payload before summarizing the report and routing the next action:

```bash
FINALIZE_INIT=$(gpd --raw init peer-review "$REVIEW_TARGET" --stage finalize)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd peer-review finalize init failed: $FINALIZE_INIT"
  # STOP — display the error to the user and do not proceed.
fi
INIT="$FINALIZE_INIT"
```

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
**Stage artifacts:** `${REVIEW_ROOT}/`
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
- [ ] Proof-bearing manuscripts also produce `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`
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

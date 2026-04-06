<purpose>
Run an independent parallel review alongside the primary six-stage peer-review panel to catch errors arising from single-agent self-consistency bias. The parallel reviewer operates on the same manuscript but uses deliberately different analytical strategies, then produces a divergence report that the referee must reconcile before issuing the final recommendation.
</purpose>

<core_principle>
A single review pipeline — no matter how well-staged — can converge on the same blind spots because all stages share implicit context and LLM tendencies. Parallel review breaks this by introducing an independent agent that:

1. Reads the manuscript without seeing the primary panel's intermediate artifacts
2. Verifies claims through alternative derivation paths
3. Stress-tests assumptions at their boundaries
4. Constructs explicit counter-narratives to the paper's main claims
5. Compares its findings with the primary panel's to identify divergences

The referee then reconciles any material divergences before issuing the final recommendation.
</core_principle>

<process>

<step name="init">
**Initialize context and verify parallel review is appropriate:**

```bash
INIT=$(gpd init phase-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `project_exists`, `state_exists`, `commit_docs`, `project_contract`, `project_contract_validation`, `project_contract_load_info`, `contract_intake`, `effective_reference_intake`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`.

**Determine invocation mode:**

1. **Standalone:** Invoked directly via `/gpd:parallel-review`. Run the full parallel review and feed results into the next peer-review round.
2. **Integrated:** Invoked as part of `/gpd:peer-review --parallel`. The parallel reviewer runs concurrently with Stages 1-5, and the divergence report is fed to Stage 6 (referee).

**Resolve manuscript target:**

Use the same resolution logic as `peer-review.md`:
1. If `$ARGUMENTS` names a directory, use it as the candidate paper directory.
2. If `$ARGUMENTS` names a `.tex` or `.md` file, use that file and its parent directory.
3. Otherwise search: `paper/main.tex`, `manuscript/main.tex`, `draft/main.tex`.

Set:
- `RESOLVED_MANUSCRIPT` = resolved entry point
- `MANUSCRIPT_ROOT` = parent directory
- Round detection follows the same convention as `peer-review.md`
</step>

<step name="preflight">
**Run preflight checks:**

```bash
gpd validate review-preflight parallel-review "$ARGUMENTS" --strict
```

If preflight exits nonzero, STOP and show blocking issues.

Verify the manuscript exists and is readable. The parallel reviewer does NOT require the full set of review-support artifacts (ARTIFACT-MANIFEST.json, BIBLIOGRAPHY-AUDIT.json) — it deliberately operates with less scaffolding than the primary panel to maintain independence.
</step>

<step name="announce">
**Announce the parallel review to the user:**

```
Launching parallel adversarial review: Phase 1 independently analyzes the manuscript's claims through alternative derivation paths and assumption stress-testing. Phase 2 compares findings with the primary panel to identify divergences. The referee will reconcile any material divergences.
```
</step>

<step name="phase_1_independent_review">
**Phase 1 — Independent manuscript analysis.**

This phase MUST run without access to any primary panel stage artifacts. It reads only the manuscript and direct support files.

Resolve parallel reviewer model:

```bash
PARALLEL_MODEL=$(gpd resolve-model gpd-parallel-reviewer)
```

> **Runtime delegation:** Spawn a fresh subagent for the task below. If `model` resolves to `null` or empty, omit it. Always pass `readonly=false`.

```
task(
  subagent_type="gpd-parallel-reviewer",
  model="{parallel_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-parallel-reviewer.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/verification/core/adversarial-review-protocol.md for the adversarial review protocol.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md for the stage artifact contract context.

Execute Phase 1 only (independent manuscript analysis). Do NOT read any primary panel STAGE-*.json artifacts.

Target journal: {target_journal}
Round: {round}
Output path: `GPD/review/PARALLEL-REVIEW{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- Summary artifacts matching `GPD/phases/*/*SUMMARY.md`
- `GPD/phases/*/*-VERIFICATION.md`
- All `*.bib` files under `${MANUSCRIPT_ROOT}`

Focus on:
1. Identify the 3-5 most critical claims and verify each through an alternative derivation path.
2. Stress-test the 3-5 most load-bearing assumptions at their boundaries.
3. Construct the strongest possible counter-narrative to the paper's main claim.
4. Cross-reference findings against the LLM physics error catalog.
5. Do NOT read any STAGE-*.json, CLAIMS.json, or other primary panel artifacts.

Return PHASE 1 COMPLETE with independent recommendation ceiling and key findings.",
  description="Parallel review phase 1: independent manuscript analysis"
)
```

If Phase 1 fails, STOP and report the failure.
</step>

<step name="phase_1_validation">
**Validate Phase 1 output:**

Check that `GPD/review/PARALLEL-REVIEW{round_suffix}.json` exists and contains the required fields:
- `version`, `round`, `stage_id`, `stage_kind`, `manuscript_path`, `manuscript_sha256`
- `independent_checks` (non-empty array)
- `assumption_stress_tests` (non-empty array)
- `counter_narrative` (non-null object)
- `recommendation_ceiling`, `confidence`

If validation fails:
1. **Retry once** with an explicit reminder to match the artifact schema.
2. **If retry fails,** STOP and report the failure.

Max retries: **1**.
</step>

<step name="wait_for_primary_panel">
**Wait for the primary panel to complete Stages 1-5:**

If running in integrated mode (`--parallel`), wait for the primary panel's Stages 1-5 to complete and their artifacts to be written:
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`
- `GPD/review/STAGE-literature{round_suffix}.json`
- `GPD/review/STAGE-math{round_suffix}.json`
- `GPD/review/STAGE-physics{round_suffix}.json`
- `GPD/review/STAGE-interestingness{round_suffix}.json`

If running in standalone mode, check whether these artifacts exist from a prior peer-review run. If they do not exist, skip Phase 2 and write a standalone divergence report noting that cross-comparison was not possible.
</step>

<step name="phase_2_divergence_analysis">
**Phase 2 — Cross-panel divergence analysis.**

This phase runs AFTER the primary panel completes Stages 1-5 and AFTER Phase 1 completes.

```
task(
  subagent_type="gpd-parallel-reviewer",
  model="{parallel_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-parallel-reviewer.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/verification/core/adversarial-review-protocol.md for the adversarial review protocol.

Execute Phase 2 only (cross-panel divergence analysis).

Round: {round}
Output path: `GPD/review/DIVERGENCE-REPORT{round_suffix}.json`

Files to read:
- `GPD/review/PARALLEL-REVIEW{round_suffix}.json` (your Phase 1 output)
- `GPD/review/CLAIMS{round_suffix}.json`
- `GPD/review/STAGE-reader{round_suffix}.json`
- `GPD/review/STAGE-literature{round_suffix}.json`
- `GPD/review/STAGE-math{round_suffix}.json`
- `GPD/review/STAGE-physics{round_suffix}.json`
- `GPD/review/STAGE-interestingness{round_suffix}.json`

Focus on:
1. Compare your independent findings with the panel's findings claim by claim.
2. Identify every divergence where you and the panel disagree.
3. Classify each divergence as material or minor.
4. For each material divergence, provide specific evidence supporting your position.
5. Assess whether the panel's recommendation ceiling is justified given the divergences.

Return PHASE 2 COMPLETE with material divergence count and reconciliation priority items.",
  description="Parallel review phase 2: cross-panel divergence analysis"
)
```

If Phase 2 fails, STOP and report the failure.
</step>

<step name="phase_2_validation">
**Validate Phase 2 output:**

Check that `GPD/review/DIVERGENCE-REPORT{round_suffix}.json` exists and contains:
- `version`, `round`, `manuscript_path`, `manuscript_sha256`
- `divergences` (array, may be empty if no divergences found)
- `material_divergence_count` (integer)
- `reconciliation_required` (boolean)
- `parallel_recommendation_ceiling`, `panel_recommendation_ceiling`

If validation fails:
1. **Retry once** with an explicit reminder to match the artifact schema.
2. **If retry fails,** STOP and report the failure.

Max retries: **1**.
</step>

<step name="summarize">
**Summarize parallel review results:**

```markdown
## Parallel Review Summary

**Phase 1 — Independent Analysis:**
- Independent checks performed: {N}
- Assumption stress tests: {M}
- Counter-narrative strength: {rebuttal_strength}
- Independent recommendation ceiling: {ceiling}

**Phase 2 — Divergence Analysis:**
- Total divergences: {total}
- Material divergences: {material_count}
- Reconciliation required: {yes/no}
- Priority items: {list}

**Artifacts:**
- `GPD/review/PARALLEL-REVIEW{round_suffix}.json`
- `GPD/review/DIVERGENCE-REPORT{round_suffix}.json`
```
</step>

<step name="route_to_referee">
**Route divergence report to the referee:**

If running in integrated mode, the divergence report is automatically included in the Stage 6 referee's input files. The referee MUST read `GPD/review/DIVERGENCE-REPORT{round_suffix}.json` and reconcile any material divergences before issuing the final recommendation.

If running in standalone mode:
- If material divergences exist and `reconciliation_required` is true, recommend re-running `/gpd:peer-review --parallel` to get a reconciled recommendation.
- If no material divergences exist, report that the parallel review confirms the primary panel's assessment.
</step>

</process>

<success_criteria>
- [ ] Manuscript target resolved
- [ ] Phase 1 independent analysis completed without reading panel artifacts
- [ ] PARALLEL-REVIEW artifact written with non-empty independent checks
- [ ] Phase 1 output validated
- [ ] Phase 2 divergence analysis completed (if panel artifacts available)
- [ ] DIVERGENCE-REPORT artifact written
- [ ] Phase 2 output validated
- [ ] Results summarized
- [ ] Divergence report routed to referee or user
</success_criteria>

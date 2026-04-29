<purpose>
Compare internal results, baselines, or methods and emit a machine-readable comparison artifact. Use this for analytics-vs-numerics, cross-method checks, baseline-vs-current runs, or any decisive internal comparison that should not stay implicit in prose.
</purpose>

<required_reading>
Read these files using the file_read tool:
- {GPD_INSTALL_DIR}/templates/paper/internal-comparison.md -- Template for decisive internal comparisons and verdict ledgers
</required_reading>

<process>

## 0. Load Project Context

Keep this init bound to the workspace the user invoked from. `compare-results` can run as a current-workspace standalone comparison, so do not auto-reenter a different recent project here.

```bash
INIT=$(gpd --raw init progress --include state --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `state_exists`, `project_exists`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `active_reference_context`, `derived_convention_lock`

If the relevant phase or artifact is contract-backed, resolve:
- `subject_id`
- `subject_kind`
- `subject_role`
- any linked `reference_id`
- the decisive threshold or pass condition

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true.
If `active_reference_context` is non-empty, keep that anchor ledger visible while resolving `subject_id`, `reference_id`, thresholds, and comparison linkage.
If `derived_convention_lock` is non-empty, keep that canonical lock visible while checking shared conventions and normalization between Source A, Source B, and the verdict threshold.
If `state_exists` is false in the current workspace, require the user to provide the comparison sources, shared conventions, and decisive threshold explicitly instead of inferring them from another project.

Do not drop back to generic prose when a contract-backed target exists.

## 1. Identify The Two Sides Of The Comparison

Establish:
- **Source A** — derivation, code path, phase output, baseline run, or prior artifact
- **Source B** — benchmark, alternate method, validation run, literature anchor, or expected behavior
- **Shared parameters** — what settings, regime, and conventions must match
- **Metric** — relative error, pull, chi-squared, overlap, consistency condition, or qualitative regime check
- **Threshold** — what counts as pass, tension, fail, or inconclusive

If the target or sources are ambiguous, ask the user before proceeding.

## 2. Verify The Comparison Is Legitimate

Before computing any verdict:
- confirm both sides represent the same observable or deliverable
- confirm the same conventions and normalization are being used
- confirm any tolerance or threshold is tied to the right anchor or scientific purpose
- reject comparisons that only validate a proxy while the decisive target remains unchecked

## 3. Compute The Comparison

For each quantity or artifact:
- compute the metric
- record the threshold
- classify the verdict: `pass`, `tension`, `fail`, or `inconclusive`
- record the follow-up action if the verdict is not a clean pass

When the comparison is decisive, always emit `comparison_verdicts`. Do not hide the answer only in tables or prose.

## 4. Write The Artifact

Set `COMPARISON_OUTPUT_PATH="GPD/comparisons/[slug]-COMPARISON.md"` and create the current-workspace managed comparison root before writing any GPD-authored outputs.

```bash
mkdir -p GPD/comparisons
```

Write `${COMPARISON_OUTPUT_PATH}` using the internal-comparison template.

The frontmatter must include:
- `comparison_verdicts`
- `comparison_sources`
- `subject_id` / `reference_id` linkage when available

After writing `${COMPARISON_OUTPUT_PATH}`, run:

```bash
gpd validate comparison-contract "${COMPARISON_OUTPUT_PATH}"
```

If validation fails, treat the comparison artifact as incomplete: fix the frontmatter ledger before routing, committing, or presenting it as decisive evidence.

If the comparison is load-bearing for a figure or table, note the resulting artifact path so the figure tracker can point back to it.
Any additional GPD-authored notes, tables, or helper artifacts created for this comparison should stay under the same current-workspace `GPD/comparisons/` subtree.

## 5. Route The Outcome

- If decisive verdict is `pass`: surface the artifact for verification and paper-writing.
- If decisive verdict is `tension` or `fail`: recommend the next bounded debugging or verification action explicitly.
- If decisive verdict is `inconclusive`: identify the missing data or missing normalization needed to make it decisive.

</process>

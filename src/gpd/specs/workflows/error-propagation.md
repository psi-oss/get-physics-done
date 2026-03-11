<purpose>
Systematic uncertainty propagation through a derivation chain. Traces how input uncertainties flow through intermediate results to final quantities, identifies dominant error sources, and produces error budgets.

Called from /gpd:error-propagation command. Complements /gpd:numerical-convergence (which establishes error bars on individual computations) by tracing how those errors combine through multi-step derivation chains.

A numerical result without error bars is not a result. But error bars on a final quantity are only meaningful if the propagation from input uncertainties through every intermediate step is tracked systematically. An error bar that ignores the dominant uncertainty source is worse than no error bar at all -- it provides false confidence.
</purpose>

<core_principle>
Uncertainties propagate. Every intermediate result in a derivation chain carries error bars from its inputs, and those errors compound -- sometimes canceling, sometimes amplifying -- as they flow through to the final quantity. The job of error propagation is to trace this flow systematically: build the dependency tree, compute how each input uncertainty transforms at every step, and arrive at a total error budget for the target quantity.

**The contract:** Every uncertainty source must be accounted for -- input measurement errors, approximation-induced systematics, numerical truncation, and model limitations. The dominant error source must be identified, because an error budget that misses the largest contributor provides false confidence. A final result quoted as "X +/- delta" is only meaningful if delta reflects the true dominant uncertainty, not just the easiest one to compute.
</core_principle>

<required_reading>
Read these reference and template files using the file_read tool:
- {GPD_INSTALL_DIR}/references/protocols/error-propagation-protocol.md -- Cross-phase uncertainty propagation protocol (verification checks, phase handoff format, catastrophic cancellation detection)
- {GPD_INSTALL_DIR}/templates/uncertainty-budget.md -- Template for project-wide uncertainty ledger (.gpd/analysis/UNCERTAINTY-BUDGET.md)
- {GPD_INSTALL_DIR}/templates/parameter-table.md -- Template for parameter registry (.gpd/analysis/PARAMETERS.md)
</required_reading>

<process>

<step name="identify_target">
## 1. Identify the Target Quantity

Determine what final result needs error bars.

**Parse arguments:**

- `--target quantity`: the specific observable or derived quantity to analyze
- `--phase-range start:end`: restrict analysis to phases in this range
- If neither provided: prompt for the target quantity

**Load project state:**

```bash
INIT=$(gpd init progress --include state,roadmap,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `state_exists`, `project_exists`, `roadmap_exists`.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context error-propagation "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

**If `state_exists` is false:**

```
ERROR: No project state found.

Error propagation requires intermediate_results tracked in STATE.md.
Run /gpd:new-project first, then complete phases with tracked results.
```

Exit.

Read STATE.md to identify:

- The target quantity (from `intermediate_results` or final results)
- The phase range containing the derivation chain
- Any existing `propagated_uncertainties` entries

If the target is not found in STATE.md intermediate_results, check SUMMARY.md files across phases for the quantity name.
</step>

<step name="trace_derivation_chain">
## 2. Trace the Derivation Chain

Build the complete dependency tree from inputs to the target quantity.

**From state.json:**

Read `intermediate_results` and follow `depends_on` chains backward from the target:

```
target_quantity
  <- intermediate_result_A (phase 05)
       <- intermediate_result_B (phase 03)
            <- input_parameter_1 (phase 01)
            <- input_parameter_2 (phase 01)
       <- intermediate_result_C (phase 04)
            <- input_parameter_3 (phase 02)
            <- approximation_X (phase 02)
  <- intermediate_result_D (phase 04)
       <- input_parameter_1 (phase 01)  [shared dependency]
```

**From SUMMARY.md files:**

Read each phase's SUMMARY.md `provides` and `requires` sections to map the phase-level flow:

```bash
for phase_dir in .gpd/phases/*/; do
  grep -A 10 "provides\|requires" "$phase_dir/SUMMARY.md" 2>/dev/null
done
```

**Build the dependency tree:**

Record for each node:

- Quantity name and symbol
- Phase where it is computed
- Mathematical expression (how it depends on its inputs)
- Current value (if numerical)
- Current uncertainty (if already known)

Display the tree:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > ERROR PROPAGATION: DEPENDENCY TREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Target: {quantity} ({symbol})

{tree visualization with indentation}

Nodes: {N} quantities across {M} phases
Leaf inputs: {K} parameters
```

</step>

<step name="identify_uncertainty_sources">
## 3. Identify Uncertainty Sources at Each Step

For each node in the dependency tree, catalog all uncertainty sources.

### 3a. Input parameter uncertainties

**State integrity check:** `propagated_uncertainties` lives in authoritative `state.json`. Before reading it, verify the paired state files are healthy:

```bash
gpd --raw state validate
```

If validation reports divergence or a parse error, stop here and run `/gpd:sync-state` (or the controlled backup + `gpd --raw state snapshot` recovery path) before trusting uncertainty values. If recovery is blocked, fall back to `STATE.md`'s `## Intermediate Results` and `## Propagated Uncertainties` sections, and clearly label the result as markdown-recovered rather than JSON-backed.

Read `propagated_uncertainties` in state.json for existing uncertainty values on input parameters. For each leaf input:

| Parameter | Value | Uncertainty | Source of Uncertainty                 |
| --------- | ----- | ----------- | ------------------------------------- |
| {param}   | {val} | {delta}     | {measurement / literature / estimate} |

### 3b. Approximation-induced uncertainties

Read `approximations` in state.json. For each approximation in the derivation chain:

- Identify the validity boundary (e.g., "valid for epsilon << 1, currently epsilon = 0.1")
- Estimate the next-order correction as the systematic uncertainty
- The order of magnitude of the neglected terms gives the approximation error

| Approximation | Phase | Validity Condition | Current Regime | Estimated Error |
| ------------- | ----- | ------------------ | -------------- | --------------- |
| {approx}      | {N}   | {condition}        | {value}        | {O(epsilon^n)}  |

### 3c. Numerical uncertainties

From SUMMARY.md computational results and any CONVERGENCE.md reports:

- Truncation errors (from basis set or series truncation)
- Discretization errors (from finite grid spacing or time step)
- Convergence errors (from iterative solvers or Monte Carlo statistics)

If /gpd:numerical-convergence has been run, read the convergence report for error estimates. If not, flag these as "numerical uncertainty not yet quantified" and recommend running convergence tests.

### 3d. Model uncertainties

Identify where the physical model itself introduces uncertainty:

- Higher-order terms dropped in a perturbative expansion
- Simplified interactions (e.g., nearest-neighbor only, mean-field approximation)
- Phenomenological parameters with uncertain values

These are typically the hardest to quantify and often dominate the error budget.
</step>

<step name="propagate_uncertainties">
## 4. Propagate Uncertainties

Work forward through the dependency tree, from leaf inputs to the target.

### 4a. Analytical expressions: standard error propagation

For a quantity f(x_1, x_2, ..., x_n) with known functional form:

```
delta_f = sqrt( sum_i (df/dx_i)^2 * (delta_x_i)^2 )   [independent errors]
delta_f = sum_i |df/dx_i| * delta_x_i                    [correlated errors, worst case]
```

At each node where the functional form is known:

1. Compute partial derivatives df/dx_i (analytically or numerically)
2. Multiply each by the corresponding input uncertainty
3. Combine in quadrature (independent) or linearly (correlated)

**Correlation tracking:** If two inputs share a common upstream dependency (e.g., both depend on input_parameter_1), their errors are correlated. Track shared dependencies from the tree and use linear addition for the correlated part:

```
delta_f^2 = sum_{i,j} (df/dx_i)(df/dx_j) * cov(x_i, x_j)
```

### 4b. Numerical computations: sensitivity analysis

For steps where the functional form is not analytically available (e.g., numerical ODE solutions, Monte Carlo results):

1. Run the computation with each input varied by +/- its uncertainty
2. Measure the output change
3. The numerical partial derivative is: df/dx_i ~ (f(x_i + delta) - f(x_i - delta)) / (2 \* delta)

```python
# Template sensitivity analysis
def sensitivity(compute_fn, base_inputs, param_name, delta):
    inputs_plus = {**base_inputs, param_name: base_inputs[param_name] + delta}
    inputs_minus = {**base_inputs, param_name: base_inputs[param_name] - delta}
    return (compute_fn(**inputs_plus) - compute_fn(**inputs_minus)) / (2 * delta)
```

### 4c. Approximation uncertainties

For each approximation used in the derivation:

- Estimate the next-order correction as the systematic error
- If the expansion parameter is epsilon, and the calculation is done to O(epsilon^n), the uncertainty is O(epsilon^{n+1}) times the leading term
- If the next-order correction can be computed, use it directly

### 4d. Combining error types

At each node, maintain separate error contributions by type:

| Error Type  | How to Combine                               |
| ----------- | -------------------------------------------- |
| Statistical | Quadrature (independent by construction)     |
| Systematic  | Linear addition (conservative) or quadrature |
| Truncation  | Estimate from next-order term                |
| Model       | Usually treated as systematic                |
| Correlated  | Full covariance propagation                  |

The total uncertainty at each node is the combination of all sources, tracked separately so the error budget can identify dominance.
</step>

<step name="produce_error_budget">
## 5. Produce Error Budget

Generate the error budget table for the target quantity:

```markdown
## Error Budget: {target quantity}

### Uncertainty Contributions

| #   | Source               | Type                                      | Phase   | Magnitude | Fraction of Total |
| --- | -------------------- | ----------------------------------------- | ------- | --------- | ----------------- |
| 1   | {source description} | {statistical/systematic/truncation/model} | {phase} | {value}   | {percentage}      |
| 2   | ...                  | ...                                       | ...     | ...       | ...               |

### Summary

| Metric                 | Value                                           |
| ---------------------- | ----------------------------------------------- |
| Target quantity        | {symbol}                                        |
| Central value          | {value}                                         |
| Total uncertainty      | {delta}                                         |
| Relative uncertainty   | {delta/value}                                   |
| Dominant error source  | {source}                                        |
| Most improvable source | {source that would most reduce total if halved} |

### Dominant Error Analysis

**Dominant source:** {source} contributes {fraction}% of the total uncertainty.

**Improvement potential:** Reducing {most_improvable_source} by a factor of 2 would reduce the total uncertainty by {factor}.

### Correlation Structure

{If correlated errors exist:}

| Pair       | Shared Upstream     | Correlation Type    | Impact            |
| ---------- | ------------------- | ------------------- | ----------------- |
| {x_i, x_j} | {common dependency} | {positive/negative} | {effect on total} |
```

Resolve the target phase directory:

```bash
TARGET_PHASE_INFO=$(gpd phase find "${target_phase_number}")
```

Extract `target_phase_dir` (the `directory` field) from the JSON result.

Save to: `${target_phase_dir}/ERROR-BUDGET.md`.

</step>

<step name="update_state">
## 6. Update State

Add the final result with error bars to `propagated_uncertainties` in state.json:

```bash
gpd uncertainty add \
  --quantity "{symbol}" --value "{central_value}" \
  --uncertainty "{delta}" --phase "{phase}" --method "error-propagation"
```

Record the error budget as a research artifact in STATE.md.

</step>

<step name="commit">
## 7. Commit

```bash
PRE_CHECK=$(gpd pre-commit-check --files ${target_phase_dir}/ERROR-BUDGET.md .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: error propagation analysis for {quantity}" --files ${target_phase_dir}/ERROR-BUDGET.md .gpd/STATE.md
```

Present results:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > ERROR PROPAGATION: COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Target: {quantity} = {value} +/- {uncertainty} ({relative}%)

Dominant error: {source} ({fraction}%)
Most improvable: {source}

Error budget: ${target_phase_dir}/ERROR-BUDGET.md

───────────────────────────────────────────────────────────────

**Also available:**
- `/gpd:numerical-convergence` -- refine error bars on individual computations
- `/gpd:verify-work` -- verify the full phase including error analysis
- `/gpd:regression-check` -- check that error budgets remain valid after changes

───────────────────────────────────────────────────────────────
```

</step>

</process>

<failure_handling>

- **Dependency tree cannot be traced:** If `depends_on` chains are missing or incomplete in state.json, fall back to reading SUMMARY.md `provides`/`requires` sections across phases. If the chain still has gaps, report the incomplete tree to the user and ask them to identify the missing links before proceeding.
- **Numerical sensitivity diverges:** If a finite-difference derivative yields Inf or NaN, reduce the perturbation step size by 10x and retry. If it still diverges, the computation is at or near a singularity -- flag the parameter and phase, report the divergence, and exclude it from the quadrature sum (treat it as a separate critical warning in the error budget).
- **Target quantity not found:** If the target is not present in `intermediate_results`, `propagated_uncertainties`, or any phase SUMMARY.md, report which phases were searched and prompt the user to specify the quantity's location or run the relevant computation first.
- **State files missing:** If STATE.md or state.json does not exist, error immediately with a clear message: "No project state found. Run `/gpd:new-project` or `/gpd:execute-phase` first to establish project state before running error propagation."

</failure_handling>

<success_criteria>

- [ ] Target quantity identified and located in project state
- [ ] Complete dependency tree traced from inputs to target
- [ ] All uncertainty sources cataloged at each step (input, approximation, numerical, model)
- [ ] Partial derivatives computed (analytically or numerically) for error propagation
- [ ] Correlated errors identified and handled correctly (shared upstream dependencies)
- [ ] Uncertainties propagated forward through the full derivation chain
- [ ] Error budget table produced with source, type, magnitude, and fraction
- [ ] Dominant error source identified
- [ ] Most improvable source identified (greatest reduction in total uncertainty per effort)
- [ ] Final result with error bars added to propagated_uncertainties in state
- [ ] ERROR-BUDGET.md written and committed
- [ ] Results presented with actionable next steps

</success_criteria>

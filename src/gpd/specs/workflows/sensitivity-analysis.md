<purpose>
Determine which input parameters most strongly affect output quantities. Compute partial derivatives, condition numbers, and rank parameters by sensitivity. Identifies which measurements or calculations would most improve final results.

Called from /gpd:sensitivity-analysis command. Used to prioritize effort: if parameter A contributes 90% of the uncertainty while parameter B contributes 1%, improving the precision of A has 90x the impact of improving B.
</purpose>

<core_principle>
Not all parameters are created equal. In any physics calculation, some inputs dominate the uncertainty of the output while others are essentially irrelevant. Sensitivity analysis answers the question: "If I could improve the precision of one input, which one would reduce the output uncertainty the most?"

**The sensitivity hierarchy:**

1. Which parameters does the result depend on? (Identify)
2. How strongly does it depend on each? (Quantify)
3. Which dependencies are dangerous? (Flag divergences, resonances, critical points)
4. Where should effort be directed? (Rank and recommend)

A result quoted as "E = 3.7 +/- 0.2 eV" is incomplete without knowing what drives that 0.2 eV. Is it the coupling constant? The cutoff? The grid spacing? The approximation order? Without sensitivity analysis, error bars are numbers without actionable meaning.
</core_principle>

<process>

<step name="initialize" priority="first">
Load project context:

```bash
INIT=$(gpd init phase-op --include state,config "${PHASE_ARG:-}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `executor_model`, `verifier_model`, `commit_docs`, `parallelization`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `phase_slug`, `state_exists`, `roadmap_exists`.

Read STATE.md for project conventions, unit system, and active approximations.
Extract `convention_lock` for unit conventions and parameter definitions.
Extract `intermediate_results` for previously computed parameter values and their uncertainties.
If `.gpd/analysis/PARAMETERS.md` exists, use it as the parameter registry (see `{GPD_INSTALL_DIR}/templates/parameter-table.md` for the template).
If no project context exists (standalone usage), proceed with explicit parameter declarations required from user.

**Convention verification** (if project exists):

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — parameter definitions may be inconsistent"
  echo "$CONV_CHECK"
fi
```

**If `phase_found` is false and a phase was specified:** Error -- phase directory not found.
**If no phase specified:** Create an analysis-specific directory:

```bash
ANALYSIS_DIR=".gpd/analysis"
mkdir -p "$ANALYSIS_DIR"
```

</step>

<step name="define_scope">
**Step 1: Define Scope**

Identify the target quantity and the parameters to analyze.

### 1a. Target quantity

Determine what output quantity f we are analyzing the sensitivity of:

- Load project state via `gpd CLI init progress --include state,config` and check `intermediate_results` for computed quantities
- Read from phase SUMMARY.md files for key results
- If `--target` is specified, use that quantity directly

```markdown
## Sensitivity Target

**Output quantity:** f = {description of the quantity}
**Expression:** f(p_1, p_2, ..., p_N) = {functional form if known}
**Nominal value:** f_0 = {current best value}
**Location:** {file:line or phase where computed}
```

### 1b. Parameter identification

Identify all input parameters that f depends on:

1. **Physical parameters:** masses, coupling constants, temperatures, fields, lengths
2. **Numerical parameters:** grid sizes, cutoffs, basis sizes, tolerances
3. **Approximation controls:** expansion orders, truncation levels, regime boundaries
4. **Measured inputs:** experimental values used in the calculation

Read from `.gpd/STATE.md` to identify active approximations and their controlling parameters. Where structured data is needed, load via `gpd CLI init progress --include state,config`.

```markdown
## Parameters

| #   | Parameter | Symbol | Nominal Value | Uncertainty | Source                |
| --- | --------- | ------ | ------------- | ----------- | --------------------- |
| 1   | {name}    | p_1    | {value}       | {delta_p_1} | {where it comes from} |
| 2   | {name}    | p_2    | {value}       | {delta_p_2} | {source}              |
```

If `--params` is specified, restrict analysis to those parameters. Otherwise analyze all identified parameters.
</step>

<step name="choose_method">
**Step 2: Choose Method**

Select the sensitivity analysis method based on the nature of the problem.

### 2a. Analytical method

Best when closed-form expressions exist for f(p_1, ..., p_N).

Compute partial derivatives symbolically from the derivation chain:

```python
# Symbolic sensitivity computation
import sympy as sp

# Define symbols
p1, p2, p3 = sp.symbols('p1 p2 p3', positive=True)

# The target function (from the derivation)
f = ...  # symbolic expression

# Partial derivatives
for p in [p1, p2, p3]:
    df_dp = sp.diff(f, p)
    S = sp.simplify(df_dp * p / f)  # dimensionless sensitivity
    print(f"df/d{p} = {df_dp}")
    print(f"S_{p} = {S}")
```

**When to use:** The functional form f(p_1, ..., p_N) is available as a closed-form expression.

### 2b. Numerical method

Best for complex computation chains where no single closed-form expression exists.

Finite-difference approximation: perturb each parameter by +/-delta, measure output change:

```python
import numpy as np

def compute_f(params):
    """The full computation pipeline."""
    ...
    return value

def numerical_sensitivity(compute_fn, params, param_names, delta_frac=0.01):
    """Compute sensitivity by central finite differences."""
    f0 = compute_fn(params)
    sensitivities = {}

    for i, name in enumerate(param_names):
        params_plus = params.copy()
        params_minus = params.copy()
        delta = abs(params[i]) * delta_frac if params[i] != 0 else delta_frac

        params_plus[i] += delta
        params_minus[i] -= delta

        f_plus = compute_fn(params_plus)
        f_minus = compute_fn(params_minus)

        # Central difference derivative
        df_dp = (f_plus - f_minus) / (2 * delta)

        # Dimensionless sensitivity coefficient
        S = df_dp * params[i] / f0 if f0 != 0 else df_dp * params[i]

        sensitivities[name] = {
            'df_dp': df_dp,
            'S': S,
            'f_plus': f_plus,
            'f_minus': f_minus,
        }

    return f0, sensitivities
```

**When to use:** The computation is a pipeline of steps without a single closed-form expression, or the expression is too complex for symbolic differentiation.

### 2c. Combined method

Use analytical derivatives where closed-form expressions exist and numerical derivatives where they do not. This is the default when `--method` is not specified.

For each parameter:

- If the dependence is through a known formula: use analytical
- If the dependence is through a numerical computation: use numerical
- Document which method was used for each parameter
  </step>

<step name="compute_sensitivity">
**Step 3: Compute Sensitivity Coefficients**

For each parameter p_i, compute the dimensionless sensitivity coefficient:

```
S_i = (partial f / partial p_i) * (p_i / f)
```

This is the fractional change in the output per fractional change in the input. A sensitivity of S_i = 2 means a 1% change in p_i produces a 2% change in f.

### 3a. Evaluate at nominal values

Compute S_i at the nominal (best-estimate) parameter values:

```python
# For each parameter p_i
for i, (name, p_nom, delta_p) in enumerate(parameters):
    # Compute df/dp_i at nominal values
    df_dp = ...  # analytical or numerical

    # Dimensionless sensitivity
    S_i = df_dp * p_nom / f_nominal

    # Absolute sensitivity (contribution to output uncertainty)
    delta_f_i = abs(df_dp) * delta_p

    # Fractional contribution to output uncertainty
    frac_contribution_i = delta_f_i / total_uncertainty

    print(f"Parameter: {name}")
    print(f"  S_i = {S_i:.4f}")
    print(f"  delta_f from delta_{name} = {delta_f_i:.6e}")
    print(f"  Fraction of total uncertainty: {frac_contribution_i:.1%}")
```

### 3b. Evaluate at boundary values

For each parameter, also compute the sensitivity at the boundaries of the validity regime:

```python
# Check sensitivity stability across the parameter range
for name, p_nom, delta_p, p_min, p_max in parameters:
    S_at_nominal = compute_S(p_nom)
    S_at_lower = compute_S(p_min)
    S_at_upper = compute_S(p_max)

    variation = max(abs(S_at_lower - S_at_nominal), abs(S_at_upper - S_at_nominal))
    relative_variation = variation / abs(S_at_nominal) if S_at_nominal != 0 else float('inf')

    print(f"Parameter: {name}")
    print(f"  S(nominal) = {S_at_nominal:.4f}")
    print(f"  S(lower)   = {S_at_lower:.4f}")
    print(f"  S(upper)   = {S_at_upper:.4f}")
    print(f"  Variation:   {relative_variation:.1%}")

    if relative_variation > 0.5:
        print(f"  WARNING: Sensitivity varies by >{relative_variation:.0%} across range -- nonlinear regime")
```

### 3c. Flag divergent sensitivities

Check for parameters where the sensitivity diverges or becomes very large:

```python
DIVERGENCE_THRESHOLD = 100  # |S| > 100 is almost certainly a problem

for name, S_values in sensitivity_scan.items():
    max_S = max(abs(s) for s in S_values)

    if max_S > DIVERGENCE_THRESHOLD:
        print(f"CRITICAL: |S_{name}| = {max_S:.1f} -- sensitivity divergence detected")
        print(f"  This may indicate:")
        print(f"  - Critical point (phase transition, resonance)")
        print(f"  - Cancellation (result is small difference of large terms)")
        print(f"  - Ill-conditioned formulation")
```

Divergent sensitivity near a specific parameter value often indicates:

| Pattern                         | Likely cause                | Prescription                                                                  |
| ------------------------------- | --------------------------- | ----------------------------------------------------------------------------- |
| S -> infinity at p = p_c        | Critical point or resonance | Analyze the singularity structure; result may need non-perturbative treatment |
| S oscillates rapidly            | Interference or aliasing    | Check for cancellation, increase numerical precision                          |
| S changes sign                  | Extremum in f(p)            | The output is at a maximum or minimum with respect to this parameter          |
| S ~ 1/epsilon for small epsilon | Regularization sensitivity  | The result depends on the regulator -- physics issue, not numerics            |

</step>

<step name="rank_parameters">
**Step 4: Rank Parameters**

### 4a. Sort by absolute sensitivity

Rank parameters by their impact on the output uncertainty:

```python
# Sort by contribution to output uncertainty
ranked = sorted(parameters, key=lambda p: abs(p['df_dp'] * p['delta']), reverse=True)

print("Parameter Ranking (by contribution to output uncertainty):")
print(f"{'Rank':>4} {'Parameter':>20} {'|S_i|':>10} {'delta_f_i':>12} {'% of total':>10}")
print("-" * 60)

cumulative = 0.0
for rank, p in enumerate(ranked, 1):
    delta_f = abs(p['df_dp'] * p['delta'])
    pct = delta_f / total_uncertainty * 100
    cumulative += pct
    print(f"{rank:4d} {p['name']:>20} {abs(p['S']):.4f} {delta_f:.6e} {pct:8.1f}%  (cumul: {cumulative:.0f}%)")
```

### 4b. Identify stiff directions

Look for large sensitivity ratios between parameters (stiff parameter space):

```python
S_values = [abs(p['S']) for p in ranked]
if len(S_values) >= 2:
    stiffness_ratio = S_values[0] / S_values[-1] if S_values[-1] != 0 else float('inf')
    print(f"\nStiffness ratio (max/min sensitivity): {stiffness_ratio:.1f}")

    if stiffness_ratio > 100:
        print("STIFF: Parameter space has widely separated sensitivity scales.")
        print(f"  Most sensitive:  {ranked[0]['name']} (|S| = {S_values[0]:.4f})")
        print(f"  Least sensitive: {ranked[-1]['name']} (|S| = {S_values[-1]:.6f})")
        print("  Implication: effort should focus almost entirely on the most sensitive parameters.")
```

### 4c. Identify null directions

Find parameter combinations that do not affect the result:

```python
# Check for near-zero sensitivities
NULL_THRESHOLD = 1e-4  # |S| below this is effectively zero

null_params = [p for p in ranked if abs(p['S']) < NULL_THRESHOLD]
if null_params:
    print(f"\nNull directions ({len(null_params)} parameters with negligible sensitivity):")
    for p in null_params:
        print(f"  {p['name']}: |S| = {abs(p['S']):.2e} -- result is insensitive to this parameter")
    print("  These parameters can be set to convenient values without affecting the output.")
```

Also check for correlated null directions -- parameter combinations that cancel:

```python
# For pairs of parameters, check if their effects cancel
for i in range(len(ranked)):
    for j in range(i + 1, len(ranked)):
        p_i, p_j = ranked[i], ranked[j]
        # If sensitivities are nearly equal and opposite, there is a null direction
        if abs(p_i['S'] + p_j['S']) < 0.1 * max(abs(p_i['S']), abs(p_j['S'])):
            print(f"  Correlated null direction: {p_i['name']} and {p_j['name']}")
            print(f"  S_{p_i['name']} = {p_i['S']:.4f}, S_{p_j['name']} = {p_j['S']:.4f}")
            print(f"  The result depends on their difference, not individual values.")
```

</step>

<step name="approximation_sensitivity">
**Step 5: Analyze Approximation Sensitivity**

For each active approximation in the project (read from `.gpd/STATE.md`; load structured data via `gpd CLI init progress --include state,config` if needed):

### 5a. Identify controlling parameters

Each approximation has a controlling parameter that determines its validity:

| Approximation       | Controlling Parameter | Valid When | Breaks When |
| ------------------- | --------------------- | ---------- | ----------- |
| Perturbation theory | coupling g            | g << 1     | g ~ 1       |
| Non-relativistic    | v/c                   | v/c << 1   | v/c ~ 1     |
| Classical limit     | S/hbar                | S >> hbar  | S ~ hbar    |
| Thermodynamic limit | 1/N                   | N >> 1     | N ~ 1       |
| Mean-field          | 1/z (coordination)    | z >> 1     | z ~ 1       |
| Continuum limit     | a/L (lattice/system)  | a << L     | a ~ L       |

### 5b. Boundary sensitivity

For each approximation, compute what happens as the controlling parameter approaches the validity boundary:

```python
def approximation_sensitivity(compute_with_approx, compute_exact_or_next_order,
                               control_param_values):
    """Measure how the result changes as we approach the approximation boundary."""
    results = []
    for val in control_param_values:
        f_approx = compute_with_approx(val)
        f_better = compute_exact_or_next_order(val)

        systematic_error = abs(f_approx - f_better)
        relative_error = systematic_error / abs(f_better) if f_better != 0 else float('inf')

        results.append({
            'control_param': val,
            'f_approx': f_approx,
            'f_better': f_better,
            'systematic_error': systematic_error,
            'relative_error': relative_error,
        })

    return results
```

### 5c. Estimate systematic error from each approximation

For each approximation, estimate the systematic error it introduces:

```python
# For perturbative approximations: error ~ next order term
# For truncation approximations: error ~ first neglected term
# For discretization approximations: error ~ O(h^p) from convergence test

for approx in active_approximations:
    control_value = approx['current_value']
    error_estimate = approx['error_scaling'](control_value)

    print(f"Approximation: {approx['name']}")
    print(f"  Controlling parameter: {approx['control_param']} = {control_value}")
    print(f"  Estimated systematic error: {error_estimate:.6e}")
    print(f"  Relative to result: {error_estimate / abs(f_nominal):.2e}")

    if error_estimate / abs(f_nominal) > 0.01:
        print(f"  WARNING: Approximation error exceeds 1% -- may dominate uncertainty budget")
```

</step>

<step name="generate_output">
**Step 6: Generate Output**

### 6a. Write SENSITIVITY-REPORT.md

```markdown
---
target: { quantity }
date: { YYYY-MM-DD }
parameters_analyzed: { N }
method: { analytical|numerical|combined }
most_sensitive: { parameter name }
least_sensitive: { parameter name }
divergences_found: { count }
status: completed
---

# Sensitivity Analysis Report

## Target Quantity

**Output:** f = {description}
**Nominal value:** f_0 = {value} +/- {uncertainty}
**Location:** {file:line or phase}

## Parameter Sensitivity Ranking

| Rank | Parameter | Symbol | Nominal | \|S_i\| | delta_f_i | % of Total | Cumulative % |
| ---- | --------- | ------ | ------- | ------- | --------- | ---------- | ------------ |
| 1    | {name}    | {sym}  | {value} | {S}     | {delta_f} | {pct}      | {cumul}      |
| 2    | {name}    | {sym}  | {value} | {S}     | {delta_f} | {pct}      | {cumul}      |

## Sensitivity Details

### {Parameter 1} (Rank 1, \|S\| = {value})

- **Dimensionless sensitivity:** S = {value} (a 1% change in {param} produces a {S}% change in f)
- **Sensitivity at nominal:** {value}
- **Sensitivity at lower bound:** {value}
- **Sensitivity at upper bound:** {value}
- **Linearity:** {linear / mildly nonlinear / strongly nonlinear}
- **Divergence risk:** {none / approaching divergence at p = {value}}

{Repeat for each parameter}

## Parameter Space Structure

### Stiff Directions

- Stiffness ratio: {max |S| / min |S|} = {value}
- Most sensitive: {param} (|S| = {value})
- Least sensitive: {param} (|S| = {value})

### Null Directions

{List parameter combinations that do not affect the result}

### Divergence Warnings

{List any parameters where sensitivity diverges, with physical interpretation}

## Approximation Sensitivity

| Approximation | Control Param | Current Value | Boundary Value | Systematic Error | % of Output |
| ------------- | ------------- | ------------- | -------------- | ---------------- | ----------- |
| {name}        | {param}       | {value}       | {boundary}     | {error}          | {pct}       |

## Uncertainty Budget

| Source                | delta_f | % of Total | Reducible?    | How to Reduce  |
| --------------------- | ------- | ---------- | ------------- | -------------- |
| {param 1} uncertainty | {value} | {pct}      | Yes           | {prescription} |
| {param 2} uncertainty | {value} | {pct}      | Yes           | {prescription} |
| {approx 1} systematic | {value} | {pct}      | {yes/limited} | {prescription} |
| Total (quadrature)    | {value} | 100%       |               |                |

## Recommendations

1. **Highest impact improvement:** Reducing uncertainty in {param} by {factor} would reduce output uncertainty by {amount} ({pct}% improvement).
2. **Diminishing returns:** Further improving {param} has minimal effect (|S| < {threshold}).
3. **Critical warnings:** {Any divergence or instability issues to address.}

## Summary

- Parameters analyzed: {N}
- Dominant parameter: {name} (contributes {pct}% of uncertainty)
- Top 3 parameters account for {pct}% of total uncertainty
- Approximation systematics contribute {pct}% of total uncertainty
- Recommended priority: {ordered list of what to improve}
```

Save to:

- If phase-scoped: `${phase_dir}/SENSITIVITY-REPORT.md`
- If standalone: `.gpd/analysis/sensitivity-{slug}.md`

### 6b. Update state

Update `propagated_uncertainties` via the CLI (which properly syncs STATE.md and state.json):

```bash
gpd uncertainty add \
  --quantity "{target quantity}" --value "{nominal_value}" \
  --uncertainty "{total_uncertainty}" --phase "{phase}" --method "sensitivity-analysis"
```

Run this for the target quantity and for each parameter whose sensitivity-derived uncertainty is significant. For example, if the analysis covers multiple intermediate quantities:

```bash
# Target quantity
gpd uncertainty add \
  --quantity "{symbol}" --value "{f_nominal}" \
  --uncertainty "{delta_f}" --phase "${phase_number}" --method "sensitivity-analysis"

# Dominant parameter contribution (if separately tracked)
gpd uncertainty add \
  --quantity "{symbol}_from_{dominant_param}" --value "{delta_f_dominant}" \
  --uncertainty "{delta_f_dominant}" --phase "${phase_number}" --method "sensitivity-analysis"
```

Record the sensitivity ranking and dominant source in STATE.md as a research artifact.

</step>

<step name="commit_and_present">
**Commit all sensitivity analysis artifacts:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${REPORT_PATH}" .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "data(phase-${phase_number}): sensitivity analysis - ${TARGET_QUANTITY}" \
  --files "${REPORT_PATH}" .gpd/STATE.md
```

Where `${REPORT_PATH}` is `${phase_dir}/SENSITIVITY-REPORT.md` or `.gpd/analysis/sensitivity-{slug}.md` depending on scope.

**Present final results:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > SENSITIVITY ANALYSIS COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**{target quantity}** = {nominal_value} +/- {total_uncertainty}

Parameters analyzed: {N}
Dominant parameter: {name} (contributes {pct}% of uncertainty)
Top 3 parameters account for {cumul_pct}% of total uncertainty

### Key Findings

- {Dominant parameter and its sensitivity coefficient}
- {Divergence warnings if any}
- {Null directions if any}

### Output Files

- `${REPORT_PATH}` -- full sensitivity report
- `.gpd/STATE.md` -- updated with uncertainty estimates

---

## Next Steps

- **Reduce uncertainty:** Improve precision of {dominant parameter} for greatest impact
- **Error propagation:** `/gpd:error-propagation` -- trace full error budget through derivation chain
- **Parameter sweep:** `/gpd:parameter-sweep` -- map out behavior across parameter range
- **Convergence:** `/gpd:numerical-convergence` -- verify numerical error bars at key points

---
```

</step>

</process>

<failure_handling>

- **Divergent sensitivity:** |S_i| exceeds threshold for one or more parameters. This may indicate a critical point, resonance, or ill-conditioned formulation. Flag prominently in the report and recommend non-perturbative treatment or reformulation near the divergence.
- **Missing parameters:** A parameter required for the analysis cannot be found in STATE.md or phase summaries. Prompt the user for its nominal value and uncertainty. Do not guess values.
- **Numerical instability:** Finite-difference derivatives give inconsistent results at different step sizes. Reduce perturbation fraction, switch to analytical derivatives if possible, or flag the parameter as requiring special treatment.
- **All-zero sensitivities:** Every |S_i| is effectively zero. Either the output does not depend on any of the analyzed parameters (check the dependency chain for errors), or the perturbation is too small to register (increase delta_frac). Investigate before reporting.

</failure_handling>

<success_criteria>

- [ ] Project context loaded via `gpd CLI init phase-op`
- [ ] Target quantity identified with nominal value and current uncertainty
- [ ] All relevant input parameters cataloged with nominal values and uncertainties
- [ ] Sensitivity method chosen (analytical, numerical, or combined) and justified
- [ ] Dimensionless sensitivity coefficient S_i computed for each parameter at nominal values
- [ ] Sensitivity evaluated at validity boundary values for each parameter
- [ ] Divergent or anomalously large sensitivities flagged with physical interpretation
- [ ] Parameters ranked by contribution to output uncertainty
- [ ] Stiff directions in parameter space identified (large sensitivity ratio)
- [ ] Null directions identified (parameter combinations with no effect)
- [ ] Active approximations analyzed for systematic error contribution
- [ ] Complete uncertainty budget constructed with dominant source identified
- [ ] SENSITIVITY-REPORT.md generated with ranked parameter table and recommendations
- [ ] propagated_uncertainties updated via `gpd CLI uncertainty add`
- [ ] Artifacts committed via `gpd CLI commit`
- [ ] User presented with key findings and next steps

</success_criteria>

---
name: gpd:error-propagation
description: Track how uncertainties propagate through multi-step calculations across phases
argument-hint: "[--target quantity] [--phase-range start:end]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - find_files
  - search_files
  - task
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Systematic uncertainty propagation through a derivation chain. Traces how input uncertainties flow through intermediate results to final quantities, identifies dominant error sources, and produces error budgets.

**Why a dedicated command:** Physics calculations are chains of transformations. Each intermediate quantity carries uncertainty from its inputs. Without systematic propagation, the final error bars are either absent (bad) or guessed (worse). This command makes the error budget explicit and identifies where to invest effort for maximum precision improvement.

**The principle:** Every final result depends on input parameters with uncertainties. The error budget decomposes the total uncertainty into contributions from each input, ranked by magnitude. If 90% of the uncertainty comes from one parameter, improving the others is wasted effort.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/error-propagation.md
</execution_context>

<context>
Target: $ARGUMENTS

@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>
Execute the error-propagation workflow from @{GPD_INSTALL_DIR}/workflows/error-propagation.md end-to-end.

## 1. Identify the Derivation Chain

Map the dependency graph from inputs to the target quantity:

- **Input parameters** — fundamental constants, experimental measurements, model parameters, each with stated uncertainty
- **Intermediate quantities** — derived values that depend on inputs (e.g., coupling constant from measured cross-section)
- **Target quantity** — the final result whose error budget is needed

For multi-phase projects, trace across phase boundaries using SUMMARY.md `provides` fields.

## 2. Classify Error Sources

| Source Type | Example | Propagation Method |
| --- | --- | --- |
| **Statistical** | Monte Carlo sampling, experimental measurement noise | Standard error propagation, central limit theorem |
| **Systematic** | Approximation truncation, model bias, discretization | Estimate from next-order correction or method comparison |
| **Parametric** | Uncertainty in physical constants (alpha, G_N, m_e) | Partial derivative × parameter uncertainty |
| **Truncation** | Series expansion to finite order, basis set cutoff | Estimate from last included vs first excluded term |
| **Numerical** | Floating-point roundoff, discretization error | Richardson extrapolation, precision comparison |

## 3. Compute Sensitivity Coefficients

For a quantity f(x_1, x_2, ..., x_n), the dimensionless sensitivity coefficient for parameter x_i is:

```
S_i = (x_i / f) × (∂f/∂x_i)
```

This measures the fractional change in f per fractional change in x_i. A sensitivity of S=2 means a 1% change in the input causes a 2% change in the output.

**Analytical method** (when f is known symbolically):

```python
# Symbolic differentiation
import sympy as sp

x, m, g = sp.symbols('x m g', positive=True)
f = g**2 / (16 * sp.pi**2 * m**2)  # Example: loop correction

S_g = sp.simplify(g * sp.diff(f, g) / f)  # = 2
S_m = sp.simplify(m * sp.diff(f, m) / f)  # = -2
```

**Numerical method** (when f is computed by code):

```python
import numpy as np

def compute_f(params):
    """The computation whose error budget is needed."""
    ...
    return value

# Central difference for each parameter
def sensitivity(compute_f, params, i, delta=1e-4):
    p_plus = params.copy()
    p_minus = params.copy()
    p_plus[i] *= (1 + delta)
    p_minus[i] *= (1 - delta)
    f0 = compute_f(params)
    return params[i] * (compute_f(p_plus) - compute_f(p_minus)) / (2 * delta * f0)
```

## 4. Handle Correlated Uncertainties

When inputs are correlated (common in experimental data or when two quantities come from the same measurement):

```
σ²_f = Σ_i Σ_j (∂f/∂x_i)(∂f/∂x_j) × Cov(x_i, x_j)
```

**Common correlation sources in physics:**
- Parameters extracted from the same fit (e.g., slope and intercept)
- Quantities derived from the same dataset
- Systematic errors shared between measurements (calibration, detector efficiency)
- Renormalization group running (parameters at different scales are correlated)

If the correlation matrix is unknown, compute error bounds for the two extreme cases (fully correlated, fully anti-correlated) to bracket the true uncertainty.

## 5. Build the Error Budget

```python
# Error budget table
import numpy as np

param_names = ["g", "m", "Lambda", "alpha_s"]
param_values = [0.3, 1.5, 1000.0, 0.118]
param_uncertainties = [0.01, 0.05, 50.0, 0.001]

sensitivities = [sensitivity(compute_f, param_values, i) for i in range(len(param_values))]

# Fractional contributions (assuming uncorrelated)
fractional_errors = [abs(S) * (du/u) for S, u, du in
                     zip(sensitivities, param_values, param_uncertainties)]
total_error = np.sqrt(sum(e**2 for e in fractional_errors))

for name, S, fe in sorted(zip(param_names, sensitivities, fractional_errors),
                           key=lambda x: -abs(x[2])):
    pct = 100 * fe**2 / total_error**2
    print(f"{name:12s}  S={S:+.3f}  δf/f={fe:.4f}  ({pct:.1f}%)")

print(f"\nTotal fractional error: {total_error:.4f}")
```

## 6. Common Pitfalls

### Non-Gaussian distributions
Linear error propagation assumes Gaussian uncertainties. When uncertainties are large (>10-20%), the output distribution may be skewed. Use Monte Carlo propagation instead:

```python
N_samples = 100000
samples = np.random.normal(param_values, param_uncertainties, size=(N_samples, len(param_values)))
results = np.array([compute_f(s) for s in samples])
mean, std = np.mean(results), np.std(results)
# Also compute percentiles for asymmetric error bars
lo, hi = np.percentile(results, [16, 84])
```

### Cancellations amplify errors
When f = A - B and A ≈ B, the relative error in f is amplified: δf/f ≈ (A/f) × δA/A. This is catastrophic cancellation for error propagation. The cure is reformulating to avoid the subtraction or computing A-B directly.

### Truncation errors are not statistical
Series truncation (perturbative expansion, multipole expansion) gives a systematic error. Estimate it from the magnitude of the last included term or the first excluded term, not by fitting a Gaussian.

### Phase boundary crossings
When propagating across phases, check that conventions match. A factor of 2π between conventions propagates as a systematic bias, not a random error.

## 7. Generate Report

Write ERROR-BUDGET.md:

```markdown
---
target: {quantity}
phases: {phase range}
date: {YYYY-MM-DD}
dominant_source: {parameter name}
total_fractional_error: {value}
---

# Error Budget: {target quantity}

## Derivation Chain

{input} → {intermediate 1} → {intermediate 2} → {target}

## Error Budget Table

| Parameter | Value | Uncertainty | Sensitivity | Contribution | % of Total |
| --- | --- | --- | --- | --- | --- |
| {param} | {val ± err} | {abs} | {S} | {frac_err} | {pct}% |

## Dominant Sources

1. {parameter}: {pct}% of variance — {what would reduce it}
2. {parameter}: {pct}% of variance — {what would reduce it}

## Correlations

{Note any correlated uncertainties and their effect}

## Recommendations

- To reduce total error by 50%: improve {parameter} measurement by {factor}
- Current precision bottleneck: {parameter}
- Systematic errors dominate / statistical errors dominate
```

Save to:
- Phase target: `.gpd/phases/XX-name/ERROR-BUDGET.md`
- Project-wide: `.gpd/analysis/error-budget-{target}.md`

</process>

<success_criteria>

- [ ] Derivation chain mapped from inputs to target
- [ ] All error sources classified (statistical, systematic, parametric, truncation, numerical)
- [ ] Sensitivity coefficients computed for each input parameter
- [ ] Correlated uncertainties handled (or correlation bounds computed)
- [ ] Error budget table with ranked contributions
- [ ] Dominant error source identified with recommendation
- [ ] Monte Carlo cross-check for non-linear propagation (if applicable)
- [ ] Report generated with full budget tables
- [ ] Phase boundary conventions checked for consistency
      </success_criteria>

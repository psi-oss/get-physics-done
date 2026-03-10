---
name: gpd:sensitivity-analysis
description: Systematic sensitivity analysis -- which parameters matter most and how uncertainties propagate
argument-hint: "[--target quantity] [--params p1,p2,...] [--method analytical|numerical]"
context_mode: project-aware
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
Determine which input parameters most strongly affect output quantities. Compute partial derivatives, condition numbers, and rank parameters by sensitivity. Identifies which measurements or calculations would most improve final results.

**Why a dedicated command:** Physics models often have many parameters, but results are typically dominated by a few. Before investing effort in high-precision determination of all parameters, identify which ones actually matter. A parameter with sensitivity coefficient 0.01 can be known to 10% without affecting the result, while one with coefficient 5.0 needs sub-percent precision.

**The principle:** Sensitivity analysis answers "where should I invest my effort?" It maps the parameter space into regions of high and low impact on observables, identifies phase transitions and critical thresholds, and reveals which directions in parameter space are stiff (high sensitivity) vs. sloppy (low sensitivity).
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md
</execution_context>

<context>
Target: $ARGUMENTS

@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>
Run centralized context preflight before executing the workflow:

```bash
CONTEXT=$(gpd --raw validate command-context sensitivity-analysis "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Execute the sensitivity-analysis workflow from @{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md end-to-end.

## 1. Identify Parameters and Observables

Catalog all input parameters and target observables:

- **Parameters** — model parameters (couplings, masses, cutoffs), numerical parameters (grid size, time step), physical constants
- **Observables** — quantities of interest (cross-sections, critical exponents, energy gaps, correlation lengths)
- **Constraints** — parameter ranges with physical meaning (positive masses, g < 1 for perturbative regime, etc.)

## 2. Choose Sensitivity Method

| Method | Best For | Cost | Captures |
| --- | --- | --- | --- |
| **Local (partial derivatives)** | Small perturbations around a working point | N+1 evaluations | Linear response, condition number |
| **Morris method (OAT screening)** | Many parameters, need to screen important ones | 10-50 × (N+1) evaluations | Mean effect + interaction indicator |
| **Sobol indices** | Full nonlinear sensitivity decomposition | 1000+ × (N+2) evaluations | First-order + total-order indices, interactions |
| **Analytical** | When f(params) is known symbolically | Zero (symbolic) | Exact sensitivity at any point |

**Selection guidance:**
- < 5 parameters → Sobol indices (affordable, gives full picture)
- 5-20 parameters → Morris screening first, then Sobol on important ones
- > 20 parameters → Morris screening to reduce to ~5-10, then Sobol
- Symbolic formula available → Analytical always

## 3. Local Sensitivity Analysis

Compute the Jacobian matrix J_ij = ∂f_i/∂x_j at the nominal parameter point:

```python
import numpy as np

def local_sensitivity(compute_f, params, param_names, delta=1e-4):
    """Compute dimensionless sensitivity coefficients via central differences."""
    f0 = compute_f(params)
    sensitivities = {}

    for i, name in enumerate(param_names):
        p_plus = params.copy()
        p_minus = params.copy()
        p_plus[i] *= (1 + delta)
        p_minus[i] *= (1 - delta)

        df = compute_f(p_plus) - compute_f(p_minus)
        # Dimensionless: (x/f) × df/dx
        S = params[i] * df / (2 * delta * params[i] * f0)
        sensitivities[name] = S

    return sensitivities
```

**Condition number** for each parameter: κ_i = |S_i|. A condition number >> 1 means the result is highly sensitive to that parameter (ill-conditioned with respect to it).

## 4. Morris Method (Screening)

For each parameter, compute the elementary effect by varying it by a fixed fraction while holding others fixed, at multiple random starting points:

```python
def morris_screening(compute_f, param_ranges, n_trajectories=20, n_levels=4):
    """Morris method: cheap screening for many parameters."""
    N = len(param_ranges)
    results = {i: [] for i in range(N)}

    for _ in range(n_trajectories):
        # Random starting point on the grid
        x = np.array([np.random.choice(np.linspace(lo, hi, n_levels))
                       for lo, hi in param_ranges])
        f_base = compute_f(x)

        # One-at-a-time perturbation
        for i in range(N):
            x_pert = x.copy()
            delta = (param_ranges[i][1] - param_ranges[i][0]) / (n_levels - 1)
            x_pert[i] += delta
            x_pert[i] = np.clip(x_pert[i], param_ranges[i][0], param_ranges[i][1])
            f_pert = compute_f(x_pert)
            results[i].append((f_pert - f_base) / delta)

    # Summary statistics
    for i in range(N):
        effects = np.array(results[i])
        mu_star = np.mean(np.abs(effects))  # Importance measure
        sigma = np.std(effects)              # Interaction/nonlinearity measure
        # High mu_star = important; High sigma/mu_star = nonlinear or interacting
    return results
```

**Interpretation:**
- High μ* → parameter is important (large average effect)
- High σ/μ* → parameter has nonlinear effects or interacts with other parameters
- Low μ* and low σ → parameter is unimportant, can be fixed at nominal value

## 5. Sobol Indices (Global Sensitivity)

For complete nonlinear decomposition of variance:

- **First-order index S_i** — fraction of variance due to parameter i alone
- **Total-order index S_Ti** — fraction of variance due to parameter i including all interactions
- **Interaction strength** — S_Ti - S_i measures how much parameter i interacts with others

```python
from SALib.sample import saltelli
from SALib.analyze import sobol

problem = {
    'num_vars': len(param_names),
    'names': param_names,
    'bounds': param_ranges
}

# Generate samples (Saltelli scheme)
X = saltelli.sample(problem, N=1024)

# Evaluate model at all sample points
Y = np.array([compute_f(x) for x in X])

# Compute Sobol indices
Si = sobol.analyze(problem, Y, print_to_console=False)
# Si['S1']  — first-order indices
# Si['ST']  — total-order indices
# Si['S2']  — second-order interaction indices
```

## 6. Identify Critical Thresholds

Beyond smooth sensitivity, look for qualitative changes:

- **Phase transitions** — Does the observable change qualitatively (e.g., ordered → disordered) at some parameter value? Map the phase boundary.
- **Divergences** — Does the observable diverge at some parameter value? Identify the critical exponent.
- **Bifurcations** — Does the system have multiple solutions that exchange stability?
- **Regime boundaries** — Where does a perturbative expansion break down? Where does a mean-field approximation fail?

These are more important than smooth sensitivity because they indicate where the physics changes fundamentally.

## 7. Common Pitfalls

### Sensitivity depends on the operating point
Local sensitivity at g=0.1 may be very different from g=0.9. Always state the parameter values at which sensitivity was computed. For global methods (Sobol), state the parameter ranges.

### Dimensionless vs. dimensional sensitivity
Always use dimensionless sensitivity S = (x/f)(∂f/∂x). Dimensional derivatives (∂f/∂x) are misleading because they depend on units. A sensitivity of 10 for a mass in GeV becomes 10⁴ for the same mass in MeV.

### Correlation between parameters
If parameters are constrained (e.g., g₁ and g₂ must satisfy a sum rule), the sensitivity analysis must respect the constraint. Parameterize in terms of independent variables.

### Numerical noise masking true sensitivity
If compute_f has numerical noise (e.g., from Monte Carlo), finite differences give noisy sensitivity estimates. Either increase statistics, use a larger perturbation (at the cost of accuracy), or use adjoint methods.

## 8. Generate Report

Write SENSITIVITY.md:

```markdown
---
target: {observable}
method: {local | morris | sobol}
date: {YYYY-MM-DD}
most_sensitive: {parameter name}
least_sensitive: {parameter name}
---

# Sensitivity Analysis: {target observable}

## Parameters

| Parameter | Nominal Value | Range | Physical Meaning |
| --- | --- | --- | --- |
| {param} | {value} | [{lo}, {hi}] | {meaning} |

## Sensitivity Rankings

| Rank | Parameter | Sensitivity (S) | Condition (κ) | Classification |
| --- | --- | --- | --- | --- |
| 1 | {param} | {S} | {κ} | Stiff |
| 2 | {param} | {S} | {κ} | Stiff |
| ... | {param} | {S} | {κ} | Sloppy |

## Stiff Directions

{Parameters where small changes produce large effects}
- {param}: S = {value}. Physical interpretation: {why it matters}

## Sloppy Directions

{Parameters that can be varied freely without affecting results}
- {param}: S = {value}. Can be fixed at nominal value.

## Critical Thresholds

{Phase transitions, divergences, bifurcations found during analysis}

## Recommendations

- **Prioritize:** Improve precision of {param} — dominates uncertainty budget
- **Deprioritize:** {param} is sloppy, current precision is sufficient
- **Investigate:** {param} shows nonlinear sensitivity — may indicate regime boundary
```

Save to:
- Phase target: `.gpd/phases/XX-name/SENSITIVITY.md`
- Project-wide: `.gpd/analysis/sensitivity-{target}.md`

</process>

<success_criteria>

- [ ] All parameters and observables identified
- [ ] Sensitivity method selected with justification
- [ ] Sensitivity coefficients computed for each parameter
- [ ] Parameters ranked by importance (stiff vs. sloppy)
- [ ] Critical thresholds and regime boundaries identified
- [ ] Interaction effects assessed (for Sobol/Morris)
- [ ] Recommendations given for effort prioritization
- [ ] Report generated with ranked sensitivity table
- [ ] Dimensionless coefficients used throughout
      </success_criteria>

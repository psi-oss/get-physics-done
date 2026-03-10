---
name: gpd:numerical-convergence
description: Systematic convergence testing for numerical physics computations
argument-hint: "[phase number or file path]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Perform systematic convergence tests on numerical computations in a physics project. Identifies all numerical parameters, varies them systematically, determines convergence rates, applies Richardson extrapolation where applicable, and assesses numerical trustworthiness.

**Why a dedicated command:** Numerical physics results are only meaningful if they are converged. A ground-state energy computed on a 10-point grid might differ from the converged value by 50%. Without systematic convergence testing, numerical results are uncontrolled approximations masquerading as answers.

**The principle:** Every numerical result depends on discretization parameters (grid size, time step, basis size, sample count, cutoff). A result is converged when further refinement changes it by less than the stated tolerance. If convergence has not been demonstrated, the result carries no error bars and cannot be trusted.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/numerical-convergence.md
</execution_context>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3"): test convergence for all numerical results in phase 3
- If a file path: test convergence for computations in that file
- If empty: prompt for target
  </context>

<process>

## 1. Identify Numerical Computations

Scan the target for numerical computations:

```bash
# Python numerical code
grep -n "np\.\|scipy\.\|integrate\|solve\|eigenval\|diagonalize\|minimize\|fft\|linspace\|arange" "$TARGET_FILE" 2>/dev/null

# Numerical parameters (grid sizes, tolerances, iterations)
grep -n "N\s*=\|n_points\|n_grid\|n_steps\|dt\s*=\|dx\s*=\|tolerance\|tol\s*=\|max_iter\|n_samples\|cutoff\|L\s*=\|lattice" "$TARGET_FILE" 2>/dev/null

# For-loops that look like parameter sweeps
grep -n "for.*range\|for.*linspace\|for.*arange\|while.*converge\|while.*tol" "$TARGET_FILE" 2>/dev/null
```

For each computation, identify:

- **What is computed** (energy, wavefunction, correlation function, etc.)
- **What numerical parameters control accuracy** (grid size, time step, basis size, etc.)
- **What the expected convergence behavior is** (power law in h, exponential in N, 1/sqrt(N_samples), etc.)

## 2. Classify Numerical Methods

| Method Class           | Typical Parameters              | Expected Convergence                    | Common Pitfalls                               |
| ---------------------- | ------------------------------- | --------------------------------------- | --------------------------------------------- |
| Finite differences     | Grid spacing h, time step dt    | O(h^p) for p-th order scheme            | CFL violation, numerical diffusion            |
| Spectral methods       | Number of basis functions N     | Exponential in N (for smooth functions) | Gibbs phenomenon, aliasing                    |
| Monte Carlo            | Number of samples N_s           | O(1/sqrt(N_s))                          | Autocorrelation, thermalization               |
| Matrix diagonalization | Hilbert space dimension D       | Exact for D = full space                | Memory scaling O(D^2), time O(D^3)            |
| Iterative solvers      | Max iterations, tolerance       | Problem-dependent                       | Stagnation, slow convergence near criticality |
| Quadrature             | Number of quadrature points N   | O(h^{2N}) for Gaussian quadrature       | Singularities, oscillatory integrands         |
| ODE integration        | Time step dt, order             | O(dt^p) for p-th order method           | Stiffness, energy drift                       |
| Basis set expansion    | Cutoff energy, number of states | Method-dependent                        | Basis set superposition error                 |
| Lattice calculations   | Lattice spacing a, volume L^d   | O(a^p) for p-th order discretization    | Finite-size effects, critical slowing down    |

## 3. Design Convergence Tests

For each numerical parameter identified:

### 3a. Parameter sweep

Choose a geometric sequence of parameter values (doubles or triples):

```python
# Template convergence test
import numpy as np

def compute_observable(N):
    """The computation being tested."""
    ...
    return value

# Geometric sequence of refinement levels
N_values = [50, 100, 200, 400, 800, 1600]  # Or appropriate for the method

results = []
for N in N_values:
    value = compute_observable(N)
    results.append((N, value))
    print(f"N={N:6d}  result={value:.12e}")
```

### 3b. Convergence rate estimation

```python
# Estimate convergence order from successive refinements
for i in range(2, len(results)):
    N1, v1 = results[i-2]
    N2, v2 = results[i-1]
    N3, v3 = results[i]

    # For O(h^p) convergence with uniform refinement ratio r = N2/N1:
    if abs(v2 - v1) > 0 and abs(v3 - v2) > 0:
        ratio = abs(v3 - v2) / abs(v2 - v1)
        r = N2 / N1  # refinement ratio
        p = -np.log(ratio) / np.log(r)
        print(f"N={N3:6d}  conv_order={p:.2f}")
```

### 3c. Richardson extrapolation

```python
# For O(h^p) convergence, extrapolate to h -> 0
# Using two finest results:
N_fine, v_fine = results[-1]
N_coarse, v_coarse = results[-2]
r = N_fine / N_coarse  # refinement ratio

# If convergence order p is known:
v_extrapolated = (r**p * v_fine - v_coarse) / (r**p - 1)
error_estimate = abs(v_extrapolated - v_fine)
print(f"Extrapolated: {v_extrapolated:.12e}")
print(f"Error estimate: {error_estimate:.2e}")
```

### 3d. Stability checks

```python
# Check for numerical instabilities:
# 1. Sign oscillations (suggests instability, not convergence)
# 2. Non-monotonic convergence (suggests aliasing or cancellation)
# 3. Sudden jumps (suggests precision loss or phase transition in algorithm)

diffs = [results[i][1] - results[i-1][1] for i in range(1, len(results))]
sign_changes = sum(1 for i in range(1, len(diffs)) if diffs[i] * diffs[i-1] < 0)
monotonic = sign_changes == 0

print(f"Monotonic convergence: {monotonic}")
print(f"Sign changes: {sign_changes}")
```

## 4. Assess Convergence Quality

| Grade                | Criteria                                                 | Interpretation                            |
| -------------------- | -------------------------------------------------------- | ----------------------------------------- |
| A: Converged         | Relative change < tolerance for last 2+ refinements      | Result is trustworthy to stated precision |
| B: Nearly converged  | Clear trend, last change < 10x tolerance                 | One more refinement would suffice         |
| C: Converging        | Consistent convergence rate but not yet within tolerance | More refinement needed                    |
| D: Slowly converging | Convergence rate is low (p < 1 or 1/sqrt(N))             | May need different method                 |
| F: Not converging    | Oscillating, diverging, or no clear trend                | Method is failing                         |
| X: Cannot assess     | Too few data points or computation too expensive         | Need at least 3 refinement levels         |

## 5. Special Convergence Considerations

### 5a. Critical phenomena and phase transitions

Near phase transitions, convergence is anomalously slow:

- Correlation length diverges -> finite-size effects dominate
- Critical slowing down in Monte Carlo
- Scaling corrections complicate extrapolation
- **Prescription:** Use finite-size scaling analysis, not naive convergence

### 5b. Stiff ODEs

Stiff systems require implicit integrators:

- Explicit methods need dt << 1/lambda_max (stability constraint)
- Test: compare explicit and implicit results
- **Prescription:** If explicit requires dt < 1e-6 for stability, switch to implicit

### 5c. Monte Carlo thermalization

Samples must be decorrelated:

- Compute autocorrelation time tau
- Effective samples = N_samples / (2 \* tau)
- Error bars scale as 1/sqrt(effective samples)
- **Prescription:** Discard first 10\*tau samples, check that observables have plateaued

### 5d. Catastrophic cancellation

When the result is a small difference of large numbers:

- Relative error amplifies: delta(A-B)/(A-B) >> delta(A)/A
- Test: compute in higher precision (float128 vs float64)
- **Prescription:** Reformulate to avoid cancellation, or use arbitrary precision

### 5e. Spectral pollution

Spurious eigenvalues from basis truncation:

- Appear in the spectrum but are not physical
- Test: compare spectra at different truncation levels
- **Prescription:** Track individual eigenvalues through refinement, flag those that don't converge

## 6. Execute Convergence Tests

For each identified numerical parameter:

1. Run the computation at multiple refinement levels
2. Compute convergence rate
3. Apply Richardson extrapolation where applicable
4. Assess convergence grade
5. Estimate error bars

If the computation is too expensive to run at multiple levels, design a targeted test:

- Fix all other parameters at coarsest acceptable values
- Vary the parameter under test
- At minimum, use 3 refinement levels (this is the absolute minimum for estimating convergence rate)

## 7. Generate Report

Write CONVERGENCE.md:

```markdown
---
target: { phase or file }
date: { YYYY-MM-DD }
computations_tested: { N }
parameters_varied: { M }
overall_status: converged | partially_converged | not_converged
---

# Convergence Report

## Computations Tested

| #   | Observable         | Method             | File        | Status  |
| --- | ------------------ | ------------------ | ----------- | ------- |
| 1   | {what is computed} | {numerical method} | {file:line} | {grade} |

## Convergence Results

### {Observable 1}: {Grade}

**Method:** {numerical method}
**Parameter:** {what was varied}
**Expected convergence:** {O(h^p) or O(1/sqrt(N)) etc.}

| N    | Result  | Change  | Relative Change | Conv. Order |
| ---- | ------- | ------- | --------------- | ----------- |
| {N1} | {value} | --      | --              | --          |
| {N2} | {value} | {delta} | {rel}           | {p}         |
| {N3} | {value} | {delta} | {rel}           | {p}         |

**Extrapolated value:** {Richardson extrapolation}
**Error estimate:** {from extrapolation}
**Assessed convergence order:** {p}
**Grade:** {A/B/C/D/F/X}

{Repeat for each observable}

## Stability Analysis

| Observable | Monotonic | Oscillating | Precision Issues | Stiffness |
| ---------- | --------- | ----------- | ---------------- | --------- |
| {obs}      | {yes/no}  | {yes/no}    | {yes/no}         | {yes/no}  |

## Error Budget

| Observable | Statistical Error | Discretization Error | Truncation Error | Total   |
| ---------- | ----------------- | -------------------- | ---------------- | ------- |
| {obs}      | {value}           | {value}              | {value}          | {value} |

## Recommendations

{For each non-converged or barely-converged result:}

- **{Observable}:** {What to do -- increase N, use different method, reformulate}

## Summary

- Computations tested: {N}
- Grade A (converged): {count}
- Grade B (nearly): {count}
- Grade C (converging): {count}
- Grade D (slow): {count}
- Grade F (failing): {count}
- Overall assessment: {trustworthiness of numerical results}
```

Save to:

- Phase target: `.gpd/phases/XX-name/CONVERGENCE.md`
- File target: `.gpd/analysis/convergence-{slug}.md`

**For comprehensive verification** (dimensional analysis + limiting cases + symmetries + convergence), use `/gpd:verify-work`.

</process>

<success_criteria>

- [ ] All numerical computations in target identified
- [ ] Numerical parameters cataloged for each computation
- [ ] Expected convergence behavior stated for each method
- [ ] Convergence tests designed with geometric refinement sequences
- [ ] Tests executed (or test scripts generated if too expensive to run)
- [ ] Convergence rates estimated from data
- [ ] Richardson extrapolation applied where appropriate
- [ ] Convergence grades assigned (A through F)
- [ ] Error estimates provided
- [ ] Special issues identified (stiffness, cancellation, critical slowing)
- [ ] Report generated with full data tables
- [ ] Recommendations given for non-converged results
      </success_criteria>

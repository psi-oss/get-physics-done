<purpose>
Perform comprehensive numerical validation of computational physics results. Combines convergence testing, analytical benchmarking, conservation law verification, stability analysis, and error estimation into a single systematic workflow.

Called from /gpd:numerical-convergence command and referenced by /gpd:verify-work for numerical phases.
</purpose>

<core_principle>
A numerical result without demonstrated convergence and error bars is not a result -- it is a number. Numerical validation establishes that the number means something physical by proving it is independent of numerical artifacts (grid size, time step, basis truncation, Monte Carlo statistics) to within stated precision.

**The validation hierarchy:**

1. Does the code run without errors? (Necessary but trivially insufficient)
2. Does it reproduce known analytical results? (Benchmark validation)
3. Does it conserve what should be conserved? (Conservation law check)
4. Does it converge as discretization is refined? (Convergence test)
5. Is it stable under perturbation? (Stability analysis)
6. Are the error bars honest? (Error estimation)
   </core_principle>

<process>

<step name="load_context" priority="first">
**Load Project Context**

Load project state and conventions before beginning validation:

- Run:

```bash
INIT=$(gpd init phase-op --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

- **If init succeeds** (non-empty JSON with `state_exists: true`): Extract `convention_lock` for unit system (needed to verify dimensional consistency of benchmarks). Extract active approximations and their validity ranges (informs which convergence tests are most critical). Extract `intermediate_results` for previously computed quantities to validate.
- **If init fails or `state_exists` is false** (standalone usage): Proceed with explicit specification of the computation to validate. The user must provide the unit system and computation details directly.

Convention context is important for numerical validation: unit system determines what "reasonable" values are, and approximation validity ranges determine the expected convergence behavior.

**Convention verification** (if project exists):

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — review before validating convergence"
  echo "$CONV_CHECK"
fi
```
</step>

<step name="identify_computations">
Catalog all numerical computations in the target:

For each computation, determine:

| Property                  | What to record                                         |
| ------------------------- | ------------------------------------------------------ |
| Observable                | Physical quantity being computed                       |
| Method                    | Algorithm / numerical scheme                           |
| Discretization parameters | Grid size, time step, basis size, cutoff, sample count |
| Expected convergence      | O(h^p), O(1/sqrt(N)), exponential, etc.                |
| Known benchmarks          | Analytical results for special cases                   |
| Conservation laws         | Energy, momentum, charge, probability, etc.            |
| Computational cost        | Time and memory scaling with parameters                |

Classify each computation:

| Type                | Examples                              | Key validation                               |
| ------------------- | ------------------------------------- | -------------------------------------------- |
| ODE integration     | Time evolution, trajectories          | Energy conservation, symplecticity           |
| PDE solving         | Diffusion, wave, Schrodinger          | CFL condition, stability, conservation       |
| Eigenvalue problems | Spectrum, ground state                | Convergence with basis size, known limits    |
| Monte Carlo         | Statistical mechanics, path integrals | Thermalization, autocorrelation, variance    |
| Optimization        | Variational, fitting                  | Local vs global minimum, sensitivity         |
| Quadrature          | Integrals, Fourier transforms         | Convergence with quadrature points, aliasing |
| Linear algebra      | Matrix operations, decompositions     | Condition number, residual                   |

</step>

<step name="benchmark_validation">
**Phase 1: Reproduce Known Results**

Before testing convergence of new results, verify the code reproduces known analytical solutions.

For each benchmark:

1. **Identify the benchmark:**

   - Exactly solvable special case (harmonic oscillator, free particle, Ising 2D, hydrogen atom)
   - Published numerical result with high precision
   - Analytical limit (weak coupling, high temperature, large N)

2. **Run the computation** at high resolution for the benchmark case.

3. **Compare quantitatively:**

   ```python
   # Template benchmark test
   computed_value = run_computation(benchmark_params)
   known_value = analytical_result(benchmark_params)

   abs_error = abs(computed_value - known_value)
   rel_error = abs_error / abs(known_value) if known_value != 0 else abs_error

   print(f"Computed:  {computed_value:.12e}")
   print(f"Known:     {known_value:.12e}")
   print(f"Abs error: {abs_error:.2e}")
   print(f"Rel error: {rel_error:.2e}")

   # Assessment:
   # rel_error < machine_epsilon * condition_number: PASSED
   # rel_error < tolerance: PASSED (with stated precision)
   # rel_error > tolerance: FAILED (investigate)
   ```

4. **Record result:**

   | Benchmark | Known Value | Computed | Rel. Error | Status    |
   | --------- | ----------- | -------- | ---------- | --------- |
   | {name}    | {value}     | {value}  | {error}    | PASS/FAIL |

**If ANY benchmark fails:** Stop. Debug before proceeding. Wrong results at high resolution cannot be fixed by convergence testing.
</step>

<step name="conservation_check">
**Phase 2: Conservation Law Verification**

Every physical system has conserved quantities. Verify they are conserved numerically.

| System Type           | Conservation Laws to Check                               |
| --------------------- | -------------------------------------------------------- |
| Hamiltonian mechanics | Energy (H), phase space volume (Liouville)               |
| Quantum mechanics     | Probability (norm), energy (for time-independent H)      |
| Electrodynamics       | Charge (continuity equation), energy-momentum (Poynting) |
| Fluid dynamics        | Mass, momentum, energy, entropy (production only)        |
| Many-body quantum     | Particle number, total spin, crystal momentum            |
| Relativistic          | 4-momentum, angular momentum                             |
| Gauge theories        | Gauge invariance (Ward identities), BRST charge          |

For each conservation law:

```python
# Template conservation check
def check_conservation(trajectory, conserved_quantity_fn, times):
    """Check that a conserved quantity stays constant."""
    Q_values = [conserved_quantity_fn(trajectory[t]) for t in times]
    Q_initial = Q_values[0]

    drift = [abs(Q - Q_initial) / abs(Q_initial) for Q in Q_values]
    max_drift = max(drift)
    avg_drift = np.mean(drift)

    print(f"Conservation of {conserved_quantity_fn.__name__}:")
    print(f"  Initial value: {Q_initial:.12e}")
    print(f"  Max drift:     {max_drift:.2e}")
    print(f"  Avg drift:     {avg_drift:.2e}")

    # Assessment:
    # Symplectic integrator: drift bounded, no secular growth
    # Non-symplectic: linear drift acceptable if small enough
    # Any method: exponential drift = UNSTABLE
    return max_drift
```

Record:

| Conserved Quantity | Initial Value | Max Drift | Growth Type                    | Status       |
| ------------------ | ------------- | --------- | ------------------------------ | ------------ |
| Energy             | {value}       | {drift}   | bounded / linear / exponential | OK/WARN/FAIL |

</step>

<step name="convergence_testing">
**Phase 3: Systematic Convergence Tests**

For each numerical parameter, vary it systematically and measure convergence.

### Design the convergence study

For parameter h (grid spacing, time step, etc.), use a geometric sequence:

- h, h/2, h/4, h/8, h/16 (factor-of-2 refinement, 5 levels)
- Or h, h/3, h/9, h/27 (factor-of-3, for higher-order methods)

Minimum: 3 levels (absolute minimum for estimating convergence order)
Recommended: 5 levels (robust estimation with error on the error)

### Run the convergence study

```python
import numpy as np

def convergence_study(compute_fn, param_name, param_values, reference_value=None):
    """Systematic convergence test."""
    results = []
    for p in param_values:
        value = compute_fn(**{param_name: p})
        results.append({'param': p, 'value': value})

    # Compute successive differences
    for i in range(1, len(results)):
        delta = results[i]['value'] - results[i-1]['value']
        results[i]['delta'] = delta

    # Estimate convergence order from Richardson ratios
    for i in range(2, len(results)):
        r = results[i-1]['param'] / results[i]['param']  # refinement ratio
        if abs(results[i]['delta']) > 0 and abs(results[i-1]['delta']) > 0:
            ratio = abs(results[i]['delta']) / abs(results[i-1]['delta'])
            p_est = np.log(ratio) / np.log(1/r)
            results[i]['conv_order'] = p_est

    # Richardson extrapolation (using last two values)
    if len(results) >= 2 and 'conv_order' in results[-1]:
        p = results[-1]['conv_order']
        r = results[-2]['param'] / results[-1]['param']
        extrapolated = (r**p * results[-1]['value'] - results[-2]['value']) / (r**p - 1)
        error_estimate = abs(extrapolated - results[-1]['value'])
    else:
        extrapolated = results[-1]['value']
        error_estimate = abs(results[-1]['value'] - results[-2]['value']) if len(results) >= 2 else None

    return results, extrapolated, error_estimate
```

### Assess convergence quality

| Grade                | Criteria                                                                 |
| -------------------- | ------------------------------------------------------------------------ |
| A: Converged         | Last 2+ refinements change result by < tolerance; order matches expected |
| B: Nearly converged  | Clear monotonic trend, last change < 10x tolerance                       |
| C: Converging        | Consistent positive convergence order but not yet within tolerance       |
| D: Slowly converging | Order < 1 or fluctuating; method may be inappropriate                    |
| F: Not converging    | Non-monotonic, oscillating, or diverging                                 |

### Multi-parameter convergence

When multiple parameters exist (grid spacing AND time step AND basis size), test each independently while holding others at their finest values. Then verify that the combined refinement gives consistent results.

**Cross-convergence check:** The result should be independent of the ORDER in which parameters are refined. If refining h first gives a different limit than refining dt first, there is a coupling between discretization errors that must be understood.

### Convergence Pitfall Detection

Standard convergence testing can miss these failure modes. Check for each explicitly.

**Oscillatory integrals:** Standard quadrature (Gauss, Simpson) fails for integrals of the form integral f(x) exp(i*omega*x) dx when omega is large. The error estimate may oscillate rather than decrease monotonically.
- Detection: error estimate oscillates or fails to decrease with refinement
- Fix: Use Filon's method, Levin's method, or stationary phase approximation. For Fourier transforms, use FFT with appropriate windowing.

**Stiff ODEs:** Explicit integrators (RK4, Euler) require absurdly small time steps for stiff systems (those with widely separated timescales). The solution may appear to converge but to the wrong answer.
- Detection: compare implicit (BDF, RADAU) vs explicit (RK4, RK45) methods. If they give different results at the same dt, the system is stiff and the explicit method is wrong.
- Fix: Use implicit methods (scipy.integrate.solve_ivp with method='Radau' or 'BDF'). Monitor the stiffness ratio (largest/smallest eigenvalue of Jacobian).

**Critical slowing down:** Near phase transitions in Monte Carlo simulations, the autocorrelation time diverges as tau ~ L^z with z ~ 2 for local algorithms. Standard convergence tests on individual configurations may appear fine while ensemble averages are severely undersampled.
- Detection: autocorrelation time grows with system size. If tau_int > N_samples/100, the simulation is too short.
- Fix: Use cluster algorithms (Swendsen-Wang, Wolff) near criticality, which have z ~ 0.2-0.5. Or use parallel tempering / multicanonical methods.

**Catastrophic cancellation:** When computing small differences of large numbers (e.g., E_binding = E_total - E_parts), the relative error of the difference can be much larger than the relative error of the individual terms.
- Detection: relative error of difference >> relative error of summands. Compute condition number: |a + b| / |a - b|. If >> 1, catastrophic cancellation is occurring.
- Fix: Reformulate the problem to avoid the subtraction (e.g., compute binding energy directly). Use higher precision arithmetic (mpmath, float128). Use compensated summation (Kahan algorithm).

**Adaptive mesh artifacts:** When using adaptive mesh refinement (AMR) or adaptive quadrature, standard convergence tests (compare N and 2N points) are inapplicable because the mesh is different at each resolution level.
- Detection: compare adaptive result with uniform mesh at the finest adaptive resolution. If they disagree significantly, the adaptive algorithm may be misallocating resolution.
- Fix: Verify that error indicators drive refinement correctly. Check that the solution is smooth on the final adaptive mesh (no under-resolved features at refinement boundaries). Run at multiple overall tolerance levels and verify convergence of the final result.

</step>

<step name="stability_analysis">
**Phase 4: Stability Analysis**

### Perturbation stability

Does the result change significantly under small perturbations?

```python
# Vary initial conditions slightly
for epsilon in [1e-2, 1e-4, 1e-6, 1e-8]:
    result_perturbed = compute(initial_conditions + epsilon * random_perturbation)
    sensitivity = abs(result_perturbed - result_unperturbed) / epsilon
    print(f"eps={epsilon:.0e}  sensitivity={sensitivity:.6e}")

# If sensitivity grows with decreasing epsilon: ill-conditioned
# If sensitivity is constant: well-conditioned (Lyapunov stable)
# If sensitivity is very large: chaotic regime (need ensemble statistics)
```

### Floating-point precision stability

```python
# Compare different precisions
result_f32 = compute(dtype=np.float32)
result_f64 = compute(dtype=np.float64)
# result_f128 = compute(dtype=np.float128)  # if available

rel_diff_32_64 = abs(result_f32 - result_f64) / abs(result_f64)
print(f"float32 vs float64: relative diff = {rel_diff_32_64:.2e}")

# If rel_diff > sqrt(machine_epsilon_f32): catastrophic cancellation suspected
# If rel_diff ~ machine_epsilon_f32: well-conditioned
```

### Algorithm stability

For time-stepping algorithms:

- Check CFL condition: dt < C \* dx (for explicit methods)
- Check that energy is bounded (no exponential growth)
- Check that solutions remain physical (positive densities, subluminal velocities)

For iterative algorithms:

- Check that residual decreases monotonically
- Check that convergence rate matches theoretical expectation
- Flag if iteration count exceeds expected bound
  </step>

<step name="error_estimation">
**Phase 5: Error Budget**

Construct a complete error budget for each computed quantity:

| Error Source   | Magnitude | How Estimated                       | Reducible?                     |
| -------------- | --------- | ----------------------------------- | ------------------------------ |
| Discretization | {value}   | Richardson extrapolation            | Yes (refine grid)              |
| Truncation     | {value}   | Vary cutoff/basis size              | Yes (increase cutoff)          |
| Statistical    | {value}   | Bootstrap / jackknife               | Yes (more samples)             |
| Floating-point | {value}   | Precision comparison                | Limited (use higher precision) |
| Approximation  | {value}   | Comparison with next order          | Depends on method              |
| Model          | {value}   | Comparison with more complete model | Research question              |

**Total error:** Combine in quadrature (if independent) or use maximum (if correlated):

```python
total_error_quadrature = np.sqrt(sum(e**2 for e in errors))  # independent
total_error_conservative = sum(abs(e) for e in errors)  # worst case
```

**Dominant error:** Identify which source dominates and whether further refinement is worthwhile.
</step>

<step name="generate_report">
Write NUMERICAL-VALIDATION.md:

```markdown
---
target: {phase or file}
date: {YYYY-MM-DD}
computations_validated: {N}
benchmarks_passed: {M}/{total}
conservation_laws_checked: {K}
convergence_grade: {overall grade}
overall_status: validated | partially_validated | not_validated
---

# Numerical Validation Report

## Benchmark Validation

| #   | Benchmark   | Known Value | Computed | Rel. Error | Status |
| --- | ----------- | ----------- | -------- | ---------- | ------ |
| 1   | {benchmark} | {value}     | {value}  | {error}    | PASS   |

## Conservation Law Verification

| #   | Quantity   | Initial | Max Drift | Growth | Status |
| --- | ---------- | ------- | --------- | ------ | ------ |
| 1   | {quantity} | {value} | {drift}   | {type} | OK     |

## Convergence Tests

### {Observable 1}

| Parameter | Value | Result   | Delta | Conv. Order |
| --------- | ----- | -------- | ----- | ----------- |
| {param}   | {val} | {result} | --    | --          |

**Extrapolated:** {value} +/- {error}
**Convergence order:** {measured} (expected: {theoretical})
**Grade:** {A-F}

## Stability Analysis

| Test                     | Result  | Condition              | Status  |
| ------------------------ | ------- | ---------------------- | ------- |
| Perturbation sensitivity | {value} | {well/ill-conditioned} | OK/WARN |
| Precision sensitivity    | {value} | {cancellation status}  | OK/WARN |
| CFL condition            | {ratio} | {satisfied/violated}   | OK/FAIL |

## Error Budget

| Observable | Discretization | Truncation | Statistical | Total   |
| ---------- | -------------- | ---------- | ----------- | ------- |
| {obs}      | {error}        | {error}    | {error}     | {total} |

## Summary

**Overall assessment:** {narrative summary}
**Dominant error source:** {what limits accuracy}
**Recommendation:** {what to improve if more precision needed}
```

Ensure output directory exists:

```bash
mkdir -p .gpd/analysis
```

Save to:

- Phase target: `${phase_dir}/NUMERICAL-VALIDATION.md`
- File target: `.gpd/analysis/numerical-{slug}.md`

**Commit the report:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${OUTPUT_PATH}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: numerical convergence validation — ${phase_slug:-standalone}" \
  --files "${OUTPUT_PATH}"
```

Where `${OUTPUT_PATH}` is the path where the report was written.

</step>

</process>

<success_criteria>

- [ ] Project context loaded (unit system, active approximations, intermediate results)
- [ ] All numerical computations identified and classified
- [ ] Benchmarks tested against known analytical results
- [ ] Conservation laws verified with drift quantified
- [ ] Convergence tested with geometric refinement sequences
- [ ] Convergence orders estimated and compared with theory
- [ ] Richardson extrapolation applied where appropriate
- [ ] Stability tested (perturbation, precision, algorithm)
- [ ] Complete error budget constructed
- [ ] Dominant error source identified
- [ ] Report generated with full data tables
- [ ] Overall validation status determined

</success_criteria>

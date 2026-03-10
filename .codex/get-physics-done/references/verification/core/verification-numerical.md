---
load_when:
  - "numerical convergence"
  - "statistical validation"
  - "Monte Carlo error"
  - "numerical stability"
  - "cross-check literature"
  - "automated verification"
tier: 2
context_cost: large
---

# Verification Numerical — Convergence, Statistics, and Numerical Stability

Convergence testing, statistical validation, cross-checks with literature, and automated verification framework. Everything needed to validate computational physics results.

**Load when:** Working with numerical calculations, simulations, Monte Carlo, or any computational physics.

**Related files:**
- `references/verification/core/verification-quick-reference.md` — compact checklist (default entry point)
- `references/verification/core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../domains/verification-domain-qft.md` — QFT, particle, GR, mathematical physics
- `../domains/verification-domain-condmat.md` — condensed matter, quantum information, AMO
- `../domains/verification-domain-statmech.md` — statistical mechanics, cosmology, fluids

---

<numerical_convergence>

## Numerical Convergence Verification

Numerical results must converge as resolution increases. If they don't, the result cannot be trusted.

**Principle:** A numerical result is only meaningful if it is stable under refinement of the numerical parameters (grid spacing, basis size, time step, sample count, etc.).

**Convergence hierarchy:**

```
1. Does it run?           -> Code executes without errors
2. Does it finish?        -> Converges to a fixed point / completes iteration
3. Does it converge?      -> Result stable as resolution increases
4. Does it converge fast? -> Rate matches theoretical expectation
5. Is it accurate?        -> Agrees with known analytical result (if available)
```

Levels 1-2 are necessary but NOT sufficient. Level 3 is the minimum for a trustworthy result.

**Standard convergence tests:**

### Grid/mesh refinement

```python
def verify_grid_convergence(compute_fn, grid_sizes, expected_order=2):
    """
    Check that results converge as grid is refined.

    Args:
        compute_fn: Function(N) -> result for grid size N
        grid_sizes: List of increasing grid sizes, e.g., [32, 64, 128, 256]
        expected_order: Expected convergence order (2 for second-order method)
    """
    results = [compute_fn(N) for N in grid_sizes]
    errors = [abs(results[i] - results[-1]) for i in range(len(results) - 1)]

    # Check convergence rate
    for i in range(len(errors) - 1):
        ratio = grid_sizes[i] / grid_sizes[i + 1]
        error_ratio = errors[i] / errors[i + 1] if errors[i + 1] > 0 else float('inf')
        observed_order = np.log(error_ratio) / np.log(1 / ratio)
        assert abs(observed_order - expected_order) < 0.5, (
            f"Convergence order {observed_order:.1f} != expected {expected_order}"
        )
```

### Basis set convergence (quantum mechanics)

```python
def verify_basis_convergence(compute_fn, basis_sizes, tolerance=1e-6):
    """
    Check convergence of eigenvalue as basis size increases.

    Typical: plane waves, harmonic oscillator basis, Gaussian basis sets.
    """
    results = [compute_fn(N) for N in basis_sizes]
    # Eigenvalues must decrease monotonically (variational principle)
    for i in range(len(results) - 1):
        assert results[i + 1] <= results[i] + tolerance, (
            f"Variational principle violated: E({basis_sizes[i+1]}) > E({basis_sizes[i]})"
        )
    # Check convergence
    final_deltas = [abs(results[i] - results[-1]) for i in range(len(results) - 1)]
    assert final_deltas[-2] < tolerance, (
        f"Not converged: delta = {final_deltas[-2]:.2e} > tolerance {tolerance:.2e}"
    )
```

### Time step convergence

```python
def verify_timestep_convergence(compute_fn, dt_values, expected_order=2):
    """
    Check that time integration converges as dt decreases.
    """
    results = [compute_fn(dt) for dt in dt_values]
    # Richardson extrapolation for error estimation
    for i in range(len(results) - 2):
        ratio = dt_values[i] / dt_values[i + 1]
        e1 = abs(results[i] - results[i + 1])
        e2 = abs(results[i + 1] - results[i + 2])
        if e2 > 0:
            observed_order = np.log(e1 / e2) / np.log(ratio)
            assert abs(observed_order - expected_order) < 0.5
```

### Monte Carlo convergence

```python
def verify_mc_convergence(compute_fn, sample_counts):
    """
    Check that Monte Carlo estimator converges as 1/sqrt(N).
    """
    results = [(compute_fn(N), N) for N in sample_counts]
    # Statistical error should decrease as 1/sqrt(N)
    errors = []
    for (mean, std), N in results:
        errors.append(std / np.sqrt(N))
    # Errors should be roughly constant (since we normalized by 1/sqrt(N))
    relative_variation = np.std(errors) / np.mean(errors)
    assert relative_variation < 0.5, (
        f"MC convergence anomalous: relative variation = {relative_variation:.2f}"
    )
```

**Convergence display format:**

```
Grid convergence test:
  N=32:   E = -7.234891      (ref)
  N=64:   E = -7.278234      delta = 4.3e-2
  N=128:  E = -7.289012      delta = 1.1e-2   order = 2.0
  N=256:  E = -7.291723      delta = 2.7e-3   order = 2.0
  N=512:  E = -7.292401      delta = 6.8e-4   order = 2.0  PASS
```

**When to apply:**

- Every numerical result that will be reported or used downstream
- When changing numerical methods or parameters
- When results disagree with expectations
- Before any quantitative claim in a paper

</numerical_convergence>

<cross_check_literature>

## Cross-Check with Known Results

Compare your results against published values, analytical solutions, and independent calculations.

**Principle:** Physics results exist in a web of interconnected knowledge. A new result should be consistent with established results in overlapping regimes.

**Cross-check hierarchy:**

| Priority | Check Against                             | Confidence if Agrees              |
| -------- | ----------------------------------------- | --------------------------------- |
| 1        | Exact analytical solution (if known)      | Very high                         |
| 2        | Published numerical benchmark             | High                              |
| 3        | Independent code/method (same problem)    | High                              |
| 4        | Textbook limiting case                    | Medium-high                       |
| 5        | Order-of-magnitude estimate               | Medium                            |
| 6        | Physical intuition / qualitative behavior | Low (but violation is a red flag) |

**Protocol for cross-checking:**

```python
def cross_check_with_literature(our_result, literature_value, literature_uncertainty,
                                 our_uncertainty=None, source=""):
    """
    Compare result with published value.
    """
    discrepancy = abs(our_result - literature_value)
    combined_sigma = np.sqrt(literature_uncertainty**2 + (our_uncertainty or 0)**2)

    if combined_sigma > 0:
        tension = discrepancy / combined_sigma
        status = "PASS" if tension < 3 else ("WARN" if tension < 5 else "FAIL")
        print(f"{status} vs {source}: {tension:.1f}sigma "
              f"(ours: {our_result}, lit: {literature_value} +/- {literature_uncertainty})")
    else:
        relative_diff = discrepancy / abs(literature_value) if literature_value != 0 else float('inf')
        status = "PASS" if relative_diff < 0.01 else ("WARN" if relative_diff < 0.1 else "FAIL")
        print(f"{status} vs {source}: {relative_diff:.1e} relative difference")
```

**Standard references by domain:**

| Domain                | Key References                                |
| --------------------- | --------------------------------------------- |
| Particle physics      | PDG (Particle Data Group) Review              |
| Atomic physics        | NIST Atomic Spectra Database                  |
| Condensed matter      | Materials Project, AFLOW databases            |
| Quantum chemistry     | NIST CCCBDB, ATcT thermochemistry             |
| Cosmology             | Planck collaboration results                  |
| Nuclear physics       | NNDC (National Nuclear Data Center)           |
| Statistical mechanics | Exactly solved models (Onsager, Bethe ansatz) |

**When to apply:**

- Before reporting any numerical value
- When a result will be compared with experiment
- When extending a known calculation to new parameter regimes
- When using a new method on a known problem (method validation)

</cross_check_literature>

<statistical_validation>

## Statistical Validation

For results involving stochastic sampling, Monte Carlo, or comparison with experimental data, statistical rigor is essential.

**Principle:** A numerical result without a proper error bar is not a result. Statistical validation ensures that quoted uncertainties are honest and that conclusions are warranted by the data.

### Error estimation methods

**Bootstrap resampling:**

```python
def bootstrap_error(data, statistic_fn, n_bootstrap=10000):
    """
    Estimate error of a statistic using bootstrap resampling.

    Returns:
        (estimate, std_error, confidence_interval)
    """
    n = len(data)
    bootstrap_stats = np.array([
        statistic_fn(np.random.choice(data, size=n, replace=True))
        for _ in range(n_bootstrap)
    ])
    estimate = statistic_fn(data)
    std_error = np.std(bootstrap_stats)
    ci_low = np.percentile(bootstrap_stats, 2.5)
    ci_high = np.percentile(bootstrap_stats, 97.5)
    return estimate, std_error, (ci_low, ci_high)
```

**When:** Non-linear functions of data, derived quantities, ratios, correlation functions.

**Jackknife resampling:**

```python
def jackknife_error(data, statistic_fn):
    """
    Estimate error using jackknife (leave-one-out) resampling.
    Better for correlated data than naive standard error.
    """
    n = len(data)
    full_stat = statistic_fn(data)
    jackknife_stats = np.array([
        statistic_fn(np.delete(data, i))
        for i in range(n)
    ])
    bias = (n - 1) * (np.mean(jackknife_stats) - full_stat)
    variance = ((n - 1) / n) * np.sum((jackknife_stats - np.mean(jackknife_stats))**2)
    return full_stat - bias, np.sqrt(variance)
```

**When:** Bias estimation important, small samples, or when bootstrap is too expensive.

**Binning analysis (for correlated time series):**

```python
def binning_analysis(time_series, max_bin_level=20):
    """
    Determine statistical error accounting for autocorrelation.
    Error estimate plateaus at the correct value when bin size exceeds
    autocorrelation time.
    """
    errors = []
    data = np.array(time_series)
    for level in range(max_bin_level):
        n = len(data)
        error = np.std(data) / np.sqrt(n - 1)
        errors.append((2**level, error))
        # Bin pairs
        if n % 2 == 1:
            data = data[:-1]
        data = (data[::2] + data[1::2]) / 2
        if len(data) < 4:
            break
    return errors  # Error should plateau; plateau value is true error
```

**When:** Monte Carlo time series, molecular dynamics trajectories, any correlated samples.

### Goodness-of-fit tests

```python
def chi_squared_test(observed, expected, errors, dof=None):
    """
    Chi-squared test for agreement between data and model.

    Returns:
        (chi2, chi2_reduced, p_value)
    """
    from scipy.stats import chi2 as chi2_dist
    chi2 = np.sum(((observed - expected) / errors)**2)
    if dof is None:
        dof = len(observed) - 1
    chi2_red = chi2 / dof
    p_value = 1 - chi2_dist.cdf(chi2, dof)

    # Interpretation:
    # chi2_red ~ 1: good fit
    # chi2_red >> 1: model doesn't fit data (or errors underestimated)
    # chi2_red << 1: overfitting (or errors overestimated)
    status = "PASS" if 0.1 < chi2_red < 3.0 else "WARN"
    print(f"{status} chi2/dof = {chi2_red:.2f}, p-value = {p_value:.4f}")
    return chi2, chi2_red, p_value
```

### Autocorrelation and effective sample size

```python
def autocorrelation_time(time_series):
    """
    Estimate integrated autocorrelation time.
    Effective independent samples = N / (2 * tau_int).
    """
    n = len(time_series)
    mean = np.mean(time_series)
    var = np.var(time_series)
    if var == 0:
        return 0

    # Compute autocorrelation function
    acf = np.correlate(time_series - mean, time_series - mean, mode='full')
    acf = acf[n-1:] / (var * n)

    # Integrate until first negative value or noise dominates
    tau_int = 0.5  # Start with C(0)/2 contribution
    for t in range(1, n // 2):
        if acf[t] < 0:
            break
        tau_int += acf[t]

    n_eff = n / (2 * tau_int)
    print(f"Autocorrelation time: tau_int = {tau_int:.1f}")
    print(f"Effective samples: N_eff = {n_eff:.0f} (out of {n} total)")
    return tau_int
```

### Thermalization check

```python
def verify_thermalization(observable_trace, n_bins=10):
    """
    Check that Monte Carlo has thermalized by comparing early and late portions.
    """
    n = len(observable_trace)
    bin_size = n // n_bins
    bin_means = [np.mean(observable_trace[i*bin_size:(i+1)*bin_size])
                 for i in range(n_bins)]

    # First half vs second half
    first_half = np.mean(bin_means[:n_bins//2])
    second_half = np.mean(bin_means[n_bins//2:])
    overall_std = np.std(bin_means)

    drift = abs(first_half - second_half) / overall_std if overall_std > 0 else 0
    status = "PASS" if drift < 2.0 else "FAIL"
    print(f"{status} Thermalization: drift = {drift:.1f}sigma between halves")
    return drift < 2.0
```

### Finite-size scaling (for phase transitions and critical phenomena)

```python
def verify_finite_size_scaling(observable_at_sizes, sizes, expected_exponent,
                                critical_point, tolerance=0.1):
    """
    Verify finite-size scaling: O(L) ~ L^{-x/nu} f((T - T_c) L^{1/nu}).

    At T = T_c: O(L) ~ L^{-x/nu}, so log(O) vs log(L) gives slope -x/nu.
    """
    log_L = np.log(sizes)
    log_O = np.log(np.abs(observable_at_sizes))
    slope, intercept = np.polyfit(log_L, log_O, 1)
    relative_diff = abs(slope - expected_exponent) / abs(expected_exponent)
    status = "PASS" if relative_diff < tolerance else "FAIL"
    print(f"{status} Finite-size scaling: exponent = {slope:.3f}, "
          f"expected = {expected_exponent:.3f}")
    return relative_diff < tolerance
```

**Verification checklist for statistical results:**

- [ ] Autocorrelation time estimated; effective sample size computed
- [ ] Error bars from proper resampling (bootstrap/jackknife/binning), not naive std/sqrt(N)
- [ ] Thermalization verified (discard burn-in)
- [ ] Goodness of fit assessed (chi-squared, p-value)
- [ ] Systematic errors estimated separately from statistical
- [ ] Finite-size effects quantified (if applicable)
- [ ] Results stable under variation of binning/resampling parameters
- [ ] Error propagation correct for derived quantities

**When to apply:**

- Every Monte Carlo simulation (classical or quantum)
- Every fit to numerical or experimental data
- Every result where randomness enters (disorder averaging, stochastic methods)
- Before quoting any numerical value with error bars

</statistical_validation>

## Numerical Calculation Checklist

- [ ] Convergence: result stable under grid/basis/timestep refinement
- [ ] Richardson extrapolation: used to estimate continuum/infinite-basis limit
- [ ] Conservation: energy, probability, charge conserved to specified tolerance
- [ ] Known limits: reproduces analytical results where available
- [ ] Sum rules: spectral sum rules satisfied (f-sum rule, moment sum rules)
- [ ] Kramers-Kronig: real and imaginary parts of response functions consistent
- [ ] Cross-check: agrees with independent method or published benchmark
- [ ] Stability: solution does not blow up or oscillate unphysically
- [ ] Resolution: sufficient points in regions of rapid variation
- [ ] Error estimation: uncertainty quantified (not just "converged")
- [ ] Physical plausibility: positive energies, normalized probabilities, etc.
- [ ] Spectral positivity: A(k,omega) >= 0 everywhere

## Simulation Checklist

- [ ] Initial conditions: physically reasonable and correctly implemented
- [ ] Time integration: symplectic integrator for Hamiltonian systems
- [ ] Conservation monitoring: tracked throughout simulation, not just at end
- [ ] Finite-size effects: checked by varying system size
- [ ] Equilibration / thermalization: verified by comparing early and late portions
- [ ] Autocorrelation: time estimated, effective sample size computed
- [ ] Statistical errors: from proper resampling (bootstrap/jackknife/binning)
- [ ] Systematic errors: extrapolated to continuum/infinite-volume limit
- [ ] Reproducibility: same result with different random seeds
- [ ] Finite-size scaling: critical exponents consistent with universality class

<automated_verification_script>

## Automated Verification Approach

For the verification subagent, use this pattern:

```python
class PhysicsVerifier:
    """Automated verification of physics calculations."""

    def __init__(self, tolerance=1e-8, unit_system="natural"):
        self.tolerance = tolerance
        self.unit_system = unit_system
        self.results = []

    def check_dimensions(self, expression, expected_dimensions):
        """Verify dimensional consistency."""
        pass

    def check_limiting_case(self, general, limit_params, expected):
        """Verify a limiting case."""
        pass

    def check_conservation(self, trajectory, conserved_qty, label=""):
        """Check a conservation law along a trajectory."""
        values = [conserved_qty(state) for state in trajectory]
        drift = max(abs(v - values[0]) for v in values) / (abs(values[0]) + 1e-30)
        passed = drift < self.tolerance
        self.results.append({
            "check": f"Conservation: {label}",
            "passed": passed,
            "detail": f"max relative drift = {drift:.2e}"
        })
        return passed

    def check_convergence(self, values, parameters, expected_order=None):
        """Check numerical convergence."""
        pass

    def check_symmetry(self, expression, transform, expected="invariant"):
        """Check symmetry under transformation."""
        pass

    def check_positivity(self, values, label=""):
        """Check that values are non-negative."""
        min_val = min(values)
        passed = min_val >= -self.tolerance
        self.results.append({
            "check": f"Positivity: {label}",
            "passed": passed,
            "detail": f"min value = {min_val:.2e}"
        })
        return passed

    def check_normalization(self, values, expected_sum=1.0, label=""):
        """Check that values sum to expected total."""
        total = sum(values)
        passed = abs(total - expected_sum) < self.tolerance
        self.results.append({
            "check": f"Normalization: {label}",
            "passed": passed,
            "detail": f"sum = {total:.10e}, expected = {expected_sum}"
        })
        return passed

    def generate_report(self):
        """Generate VERIFICATION.md content."""
        lines = ["# Verification Report\n"]
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        lines.append(f"**Overall: {passed}/{total} checks passed**\n")

        for r in self.results:
            symbol = "PASS" if r["passed"] else "FAIL"
            lines.append(f"- {symbol} {r['check']}: {r['detail']}")

        return "\n".join(lines)
```

Run these checks against each physics artifact. Aggregate results into VERIFICATION.md.

</automated_verification_script>

## Pre-Checkpoint Automation

For automation-first checkpoint patterns, computational environment management, and error recovery protocols, see:

**references/orchestration/checkpoints.md** -> `<automation_reference>` section

Key principles:

- GPD sets up verification environment BEFORE presenting checkpoints
- Users review results (plots, tables, convergence data), not raw output
- Computational lifecycle: set up environment, run checks, present results
- Package installation: auto-install where safe, checkpoint for user choice otherwise
- Error handling: fix numerical issues before checkpoint, never present checkpoint with failed convergence

## See Also

- `references/verification/core/verification-quick-reference.md` -- Compact checklist (default entry point)
- `references/verification/core/verification-core.md` -- Dimensional analysis, limiting cases, conservation laws
- `../domains/verification-domain-qft.md` -- QFT, particle physics, GR, mathematical physics
- `../domains/verification-domain-condmat.md` -- Condensed matter, quantum information, AMO
- `../domains/verification-domain-statmech.md` -- Statistical mechanics, cosmology, fluids

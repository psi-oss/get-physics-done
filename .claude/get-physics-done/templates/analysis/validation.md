---
template_version: 1
---
> **Status:** Supplemental analysis template. The live `map-theory` workflow now loads
> `./.claude/get-physics-done/references/templates/theory-mapper/*` via `gpd-theory-mapper`, not this file.
> Keep this template only as standalone reference material for manual analysis work.
>
> For pre-project literature research, see `templates/research-project/`.

# Validation Template

Template for `.gpd/analysis/VALIDATION.md` - captures the validation strategy for the research.

**Purpose:** Document how results are verified. Guide for adding validation checks that match existing patterns. Covers analytical limits, numerical tests, and comparisons with literature.

---

## File Template

````markdown
# Validation Strategy

**Analysis Date:** [YYYY-MM-DD]

## Test Framework

**Runner:**

- [Framework: e.g., "pytest 8.x for computational code"]
- [Config: e.g., "pyproject.toml [tool.pytest.ini_options]"]

**Assertion approach:**

- [e.g., "numpy.testing.assert_allclose with rtol=1e-10 for numerical comparisons"]
- [e.g., "Exact match for integer/rational PN coefficients"]

**Run Commands:**

```bash
[e.g., "pytest tests/unit"]                    # Unit checks
[e.g., "pytest tests/integration"]             # Cross-module validation
[e.g., "pytest tests -k 'test_name'"]         # Single test
[e.g., "make test-cov"]                        # Coverage report
```
````

## Analytical Checks

**Known limits:**

- [Limit]: [What should be recovered and how it is tested]

  - Expected: [Exact analytic result in this limit]
  - Test: [How automated: e.g., "test file", "notebook check"]
  - Tolerance: [e.g., "exact match", "< 10^-12 relative error"]

- [Limit]: [Description]
  - Expected: [Analytic result]
  - Test: [How tested]
  - Tolerance: [Precision]

**Symmetry checks:**

- [Symmetry]: [What it implies for the result]
  - Test: [e.g., "Verify result is invariant under m_1 <-> m_2 exchange for equal masses"]
  - File: [Test file location]

**Sum rules and identities:**

- [Identity]: [What it states]
  - Test: [How verified: e.g., "energy balance dE/dt = -F at each PN order"]
  - Tolerance: [Precision of check]

## Numerical Convergence Tests

**Resolution convergence:**

- [Quantity]: [What is checked for convergence]
  - Method: [e.g., "Run at N, 2N, 4N grid points; check Richardson extrapolation"]
  - Expected scaling: [e.g., "4th order convergence for RK4"]
  - File: [Test or notebook location]

**Series convergence:**

- [Series]: [Which perturbative series]
  - Method: [e.g., "Compare partial sums at orders N-1, N, N+1"]
  - Regime: [e.g., "Converges for v/c < 0.3"]
  - File: [Where tested]

**Parameter sensitivity:**

- [Parameter]: [What parameter is varied]
  - Method: [e.g., "Vary integration tolerance by 10x; check result stability"]
  - Acceptable variation: [e.g., "< 10^-10 change in output"]

## Literature Comparisons

**Published analytical results:**

- [Reference]: [What result is compared]

  - Our result: [Location of our calculation]
  - Their result: [Equation/table number in reference]
  - Agreement: [e.g., "Exact match through 3.5PN", "Agrees to 8 significant digits"]
  - File: [Test file that automates this check]

- [Reference]: [What is compared]
  - Our result: [Location]
  - Their result: [Reference location]
  - Agreement: [Level of agreement]
  - File: [Automated test location]

**Published numerical results:**

- [Reference]: [What numerical result is compared]
  - Our result: [How computed]
  - Their result: [Published value]
  - Agreement: [e.g., "Within 0.1% for all tested parameter points"]
  - File: [Test location]

## Cross-Code Comparisons

**[Code name]:**

- What is compared: [e.g., "Waveform phase and amplitude"]
- Parameter space tested: [e.g., "100 points in (m_1, m_2, chi) space"]
- Agreement metric: [e.g., "Mismatch < 10^-3 for all points"]
- File: [Test location]

**[Code name]:**

- What is compared: [Description]
- Parameter space tested: [Range]
- Agreement metric: [Threshold]
- File: [Test location]

## Internal Consistency Checks

**Self-consistency:**

- [Check]: [e.g., "Energy balance: independently computed energy and flux satisfy dE/dt = -F"]

  - How tested: [e.g., "Numerical comparison at 50 frequency points"]
  - Tolerance: [e.g., "Relative difference < 10^-12"]
  - File: [Test location]

- [Check]: [Description]
  - How tested: [Method]
  - Tolerance: [Precision]
  - File: [Location]

**Gauge invariance:**

- [Check]: [e.g., "Physical observables are independent of coordinate choice"]
  - How tested: [e.g., "Compute GW phase in harmonic and ADM gauges; compare"]
  - Tolerance: [Expected agreement]
  - File: [Location]

## Test Organization

**Location:**

- [Pattern: e.g., "tests/unit/ for isolated function checks"]
- [Pattern: e.g., "tests/integration/ for end-to-end validation"]

**Naming:**

- [Pattern: e.g., "test*[module]*[aspect].py"]
- [Pattern: e.g., "test_pn_coefficients.py, test_waveform_accuracy.py"]

**Structure:**

```python
[Show actual test pattern used, e.g.:

class TestPNCoefficients:
    """Verify PN expansion coefficients against published values."""

    def test_energy_newtonian(self):
        """E_0 = -mu v^2 / 2 (Newtonian binding energy)."""
        result = compute_energy(v=0.1, nu=0.25, pn_order=0)
        expected = -0.25 * 0.1**2 / 2
        np.testing.assert_allclose(result, expected, rtol=1e-14)

    def test_energy_1pn_equal_mass(self):
        """1PN energy coefficient for equal mass: -(3/4 + nu/12)."""
        ...
]
```

**Markers:**

- [e.g., "@pytest.mark.unit for fast isolated tests"]
- [e.g., "@pytest.mark.integration for slower cross-module tests"]
- [e.g., "@pytest.mark.slow for convergence studies"]

## Coverage

**Requirements:**

- [Target: e.g., "All PN coefficients checked against literature"]
- [Target: e.g., "All known limits verified analytically"]
- [Enforcement: e.g., "CI runs unit tests on every commit"]

**Gaps:**

- [Gap]: [What is not yet validated and why]
- [Gap]: [What is not yet validated and why]

---

_Validation analysis: [date]_
_Update when validation strategy changes_

````

<good_examples>
```markdown
# Validation Strategy

**Analysis Date:** 2025-06-15

## Test Framework

**Runner:**
- pytest 8.0 with numpy testing utilities
- Config: pyproject.toml [tool.pytest.ini_options], asyncio_mode = "auto"

**Assertion approach:**
- numpy.testing.assert_allclose(rtol=1e-12) for floating-point comparisons
- Exact == for integer coefficients and rational number checks
- Custom assert_pn_coefficient() helper in tests/conftest.py

**Run Commands:**
```bash
pytest tests/unit                              # Fast coefficient checks (~5s)
pytest tests/integration                       # Cross-module validation (~60s)
pytest tests -k "test_energy"                  # All energy-related tests
pytest tests --cov=src --cov-report=html       # Coverage report
````

## Analytical Checks

**Known limits:**

- Test-particle limit (nu -> 0): Should recover Schwarzschild geodesic results

  - Expected: Energy E(x) = -(mu/2) x [1 - (3/4)x - (27/8)x^2 + ...] matches Fujita (2012)
  - Test: `tests/unit/test_known_limits.py::test_test_particle_energy`
  - Tolerance: Exact rational coefficient match

- Equal-mass limit (nu = 1/4): Maximum symmetric mass ratio

  - Expected: All odd-in-delta terms vanish; cross-check against Blanchet (2014) Table I
  - Test: `tests/unit/test_known_limits.py::test_equal_mass_symmetry`
  - Tolerance: < 10^-14 relative error for numerical coefficients

- Newtonian limit (x -> 0): Leading-order should recover Keplerian orbit
  - Expected: E = -mu x / 2, F = (32/5) nu^2 x^5
  - Test: `tests/unit/test_known_limits.py::test_newtonian_limit`
  - Tolerance: Exact match

**Symmetry checks:**

- Exchange symmetry (1 <-> 2): Results must be invariant under m_1 <-> m_2

  - Test: Compute for (m_1, m_2) and (m_2, m_1); results must be identical
  - File: `tests/unit/test_symmetries.py::test_exchange_symmetry`

- Time reversal: Conservative dynamics must be time-reversal symmetric
  - Test: Evolve forward and backward; check trajectory matches (without radiation reaction)
  - File: `tests/integration/test_time_reversal.py`

**Sum rules and identities:**

- Energy balance: dE/dt = -F (energy loss equals radiated flux)

  - Test: Independently compute dE/dt from orbital evolution and F from multipole moments
  - Tolerance: Relative difference < 10^-12 at each PN order
  - File: `tests/integration/test_energy_balance.py`

- Angular momentum balance: dJ/dt = -G (angular momentum flux)
  - Test: Same approach as energy balance
  - Tolerance: < 10^-12
  - File: `tests/integration/test_angular_momentum_balance.py`

## Numerical Convergence Tests

**ODE integration convergence:**

- Orbital phase: Check convergence with decreasing timestep
  - Method: Run with rtol = 10^-8, 10^-10, 10^-12, 10^-14; verify phase converges
  - Expected scaling: Error ~ rtol for adaptive methods
  - File: `tests/integration/test_ode_convergence.py`

**PN series convergence:**

- Energy flux partial sums: Monitor convergence of sum over PN orders
  - Method: Compare F_N and F_{N+1} at fixed v/c
  - Regime: Well-converged for v/c < 0.3; oscillatory for v/c > 0.35
  - File: `notebooks/convergence_study.ipynb`

**FFT resolution:**

- Frequency-domain waveform: Convergence with increasing time-domain sampling
  - Method: Double sampling rate; check h(f) changes by < 10^-6
  - Acceptable variation: < 10^-8 in strain at all frequencies
  - File: `tests/integration/test_fft_convergence.py`

## Literature Comparisons

**Published analytical results:**

- Blanchet, Living Reviews (2014), Table I: PN energy coefficients through 3PN

  - Our result: `src/dynamics/pn_equations.py`, function `energy_pn()`
  - Their result: Eq. (190), coefficients listed in Table I
  - Agreement: Exact match through 3PN (all rational + pi^2 terms)
  - File: `tests/unit/test_pn_coefficients.py::TestEnergyCoefficients`

- Blanchet et al. (2023): 4.5PN energy flux

  - Our result: `src/dynamics/pn_equations.py`, function `flux_pn()`
  - Their result: Eq. (4.3), new logarithmic terms at 4PN and 4.5PN
  - Agreement: Exact match for all known coefficients
  - File: `tests/unit/test_pn_coefficients.py::TestFluxCoefficients`

- Fujita (2012): High-order PN coefficients from black hole perturbation theory
  - Our result: Test-particle limit of our general expressions
  - Their result: Table II, coefficients through 22PN
  - Agreement: Exact through 3.5PN; numerical agreement to 30 digits at 4PN
  - File: `tests/unit/test_test_particle_limit.py`

## Cross-Code Comparisons

**LALSuite (IMRPhenomD):**

- What is compared: GW phase Phi(f) and amplitude A(f) in frequency domain
- Parameter space tested: 100 points on grid m_1 in [5, 50], m_2 in [5, 50], chi = 0
- Agreement metric: Phase difference < 0.05 rad for f < 100 Hz; mismatch < 10^-3
- File: `tests/integration/test_lalsuite_comparison.py`

**EOBNRv4 (via LALSuite):**

- What is compared: Time-domain waveform h\_+(t) for quasi-circular inspiral
- Parameter space tested: 20 equal-mass non-spinning configurations
- Agreement metric: Phase difference < 0.5 rad through 0.9 \* f_ISCO
- File: `tests/integration/test_eob_comparison.py`

## Internal Consistency Checks

**Energy balance self-consistency:**

- Check: Energy and flux computed independently from different code paths satisfy dE/dt = -F
  - How tested: Evaluate at 50 values of x from 0.01 to 0.2
  - Tolerance: Relative difference < 10^-12 at each point
  - File: `tests/integration/test_energy_balance.py`

**Circular orbit consistency:**

- Check: Circular orbit condition dE/dr = 0 at r = r_circ is satisfied
  - How tested: Numerically verify that energy is minimized at computed circular radius
  - Tolerance: |dE/dr| < 10^-14 at r_circ
  - File: `tests/unit/test_circular_orbit.py`

## Test Organization

**Location:**

- tests/unit/ for fast isolated function checks (< 1s each)
- tests/integration/ for cross-module and cross-code validation (< 60s each)
- notebooks/ for exploratory convergence studies (manual)

**Naming:**

- test_pn_coefficients.py: Coefficient verification against literature
- test_known_limits.py: Analytical limit checks
- test_symmetries.py: Symmetry property verification
- test\_[code]\_comparison.py: Cross-code comparison tests

**Markers:**

- @pytest.mark.unit: Fast, no external dependencies
- @pytest.mark.integration: May call external codes, slower
- @pytest.mark.slow: Convergence studies, parameter surveys (> 60s)

## Coverage

**Requirements:**

- All published PN coefficients verified against literature references
- All known analytical limits checked (test-particle, equal-mass, Newtonian)
- Energy balance verified at every PN order
- At least one cross-code comparison per waveform family

**Gaps:**

- Spinning binary coefficients: Only leading-order spin-orbit tested; higher spin-spin terms not yet verified against Marsat et al. (2013)
- Eccentric orbits: No tests yet (quasi-circular only)
- Memory contribution: Not tested against Favata (2009) results

---

_Validation analysis: 2025-06-15_
_Update when validation strategy changes_

```
</good_examples>

<guidelines>
**What belongs in VALIDATION.md:**
- Test framework and run commands
- Analytical limit checks (known results the code must reproduce)
- Symmetry verification
- Numerical convergence tests
- Literature comparisons with specific references
- Cross-code comparisons
- Internal consistency checks (sum rules, balance equations)
- Test organization and naming patterns
- Coverage requirements and gaps

**What does NOT belong here:**
- Specific test results (those belong in test output)
- Theoretical framework (that's THEORETICAL_FRAMEWORK.md)
- Implementation details (defer to actual test files)
- Methods description (that's METHODS.md)

**When filling this template:**
- Identify all published results that can serve as benchmarks
- List analytical limits that provide exact checks
- Note symmetries that constrain the results
- Check for existing test files and their patterns
- Document what is NOT yet tested (gaps are critical information)
- Be specific about tolerances and agreement metrics

**Useful for research planning when:**
- Adding new calculations (what tests should accompany them?)
- Debugging discrepancies (what checks exist? what is missing?)
- Assessing reliability (how thoroughly are results validated?)
- Extending to new regimes (what new tests are needed?)
- Writing papers (what validation can be cited?)

**Why this matters:**
Physics calculations have no compiler to catch errors. A sign mistake in a derivation propagates silently. The only defense is systematic validation against known results, limits, and independent calculations. This document is the map of that defense.
</guidelines>
```

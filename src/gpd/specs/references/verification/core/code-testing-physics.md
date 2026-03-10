# Physics-Specific Code Testing

Patterns for writing tests that catch physics errors, not just software bugs. Standard software testing checks that code runs correctly; physics testing checks that the code produces correct physics.

<core_principle>

**Test the physics, not the implementation.**

A physics test should fail when the physics is wrong and pass when it is right, regardless of how the code is structured internally. The test suite is a machine-readable statement of what physical properties the code must satisfy.

**Priority order:**

1. Conservation laws and exact constraints (must always hold)
2. Known limiting cases (must reproduce textbook results)
3. Symmetry properties (must respect the theory's symmetries)
4. Regression values (must match previously validated results)
5. Convergence behavior (must improve with resolution)

</core_principle>

<limiting_case_tests>

## Parameterized Tests Over Known Limiting Cases

The most powerful physics tests: a general result must reproduce known special cases.

### Pattern: Parameterized Limit Tests

```python
import pytest
import numpy as np

# Test that a general dispersion relation reduces to known limits
@pytest.mark.parametrize("limit_name, params, expected_fn", [
    (
        "free_particle",
        {"mass": 1.0, "coupling": 0.0},
        lambda k: k**2 / 2,  # E = k^2 / (2m)
    ),
    (
        "strong_coupling_gap",
        {"mass": 1.0, "coupling": 100.0},
        lambda k: np.sqrt(100.0 + k**2),  # E ~ sqrt(Delta^2 + k^2)
    ),
    (
        "long_wavelength",
        {"mass": 1.0, "coupling": 0.5},
        lambda k: 0.5 + k**2 / 2,  # E ~ Delta + k^2/(2m) for small k
    ),
])
def test_dispersion_limiting_cases(limit_name, params, expected_fn):
    """Verify dispersion relation reproduces known limits."""
    k_values = np.linspace(0, 0.1, 20)  # Small k for long-wavelength test
    for k in k_values:
        computed = compute_dispersion(k, **params)
        expected = expected_fn(k)
        np.testing.assert_allclose(
            computed, expected, rtol=1e-6,
            err_msg=f"Limit '{limit_name}' failed at k={k:.4f}"
        )
```

### Pattern: Classical Limit (hbar -> 0)

```python
@pytest.mark.parametrize("hbar", [1.0, 0.1, 0.01, 0.001])
def test_classical_limit(hbar):
    """Quantum result must approach classical result as hbar -> 0."""
    quantum_result = compute_quantum_energy(hbar=hbar)
    classical_result = compute_classical_energy()

    # Error should scale as hbar^2 (leading quantum correction)
    error = abs(quantum_result - classical_result)
    expected_scaling = hbar**2
    # Allow factor of 100 for the unknown prefactor
    assert error < 100 * expected_scaling, (
        f"Classical limit: error {error:.2e} does not scale as hbar^2 = {expected_scaling:.2e}"
    )
```

### Pattern: Non-Relativistic Limit (c -> infinity)

```python
def test_non_relativistic_limit():
    """Relativistic energy must reduce to p^2/(2m) + mc^2 for v << c."""
    m, p = 1.0, 0.01  # p << mc (non-relativistic)
    for c in [10.0, 100.0, 1000.0]:
        relativistic = compute_relativistic_energy(m, p, c)
        non_relativistic = m * c**2 + p**2 / (2 * m)
        np.testing.assert_allclose(
            relativistic, non_relativistic,
            rtol=(p / (m * c))**2,  # Correction is O(v^2/c^2)
            err_msg=f"Non-relativistic limit failed at c={c}"
        )
```

### Pattern: Weak-Coupling Limit

```python
@pytest.mark.parametrize("g", [0.001, 0.01, 0.1])
def test_weak_coupling_limit(g):
    """Interacting result must approach free result as coupling -> 0."""
    interacting = compute_ground_state_energy(coupling=g)
    free = compute_free_energy()
    first_order = compute_first_order_correction(coupling=g)

    # Result should match free + g * first_order + O(g^2)
    expected = free + first_order
    error = abs(interacting - expected)
    assert error < 10 * g**2, (
        f"Weak-coupling: residual {error:.2e} should be O(g^2) = O({g**2:.2e})"
    )
```

</limiting_case_tests>

<symmetry_tests>

## Property-Based Testing for Symmetries

Symmetry tests verify that the code respects the mathematical structure of the physical theory. These tests are powerful because they don't require knowing the answer -- only that it transforms correctly.

### Pattern: Rotational Invariance

```python
import numpy as np
from scipy.spatial.transform import Rotation

def random_rotation():
    """Generate a random 3D rotation matrix."""
    return Rotation.random().as_matrix()

@pytest.mark.parametrize("seed", range(10))
def test_energy_rotational_invariance(seed):
    """Energy of an isolated system must be independent of orientation."""
    rng = np.random.default_rng(seed)
    positions = rng.standard_normal((10, 3))  # 10 particles in 3D
    R = random_rotation()

    energy_original = compute_energy(positions)
    energy_rotated = compute_energy(positions @ R.T)

    np.testing.assert_allclose(
        energy_original, energy_rotated, rtol=1e-12,
        err_msg="Energy is not rotationally invariant"
    )
```

### Pattern: Translational Invariance

```python
@pytest.mark.parametrize("displacement", [
    np.array([1.0, 0.0, 0.0]),
    np.array([0.0, 0.0, 5.7]),
    np.array([3.1, -2.4, 0.8]),
])
def test_energy_translational_invariance(displacement):
    """Energy must not change under uniform translation."""
    positions = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    energy_original = compute_energy(positions)
    energy_shifted = compute_energy(positions + displacement)
    np.testing.assert_allclose(energy_original, energy_shifted, atol=1e-14)
```

### Pattern: Particle Exchange Symmetry

```python
def test_boson_exchange_symmetry():
    """Bosonic wavefunction must be symmetric under particle exchange."""
    r1, r2 = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
    psi_12 = wavefunction(r1, r2)
    psi_21 = wavefunction(r2, r1)
    np.testing.assert_allclose(psi_12, psi_21, atol=1e-14,
                               err_msg="Bosonic wavefunction not symmetric")

def test_fermion_exchange_antisymmetry():
    """Fermionic wavefunction must be antisymmetric under particle exchange."""
    r1, r2 = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
    psi_12 = wavefunction(r1, r2)
    psi_21 = wavefunction(r2, r1)
    np.testing.assert_allclose(psi_12, -psi_21, atol=1e-14,
                               err_msg="Fermionic wavefunction not antisymmetric")
```

### Pattern: Time-Reversal Symmetry

```python
def test_time_reversal_energy_spectrum():
    """For a time-reversal-invariant Hamiltonian, E(k) = E(-k)."""
    k_values = np.linspace(-np.pi, np.pi, 100)
    for k in k_values:
        E_k = compute_band_energy(k)
        E_minus_k = compute_band_energy(-k)
        np.testing.assert_allclose(
            E_k, E_minus_k, atol=1e-12,
            err_msg=f"Time reversal violated: E({k:.3f}) != E({-k:.3f})"
        )
```

### Pattern: Gauge Invariance

```python
@pytest.mark.parametrize("gauge_param", [0.0, 0.5, 1.0, 2.0])
def test_observable_gauge_invariance(gauge_param):
    """Physical observables must not depend on gauge parameter."""
    cross_section = compute_cross_section(gauge_xi=gauge_param)
    reference = compute_cross_section(gauge_xi=1.0)  # Feynman gauge
    np.testing.assert_allclose(
        cross_section, reference, rtol=1e-10,
        err_msg=f"Cross section depends on gauge parameter xi={gauge_param}"
    )
```

</symmetry_tests>

<conservation_tests>

## Conservation Law Tests

Conservation laws are exact constraints. Any violation in a simulation indicates a bug (or a physics effect that must be explicitly justified).

### Pattern: Energy Conservation in Time Evolution

```python
def test_energy_conservation(simulation_trajectory):
    """Total energy must be conserved in Hamiltonian dynamics."""
    energies = [compute_total_energy(state) for state in simulation_trajectory]
    E0 = energies[0]
    max_drift = max(abs(E - E0) for E in energies)
    relative_drift = max_drift / abs(E0)

    # Symplectic integrator: energy oscillates but doesn't drift
    # Drift tolerance depends on dt and integrator order
    assert relative_drift < 1e-8, (
        f"Energy drift: {relative_drift:.2e} (max |dE| = {max_drift:.2e})"
    )
```

### Pattern: Probability Conservation

```python
def test_probability_conservation():
    """Quantum evolution must preserve total probability."""
    psi_0 = initial_state()
    assert abs(np.linalg.norm(psi_0) - 1.0) < 1e-14, "Initial state not normalized"

    for t in np.linspace(0, 10, 100):
        psi_t = evolve(psi_0, t)
        norm = np.linalg.norm(psi_t)
        assert abs(norm - 1.0) < 1e-10, (
            f"Probability not conserved at t={t}: ||psi|| = {norm}"
        )
```

### Pattern: Charge Conservation

```python
def test_charge_conservation(field_evolution):
    """Total charge Q = integral rho d^3x must be constant."""
    charges = []
    for timestep in field_evolution:
        rho = timestep["charge_density"]
        Q = np.sum(rho) * timestep["volume_element"]
        charges.append(Q)

    Q0 = charges[0]
    max_violation = max(abs(Q - Q0) for Q in charges)
    assert max_violation < 1e-12, (
        f"Charge conservation violated: max |dQ| = {max_violation:.2e}"
    )
```

### Pattern: Momentum Conservation

```python
def test_momentum_conservation_collision():
    """Total momentum must be conserved in a collision."""
    p_before = sum(particle.momentum for particle in initial_state)
    p_after = sum(particle.momentum for particle in final_state)

    for component in range(3):
        np.testing.assert_allclose(
            p_before[component], p_after[component], atol=1e-12,
            err_msg=f"Momentum component {component} not conserved"
        )
```

### Pattern: Sum Rule Verification

```python
def test_f_sum_rule(spectral_function, omega_grid, n_electrons, mass):
    """f-sum rule: integral of omega * Im[epsilon(omega)] = pi/2 * omega_p^2."""
    from scipy.integrate import trapezoid

    integrand = omega_grid * spectral_function
    integral = trapezoid(integrand, omega_grid)
    omega_p_squared = 4 * np.pi * n_electrons / mass  # Plasma frequency squared
    expected = np.pi / 2 * omega_p_squared

    np.testing.assert_allclose(
        integral, expected, rtol=0.01,
        err_msg=f"f-sum rule violated: integral={integral:.4e}, expected={expected:.4e}"
    )
```

</conservation_tests>

<regression_tests>

## Regression Tests for Numerical Results

Store validated numerical results and check that code changes don't break them.

### Pattern: Gold Value Registry

```python
import json
from pathlib import Path

GOLD_VALUES_FILE = Path(__file__).parent / "gold_values.json"

def load_gold_values():
    """Load previously validated numerical results."""
    with open(GOLD_VALUES_FILE) as f:
        return json.load(f)

GOLD = load_gold_values()

@pytest.mark.parametrize("case_name, params", [
    ("hydrogen_ground_state", {"Z": 1, "n": 1}),
    ("helium_ground_state", {"Z": 2, "n": 1}),
    ("lithium_ground_state", {"Z": 3, "n": 1}),
])
def test_against_gold_values(case_name, params):
    """Computed values must match previously validated results."""
    computed = compute_energy(**params)
    expected = GOLD[case_name]["energy"]
    tolerance = GOLD[case_name]["tolerance"]

    np.testing.assert_allclose(
        computed, expected, rtol=tolerance,
        err_msg=(
            f"Regression: {case_name} energy changed.\n"
            f"  Previous: {expected}\n"
            f"  Current:  {computed}\n"
            f"  If intentional, update gold_values.json with justification."
        )
    )
```

### Gold Values File Format

```json
{
  "hydrogen_ground_state": {
    "energy": -13.605693,
    "tolerance": 1e-6,
    "unit": "eV",
    "source": "NIST, exact: -13.605693009 eV",
    "validated_date": "2025-01-15",
    "method": "variational with 50-term Hylleraas expansion"
  },
  "helium_ground_state": {
    "energy": -79.0052,
    "tolerance": 1e-4,
    "unit": "eV",
    "source": "Drake (2006), exact: -79.005 151 042 eV",
    "validated_date": "2025-01-15",
    "method": "CI with cc-pVQZ basis"
  }
}
```

### Pattern: Literature Benchmark Comparison

```python
# Benchmark values from published papers with full citations
BENCHMARKS = {
    "2d_ising_Tc": {
        "value": 2.269185,
        "uncertainty": 1e-6,
        "source": "Onsager exact solution: 2J/(k_B * ln(1 + sqrt(2)))",
        "reference": "Onsager, Phys. Rev. 65, 117 (1944)"
    },
    "3d_ising_nu": {
        "value": 0.6300,
        "uncertainty": 0.0004,
        "source": "Conformal bootstrap",
        "reference": "Kos et al., JHEP 08, 036 (2016)"
    },
    "qed_anomalous_moment": {
        "value": 0.00115965218128,
        "uncertainty": 1.8e-13,
        "source": "10th order QED + hadronic + electroweak",
        "reference": "Aoyama et al., Phys. Rev. Lett. 109, 111808 (2012)"
    },
}

@pytest.mark.parametrize("name, benchmark", BENCHMARKS.items())
def test_literature_benchmarks(name, benchmark):
    """Verify computed values match published benchmarks."""
    computed = compute_benchmark(name)
    np.testing.assert_allclose(
        computed, benchmark["value"],
        atol=10 * benchmark["uncertainty"],  # 10-sigma tolerance
        err_msg=f"Benchmark {name} failed. Reference: {benchmark['reference']}"
    )
```

### When to Update Gold Values

Gold values should only change when:

1. A bug is found and fixed (old value was wrong)
2. The method is improved (new value is more accurate, with justification)
3. Better literature values become available

Every gold value update must include a justification in the commit message explaining why the old value was wrong or why the new one is better.

</regression_tests>

<convergence_tests>

## Convergence Tests

Verify that numerical results improve systematically as resolution increases.

### Pattern: Grid Convergence with Order Verification

```python
@pytest.mark.parametrize("expected_order", [2, 4])
def test_grid_convergence(expected_order):
    """Result must converge at the expected rate as grid is refined."""
    grid_sizes = [32, 64, 128, 256]
    results = [compute_on_grid(N) for N in grid_sizes]

    # Use finest grid as reference
    ref = results[-1]
    errors = [abs(r - ref) for r in results[:-1]]

    for i in range(len(errors) - 1):
        ratio = grid_sizes[i] / grid_sizes[i + 1]
        if errors[i + 1] > 1e-15:  # Avoid division by zero at machine precision
            observed_order = np.log(errors[i] / errors[i + 1]) / np.log(1 / ratio)
            assert abs(observed_order - expected_order) < 0.5, (
                f"Convergence order {observed_order:.1f} != expected {expected_order} "
                f"between N={grid_sizes[i]} and N={grid_sizes[i+1]}"
            )
```

### Pattern: Basis Set Convergence (Variational)

```python
def test_variational_convergence():
    """Energy must decrease monotonically as basis size increases."""
    basis_sizes = [10, 20, 40, 80, 160]
    energies = [compute_ground_state(basis_size=N) for N in basis_sizes]

    # Variational principle: more basis functions -> lower energy
    for i in range(len(energies) - 1):
        assert energies[i + 1] <= energies[i] + 1e-12, (
            f"Variational principle violated: "
            f"E(N={basis_sizes[i+1]})={energies[i+1]:.10f} > "
            f"E(N={basis_sizes[i]})={energies[i]:.10f}"
        )

    # Check that the sequence is converging
    final_delta = abs(energies[-1] - energies[-2])
    assert final_delta < 1e-6, (
        f"Not converged: last two energies differ by {final_delta:.2e}"
    )
```

</convergence_tests>

<dimensional_analysis_tests>

## Dimensional Analysis Tests

Verify that computed quantities have the correct physical dimensions and scale correctly with dimensionful parameters.

### Pattern: Scaling Tests

```python
@pytest.mark.parametrize("scale_factor", [0.5, 2.0, 10.0])
def test_energy_scales_correctly(scale_factor):
    """Energy must scale as expected under rescaling of length."""
    # For Coulomb potential: E ~ 1/a_0, so doubling a_0 halves E
    E_original = compute_energy(bohr_radius=1.0)
    E_scaled = compute_energy(bohr_radius=scale_factor)

    expected_ratio = 1.0 / scale_factor  # E ~ 1/a_0
    actual_ratio = E_scaled / E_original

    np.testing.assert_allclose(
        actual_ratio, expected_ratio, rtol=1e-10,
        err_msg=f"Energy does not scale as 1/a_0: ratio={actual_ratio:.6f}, "
                f"expected={expected_ratio:.6f}"
    )
```

### Pattern: Dimensionless Combination Tests

```python
def test_fine_structure_dimensionless():
    """Fine structure constant alpha = e^2/(4*pi*epsilon_0*hbar*c) must be ~1/137."""
    from scipy.constants import e, epsilon_0, hbar, c, pi

    alpha = e**2 / (4 * pi * epsilon_0 * hbar * c)
    np.testing.assert_allclose(alpha, 1 / 137.036, rtol=1e-5,
                               err_msg="Fine structure constant is wrong")

def test_result_is_dimensionless():
    """Arguments of exp, log, sin must be dimensionless."""
    # If computing exp(-beta * E), verify beta * E is dimensionless
    beta = 1.0  # 1/energy
    E = 2.5     # energy
    argument = beta * E
    # This is a structural test -- verify the code doesn't accidentally
    # pass exp(E) instead of exp(beta * E)
    result = np.exp(-argument)
    assert 0 < result <= 1, "Boltzmann factor must be in (0, 1]"
```

</dimensional_analysis_tests>

<anti_patterns>

## Anti-Patterns: What NOT to Test

### Testing implementation instead of physics

```python
# BAD: Tests internal data structure, not physics
def test_hamiltonian_is_sparse():
    H = build_hamiltonian(N=100)
    assert isinstance(H, scipy.sparse.csr_matrix)  # Implementation detail

# GOOD: Tests physical property of the Hamiltonian
def test_hamiltonian_is_hermitian():
    H = build_hamiltonian(N=100)
    diff = H - H.conj().T
    assert scipy.sparse.linalg.norm(diff) < 1e-14
```

### Testing formatting instead of correctness

```python
# BAD: Tests output format
def test_energy_output_format():
    result = compute_energy()
    assert isinstance(result, float)
    assert "energy" in str(result).lower()  # Meaningless

# GOOD: Tests physical constraint
def test_energy_is_bounded_below():
    result = compute_energy()
    assert result > -1e6, "Energy unreasonably negative"
    assert np.isfinite(result), "Energy is not finite"
```

### Over-fitting tests to specific values

```python
# BAD: Brittle test that breaks with any algorithm change
def test_energy_exact_value():
    E = compute_energy(N=100)
    assert E == -7.28923456789012  # Exact float comparison

# GOOD: Test against known result with physical tolerance
def test_energy_matches_literature():
    E = compute_energy(N=100)
    E_literature = -7.2892  # Known to 4 decimal places
    assert abs(E - E_literature) < 0.001  # Physical precision
```

### Testing with trivial inputs only

```python
# BAD: Only tests the trivial case
def test_energy_zero_coupling():
    E = compute_energy(coupling=0.0)
    assert E == 0.0  # Free theory is trivially zero

# GOOD: Tests non-trivial regime AND trivial limit
def test_energy_weak_coupling_expansion():
    E_0 = compute_energy(coupling=0.0)
    assert abs(E_0) < 1e-14  # Free energy is zero

    for g in [0.01, 0.1, 0.5]:
        E_g = compute_energy(coupling=g)
        # First-order correction is known analytically
        expected_correction = -g * analytical_first_order()
        assert abs((E_g - E_0) - expected_correction) < g**2 * 10
```

### Not testing edge cases that matter physically

```python
# BAD: Only tests generic case
def test_spectrum():
    spectrum = compute_spectrum(N=10)
    assert len(spectrum) == 10

# GOOD: Tests physically important edge cases
def test_spectrum_degeneracies():
    """Degeneracies must match symmetry group predictions."""
    spectrum = compute_spectrum(N=10)
    # For SU(2) symmetry, states must come in multiplets of size 2j+1
    degeneracies = count_degeneracies(spectrum, tolerance=1e-10)
    for deg in degeneracies:
        assert deg in [1, 3, 5, 7, 9], (
            f"Degeneracy {deg} is not consistent with SU(2) symmetry"
        )
```

</anti_patterns>

<test_organization>

## Test Suite Organization

```
tests/
  conftest.py              # Shared fixtures (Hamiltonian builders, test parameters)
  test_limiting_cases.py   # All limiting case tests (§1)
  test_symmetries.py       # All symmetry tests (§2)
  test_conservation.py     # All conservation law tests (§3)
  test_regression.py       # Gold value regression tests (§4)
  test_convergence.py      # Convergence tests (§5)
  gold_values.json         # Registry of validated numerical results
```

### Fixture Patterns for Physics

```python
# conftest.py
import pytest
import numpy as np

@pytest.fixture(params=[4, 8, 12, 16])
def system_size(request):
    """Parameterize over system sizes for finite-size scaling."""
    return request.param

@pytest.fixture
def random_state():
    """Reproducible random state for stochastic tests."""
    return np.random.default_rng(seed=42)

@pytest.fixture
def hamiltonian(system_size):
    """Build Hamiltonian for given system size."""
    return build_hamiltonian(N=system_size)
```

### Marking Tests by Category

```python
# Use marks to categorize tests by physics type
pytestmark = pytest.mark.physics

@pytest.mark.slow
def test_large_system_convergence():
    """Convergence test that takes > 1 minute."""
    ...

@pytest.mark.exact
def test_against_exact_solution():
    """Test against known exact analytical result."""
    ...

@pytest.mark.parametric
def test_parameter_sweep():
    """Test across parameter range."""
    ...
```

## See Also

- `references/verification/core/verification-core.md` — analytical verification checks (dimensional analysis, limiting cases, conservation laws) that code tests should encode
- `references/protocols/hypothesis-driven-research.md` — predict-derive-verify cycle; code tests are the computational implementation of stated predictions

</test_organization>

# Verifier Worked Examples

Executable templates and code examples for computational physics verification. The live verifier registry now has 19 checks: 14 universal checks (`5.1`-`5.14`) plus 5 contract-aware checks (`5.15`-`5.19`).

**Template note:** This file is a library of reusable worked examples and support patterns for the universal physics checks. It is not the machine-readable source of truth for current verifier numbering or required scope. Use `gpd.core.verification_checks` and `references/verification/meta/verifier-profile-checks.md` to decide which checks are actually required for a phase.

Load on demand when performing the corresponding verification check.

---

## 5.1 Dimensional Analysis — Executable Template

For each key equation, write out the dimensional analysis explicitly:

```
Equation: E = p^2 / (2m) + V(x)
  Term 1: p^2/(2m) -> [momentum]^2 / [mass] = [mass * velocity]^2 / [mass] = [mass * velocity^2] = [energy] ✓
  Term 2: V(x) -> [energy] ✓ (given V is potential energy)
  LHS: E -> [energy] ✓
  All terms: [energy] -> CONSISTENT
```

If natural units are used (hbar = c = k_B = 1), verify that the counting of dimensions in natural units is internally consistent. For example, in natural units [energy] = [mass] = [length]^{-1} = [time]^{-1}, so verify this holds throughout.

```bash
# Extract equations from artifact (helper — but YOU do the dimensional analysis)
grep -nE "(=|\\\\frac|\\\\int|def )" "$artifact_path" 2>/dev/null | head -20
```

---

## 5.2 Numerical Spot-Check — Executable Template

```bash
python3 -c "
import numpy as np

# Substitute concrete values into the derived expression
# Example: dispersion omega(k) = sqrt(J*S*(1 - cos(k*a)))
J, S, a = 1.0, 0.5, 1.0  # test values

def omega(k): return np.sqrt(J*S*(1 - np.cos(k*a)))

# Test point 1: k=0 (should give omega=0 for acoustic mode)
assert np.isclose(omega(0), 0.0, atol=1e-10), f'FAIL: omega(0) = {omega(0)}, expected 0'
print(f'Test 1 (k=0): omega = {omega(0):.6f}, expected = 0.0 — PASS')

# Test point 2: k=pi/a (zone boundary)
k_max = np.pi/a
expected_max = np.sqrt(2*J*S)  # known result
assert np.isclose(omega(k_max), expected_max, rtol=1e-10), f'FAIL: omega(pi/a) = {omega(k_max)}'
print(f'Test 2 (k=pi/a): omega = {omega(k_max):.6f}, expected = {expected_max:.6f} — PASS')
"
```

**Adapt this template** to the specific expressions found in the research artifacts. The example above uses spin-wave dispersion — replace with your actual expressions.

**For analytical expressions in .py or .tex files:**

1. Read the expression
2. Write a short Python snippet that evaluates it at the test points using the template above
3. Compare with independently calculated values using `np.isclose`

**For numerical code:**

1. Run the code with known inputs where the answer is analytically known
2. Verify the output matches to the expected precision

---

## 5.3 Independent Limiting Case — Executable Template

```bash
python3 -c "
import sympy as sp

k, a, J, S = sp.symbols('k a J S', positive=True)
omega = sp.sqrt(J*S*(1 - sp.cos(k*a)))

# Long-wavelength limit: k*a << 1
long_wave = sp.series(omega, k, 0, n=2).removeO()
print(f'Long-wavelength limit: omega ~ {long_wave}')
# Should give omega ~ k*sqrt(J*S*a^2/2) = v*k (acoustic)

expected = k * sp.sqrt(J*S*a**2/2)
diff = sp.simplify(long_wave - expected)
print(f'Match with v*k: {\"PASS\" if diff == 0 else \"FAIL: diff = \" + str(diff)}')
"
```

**Adapt this template** to the specific expressions found in the research artifacts. The example above uses spin-wave dispersion — replace with your actual expressions.

---

## 5.4 Independent Cross-Check — Executable Template

```bash
# Example: cross-check analytical ground state energy against numerical diagonalization
python3 -c "
import numpy as np

# Analytical result from artifact (e.g., perturbation theory to 2nd order)
def E0_perturbative(g, N):
    # ... expression from artifact ...
    pass

# Independent cross-check: exact diagonalization for small N
def E0_exact(g, N):
    # Build Hamiltonian matrix
    # Diagonalize
    # Return lowest eigenvalue
    pass

# Compare at test points
for g in [0.1, 0.5, 1.0]:
    for N in [2, 4]:
        e_pert = E0_perturbative(g, N)
        e_exact = E0_exact(g, N)
        rel_error = abs(e_pert - e_exact) / abs(e_exact)
        print(f'g={g}, N={N}: perturbative={e_pert:.6f}, exact={e_exact:.6f}, rel_error={rel_error:.2e}')
"
```

**Cross-check strategies by result type:**

| Result type          | Cross-check method                                                            |
| -------------------- | ----------------------------------------------------------------------------- |
| Analytical formula   | Evaluate numerically; compare with series expansion; check special cases      |
| Numerical solution   | Compare with analytical approximation; verify at known benchmark points       |
| Perturbative result  | Check against exact solution for solvable special case; verify order-by-order |
| Variational result   | Verify it is an upper bound; compare with perturbation theory                 |
| Monte Carlo result   | Compare with high-T expansion, mean-field, or exact small-system result       |
| Green's function     | Verify spectral sum rule; check Kramers-Kronig; evaluate at known momenta     |
| Scattering amplitude | Check optical theorem; verify crossing symmetry; check partial-wave unitarity |

---

## 5.6 Symmetry Verification — Executable Template

```bash
# Example: verify rotational invariance of a scattering cross-section
python3 -c "
import numpy as np

# The cross-section from artifact: dsigma/dOmega(theta, phi)
# For a rotationally symmetric potential, it should be independent of phi

def dsigma(theta, phi):
    # ... expression from artifact ...
    pass

# Test phi-independence at several theta values
for theta in [0.3, 0.7, 1.2, 2.5]:
    values = [dsigma(theta, phi) for phi in np.linspace(0, 2*np.pi, 20)]
    variation = np.std(values) / np.mean(values) if np.mean(values) != 0 else 0
    print(f'theta={theta:.1f}: phi-variation = {variation:.2e} (should be ~0)')
"
```

**For specific symmetry types:**

- **Gauge invariance:** If the result depends on a gauge parameter (xi), vary xi and verify physical observables do not change
- **Hermiticity:** For operators/matrices, verify H = H† by checking matrix elements
- **Unitarity:** For S-matrix or time evolution, verify S†S = I or norm preservation
- **Time-reversal:** For time-reversal invariant systems, verify T-symmetry of the Hamiltonian
- **Parity:** Apply parity transformation and verify correct transformation behavior
- **Particle-hole:** In condensed matter, verify particle-hole symmetry if expected

---

## 5.7 Conservation Law — Executable Template

```bash
# Example: verify energy conservation in a time-evolution code
python3 -c "
import numpy as np

# Run the simulation for a short time
# ... load or compute trajectory ...

# Compute energy at multiple time steps
# E_values = [compute_energy(state_t) for state_t in trajectory]
# drift = (E_values[-1] - E_values[0]) / abs(E_values[0])
# print(f'Energy drift over simulation: {drift:.2e} (should be < tolerance)')
"
```

**For analytical derivations:** Verify that the derived equations of motion conserve the expected quantities. This means computing dQ/dt (using the equations of motion) and verifying it equals zero.

**For numerical code:** Run the code and extract the conserved quantity at multiple time steps. Compute the drift.

---

## 5.8 Mathematical Consistency — Executable Template

```bash
# Example: verify a tensor contraction has correct index structure
python3 -c "
import numpy as np

# From artifact: T^{mu nu} = eta^{mu alpha} eta^{nu beta} T_{alpha beta}
# Verify with a test tensor
eta = np.diag([-1, 1, 1, 1])  # Minkowski metric (check sign convention!)
T_lower = np.random.randn(4, 4)

# Compute T^{mu nu} two ways
T_upper_method1 = eta @ T_lower @ eta  # matrix multiplication
T_upper_method2 = np.einsum('ma,nb,ab->mn', eta, eta, T_lower)  # explicit index contraction

print(f'Methods agree: {np.allclose(T_upper_method1, T_upper_method2)}')
# Verify symmetry properties are preserved
print(f'Input symmetric: {np.allclose(T_lower, T_lower.T)}')
print(f'Output symmetric: {np.allclose(T_upper_method1, T_upper_method1.T)}')
"
```

---

## 5.9 Numerical Convergence — Executable Template

```bash
# Example: test convergence of a ground state energy calculation
python3 -c "
import numpy as np
import subprocess, json

# Run at three resolutions
results = {}
for N in [50, 100, 200]:
    # Run the artifact code with different N
    # result = subprocess.run(['python3', artifact_path, '--N', str(N)], capture_output=True, text=True, timeout=60)
    # results[N] = float(result.stdout.strip())
    pass

# Check convergence rate
# For a method with error O(1/N^p):
# p = log(|E_50 - E_100| / |E_100 - E_200|) / log(2)
# Richardson extrapolation: E_exact ≈ (4*E_200 - E_100) / 3  (for p=2)
"
```

**If the code cannot be run directly** (missing dependencies, long runtime):

1. Check if convergence results are stored in output files
2. Read the stored results and verify they show convergence
3. Verify the convergence rate is consistent with the expected order of the method

---

## 5.10 Agreement with Known Results — Executable Template

```bash
# Example: compare computed critical temperature with known value
python3 -c "
import numpy as np

# Known result: 2D Ising model on square lattice
# T_c / J = 2 / ln(1 + sqrt(2)) ≈ 2.26918...
T_c_exact = 2.0 / np.log(1 + np.sqrt(2))

# Computed result from artifact
# T_c_computed = ...  (extract from file)

# rel_error = abs(T_c_computed - T_c_exact) / T_c_exact
# print(f'T_c computed: {T_c_computed:.5f}')
# print(f'T_c exact: {T_c_exact:.5f}')
# print(f'Relative error: {rel_error:.2e}')
# print(f'Within 0.1%: {rel_error < 0.001}')
"
```

---

## 5.11 Physical Plausibility — Executable Template

```bash
# Example: verify spectral function positivity
python3 -c "
import numpy as np

# Load spectral function from artifact
# A_omega = np.loadtxt('spectral_density.dat')
# omega, A = A_omega[:, 0], A_omega[:, 1]

# Check positivity
# negative_values = A[A < -1e-10]  # allow for numerical noise
# if len(negative_values) > 0:
#     print(f'PLAUSIBILITY VIOLATION: Spectral function has {len(negative_values)} negative values')
#     print(f'Most negative: {negative_values.min():.2e}')
# else:
#     print('Spectral function is non-negative: PASS')

# Check sum rule: integral of A(omega) d(omega)/(2*pi) should equal 1
# integral = np.trapz(A, omega) / (2 * np.pi)
# print(f'Sum rule: integral = {integral:.6f} (expected 1.0)')
"
```

---

## 5.12 Statistical Rigor — Executable Template

```bash
# Example: verify Monte Carlo error bars account for autocorrelation
python3 -c "
# Load MC data from artifact
# data = np.loadtxt('mc_measurements.dat')

# Compute naive error bar
# naive_err = np.std(data) / np.sqrt(len(data))

# Compute autocorrelation time
# from scipy.signal import correlate
# acf = correlate(data - np.mean(data), data - np.mean(data), mode='full')
# acf = acf[len(acf)//2:] / acf[len(acf)//2]
# tau_int = 0.5 + np.sum(acf[1:np.argmin(acf > 0)])  # integrated autocorrelation time

# Corrected error bar
# corrected_err = naive_err * np.sqrt(2 * tau_int)
# print(f'Naive error: {naive_err:.4e}')
# print(f'Autocorrelation time: {tau_int:.1f}')
# print(f'Corrected error: {corrected_err:.4e}')
# print(f'Underestimation factor: {corrected_err / naive_err:.1f}x')
"
```

---

## 5.13 Thermodynamic Consistency — Executable Template

```bash
# Example: verify Maxwell relation dS/dV|_T = dP/dT|_V
python3 -c "
import numpy as np

# From artifact: free energy F(T, V) is available
# Compute S = -dF/dT and P = -dF/dV numerically
# Then verify d^2F/dTdV is the same computed both ways

# T_values = np.linspace(...)
# V_values = np.linspace(...)
# F_grid = ...  # F(T, V) on a grid

# dS_dV = numerical derivative of S with respect to V
# dP_dT = numerical derivative of P with respect to T
# max_discrepancy = np.max(np.abs(dS_dV - dP_dT))
# print(f'Maxwell relation discrepancy: {max_discrepancy:.2e}')
"
```

---

## 5.14 Spectral/Analytic Structure — Executable Template

```bash
# Example: verify Kramers-Kronig for a response function
python3 -c "
import numpy as np

# From artifact: chi(omega) = chi_real(omega) + i * chi_imag(omega)
# KK relation: chi_real(omega) = (1/pi) * P.V. integral of chi_imag(omega') / (omega' - omega) domega'

# omega = np.linspace(-10, 10, 1000)
# chi_imag = ...  # from artifact
# chi_real_from_artifact = ...  # from artifact

# Compute KK transform numerically
# chi_real_from_KK = np.zeros_like(omega)
# for i, w in enumerate(omega):
#     integrand = chi_imag / (omega - w)
#     integrand[i] = 0  # principal value
#     chi_real_from_KK[i] = np.trapz(integrand, omega) / np.pi

# discrepancy = np.max(np.abs(chi_real_from_artifact - chi_real_from_KK))
# print(f'KK discrepancy: {discrepancy:.2e}')
"
```

---

## 5.15 Anomalies/Topological Properties — Executable Template

```bash
# Example: verify Berry phase is quantized
python3 -c "
import numpy as np

# From artifact: Berry phase computed for a parameter loop
# berry_phase = ...  # should be integer multiple of pi for time-reversal invariant systems

# Check quantization
# n = berry_phase / np.pi
# print(f'Berry phase / pi = {n:.6f}')
# print(f'Quantized (integer): {abs(n - round(n)) < 0.01}')
"
```

---

## Placeholder Hygiene

Each prompt that flows through the live verifier registry is already subject to automated hygiene checks: `tests/test_command_boilerplate_cleanup.py` enforces zero unresolved placeholder markers in any prompt-style file, and the canonical scripts (`scripts/render_runtime_catalog_table.py` and `scripts/schema_registry_sources.py`) are covered by their smoke tests. Keep this note lean by relying on those guards instead of copying placeholder samples here.

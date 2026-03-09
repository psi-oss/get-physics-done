---
load_when:
  - "code implementation"
  - "numerical implementation"
  - "equation registry"
  - "unit conversion"
  - "symbolic to numerical"
  - "test case derivation"
tier: 2
context_cost: medium
---

# Symbolic-to-Numerical Translation Protocol

The transition from analytical derivation to numerical implementation is where a large class of subtle errors originate. An equation on paper and its implementation in code are not the same object --- they differ in representation, precision, and failure modes. This protocol ensures faithful translation.

## Related Protocols

- See `numerical-computation.md` for convergence testing and error budgets of the numerical code
- See `derivation-discipline.md` for the analytical derivation that produces the equations to implement
- See `integral-evaluation.md` for handling integrals that must be evaluated numerically
- See `variational-methods.md` for translating variational problems into numerical optimization

## Equation Registry

Before writing any numerical code, create an explicit registry of every equation to be implemented:

```markdown
## Equation Registry

| ID   | LaTeX                                                 | Code function                       | Variables mapping                                             | Status      |
| ---- | ----------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------- | ----------- |
| eq:1 | $H = -\frac{\hbar^2}{2m}\nabla^2 + V(r)$              | `hamiltonian(r, psi)`               | $\hbar$ -> `hbar`, $m$ -> `mass`, $r$ -> `r_grid`             | Implemented |
| eq:2 | $G^R(\omega) = \frac{1}{\omega - \epsilon_k + i\eta}$ | `green_retarded(omega, eps_k, eta)` | $\omega$ -> `omega`, $\epsilon_k$ -> `eps_k`, $\eta$ -> `eta` | Tested      |
```

Every equation that appears in a derivation file and will be evaluated numerically MUST appear in this registry before coding begins. The mapping between mathematical symbols and code variable names must be unambiguous.

## Unit Translation Table

Map physical units to code units explicitly. Document ALL unit conversions:

```markdown
## Unit Translation

| Physical quantity | Symbol | Physical unit | Code unit     | Conversion factor                 |
| ----------------- | ------ | ------------- | ------------- | --------------------------------- |
| Energy            | E      | eV            | dimensionless | E_code = E_phys / E_scale         |
| Length            | r      | Angstrom      | dimensionless | r_code = r_phys / a_0             |
| Time              | t      | fs            | dimensionless | t_code = t_phys \* E_scale / hbar |
| Temperature       | T      | K             | dimensionless | T_code = k_B \* T / E_scale       |
```

If working in natural units in the derivation but SI or CGS in code (or vice versa), every conversion must be documented. A missing factor of hbar or c is a unit translation error, not a physics error.

## Test Case Derivation

For every implemented equation, derive at minimum 2-3 test cases analytically BEFORE running the code:

1. **Trivial case:** Set most parameters to zero or one, compute the result by hand. Example: free particle (V=0), single site (N=1), zero coupling (g=0).
2. **Known exact case:** Use a case where the answer is known exactly. Example: harmonic oscillator, hydrogen atom, Ising model on 2 sites.
3. **Asymptotic case:** Use a parameter regime where an asymptotic expansion is valid. Example: high-temperature limit, weak-coupling limit, large-N limit.

Write these test cases as assertions in the code:

```python
# Test case 1: Free particle (V=0), expect E = hbar^2 k^2 / (2m)
assert abs(compute_energy(k=1.0, V=0, m=1.0) - 0.5) < 1e-10, "Free particle test failed"

# Test case 2: Harmonic oscillator, expect E_0 = 0.5 * hbar * omega
assert abs(compute_ground_state(omega=1.0) - 0.5) < 1e-8, "Harmonic oscillator test failed"
```

## Dimensional Analysis of Code

Verify that every line of numerical code preserves dimensional consistency:

1. **Annotate dimensions in comments** for non-trivial expressions:

   ```python
   # [energy] = [hbar^2] / ([mass] * [length^2])
   kinetic = -hbar**2 / (2 * mass) * laplacian(psi)  # [energy * wavefunction]
   ```

2. **Check at interfaces:** When a function returns a value, state its dimensions. When a function takes arguments, state their expected dimensions.

3. **Verify with scaling test:** Multiply all inputs by a scale factor and verify the output scales correctly. If energy should scale as [mass * length^2 / time^2], doubling mass should double energy (all else equal).

## Limiting Case Validation

After implementation, run the code at parameter values where the analytical result is known:

```
| Limiting case        | Parameters              | Expected         | Computed         | Relative error |
| -------------------- | ----------------------- | ---------------- | ---------------- | -------------- |
| Free particle        | V=0, m=1, k=1          | E = 0.5          | 0.500000         | < 1e-12        |
| Classical limit      | hbar -> 0 (hbar=1e-6)  | E = V(x_min)     | V(x_min) + O(hbar) | 2e-6         |
| High-T limit         | T=1e4, J=1             | C_V = Nk_B       | 0.9998 * Nk_B    | 2e-4           |
```

If any limiting case fails beyond the expected numerical tolerance: the implementation has a bug. Do not proceed to production runs until all limiting cases pass.

## Worked Example: Implementing the 1D Schrödinger Equation — Unit Conversion Trap

**Problem:** Implement a finite-difference solver for the 1D time-independent Schrödinger equation with a harmonic potential, and compute the ground state energy. Demonstrate how a missing unit conversion factor produces a result that is dimensionally correct but numerically wrong by orders of magnitude.

### Step 1: Equation Registry

| ID   | LaTeX | Code function | Variables |
|------|-------|---------------|-----------|
| eq:1 | −(ℏ²/2m) d²ψ/dx² + (1/2)mω²x²ψ = Eψ | `solve_harmonic(m, omega, N, L)` | ℏ→`hbar`, m→`mass`, ω→`omega`, x→`x_grid` |

### Step 2: Unit Translation

Working in SI internally, reporting in natural units:

| Quantity | Symbol | SI unit | Code variable | Natural units |
|----------|--------|---------|---------------|---------------|
| Mass | m | kg | `mass` | m_e = 9.109e-31 kg |
| Length | x | m | `x_grid` | a_0 = 5.292e-11 m |
| Energy | E | J | `energy` | Hartree = 4.360e-18 J |
| ℏ | ℏ | J·s | `hbar` | 1.055e-34 J·s |
| Frequency | ω | s⁻¹ | `omega` | ω in rad/s |

### Step 3: Implementation

Finite-difference Hamiltonian on N grid points with spacing dx:

```python
# Kinetic energy: -hbar^2 / (2*mass) * d^2/dx^2
# [hbar^2/mass] = J^2 s^2 / kg = J * m^2  -> [energy * length^2]
T_coeff = -hbar**2 / (2 * mass * dx**2)   # [energy]

# Potential: (1/2) * mass * omega^2 * x^2
# [mass * omega^2 * x^2] = kg * s^{-2} * m^2 = J  -> [energy]
V = 0.5 * mass * omega**2 * x_grid**2      # [energy]
```

### Step 4: The Unit Conversion Error

**Correct implementation (SI throughout):**
For an electron (m = m_e) in a trap with ℏω = 1 eV (ω = 1.519e15 rad/s):
- E_0 = (1/2)ℏω = 0.5 eV = 8.01e-20 J

**Wrong implementation (common error — mixed units):**
If someone uses m = 1 (atomic units) but ℏ = 1.055e-34 (SI) and ω in eV (not rad/s):

```python
# WRONG: mixed units
mass = 1.0           # atomic units (m_e = 1)
hbar = 1.055e-34     # SI (J·s)
omega = 1.0          # "1 eV" but actually dimensionless
E_0 = 0.5 * hbar * omega  # = 5.27e-35 J ≈ 3.3e-16 eV  [WRONG by 15 orders of magnitude!]
```

The result is dimensionally an energy (Joules), so a naive dimensional check passes. But the value is catastrophically wrong because SI ℏ was multiplied by a dimensionless "frequency."

**Correct in atomic units:**
```python
# CORRECT: consistent atomic units (hbar = m_e = e = 1)
mass = 1.0
hbar = 1.0
omega = 0.03675      # 1 eV in atomic units (1 eV / 27.21 eV/Hartree)
E_0 = 0.5 * hbar * omega  # = 0.01837 Hartree = 0.500 eV  [CORRECT]
```

### Step 5: Test Case Validation

| Test case | Parameters | Expected E_0 | Computed E_0 | Relative error |
|-----------|-----------|--------------|--------------|----------------|
| ℏω = 1 Hartree | m=1, ω=1 (a.u.) | 0.5 Hartree | 0.50000 | < 1e-8 |
| ℏω = 1 eV | m=1, ω=0.03675 (a.u.) | 0.01837 Ha | 0.01837 | < 1e-6 |
| Classical limit (ω→0) | m=1, ω=1e-6 | ~5e-7 Ha | 5.00e-7 | < 1e-4 |
| High frequency | m=1, ω=100 | 50 Ha | 49.998 | 4e-5 |

### Verification

1. **Known eigenvalues.** E_n = (n + 1/2)ℏω for all n. Verify the first 5 eigenvalues agree with this formula to within the finite-difference truncation error (O(dx²)).

2. **Grid convergence.** Halve dx and verify E_0 changes by a factor of ~4 (second-order scheme). If it changes by a factor of ~2, the scheme is first-order (wrong). If it doesn't change, the grid was already converged.

3. **Wavefunction normalization.** ∫|ψ|² dx = 1. Check this numerically with the trapezoidal rule. Deviation > 1e-6 indicates a normalization bug.

4. **Parity symmetry.** The ground state ψ_0(x) is even: ψ_0(-x) = ψ_0(x). The first excited state ψ_1(x) is odd. If parity is violated, the grid is asymmetric or the boundary conditions are wrong.

5. **Unit consistency cross-check.** Compute E_0 in two different unit systems (SI and atomic units) and convert to the same output unit. They must agree to machine precision. Disagreement immediately reveals the unit conversion error.

## Worked Example: Numerically Unstable Fermi-Dirac Integral — Analytically Correct but Computationally Catastrophic

**Problem:** Implement the Fermi-Dirac integral F_n(eta) = integral_0^inf x^n / (exp(x - eta) + 1) dx for the chemical potential eta = 50 (deep degenerate limit). Demonstrate that the textbook formula is analytically correct but produces catastrophic numerical errors, and show the correct implementation. This targets the LLM error class of implementing mathematically valid expressions that suffer from floating-point overflow, underflow, or catastrophic cancellation.

### Step 1: Equation Registry

| ID | LaTeX | Code function | Variables |
|----|-------|---------------|-----------|
| eq:1 | F_n(eta) = integral_0^inf x^n / (exp(x - eta) + 1) dx | `fermi_dirac(n, eta)` | n -> `n`, eta -> `eta` |

### Step 2: The Naive Implementation (WRONG)

Direct numerical integration of the textbook formula:

```python
import numpy as np
from scipy import integrate

def fermi_dirac_naive(n, eta):
    def integrand(x):
        return x**n / (np.exp(x - eta) + 1)
    result, _ = integrate.quad(integrand, 0, np.inf)
    return result
```

**At eta = 50:**
```
fermi_dirac_naive(1, 50)  # RuntimeWarning: overflow encountered in exp
                           # Returns: nan or inf
```

The problem: when x < eta = 50, the exponent (x - eta) is large and negative, so exp(x - eta) ~ 0, and the integrand is well-behaved (~x^n). But when x > eta, the exponent is positive and exp(x - eta) grows rapidly. The integrand is small but nonzero, and the numerical integration must resolve the sharp transition near x = eta.

The catastrophic failure: `np.exp(50)` = 5.18e21, which is fine. But `np.exp(700)` overflows to inf in IEEE 754 double precision (max representable ~ 1.8e308, and exp(709.78) is the limit). The integrand for x near 0 computes exp(0 - 50) = exp(-50) = 1.93e-22, so the denominator is 1 + 1.93e-22 ~ 1.0, giving x^n / 1.0 = x^n. Fine. But the adaptive integrator may evaluate the integrand at large x where exp(x - 50) overflows.

### Step 3: The Correct Implementation

**Rewrite the integrand to avoid overflow.** Use the identity:
```
1 / (exp(x - eta) + 1) = exp(eta - x) / (exp(eta - x) + 1)    when x > eta
                        = 1 / (1 + exp(x - eta))                when x < eta
```

Implementation using the log-sum-exp trick:

```python
def fermi_dirac_stable(n, eta):
    def integrand(x):
        if x < eta:
            # exp(x - eta) is small, denominator ~ 1
            return x**n / (1.0 + np.exp(x - eta))
        else:
            # Rewrite: x^n * exp(eta - x) / (1 + exp(eta - x))
            return x**n * np.exp(eta - x) / (1.0 + np.exp(eta - x))
    result, _ = integrate.quad(integrand, 0, np.inf)
    return result
```

Even better, use scipy's built-in (which handles this internally):
```python
from scipy.special import fdtri  # or mpmath.fp.polylog
```

### Step 4: Results Comparison

| eta | F_1(eta) naive | F_1(eta) stable | F_1(eta) exact (Sommerfeld) |
|-----|---------------|-----------------|----------------------------|
| 1.0 | 1.8063 | 1.8063 | 1.8063 |
| 10.0 | 52.36 | 52.36 | 52.36 |
| 50.0 | nan | 1252.1 | 1250.0 + pi^2/6 = 1251.6 |
| 100.0 | nan | 5016.4 | 5000.0 + pi^2/6 = 5001.6 |
| 500.0 | nan | 125016.4 | 125000 + pi^2/6 |

The naive implementation fails completely for eta > ~700 (where exp(eta) overflows) and gives inaccurate results for eta > ~30 (where the integrator struggles with the sharp Fermi edge).

### Step 5: Asymptotic Cross-Check (Sommerfeld Expansion)

For large eta (degenerate limit), the Sommerfeld expansion gives:
```
F_n(eta) = eta^{n+1}/(n+1) + n*pi^2/6 * eta^{n-1} + O(eta^{n-3})
```

For n = 1, eta = 50:
```
F_1(50) = 50^2/2 + pi^2/6 = 1250 + 1.645 = 1251.645
```

The stable numerical result (1252.1) agrees to 0.04% — the difference is the O(eta^{-1}) correction term.

### Verification

1. **Known limit (eta -> -inf).** In the classical limit: F_n(eta) -> Gamma(n+1) * exp(eta). For n = 1, eta = -10: F_1(-10) = 1 * exp(-10) = 4.54e-5. Both implementations should agree here (no overflow/underflow issues). This validates the basic integral setup.

2. **Known limit (eta = 0).** F_n(0) = (1 - 2^{-n}) * Gamma(n+1) * zeta(n+1). For n = 1: F_1(0) = (1/2) * 1 * pi^2/6 = pi^2/12 = 0.8225. Verify to 4 significant figures.

3. **Monotonicity.** F_n(eta) is strictly increasing in eta for all n >= 0. If the numerical result decreases for increasing eta, there is a bug.

4. **Recursion relation.** dF_n/d eta = n * F_{n-1}(eta). Verify numerically: [F_n(eta + h) - F_n(eta - h)] / (2h) = n * F_{n-1}(eta) to O(h^2). This catches sign errors and missing factors of n.

5. **No overflow/underflow warnings.** The correct implementation must run without any floating-point warnings for all eta in [-100, 1000]. If any warning appears, the implementation is not robust.

**The typical LLM error** implements the textbook integral directly, tests it at eta = 1 (where it works), and declares it correct. The failure only appears at large eta (degenerate metals, white dwarf interiors, neutron stars), which is exactly the physically important regime. A unit test at eta = 1 does not catch this bug.

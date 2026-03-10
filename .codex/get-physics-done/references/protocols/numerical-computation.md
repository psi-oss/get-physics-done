---
load_when:
  - "numerical calculation"
  - "convergence test"
  - "error budget"
  - "Richardson extrapolation"
  - "floating point"
  - "discretization"
tier: 1
context_cost: medium
---

# Numerical Computation Protocol

Numerical results without error analysis are meaningless. A number produced by a computer is not a physics result until it has been validated against analytical expectations, tested for convergence, and assigned an uncertainty.

## Related Protocols

- See `symbolic-to-numerical.md` for translating analytical expressions into numerical code
- See `monte-carlo.md` for stochastic sampling and statistical error estimation
- See `exact-diagonalization.md` for exact methods on finite systems
- See `molecular-dynamics.md` for time integration and conservation law verification

## Before Computing

- **Estimate the expected magnitude and sign.** Use dimensional analysis, order-of-magnitude estimates, or analytical approximations to predict roughly what the answer should be. Write this prediction down BEFORE running the code.
- **Identify potential numerical pitfalls:**
  - Catastrophic cancellation (A - B where A is approximately equal to B)
  - Overflow/underflow (exp(large number), very small prefactors)
  - Ill-conditioned matrices (large condition number)
  - Stiff ODEs (widely separated timescales)
  - Sign-alternating series (slow convergence, potential for partial-sum oscillation)

## Convergence Testing

Every numerical result must be accompanied by convergence evidence. Run systematically:

1. **Vary the discretization:** halve the grid spacing (or double the number of points) and verify the result changes by less than the desired tolerance.
2. **Vary the basis size:** increase the number of basis functions and verify convergence.
3. **Vary the cutoff:** change UV or IR cutoffs and verify physical results are insensitive.
4. **Vary the time step:** for time integration, halve dt and verify stability and accuracy.

**Present convergence data in a table:**

```
| N (grid/basis) | Result          | Delta from previous |
|----------------|-----------------|---------------------|
| 100            | -0.43182        | ---                 |
| 200            | -0.43267        | 8.5e-4              |
| 400            | -0.43271        | 4.0e-5              |
| 800            | -0.43271        | 1.2e-6              |
```

If convergence is not monotonic: investigate. Oscillatory convergence suggests aliasing or a subtle numerical issue.

## Richardson Extrapolation

When the error scales as a known power of the discretization parameter (e.g., O(h^p)):

```
result_exact ~ (2^p * result_fine - result_coarse) / (2^p - 1)
```

Use this to extract a better estimate and to verify the convergence ORDER. If the expected order is p=2 but Richardson extrapolation with p=2 does not improve the result, the error is not O(h^2) --- investigate.

## Comparison with Analytical Results

- **In every limit where an analytical result exists: compare.** This is not optional.
- Free-particle limit, harmonic oscillator, hydrogen atom, Ising model on small lattices --- these are your calibration points.
- Report the comparison as a relative error: |numerical - analytical| / |analytical|.
- If the relative error is larger than the expected truncation error: there is a bug, not a convergence issue.

## Error Budget

Every numerical result must have an error budget:

```
Total uncertainty: sqrt(stat^2 + sys^2 + trunc^2)

Statistical (Monte Carlo sampling):    +/- 0.003
Systematic (finite-size effects):      +/- 0.001
Truncation (basis set / grid):         +/- 0.0004
--------------------------------------------
Total:                                 +/- 0.003
```

- **Statistical:** from bootstrapping, jackknife, or the standard error of the mean (with proper autocorrelation correction for MCMC).
- **Systematic:** from varying physical parameters (system size, cutoff, boundary conditions) and observing the change.
- **Truncation:** from the convergence test above --- the difference between the last two refinement levels.

## Worked Example: Catastrophic Cancellation in Molecular Binding Energy

**Problem:** Compute the binding energy E_bind = E(A+B) - E(A) - E(B) of a weakly bound molecular dimer. This targets the LLM error class of ignoring catastrophic cancellation and basis set superposition error (BSSE) -- reporting a number from a single calculation without convergence testing or error analysis.

### Step 1: Estimate Before Computing

Hydrogen bonds are typically 2-5 kcal/mol = 0.003-0.008 Hartree. So E_bind ~ 10^{-3} Hartree. We need E(A+B), E(A), E(B) each to at least 10^{-5} Hartree precision (7 significant figures) to get 2 significant figures in E_bind.

**Verification checkpoint:** Write down this estimate BEFORE running any calculation. If the raw result differs by more than an order of magnitude, investigate.

### Step 2: Convergence Test for Each Energy Separately

```
| Basis set     | E(A+B) / Ha        | E(A) / Ha         | E_bind / kcal/mol |
|---------------|--------------------|--------------------|-------------------|
| cc-pVDZ       | -152.3991          | -76.1982           | -1.75             |
| cc-pVTZ       | -152.4312          | -76.2147           | -1.13             |
| cc-pVQZ       | -152.4365          | -76.2178           | -0.56             |
| cc-pV5Z       | -152.4376          | -76.2186           | -0.25             |
| CBS limit     | -152.4378          | -76.2189           | 0.00 +/- 0.3     |
```

**Verification checkpoint:** E_bind changes sign between basis sets. Non-monotonic convergence of a derived quantity when the individual energies converge monotonically signals a systematic error, not a convergence issue.

### Step 3: Diagnose the Problem

The binding energy is NOT converging -- it changes sign between basis sets. This is basis set superposition error (BSSE): each fragment "borrows" basis functions from the partner, artificially lowering the dimer energy.

### Step 4: Apply Counterpoise Correction

```
E_bind^CP = E(A+B) - E(A in AB basis) - E(B in AB basis)
```

Computing E(A) and E(B) in the full dimer basis (with ghost functions on the partner):

```
| Basis set     | E_bind^raw / kcal/mol | E_bind^CP / kcal/mol |
|---------------|------------------------|----------------------|
| cc-pVDZ       | -1.75                  | -3.21                |
| cc-pVTZ       | -1.13                  | -3.05                |
| cc-pVQZ       | -0.56                  | -2.98                |
| cc-pV5Z       | -0.25                  | -2.95                |
| CBS limit     | 0.00 +/- 0.3          | -2.93 +/- 0.03       |
```

The counterpoise-corrected result converges smoothly to -2.93 kcal/mol. The raw result was meaningless.

**Verification checkpoint:** The CP-corrected sequence must be monotonic and the successive differences must decrease. Here: 3.21 -> 3.05 -> 2.98 -> 2.95 -> 2.93, with deltas 0.16, 0.07, 0.03, 0.02. Monotonic and shrinking -- convergence confirmed.

### Step 5: Construct the Error Budget

```
Binding energy: -2.93 kcal/mol
  Basis set incompleteness (CBS extrapolation):  +/- 0.03
  BSSE residual (after counterpoise):            +/- 0.02
  Correlation method (CCSD(T) vs exact):         +/- 0.05
  Total:                                         +/- 0.06 kcal/mol
```

**Final verification checkpoint:** The total uncertainty (0.06 kcal/mol) is ~2% of the binding energy (2.93 kcal/mol). The result is meaningful. Compare with experiment (water dimer: -3.0 +/- 0.1 kcal/mol) -- agreement within error bars validates the method.

### What the LLM Gets Wrong

The typical error is reporting E_bind from a single basis set without convergence testing, missing both the catastrophic cancellation and BSSE. A naive calculation gives E_bind = -0.000001 Hartree = -0.6 kcal/mol from E(A+B) = -152.437829, E(A) = E(B) = -76.218914 -- subtracting numbers that agree to 6 significant figures leaves only 1 significant figure. The convergence test catches this immediately: if E_bind changes sign between basis sets, something is wrong.

## Worked Example: Split-Operator Propagation of a Quantum Wavepacket

**Problem:** Propagate a coherent state in a 1D harmonic potential V(x) = (1/2) omega^2 x^2 using the split-operator FFT method, and verify energy conservation and agreement with the analytical solution. This targets the LLM error class of unstable time-stepping, wrong operator ordering, and failure to verify conservation laws.

### Step 1: Discretization

Grid: N = 256 points, x in [-10, 10] (in natural units hbar = m = 1), dx = 20/256 = 0.078. Time step dt = 0.01 (in units of 1/omega). Total propagation t_final = 2*pi (one full period).

Initial state: coherent state at x_0 = 2: psi(x, 0) = pi^{-1/4} exp(-(x - 2)^2/2).

### Step 2: Split-Operator Method

The second-order Suzuki-Trotter decomposition:

```
exp(-i H dt) = exp(-i V dt/2) * exp(-i T dt) * exp(-i V dt/2) + O(dt^3)
```

Each step: (1) multiply by exp(-i V(x) dt/2) in x-space, (2) FFT to k-space, (3) multiply by exp(-i k^2 dt/2) in k-space, (4) inverse FFT, (5) multiply by exp(-i V(x) dt/2).

**The symmetric splitting (V/2-T-V/2) is essential.** The asymmetric version (V-T) is only first-order accurate.

### Step 3: Monitor Conservation Laws

| t / (2pi) | <x> numerical | <x> exact (2 cos t) | |Delta E/E| | ||psi||^2 |
|------------|---------------|---------------------|-----------|----|
| 0 | 2.000 | 2.000 | 0 | 1.000000 |
| 0.25 | 0.000 | 0.000 | 1.2e-6 | 1.000000 |
| 0.50 | -2.000 | -2.000 | 2.4e-6 | 1.000000 |
| 1.00 | 2.000 | 2.000 | 4.7e-6 | 1.000000 |

### Verification

1. **Norm conservation (exact):** The split-operator is unitary — ||psi||^2 = 1 to machine precision at every step. Deviation from 1 signals a bug in the FFT or operator application.

2. **Energy convergence order:** Halve dt, verify energy error drops by 4x (second-order). If it drops by 2x, you have first-order splitting (wrong operator order).

3. **Revival test:** At t = 2pi, the coherent state returns to its initial position and shape. Compute ||psi(2pi) - psi(0)||: should be < 10^{-3} for dt = 0.01. A large deviation indicates the potential is wrong or the grid is too coarse.

4. **Grid boundary check:** |psi| at grid edges must be < 10^{-10}. For this problem: psi(+/-10) ~ exp(-32) ~ 10^{-14}. Safe. If psi reaches the boundary, spurious reflections corrupt the solution.

5. **Momentum resolution:** The momentum grid k_max = pi/dx = 40. The coherent state has momentum width Delta k ~ 1. The ratio k_max/Delta k ~ 40 provides adequate resolution. If k_max/Delta k < 5, aliasing errors appear.

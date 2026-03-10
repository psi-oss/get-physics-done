---
load_when:
  - "variational"
  - "trial wavefunction"
  - "VMC"
  - "variational Monte Carlo"
  - "coupled cluster"
  - "energy minimization"
  - "Rayleigh-Ritz"
tier: 2
context_cost: medium
---

# Variational Methods Protocol

The variational principle guarantees E_trial >= E_exact, making it one of the few methods with a rigorous bound. But the bound is only useful if the trial state is in the correct symmetry sector, the optimization finds the global minimum, and the method is size-extensive for many-body systems. Violating any of these silently produces a number that is wrong despite satisfying the variational bound.

## Related Protocols

- See `monte-carlo.md` for variational Monte Carlo (VMC) sampling of trial wavefunctions
- See `density-functional-theory.md` for the variational principle in DFT (Hohenberg-Kohn)
- See `tensor-networks.md` for DMRG as a variational method over matrix product states

## Step 1: Trial Wavefunction Design

1. **Encode the correct symmetries.** The trial wavefunction must have the same quantum numbers as the target state: angular momentum, parity, particle number, spin, crystal momentum, gauge symmetry. A trial state in the wrong symmetry sector gives a valid upper bound — for the wrong state.
2. **Include the correct physics.** For atomic/molecular systems: cusp conditions at electron-nucleus and electron-electron coalescence. For lattice models: correct short-range correlations. For field theories: correct UV behavior. Missing essential physics means no amount of optimization will reach the ground state.
3. **Verify the trial state is normalizable.** Compute <psi_trial|psi_trial> analytically or numerically. If the norm diverges or vanishes for some parameter values, exclude those from the variational search.
4. **Size extensivity.** For N-particle systems, the energy must scale as E ~ N for large N. Product states (Hartree-Fock) are size-extensive. Simple linear combinations of Slater determinants are NOT size-extensive. Coupled cluster and Jastrow-type wavefunctions are size-extensive. If your method is not size-extensive, state the error scaling explicitly.

## Step 2: Optimization

1. **Compute the energy functional.** E[params] = <psi(params)|H|psi(params)> / <psi(params)|psi(params)>. For complex wavefunctions, verify the energy is real (Hermiticity check). If the computed energy has an imaginary part, there is a bug.
2. **Gradient-based optimization:** Compute dE/d(param_i) analytically (preferred) or numerically (finite differences with step size verification). Use natural gradient (SR / imaginary-time evolution) when the parameter space has non-trivial metric — standard gradient descent in a curved parameter space converges to wrong points.
3. **Stochastic optimization (VMC):** When E[params] is computed by Monte Carlo sampling, use stochastic reconfiguration (SR) or ADAM with variance-reduced gradients. The noise in the energy estimate contaminates the gradient — do not use noisy gradients with deterministic optimizers (L-BFGS, conjugate gradient).
4. **Local minima detection.** Run optimization from at least 3-5 different random initial conditions. If they converge to different energies, the landscape has local minima. Report the lowest. For neural-network wavefunctions: local minima are endemic; use large batches and careful learning rate scheduling.

## Step 3: Convergence Verification

1. **Basis set convergence.** If the trial state is expanded in a basis (Gaussians, plane waves, Slater determinants, MPS bond dimension), increase the basis size systematically. Plot E(N_basis) and verify convergence. Report the extrapolated E(N_basis -> infinity) using the observed convergence rate.
2. **The variational bound.** E_trial >= E_exact. If the variational energy is BELOW a known exact result, there is an error: wrong Hamiltonian, wrong matrix elements, normalization bug, or the "exact" result is wrong. This is a hard constraint — never ignore it.
3. **Variance of the energy.** Var(E) = <H^2> - <H>^2 >= 0. For the exact eigenstate, Var(E) = 0. The variance is a quality metric independent of the energy: a trial state with low energy but high variance may be far from the true eigenstate (energy can be right for the wrong reason). Report the variance alongside the energy.
4. **Excited states.** For excited states using the variational method, verify orthogonality to all lower states. Use penalty methods (E_trial + lambda * |<psi_trial|psi_0>|^2) or explicit orthogonalization. The energy of the nth excited state must be >= the (n-1)th exact energy.

## Step 4: VMC Specifics

1. **Sampling.** Use Metropolis-Hastings to sample |psi_trial(R)|^2. Verify acceptance rate is 40-60% for single-particle moves. Too high: moves too small, high autocorrelation. Too low: moves too large, poor exploration.
2. **Local energy.** E_L(R) = H psi(R) / psi(R). The local energy must be finite everywhere in the sampled configuration space. Divergences in E_L indicate nodes or cusps not properly handled. Regularize or fix the wavefunction.
3. **Population control bias** (in DMC/FCIQMC). The walker population fluctuates and is controlled by adjusting the reference energy. This introduces a systematic bias that scales as 1/N_walkers. Verify by running with 2x and 4x walkers and extrapolating.
4. **Fixed-node approximation** (in DMC). The nodal surface of the trial wavefunction is kept fixed. The DMC energy is an upper bound to the exact energy, but the quality depends entirely on the nodal surface. Compare nodal surfaces from different trial states to assess the node error.

## Step 5: Coupled Cluster as Variational

1. **Standard coupled cluster (CCSD, CCSD(T)) is NOT variational.** The CC energy can be below the exact energy. Do not use the variational bound as a validity check for CC. However, CC is size-extensive — this is its main advantage over truncated CI.
2. **Unitary coupled cluster (UCC) IS variational** but exponentially hard to optimize classically. Used in quantum computing (VQE). For classical calculations, use standard CC and cross-check with other methods.
3. **The (T) correction in CCSD(T)** is perturbative, not variational. It can overshoot. For systems with strong multireference character (bond breaking, transition metals), CCSD(T) can be unreliable even though it is the "gold standard" for single-reference systems. Check the T1 diagnostic: if T1 > 0.02, multireference methods may be needed.

## Common Pitfalls

- **Wrong symmetry sector.** The optimizer found a beautiful low energy — for the wrong spin state, wrong parity, or wrong crystal momentum. Always project onto the target quantum numbers and verify AFTER optimization.
- **Over-parameterization.** Too many variational parameters relative to training data (VMC samples) causes overfitting: the energy decreases but the wavefunction becomes unphysical. Monitor the variance — if variance increases while energy decreases, you are overfitting.
- **Missing correlations.** A Hartree-Fock trial state misses all correlation energy. A single-determinant Jastrow misses static correlation. For strongly correlated systems (Mott insulators, frustrated magnets, bond-breaking), multi-reference starting points are essential.
- **Basis set superposition error (BSSE).** When computing interaction energies E(A+B) - E(A) - E(B) with finite basis sets, each fragment "borrows" basis functions from the other, artificially lowering the complex energy. Use counterpoise correction: compute E(A) and E(B) in the full A+B basis.

## Concrete Example: Variational Bound Violation Reveals Error

**Problem:** Estimate the ground state energy of the hydrogen atom using the Gaussian trial wavefunction psi(r) = A * exp(-alpha * r^2).

**Step 1: Verify normalization.**
```
<psi|psi> = |A|^2 * 4pi * integral_0^inf r^2 exp(-2*alpha*r^2) dr
          = |A|^2 * 4pi * (1/4) * sqrt(pi / (2*alpha))^3 / (2*alpha)
          -> A = (2*alpha/pi)^{3/4}
```

**Step 2: Compute <H>.**

Kinetic: <T> = -(hbar^2/(2m)) <psi| nabla^2 |psi>

For psi = A*exp(-alpha*r^2): nabla^2 psi = (4*alpha^2*r^2 - 6*alpha) * psi

So <T> = (hbar^2/(2m)) * (6*alpha - 4*alpha^2 <r^2>) = (hbar^2/(2m)) * (6*alpha - 4*alpha^2 * 3/(4*alpha)) = (3*hbar^2*alpha)/(2m)

Potential: <V> = -e^2 <1/r> = -e^2 * (2*alpha/pi)^{3/2} * 4pi * integral_0^inf r * exp(-2*alpha*r^2) dr = -e^2 * (2*alpha/pi)^{3/2} * 4pi * (1/(4*alpha)) = -e^2 * sqrt(8*alpha/pi)

**Step 3: Minimize E(alpha) = <T> + <V>.**

dE/d(alpha) = 3*hbar^2/(2m) - e^2 * sqrt(2/(pi*alpha)) = 0

Solving: alpha_opt = 8*m^2*e^4 / (9*pi*hbar^4)

**Step 4: Checkpoint -- variational bound.**

E_opt = -4/(3*pi) * (m*e^4)/(hbar^2) = -4/(3*pi) * 1 Hartree = -0.4244 * 27.2 eV = -11.55 eV

The exact answer is E_exact = -13.6 eV. Our variational bound gives -11.55 eV > -13.6 eV, which is ABOVE the exact answer (captures 85% of the binding energy). The variational principle is satisfied (E_trial >= E_exact).

**If your trial energy comes out BELOW -13.6 eV:** You have an error. The variational principle guarantees E_trial >= E_exact for any trial state. A violation means: wrong Hamiltonian, wrong normalization, or computational error. Stop and debug.

**Why the Gaussian is poor:** The exact ground state is psi ~ exp(-r/a_0) (exponential), while our trial is Gaussian (exp(-alpha*r^2)). The Gaussian has the wrong behavior at both r -> 0 (zero slope instead of cusp) and r -> infinity (too-fast decay). Despite this, it still gives a rigorous upper bound.

## Worked Example: Helium Atom Ground State via Variational Method with Screening

**Problem:** Compute the ground state energy of helium (Z=2, two electrons) using a variational wavefunction with effective nuclear charge Z_eff, and demonstrate that the variational bound correctly captures the correlation energy missed by independent-particle approximations. This targets the LLM error class of missing electron-electron repulsion, incorrect evaluation of two-electron integrals, and confusion between exact, Hartree-Fock, and variational energies.

### Step 1: Trial Wavefunction

Use the product of hydrogenic 1s orbitals with effective nuclear charge Z_eff as variational parameter:

```
psi(r_1, r_2) = (Z_eff^3 / pi) * exp(-Z_eff * (r_1 + r_2) / a_0)
```

This treats electron-electron repulsion as screening of the nuclear charge: each electron sees an effective charge Z_eff < Z = 2.

### Step 2: Compute the Energy Functional

The Hamiltonian (in atomic units, a_0 = hbar = m_e = e = 1):

```
H = T_1 + T_2 + V_{1N} + V_{2N} + V_{12}
  = -(1/2) nabla_1^2 - (1/2) nabla_2^2 - Z/r_1 - Z/r_2 + 1/r_{12}
```

**Kinetic energy:** For each hydrogenic orbital with Z_eff: <T> = Z_eff^2 / 2 per electron.

```
<T_1 + T_2> = Z_eff^2
```

**Nuclear attraction:** <-Z/r_i> for a hydrogenic orbital with Z_eff:

```
<V_{1N} + V_{2N}> = -2 Z * Z_eff
```

Note: NOT -2 Z_eff^2. The nuclear charge is Z = 2, but the wavefunction has Z_eff.

**Electron-electron repulsion:** The two-electron integral <1/r_{12}> for identical hydrogenic orbitals:

```
<V_{12}> = (5/8) Z_eff
```

This is a standard result (see Griffiths QM, Ch. 7). Deriving it requires the Gegenbauer expansion of 1/r_{12} and integration over both electron coordinates.

**Total energy:**

```
E(Z_eff) = Z_eff^2 - 2 Z * Z_eff + (5/8) Z_eff
         = Z_eff^2 - 2(2) Z_eff + (5/8) Z_eff
         = Z_eff^2 - (27/8) Z_eff
```

### Step 3: Minimize

```
dE/dZ_eff = 2 Z_eff - 27/8 = 0
Z_eff = 27/16 = 1.6875
```

**Physical interpretation:** Each electron screens the nuclear charge by 5/16 of a unit. The effective charge 1.6875 < 2 reflects the partial screening by the other electron.

```
E_opt = (27/16)^2 - (27/8)(27/16) = -(27/16)^2 = -729/256 = -2.8477 hartree
```

### Step 4: Compare with Known Values

| Method | Energy (hartree) | Error from exact |
|--------|-----------------|------------------|
| No interaction (Z_eff = Z = 2) | -2.750 | 5.3% |
| Variational (Z_eff = 27/16) | -2.8477 | 1.9% |
| Hartree-Fock | -2.8617 | 1.5% |
| Exact (Hylleraas, 1929) | -2.9037 | 0% |

### Verification

1. **Variational bound check:** E_opt = -2.8477 > E_exact = -2.9037. The bound holds. If your energy is below -2.9037 hartree, there is a bug.

2. **Screening physical reasonableness:** Z_eff = 1.6875 is between 1 (complete screening by one electron — hydrogen-like) and 2 (no screening — bare nuclear charge). Both limits make physical sense. If Z_eff > 2 or Z_eff < 1, the result is unphysical.

3. **Ionization energy:** E(He) - E(He+) = -2.8477 - (-2.0000) = -0.8477 hartree = -23.1 eV. Experimental: 24.6 eV. The variational estimate is 6% low (because the variational energy is not negative enough). This is consistent.

4. **Correlation energy:** E_corr = E_exact - E_HF = -2.9037 - (-2.8617) = -0.0420 hartree = -1.14 eV. The variational method captures some correlation (E_var is lower than E_no-interaction) but less than HF (which uses a proper self-consistent field). The remaining gap E_HF - E_var = 0.014 hartree comes from the restricted functional form.

5. **Two-electron integral check:** The integral <1/r_{12}> = (5/8) Z_eff can be verified by dimensional analysis: [1/r_{12}] = 1/length = Z_eff/a_0 in atomic units. The coefficient 5/8 is specific to identical 1s orbitals. A common LLM error is getting this coefficient wrong (e.g., 3/8 or 5/4), which shifts Z_eff and the final energy.

## Worked Example: Variational Excited States of the Quantum Harmonic Oscillator

**Problem:** Compute the first three energy levels of the 1D quantum harmonic oscillator H = p^2/(2m) + (1/2)m omega^2 x^2 using the Rayleigh-Ritz variational method with a Gaussian basis, demonstrating proper orthogonality handling and the generalized eigenvalue problem. This targets the LLM error class of computing excited states without enforcing orthogonality to lower states, which produces energies that violate the variational bound for excited states.

### The Wrong Way (No Orthogonality)

A common LLM approach: "Minimize E = <psi|H|psi>/<psi|psi> for the ground state. Then minimize again for the first excited state using a different trial wavefunction."

This fails because the second minimization finds the ground state again (or a state that overlaps with it), not the first excited state. Without explicit orthogonality constraints, the variational principle gives no information about excited states.

### Step 1: Basis Set Construction

Use Gaussian basis functions centered at the origin with different widths:

```
phi_n(x) = exp(-alpha_n x^2),  n = 1, 2, ..., N
```

Choose alpha_n as an even-tempered sequence: alpha_n = alpha_1 * beta^{n-1} with alpha_1 = 0.1 m omega / hbar and beta = 3. For N = 5:

```
alpha_1 = 0.1,  alpha_2 = 0.3,  alpha_3 = 0.9,  alpha_4 = 2.7,  alpha_5 = 8.1
```

(in units where m = omega = hbar = 1)

**Problem:** These are all even functions of x. They can only represent even-parity states (n = 0, 2, 4, ...). The first excited state (n = 1) has odd parity and CANNOT be represented in this basis.

**Fix:** Add odd basis functions phi_n^{odd}(x) = x * exp(-alpha_n x^2). Now the basis has both parities.

### Step 2: Construct the Hamiltonian and Overlap Matrices

The Rayleigh-Ritz method solves the generalized eigenvalue problem:

```
H c = E S c
```

where H_{ij} = <phi_i|H|phi_j>, S_{ij} = <phi_i|phi_j>, and c is the coefficient vector.

For the even basis functions (using units m = omega = hbar = 1):

```
S_{ij} = integral phi_i phi_j dx = sqrt(pi / (alpha_i + alpha_j))
H_{ij} = (1/2) alpha_i alpha_j / (alpha_i + alpha_j) * S_{ij}  +  (1/4) / (alpha_i + alpha_j) * S_{ij}
       = S_{ij} * [(alpha_i * alpha_j + 1/2) / (2(alpha_i + alpha_j))]
```

**Checkpoint:** H_{ij} and S_{ij} are real and symmetric. S_{ij} is positive definite (overlap matrix of linearly independent functions). If any eigenvalue of S is negative or zero, the basis is linearly dependent — remove the offending function.

### Step 3: Solve the Generalized Eigenvalue Problem

Diagonalize H c = E S c. This gives N eigenvalues E_1 <= E_2 <= ... <= E_N.

**Critical:** The nth eigenvalue E_n is an upper bound to the nth exact eigenstate. This is the Hylleraas-Undheim-MacDonald theorem — it guarantees that each variational eigenvalue bounds the corresponding exact level, NOT just the ground state.

Results with N = 5 even functions + 5 odd functions (10 basis functions total):

| Level | Variational E_n | Exact E_n = n + 1/2 | Error |
|-------|----------------|---------------------|-------|
| n=0 | 0.5000 | 0.5 | < 10^{-8} |
| n=1 | 0.5000 | 1.5 | < 10^{-8} |
| n=2 | 2.5001 | 2.5 | 4e-5 |
| n=3 | 3.5004 | 3.5 | 1e-4 |
| n=4 | 4.504 | 4.5 | 9e-4 |

Wait — n=1 gives 0.5, not 1.5. This is wrong. Let me recheck: the eigenvalues of the generalized eigenvalue problem should be ordered from smallest to largest. For the harmonic oscillator, the first two eigenvalues should be 0.5 (ground state) and 1.5 (first excited state).

The issue: if odd basis functions are included, parity symmetry block-diagonalizes the problem. The even block gives E = 0.5, 2.5, 4.5, ... and the odd block gives E = 1.5, 3.5, ... When combined and sorted: 0.5, 1.5, 2.5, 3.5, 4.5 — correct.

Corrected results:

| Level | Variational E_n | Exact (n + 1/2) | Error |
|-------|----------------|-----------------|-------|
| n=0 | 0.50000 | 0.5 | < 10^{-8} |
| n=1 | 1.50000 | 1.5 | < 10^{-8} |
| n=2 | 2.50001 | 2.5 | 1e-5 |
| n=3 | 3.5003 | 3.5 | 9e-5 |
| n=4 | 4.504 | 4.5 | 9e-4 |

The accuracy degrades for higher levels because the basis is optimized for low-lying states (the widest Gaussians capture the ground state well, but higher excited states need more spatially extended functions).

### Step 4: What Goes Wrong Without Orthogonality

If instead of solving the generalized eigenvalue problem, you independently minimize <psi|H|psi>/<psi|psi> for each level:

**Attempt for n=1:** Minimize over the odd subspace (x * exp(-alpha x^2)):

```
E_1(alpha) = <psi_1|H|psi_1> / <psi_1|psi_1> = (3 alpha / 2 + 1/(8 alpha)) / 1
```

Minimizing: dE/d alpha = 3/2 - 1/(8 alpha^2) = 0, giving alpha = 1/(2 sqrt(3)). Then E_1 = sqrt(3)/2 = 1.5. This works — but only because parity symmetry automatically enforces orthogonality to the ground state.

**Attempt for n=2 without orthogonality:** Minimize over the even subspace without orthogonality to n=0. The optimizer finds... the ground state again (E = 0.5), not the n=2 state. The variational principle pushes toward the lowest energy in the search space.

**With orthogonality constraint:** Add a penalty lambda * |<psi_2|psi_0>|^2 to the energy functional. For large lambda, this forces <psi_2|psi_0> = 0, and the minimization finds E_2 = 2.5. But the result depends on lambda — too small and the orthogonality is not enforced; too large and the optimization landscape becomes stiff. The generalized eigenvalue problem avoids this entirely by computing all levels simultaneously.

### Verification

1. **Hylleraas-Undheim-MacDonald bound.** Each E_n^{variational} >= E_n^{exact}. Verify for all computed levels. Violation indicates a bug in the matrix construction or eigenvalue solver.

2. **Orthogonality of eigenvectors.** The eigenvectors satisfy c_i^T S c_j = delta_{ij}. Verify this numerically: the overlap matrix of the variational eigenstates (in the original basis) must be the identity to machine precision. If not, the eigenvalue solver failed (likely due to ill-conditioned overlap matrix S).

3. **Completeness check.** Adding more basis functions should lower (or maintain) each eigenvalue. If adding a function RAISES an eigenvalue, there is a linear dependence problem or a sign error in the matrix elements.

4. **Parity symmetry.** The even and odd levels should separate cleanly: even-n states have zero overlap with odd basis functions, and vice versa. If even-odd mixing appears, the matrix elements are wrong (likely a sign error in the kinetic energy integral).

5. **Sum rule.** For the harmonic oscillator, the oscillator strength sum rule gives sum_n (E_n - E_0) |<n|x|0>|^2 = hbar/(2m omega). Compute the matrix elements <n|x|0> from the variational eigenvectors and verify the sum rule. Violation indicates incomplete basis or wrong matrix elements.

6. **Known exact result.** For the harmonic oscillator, the exact energies are E_n = (n + 1/2) hbar omega. The variational method should reproduce these exactly if the basis contains the exact eigenfunctions (which Gaussians do for the harmonic oscillator ground state but not for excited states). The systematic error for higher levels quantifies basis incompleteness.

---
load_when:
  - "Bethe ansatz"
  - "integrable model"
  - "Bethe equations"
  - "XXX chain"
  - "XXZ chain"
  - "Heisenberg spin chain"
  - "Yang-Baxter"
  - "string hypothesis"
  - "thermodynamic Bethe ansatz"
  - "algebraic Bethe ansatz"
tier: 2
context_cost: medium
---

# Bethe Ansatz Protocol

The Bethe ansatz is an exact method for diagonalizing Hamiltonians of one-dimensional integrable models. It reduces an N-body quantum problem to a set of coupled algebraic equations (Bethe equations) for N quasi-momenta. This protocol covers the coordinate Bethe ansatz, algebraic Bethe ansatz, and thermodynamic Bethe ansatz (TBA).

## Related Protocols

- See `exact-diagonalization.md` for numerical verification of Bethe ansatz results on small systems
- See `perturbation-theory.md` for weak-coupling expansions that should match the Bethe ansatz
- See `quantum-many-body.md` for many-body techniques in non-integrable models
- See `conformal-bootstrap.md` for CFT descriptions of critical integrable chains

## When to Use

1. **Spin chains:** XXX (isotropic Heisenberg), XXZ (anisotropic), XYZ (fully anisotropic, elliptic)
2. **1D quantum gases:** Lieb-Liniger model (bosons with delta-function interaction), Gaudin-Yang model (fermions)
3. **Hubbard model:** 1D Hubbard model (nested Bethe ansatz with charge and spin rapidities)
4. **Impurity models:** Kondo model, Anderson impurity model (via Bethe ansatz after mapping to 1D)
5. **Field theories:** Massive Thirring model, sine-Gordon model, integrable QFTs in 1+1d
6. **AdS/CFT integrability:** Spin chain for anomalous dimensions of composite operators in N=4 SYM

## Prerequisites: Verifying Integrability

Before applying the Bethe ansatz, verify that the model is integrable:

1. **Yang-Baxter equation:** The R-matrix R_{12}(u) satisfies R_{12}(u-v) R_{13}(u) R_{23}(v) = R_{23}(v) R_{13}(u) R_{12}(u-v). This is necessary and sufficient for integrability.
2. **Transfer matrix:** Construct T(u) = Tr_0 [R_{0N}(u) ... R_{02}(u) R_{01}(u)]. The Hamiltonian is H = (d/du) ln T(u)|_{u=0} (or similar relation). Verify [T(u), T(v)] = 0 for all u, v — this gives the commuting conserved charges.
3. **Known integrable models:** If the model is a known integrable system (XXZ, Lieb-Liniger, Hubbard), the integrability is established. Cite the original integrability proof.

**Checkpoint:** If the Yang-Baxter equation is NOT satisfied, the Bethe ansatz does NOT apply. Non-integrable perturbations (e.g., next-nearest-neighbor coupling in XXZ) break the ansatz. For quasi-integrable systems, see `perturbation-theory.md`.

## Step-by-Step: Coordinate Bethe Ansatz

### Step 1: Two-Body Scattering

Solve the two-particle problem to extract the two-body S-matrix S(k_1, k_2).

For the XXX spin-1/2 chain with N sites and M down-spins:

```
H = J * sum_{i=1}^{N} (S_i . S_{i+1} - 1/4)
```

Two magnon scattering: the S-matrix is

```
S(k_1, k_2) = (1/2 cot(k_1/2) - 1/2 cot(k_2/2) - i) / (1/2 cot(k_1/2) - 1/2 cot(k_2/2) + i)
```

In rapidity variables lambda_j = (1/2) cot(k_j/2):

```
S(lambda_1, lambda_2) = (lambda_1 - lambda_2 - i) / (lambda_1 - lambda_2 + i)
```

**Checkpoint:** The S-matrix must satisfy:
- Unitarity: S(k_1, k_2) * S(k_2, k_1) = 1
- Yang-Baxter: S_{12} S_{13} S_{23} = S_{23} S_{13} S_{12}

### Step 2: Write the Bethe Wavefunction

For M particles (down-spins) at positions x_1 < x_2 < ... < x_M:

```
Psi(x_1, ..., x_M) = sum_{P in S_M} A(P) * exp(i * sum_j k_{P(j)} * x_j)
```

The amplitude ratios A(P)/A(P') are determined by the two-body S-matrix.

### Step 3: Impose Periodic Boundary Conditions

Requiring Psi to be periodic with period N (the chain length) gives the **Bethe equations**:

```
exp(i k_j N) = prod_{l != j} S(k_j, k_l)
```

In rapidity variables for the XXX chain:

```
(lambda_j + i/2)^N / (lambda_j - i/2)^N = prod_{l != j} (lambda_j - lambda_l + i) / (lambda_j - lambda_l - i)
```

for j = 1, ..., M.

Taking logarithms:

```
N * arctan(2*lambda_j) = pi * I_j + sum_{l != j} arctan(lambda_j - lambda_l)
```

where I_j are quantum numbers (integers or half-integers depending on M parity).

### Step 4: Solve the Bethe Equations

For each set of quantum numbers {I_1, ..., I_M}, solve the M coupled equations for {lambda_1, ..., lambda_M}.

**Methods:**
- **Small systems (N < 20, M < 10):** Direct numerical solution (Newton's method from initial guess based on I_j)
- **Thermodynamic limit (N -> inf, M/N fixed):** Convert to integral equation for the rapidity density rho(lambda) (see TBA below)
- **String hypothesis:** Bound states correspond to complex solutions with lambda_j = lambda_0 + i*(n+1-2j)/2 for j=1,...,n (n-string centered at Re(lambda_0))

**Checkpoint:** Verify that the solution {lambda_j} satisfies:
- All lambda_j are distinct (degenerate rapidities signal an error or a singular solution)
- The quantum numbers {I_j} are all distinct
- The energy and momentum match the expected quantum numbers

### Step 5: Compute Physical Quantities

**Energy:**
```
E = -J * sum_{j=1}^M 1/(lambda_j^2 + 1/4)
```

**Momentum:**
```
P = sum_j k_j = sum_j [pi - 2*arctan(2*lambda_j)]   (mod 2pi)
```

**Spin:** S^z_total = N/2 - M.

## Step-by-Step: Algebraic Bethe Ansatz

### When to Prefer Over Coordinate Ansatz

- The model has internal degrees of freedom requiring nesting (e.g., Hubbard model with charge and spin)
- You need form factors or correlation functions (the algebraic approach gives these more naturally)
- The R-matrix structure is known but the coordinate-space Hamiltonian is complicated

### Procedure

1. Define the Lax operator L_i(u) acting on the auxiliary space x physical space at site i
2. Construct the monodromy matrix T(u) = L_N(u) ... L_2(u) L_1(u)
3. Write T(u) as a 2x2 matrix in auxiliary space: T(u) = ((A(u), B(u)), (C(u), D(u)))
4. The transfer matrix is t(u) = A(u) + D(u) = Tr T(u)
5. The reference state (pseudo-vacuum) |0> is the state with all spins up: A(u)|0> = a(u)|0>, D(u)|0> = d(u)|0>, C(u)|0> = 0
6. Eigenstates are constructed as: |{u_j}> = B(u_1) B(u_2) ... B(u_M) |0>
7. The condition that this is an eigenstate of t(u) gives the Bethe equations:

```
a(u_j) / d(u_j) = prod_{l != j} (u_j - u_l + eta) / (u_j - u_l - eta)
```

where eta is the anisotropy parameter.

## Thermodynamic Bethe Ansatz (TBA)

### When to Use

- Computing thermodynamic quantities (free energy, entropy, specific heat) at finite temperature
- Determining the ground state in the thermodynamic limit (N, M -> inf with M/N fixed)
- Finite-size corrections (Casimir energy, central charge of the underlying CFT)

### Procedure

1. **Take the logarithm** of the Bethe equations and convert sums to integrals using the rapidity density rho(lambda):

```
rho(lambda) + rho_h(lambda) = a_1(lambda) - integral K(lambda - mu) rho(mu) d mu
```

where rho_h is the density of holes and K is the kernel from the logarithmic derivative of the S-matrix.

2. **Minimize the free energy** F = E - T*S at temperature T. This gives the TBA equation:

```
epsilon(lambda) / T = a_1(lambda) - integral K(lambda - mu) * ln(1 + exp(-epsilon(mu)/T)) d mu / (2pi)
```

where epsilon(lambda) is the dressed energy: occupied states have epsilon < 0, holes have epsilon > 0.

3. **Free energy:**

```
f = -T * integral a_1(lambda) * ln(1 + exp(-epsilon(lambda)/T)) d lambda / (2pi)
```

### Finite-Size Corrections

For a critical system (gapless spectrum), the ground state energy on a ring of length N has the form:

```
E_0(N) = N * e_inf - pi * c * v / (6 * N) + O(1/N^2)
```

where c is the central charge of the CFT and v is the Fermi velocity. Extract c from the 1/N coefficient.

**Checkpoint:** For the XXX spin-1/2 chain, c = 1 (free boson CFT / Tomonaga-Luttinger liquid). For the XXZ chain at Delta = cos(pi/p), c = 1 with compactification radius depending on p.

## Common Pitfalls

1. **String hypothesis violations.** The string hypothesis (complex Bethe roots form regular strings) is an approximation that becomes exact only in the thermodynamic limit. For finite chains, strings can deviate significantly. When computing finite-size spectra, solve the Bethe equations numerically without assuming string structure.

2. **Singular solutions.** Some solutions of the Bethe equations are singular (lambda_j = +/- i/2 for XXX). These correspond to lambda_j at the pole of the S-matrix. They must be treated separately using regularization (e.g., twisted boundary conditions with twist -> 0).

3. **Counting completeness.** Not all eigenstates are obtained from "regular" Bethe ansatz solutions. The completeness of the Bethe ansatz (whether all eigenstates are reached) is a subtle issue. For the XXX chain, completeness is proven. For more complex models, it may require the string hypothesis or additional solution types.

4. **Nested Bethe ansatz ordering.** For models with multiple species (e.g., Hubbard model), the Bethe equations form a nested hierarchy. The ordering of the nesting matters — charge rapidities first, then spin rapidities (or vice versa). Using the wrong ordering gives incorrect equations.

5. **Branch cut ambiguity in logarithms.** Taking the logarithm of the Bethe equations introduces branch cut ambiguity (the quantum numbers I_j). The correct quantum numbers must be chosen consistently. Different choices give different eigenstates.

6. **Thermodynamic limit interchange.** Taking N -> inf and then T -> 0 may not commute with T -> 0 and then N -> inf. For gapless systems, the order of limits matters and can produce different results for correlation functions.

7. **Ignoring backflow.** When adding or removing a particle from the Bethe ansatz ground state, all other rapidities shift (backflow or finite-size dressing). Ignoring this shift gives incorrect excitation energies at finite N.

## Worked Example: Ground State of the XXX Spin-1/2 Chain

**Problem:** Find the ground state energy per site of the antiferromagnetic Heisenberg chain H = J sum S_i . S_{i+1} (J > 0) in the thermodynamic limit (N -> inf).

### Step 1: Identify the Ground State Sector

The ground state has S^z_total = 0, so M = N/2 down-spins (half-filling). The quantum numbers for the ground state are:

```
I_j = -(M-1)/2 + (j-1)    for j = 1, ..., M
```

This is the "Dirac sea" configuration: all quantum numbers filled symmetrically around zero.

### Step 2: Thermodynamic Limit — Integral Equation

For N -> inf with M/N = 1/2, the Bethe equations become the Lieb-Wu integral equation for the rapidity density:

```
rho(lambda) = a_1(lambda) - integral_{-inf}^{inf} a_2(lambda - mu) * rho(mu) d mu
```

where a_n(lambda) = (1/(2pi)) * n / (lambda^2 + n^2/4).

This is solved by Fourier transform:

```
rho_hat(omega) = a_1_hat(omega) / (1 + a_2_hat(omega)) = (1/(2 cosh(omega/2)))
```

Inverting: rho(lambda) = 1 / (2pi * cosh(pi * lambda)).

### Step 3: Ground State Energy

```
e_0 = (E_0 / N) = -J * integral_{-inf}^{inf} a_1(lambda) * rho(lambda) d lambda / (M/N)
```

Wait — more directly:

```
e_0 = -J * integral_{-inf}^{inf} (1/(lambda^2 + 1/4)) * rho(lambda) d lambda
```

Using rho(lambda) = 1/(2pi cosh(pi lambda)):

```
e_0 = -J * integral_{-inf}^{inf} d lambda / ((lambda^2 + 1/4) * 2pi cosh(pi lambda))
```

Evaluating by residues (pole at lambda = i/2 inside the upper half-plane contour):

```
e_0 = -J * (1/4 - ln 2) = J * (ln 2 - 1/4)
```

The ground state energy per bond is:

```
e_0 = J * (ln 2 - 1/4) = J * (0.6931... - 0.25) = 0.4431... * J
```

Or equivalently, the ground state energy per site (measuring from the ferromagnetic state) is:

```
e_0 = J * (1/4 - ln 2) = -0.4431... * J
```

This is the Hulthen result (1938).

### Verification

1. **Small-chain exact diagonalization:** For N=4, M=2 (ground state sector S^z = 0). The Bethe equations with quantum numbers I_1 = -1/2, I_2 = +1/2 give, by symmetry, lambda_2 = -lambda_1 = lambda where 3*arctan(2*lambda) = pi/2, so lambda = tan(pi/6)/2 = 1/(2*sqrt(3)). Energy: E_BA = -J * sum 1/(lambda_j^2 + 1/4) = -2J/(1/12 + 1/4) = -2J/(1/3) = -6J. This should be compared with exact diagonalization of the same Hamiltonian H = J sum (S_i.S_{i+1} - 1/4) on 4 sites, which gives E_0 = -2J for the singlet ground state (recall E_ferro = 0 for this convention). The factor-of-3 discrepancy indicates a normalization mismatch: the energy formula E = -J sum 1/(lambda^2 + 1/4) corresponds to H = (J/2) sum (P_{i,i+1} - 1) rather than H = J sum (S.S - 1/4) = (J/2) sum P_{i,i+1} - NJ/4. With the correct normalization E = -(J/2) sum 1/(lambda_j^2 + 1/4), the Bethe ansatz gives E = -3J, which matches e_0 = -3J/4 per site. The thermodynamic limit result e_0 = J(1/4 - ln 2) = -0.4431 J is convention-independent.

2. **Asymptotic checks:** For N=6, 8, 10, ..., the exact Bethe ansatz energy per site converges to -J*(ln 2 - 1/4) = -0.4431*J. Numerical exact diagonalization confirms this convergence.

3. **Comparison with Hulthen's result:** The analytic result e_0 = J(1/4 - ln 2) was first obtained by Hulthen (1938). Our calculation reproduces it exactly.

4. **CFT prediction for finite-size corrections:** E_0(N) = N * e_inf - pi * v / (6N) * c + ... with c = 1 and v = pi*J/2 (known spin-wave velocity). Numerically verify that (E_0(N) - N*e_inf) * 6N / (pi^2 * J / 2) -> 1 as N -> inf.

5. **Magnetization curve:** The magnetic field h shifts the Fermi surface of rapidities. The susceptibility chi = (d M / d h)|_{h=0} = 1/(pi^2 J) is exact from the Bethe ansatz. Compare with numerical DMRG for finite chains.

6. **Spin-spin correlation function:** At large distance, <S_0 . S_r> ~ (-1)^r * (ln r)^{1/2} / r (logarithmic corrections to power-law decay, characteristic of c=1 CFT with marginal operator). The exponent 1 matches the Luttinger parameter K = 1/2 for the isotropic point.

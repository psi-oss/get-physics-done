---
load_when:
  - "random matrix"
  - "Wigner-Dyson"
  - "level spacing"
  - "GOE"
  - "GUE"
  - "GSE"
  - "Tracy-Widom"
  - "eigenvalue statistics"
  - "quantum chaos"
  - "Wigner semicircle"
tier: 2
context_cost: medium
---

# Random Matrix Theory Protocol

Random Matrix Theory (RMT) studies the statistical properties of eigenvalues and eigenvectors of large random matrices. It provides universal predictions for spectral statistics in quantum chaotic systems, disordered conductors, nuclear spectra, and many other contexts. This protocol covers the three classical Wigner-Dyson ensembles (GOE, GUE, GSE), level spacing statistics, universal correlations, and connections to quantum chaos.

## Related Protocols

- See `exact-diagonalization.md` for numerically computing spectra to compare with RMT predictions
- See `statistical-inference.md` for fitting RMT distributions to data
- See `symmetry-analysis.md` for identifying the symmetry class (which determines the ensemble)
- See `stochastic-processes.md` for Dyson Brownian motion and dynamical RMT

## When to Use

1. **Quantum chaos:** Classically chaotic systems have quantum spectra described by RMT (BGS conjecture)
2. **Nuclear physics:** Nuclear level spacings follow Wigner-Dyson statistics (Wigner's original motivation)
3. **Disordered systems:** Anderson localization transitions, mesoscopic conductance fluctuations, universal conductance fluctuations
4. **Number theory:** Zeros of the Riemann zeta function follow GUE statistics (Montgomery-Odlyzko conjecture)
5. **Quantum chromodynamics:** Dirac operator eigenvalues in QCD follow chiral RMT (chGUE, chGOE, chGSE)
6. **Wireless communications:** MIMO channel capacity, signal-to-noise ratio distributions
7. **Financial mathematics:** Correlation matrices of stock returns, Marcenko-Pastur distribution

## The Three Classical Ensembles

### Classification by Symmetry

The ensemble is determined by the symmetry class of the Hamiltonian:

| Ensemble | Symmetry | Matrix Type | Dyson Index beta | Physical Example |
|----------|----------|-------------|-----------------|-----------------|
| **GOE** (Gaussian Orthogonal) | Time-reversal + integer spin | Real symmetric | beta = 1 | Nuclei, billiards without magnetic field |
| **GUE** (Gaussian Unitary) | No time-reversal symmetry | Complex Hermitian | beta = 2 | Systems in magnetic field, QCD at finite chemical potential |
| **GSE** (Gaussian Symplectic) | Time-reversal + half-integer spin | Quaternion self-dual | beta = 4 | Spin-orbit coupled systems without magnetic field |

**Checkpoint:** Before applying RMT, identify the symmetry class:
1. Is time-reversal symmetry present? (No magnetic field, no complex phases in Hamiltonian)
2. If yes, what is T^2? T^2 = +1 (integer spin, GOE) or T^2 = -1 (half-integer spin, GSE)
3. If no time-reversal: GUE

### Joint Eigenvalue Distribution

For an N x N random matrix from the Gaussian ensemble with Dyson index beta:

```
P(lambda_1, ..., lambda_N) = C_N * prod_{i<j} |lambda_i - lambda_j|^beta * exp(-beta * N / 4 * sum_i lambda_i^2)
```

The |lambda_i - lambda_j|^beta factor is the **eigenvalue repulsion** — the hallmark of RMT. Larger beta means stronger repulsion.

## Key Results and How to Use Them

### Wigner Semicircle Law (Bulk Density of States)

For large N, the eigenvalue density converges to the semicircle:

```
rho(lambda) = (2 / (pi * R^2)) * sqrt(R^2 - lambda^2)    for |lambda| < R
```

where R = 2 * sqrt(N/beta) for the standard Gaussian ensemble.

**Use:** Compare the empirical eigenvalue density of your matrix with the semicircle. Deviations indicate non-random structure in the matrix (signal, localization, or non-Gaussian tails in the matrix element distribution).

### Level Spacing Distribution (Nearest-Neighbor)

**Unfold the spectrum first:** Transform eigenvalues so that the mean spacing is 1:
```
s_i = rho_local * (lambda_{i+1} - lambda_i)
```
where rho_local is the local density of states.

**Wigner surmise (excellent approximation for 2x2 matrices, good for all N):**

```
P_GOE(s) = (pi/2) * s * exp(-pi * s^2 / 4)        (beta = 1)
P_GUE(s) = (32/pi^2) * s^2 * exp(-4 * s^2 / pi)   (beta = 2)
P_GSE(s) = (2^18 / (3^6 * pi^3)) * s^4 * exp(-64 * s^2 / (9*pi))  (beta = 4)
```

**Key feature:** P(s) ~ s^beta for small s. This is **level repulsion** — the probability of two eigenvalues being close vanishes as their spacing to the power beta.

**Contrast with Poisson (integrable/localized):**
```
P_Poisson(s) = exp(-s)
```
No level repulsion: P(0) = 1. Neighboring levels cluster.

**Use:** Compute the nearest-neighbor spacing distribution from your spectrum (after unfolding). Compare with Wigner-Dyson (chaotic) vs Poisson (integrable/localized). This is the primary diagnostic for quantum chaos.

### Number Variance and Spectral Rigidity

**Number variance:** Sigma^2(L) = <(n(L) - L)^2> where n(L) is the number of unfolded eigenvalues in an interval of length L.

- Poisson: Sigma^2(L) = L (shot noise)
- GOE: Sigma^2(L) ~ (2/(pi^2)) * [ln(2*pi*L) + gamma + 1 - pi^2/8] for L >> 1
- GUE: Sigma^2(L) ~ (1/(pi^2)) * [ln(2*pi*L) + gamma + 1] for L >> 1

**Spectral rigidity (Delta_3 statistic):** Average least-squares deviation of the staircase function from a best-fit line over an interval of length L.

**Use:** The number variance and Delta_3 are more sensitive than the spacing distribution for distinguishing RMT from Poisson, especially for intermediate cases (partial chaos, mixed phase space).

### Tracy-Widom Distribution (Extreme Eigenvalues)

The distribution of the largest eigenvalue lambda_max, properly centered and scaled, converges to the Tracy-Widom distribution:

```
P(lambda_max < (N^{1/2} + s * N^{-1/6}) * sqrt(2/beta)) -> F_beta(s)
```

- F_1(s): Tracy-Widom GOE distribution
- F_2(s): Tracy-Widom GUE distribution (also appears in many combinatorial problems)
- F_4(s): Tracy-Widom GSE distribution

These are NON-Gaussian. The left tail decays as exp(-|s|^3/12) and the right tail as exp(-2*s^{3/2}/3) for F_2.

**Use:** Compare the distribution of extreme eigenvalues with Tracy-Widom. Deviations (heavier tails, different scaling exponent) indicate non-universality or finite-size effects.

## Step-by-Step: Applying RMT to a Physical System

### Step 1: Obtain the Spectrum

Compute or measure a set of energy eigenvalues {E_1, E_2, ..., E_N} (or other spectral data: Dirac eigenvalues, scattering matrix eigenphases, etc.).

**Requirements:**
- The spectrum must be in a SINGLE symmetry sector. Mix different angular momentum, parity, or other quantum numbers and RMT does NOT apply (the spectrum is a superposition of independent RMT sequences).
- N should be large enough for meaningful statistics (N > 50 for spacing distribution, N > 200 for higher-order correlations).

### Step 2: Unfold the Spectrum

Separate the smooth (average) density of states from the fluctuations:

1. Compute the cumulative staircase function: N(E) = #{E_i < E}
2. Fit a smooth function N_smooth(E) to N(E) (polynomial fit, Weyl formula, or Thomas-Fermi approximation)
3. Unfolded eigenvalues: x_i = N_smooth(E_i)

After unfolding, the mean spacing is 1 everywhere.

**Checkpoint:** The unfolding procedure must NOT introduce artificial correlations. Verify by checking that the average spacing of the unfolded spectrum is 1.0 and the variance of spacings matches the expected value (0.273 for GOE, 0.178 for GUE).

### Step 3: Compute the Nearest-Neighbor Spacing Distribution

```
s_i = x_{i+1} - x_i
```

Histogram P(s) and compare with Wigner-Dyson and Poisson.

**Quantitative comparison:**
- Mean spacing: <s> = 1 (by construction after unfolding)
- Spacing variance: var(s) = 4/pi - 1 = 0.273 (GOE), 4 - 128/(9pi^2) = 0.178 (GUE)
- Brody parameter q: fit P(s) = (q+1) * beta_param * s^q * exp(-beta_param * s^{q+1}). q = 0 is Poisson, q = 1 is GOE. Intermediate q indicates partial chaos (mixed phase space).

### Step 4: Compute Higher-Order Statistics

- **Number variance** Sigma^2(L) for L from 0.1 to 10 (or larger)
- **Spectral rigidity** Delta_3(L)
- **Two-point correlation function** R_2(s) = 1 - Y_2(s) where Y_2 is the cluster function
- **Ratio of consecutive spacings** r_i = min(s_i, s_{i+1}) / max(s_i, s_{i+1}): does not require unfolding

### Step 5: Interpret Results

| Observation | Interpretation |
|------------|---------------|
| P(s) matches Wigner-Dyson | System is quantum chaotic (classical limit is chaotic) |
| P(s) matches Poisson | System is integrable or localized |
| P(s) intermediate (0 < q < 1) | Mixed phase space: regular islands + chaotic sea |
| P(s) is GOE for some sectors, GUE for others | Magnetic field breaks time-reversal in some sectors |
| Spectral rigidity saturates at large L | System has a finite Heisenberg time; short-range chaos with long-range regularity |

## Common Pitfalls

1. **Mixing symmetry sectors.** The most common error in applying RMT. If eigenvalues from different symmetry classes (different parity, angular momentum, etc.) are combined, the result looks like a superposition of independent Poisson sequences — even for a chaotic system. Always separate the spectrum by all good quantum numbers.

2. **Unfolding artifacts.** Over-fitting or under-fitting the smooth density of states introduces spurious correlations or destroys real ones. Use the Weyl formula (semiclassical density of states) when available. When using polynomial unfolding, test sensitivity to polynomial degree.

3. **Small sample size.** With N < 50 eigenvalues, the spacing distribution is noisy and the Brody parameter is poorly determined. Higher-order statistics (number variance, Delta_3) require even more eigenvalues. Report confidence intervals.

4. **Non-universal features at short range.** The universal RMT predictions apply to fluctuations on the scale of the mean level spacing. Correlations on larger energy scales (smooth density of states, shell structure) are system-specific and should be removed by unfolding.

5. **Confusing Wigner surmise with exact result.** The Wigner surmise is the exact result for 2x2 matrices. For large N, the exact spacing distribution differs slightly (at the ~1% level). For precision work, use the exact Gaudin-Mehta distribution (expressed in terms of Fredholm determinants of the sine kernel).

6. **Applying RMT to non-ergodic systems.** RMT assumes ergodicity in the appropriate symmetry class. Systems with localization (Anderson model in 3D near the transition), many-body localized systems, or systems with approximate symmetries may show deviations from both Wigner-Dyson and Poisson.

7. **Ignoring Thouless energy.** In disordered systems, RMT statistics hold for energy scales below the Thouless energy E_Th = hbar * D / L^2 (where D is the diffusion coefficient). Above E_Th, the spectrum crosses over to Poisson. The number variance saturates at L ~ E_Th / Delta (Delta = mean spacing).

## Worked Example: Quantum Billiard Spectrum and the BGS Conjecture

**Problem:** Verify that the energy levels of the Sinai billiard (square billiard with a circular scatterer at the center, classically chaotic) follow GOE statistics, while the rectangular billiard (classically integrable) follows Poisson statistics.

### Step 1: Compute the Spectra

**Sinai billiard:** Square of side L with a circular disc of radius R at the center (R/L = 0.2). Solve the Helmholtz equation nabla^2 psi + k^2 psi = 0 with Dirichlet boundary conditions numerically. Extract the first 1000 eigenvalues k_n^2 in the sector with no symmetry (odd-odd parity to avoid accidental degeneracies from the square symmetry).

**Rectangular billiard:** Sides L_x, L_y with L_x/L_y = sqrt(2) (irrational to avoid systematic degeneracies). Eigenvalues are E_{mn} = (pi hbar)^2/(2m) * [(n/L_x)^2 + (m/L_y)^2]. Take the first 1000 eigenvalues.

### Step 2: Unfold

For both billiards, the Weyl formula gives the smooth density of states:

```
N_smooth(E) = (A / (4pi)) * E - (P / (4pi)) * sqrt(E) + corrections
```

where A is the area and P is the perimeter. Unfold: x_i = N_smooth(E_i).

**Checkpoint:** After unfolding, verify <s> = 1.00 +/- 0.03 and the staircase function of unfolded eigenvalues fluctuates around the diagonal with unit slope.

### Step 3: Nearest-Neighbor Spacing Distribution

**Sinai billiard result:**
- P(s) matches the Wigner surmise P_GOE(s) = (pi/2)*s*exp(-pi*s^2/4)
- P(0) = 0 (level repulsion present)
- <s^2> = 4/pi - 1 + 1 = 4/pi = 1.273, var(s) = 4/pi - 1 = 0.273. Matches GOE prediction.
- Brody parameter: q = 0.96 +/- 0.04. Consistent with q = 1 (Wigner-Dyson).

**Rectangular billiard result:**
- P(s) matches P_Poisson(s) = exp(-s)
- P(0) = 1 (no level repulsion)
- var(s) = 1.00 +/- 0.05. Matches Poisson prediction.
- Brody parameter: q = 0.03 +/- 0.05. Consistent with q = 0 (Poisson).

### Step 4: Number Variance

**Sinai billiard:** Sigma^2(L) follows the GOE prediction: Sigma^2(L) ~ (2/pi^2) * ln(L) for L from 1 to 20. The logarithmic growth (spectral rigidity) is the signature of eigenvalue repulsion.

**Rectangular billiard:** Sigma^2(L) = L (linear growth = Poisson shot noise). No spectral rigidity.

### Verification

1. **Symmetry class check:** The Sinai billiard has time-reversal symmetry (no magnetic field) and the Schrodinger equation is real (integer "spin" = no spin). Therefore: GOE (beta = 1). If we add a magnetic field (Aharonov-Bohm flux through the disc), time-reversal is broken and the statistics should switch to GUE. Verified: P(s) transitions from GOE to GUE as flux increases from 0 to Phi_0/2.

2. **Sector separation check:** If we do NOT separate parity sectors in the Sinai billiard (the square has D_4 symmetry), the mixed spectrum looks approximately Poisson (superposition of 4 independent GOE sequences). This is a known artifact — the BGS conjecture applies to a single irreducible symmetry sector only.

3. **Finite-size check:** Repeat with 500 and 2000 eigenvalues. The Brody parameter should be stable (not approach Poisson as N increases, which would signal localization or other non-universal effects).

4. **Comparison with KAM regime:** For a billiard with mixed phase space (e.g., stadium billiard with soft boundary), the spacing distribution is intermediate between Poisson and GOE, with Brody parameter 0 < q < 1. The value of q correlates with the fraction of phase space that is chaotic.

5. **Ratio statistic (unfolding-free):** Compute r_i = min(s_i, s_{i+1}) / max(s_i, s_{i+1}). The mean is <r>_Poisson = 2*ln(2) - 1 = 0.386 and <r>_GOE = 4 - 2*sqrt(3) = 0.536. The Sinai billiard gives <r> = 0.53 +/- 0.02 (GOE), the rectangle gives <r> = 0.39 +/- 0.02 (Poisson). This confirms the result without any unfolding procedure.

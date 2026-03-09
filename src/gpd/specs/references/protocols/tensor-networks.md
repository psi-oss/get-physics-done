---
load_when:
  - "tensor network"
  - "DMRG"
  - "MPS"
  - "matrix product state"
  - "PEPS"
  - "entanglement"
  - "bond dimension"
  - "TEBD"
tier: 2
context_cost: medium
---

# Tensor Network Methods Protocol

Tensor networks provide a controlled approximation scheme for quantum many-body systems, with entanglement as the organizing principle. The bond dimension chi controls accuracy: larger chi captures more entanglement. But convergence is subtle — area-law systems converge exponentially while critical and higher-dimensional systems converge polynomially or worse. This protocol ensures systematic convergence and correct identification of the entanglement structure.

## Related Protocols

- See `monte-carlo.md` for comparison: when to use tensor networks vs quantum Monte Carlo (TN excels in 1D and for sign-problem systems; QMC excels in higher dimensions without sign problem)
- See `variational-methods.md` for DMRG as a variational method and general variational optimization principles

## Step 1: Entanglement Structure Assessment

1. **Before choosing a tensor network ansatz:** Determine the entanglement scaling of the target state. This dictates which tensor network is appropriate.
   - **Area law** (S ~ L^{d-1} for a region of linear size L): Ground states of gapped local Hamiltonians in any dimension. MPS/DMRG is efficient in 1D.
   - **Area law with log correction** (S ~ L^{d-1} * log(L)): Critical 1D systems (CFT ground states). MPS works but requires chi ~ L^{c/6} where c is the central charge. Converges slowly for large c.
   - **Volume law** (S ~ L^d): Highly excited states, random states, thermal states at high T. Tensor networks are NOT efficient for volume-law states. Use other methods (exact diagonalization, quantum Monte Carlo, typicality).
2. **Match the ansatz to the geometry:**
   - **1D chains/rings:** MPS (Matrix Product States). Bond dimension chi controls entanglement. DMRG is the standard optimization algorithm.
   - **1D with long-range interactions or criticality:** MPS with larger chi, or MERA (Multi-scale Entanglement Renormalization Ansatz) which naturally encodes scale invariance.
   - **2D lattices:** PEPS (Projected Entangled Pair States). Exact contraction is #P-hard; approximations required (boundary MPS, corner transfer matrix, simple update vs full update).
   - **Trees / Bethe lattices:** Tree Tensor Networks (TTN). Exact contraction is efficient.
   - **Thermal states:** Purification (double the Hilbert space) with MPS, or directly use matrix product operators (MPO) for the density matrix.

## Step 2: Bond Dimension Convergence (MPS/DMRG)

1. **Systematic convergence study.** Run DMRG at chi = chi_1, chi_2, chi_3, ... with chi increasing by factors of 1.5-2. For each chi, record: ground state energy E(chi), entanglement entropy S(chi), correlation length xi(chi), and any target observables.
2. **Convergence criterion:** The energy difference |E(chi) - E(chi/2)| < target accuracy. For gapped systems: convergence is exponential in chi — a few hundred is usually sufficient. For critical systems: convergence is polynomial — chi must be large enough that xi(chi) exceeds the system size.
3. **Truncation error.** DMRG produces a discarded weight epsilon(chi) = sum of discarded singular values squared. This is a direct measure of approximation quality. For converged results: epsilon < 10^{-8} for gapped systems, epsilon < 10^{-5} for critical systems.
4. **Extrapolation in truncation error.** Plot observables vs epsilon and extrapolate to epsilon -> 0. This is more reliable than extrapolation in 1/chi because the relationship between observables and epsilon is more nearly linear.

## Step 3: Boundary Effects and System Size

1. **Open vs periodic boundary conditions.**
   - **Open BC (standard DMRG):** Much more efficient — bond dimension needed for a given accuracy is smaller. But: boundary effects penetrate into the bulk by a distance ~ xi (correlation length). Measure observables in the bulk (center of the chain), not near edges.
   - **Periodic BC:** No boundary effects but the MPS has a more complex structure (the bond dimension effectively doubles). More expensive by a factor of chi. Use when boundary effects would contaminate the physics (e.g., momentum-resolved properties, topological ground state degeneracy).
2. **Finite-size scaling.** Run at system sizes L = L_1, L_2, L_3, ... and extrapolate to L -> infinity. For gapped systems: finite-size corrections ~ exp(-L/xi). For critical systems: corrections ~ L^{-1/nu} or L^{-c/6} depending on the quantity. Use the expected CFT finite-size scaling form for critical systems.
3. **Edge modes and topological order.** In topological phases (Haldane chain, AKLT, topological insulators), open boundary conditions produce edge modes that are physical features, not artifacts. The entanglement spectrum (eigenvalues of the reduced density matrix) reveals topological order through its degeneracy structure. Report the entanglement spectrum alongside energies.

## Step 4: PEPS and 2D Tensor Networks

1. **Contraction approximation.** Exact contraction of a 2D PEPS scales exponentially with system size. Approximate contraction introduces a systematic error that is ADDITIONAL to the finite-bond-dimension error. Control both independently.
2. **Simple update vs full update.**
   - **Simple update:** Uses a mean-field-like environment. Fast but less accurate — the effective bond dimension is underutilized. Good for initial exploration and gapped phases.
   - **Full update:** Uses the full tensor environment. More accurate but much more expensive (scales as chi^{10-12} in 2D). Necessary for critical systems and quantitative accuracy.
3. **Boundary MPS method.** Contract the 2D network by approximating the boundary as an MPS with bond dimension chi_boundary. The accuracy depends on BOTH the PEPS bond dimension chi and chi_boundary. Converge both independently.
4. **Fermion signs.** For fermionic PEPS, the tensor network must encode the fermionic sign structure (anticommutation). Use fermionic PEPS (fPEPS) with graded tensor spaces, or Jordan-Wigner transformation (introduces long-range strings that complicate the tensor network). State which approach is used.

## Step 5: Time Evolution

1. **TEBD (Time-Evolving Block Decimation).** Apply the time-evolution operator e^{-iHdt} via Trotter decomposition. Sources of error:
   - Trotter error: O(dt^{p+1}) for pth-order decomposition. Use at least 2nd order (Strang splitting). Verify convergence in dt.
   - Truncation error: At each time step, the bond dimension is truncated back to chi. Entanglement grows linearly in time for generic quenches, requiring chi ~ exp(S(t)) which grows exponentially. There is a maximum reliable time t_max ~ chi / (entanglement growth rate).
2. **TDVP (Time-Dependent Variational Principle).** Projects the exact evolution onto the MPS manifold at fixed chi. Conserves energy exactly (for the 2-site variant) and handles long-range interactions without Trotter decomposition. Preferred over TEBD for long-range Hamiltonians.
3. **Entanglement growth monitoring.** Plot S(t) during time evolution. When S(t) approaches log(chi), the MPS can no longer faithfully represent the state. All results beyond this point are unreliable. Report t_max explicitly.
4. **Spectral functions.** Compute via time evolution: S(k, omega) = FT of <psi| O^dag(t) O(0) |psi>. The frequency resolution is ~ 1/t_max, which is limited by entanglement growth. Linear prediction or Chebyshev expansion can extend the resolution, but with assumptions about the spectral shape that must be stated.

## Worked Example: DMRG Ground State of the Spin-1/2 Heisenberg Chain

**Problem:** Compute the ground state energy per site of the antiferromagnetic spin-1/2 Heisenberg chain H = J sum_i S_i . S_{i+1} with J = 1, and verify convergence in bond dimension and system size. The exact result (Bethe ansatz) is E_0/N = 1/4 - ln(2) = -0.443147... per site.

### Step 1: Entanglement Assessment

The Heisenberg chain is critical (gapless, central charge c = 1). Therefore:
- Entanglement entropy scales as S ~ (c/6) ln(L) = (1/6) ln(L) for open BC
- MPS needs chi ~ L^{c/6} = L^{1/6} for convergence
- This is polynomial, not exponential — DMRG works but needs careful convergence

### Step 2: Bond Dimension Convergence

Run DMRG at L = 100 (open BC) with increasing chi:

| chi | E_0/L | |E - E_exact|/L | Discarded weight epsilon | S(L/2) |
|-----|-------|-----------------|--------------------------|--------|
| 32  | -0.44308 | 7e-5 | 3.2e-6 | 1.76 |
| 64  | -0.44314 | 1e-5 | 8.1e-8 | 1.82 |
| 128 | -0.443146 | 1e-6 | 1.9e-9 | 1.85 |
| 256 | -0.4431471 | 2e-7 | 4.5e-11 | 1.87 |

**Key observations:**
- Energy converges exponentially in chi even though the system is critical — this is because open BC at finite L has an effective gap ~ v_s/L
- Entanglement entropy S(L/2) grows slowly with chi, approaching the CFT prediction S = (c/6) ln(L/a) ~ (1/6) ln(100) ~ 0.77 * 2.37 (with a UV cutoff correction)

### Step 3: Finite-Size Extrapolation

For the critical Heisenberg chain with open BC, CFT predicts:
```
E_0(L)/L = e_inf + (pi v_s c) / (6 L^2) * f(BC)
```
where e_inf = 1/4 - ln(2), v_s = pi/2 (spinon velocity), c = 1, and f(OBC) includes surface energy corrections.

Run at chi = 256 (well converged) for multiple L:

| L | E_0/L (DMRG) | Exact (Bethe) |
|---|-------------|---------------|
| 20 | -0.44899 | -0.44899 |
| 50 | -0.44502 | -0.44502 |
| 100 | -0.44409 | -0.44409 |
| 200 | -0.44362 | -0.44362 |

Extrapolating E_0/L vs 1/L^2 to L -> infinity gives e_inf = -0.4431(1), consistent with the exact value -0.443147.

### Step 4: Correlation Function Check

The spin-spin correlation function for the critical Heisenberg chain decays as:
```
<S_i . S_j> ~ (-1)^{|i-j|} / |i-j| * [ln(|i-j|)]^{1/2}
```
(power law with logarithmic corrections from marginally irrelevant operators).

Measure at L = 200 from the center (site 100) to avoid boundary effects:
- |i-j| = 1: <S.S> ~ -0.4431 (nearest-neighbor)
- |i-j| = 10: <S.S> ~ (-1)^{10} * 0.044 * [ln(10)]^{0.5} ~ 0.067
- |i-j| = 50: <S.S> ~ (-1)^{50} * 0.0089 * [ln(50)]^{0.5} ~ 0.018

If the correlation function decays exponentially instead of as a power law, the bond dimension is too small (the MPS is imposing a finite correlation length xi ~ chi^{kappa}).

### Verification

1. **Energy per site vs exact:** |E_0/N - (1/4 - ln 2)| < 10^{-4} for chi >= 64 at L = 100. If the error is larger, check the DMRG algorithm (sweeps, noise terms, convergence criterion).

2. **Entanglement entropy scaling:** Plot S(l) vs ln(l) for a cut at position l from the edge. The slope should be c/6 = 1/6. If the slope is wrong, either chi is too small (S is saturated at ln(chi)) or the system is not in the ground state (excited state has different entanglement).

3. **SU(2) symmetry check:** The Heisenberg Hamiltonian has SU(2) symmetry. The ground state is a singlet (total spin S_tot = 0). Verify: <S_tot^2> = 0 to machine precision. If <S_tot^2> > 0, the DMRG may have converged to a symmetry-broken state (use symmetry-preserving DMRG or add noise to escape the local minimum).

4. **Variational bound:** DMRG is variational — every E_0(chi) must satisfy E_0(chi) >= E_exact. If E_0(chi) < E_exact, there is a bug in the code or the Hamiltonian construction.

5. **Discarded weight extrapolation:** Plot E_0 vs epsilon (discarded weight) and extrapolate to epsilon -> 0. The extrapolated energy should agree with the Bethe ansatz value to within the fitting uncertainty.

## Worked Example: Quench Dynamics of the Transverse-Field Ising Chain via TEBD

**Problem:** Compute the time evolution of the magnetization and entanglement entropy after a sudden quench in the 1D transverse-field Ising model H = -J sum_i (sigma_z_i sigma_z_{i+1} + g sigma_x_i), quenching from g = 2.0 (paramagnetic) to g = 0.5 (ferromagnetic). Identify the maximum reliable simulation time and demonstrate that results beyond entanglement saturation are artifacts. This example targets the most common error in tensor network dynamics: trusting results after the bond dimension is saturated.

### Step 1: Entanglement Growth Assessment

After a global quench, entanglement grows linearly in time: S(t) ~ v_E * t, where v_E is the entanglement velocity. For the transverse-field Ising model quenched into the ferromagnetic phase, v_E ~ J (the maximum group velocity of quasiparticle excitations). The MPS bond dimension chi can represent entanglement up to S_max = ln(chi). Therefore:

```
t_max ~ ln(chi) / v_E
```

For chi = 256: t_max ~ ln(256) / J ~ 5.5 / J. For chi = 1024: t_max ~ ln(1024) / J ~ 6.9 / J. This is a logarithmic improvement — doubling chi adds only about 0.7/J to the reliable time window.

### Step 2: TEBD Setup

- L = 100 sites, open boundary conditions
- Initial state: ground state of H(g=2.0), computed by DMRG at chi = 64 (paramagnetic phase, low entanglement, converges quickly)
- Time evolution: 2nd-order Trotter (Strang splitting) with dt = 0.01/J
- Bond dimensions: chi = 64, 128, 256, 512

### Step 3: Results — Magnetization

Track the staggered magnetization m_s(t) = (1/L) sum_i (-1)^i <sigma_z_i(t)>:

| t * J | m_s (chi=64) | m_s (chi=128) | m_s (chi=256) | m_s (chi=512) | Converged? |
|-------|-------------|--------------|--------------|--------------|------------|
| 0.0 | 0.000 | 0.000 | 0.000 | 0.000 | Yes |
| 1.0 | 0.142 | 0.143 | 0.143 | 0.143 | Yes |
| 2.0 | 0.251 | 0.258 | 0.259 | 0.259 | Yes |
| 3.0 | 0.310 | 0.335 | 0.341 | 0.342 | Yes |
| 4.0 | 0.298 | 0.370 | 0.395 | 0.401 | Marginal |
| 5.0 | 0.215 | 0.320 | 0.410 | 0.438 | No |
| 6.0 | 0.120 | 0.230 | 0.380 | 0.445 | No |
| 8.0 | 0.008 | 0.090 | 0.250 | 0.390 | No |

At t*J = 3, all bond dimensions agree to within 2% — the result is reliable. At t*J = 5, the spread across chi values is 50% — the result is not converged. At t*J = 8, chi = 64 shows near-zero magnetization (the MPS has lost all memory of the quench dynamics), while chi = 512 still shows significant order. Neither is necessarily correct at t*J = 8.

### Step 4: Entanglement Entropy Monitoring

The half-chain entanglement entropy S(L/2, t):

| t * J | S (chi=64) | S (chi=128) | S (chi=256) | S (chi=512) |
|-------|-----------|------------|------------|------------|
| 0.0 | 0.02 | 0.02 | 0.02 | 0.02 |
| 1.0 | 0.89 | 0.89 | 0.89 | 0.89 |
| 2.0 | 1.78 | 1.82 | 1.82 | 1.82 |
| 3.0 | 2.55 | 2.74 | 2.77 | 2.77 |
| 4.0 | 3.10 | 3.62 | 3.72 | 3.73 |
| 5.0 | 3.45 | 4.30 | 4.65 | 4.68 |
| 6.0 | 3.62 | 4.65 | 5.40 | 5.63 |
| 8.0 | 3.78 | 4.82 | 5.52 | 6.30 |

S_max = ln(chi): for chi = 64, S_max = 4.16; for chi = 128, S_max = 4.85; for chi = 256, S_max = 5.55; for chi = 512, S_max = 6.21.

When S approaches ~85% of S_max, truncation errors dominate. For chi = 64, this happens at t*J ~ 3.5. For chi = 256, at t*J ~ 5. The entanglement entropy is the primary diagnostic: when S(t) curves away from the linear growth seen at higher chi, the simulation at that chi is no longer reliable.

### Step 5: Trotter Error Check

Compare dt = 0.01/J with dt = 0.005/J at chi = 256:

| t * J | m_s (dt=0.01) | m_s (dt=0.005) | |Delta m_s| |
|-------|--------------|---------------|------------|
| 2.0 | 0.259 | 0.259 | 4e-5 |
| 4.0 | 0.395 | 0.395 | 2e-4 |

Trotter error is negligible compared to truncation error. This is typical: for 2nd-order Trotter with dt = 0.01/J, the error per step is O(dt^3) ~ 10^{-6}/J^3, while truncation errors are O(10^{-3}) at t*J = 4.

### Verification

1. **Energy conservation:** TEBD is not exactly energy-conserving (Trotter + truncation break the symplectic structure). Monitor <H(t)> - <H(0)>. At chi = 256: energy drift is < 10^{-4} * J for t*J < 4, growing to 10^{-2} * J by t*J = 6. Large energy drift signals unreliable dynamics.

2. **Entanglement as reliability diagnostic:** Plot S(t) for all chi values on the same axes. The curves should overlap at early times and peel off one by one as each chi saturates. The true S(t) is the envelope of the highest-chi curve in the linear-growth regime. If S(t) for the highest chi is already saturating, no results at that time are trustworthy.

3. **Light cone check:** After the quench, correlations spread at the Lieb-Robinson velocity v_LR = 2*J*g (for the Ising model). Plot the connected correlator <sigma_z_i sigma_z_j> - <sigma_z_i><sigma_z_j> as a function of |i-j| and t. Correlations should be negligible outside the light cone |i-j| > v_LR * t. If correlations appear outside the light cone, the time step is too large or the MPS is introducing spurious long-range correlations due to truncation.

4. **Comparison with exact solution:** The transverse-field Ising chain is exactly solvable (Jordan-Wigner transformation to free fermions). At L = 100: compare m_s(t) with the exact result for t*J < 3 (where MPS is converged). Agreement within 10^{-3} validates the TEBD implementation.

5. **Do NOT trust results beyond t_max.** The key message: for chi = 256, results at t*J > 5 are artifacts of bond dimension truncation, even though the simulation continues to produce numbers. The magnetization at t*J = 8 with chi = 256 (m_s = 0.250) is wrong — it is an artifact of the MPS being unable to represent the true entangled state. Report t_max explicitly in any publication.

## Common Pitfalls

- **Insufficient bond dimension for critical systems.** Chi = 100 is enough for a gapped 1D system of any size. For a critical system at the Heisenberg point, chi = 100 gives xi ~ 30 — meaningless for L = 200. Scale chi with L for critical systems.
- **Wrong boundary conditions hiding physics.** Periodic BC with small chi can miss spontaneous symmetry breaking because the MPS favors the symmetric superposition. Open BC with symmetry-broken initial state can artificially pin a specific broken-symmetry state. Be aware of what BC does to the target state.
- **Ignoring entanglement growth in dynamics.** "The simulation ran to t = 100 with chi = 256" is meaningless if the entanglement saturated chi at t = 5. Always report S(t) and the time at which truncation errors become significant.
- **2D tensor network accuracy.** PEPS with chi = 6 in 2D is roughly comparable to MPS with chi = 6^2 = 36 in 1D (due to contraction approximation errors on top of finite-chi errors). Do not expect 2D tensor network accuracy comparable to 1D DMRG. Benchmark against exact diagonalization on small systems before trusting 2D results on larger systems.

## Worked Example: Entanglement Entropy Scaling and Central Charge Extraction at a Quantum Critical Point

**Problem:** Extract the central charge c of the critical transverse-field Ising chain H = -sum_i (sigma^z_i sigma^z_{i+1} + sigma^x_i) from the entanglement entropy scaling S(l) using DMRG. Demonstrate how insufficient bond dimension and wrong boundary conditions produce incorrect values of c. This targets the LLM error class of reading off the central charge from a fit to S = (c/6) ln(l) without checking that the system is at criticality, the bond dimension is sufficient, and the finite-size/boundary effects are correctly accounted for.

### Step 1: CFT Prediction for Entanglement Entropy

At a critical point described by a 1+1D CFT with central charge c, the entanglement entropy of a subsystem of length l in a chain of total length L obeys:

```
Open BC:    S(l) = (c/6) ln[(2L/pi) sin(pi l/L)] + c_1 + S_osc(l)
Periodic BC: S(l) = (c/3) ln[(L/pi) sin(pi l/L)] + c_1'
```

where c_1, c_1' are non-universal constants and S_osc(l) contains oscillating corrections (from the lattice, decaying as l^{-2 Delta} where Delta is the dimension of the leading irrelevant operator).

For the critical Ising chain (g = 1): c = 1/2 (the free Majorana fermion CFT, equivalently the Ising CFT).

### Step 2: DMRG Computation

Run DMRG at g = 1.0 (critical point), open BC, L = 200, at several bond dimensions:

```
chi = 32:   S(L/2) = 0.696,  fitted c = 0.47
chi = 64:   S(L/2) = 0.719,  fitted c = 0.49
chi = 128:  S(L/2) = 0.728,  fitted c = 0.499
chi = 256:  S(L/2) = 0.731,  fitted c = 0.500
chi = 512:  S(L/2) = 0.732,  fitted c = 0.500
```

Fit procedure: fit S(l) for l in [20, 180] (avoiding edges) to S = (c/6) ln[(2L/pi) sin(pi l/L)] + c_1 using least-squares.

**Key observation:** At chi = 32, the fitted central charge c = 0.47 is 6% below the exact value c = 1/2. This is because the MPS imposes a finite correlation length xi_chi ~ chi^{kappa} (with kappa = 6/c = 12 for the Ising CFT). For chi = 32: xi_chi ~ 32^{12} is astronomically large — but the ENTANGLEMENT entropy saturates at S_max ~ ln(chi) = 3.5, which for our fit window is NOT the limiting factor. The actual issue is that the effective central charge is reduced when the Schmidt spectrum is truncated: the smallest Schmidt values are discarded, reducing S(l) below its true value.

### Step 3: The Wrong-Criticality Error

Run DMRG at g = 0.95 (slightly in the ordered phase, NOT critical) with chi = 256:

```
S(l) for g = 0.95: S(L/2) = 0.68, fitted c = 0.43
```

The system has a correlation length xi ~ 20 lattice sites at g = 0.95. The entanglement entropy crosses over from the logarithmic critical scaling S ~ (c/6) ln(l) at l << xi to the area-law saturation S ~ const at l >> xi. Fitting the whole range l in [20, 180] to the CFT formula gives a spurious c = 0.43 because the large-l data pulls the fit toward area-law behavior.

**Checkpoint:** Before fitting for c, verify the system is at the critical point:
1. The correlation length xi should exceed L/2 (for a critical system at finite L, xi ~ L)
2. The gap Delta E = E_1 - E_0 should scale as 1/L (conformal tower)
3. The entanglement entropy should not show saturation at large l

At g = 0.95: xi ~ 20 << L/2 = 100. The system is NOT at the critical point, and the CFT fit is invalid.

### Step 4: The Boundary Condition Trap

Run at g = 1.0 (critical), chi = 256, but now with PERIODIC boundary conditions, L = 100:

```
S(l) fit to (c/3) ln[(L/pi) sin(pi l/L)] gives c = 0.499
S(l) fit to (c/6) ln[(2L/pi) sin(pi l/L)] (wrong: OBC formula) gives c = 0.998
```

Using the OBC formula for PBC data doubles the extracted central charge because the PBC prefactor is c/3 (not c/6). This factor-of-2 error is one of the most common LLM mistakes in central charge extraction.

**The physics:** With PBC, a bipartition of a ring creates TWO boundaries between the subsystem and its complement. Each boundary contributes c/6 to the entropy, giving c/3 total. With OBC, the bipartition creates only ONE boundary.

### Step 5: Oscillation Subtraction

At the critical Ising point, the entanglement entropy has oscillating corrections:

```
S(l) = (c/6) ln[...] + c_1 + A * (-1)^l * l^{-2/8} + ...
```

The alternating term with exponent -2/8 = -1/4 comes from the leading irrelevant operator (energy density, Delta = 1). Without subtracting this oscillation:

```
Fit S(l) for even l only:   c = 0.500(1)
Fit S(l) for all l:        c = 0.497(3)  (oscillations bias the fit)
Fit S(l) for odd l only:   c = 0.494(5)  (worse, smaller sample)
```

The most robust procedure: fit even-l and odd-l data separately, or include the oscillating term in the fit model. Fitting all l together without the oscillation term introduces a systematic bias that is small for c = 1/2 but significant for larger c (e.g., the 3-state Potts model with c = 4/5).

### Verification

1. **Known exact value.** c = 1/2 for the critical Ising chain. The extracted value must agree within the fitting uncertainty. If c > 0.55 or c < 0.45, there is a systematic error (wrong g, wrong BC formula, or insufficient chi).

2. **Bond dimension convergence.** c(chi) should converge monotonically from below to the true value. If c(chi) oscillates or converges from above, the fit is unreliable (likely including data at l > xi_chi where the MPS is not faithful).

3. **Fit range stability.** Vary the fit range: [10, 190], [20, 180], [40, 160], [60, 140]. The extracted c should be stable to within 0.01. If c depends strongly on the fit range, there are boundary effects (small l) or saturation effects (large l) contaminating the fit.

4. **Gap scaling cross-check.** Compute the first excited state energy E_1 at several L values. At the critical point: Delta E = E_1 - E_0 = pi v c / (6 L) (with logarithmic corrections for OBC). Fit v and c independently. The c from the gap should agree with the c from the entropy.

5. **Cross-check at g != 1.** At g = 0.5 (deep in the ordered phase): S(l) should be essentially constant for l > 5 (area law). At g = 2.0 (deep in the disordered phase): same. Fitting the CFT formula in these phases should give c ~ 0, confirming the fit procedure correctly identifies non-critical behavior.

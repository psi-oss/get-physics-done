---
load_when:
  - "GW approximation"
  - "Bethe-Salpeter"
  - "quasiparticle"
  - "self-energy"
  - "spectral function"
  - "MBPT"
  - "many-body perturbation"
  - "exciton"
tier: 2
context_cost: high
---

# Many-Body Perturbation Theory Protocol

Many-body perturbation theory (MBPT) provides systematic corrections to independent-particle descriptions of electronic structure. The GW approximation, Bethe-Salpeter equation, and self-consistent Green's function methods capture quasiparticle renormalization, satellite structure, and optical excitations that DFT fundamentally cannot describe. These methods are powerful but expensive, and every approximation (starting point, frequency treatment, self-consistency level) can qualitatively change results.

## Related Protocols

- See `density-functional-theory.md` for the DFT starting point that feeds into MBPT (functional choice, convergence, k-mesh)
- See `analytic-continuation.md` for Matsubara-to-real-frequency continuation of self-energies and response functions
- See `numerical-computation.md` for convergence testing of basis sets, frequency grids, and k-point sampling
- See `variational-methods.md` for connections to VMC, coupled cluster, and other correlated methods

## When to Apply

Use this protocol when computing quasiparticle band structures, photoemission spectra, optical absorption, exciton binding energies, or any electronic property where DFT eigenvalues are qualitatively insufficient. Typical triggers:
- The DFT band gap is wrong by more than 20%
- Satellite features (plasmon replicas, Hubbard bands) are needed
- Excitonic effects dominate the optical spectrum
- You need the spectral function A(k, omega), not just eigenvalues
- Starting-point dependence of DFT results suggests strong correlation effects

## Step 1: DFT Starting Point

1. **Choose the DFT functional deliberately.** G0W0 is a one-shot correction and inherits the DFT starting point. LDA and PBE typically underestimate gaps, so G0W0@LDA/PBE underestimates quasiparticle gaps. Hybrid functionals (HSE06, PBE0) provide a better starting point but are more expensive. For systems where the DFT gap is qualitatively wrong (zero when it should be finite), a hybrid starting point is essential.

2. **Converge the DFT calculation tightly.** The MBPT calculation amplifies any noise in the DFT input:
   - SCF convergence to at least 10^{-8} eV in total energy
   - Eigenvalues converged to < 1 meV
   - Use a k-mesh at least as dense as the final GW k-mesh (typically denser, since GW interpolation can be used)

3. **Include enough empty states from the start.** GW requires summation over unoccupied states for the polarizability and self-energy. Typically 10-100x the number of occupied states, depending on the system and basis set. This is the single most expensive convergence parameter. Modern stochastic or low-rank approaches can reduce this cost but introduce their own convergence parameters.

4. **Document the starting point completely.** Report: functional, pseudopotential/basis set, k-mesh, plane-wave cutoff (or Gaussian basis), number of bands, SCF convergence threshold. G0W0 results without this information are not reproducible.

## Step 2: Self-Energy Calculation (GW Approximation)

1. **Understand the self-consistency ladder.** Each level has different cost, accuracy, and properties:
   - **G0W0** (one-shot): Cheapest. Results depend on starting point. No conservation laws guaranteed. Often surprisingly accurate for sp semiconductors.
   - **GW0** (partial self-consistency in G): Update G but keep W fixed from DFT. Reduces starting-point dependence. Typically opens gaps relative to G0W0.
   - **scGW** (full self-consistency): Update both G and W iteratively until convergence. Starting-point independent. Satisfies conservation laws (Baym-Kadanoff). But: tends to overestimate band gaps and washes out satellite structure because the spectral function loses sharp quasiparticle features.
   - **QSGW** (quasiparticle self-consistent GW): Update only the quasiparticle part of G (the Hermitian, static part of Sigma). Good compromise: reduces starting-point dependence while preserving spectral features. Currently the recommended approach for materials where starting-point dependence exceeds 0.3 eV.

2. **Choose the frequency treatment carefully.** The screened interaction W(omega) has strong frequency dependence near the plasmon frequency:
   - **Plasmon-pole approximation (PPA):** Models the frequency dependence of the inverse dielectric function with a single pole. Fast but can be qualitatively wrong for systems with multiple plasmon branches, d-electron systems, or when the detailed frequency structure of W matters (e.g., satellites). Always validate PPA against full-frequency for at least one system in each material class.
   - **Full frequency integration — contour deformation (CD):** Numerically stable. Integrates along the imaginary axis (smooth integrand) plus residue contributions from poles between the real and imaginary axes. The standard for production calculations.
   - **Full frequency integration — analytic continuation (AC):** Evaluate Sigma on the imaginary axis and continue to the real axis via Pade approximants. Can be unstable for complex self-energy structure — test by varying the number of frequency points.
   - **Imaginary-frequency formulation:** Work entirely on the imaginary axis and analytically continue final results. Avoids all real-axis plasmon structure but requires reliable continuation (see `analytic-continuation.md`).

3. **Convergence parameters to test systematically:**
   - Number of empty states in the polarizability (chi0) and self-energy (Sigma)
   - Plane-wave cutoff for the dielectric matrix (often much smaller than the DFT cutoff — typically 10-30% of E_cut)
   - Number of frequency points on the imaginary axis or along the contour
   - k-point mesh for the polarizability sum (can often be coarser than the k-mesh for eigenvalues)
   - Convergence is often slowest with respect to empty states — always test this parameter first

## Step 3: Dyson Equation and Quasiparticle Energies

1. **The quasiparticle equation.** The full Dyson equation G = G0 + G0 Sigma G gives the interacting Green's function. For quasiparticle energies, solve the nonlinear equation:
   E_nk = epsilon_nk + Z_nk * Re[Sigma_nk(epsilon_nk) - V_xc_nk]
   where Z_nk = (1 - d Re Sigma / d omega)^{-1} is the quasiparticle weight.

2. **Linearized vs full solution.** The linearized solution (Taylor-expand Sigma around epsilon_nk) is standard and usually sufficient when Z_nk > 0.5. For strongly correlated systems where Z_nk < 0.5, the linearization breaks down and the full frequency-dependent equation must be solved graphically or iteratively. In this regime, the spectral function may show multiple solutions (quasiparticle peak plus satellites) and a single quasiparticle energy is insufficient.

3. **Quasiparticle weight interpretation.** Z_nk measures the fraction of spectral weight in the quasiparticle peak:
   - Z_nk = 1: non-interacting electron (no correlation)
   - Z_nk ~ 0.7-0.8: weakly correlated (typical sp semiconductors)
   - Z_nk ~ 0.3-0.5: moderately correlated (transition metal d-states)
   - Z_nk -> 0: quasiparticle picture breaks down (Mott physics, heavy fermions)
   - Z_nk < 0 or Z_nk > 1: calculation error or linearization failure

4. **Off-diagonal elements.** Standard G0W0 neglects off-diagonal self-energy matrix elements (assumes DFT wavefunctions are good quasiparticle wavefunctions). For systems with strong hybridization, band crossing, or orbital reordering between DFT and GW, off-diagonal elements can matter qualitatively. QSGW includes these by construction.

## Step 4: Spectral Function Extraction

1. **The spectral function** A(k, omega) = -1/pi * Im G(k, omega) contains all single-particle excitation information: quasiparticle peaks, satellites, lifetime broadening. It is directly comparable to angle-resolved photoemission (ARPES) for occupied states and inverse photoemission for unoccupied states.

2. **From imaginary to real axis.** If the calculation was done on the imaginary frequency axis, analytic continuation is required. Methods in order of reliability:
   - **Direct evaluation on the real axis** (if available from contour deformation): Most reliable. No continuation needed. Use this when possible.
   - **Pade approximants:** Fit a rational function to imaginary-axis data and evaluate on the real axis. Sensitive to noise and the number of Pade coefficients. Always test stability by varying the number of input points by +/- 20%.
   - **Maximum entropy method (MaxEnt):** Bayesian inference with a default model (usually flat). More robust to noise than Pade but introduces broadening. The default model biases the result — test sensitivity by using flat, Gaussian, and DFT-derived default models.
   - **Stochastic analytic continuation:** Sample spectral functions consistent with the imaginary-axis data via Monte Carlo. Gives error bars on the spectral function but is computationally expensive. Best for validating Pade/MaxEnt results.

3. **Artifacts to watch for:**
   - Spurious peaks from Pade instability (appear/disappear when varying number of coefficients)
   - Artificial broadening from MaxEnt (smears sharp features)
   - Negative spectral weight (unphysical — indicates an error in the calculation or continuation)
   - Missing high-energy satellites (insufficient frequency range or basis set)
   - Causality violation: Im Sigma(omega) must be negative (for retarded self-energy)

## Step 5: Bethe-Salpeter Equation (Optical Properties)

1. **The BSE describes bound electron-hole pairs (excitons).** After obtaining quasiparticle energies from GW and the screened interaction W, the BSE gives optical absorption including excitonic effects. The two-particle Hamiltonian acts in the space of electron-hole pairs (v,c,k) -> (v',c',k').

2. **BSE kernel construction.** The kernel has two parts:
   - **Direct (screened exchange):** Attractive electron-hole interaction via W. This binds excitons and produces absorption peaks below the quasiparticle gap.
   - **Exchange (bare Coulomb):** Repulsive contribution from the unscreened v. Responsible for singlet-triplet splitting (only singlet excitons are optically active in dipole approximation).
   - The static approximation W(omega=0) is standard and usually adequate. Dynamical BSE corrections are small (< 0.1 eV) for most systems but can matter for molecules and 2D systems.

3. **Tamm-Dancoff approximation (TDA).** Neglects coupling between resonant (positive frequency) and antiresonant (negative frequency) parts of the BSE. Valid when excitation energies are much smaller than twice the gap. For wide-gap insulators, TDA is excellent. For narrow-gap systems, metals, or when computing the full dielectric function (not just absorption), the full BSE may be needed.

4. **k-point convergence for BSE is critical.** The BSE requires a MUCH denser k-mesh than GW — typically 2-4x denser in each direction (8-64x more k-points). For exciton binding energies in 2D materials, extremely dense k-meshes (> 24x24) may be needed due to the long-range electron-hole interaction. Interpolation schemes (Wannier function interpolation) can reduce cost substantially.

5. **Convergence with number of bands.** Include enough valence and conduction bands to capture all relevant transitions. For optical absorption up to energy E, include bands up to at least 2E above the Fermi level. Convergence test: add more bands and verify the spectrum does not change in the energy range of interest.

## Step 6: Conserving Approximations (Baym-Kadanoff)

1. **Phi-derivable approximations.** An approximation for Sigma is called Phi-derivable if Sigma = delta Phi / delta G for some functional Phi[G]. Phi-derivable approximations automatically satisfy conservation laws: particle number, momentum, energy, and the Ward identities connecting self-energy to vertex function.

2. **GW is Phi-derivable.** The GW self-energy Sigma = iGW comes from Phi = -1/2 Tr[ln(1-vP)] where P = -iGG. This guarantees that fully self-consistent scGW satisfies all conservation laws. G0W0 does NOT — it violates conservation laws because G0 and W0 are computed from inconsistent input. This matters for total energies and transport properties.

3. **Beyond GW: vertex corrections.** The GW approximation sets the vertex function Gamma = 1. Including vertex corrections improves several properties:
   - **Satellite structure:** The cumulant expansion captures the series of plasmon satellites (multiple shake-up features) that single-pole GW misses entirely.
   - **Exchange-correlation in screening:** The vertex in the polarizability (P = -iGG*Gamma) improves the description of screening. The "vertex cancellation" (between self-energy and polarizability vertices) is partial, not exact — including only one vertex without the other worsens results.
   - **Electron-phonon coupling:** Deformation potential and Frohlich coupling enter through the electron-phonon vertex.

4. **Higher-order diagrammatic methods:** T-matrix (particle-particle ladder, good for pairing), FLEX (fluctuation exchange, treats particle-particle and particle-hole channels), and parquet (all channels simultaneously via crossing symmetry). These are systematically improvable but computationally demanding. Use when GW fails qualitatively: Mott transition, magnetic instabilities, superconducting pairing.

## Step 7: Verification Checklist

- [ ] **f-sum rule:** Integral of omega * Im[epsilon(omega)] over all frequencies equals (pi/2) * omega_p^2 (plasma frequency from total electron density). Violation indicates insufficient frequency range or basis set.
- [ ] **Kramers-Kronig consistency:** Re[Sigma(omega)] and Im[Sigma(omega)] must satisfy the Kramers-Kronig relation. Compute one from the other and compare. Discrepancy > 1% indicates frequency grid or analytic continuation issues.
- [ ] **Spectral weight conservation:** Integral of A(k, omega) over all omega equals 1 for each k-point and band. Deviation > 10^{-3} indicates missing high-energy spectral weight.
- [ ] **Quasiparticle weights:** 0 < Z_nk <= 1 for all states. Z < 0 or Z > 1 signals an error in the calculation or the linearization.
- [ ] **Starting-point test:** Compare G0W0 results from at least two functionals (LDA/PBE vs HSE06). If results differ by more than 0.3 eV, starting-point dependence is significant — use self-consistent GW or QSGW.
- [ ] **Basis set convergence:** Plot quasiparticle energies vs basis set size (number of empty states, dielectric cutoff). Extrapolate to complete basis set limit if feasible (1/N_bands extrapolation).
- [ ] **k-point convergence:** Systematic mesh refinement for both GW and BSE independently. For BSE, test at least three mesh densities.
- [ ] **Comparison to experiment:** Band gaps (photoemission + inverse photoemission), optical gaps (absorption onset), exciton binding energies, satellite positions and intensities.

## Worked Example: G0W0 Band Gap of Silicon

**Problem:** Compute the quasiparticle band gap of bulk silicon using G0W0 on top of DFT-PBE, and verify convergence with respect to empty states, dielectric cutoff, and frequency treatment. The experimental indirect band gap is 1.17 eV (Gamma -> X minimum). DFT-PBE gives ~0.6 eV. This example targets the most common GW errors: insufficient empty states, plasmon-pole inaccuracy, and confusing quasiparticle with optical gaps.

### Step 1: DFT Starting Point

DFT-PBE for Si (diamond structure, a = 5.43 Angstrom, 2 atoms/cell):
- Plane-wave cutoff: 50 Ry, norm-conserving pseudopotentials
- k-mesh: 8x8x8 Monkhorst-Pack, SCF converged to 10^{-10} Ry

DFT-PBE eigenvalues:

| k-point | VBM (eV) | CBM (eV) |
|---|---|---|
| Gamma_25' | 0.00 (ref) | -- |
| X_1 | -- | 0.62 |
| L_1 | -- | 1.54 |

PBE indirect gap: 0.62 eV (experiment: 1.17 eV). Underestimated by ~50%.

### Step 2: Empty States Convergence

Run G0W0 at 4x4x4 k-mesh with contour deformation, varying N_bands:

| N_bands | E_gap^{GW} (eV) | Delta from converged |
|---|---|---|
| 50 | 1.30 | +0.16 |
| 100 | 1.21 | +0.07 |
| 200 | 1.18 | +0.04 |
| 400 | 1.16 | +0.02 |
| 800 | 1.14 | reference |

Convergence is slow (~1/N_bands). Plot E_gap vs 1/N_bands, fit linear, extrapolate to get E_gap(N->inf) = 1.13(1) eV.

### Step 3: Frequency Treatment Comparison

| Method | E_gap (eV) |
|---|---|
| Plasmon-pole (Hybertsen-Louie) | 1.21 |
| Plasmon-pole (Godby-Needs) | 1.17 |
| Contour deformation (full freq) | 1.14 |

For Si, PPA overestimates by ~0.07 eV. Acceptable as an estimate, but contour deformation is the reference.

### Step 4: Quasiparticle Corrections

Final parameters: 6x6x6 k-mesh, 400 bands, contour deformation.

| State | E_PBE (eV) | Z | E_QP (eV) |
|---|---|---|---|
| Gamma_25' (VBM) | 0.00 | 0.78 | -0.21 |
| X_1 (CBM) | 0.62 | 0.79 | 0.93 |

G0W0 indirect gap: 0.93 - (-0.21) = 1.14 eV. Quasiparticle weights Z ~ 0.78 confirm the weakly correlated regime.

### Verification

1. **Quasiparticle weights:** Z = 0.78 (in range 0.7-0.85 for sp semiconductors). Z < 0 or Z > 1 signals an error.

2. **Starting-point test:** G0W0@LDA gives 1.12 eV, G0W0@PBE gives 1.14 eV. Spread of 0.02 eV confirms Si is not starting-point sensitive.

3. **f-sum rule:** Integral of Re[sigma(omega)] from 0 to 50 eV should equal pi*n*e^2/(2m). Violation > 5% indicates insufficient bands or frequency range.

4. **Experimental comparison:** Indirect gap 1.14 eV vs 1.17 eV (error: 0.03 eV, within G0W0 accuracy). Direct gap at Gamma: 3.3 eV vs 3.4 eV.

5. **Quasiparticle vs optical gap:** The GW gap (1.14 eV) is the transport gap. The optical gap from BSE would be ~1.0 eV (exciton binding ~0.15 eV for Si). Confusing these is a common error.

## Worked Example: BSE Optical Absorption of Monolayer MoS2 — k-Mesh Convergence Trap

**Problem:** Compute the optical absorption spectrum of monolayer MoS2 using the GW+BSE approach, demonstrating that the k-mesh requirements for BSE are far more stringent than for GW. Show that underconverged k-meshes produce artificially broadened exciton peaks, wrong binding energies, and missing fine structure. This targets the single most common error in BSE calculations: using the GW k-mesh for BSE without separate convergence testing.

### Step 1: DFT and GW Starting Point

DFT-PBE for monolayer MoS2 (1H phase, hexagonal lattice a = 3.16 Angstrom):
- Plane-wave cutoff: 60 Ry, fully relativistic PAW pseudopotentials (spin-orbit included)
- Vacuum separation: 20 Angstrom (to decouple periodic images in the out-of-plane direction)
- k-mesh for SCF: 18x18x1 Monkhorst-Pack

G0W0@PBE:
- 300 empty bands (10x occupied)
- Dielectric cutoff: 10 Ry
- Contour deformation for frequency integration
- k-mesh: 12x12x1 (sufficient for GW — convergence within 0.05 eV)

GW quasiparticle gap: 2.72 eV (direct gap at K). DFT-PBE gap: 1.67 eV. Experimental optical gap: 1.88 eV (the difference from the GW gap is the exciton binding energy).

### Step 2: BSE at Multiple k-Meshes

Run BSE with static W, Tamm-Dancoff approximation, including 4 valence + 4 conduction bands:

| k-mesh | E_A exciton (eV) | E_B exciton (eV) | E_binding (eV) | Linewidth (meV) |
|--------|-----------------|-----------------|----------------|-----------------|
| 6x6x1 | 2.15 | 2.52 | 0.57 | 280 |
| 12x12x1 | 1.98 | 2.32 | 0.74 | 120 |
| 18x18x1 | 1.92 | 2.25 | 0.80 | 60 |
| 24x24x1 | 1.90 | 2.23 | 0.82 | 35 |
| 30x30x1 | 1.89 | 2.22 | 0.83 | 25 |
| 36x36x1 | 1.89 | 2.22 | 0.83 | 20 |

**Convergence is reached at 30x30x1 for the A exciton energy but 24x24x1 for the binding energy.** The 6x6x1 mesh (same as a typical GW mesh for bulk systems) gives a binding energy of 0.57 eV — 30% too low. The exciton energy is 0.26 eV too high.

**Why BSE needs a much denser mesh than GW:** The exciton wavefunction in reciprocal space extends over a region of size ~1/a_exciton around the K point, where a_exciton ~ 1 nm is the exciton Bohr radius. To resolve this structure, the k-spacing must be smaller than 1/a_exciton. For a_exciton = 1 nm and a = 3.16 Angstrom: need Delta k < 2 pi / (10 Angstrom) ~ 0.6 Angstrom^{-1}, which at a = 3.16 Angstrom requires N_k > 2 pi / (a * 0.6) ~ 33 in each direction. GW self-energies are smoother functions of k and converge much faster.

### Step 3: The 2D Coulomb Divergence

In 2D materials, the head of the Coulomb interaction v(q) = 2 pi e^2 / q diverges as q->0. This divergence must be handled correctly:

1. **Truncated Coulomb interaction.** Cut off the Coulomb interaction at z = L/2 (half the vacuum separation) to eliminate artificial interlayer coupling from periodic images. Without truncation: the exciton binding energy depends on the vacuum separation (unphysical).
2. **Non-uniform q-grid.** The divergence at q->0 requires special treatment. Standard approaches: analytical integration of the q->0 contribution (Ismail-Beigi), mini-BZ averaging, or adaptive q-mesh refinement near Gamma.
3. **Convergence test with vacuum.** Double the vacuum from 20 to 40 Angstrom. The exciton energy should change by less than 0.02 eV with truncated Coulomb. Without truncation: the change can be > 0.2 eV.

### Step 4: Spin-Orbit Splitting

MoS2 has strong spin-orbit coupling from the Mo d-orbitals. The valence band at K splits by Delta_SO = 150 meV, producing two exciton series:
- **A exciton:** transition from the upper valence band (VB1) to the conduction band. E_A = 1.89 eV.
- **B exciton:** transition from the lower valence band (VB2) to the conduction band. E_B = 2.22 eV.

The A-B splitting should be approximately Delta_SO + corrections from the electron-hole exchange: E_B - E_A = 0.33 eV (vs bare SOC splitting of 0.15 eV — the difference comes from different exciton binding energies for A and B).

Without spin-orbit coupling in the DFT starting point: the A and B excitons are degenerate, and the spectrum is qualitatively wrong. This is a common error for transition metal dichalcogenides.

### Verification

1. **k-mesh convergence plot.** Plot the A exciton energy vs 1/N_k. The data should converge smoothly (no oscillations). If oscillations are present, the Brillouin zone sampling has an issue (check the high-symmetry point alignment).

2. **Binding energy.** E_b = E_QP_gap - E_optical = 2.72 - 1.89 = 0.83 eV. Experimental: 0.44 eV (with substrate screening) to 0.96 eV (suspended, theory). The large binding energy is characteristic of 2D materials due to reduced screening. If E_b < 0.3 eV, the BSE k-mesh is too coarse (the exciton wavefunction is not resolved).

3. **Exciton wavefunction in real space.** Fourier-transform the BSE eigenvector to get the electron-hole pair distribution |Psi(r_e - r_h)|^2. For the A exciton: it should be approximately hydrogenic with radius ~ 1 nm. If the wavefunction is delocalized over the entire supercell, the k-mesh is too coarse (the exciton is an artifact of the discrete k-grid, not a bound state).

4. **Sum rule.** The oscillator strength must satisfy the Thomas-Reiche-Kuhn sum rule: sum of f_n over all exciton states = N_electrons. Partial sum up to a cutoff energy gives a lower bound that can be checked against the independent-particle result.

5. **Comparison with experiment.** Photoluminescence: A exciton at 1.88 eV (monolayer on SiO2). Absorption: A peak at 1.88 eV, B peak at 2.04 eV. Our BSE result (1.89 eV for A) is for a freestanding monolayer — the substrate red-shifts by ~0.01 eV (small for SiO2). Agreement within 0.02 eV validates the calculation.

6. **GW mesh vs BSE mesh.** Verify that using 12x12x1 for GW but 30x30x1 for BSE gives the same result as using 30x30x1 for both. The GW self-energy can be interpolated from the coarser mesh to the finer BSE mesh (Wannier interpolation). If the interpolated and direct results differ by > 0.05 eV, the GW mesh is too coarse for reliable interpolation.

## Worked Example: Self-Energy Double-Counting in G0W0 Correction to ZnO — The V_xc Subtraction Error

**Problem:** Compute the quasiparticle band gap of wurtzite ZnO using G0W0@PBE and identify the double-counting error that arises when the DFT exchange-correlation potential V_xc is not properly subtracted from the GW self-energy. ZnO is chosen because its deep Zn 3d states interact strongly with the O 2p valence band, making the double-counting error large and clearly detectable. The experimental fundamental gap is 3.44 eV; DFT-PBE gives 0.73 eV.

### Step 1: Correct Dyson Equation

The quasiparticle energy is:
E_nk = epsilon_nk + Z_nk * Re[Sigma_nk(epsilon_nk) - V_xc_nk]

The crucial term is (Sigma - V_xc). The GW self-energy Sigma replaces the DFT exchange-correlation potential V_xc. Subtracting V_xc prevents double-counting: the DFT eigenvalue epsilon_nk already includes V_xc, so adding the full Sigma without subtracting V_xc would count exchange-correlation twice.

Matrix elements needed:
- Sigma_nk = <psi_nk| Sigma(epsilon_nk) |psi_nk> (GW self-energy, complex and frequency-dependent)
- V_xc_nk = <psi_nk| V_xc |psi_nk> (DFT xc potential, real and static)

### Step 2: The Error — Omitting V_xc Subtraction

A common implementation error: computing E_nk = epsilon_nk + Z_nk * Re[Sigma_nk] without subtracting V_xc. This double-counts exchange-correlation because epsilon_nk already contains V_xc contributions.

Results for ZnO (4x4x4 k-mesh, 200 bands, contour deformation):

| Quantity | Correct (Sigma - V_xc) | Wrong (Sigma only) | Difference |
|---|---|---|---|
| VBM correction (eV) | -0.82 | -4.15 | 3.33 |
| CBM correction (eV) | +1.89 | -1.42 | 3.31 |
| QP gap (eV) | 3.44 | 0.00 | 3.44 |
| Zn 3d position (eV) | -7.5 | -12.8 | 5.3 |

The wrong result gives a QP gap of ~0 eV (barely improved from DFT) because both VBM and CBM shift down by similar amounts. The Zn 3d states are shifted 5 eV too deep because V_xc for the localized d-states is large and negative.

### Step 3: Diagnosing the Error

Three signatures that V_xc subtraction is missing or incorrect:

1. **GW corrections are uniformly negative.** In the correct calculation, valence states shift down and conduction states shift up (opening the gap). If all corrections are negative, the missing V_xc term is pulling everything down.

2. **The gap barely changes from DFT.** Without V_xc subtraction, the correction to each state is Sigma_nk (not Sigma_nk - V_xc). Since Sigma and V_xc have similar magnitudes for occupied states, the net correction is small but wrong.

3. **d-state positions are far from experiment.** For ZnO, the Zn 3d peak is at -7.5 to -8.0 eV below VBM experimentally. Without V_xc subtraction, it lands at -12 to -13 eV because the PBE V_xc for these states is large (~5 eV) and is being double-counted.

### Step 4: A Subtler Variant — Wrong V_xc Functional

Even when V_xc is subtracted, using the wrong functional introduces systematic errors. If the GW calculation was run on top of PBE but V_xc is computed with LDA (or vice versa):

| Scenario | Gap (eV) | Error vs correct |
|---|---|---|
| G0W0@PBE, subtract V_xc^PBE (correct) | 3.44 | reference |
| G0W0@PBE, subtract V_xc^LDA (wrong) | 3.21 | -0.23 |
| G0W0@PBE, subtract V_xc^PBE0 (wrong) | 3.82 | +0.38 |
| G0W0@PBE, no V_xc subtraction | 0.00 | -3.44 |

The mismatch between the functional used for the DFT calculation and the one used for V_xc subtraction typically causes errors of 0.2-0.4 eV. For ZnO this is comparable to other sources of error, but for systems with a smaller gap it can flip the sign of the correction.

### Verification

1. **Sum rule on corrections.** For a given k-point, the sum of quasiparticle corrections over all occupied states should be close to the sum over unoccupied states (with opposite sign), up to the change in total exchange-correlation energy. Large asymmetry signals a double-counting issue.

2. **Check V_xc matrix elements directly.** Print <psi_nk|V_xc|psi_nk> for each state. For valence states, V_xc should be negative (typically -5 to -15 eV for PBE). For conduction states, V_xc is smaller in magnitude. If V_xc is exactly zero for all states, the subtraction is not being performed.

3. **Compare Sigma and V_xc magnitudes.** For occupied states: Re[Sigma] and V_xc should be similar in magnitude (both negative, both order 5-15 eV). Their difference (the QP correction) should be order 1 eV. If the QP correction is order 5-15 eV, one of them is missing.

4. **Experimental comparison.** ZnO fundamental gap: 3.44 eV. Zn 3d binding energy: 7.5-8.0 eV below VBM. O 2s: ~20 eV below VBM. If any of these deviate by > 1 eV, suspect the V_xc subtraction.

5. **Code-level check.** In the self-energy output, verify that the reported correction is (Sigma - V_xc), not Sigma alone. Most GW codes (BerkeleyGW, VASP, Yambo, WEST) print both Sigma and V_xc separately — verify their difference matches the reported QP shift.

## Common Pitfalls

- **Insufficient empty states.** The single most common source of error. GW convergence with empty states is slow (1/N_empty for the self-energy). Use at least 10x the occupied states; for accurate absolute band positions, 100x or more. Extrapolation to infinite empty states (plot vs 1/N_bands, fit linear, extrapolate) can help significantly.
- **Neglecting frequency dependence of W.** The plasmon-pole approximation fails for d-electron systems (Cu, Ni, Fe), systems with multiple plasmon branches, and core-level spectroscopy. Always validate against full-frequency for new classes of materials.
- **Analytic continuation artifacts.** Spurious peaks from Pade approximants can be mistaken for physical satellites. Cross-check with contour deformation or MaxEnt. If a feature appears with Pade but not MaxEnt (or vice versa), treat it as suspect until confirmed by a third method.
- **GW total energies are NOT variational.** The GW total energy from the Galitskii-Migdal formula is not a minimum — it can be above or below the true ground state energy. Do not use it for structural optimization without extreme care and benchmarking.
- **Spin-orbit coupling.** For heavy elements (Z > 50), spin-orbit coupling can split bands by > 1 eV and qualitatively change the band topology (topological insulators, Rashba splitting). Include SOC in the DFT starting point when relevant — adding SOC perturbatively after GW is less reliable.
- **Wrong Brillouin zone sampling for BSE.** The BSE needs a much finer k-mesh than GW. Using the GW k-mesh for BSE will give unconverged exciton binding energies and wrong optical spectra. Test k-convergence separately for GW and BSE.
- **Confusing quasiparticle gap with optical gap.** The quasiparticle gap (from GW) is the transport gap: E_gap = IP - EA. The optical gap (from BSE) is lower by the exciton binding energy: E_opt = E_gap - E_b. These can differ by 0.1 eV (bulk Si) to > 1 eV (molecular crystals, 2D materials).
- **Core-valence partitioning errors.** The frozen-core approximation (excluding deep core states from the GW calculation) is standard but can introduce errors of 0.1-0.3 eV for absolute band positions. For relative band gaps this usually cancels, but verify for systems with shallow core states (e.g., 3d semicore in Ga, Zn).

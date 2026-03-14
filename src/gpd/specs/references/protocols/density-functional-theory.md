---
load_when:
  - "DFT"
  - "density functional"
  - "Kohn-Sham"
  - "exchange-correlation"
  - "band gap"
  - "pseudopotential"
  - "electronic structure"
tier: 2
context_cost: medium
---

# Density Functional Theory Protocol

DFT is exact in principle but approximate in practice: the exchange-correlation functional is unknown, and the choice of functional, pseudopotential, and numerical parameters can each introduce errors larger than the physical effect being studied. This protocol ensures systematic convergence and appropriate functional selection.

## Related Protocols
- `symmetry-analysis.md` — Crystal symmetries, space groups, Wyckoff positions
- `variational-methods.md` — DFT as a variational method
- `numerical-computation.md` — Convergence testing for k-points, cutoffs, grids

## Step 1: Functional Selection

1. **Know the Jacob's ladder.** Functionals are ordered by accuracy and cost:
   - **LDA** (local density): Uniform electron gas. Overbinds. Use only for qualitative trends or metallic systems where it is surprisingly good.
   - **GGA** (PBE, PBEsol, BLYP): Semi-local. PBE for general use, PBEsol for solids/lattice constants. Underestimates band gaps by 30-50%.
   - **meta-GGA** (SCAN, r2SCAN, TPSS): Includes kinetic energy density. SCAN satisfies all 17 known exact constraints. Better for diverse chemistry.
   - **Hybrid** (PBE0, HSE06, B3LYP): Mix exact exchange. HSE06 for solids (screened exchange avoids divergence). B3LYP for molecules (NOT for solids). Band gaps improved but still typically underestimated by 10-20%.
   - **Double hybrid** (B2PLYP): Adds MP2 correlation. Most accurate for molecular thermochemistry. Too expensive for periodic systems.
2. **Match the functional to the physics:**
   - Metallic systems: PBE or PBEsol (hybrids can have convergence issues with metals)
   - Semiconductors/insulators band gaps: HSE06 or GW@PBE
   - Strongly correlated (transition metal oxides, Mott insulators): DFT+U or hybrid functionals. State the U value and how it was determined (self-consistent linear response, fitted to experiment, or literature value with citation).
   - Van der Waals bound systems: Add explicit vdW correction (DFT-D3, DFT-D4, vdW-DF, MBD). Standard DFT has NO long-range dispersion.
   - Molecular thermochemistry: B3LYP or double hybrids with appropriate basis set.
3. **Never use LDA or plain GGA for:** band gap predictions, van der Waals complexes, reaction barriers (underestimated by GGA), charge transfer states, or strongly correlated systems.

## Step 2: Pseudopotential / Basis Set

1. **Pseudopotentials (plane-wave codes):** Use well-tested libraries (SSSP, PseudoDojo, GBRV). For each element, verify the pseudopotential was tested for the property of interest. Check: are semicore states included? For transition metals and lanthanides, semicore states are often essential.
2. **Plane-wave cutoff convergence.** Increase E_cut systematically. Plot total energy (or the target property: forces, stress, phonon frequencies) vs E_cut. Converge to within the target accuracy (typically 1 meV/atom for energetics). The cutoff must be converged for EVERY element in the system — the hardest element sets the cutoff.
3. **Gaussian basis sets (molecular codes):** Use correlation-consistent basis sets (cc-pVnZ, aug-cc-pVnZ) and extrapolate to the complete basis set (CBS) limit. For DFT: triple-zeta is usually sufficient. For post-DFT (RPA, GW): larger bases needed.
4. **Basis set superposition error.** Same issue as in variational methods — use counterpoise correction for interaction energies computed with finite basis sets.

## Step 3: k-Point Convergence

1. **Increase k-mesh density systematically.** Use Monkhorst-Pack grids. Test: NxNxN, (N+2)x(N+2)x(N+2), etc. Converge the total energy to < 1 meV/atom. Different properties converge at different rates — forces and stress tensors may need denser k-meshes than total energies.
2. **Metals require denser k-meshes** than insulators (Fermi surface sampling). Use Methfessel-Paxton or Marzari-Vanderbilt smearing with explicit convergence test vs smearing width.
3. **Symmetry reduction.** Use crystal symmetries to reduce the k-point count. Verify the symmetry-reduced mesh gives the same result as the full mesh to within numerical precision.
4. **Gamma-point-only calculations** are acceptable only for large supercells where the k-point spacing is already fine enough. For the primitive cell: always use a converged k-mesh.

## Step 4: Self-Consistency and Convergence

1. **SCF convergence threshold.** Total energy converged to at least 10^{-6} eV. For forces: 10^{-8} eV. If SCF does not converge: try mixing schemes (Pulay, Broyden, Kerker), reduce mixing parameter, increase number of empty bands, use smearing.
2. **Magnetic state initialization.** For magnetic systems, the SCF can converge to different magnetic states depending on the initial spin configuration. Initialize with the expected magnetic order (ferromagnetic, antiferromagnetic, ferrimagnetic) AND try alternative orderings. Report the lowest-energy solution.
3. **Charge sloshing in slabs/surfaces.** Metallic slabs with vacuum can exhibit charge sloshing that prevents SCF convergence. Use dipole corrections and Kerker preconditioning.
4. **Spin-orbit coupling.** For heavy elements (Z > 50), spin-orbit effects can qualitatively change band structures (topological insulators, Rashba splitting). Include SOC when relevant and verify it changes results by more than the target accuracy.

## Step 5: Band Gap Corrections

1. **The DFT band gap problem.** Kohn-Sham eigenvalues are NOT quasiparticle energies. The KS gap systematically underestimates the true gap. This is not a bug — it is a fundamental limitation of KS-DFT.
2. **Scissors operator.** Rigid shift of conduction bands. Cheap but crude. Only valid when the gap error is uniform across k-space (rarely true).
3. **GW approximation.** G0W0@PBE or self-consistent GW. The standard for quasiparticle band structures. Verify convergence with: number of empty bands, frequency grid, k-mesh, and basis set. G0W0 results depend on the starting functional — try G0W0@PBE and G0W0@HSE06 to assess sensitivity.
4. **DFT+U for correlated systems.** Adds an on-site Hubbard U to localized orbitals (d or f). U is NOT a free parameter — determine it self-consistently (linear response) or cite the source. Different U values can give qualitatively different ground states (metal vs insulator). Always report U and the method used to determine it.

## Step 6: van der Waals Corrections

1. **DFT-D3/D4 (Grimme).** Pairwise additive dispersion with damping function. DFT-D4 includes charge-dependent coefficients. Cheap and effective for molecular crystals, layered materials, physisorption. But: pairwise additivity fails for metallic systems and confined geometries.
2. **Many-body dispersion (MBD).** Includes screening and many-body effects. Better for polarizable systems, metallic surfaces, and dense materials. More expensive than D3/D4.
3. **vdW-DF family.** Non-local correlation functionals. Self-consistent, no empirical parameters. But: different vdW-DF versions give different results (vdW-DF, vdW-DF2, optB88-vdW). State which version.
4. **When vdW matters:** Layered materials (graphite, MoS2), molecular crystals, polymer conformations, surface adsorption, noble gas solids. When it does NOT matter: covalent/ionic bonding, metallic bonding (dominated by electronic contribution).

## Common Pitfalls

- **Wrong functional for strongly correlated systems.** GGA predicts FeO, CoO, NiO to be metals — they are Mott insulators. Use DFT+U or hybrid functionals for any system with partially filled d or f shells.
- **Insufficient k-mesh.** Phonon calculations, elastic constants, and Fermi surface properties are much more sensitive to k-mesh than total energy. Always converge the target property, not just the energy.
- **DFT+U parameter sensitivity.** U = 3 eV and U = 5 eV for the same material can give different magnetic ground states, different band gaps, and different structural predictions. Perform a U scan and report the sensitivity.
- **Comparing absolute energies across different codes/pseudopotentials.** Absolute DFT energies are meaningless — only energy DIFFERENCES within the same setup are physical. Never compare total energies from VASP with total energies from Quantum ESPRESSO.
- **Neglecting zero-point energy.** For light elements (H, Li) and phase stability comparisons at low temperature, zero-point phonon energy can exceed the energy differences between phases.

## Concrete Example: Wrong Magnetic Ground State From Wrong Functional

**Problem:** Determine the magnetic ground state of NiO using DFT.

**Wrong approach (common LLM error):** Use PBE (standard GGA) and find that NiO is a nonmagnetic metal with zero band gap. "PBE predicts NiO to be metallic."

NiO is experimentally a type-II antiferromagnetic insulator with a gap of 4.3 eV. PBE getting this completely wrong is a KNOWN limitation, not a result to report.

**Correct approach:**

Step 1. **Recognize the system is strongly correlated.** Ni^{2+} has a partially filled d-shell (d^8). Standard GGA fails for systems with localized d or f electrons. Use DFT+U or a hybrid functional.

Step 2. **DFT+U calculation:**
```
Functional: PBE+U with U_eff = 6.3 eV on Ni-d (from linear response)
k-mesh: 8x8x8 (converge to within 1 meV/atom)
Magnetic ordering: Initialize AF-II (alternating (111) planes)
```
Result: AF-II insulator with gap = 3.1 eV, magnetic moment = 1.7 mu_B per Ni.

Step 3. **Convergence and sensitivity tests:**
```
| Method       | Gap (eV) | Moment (mu_B) | Expt   |
|-------------|----------|----------------|--------|
| PBE          | 0 (metal)| 0              | ---    |
| PBE+U (4 eV)| 1.8      | 1.5            |        |
| PBE+U (6 eV)| 3.0      | 1.7            |        |
| PBE+U (8 eV)| 4.2      | 1.8            |        |
| HSE06        | 4.1      | 1.6            |        |
| Experiment   | 4.3      | 1.7-1.9        | target |
```

Step 4. **Report honestly:** "PBE+U with U_eff = 6.3 eV gives a gap of 3.1 eV and moment of 1.7 mu_B. HSE06 gives 4.1 eV. Both correctly predict the AF-II insulating ground state. The gap is sensitive to U (range 1.8-4.2 eV for U = 4-8 eV), reflecting the systematic uncertainty of DFT+U."

**The typical LLM error** either reports the PBE metallic result as a "prediction" (ignoring the known GGA failure for correlated systems), or uses DFT+U with an arbitrary U without justifying or scanning U values.

## Worked Example: K-Point Convergence Failure for a Metallic Surface

**Problem:** Compute the surface energy of Al(111) using PBE with a slab model. This targets the LLM error class of using an insufficiently dense k-mesh for metallic systems, where the Fermi surface sampling error dominates all other errors but is invisible without a convergence test.

### Step 1: Slab Setup

- 7-layer Al(111) slab with 15 A vacuum
- PBE functional, ultrasoft pseudopotential (SSSP library)
- Plane-wave cutoff: 30 Ry (converged for Al)
- Methfessel-Paxton smearing, sigma = 0.02 Ry

The surface energy is:

```
gamma = (E_slab - N * E_bulk) / (2 * A)
```

where N is the number of atoms, E_bulk is the bulk energy per atom, and A is the surface area. The factor of 2 accounts for two surfaces.

### Step 2: K-Point Convergence (the Critical Test)

**The common LLM error:** Use a 4x4x1 k-mesh (typical for semiconductors) and report the result as converged.

For Al (a metal), the Fermi surface must be resolved. Convergence test:

```
| k-mesh  | E_slab (eV)     | E_bulk (eV/atom) | gamma (J/m^2) |
|---------|-----------------|-------------------|---------------|
| 4x4x1  | -947.3821       | -135.2142         | 1.42          |
| 6x6x1  | -947.4156       | -135.2189         | 0.89          |
| 8x8x1  | -947.4098       | -135.2183         | 0.93          |
| 12x12x1| -947.4112       | -135.2185         | 0.91          |
| 16x16x1| -947.4115       | -135.2185         | 0.91          |
| 20x20x1| -947.4115       | -135.2185         | 0.91          |
```

The surface energy at 4x4x1 (1.42 J/m^2) is **56% too large**. The result is not converged until 12x12x1 or denser. The experimental value is 1.14 J/m^2 (PBE systematically underestimates, but the converged value 0.91 J/m^2 is in the right ballpark for PBE).

### Step 3: Smearing Convergence

The smearing width sigma also affects metallic systems. Too large: artificial electronic temperature smears the Fermi surface. Too small: k-mesh must be even denser.

```
| sigma (Ry) | gamma (J/m^2) at 12x12x1 |
|------------|---------------------------|
| 0.05       | 0.88                      |
| 0.02       | 0.91                      |
| 0.01       | 0.91                      |
| 0.005      | 0.91 (but SCF slower)     |
```

sigma = 0.02 Ry is adequate. At sigma = 0.05, there is a noticeable smearing artifact (3% error).

### Step 4: Slab Thickness Convergence

The slab must be thick enough that the interior atoms have bulk-like properties:

```
| N_layers | gamma (J/m^2) at 12x12x1 |
|----------|---------------------------|
| 3        | 1.15                      |
| 5        | 0.96                      |
| 7        | 0.91                      |
| 9        | 0.90                      |
| 11       | 0.90                      |
```

Converged at 7-9 layers. The 3-layer result has 28% error — the quantum confinement effects in thin slabs produce spurious oscillations in the surface energy (quantum size effect).

### Verification

1. **Experimental comparison.** gamma_expt(Al 111) = 1.14 J/m^2. PBE gives 0.90 J/m^2 (21% below). This systematic underestimate is KNOWN for PBE surfaces — PBE underestimates cohesive energies and surface energies of metals. Report the PBE value honestly; do not adjust to match experiment.

2. **Work function cross-check.** The work function Phi = V_vacuum - E_Fermi should converge at the same k-mesh as the surface energy. Phi(Al 111) = 4.2 eV (experiment), PBE gives 4.0-4.1 eV. If your work function is far off, the slab calculation has a bug.

3. **Bulk energy consistency.** E_bulk from the slab interior (force-relaxed central layer) should match E_bulk from an independent bulk calculation. Discrepancy > 1 meV/atom indicates insufficient slab thickness or vacuum.

4. **Error budget:**
```
Surface energy: 0.90 J/m^2
  k-mesh convergence:           +/- 0.01
  Slab thickness (7 vs 11 layers): +/- 0.01
  Smearing:                     +/- 0.01
  Functional error (PBE):       ~ -0.24 (systematic, not statistical)
  Total numerical:              +/- 0.02 J/m^2
```

The dominant error is the functional choice (PBE), not the numerical parameters. An LLM that reports gamma = 1.42 J/m^2 from a 4x4 k-mesh has a numerical error larger than the functional error — the convergence test catches this immediately.

## Worked Example: Band Gap of Silicon — The DFT Gap Problem

**Problem:** Compute the electronic band gap of silicon and demonstrate why standard DFT (LDA/GGA) systematically underestimates the gap, while hybrid functionals and GW corrections give the correct value. This targets the most common DFT misconception: treating Kohn-Sham eigenvalue differences as physical excitation energies.

### Step 1: The Fundamental Issue

The Kohn-Sham (KS) band gap is:

```
E_gap^KS = epsilon_{CBM} - epsilon_{VBM} (difference of KS eigenvalues)
```

The physical (quasiparticle) gap is:

```
E_gap^QP = I - A = (E(N-1) - E(N)) - (E(N) - E(N+1))
```

where I is the ionization energy and A is the electron affinity. These are NOT the same. The difference:

```
E_gap^QP = E_gap^KS + Delta_xc
```

where Delta_xc is the derivative discontinuity of the exchange-correlation functional. For LDA and GGA: Delta_xc ~ 0.5-1.5 eV for typical semiconductors. This is NOT a numerical error — it is a fundamental limitation of the KS eigenvalue interpretation.

**The LLM error:** "Run DFT with PBE, report the band gap." This gives a KS gap that is systematically 30-50% below the experimental gap. The error is not fixable by increasing k-points, cutoff, or any numerical parameter.

### Step 2: Converged PBE Calculation

Silicon: FCC diamond structure, a_exp = 5.431 Angstrom, space group Fd-3m.

**Convergence study at PBE level:**

| E_cut (eV) | k-grid | E_gap (eV) | Total energy (eV/atom) |
|------------|--------|------------|------------------------|
| 300 | 4x4x4 | 0.58 | -5.420 |
| 400 | 4x4x4 | 0.61 | -5.424 |
| 500 | 4x4x4 | 0.62 | -5.425 |
| 500 | 6x6x6 | 0.61 | -5.425 |
| 500 | 8x8x8 | 0.61 | -5.425 |
| 500 | 12x12x12 | 0.61 | -5.425 |

Converged PBE gap: E_gap^PBE = 0.61 eV. Experimental gap: E_gap^exp = 1.17 eV (indirect, Gamma -> X). The PBE value is 48% too low.

**This is NOT a convergence failure.** The gap is fully converged in k-points and cutoff energy. The 0.56 eV discrepancy is the derivative discontinuity Delta_xc.

### Step 3: Lattice Constant Optimization

Before computing the gap, optimize the lattice constant:

| Functional | a_opt (Angstrom) | Error vs exp |
|-----------|------------------|--------------|
| LDA | 5.403 | -0.5% |
| PBE | 5.467 | +0.7% |
| PBEsol | 5.431 | 0.0% |
| Experiment | 5.431 | -- |

Use the optimized lattice constant for each functional (not the experimental one). Computing the band gap at the wrong lattice constant introduces an additional error of ~0.1 eV per 1% strain.

### Step 4: Beyond-DFT Corrections

| Method | E_gap (eV) | Cost relative to PBE | Error vs exp |
|--------|-----------|---------------------|--------------|
| LDA | 0.52 | 1x | -56% |
| PBE | 0.61 | 1x | -48% |
| HSE06 (hybrid) | 1.15 | 10-50x | -2% |
| G0W0@PBE | 1.12 | 100-500x | -4% |
| scGW | 1.20 | 1000x | +3% |
| Experiment | 1.17 | -- | 0% |

**HSE06 (hybrid functional):** Mixes 25% exact exchange with 75% PBE exchange + PBE correlation. The exact exchange partially corrects the derivative discontinuity. HSE06 gives gaps within 0.1-0.2 eV for most semiconductors without any adjustable parameters.

**G0W0 (GW approximation):** Perturbative correction to PBE eigenvalues using the screened Coulomb interaction. The most systematic approach: it computes the self-energy Sigma(omega) and gives the quasiparticle energies directly. The starting-point dependence (PBE vs LDA vs HSE) is ~0.1-0.2 eV.

### Step 5: Band Structure Along High-Symmetry Path

Compute the band structure along Gamma-X-W-K-Gamma-L at PBE and HSE06:

```
PBE:   VBM at Gamma, CBM near X (0.85 along Gamma-X). Indirect gap: 0.61 eV. Direct gap at Gamma: 2.56 eV.
HSE06: VBM at Gamma, CBM near X (0.85 along Gamma-X). Indirect gap: 1.15 eV. Direct gap at Gamma: 3.32 eV.
Expt:  Indirect gap: 1.17 eV. Direct gap at Gamma: 3.40 eV.
```

HSE06 corrects both the indirect and direct gaps with roughly the same shift (~0.55 eV). This is expected — the derivative discontinuity is approximately constant across the Brillouin zone for simple semiconductors.

### Verification

1. **Symmetry check.** Silicon has diamond symmetry (Oh). The VBM at Gamma is triply degenerate (Gamma_25' representation). The CBM near X is singly degenerate (Delta_1). Verify the degeneracies from the calculation. If the VBM is not triply degenerate, the pseudopotential may not be treating spin-orbit coupling correctly (for Si, spin-orbit splitting is small, ~44 meV, but it should be present).

2. **Effective mass cross-check.** The electron effective mass at the CBM: m*/m_e = 0.19 (transverse), 0.92 (longitudinal) experimentally. Compute from the band curvature at PBE and HSE06. PBE gives m*_t ~ 0.19, m*_l ~ 0.91 (good agreement — effective masses are less sensitive to the gap error than the gap itself). If the effective mass is wrong by > 20%, the k-mesh is too coarse near the CBM.

3. **Dielectric constant.** The electronic dielectric constant epsilon_inf can be computed from the KS eigenvalues via the RPA. PBE gives epsilon_inf ~ 13.0 (experiment: 11.9). The overestimate is consistent with the underestimated gap (smaller gap -> larger polarizability). HSE06 gives epsilon_inf ~ 11.8 (within 1% of experiment).

4. **Known value table.** Compare with published computational results (e.g., Heyd, Scuseria, Ernzerhof 2003 for HSE; Shishkin and Kresse 2007 for GW):

| Method | Published gap (eV) | Your gap (eV) | Agreement? |
|--------|-------------------|---------------|------------|
| PBE | 0.61 | 0.61 | Yes |
| HSE06 | 1.14 | 1.15 | Yes (within 0.01) |
| G0W0@PBE | 1.12 | -- | -- |

If your PBE gap deviates from 0.61 by more than 0.02 eV, check: pseudopotential (norm-conserving vs PAW, version), basis set convergence, lattice constant used, k-mesh.

5. **Do NOT "fix" the PBE gap.** The 0.61 eV is the correct PBE result. Adjusting it with a scissors operator (rigid shift of conduction bands) is ad hoc and should be clearly labeled. The physically motivated correction is to use a higher-level method (HSE06, GW), not to fudge the PBE result.

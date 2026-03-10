---
load_when:
  - "soft matter verification"
  - "polymer physics"
  - "colloid"
  - "membrane"
  - "molecular dynamics verification"
  - "coarse-grained model"
  - "biophysics simulation"
  - "active matter"
  - "self-assembly"
tier: 2
context_cost: large
---

# Verification Domain — Soft Matter & Biophysics

Equilibration, thermodynamic consistency, scaling law verification, force field validation, finite-size analysis, and simulation correctness checks for soft matter and biological physics.

**Load when:** Working on polymer physics, colloidal systems, membranes, molecular dynamics, coarse-grained models, active matter, biophysics simulations, or self-assembly.

**Related files:**
- `../core/verification-quick-reference.md` — compact checklist (default entry point)
- `../core/verification-core.md` — dimensional analysis, limiting cases, conservation laws
- `../core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `references/verification/domains/verification-domain-statmech.md` — statistical mechanics (partition functions, phase transitions)
- `references/verification/domains/verification-domain-condmat.md` — condensed matter (order parameters, symmetry breaking)

---

<equilibration_verification>

## Equilibration and Sampling Verification

The most common error in soft matter simulations is drawing conclusions from non-equilibrated systems.

**Energy and structural convergence:**

```
A system is equilibrated when ALL of the following hold:
1. Total energy E(t) has no drift (constant mean over last half of trajectory)
2. Pressure P(t) has no drift
3. Structural observables (R_g, g(r), nematic order) have no drift
4. Multiple independent runs from different initial conditions converge to the same values

Verification:
1. COMPUTE: Split trajectory into 5 blocks. Compute mean of observable in each block.
   If means show a monotonic trend: NOT equilibrated. Need longer equilibration.
2. COMPUTE: Autocorrelation time tau_auto of slowest observable.
   Production run must be >> 100 * tau_auto for reliable statistics.
3. For polymers: tau_auto ~ tau_Rouse = N^2 * tau_monomer (unentangled) or
   tau_auto ~ tau_rep = N^3.4 * tau_e (entangled). If run length < 10 * tau_auto: insufficient sampling.
```

**Autocorrelation analysis:**

```
Autocorrelation function: C(t) = <A(0)A(t)> - <A>^2 / (<A^2> - <A>^2)
Autocorrelation time: tau_auto = integral_0^inf C(t) dt

Effective number of independent samples: N_eff = N_total / (2 * tau_auto)
Statistical error: sigma = sqrt(Var(A) / N_eff)

Verification:
1. COMPUTE: tau_auto for the target observable. If tau_auto > run_length / 10:
   simulation is too short for reliable statistics.
2. COMPUTE: error bars using block averaging with block size >> tau_auto.
   Block averages should be normally distributed (check with Shapiro-Wilk test).
3. Compare: error from block averaging vs error from multiple independent runs.
   Must agree within a factor of 2; large disagreement indicates non-stationary statistics.
```

</equilibration_verification>

<thermodynamic_verification>

## Thermodynamic Consistency Checks

**Equipartition theorem:**

```
For a system at temperature T in thermal equilibrium:
  <(1/2) m v_i^2> = (1/2) k_BT  for each velocity component i

Kinetic temperature: T_kin = (2/3) * <E_kin> / (N * k_B)

Verification:
1. COMPUTE: T_kin from simulation. Must equal thermostat target temperature to within 1%.
   Deviation > 5%: thermostat coupling too weak or system not equilibrated.
2. For constrained systems (SHAKE/RATTLE): subtract constrained DOF from denominator.
   T_kin = 2 * E_kin / (k_B * N_DOF) where N_DOF = 3*N - N_constraints - 3 (COM fixed).
3. For rigid molecules: rotational and translational temperatures should be equal.
   If T_rot != T_trans: thermostat not coupling correctly to rotational DOF.
```

**Virial pressure:**

```
P = N*k_BT/V + (1/(3V)) * <sum_{i<j} r_ij * f_ij>

where f_ij = -dU/dr_ij is the pair force.

Verification:
1. COMPUTE: P from virial and from equation of state independently.
   For ideal gas (dilute limit): P -> N*k_BT/V. Check this limit.
2. For hard spheres: P/(n*k_BT) = 1 + 4*phi*g(sigma+) where phi = (pi/6)*n*sigma^3.
   Compare with Carnahan-Starling: (1+phi+phi^2-phi^3)/(1-phi)^3.
3. Tail corrections: If LJ cutoff at r_c, add P_tail = (16/3)*pi*n^2*epsilon*sigma^3 *
   [(2/3)*(sigma/r_c)^9 - (sigma/r_c)^3]. Omitting tail correction at r_c = 2.5*sigma
   gives ~2% error in pressure.
```

**Fluctuation-dissipation relations:**

```
Isothermal compressibility: kappa_T = V * <(delta N)^2> / (<N>^2 * k_BT)  (grand canonical)
                          = V * <(delta rho)^2> / (rho^2 * k_BT)
                          = (1/rho) * S(q->0) / k_BT  (from structure factor)

Heat capacity: C_V = (<E^2> - <E>^2) / (k_BT^2)

Verification:
1. COMPUTE: kappa_T from fluctuations and from equation of state derivative.
   Must agree. Disagreement indicates sampling or ensemble issues.
2. COMPUTE: C_V from energy fluctuations. Compare with finite-difference dE/dT.
3. For NVT simulations: delta_E is correct but delta_P has thermostat corrections.
   For NPT simulations: use enthalpy fluctuations for C_P.
```

**Detailed balance (Monte Carlo):**

```
For MC moves with acceptance probability:
  P_acc(old -> new) / P_acc(new -> old) = exp(-beta * Delta E)

Verification:
1. For Metropolis: P_acc = min(1, exp(-beta*Delta E)). Verify implementation:
   - Delta E computed CORRECTLY (new - old, not old - new)
   - Random number comparison is < (not <=; doesn't matter in practice but shows attention)
   - Energy change includes ALL affected interactions (not just nearest neighbor for long-range forces)
2. For configurational bias MC (polymers): verify Rosenbluth weights are correctly computed.
3. COMPUTE: energy histogram from MC. Must match Boltzmann distribution:
   P(E) proportional to g(E) * exp(-beta*E).
```

</thermodynamic_verification>

<scaling_verification>

## Scaling Law Verification

**Polymer scaling:**

```
Key exponents (3D, good solvent):
  R_g ~ N^nu       nu = 0.5876 +/- 0.0001 (Flory-Edwards renormalization group)
  R_ee ~ N^nu      same exponent (ratio R_ee/R_g = sqrt(6) for Gaussian, ~6.25 for SAW)
  D ~ N^{-nu}      for Rouse (no HI); D ~ N^{-nu} for Zimm (with HI, different prefactor)
  eta ~ c^{1/(3nu-1)} in semidilute regime (c > c*)

Theta solvent: nu = 1/2 (Gaussian behavior)
Poor solvent (globule): R_g ~ N^{1/3}

Verification:
1. COMPUTE: R_g vs N for at least 4 chain lengths spanning a factor of 8 in N.
   Log-log fit should give nu within 0.02 of the expected value.
2. If nu < 0.5: check for attractive interactions or collapsed conformations.
3. If nu > 0.6: check for excluded volume artifacts or chain stiffness effects.
4. For theta solvent: nu = 0.5 +/- 0.01 AND R_g^2 = b^2*N/6 with b the Kuhn length.
5. Cross-check: R_ee^2 / R_g^2 ratio. For ideal chains: = 6. For SAW in 3D: ~ 6.25.
   Values far from this range indicate sampling problems.
```

**Diffusion coefficient:**

```
D = lim_{t->inf} <|r(t) - r(0)|^2> / (6t)   (3D, center of mass)

Finite-size correction (PBC):
  D(L) = D(inf) - 2.837 * k_BT / (6*pi*eta*L)   (Yeh-Hummer correction)

Verification:
1. COMPUTE: MSD(t). Must show three regimes:
   - Short time: ballistic MSD ~ t^2 (if NVE) or overdamped MSD ~ t (if Langevin)
   - Intermediate: subdiffusive MSD ~ t^alpha with alpha < 1 (for polymers, entangled systems)
   - Long time: diffusive MSD ~ t (alpha = 1)
2. Extract D from the slope of MSD in the diffusive regime ONLY.
   If extracted from subdiffusive regime: D will be wrong (too large at short times).
3. Apply finite-size correction if box size L < 10*R_g.
4. For polymers: D ~ N^{-1} (Rouse, no HI) or D ~ N^{-nu} (Zimm, with HI).
   Check consistency with the hydrodynamic model used.
```

**Phase transition scaling:**

```
Near a continuous phase transition at T_c:
  Order parameter: m ~ |T - T_c|^beta     (beta = 0.326 for 3D Ising)
  Susceptibility:  chi ~ |T - T_c|^{-gamma} (gamma = 1.237 for 3D Ising)
  Correlation length: xi ~ |T - T_c|^{-nu}  (nu = 0.630 for 3D Ising)

Finite-size scaling:
  m(L) ~ L^{-beta/nu} * f_m((T-T_c)*L^{1/nu})
  chi(L) ~ L^{gamma/nu} * f_chi((T-T_c)*L^{1/nu})

Verification:
1. COMPUTE: data collapse. Plot m*L^{beta/nu} vs (T-T_c)*L^{1/nu} for multiple L values.
   All curves must collapse onto a single master curve.
2. If data does not collapse: either T_c is wrong, exponents are wrong, or system is too small.
3. Hyperscaling relation: 2-alpha = d*nu where d is spatial dimension. Check consistency.
4. gamma = (2-eta)*nu, beta = nu*(d-2+eta)/2. Verify exponent relations.
```

</scaling_verification>

<force_field_verification>

## Force Field and Model Validation

**Structural validation:**

```
Before production, validate the model against at least one experimental structural observable.

Polymer:
  R_g, R_ee, persistence length l_p from SAXS/SANS or single-molecule experiments.
  Pair correlation g(r) peak positions from X-ray/neutron scattering.

Protein:
  RMSD from crystal structure < 2 A for well-folded proteins.
  Radius of gyration from SAXS.
  NMR chemical shifts, NOE distances, J-couplings from NMR experiments.

Membrane:
  Area per lipid (A_L), bilayer thickness (d_HH), order parameter S_CD from NMR/X-ray.
  Bending modulus kappa from fluctuation analysis.

Verification:
1. COMPUTE: target structural observable from simulation.
2. COMPARE: with experimental value. Agreement within 10%: acceptable for CG models.
   Agreement within 5%: acceptable for all-atom models. Worse: model needs refinement.
3. For CG models: validate at MULTIPLE state points (T, P, concentration).
   Failure at a state point different from parameterization indicates limited transferability.
```

**Energy minimization sanity:**

```
After building initial configuration:
1. COMPUTE: initial energy per particle. Compare with known values for the force field.
   If E/N >> k_BT * 100: steric clashes present. Minimize further or rebuild.
2. No atom overlaps: minimum interatomic distance > 0.5 * sigma (LJ) or > 1.0 A (all-atom).
3. No stretched bonds: bond lengths within 20% of equilibrium value.
4. For proteins: Ramachandran plot should show physical phi/psi distribution.
```

**Coarse-graining validation:**

```
CG model must reproduce target properties from the reference (all-atom or experimental):

Structural:
  RDF g_CG(r) should match g_AA(r) at the CG resolution.
  Distributions of bonded degrees of freedom (bonds, angles, dihedrals) must match.

Thermodynamic:
  Density, pressure, compressibility within 5% of reference.
  Free energy of transfer (for MARTINI-type models) within 1 kJ/mol.

Verification:
1. COMPUTE: g_CG(r) and overlay with g_AA(r) from reference simulation.
   Peak positions must match within 0.1 sigma. Peak heights within 20%.
2. CG dynamics is faster than all-atom by a speed-up factor (typically 3-10x for MARTINI).
   This factor must be applied when comparing dynamical properties.
3. NEVER use CG model at a state point far from its parameterization without re-validation.
```

</force_field_verification>

<finite_size_verification>

## Finite-Size Effect Assessment

**Box size requirements:**

```
Minimum box size depends on the largest correlation length in the system:

| System | Minimum L | Reason |
|--------|----------|--------|
| Polymer solution | L > 3*R_g | Chain cannot interact with own periodic image |
| Colloidal suspension | L > 10*sigma + 2*kappa^{-1} | Must contain several Debye lengths |
| Lipid membrane | L > 5*xi_mesh | Fluctuations of mesh size must be captured |
| Near phase transition | L > 5*xi(T) | Correlation length diverges at T_c |
| Electrolyte | L > 5*lambda_D | Debye screening length sets minimum |

Verification:
1. RUN: at least 3 system sizes (L, 2L, 4L) and compare target observable.
   If observable changes by > 5% between sizes: finite-size effects are significant.
2. For long-range interactions (electrostatics): check that Ewald sum is converged.
   Real-space cutoff + k-space terms must give total energy converged to < 0.1%.
3. For diffusion: apply Yeh-Hummer finite-size correction D(L) = D(inf) - C*k_BT/(6*pi*eta*L).
```

**Periodic image artifacts:**

```
Long-range hydrodynamic interactions (1/r decay) are strongly affected by PBC.

Verification:
1. For charged systems: Ewald/PME removes spurious electrostatic image interactions.
   But: net-charged simulation boxes require background charge. Verify total charge = 0.
2. For flow problems: PBC imposes no-slip velocity periodicity. If studying bulk flow
   near a wall, buffer regions of at least 3*sigma should separate wall and periodic image.
3. For polymer: if R_ee > L/2, the chain wraps around the box. This is unphysical unless
   studying dense melts where entanglement requires chains to span the box.
```

</finite_size_verification>

<active_matter_verification>

## Active Matter and Non-Equilibrium Checks

Active systems violate detailed balance. Equilibrium statistical mechanics does NOT apply.

**Non-equilibrium signatures:**

```
Verification that a system is truly active (out of equilibrium):
1. COMPUTE: entropy production rate sigma = <P_forward / P_reverse> > 0.
   If sigma = 0: system is in equilibrium despite active forces.
2. COMPUTE: detailed balance violation in trajectory space.
   P(trajectory) / P(time-reversed trajectory) != 1 for non-equilibrium.
3. CHECK: <v_i * f_j> - <v_j * f_i> != 0 for i != j (broken Onsager reciprocity).
4. Effective temperature from FDT violation: T_eff(omega) = S(omega) / (2*chi''(omega)).
   If T_eff depends on frequency: system is out of equilibrium.
```

**Active matter consistency:**

```
For active Brownian particles (ABPs):
  v_0 = self-propulsion speed (>= 0)
  D_r = rotational diffusion coefficient (>= 0)
  Persistence length: l_p = v_0 / D_r
  Peclet number: Pe = v_0 * sigma / D_t (activity parameter)

Motility-induced phase separation (MIPS):
  Occurs for Pe > Pe_c ~ 40-100 (depends on interaction potential and dimension).

Verification:
1. COMPUTE: effective speed <|v|>. Must be close to v_0 at low density.
   At high density: <|v|> < v_0 due to collisions (correct).
2. For MIPS: verify that dense phase has lower motility and dilute phase has higher motility.
   If both phases have same motility: not MIPS (may be equilibrium phase separation).
3. Do NOT use free energy minimization for active systems.
   Active phase behavior cannot be derived from an equilibrium free energy.
4. Pressure is NOT a state function for active systems in general.
   Wall pressure depends on wall properties (not just bulk state). Verify by measuring
   pressure at different wall types.
```

</active_matter_verification>

<conservation_checks>

## Conservation Law Verification

**Energy conservation (NVE):**

```
For microcanonical MD with velocity-Verlet integrator:
  Total energy E = E_kin + E_pot should be conserved.
  Energy drift: |Delta E / E| < 10^{-5} per tau for good integration.

Verification:
1. COMPUTE: energy drift rate. Plot E(t) over 10^4 timesteps.
   Linear drift indicates systematic error (wrong forces, missed interactions).
   Random walk indicates timestep at stability limit.
2. For dt_optimal: energy fluctuations delta_E / E ~ (dt/tau)^4 for velocity-Verlet.
   If delta_E/E ~ (dt/tau)^2: forces are not conservative (constraint algorithm error or interpolation).
3. For constrained systems (SHAKE): verify constraints are satisfied to tolerance at every step.
```

**Momentum conservation:**

```
Total momentum P = sum m_i v_i should be conserved (or zero if COM is fixed).

Verification:
1. COMPUTE: |P(t)| / |P(0)|. Should be constant to machine precision.
   Drift indicates non-pairwise forces or broken Newton's third law.
2. For Langevin thermostat: momentum is NOT conserved (thermostat adds random forces).
   But: <P> = 0 should hold on average.
3. For LAMMPS with "fix momentum": COM velocity is periodically removed.
   This is an artifact — check that physical results don't depend on removal frequency.
```

</conservation_checks>

## Worked Examples

### Detecting non-equilibration in a polymer melt

**Scenario:** Running MD of an entangled polymer melt (N=500, 100 chains). Production run of 10^6 tau.

```python
import numpy as np

# Estimate entanglement time
N = 500          # monomers per chain
N_e = 65         # entanglement length for bead-spring model
tau_e = 1800     # entanglement time in LJ units (known for Kremer-Grest model)

# Reptation time
tau_rep = 3 * tau_e * (N / N_e)**3.4
print(f"Reptation time: {tau_rep:.1e} tau")
# tau_rep ~ 3 * 1800 * (500/65)^3.4 ~ 3 * 1800 * 2650 ~ 1.4e7 tau

run_length = 1e6  # tau
print(f"Run length: {run_length:.1e} tau")
print(f"Run / tau_rep: {run_length/tau_rep:.2f}")
# Run / tau_rep ~ 0.07

# VERDICT: Run is only 7% of ONE reptation time.
# The chains have not relaxed even once.
# ALL dynamical observables (diffusion, viscosity, relaxation times) are WRONG.
# Need at least 10 * tau_rep ~ 1.4e8 tau for reliable entangled dynamics.
# Static observables (R_g at single-chain level) may still be OK if initial
# conditions were prepared from an equilibrated melt.
```

### Verifying Flory exponent from simulation

**Scenario:** Bead-spring polymer in good solvent, computing R_g vs N.

```python
import numpy as np
from scipy.stats import linregress

# Simulation data (R_g in sigma, N in monomers)
N_values = np.array([20, 40, 80, 160, 320])
Rg_values = np.array([2.45, 3.72, 5.65, 8.55, 12.95])

# Log-log fit
slope, intercept, r_value, p_value, std_err = linregress(np.log(N_values), np.log(Rg_values))

print(f"Flory exponent nu = {slope:.4f} +/- {std_err:.4f}")
print(f"R^2 = {r_value**2:.6f}")
# Expected: nu = 0.588 +/- 0.001 (3D good solvent)

# Checks:
# 1. nu should be in [0.57, 0.60] for good solvent in 3D
# 2. R^2 should be > 0.999 (power law must be excellent)
# 3. Ratio R_ee^2 / R_g^2 should be ~6.25 (not 6.0 which is the Gaussian value)
# 4. Shortest chain N=20 may show corrections to scaling; re-fit excluding N=20
```

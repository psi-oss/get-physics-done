---
load_when:
  - "molecular dynamics"
  - "MD simulation"
  - "force field"
  - "thermostat"
  - "barostat"
  - "Verlet integrator"
  - "equilibration"
tier: 2
context_cost: medium
---

# Molecular Dynamics Protocol

Molecular dynamics integrates Newton's equations for a system of interacting particles. The results look like physics but are only as good as the force field, the integrator, and the statistical sampling. Thermostat artifacts, insufficient equilibration, and finite-size effects routinely produce plausible but wrong answers. This protocol ensures correct MD simulations.

## Related Protocols
- `monte-carlo.md` — Alternative sampling; use MC when dynamics are not needed
- `numerical-computation.md` — Convergence testing, error budgets
- `stochastic-processes.md` — Langevin dynamics, Brownian dynamics

## Step 1: Force Field Selection

1. **Match the force field to the physics.** Classical force fields (Lennard-Jones, Coulomb + bonded terms) cannot describe bond breaking, charge transfer, or electronic excitations. If any of these matter, use ab initio MD (AIMD) or a reactive force field (ReaxFF).
2. **State the force field explicitly.** Name the force field (OPLS-AA, AMBER ff19SB, CHARMM36m, TIP4P/2005 for water) and cite the parameterization. Different parameterizations of the "same" force field give different results — the version matters.
3. **Combination rules.** For mixed interactions (A-B when only A-A and B-B parameters are given), state whether Lorentz-Berthelot, geometric, or other combination rules are used. Different simulation packages default to different rules.
4. **Long-range interactions.** Coulomb interactions decay as 1/r and cannot be truncated. Use Ewald summation (or PME/PPPM variants) for periodic systems. State the real-space cutoff, Ewald splitting parameter, and k-space mesh. For Lennard-Jones: either apply long-range tail corrections or use a large cutoff (> 2.5 sigma minimum, 3.5 sigma preferred).
5. **Cutoff artifacts.** A sharp cutoff in the potential introduces a delta-function force at r_cut. Use a switching function or shifted potential to smooth the cutoff. Verify that the pressure and energy are insensitive to the cutoff distance.

## Step 2: Integration Scheme

1. **Velocity Verlet (standard choice).** Time-reversible, symplectic, second-order:
   r(t + dt) = r(t) + v(t) dt + (1/2) a(t) dt^2
   v(t + dt) = v(t) + (1/2)(a(t) + a(t + dt)) dt
   Conserves a shadow Hamiltonian to O(dt^2) per step. Energy drift should be negligible over the simulation timescale.
2. **Timestep selection.** The timestep must resolve the fastest motion in the system. For atomistic MD with hydrogen: dt <= 1 fs (2 fs with SHAKE/LINCS constraints on H-X bonds). For coarse-grained: dt can be 5-20 fs depending on the model. For AIMD: dt ~ 0.5 fs (electronic degrees of freedom set the timescale).
3. **Energy conservation check.** In the NVE ensemble, total energy must be conserved. Plot E_total vs time. Drift should be < 10^{-4} kT per particle per nanosecond. Significant drift signals: timestep too large, force discontinuities from cutoff artifacts, or a bug.
4. **Multiple timestep methods.** RESPA (reversible reference system propagator algorithm) integrates fast forces (bonds, angles) with a short timestep and slow forces (long-range electrostatics) with a longer timestep. Verify stability: resonance artifacts appear when the outer timestep is near half the period of a fast mode.

## Step 3: Thermostat and Barostat

1. **NVE (microcanonical).** No thermostat. Use for: energy conservation checks, short-time dynamics, and transport coefficients via Green-Kubo relations. Not suitable for equilibrium sampling at a target temperature.
2. **Nose-Hoover thermostat.** Generates the correct canonical (NVT) ensemble. Requires a coupling time constant tau_T. Too small: oscillatory temperature artifacts. Too large: slow equilibration. Typical: tau_T = 100 dt to 1000 dt. For stiff systems, use Nose-Hoover chains (at least 3 chains) to ensure ergodicity.
3. **Langevin thermostat.** Adds friction and random forces: m a = F - gamma v + sqrt(2 gamma k_B T) xi(t). Generates the canonical ensemble but modifies the dynamics — diffusion coefficients and time correlations are affected by gamma. Do NOT use for computing transport properties unless gamma-dependence is extrapolated to gamma -> 0.
4. **Velocity rescaling (Berendsen).** Does NOT generate the canonical ensemble — it suppresses fluctuations. Use only for initial equilibration, never for production. The stochastic velocity rescaling thermostat (Bussi-Donadio-Parrinello) fixes this and generates the correct ensemble.
5. **Barostats.** For NPT simulations, use Parrinello-Rahman (correct ensemble, allows cell shape changes) or MTTK (Martyna-Tuckerman-Tobias-Klein). Berendsen barostat does not generate the correct NPT ensemble — use only for equilibration. State the coupling time constant and target pressure.

## Step 4: Equilibration

1. **Energy minimization first.** Before dynamics, minimize the potential energy to remove steric clashes and bad contacts. Use steepest descent or conjugate gradient. The minimized structure is the starting point, not the result.
2. **Staged equilibration.** For complex systems (biomolecules, interfaces): equilibrate in stages. Typical protocol: (a) minimize, (b) heat from 0 K to target T over 100-500 ps with position restraints, (c) release restraints gradually, (d) equilibrate in target ensemble for >= 1 ns.
3. **Equilibration diagnostics.** Monitor: temperature, pressure, density, potential energy, RMSD from initial structure. All must plateau before production begins. If any quantity drifts during "production," the system is not equilibrated.
4. **Discard equilibration data.** Never include equilibration trajectories in production averages. The length of equilibration depends on the system — it must be measured, not assumed.

## Step 5: Sampling and Analysis

1. **Autocorrelation analysis.** Compute the autocorrelation function for every reported observable. The integrated autocorrelation time tau_int determines the effective number of independent samples: N_eff = T_sim / (2 tau_int). If N_eff < 50, the statistical error estimate is unreliable.
2. **Block averaging.** Divide the trajectory into blocks of length >= 2 tau_int. Compute the observable for each block. The standard error of the block means gives the correct statistical error.
3. **Structural properties.** Radial distribution functions g(r), structure factors S(q), density profiles. Compare with experimental data (X-ray/neutron scattering) when available.
4. **Dynamic properties.** Mean-square displacement (MSD) for diffusion: D = lim_{t->inf} <|r(t) - r(0)|^2> / (6t). Velocity autocorrelation function (VACF) for the vibrational density of states. Time correlation functions for viscosity (Green-Kubo) and thermal conductivity.
5. **Free energy methods.** Direct MD does not sample free energy landscapes. Use: thermodynamic integration, free energy perturbation, umbrella sampling + WHAM, metadynamics, or replica exchange (REMD). State the method and verify convergence of the free energy estimate.

## Step 6: Finite-Size and Convergence

1. **Finite-size effects.** Periodic boundary conditions introduce artificial periodicity. The minimum image convention requires the box length L > 2 r_cut. For properties sensitive to long-range correlations (e.g., critical phenomena, dielectric constant), simulate multiple box sizes and extrapolate to L -> infinity.
2. **System-size scaling.** For bulk properties, N = 500-1000 particles is often sufficient. For interfaces, polymers, and large biomolecules, much larger systems may be needed. Verify by doubling N and checking that per-particle properties are unchanged.
3. **Timestep convergence.** Halve dt and verify that all reported properties change by less than the statistical error. If they change: the original dt was too large.
4. **Trajectory length.** The simulation must be long enough to sample the slowest relevant motion. For proteins: microsecond timescales for conformational changes. For simple liquids: nanoseconds suffice. Report the total simulation time and the autocorrelation time of the slowest observable.

## Worked Example: Lennard-Jones Liquid — Thermostat Comparison

**Problem:** Compute the self-diffusion coefficient D of a Lennard-Jones liquid at reduced temperature T* = 0.85 and reduced density rho* = 0.85 (near the triple point). Compare NVE (microcanonical) with Langevin thermostat at various friction coefficients to demonstrate the thermostat artifact on dynamics.

### Setup

- N = 864 particles (6^3 * 4 for FCC initial lattice), periodic BC
- LJ potential: U(r) = 4 epsilon [(sigma/r)^12 - (sigma/r)^6], cutoff r_c = 2.5 sigma with tail corrections
- Reduced units: sigma = epsilon = m = k_B = 1
- Timestep: dt = 0.005 tau (where tau = sigma * sqrt(m/epsilon))
- Box length: L = (N/rho*)^{1/3} = (864/0.85)^{1/3} = 10.05 sigma

### Step 1: Equilibrate

1. Start from FCC lattice at rho* = 0.85
2. Assign random velocities from Maxwell-Boltzmann at T* = 0.85
3. Run NVT (Nose-Hoover, tau_T = 100 dt = 0.5 tau) for 10000 steps (50 tau)
4. Verify: T fluctuates around 0.85, PE stabilized at ~ -5.27 epsilon/particle

### Step 2: Production — NVE reference

Switch to NVE. Run for 100000 steps (500 tau).

Energy conservation check: |E(t) - E(0)| / |E(0)| < 10^{-5} over 500 tau. If drift exceeds this, reduce dt.

Compute MSD: <|r(t) - r(0)|^2> = 6 D t at long times.
From the slope: D_NVE = 0.033 sigma^2/tau (literature value: D* = 0.033 +/- 0.002).

### Step 3: Langevin thermostat at various gamma

Run the same system with Langevin dynamics at T* = 0.85 with different friction coefficients:

| gamma (1/tau) | D_measured (sigma^2/tau) | D_corrected | D_NVE reference |
|---------------|--------------------------|-------------|-----------------|
| 0.1 | 0.031 | 0.033 | 0.033 |
| 1.0 | 0.020 | 0.033 | 0.033 |
| 10.0 | 0.0029 | 0.033 | 0.033 |
| 100.0 | 0.00030 | 0.033 | 0.033 |

**Key observation:** Larger gamma suppresses D_measured. The Langevin thermostat modifies the dynamics by adding friction. The measured D is NOT the physical diffusion coefficient.

**Correction:** In the overdamped limit (large gamma), D_measured ~ k_B T / (m gamma). The physical D can be recovered by extrapolating to gamma -> 0:
```
1/D_measured = 1/D_physical + m*gamma / (k_B T)
```
Plot 1/D vs gamma: the y-intercept gives 1/D_physical = 1/D_NVE.

### Step 4: Nose-Hoover — Correct Dynamics

Run with Nose-Hoover thermostat (tau_T = 0.5 tau, 3 chains):
- D_NH = 0.033 sigma^2/tau — agrees with NVE reference
- Nose-Hoover preserves Newtonian dynamics (no friction), so transport coefficients are correct

### Verification

1. **Energy conservation (NVE):** Total energy drift < 10^{-5} * |E_total| over 500 tau. If violated, dt is too large or the force calculation has errors.

2. **Temperature (all ensembles):** <T> = 0.85 +/- 0.01 in production. The instantaneous T = (2/3N) * KE fluctuates; the time average must match the target.

3. **Radial distribution function:** g(r) should show a first peak at r ~ 1.12 sigma (the LJ minimum) with height ~ 2.7. This is independent of the thermostat. If g(r) differs between NVE and Langevin runs, the system is not equilibrated.

4. **Einstein relation check:** Plot <|r(t)|^2> vs t. Must be linear for t >> tau_collision (a few tau). The slope is 6D. If the MSD shows a plateau (caging) followed by diffusion, the system may be approaching glass transition — check the state point.

5. **Known value benchmark:** For LJ at T* = 0.85, rho* = 0.85:
   - Pressure: P* ~ 1.0
   - Potential energy: U*/N ~ -5.27
   - D* ~ 0.033
   Verify against published values (e.g., Meier et al., JCP 2004).

6. **Finite-size correction:** For periodic systems, D has a 1/L correction from hydrodynamic interactions:
   D(L) = D(inf) - k_B T * xi / (6 pi eta L)
   where xi = 2.837... (Hasimoto constant) and eta is the shear viscosity. For N = 864 at this state point, the correction is ~ 5%. Report the corrected value.

## Worked Example: Solvation Free Energy of Methane in Water via Thermodynamic Integration

**Problem:** Compute the solvation free energy of methane in TIP3P water using thermodynamic integration (TI). The experimental value is Delta G_solv = +2.0 kcal/mol (hydrophobic — unfavorable). This example targets three common errors: confusing direct MD sampling (which cannot access free energies) with free energy methods, insufficient lambda sampling, and hysteresis from irreversible transformations.

### Step 1: Why Direct MD Fails

Direct MD samples configurations at fixed T, P, N. It gives the potential energy <U> and its fluctuations, but NOT the free energy F = -k_B T ln(Z). The partition function Z requires integration over ALL configurations, including those never visited during the simulation. The free energy difference between methane-in-water and methane-in-vacuum requires comparing two partition functions — impossible by direct sampling.

A common LLM error: "Run MD of methane in water, compute <U>, then Delta G = <U_solv> - <U_vac>." This confuses internal energy with free energy. The entropy contribution T*Delta S is missing, and for hydrophobic solvation it dominates (Delta S < 0 due to water restructuring around the nonpolar solute).

### Step 2: Thermodynamic Integration Setup

Create a lambda pathway that gradually decouples methane from the solvent:

```
H(lambda) = H_water + lambda * H_methane-water
```

At lambda = 1: methane fully interacts with water (physical system). At lambda = 0: methane is a ghost particle (no interactions with water). The free energy difference:

```
Delta G = integral_0^1 <dH/dlambda>_lambda d lambda
```

**Parameters:**
- 1 methane + 895 TIP3P water molecules in a cubic box (L ~ 30 Angstrom)
- OPLS-AA force field for methane (sigma = 3.73 Angstrom, epsilon = 0.294 kcal/mol)
- Lambda values: 0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0 (13 windows)
- Dense spacing near lambda = 0 and 1 where <dH/dlambda> changes rapidly
- Each window: 2 ns equilibration + 5 ns production, NPT at 298 K, 1 atm

**Soft-core potential:** At small lambda, the LJ repulsion vanishes and water molecules can overlap with the methane site, causing singularities. Use a soft-core potential:

```
U_sc(r, lambda) = 4 epsilon lambda^n [(alpha (1-lambda)^m + (r/sigma)^6)^{-2} - (alpha (1-lambda)^m + (r/sigma)^6)^{-1}]
```

with alpha = 0.5, n = 1, m = 1 (standard Gromacs soft-core parameters). Without soft-core: the simulation crashes at lambda < 0.1 due to particle overlap singularities.

### Step 3: Results

| lambda | <dH/dlambda> (kcal/mol) | std error |
|--------|------------------------|-----------|
| 0.00 | 0.12 | 0.03 |
| 0.05 | 0.35 | 0.05 |
| 0.10 | 0.82 | 0.08 |
| 0.20 | 1.95 | 0.12 |
| 0.30 | 2.78 | 0.15 |
| 0.40 | 3.21 | 0.14 |
| 0.50 | 3.40 | 0.13 |
| 0.60 | 3.28 | 0.12 |
| 0.70 | 2.85 | 0.11 |
| 0.80 | 2.20 | 0.10 |
| 0.90 | 1.35 | 0.08 |
| 0.95 | 0.82 | 0.06 |
| 1.00 | 0.40 | 0.04 |

Numerical integration (trapezoidal rule):
```
Delta G_solv = integral_0^1 <dH/dlambda> dlambda = 2.15 +/- 0.18 kcal/mol
```

### Step 4: Convergence and Error Analysis

**Autocorrelation check:** For each lambda window, compute the autocorrelation time of dH/dlambda. Typical: tau_int = 2-5 ps. With 5 ns production and tau_int = 3 ps, N_eff = 5000/6 ~ 830 independent samples per window. The statistical error per window is sigma/sqrt(N_eff) ~ 0.1-0.15 kcal/mol.

**Lambda grid convergence:** Repeat with 21 lambda points (adding 0.15, 0.25, ..., 0.85):
```
Delta G_solv (21 points) = 2.12 +/- 0.12 kcal/mol
```

The shift (0.03 kcal/mol) is within statistical error, confirming the 13-point grid is adequate.

**Forward vs reverse:** Run the TI in reverse (lambda: 1 -> 0). If Delta G_forward and Delta G_reverse differ by more than 2*sigma, the individual windows are not equilibrated. Here: Delta G_forward = 2.15, Delta G_reverse = 2.09 kcal/mol. Difference: 0.06 kcal/mol ~ 0.3 sigma. Acceptable.

### Verification

1. **Energy component analysis:** Decompose Delta G into van der Waals and electrostatic contributions. For methane (nonpolar), the electrostatic contribution should be near zero (<0.1 kcal/mol). If significant, the force field parameters are wrong (methane should have no partial charges in OPLS-AA).

2. **Comparison with experiment:** Delta G_solv = 2.15 +/- 0.18 kcal/mol (calculated) vs 2.0 +/- 0.1 kcal/mol (experimental). Agreement within uncertainties. The slight overestimate is consistent with known TIP3P limitations (understructured hydration shell).

3. **Free energy perturbation cross-check:** Compute Delta G by FEP (exponential averaging) using the same trajectories. Bennett Acceptance Ratio (BAR) between adjacent lambda windows should give a consistent result. BAR estimate: 2.11 +/- 0.15 kcal/mol. Agreement with TI confirms both methods are converged.

4. **Known limit:** At lambda = 0, the system is pure TIP3P water. The pressure, density, and radial distribution function must match known TIP3P values (rho = 0.985 g/cm^3, first peak of g_OO at 2.77 Angstrom). Deviations indicate a setup error.

5. **Enthalpy-entropy decomposition:** Delta H = <U(lambda=1)> - <U(lambda=0)> from direct energy averages. Delta S = (Delta H - Delta G) / T. For methane in water: Delta H ~ -2.5 kcal/mol (favorable van der Waals), T*Delta S ~ -4.5 kcal/mol (unfavorable entropy — water cage formation). The positive Delta G arises from the entropy penalty dominating the enthalpy gain. If Delta S > 0, something is wrong — hydrophobic solvation always decreases entropy.

6. **Finite-size correction:** For a charged solute, the free energy has a 1/L correction from periodic images. For neutral methane, this correction is negligible. However, long-range LJ dispersion corrections (~0.1 kcal/mol) should be included.

## Common Pitfalls

- **Berendsen thermostat/barostat in production.** Berendsen methods do not generate the correct statistical ensemble. Fluctuations are suppressed, and ensemble averages are biased. Use only for equilibration; switch to Nose-Hoover or Parrinello-Rahman for production.
- **Truncated electrostatics.** Cutting off Coulomb interactions at a finite distance introduces massive artifacts in charged and polar systems. Always use Ewald summation (PME/PPPM) for periodic systems with charges.
- **Insufficient equilibration.** Starting production before the system has equilibrated biases all averages. The first sign is drift in the potential energy or density during "production." If in doubt, equilibrate longer.
- **Flying ice cube.** Some thermostats (velocity rescaling without proper implementation) can funnel kinetic energy into center-of-mass translation, freezing internal degrees of freedom while the total kinetic energy looks correct. Remove center-of-mass motion periodically and verify the temperature from internal degrees of freedom.
- **Periodic image artifacts.** A molecule interacting with its periodic image through the boundary produces unphysical correlations. For biomolecules in solution: ensure at least 1.0-1.2 nm of solvent between the solute and the box edge.
- **Wrong ensemble for the observable.** Computing pressure in NVT vs NPT, or heat capacity from energy fluctuations in the wrong ensemble, gives systematically wrong results. Match the ensemble to the thermodynamic relation being used.

## Verification Checklist

- [ ] Force field named, version cited, combination rules stated
- [ ] Long-range electrostatics: Ewald/PME with stated parameters
- [ ] Timestep: energy conservation verified in NVE (drift < 10^{-4} kT/atom/ns)
- [ ] Thermostat/barostat: correct ensemble (not Berendsen in production)
- [ ] Equilibration: all monitored quantities plateaued before production
- [ ] Autocorrelation: tau_int computed, N_eff > 50 for all reported observables
- [ ] Finite-size: box large enough (L > 2 r_cut, solvent padding > 1 nm)
- [ ] Timestep convergence: halving dt does not change results beyond statistical error
- [ ] Known limits: ideal gas recovers PV = NkT; harmonic solid gives correct C_V = 3Nk_B

## Worked Example: Timestep Artifact in Liquid Water — The Flying Ice Cube and Shadow Hamiltonian

**Problem:** Demonstrate that using too large a timestep in an NVE simulation of TIP3P water produces energy drift and incorrect structural properties, and that this artifact is masked when using a thermostat. Show how to systematically determine the maximum safe timestep and diagnose the "flying ice cube" effect. This targets the LLM error class of running MD with a timestep that is too large (e.g., 4 fs without constraints, or 5 fs with SHAKE) and trusting the thermostatted results, which appear correct but contain artifacts in dynamical properties.

### Step 1: Energy Conservation Test (NVE)

Run NVE simulations of 1000 TIP3P water molecules in a cubic box at density 0.997 g/cm^3 (T ~ 300 K) with SHAKE constraints on O-H bonds. Measure the total energy drift per atom per nanosecond:

| Timestep (fs) | Energy drift (kJ/mol/atom/ns) | Temperature drift (K/ns) | Status |
|--------------|------------------------------|--------------------------|--------|
| 0.5 | 2.1e-5 | 0.001 | Excellent |
| 1.0 | 1.8e-4 | 0.01 | Good |
| 2.0 | 3.2e-3 | 0.15 | Acceptable |
| 3.0 | 4.8e-2 | 2.3 | Marginal |
| 4.0 | 0.85 | 42 | Unacceptable |
| 5.0 | 12.3 | 590 | Catastrophic |

**Acceptance criterion:** Energy drift < 10^{-3} kJ/mol/atom/ns (~ 0.01 kT/atom/ns). This gives dt_max = 2 fs with SHAKE. Without SHAKE (flexible water): dt_max = 0.5 fs (the O-H stretch has period ~10 fs, requiring dt < T_OH/20 = 0.5 fs).

### Step 2: The Thermostat Mask

Now run the SAME systems with a Nose-Hoover thermostat (T = 300 K, tau = 1 ps):

| Timestep (fs) | <T> (K) | sigma_T (K) | <P> (bar) | g_OO first peak |
|--------------|---------|-------------|-----------|----------------|
| 1.0 | 300.0 | 6.2 | 1.0 | 2.76 A |
| 2.0 | 300.0 | 6.3 | 1.2 | 2.76 A |
| 3.0 | 300.0 | 6.5 | 2.8 | 2.76 A |
| 4.0 | 300.0 | 7.1 | 12.5 | 2.75 A |
| 5.0 | 300.1 | 8.8 | 85 | 2.73 A |

The thermostat forces <T> = 300 K regardless of the timestep. The temperature, RDF first peak, and even the density all look correct at dt = 4 fs. **The artifact hides in the pressure** (which is very sensitive to forces) and in **dynamical properties**:

| Timestep (fs) | D_self (10^{-5} cm^2/s) | tau_dipole (ps) | Correct? |
|--------------|------------------------|-----------------|----------|
| 1.0 | 5.8 | 4.2 | Yes |
| 2.0 | 5.7 | 4.3 | Yes |
| 3.0 | 5.2 | 4.8 | Marginal |
| 4.0 | 3.8 | 7.1 | No (35% error in D) |
| 5.0 | 1.9 | 15.3 | No (67% error in D) |

The self-diffusion coefficient D drops by 67% at dt = 5 fs. The thermostat masks the energy non-conservation but cannot fix the corrupted dynamics.

### Step 3: The Flying Ice Cube Diagnostic

At dt = 5 fs with velocity rescaling thermostat (simple rescaling, not Nose-Hoover): after 100 ps, the kinetic energy partition between translational and rotational/vibrational modes becomes anomalous:

```
Expected (equipartition): T_trans = T_rot = T_vib = 300 K
Observed at dt = 5 fs:    T_trans = 385 K, T_rot = 260 K, T_vib = 175 K
```

The velocity rescaling thermostat scales ALL velocities uniformly, which funnels energy into center-of-mass translation at the expense of internal modes. The system appears to have the correct total temperature but the equipartition theorem is violated. The molecules translate fast but rotate/vibrate slowly — like an "ice cube flying through the box."

**Diagnosis:** Compute the temperature from each degree of freedom separately. If T_trans >> T_rot, the thermostat is transferring energy to translation. This does not occur with Nose-Hoover (which couples to all degrees of freedom independently) but is a known artifact of simple velocity rescaling.

### Step 4: Shadow Hamiltonian Analysis

The Verlet integrator exactly conserves a "shadow Hamiltonian" H_shadow that differs from the true Hamiltonian by terms of O(dt^2):

```
H_shadow = H + (dt^2/12) [{H, {H, H}_PB}_PB] + O(dt^4)
```

The energy drift in an NVE simulation is NOT from the Verlet integrator losing energy (it conserves H_shadow exactly) but from the shadow Hamiltonian differing from the true one. The drift rate scales as dt^p where p = 2 for the velocity-Verlet integrator.

**Verification:** Plot the shadow energy (computed from the corrected Hamiltonian) alongside the true energy. At dt = 4 fs:
- True energy drift: 0.85 kJ/mol/atom/ns
- Shadow energy drift: < 10^{-6} kJ/mol/atom/ns (machine precision)

This confirms the integrator is working correctly; the issue is that H_shadow != H at large dt.

### Verification

1. **Energy conservation as THE primary diagnostic.** Always run a short NVE simulation before production. If the energy drift exceeds 10^{-3} kT/atom/ns, the timestep is too large. This test takes 100 ps and catches problems that thermostats mask.

2. **Pressure sensitivity.** The pressure is proportional to the virial (sum of r . F), which depends on the forces. Wrong forces from large dt produce wrong pressure even when the thermostat corrects the temperature. A 10% pressure error at 1 bar (i.e., 100 bar systematic error) indicates dt is too large.

3. **Diffusion coefficient convergence.** Compute D at dt and dt/2. If they differ by more than 5%, the larger dt is not safe. Diffusion is sensitive because it depends on the long-time dynamics, which are most affected by timestep artifacts.

4. **Equipartition check.** Compute T_trans, T_rot, T_vib separately. They must all agree within statistical fluctuations. Violation of equipartition is a strong sign of thermostat artifact or timestep too large.

5. **Rule of thumb.** dt < T_fastest / 20 where T_fastest is the period of the fastest oscillation. With SHAKE (removing O-H stretch at T = 10 fs): the fastest remaining mode is H-O-H bend at T = 21 fs, giving dt < 1 fs. The standard 2 fs works because the bend is nearly harmonic and the Verlet integrator handles harmonic oscillators exactly. But this only holds for rigid-bond water models — flexible models require dt < 0.5 fs.

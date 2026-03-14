---
load_when:
  - "general relativity"
  - "cosmology"
  - "Friedmann equation"
  - "black hole"
  - "gravitational wave"
  - "dark energy"
  - "CMB"
  - "Einstein equation"
tier: 2
context_cost: medium
---

# GR & Cosmology

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/perturbation-theory.md` (post-Newtonian expansion, gravitational perturbation theory), `references/protocols/cosmological-perturbation-theory.md` (CMB, inflation, primordial perturbations), `references/protocols/de-sitter-space.md` (positive cosmological constant, cosmological horizons, dS/CFT, static patch holography), `references/protocols/asymptotic-symmetries.md` (Bondi gauge, null infinity, BMS charges, memory, soft theorems), `references/protocols/numerical-computation.md` (general numerical methods), `references/protocols/numerical-relativity.md` (3+1 decomposition, constraint equations, gravitational wave extraction), `references/protocols/effective-field-theory.md` (gravitational EFT, parameterized post-Einsteinian framework).

**Friedmann Equations:**

- H^2 = (8*pi*G / 3) \* rho - k/a^2 + Lambda/3 (first Friedmann equation)
- a-double-dot / a = -(4*pi*G / 3) * (rho + 3*P) + Lambda/3 (acceleration equation)
- Continuity: d(rho)/dt + 3*H*(rho + P) = 0; with equation of state P = w\*rho
- Solutions: matter-dominated (a ~ t^{2/3}), radiation-dominated (a ~ t^{1/2}), Lambda-dominated (a ~ exp(H\*t))
- Friedmann-Lemaitre-Robertson-Walker metric: ds^2 = -dt^2 + a(t)^2 * [dr^2/(1-kr^2) + r^2 d_Omega^2]

**Cosmological Perturbation Theory:**

- Scalar, vector, tensor decomposition of metric perturbations
- Gauge choices: conformal Newtonian (Poisson), synchronous, comoving; gauge-invariant variables (Bardeen potentials)
- Boltzmann hierarchy: coupled Einstein + Boltzmann equations for photons, neutrinos, baryons, CDM
- Transfer functions: relate primordial power spectrum to observed power spectrum at late times
- Non-linear perturbation theory: SPT (standard PT), EFT of large-scale structure, Lagrangian PT (Zel'dovich approximation)

**CMB Physics:**

- Temperature anisotropies: delta_T/T ~ 10^{-5}; acoustic oscillations in baryon-photon fluid
- Angular power spectrum C_l: decompose in spherical harmonics; peaks at l ~ 220, 540, 810, ...
- Sachs-Wolfe effect (large scales), acoustic oscillations (degree scales), Silk damping (small scales)
- Polarization: E-modes from scalar perturbations, B-modes from tensors (gravitational waves) and lensing
- CMB lensing: secondary effect from gravitational deflection; probes matter distribution at z ~ 2

**N-body Simulations:**

- Gravitational N-body: solve N coupled equations of motion for collisionless dark matter particles
- Tree codes (Barnes-Hut): O(N log N); hierarchical force calculation
- Particle-mesh (PM): O(N log N); FFT-based; limited spatial resolution
- TreePM and adaptive mesh refinement (AMR): combine tree and mesh for dynamic range
- Hydrodynamics: SPH (smoothed-particle), AMR (Eulerian), moving mesh (Voronoi)

**21cm Cosmology:**

- Brightness temperature: T_b = T_S * (1 - exp(-tau)) \_ (1 - T_CMB/T_S)
- Spin temperature T_S: coupled to gas, CMB, and Lyman-alpha radiation
- Epochs: dark ages, cosmic dawn (first stars), reionization
- Power spectrum: 3D tomography of neutral hydrogen; probes dark ages through reionization

**Gravitational Lensing:**

- Weak lensing: statistical distortion of background galaxy shapes; cosmic shear power spectrum
- Strong lensing: multiple images, arcs, Einstein rings; mass modeling
- Convergence kappa and shear gamma; related to projected mass distribution
- Lensing potential: phi = (2/c^2) _ integral Phi _ (D_ls/D_s) dz

**Dark Matter Models:**

- CDM (cold dark matter): standard; pressureless, collisionless; forms halos
- WDM (warm): free-streaming suppresses small-scale structure; constraints from Lyman-alpha forest
- SIDM (self-interacting): finite cross section; cores instead of cusps in halos
- Fuzzy DM (ultra-light axions): m ~ 10^{-22} eV; de Broglie wavelength ~ kpc scale
- WIMP: weakly interacting massive particle; annihilation cross section sets relic abundance (thermal freeze-out)

**de Sitter Space and Cosmological Horizons:**

- Exact de Sitter: `a(t) = exp(H t)` with `H = sqrt(Lambda / 3)` in 4d; more generally `R_{mu nu} = (d-1) H^2 g_{mu nu}`
- Static patch metric: `ds^2 = -(1-r^2/L^2) dt^2 + dr^2/(1-r^2/L^2) + r^2 dOmega_{d-2}^2`; cosmological horizon at `r = L = H^{-1}`
- Gibbons-Hawking thermodynamics: `T_dS = H/(2*pi)` and `S_GH = A_H/(4G_N)`; observer dependence matters because each static patch has its own horizon
- QFT in de Sitter: Bunch-Davies vacuum is the default reference state; in-in formalism is the correct language for late-time correlators and inflationary observables
- Late-time representation theory: light fields lie in complementary series, heavy fields in principal series; complex scaling weights are not automatically pathologies
- Schwarzschild-de Sitter and Nariai regimes: black-hole and cosmological horizons compete; near-coincident horizons require special care with temperatures and patch definitions

## Key Tools and Software

| Tool                             | Purpose                                           | Notes                                                             |
| -------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------- |
| **CAMB**                         | Boltzmann solver for CMB and matter power spectra | Python/Fortran; standard for Planck analysis                      |
| **CLASS**                        | Boltzmann solver (alternative to CAMB)            | C with Python wrapper; modular; easy to modify                    |
| **Gadget-4**                     | N-body + SPH cosmological simulation              | Massively parallel; TreePM; standard for large-volume simulations |
| **AREPO**                        | Moving-mesh hydrodynamics                         | Voronoi tessellation; Illustris/TNG simulations                   |
| **RAMSES**                       | AMR N-body + hydro                                | Octree AMR; widely used for zoom-in simulations                   |
| **Enzo**                         | AMR cosmological hydro                            | Block-structured AMR; includes chemistry, radiation               |
| **CosmoMC**                      | MCMC cosmological parameter estimation            | Interfaces with CAMB; standard for CMB analysis                   |
| **Cobaya**                       | Bayesian inference framework                      | Modern replacement for CosmoMC; modular                           |
| **emcee**                        | Ensemble MCMC sampler                             | General purpose; widely used in astrophysics                      |
| **GetDist**                      | MCMC chain analysis and plotting                  | Triangle plots, marginalized posteriors                           |
| **HEALPix**                      | Pixelization of the sphere                        | Standard for CMB maps; spherical harmonics                        |
| **NaMaster**                     | Pseudo-C_l power spectrum estimation              | Handles masks, mode coupling                                      |
| **CCL (Core Cosmology Library)** | Cosmological calculations                         | Background, distances, growth, power spectra                      |
| **COLOSSUS**                     | Halo mass function and concentration              | Python; multiple fitting functions                                |
| **halomod**                      | Halo model calculations                           | Power spectra, correlation functions                              |
| **21cmFAST**                     | Semi-numerical 21cm simulations                   | Fast; excursion set formalism                                     |
| **nbodykit**                     | Large-scale structure analysis toolkit            | Power spectra, correlation functions, HOD                         |

## Validation Strategies

**CMB Power Spectrum:**

- Planck 2018 best-fit: H_0 = 67.4 km/s/Mpc, Omega_b*h^2 = 0.0224, Omega_c*h^2 = 0.120, n_s = 0.965, A_s = 2.1e-9, tau = 0.054
- First acoustic peak at l ~ 220; angular scale theta_* = r_s(z_*) / D_A(z_*) ~ 1 degree
- Check: Boltzmann code output must reproduce Planck best-fit C_l to sub-percent level
- CAMB and CLASS must agree on C_l to ~0.1% level for standard cosmology

**BAO (Baryon Acoustic Oscillations):**

- Sound horizon at drag epoch: r_d ~ 147 Mpc (comoving)
- BAO feature in correlation function at ~100 h^{-1} Mpc; in power spectrum as oscillations
- Check: correlation function or P(k) from N-body must show BAO feature at correct scale

**Structure Formation:**

- Press-Schechter mass function: n(M) dM gives halo abundance; compare with Sheth-Tormen or Tinker fitting functions
- Halo mass function from simulation must agree with fitting functions to ~10-20%
- Halo density profiles: NFW profile rho(r) = rho_s / [(r/r_s) * (1 + r/r_s)^2]; check concentration-mass relation

**Distance Measures:**

- Flat LCDM: comoving distance chi = integral_0^z c\*dz'/H(z')
- Angular diameter distance: D_A = chi / (1+z)
- Luminosity distance: D_L = (1+z) \* chi
- Check: D_L(z) must be consistent with Type Ia supernovae distance ladder

**Energy Conservation:**

- Friedmann + continuity equations imply: d(rho*a^3)/dt + P*d(a^3)/dt = 0
- Check: energy density evolution in simulation/Boltzmann code must satisfy continuity equation
- In N-body: total energy (kinetic + potential) conserved; monitor drift

## Common Pitfalls

- **H_0 tension:** Planck (CMB) gives H_0 ~ 67.4; SH0ES (local distance ladder) gives H_0 ~ 73. Do not assume one is "correct" without specifying the dataset and model
- **Confusing comoving and physical distances:** Comoving distance is fixed; physical distance = a(t) \* comoving. Factor of (1+z) errors are common
- **Wrong power spectrum normalization:** sigma_8 normalizes the matter power spectrum in spheres of 8 h^{-1} Mpc. Confusion between sigma_8 and A_s propagates to all structure formation calculations
- **Neglecting neutrino mass effects:** Even minimal neutrino mass (sum m_nu ~ 0.06 eV) suppresses small-scale power by ~1%. Precision cosmology requires including massive neutrinos
- **N-body initial conditions at wrong redshift:** Must use second-order Lagrangian PT (2LPT) for initial conditions; first-order (Zel'dovich) introduces transient errors
- **Resolution effects in simulations:** Force softening, mass resolution, and box size all affect results. Always quote resolution and perform convergence tests
- **Gauge artifacts:** Perturbation theory results depend on gauge choice for gauge-dependent quantities. Only compare gauge-invariant observables between codes or with data
- **Forgetting to marginalize:** Cosmological constraints require marginalization over all nuisance parameters. Fixing nuisance parameters artificially tightens error bars

---

# General Relativity

## Core Methods

**Metric Perturbation Theory:**

- g_mu_nu = g_bar_mu_nu + h_mu_nu with |h| << 1 (linearized gravity)
- Gauge freedom: h_mu_nu -> h_mu_nu + partial_mu xi_nu + partial_nu xi_mu; choose Lorenz gauge, transverse-traceless (TT), Regge-Wheeler
- Schwarzschild perturbations: Regge-Wheeler equation (odd/axial), Zerilli equation (even/polar); both reduce to single ODE
- Kerr perturbations: Teukolsky equation for spin-weighted spheroidal harmonics; separable in Boyer-Lindquist coordinates
- Post-Newtonian: expansion in v/c and GM/(rc^2); systematic weak-field slow-motion approximation; 4.5PN state of the art for conservative dynamics

**Numerical Relativity:**

- **BSSN formulation:** Conformal decomposition of ADM equations; well-posed; standard for binary mergers
- **Generalized Harmonic:** Wave-equation formulation; well-posed; used by SpEC/SpECTRE
- **Constraint damping:** Z4 or CCZ4 formulations; actively damp constraint violations
- **Initial data:** Solve Hamiltonian and momentum constraints; conformal thin-sandwich, Bowen-York puncture data
- **Gauge conditions:** 1+log slicing for lapse, Gamma-driver for shift; avoid coordinate singularities at horizons
- **Mesh refinement:** AMR (Carpet/Cactus) or multi-domain spectral (SpECTRE); need resolution at horizons and in wave zone

**Geodesics:**

- Geodesic equation: d^2 x^mu / d_tau^2 + Gamma^mu_alpha_beta * (dx^alpha/d_tau) * (dx^beta/d_tau) = 0
- Constants of motion: energy E (time Killing vector), angular momentum L (azimuthal Killing vector), Carter constant Q (Kerr spacetime)
- Effective potential: reduces geodesic problem to 1D; ISCO, photon sphere, bound and unbound orbits
- Null geodesics: photon paths, gravitational lensing, black hole shadows

**Gravitational Waves:**

- Quadrupole formula: h_ij^TT = (2*G / (c^4 * r)) \* I-double-dot_ij^TT (lowest order)
- Energy flux: dE/dt = (G / (5*c^5)) * <I-triple-dot_ij \* I-triple-dot_ij> (quadrupole)
- LIGO strain sensitivity: h ~ 10^{-23} at 100 Hz; Advanced LIGO design
- Waveform models: EOB (effective one body), IMR (inspiral-merger-ringdown) phenomenological, NR surrogates
- Matched filtering: optimal SNR = sqrt(4 \* integral |h-tilde(f)|^2 / S_n(f) df)

**Black Hole Thermodynamics:**

- Laws of BH mechanics ↔ thermodynamics: T_H = kappa/(2*pi) (Hawking temperature); S = A/(4*G\*hbar) (Bekenstein-Hawking entropy)
- First law: dM = (kappa / 8*pi*G) _ dA + Omega_H _ dJ + Phi_H \* dQ
- Area theorem: delta_A >= 0 (classically; violated by Hawking radiation)
- Black hole information problem: unitarity of quantum mechanics vs thermal Hawking radiation

**Asymptotic Structure and Null Infinity:**

- Bondi-Sachs expansion organizes asymptotically flat radiative data near null infinity in terms of the Bondi mass aspect, angular-momentum aspect, shear `C_AB`, and news `N_AB = partial_u C_AB`
- The 4d asymptotic symmetry group at null infinity is BMS: supertranslations plus Lorentz transformations; `l = 0,1` supertranslations reproduce ordinary translations
- Bondi mass loss and charge-flux balance laws tie asymptotic charges to gravitational radiation; memory observables are time-integrated consequences of the same conservation laws
- Numerical relativity waveforms must be compared in a fixed BMS frame; Cauchy-characteristic extraction or careful frame fixing is needed to resolve memory and avoid supertranslation ambiguity

## Key Tools and Software

| Tool                                | Purpose                               | Notes                                                             |
| ----------------------------------- | ------------------------------------- | ----------------------------------------------------------------- |
| **Einstein Toolkit**                | Open-source numerical relativity      | Cactus framework; BSSN; BBH, BNS; AMR (Carpet)                    |
| **SpECTRE**                         | Next-gen numerical relativity         | Discontinuous Galerkin; task-based parallelism; SXS collaboration |
| **SpEC**                            | Spectral Einstein Code                | Multi-domain spectral; highest accuracy for BBH waveforms         |
| **GRChombo**                        | Numerical GR with AMR                 | C++; AMR; modified gravity, cosmological spacetimes               |
| **LORENE / Kadath**                 | Spectral solver for initial data      | Neutron star initial data; quasi-equilibrium configurations       |
| **Black Hole Perturbation Toolkit** | Perturbation theory                   | Mathematica/Python; Teukolsky equation, self-force                |
| **PyCBC / GWpy / LALSuite**         | GW data analysis                      | Matched filtering, parameter estimation; LIGO/Virgo software      |
| **Bilby**                           | Bayesian inference for GW             | Python; nested sampling; parameter estimation                     |
| **SXS Catalog**                     | NR waveform database                  | Public catalog of numerical waveforms; calibration for models     |
| **xAct / xTensor**                  | Tensor computer algebra (Mathematica) | Abstract and component tensor calculus; GR-specific               |
| **SageManifolds**                   | Differential geometry (SageMath)      | Manifolds, tensor fields, connections; symbolic                   |
| **GRTensorIII**                     | Tensor algebra (Maple)                | Christoffel symbols, Riemann tensor, Einstein equations           |
| **CadabraV2**                       | Tensor computer algebra               | Field theory and GR; index manipulation; Python interface         |
| **PRECESSION**                      | Black hole binary spin dynamics       | Post-Newtonian spin precession; Python                            |

## Validation Strategies

**Constraint Monitoring:**

- Hamiltonian constraint: H = R + K^2 - K_ij*K^ij - 16*pi\*rho = 0
- Momentum constraint: M_i = D_j K^j_i - D_i K - 8*pi*j_i = 0
- Check: constraints must remain small (converge to zero with resolution) throughout evolution
- Constraint violation norm: L2 norm of H and M_i should decrease at expected convergence order

**Convergence Testing:**

- Richardson extrapolation: run at three resolutions (h, h/2, h/4); convergence order = log(e_1/e_2) / log(2)
- For N-th order scheme: error ~ h^N; check observed rate matches expected
- Self-convergence test: no analytical solution needed; compare coarse-medium and medium-fine

**Known Solutions:**

- Schwarzschild: metric is time-independent; any deviation = numerical artifact
- Kerr: axisymmetric; has analytical geodesics, QNM frequencies
- Quasinormal modes: compare NR ringdown frequencies with perturbation theory predictions (Leaver, continued fraction method)
- Binary black hole: SXS catalog waveforms for cross-validation between codes

**ADM Quantities:**

- ADM mass: M_ADM = -(1/(16*pi)) * oint (g^{ij},\_j - g^{jj},\_i) dS_i (surface integral at spatial infinity)
- ADM angular momentum: J_i = (1/(16*pi*G)) \* epsilon_{ijk} _ oint (x^j _ K^{kl} - x^k \* K^{jl}) dS_l
- Bondi mass: M_Bondi = M_ADM - E_radiated; must decrease monotonically
- Check: ADM mass must be conserved; energy radiated in GW must account for mass loss

**Gauge Invariance:**

- Physical observables (waveform at infinity, quasinormal mode frequencies) must be gauge-independent
- Check: compare gauge-invariant waveform extractions (Psi_4 vs h at various extraction radii; Cauchy-characteristic extraction)
- Coordinate effects: coordinate observers can show artifacts (e.g., gauge-mode oscillations in lapse)

## Common Pitfalls

- **Coordinate singularities vs physical singularities:** Schwarzschild r=2M is a coordinate singularity (removable); r=0 is physical. Check the Kretschmann scalar R\_{abcd}\*R^{abcd} to distinguish
- **Wrong sign convention for metric:** (-,+,+,+) vs (+,-,-,-) is a choice; mixing them produces wrong signs in Einstein equations. Be consistent
- **Constraint-violating initial data:** Freely specifying all of g_ij and K_ij generally violates constraints. Must solve constraint equations (York procedure, conformal thin sandwich)
- **Insufficient outer boundary distance:** Waves reflected from outer boundary contaminate the solution. Place boundary at r >> L/c \* T_simulation or use constraint-preserving boundary conditions
- **Junk radiation:** Initial data that is not in quasi-equilibrium emits spurious radiation. Must wait for junk to leave the computational domain before extracting physics
- **Coordinate extraction artifacts:** Gravitational wave extraction at finite radius has systematic errors. Extrapolate to r -> infinity or use Cauchy-characteristic extraction (CCE)
- **Spin magnitude errors in post-Newtonian:** PN spin effects enter at 1.5PN; spin-orbit, spin-spin, and spin-induced quadrupole all matter. Missing any term leads to dephasing
- **Neglecting tidal effects for neutron stars:** Tidal deformability Lambda-tilde enters GW phase at 5PN. Essential for BNS waveforms and EOS inference

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Post-Minkowskian gravity** | Conservative + dissipative dynamics of binary systems via scattering amplitudes | Bern, Cheung, Porto, Damour | Excellent — QFT methods for classical GR |
| **Gravitational wave cosmology** | Hubble tension resolution, primordial GW background, standard sirens | LIGO/Virgo/KAGRA, LISA consortium | Good — Boltzmann code + data analysis |
| **Black hole information paradox** | Islands formula, replica wormholes, Page curve from semiclassical gravity | Penington, Almheiri, Maldacena, Hartman | Good — semiclassical calculations |
| **de Sitter quantum gravity / holography** | What is the correct observable framework for positive cosmological constant: wavefunction, dS/CFT, or static-patch holography? | Anninos, Strominger, Maldacena, Galante, Stanford/Perimeter dS groups | Good — strong on geometry, EFT, correlators, and consistency checks; speculative dictionary entries need explicit citation |
| **Asymptotic symmetries / celestial gravity** | How do BMS charges, memory, soft theorems, and celestial currents organize flat-space gravity? | Strominger, Donnay, Ciambelli, Pasterski, Mitman, Boyle | Good — strong for symmetry logic and verification; superrotations/celestial dictionary remain frontier topics |
| **Modified gravity** | Horndeski/beyond-Horndeski, massive gravity, testing GR with GW observations | Zumalacárregui, Creminelli, Baker | Excellent — perturbation theory + data fits |
| **Inflation model selection** | Primordial non-Gaussianity (f_NL), primordial gravitational waves (r), spectral tilt running | Planck, CMB-S4, LiteBIRD teams | Good — slow-roll calculations + forecasts |
| **Numerical relativity for LISA** | Extreme mass ratio inspirals (EMRIs), supermassive BH mergers | Warburton, Barack, Pound | Moderate — self-force + NR hybrid |

## Methodology Decision Tree

```
What regime?
├── Weak field, slow motion (v/c << 1, GM/rc^2 << 1)
│   ├── Bound system? → Post-Newtonian expansion (PN)
│   ├── Unbound scattering? → Post-Minkowskian expansion (PM)
│   └── Cosmological perturbations? → Linearized GR in FRW background
├── Strong field, dynamic (mergers, collapse)
│   ├── Comparable mass? → Full numerical relativity (3+1 decomposition)
│   ├── Extreme mass ratio? → Black hole perturbation theory + self-force
│   └── Symmetry (spherical/axial)? → 1+1 or 2+1 codes
├── Strong field, stationary
│   ├── Vacuum? → Exact solutions (Kerr, Schwarzschild)
│   ├── With matter? → TOV equation (static) or rotating NS models (COCAL, RNS)
│   └── Thermodynamic? → Black hole thermodynamics, Hawking radiation
└── Cosmological
    ├── Background? → Friedmann equations (CLASS/CAMB for full Boltzmann)
    ├── Linear perturbations? → Boltzmann hierarchy (scalar, vector, tensor)
    ├── Non-linear structure? → N-body simulation (Gadget, AREPO)
    └── Primordial? → Inflation slow-roll + Mukhanov-Sasaki equation
```

## Common Collaboration Patterns

- **GR theory + GW experiment:** Theorists provide waveform templates (PN/NR/EOB); LIGO/Virgo uses them for matched filtering. Parameter estimation constrains source physics.
- **Cosmology + CMB experiments:** Boltzmann code predictions compared with Planck/ACT/SPT data via MCMC. Joint constraints on cosmological parameters.
- **GR + High-energy physics:** Amplitude methods applied to gravitational scattering. Double copy (gauge theory → gravity) produces state-of-the-art PN results.
- **GR + Astrophysics:** Neutron star equation of state from nuclear physics + GW tidal deformability constraints. Multi-messenger astronomy (GW + EM).

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One PN calculation to new order, or Boltzmann code modification for one extension | "3PN spin-orbit contributions to the gravitational wave phase for precessing binaries" |
| **Postdoc** | Waveform model development, NR simulation campaign, or cosmological parameter estimation | "NR-calibrated EOB model for precessing binary black holes with higher modes" |
| **Faculty** | New computational framework, resolution of conceptual puzzle, or major observational program | "Self-consistent treatment of radiation reaction in Kerr spacetime for LISA EMRIs"

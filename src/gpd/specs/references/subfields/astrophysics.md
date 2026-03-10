---
load_when:
  - "astrophysics"
  - "stellar structure"
  - "accretion disk"
  - "compact object"
  - "neutron star"
  - "supernova"
  - "galaxy"
  - "interstellar medium"
tier: 2
context_cost: medium
---

# Astrophysics

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/numerical-relativity.md` (gravitational wave sources, compact objects), `references/protocols/cosmological-perturbation-theory.md` (CMB, inflation, primordial perturbations), `references/protocols/numerical-computation.md` (general numerical methods), `references/protocols/monte-carlo.md` (statistical inference in astrophysics), `references/protocols/perturbation-theory.md` (post-Newtonian expansion, gravitational lensing), `references/protocols/stochastic-processes.md` (stochastic gravitational wave backgrounds, noise characterization).

**Stellar Structure and Evolution:**

- Hydrostatic equilibrium: dP/dr = -Gm(r)ρ/r² (Newtonian), TOV equation for relativistic stars
- Energy transport: radiative (dT/dr from opacity κ and luminosity L), convective (mixing-length theory, Schwarzschild criterion: dT/dr > (dT/dr)_ad)
- Nuclear reaction networks: pp chain (T < 1.7 × 10⁷ K), CNO cycle (T > 1.7 × 10⁷ K), triple-alpha process (He burning), s-process and r-process nucleosynthesis
- Equations of state: ideal gas + radiation + degeneracy pressure; OPAL opacity tables; nuclear EOS for neutron stars
- Stellar evolution tracks on the HR diagram: main sequence → subgiant → red giant → horizontal branch → AGB → white dwarf/supernova

**Accretion Disk Physics:**

- Thin disk (Shakura-Sunyaev): geometrically thin (H/R ≪ 1), optically thick, thermal spectrum. Viscosity parameterized as ν = αc_sH (α-prescription). Luminosity: L = ηṀc² with η ≈ 0.1 for Schwarzschild, up to 0.42 for maximally spinning Kerr
- Advection-dominated accretion flow (ADAF): low-luminosity, geometrically thick, optically thin. Relevant for Sgr A* and low-luminosity AGN. Two-temperature plasma: T_ion ≫ T_electron
- MHD accretion: magnetorotational instability (MRI) drives turbulence → angular momentum transport. Requires resolving the fastest-growing MRI mode: λ_MRI = 2πv_A/Ω (at least ~10 cells per wavelength in simulations)
- Relativistic disks: ISCO (innermost stable circular orbit) at r = 6M (Schwarzschild), r = M (prograde Kerr a=1). No stable orbits inside ISCO → plunging region
- Jets: Blandford-Znajek mechanism (electromagnetic extraction of black hole spin energy), Blandford-Payne mechanism (magneto-centrifugal acceleration from disk)

**Compact Objects:**

- White dwarfs: electron degeneracy pressure support; Chandrasekhar mass M_Ch = 1.44 M_sun (for μ_e = 2); mass-radius relation R ∝ M^{-1/3} (non-relativistic) → R → 0 as M → M_Ch
- Neutron stars: nuclear matter EOS unknown above ρ_0 ≈ 2.8 × 10¹⁴ g/cm³; mass range ~1.2-2.3 M_sun; radius ~10-14 km; maximum mass depends on EOS (constraint: M_max > 2.0 M_sun from PSR J0740+6620). Tolman-Oppenheimer-Volkoff equation: dP/dr = -(ρ + P/c²)(m + 4πr³P/c²)G/(r²(1 - 2Gm/(rc²)))
- Black holes: Schwarzschild (non-spinning), Kerr (spinning). Kerr metric parameterized by M and a = J/M (0 ≤ a ≤ M). Horizon at r_+ = M + √(M² - a²). Ergosphere from r_+ to r_E = M + √(M² - a²cos²θ)
- Pulsars: rotating neutron stars with magnetic dipole radiation. Spin-down luminosity: Ė = 4π²I Ṗ/P³. Characteristic age: τ_c = P/(2Ṗ). Braking index: n = ΩΩ̈/Ω̇² (= 3 for pure magnetic dipole)

**Radiative Transfer:**

- Formal solution: I_ν(s) = I_ν(0) e^{-τ_ν} + ∫₀^{τ_ν} S_ν(τ') e^{-(τ_ν - τ')} dτ' where τ_ν is optical depth and S_ν is source function
- Local thermodynamic equilibrium (LTE): S_ν = B_ν(T) (Planck function). Non-LTE: S_ν depends on level populations, which depend on the radiation field (iterative solution)
- Eddington luminosity: L_Edd = 4πGMc/κ ≈ 1.3 × 10³⁸ (M/M_sun) erg/s (for electron scattering opacity). Exceeding L_Edd drives radiation-pressure-driven outflows
- Line transfer: Sobolev approximation for expanding atmospheres; Monte Carlo radiative transfer for complex geometries

**Gravitational Waves from Astrophysical Sources:**

- Compact binary inspiral: GW frequency f = 2f_orb = (1/π)(GM_c/r³)^{1/2} where M_c = (m₁m₂)^{3/5}/(m₁+m₂)^{1/5} is the chirp mass. Strain: h ~ 4(GM_c)^{5/3}(πf)^{2/3}/(c⁴d_L)
- Post-Newtonian expansion: expansion in v/c for the inspiral phase. 3.5PN order known for point masses. Tidal effects enter at 5PN for neutron stars (tidal deformability Λ)
- Numerical relativity merger waveforms: required for the late inspiral, merger, and ringdown. Effective-one-body (EOB) models calibrated to NR provide full inspiral-merger-ringdown waveforms
- Ringdown: quasi-normal modes of the remnant Kerr black hole. Fundamental mode: f ≈ 1.2 × 10⁴ (M_sun/M) Hz, damping time τ ≈ 0.06 (M/M_sun) s (for a/M ~ 0.7)
- Stochastic background: superposition of unresolved sources. Characterized by Ω_GW(f) = (1/ρ_c)(dρ_GW/d ln f)
- Continuous waves: spinning neutron stars with asymmetry (mountains, r-modes). Strain h₀ ~ 4π²Gε I f²/(c⁴d)

## Key Tools and Software

| Tool | Purpose | Notes |
|---|---|---|
| **MESA** | 1D stellar structure and evolution | Open-source; nucleosynthesis, asteroseismology, binary evolution |
| **Cloudy** | Spectral synthesis and photoionization modeling | Non-LTE; ISM, nebulae, AGN |
| **RADMC-3D** | 3D dust continuum and line radiative transfer | Monte Carlo; protoplanetary disks, star formation |
| **Einstein Toolkit** | Numerical relativity framework | Cactus + Carpet + thorn ecosystem; BBH, BNS mergers |
| **LALSuite** | LIGO/Virgo data analysis | GW signal processing, parameter estimation, waveform models |
| **Athena++** | MHD and radiation MHD | AMR; accretion disks, jets, ISM turbulence |
| **PLUTO** | MHD/relativistic HD | AMR; jets, accretion, stellar winds |
| **FLASH** | Multi-physics AMR hydro | Supernovae, XRB, stellar interiors |
| **Bilby** | Bayesian inference for GW sources | Python; parameter estimation, model selection |
| **PyCBC** | GW matched filtering and search | Python; compact binary search pipeline |
| **GYRE** | Stellar oscillation code | Asteroseismology; oscillation modes and frequencies |
| **SkyNet** | Nuclear reaction network | Nucleosynthesis; r-process, s-process |
| **SpEC** | Spectral Einstein Code | High-accuracy NR; spectral methods for BBH |
| **BAM** | Berger-AMR NR code | Finite differences + AMR; BBH and BNS |

## Validation Strategies

**Fundamental Scales and Relations:**

- Hertzsprung-Russell diagram: verify that evolutionary tracks cross the correct regions (main sequence band, Hayashi track, horizontal branch, AGB)
- Eddington luminosity: L_Edd = 4πGMc/κ_es ≈ 3.3 × 10⁴ (M/M_sun) L_sun. Accretion luminosity should not exceed L_Edd without radiation-driven outflow physics
- Chandrasekhar mass: M_Ch = 5.83 μ_e^{-2} M_sun ≈ 1.44 M_sun for μ_e = 2 (carbon-oxygen WD). If a WD model exceeds M_Ch without detonation, the EOS or numerical method has an error
- Jeans mass: M_J = (5k_BT/(Gμm_H))^{3/2} (3/(4πρ))^{1/2}. Cloud fragments should have M > M_J to collapse. Verify initial conditions satisfy this
- TOV maximum mass: must exceed ~2 M_sun (observational constraint). Verify the EOS produces this

**Gravitational Wave Checks:**

- Chirp mass from frequency evolution: M_c = (c³/G)(5/(96π^{8/3}))^{3/5} f^{-11/3} ḟ^{3/5}. Verify consistency between inspiral frequency evolution and chirp mass
- Energy balance: E_rad + M_remnant = M_initial (ADM mass). For equal-mass non-spinning BBH: E_rad ≈ 0.05 M c²
- Final spin: for equal-mass non-spinning BBH merger, a_f ≈ 0.69. For equal-mass aligned-spin: a_f depends on initial spins via fitting formulas (Rezzolla et al., Barausse-Rezzolla)
- Quasi-normal mode frequencies: verify the ringdown matches the remnant Kerr BH parameters

**Stellar Evolution Checks:**

- Main sequence lifetime: t_MS ≈ 10¹⁰ (M/M_sun)^{-2.5} yr (rough scaling). Verify MESA models give consistent lifetimes
- Solar model: verify L = 3.828 × 10²⁶ W, R = 6.957 × 10⁸ m, T_c ≈ 1.57 × 10⁷ K, ρ_c ≈ 1.5 × 10⁵ kg/m³ for a 1 M_sun, 4.6 Gyr model
- White dwarf cooling: verify the cooling curve matches observed WD luminosity functions
- Core-collapse supernovae: verify that the bounce occurs at nuclear density ρ_nuc ≈ 2.8 × 10¹⁴ g/cm³ and that the shock energy is ~10⁵¹ erg (1 Bethe)

**Accretion Disk Checks:**

- Thin disk temperature profile: T(r) ∝ r^{-3/4} (far from inner edge). Inner disk temperature: T_max ≈ 10⁷ (M/10 M_sun)^{-1/4} (Ṁ/Ṁ_Edd)^{1/4} K
- Radiative efficiency: η = 1 - E_ISCO/c². Schwarzschild: η ≈ 0.057. Maximal Kerr (prograde): η ≈ 0.42. If computed efficiency exceeds 0.42, there is an error
- MRI fastest-growing wavelength must be resolved (quality factor Q_θ = λ_MRI/Δθ > 10 for convergence)

## Common Pitfalls

- **Wrong factors of G, c in relativistic expressions.** Natural units (G=c=1) are standard in GR; CGS is standard in stellar physics. Converting between them introduces factors of G = 6.674 × 10⁻⁸ cm³ g⁻¹ s⁻² and c = 3 × 10¹⁰ cm/s. Errors of factors of c² or c⁴ are common.
- **Confusing coordinate and physical quantities.** In GR, coordinate radius r is not the physical distance. The physical (proper) distance is ∫ √(g_rr) dr. Similarly, coordinate time t is not the proper time for an observer at finite radius (gravitational time dilation).
- **Neglecting general relativistic effects when they matter.** For neutron stars (GM/(Rc²) ~ 0.2), GR corrections to Newtonian gravity are 20-40%. A Newtonian stellar structure model will give the wrong mass-radius relation. Use the TOV equation.
- **Sign errors in the stress-energy tensor.** T^{00} should be positive for physical matter. In the (−+++) convention, T_{00} > 0. Check the sign convention of the Einstein equation: G_{μν} = 8πG T_{μν} (in +−−−) vs G_{μν} = -8πG T_{μν} (in −+++, some conventions).
- **Incorrect boundary conditions at infinity.** Asymptotically flat spacetimes require γ_{ij} → δ_{ij} and K_{ij} → 0 as r → ∞. Finite computational domains require outgoing-wave (Sommerfeld) boundary conditions for the evolved variables.
- **Insufficient resolution for MRI turbulence.** Under-resolved MRI produces too-low effective viscosity, leading to incorrect accretion rates and disk structure. Always check the MRI quality factor.
- **Forgetting gravitational redshift.** Observed quantities (luminosity, temperature, frequency) are redshifted relative to local values. For a neutron star surface: z = (1 - 2GM/(Rc²))^{-1/2} - 1 ≈ 0.3. Forgetting this factor systematically biases all observational comparisons.
- **Using Newtonian tidal deformability for neutron stars.** The tidal deformability Λ entering GW waveforms is a relativistic quantity (computed from the relativistic Love number k₂). Newtonian k₂ differs from the relativistic value by ~30%.

---

## Research Frontiers (2024-2026)

| Frontier | Key question | GPD suitability |
|----------|-------------|-----------------|
| **Multi-messenger astronomy** | Joint GW + EM constraints on neutron star EOS, kilonova physics | Good — TOV + nucleosynthesis calculations |
| **Exoplanet atmospheres** | Biosignatures, atmospheric retrieval with JWST spectra | Moderate — radiative transfer codes |
| **Fast radio bursts** | Origin mechanism, coherent emission, dispersion measure cosmology | Good — plasma physics + radiation mechanisms |
| **Supermassive BH formation** | Direct collapse vs seed mergers, LISA observations of high-z mergers | Good — accretion physics + GR |
| **r-process nucleosynthesis** | Origin of heavy elements, kilonova light curves, nuclear network calculations | Good — nuclear reaction networks |
| **Galaxy formation at cosmic dawn** | First galaxies with JWST, reionization sources, Pop III stars | Moderate — requires hydro simulations |

## Methodology Decision Tree

```
What astrophysical regime?
├── Stellar structure
│   ├── Main sequence? → Stellar evolution code (MESA)
│   ├── Compact object? → TOV equation (NS), Oppenheimer-Snyder (BH formation)
│   └── Binary? → Roche lobe geometry + mass transfer (MESA binary)
├── Accretion / jets
│   ├── Thin disk? → Shakura-Sunyaev alpha-disk model
│   ├── Thick / ADAF? → Self-similar ADAF or GRMHD simulation
│   └── Jet? → GRMHD + radiation transport
├── Radiative processes
│   ├── Thermal? → Blackbody + opacity tables
│   ├── Non-thermal? → Synchrotron, inverse Compton, pair production
│   └── Line emission? → CLOUDY or CHIANTI atomic databases
├── Gravitational dynamics
│   ├── Few-body? → Direct N-body integration
│   ├── Collisionless (galaxies)? → N-body (Gadget, AREPO)
│   └── Gas + gravity? → SPH or AMR hydro + gravity (FLASH, Athena)
└── High-energy transients
    ├── GRB? → Fireball model + afterglow dynamics
    ├── Supernova? → 1D (MESA) or 3D (FLASH/Fornax) neutrino-driven
    └── Kilonova? → Nuclear network + radiation transport
```

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One object class, one observable, full modeling pipeline | "Neutron star mass-radius constraints from X-ray pulse profile modeling" |
| **Postdoc** | Multi-messenger analysis or new theoretical model | "Kilonova light curves from ab initio r-process yields with nuclear uncertainties" |
| **Faculty** | Large survey program, definitive theoretical prediction, or new observational technique | "Constraining the neutron star equation of state with next-generation GW detectors"

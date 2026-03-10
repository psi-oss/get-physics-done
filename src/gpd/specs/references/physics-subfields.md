# Physics Subfield References

Comprehensive guidance for working within specific physics subfields. Each subfield reference provides: key methods, standard tools, validation strategies, common pitfalls, and recommended software.

<purpose>
This reference is loaded by GPD agents when research involves a specific physics subfield. It provides:

1. **For the planner (gpd-planner):** Which methods and tools are standard for the subfield, what validation checks to include in plans
2. **For the executor (gpd-executor):** Correct conventions, standard software, typical numerical parameters
3. **For the verifier (gpd-verifier):** Subfield-specific validation strategies, known exact results, standard benchmarks
4. **For the researcher (gpd-phase-researcher):** What tools and libraries to investigate, what communities and databases to consult
</purpose>

---

## Supported Subfields

GPD is designed for physics research broadly, with particular strength in problems that involve symbolic manipulation, numerical computation, or both. Load the relevant subfield reference for your project's domain.

**Load only the subfield(s) relevant to your current project** to conserve context budget.

| Subfield | Reference | Key Topics |
|----------|-----------|------------|
| Quantum Field Theory | references/subfields/qft.md | Perturbative QFT, renormalization, Feynman diagrams, gauge theories, EFTs, lattice QFT, generalized symmetries, supersymmetry |
| Quantum Gravity | references/subfields/quantum-gravity.md | Semiclassical gravity, black hole information, holography, quantum chaos, asymptotic safety, nonperturbative approaches |
| String Theory | references/subfields/string-theory.md | Worldsheet CFT, D-branes, dualities, compactification, moduli stabilization, swampland, string phenomenology |
| Condensed Matter | references/subfields/condensed-matter.md | Many-body, DFT, DMFT, tensor networks, topological phases, band theory |
| GR & Cosmology | references/subfields/gr-cosmology.md | Perturbation theory, CMB, inflation, de Sitter space, numerical relativity, gravitational waves, black holes |
| Statistical Mechanics | references/subfields/stat-mech.md | Phase transitions, Monte Carlo, critical phenomena, RG, exactly solved models |
| AMO Physics | references/subfields/amo.md | Quantum optics, cold atoms, scattering theory, master equations, BEC |
| Nuclear & Particle | references/subfields/nuclear-particle.md | QCD, nuclear structure, collider phenomenology, flavor physics, PDFs, effective theories, global fits |
| Quantum Information | references/subfields/quantum-info.md | Circuits, error correction, entanglement, tensor networks, variational algorithms |
| Fluid & Plasma | references/subfields/fluid-plasma.md | Navier-Stokes, MHD, turbulence, kinetic theory, spectral methods |
| Mathematical Physics | references/subfields/mathematical-physics.md | Rigorous proofs, functional analysis, representation theory, integrable systems, CFT, topological defects |
| Algebraic QFT | references/subfields/algebraic-qft.md | Haag-Kastler nets, modular theory, von Neumann factor types, DHR sectors |
| String Field Theory | references/subfields/string-field-theory.md | Open/closed superstrings, BRST, BV, tachyon condensation, `A_infinity` / `L_infinity` |
| Classical Mechanics | references/subfields/classical-mechanics.md | Lagrangian/Hamiltonian dynamics, nonlinear dynamics, chaos, celestial mechanics |
| Soft Matter & Biophysics | references/subfields/soft-matter-biophysics.md | Polymer physics, membrane dynamics, active matter, colloids, self-assembly, biomolecular simulation |
| Astrophysics | references/subfields/astrophysics.md | Stellar structure, accretion disks, compact objects, radiative transfer, gravitational waves, nucleosynthesis |

---

## Subfield Selection Guide

When a research project spans multiple subfields, use this guide to identify the primary subfield for validation purposes.

| If the research involves...                          | Primary subfield      | Also consult                                                   |
| ---------------------------------------------------- | --------------------- | -------------------------------------------------------------- |
| Feynman diagrams, loops, renormalization             | QFT                   | Nuclear/Particle for phenomenology                             |
| Band structure, DFT, Hubbard models                  | Condensed Matter      | Stat Mech for phase transitions                                |
| Phase transitions, critical exponents, Monte Carlo   | Statistical Mechanics | Condensed Matter for lattice models                            |
| CMB, large-scale structure, N-body                   | Cosmology             | GR for metric perturbations                                    |
| de Sitter space, cosmological horizons, dS/CFT       | GR & Cosmology        | QFT for fields in curved spacetime; Mathematical Physics for representation theory |
| Black hole information, Page curve, replica wormholes, holography | Quantum Gravity | GR for geometry; QFT for matter entanglement and EFT control |
| Worldsheet CFT, D-branes, compactification, moduli stabilization, swampland | String Theory | QFT for low-energy EFT; Mathematical Physics for modular/CFT structure; Quantum Gravity for holography or black-hole applications; String Field Theory for off-shell control or tachyon condensation |
| Higher-form symmetries, non-invertible defects, center symmetry, anomalies | QFT | Mathematical Physics for categorical/topological structure; Condensed Matter for topological-order applications |
| Haag-Kastler nets, modular theory, local algebras, von Neumann factor types | Algebraic QFT | Mathematical Physics for operator-algebra rigor; QFT for model input; Quantum Gravity for semiclassical/holographic entanglement questions |
| Superfields, BPS bounds, localization, Seiberg-Witten, superconformal index | QFT | Mathematical Physics for representation theory; GR for supergravity or holography |
| Quantum circuits, entanglement, error correction     | Quantum Information   | AMO for physical implementations                               |
| Laser-atom interaction, cold atoms, scattering       | AMO                   | Quantum Information for entanglement aspects                   |
| Collider physics, PDFs, cross sections               | Nuclear/Particle      | QFT for calculational methods                                  |
| Open/closed string interactions, tachyon condensation, BRST string vertices | String Field Theory | QFT for BRST/BV language; Mathematical Physics for homotopy algebra; String Theory for worldsheet CFT, D-branes, compactification, or duality physics; GR for background geometry |
| Global fits, SMEFT, public likelihoods, recasting    | Nuclear/Particle      | QFT for matching/running; Mathematical Physics for statistics-aware inference structure |
| CFD, turbulence, MHD                                 | Fluid Dynamics/Plasma | Stat Mech for turbulence theory                                |
| Black holes, gravitational waves, spacetime geometry | General Relativity    | QFT for Hawking radiation                                      |
| Rigorous proofs, topology, representation theory     | Mathematical Physics  | Relevant physical subfield                                     |
| Newtonian mechanics, Lagrangian/Hamiltonian dynamics | Classical Mechanics   | Mathematical Physics for geometric mechanics                   |
| Topological phases, Berry curvature                  | Condensed Matter      | Mathematical Physics for topology                              |
| Lattice gauge theory                                 | QFT                   | Stat Mech for Monte Carlo; Condensed Matter for tensor methods |
| Quantum gravity, holography                          | Quantum Gravity       | String Theory for UV completions, D-branes, or compactification data; Mathematical Physics for rigor |
| Asymptotic symmetries, soft theorems, memory, celestial amplitudes | GR & Cosmology | QFT for scattering amplitudes; Mathematical Physics for representation theory |
| Polymers, membranes, colloids, self-assembly         | Soft Matter           | Stat Mech for phase behavior; Fluid for hydrodynamics          |
| Active matter, molecular motors, biophysics          | Soft Matter           | Stat Mech for non-equilibrium; Fluid for active hydrodynamics  |
| Stellar structure, nucleosynthesis, supernovae       | Astrophysics          | Nuclear/Particle for reaction rates; Stat Mech for EOS         |
| Accretion disks, jets, MHD winds                     | Astrophysics          | Fluid/Plasma for MHD; GR for relativistic disks                |
| Gravitational wave sources, compact binary mergers   | Astrophysics          | GR for waveforms; Nuclear/Particle for EOS                     |
| Cosmological simulations, N-body, structure formation | Astrophysics          | GR & Cosmology for perturbation theory; Stat Mech for halo statistics |

---

## Cross-Subfield Validation Patterns

Some validation strategies transcend subfield boundaries. Apply these whenever the research touches multiple domains.

**Universality:**

- Same critical exponents must appear in different physical realizations of the same universality class
- Example: 3D Ising exponents apply to liquid-gas critical point, uniaxial magnetic transitions, binary mixtures

**Dualities:**

- Strong coupling in one description = weak coupling in another
- Examples: Kramers-Wannier (2D Ising high-T <-> low-T), electric-magnetic (Montonen-Olive), AdS/CFT
- Check: observables computed on both sides of duality must agree

**Emergent Symmetries:**

- Low-energy effective theory may have more symmetry than the UV theory
- Example: Lorentz invariance emerges from lattice models at long wavelengths
- Check: verify that the additional symmetry is respected by low-energy observables

**Anomaly Matching:**

- 't Hooft anomaly matching: UV and IR descriptions must have the same anomaly
- Applies across scales: useful for constraining low-energy behavior from UV data
- Check: compute anomaly coefficients in both descriptions and verify agreement

**Holographic Correspondence:**

- Bulk gravity calculation = boundary field theory calculation (in appropriate limit)
- Check: entropy from area of horizon = entropy from boundary thermal state
- Check: bulk geodesic length = boundary correlator (in geodesic approximation)

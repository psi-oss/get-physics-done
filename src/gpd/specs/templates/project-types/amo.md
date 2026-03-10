---
template_version: 1
---

# AMO Physics Project Template

Default project structure for atomic, molecular, and optical physics: Hamiltonian construction, basis selection, transition rates, scattering, dynamics, and quantum optics.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Hamiltonian Construction** - Write down the full Hamiltonian, identify symmetries, choose coupling scheme (LS vs jj), establish basis
- [ ] **Phase 2: Basis Selection and Matrix Elements** - Choose computational basis, compute angular momentum coupling coefficients, evaluate radial integrals
- [ ] **Phase 3: Transition Matrix Elements** - Compute dipole/multipole matrix elements, identify selection rules, calculate oscillator strengths
- [ ] **Phase 4: Scattering and Dynamics** - Set up scattering equations, compute phase shifts or solve time-dependent equations, handle resonances
- [ ] **Phase 5: Observables and Rates** - Compute cross sections, transition rates, lifetimes, spectral line profiles
- [ ] **Phase 6: Benchmarking and Validation** - Compare with NIST data, check sum rules, verify optical theorem, test convergence
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Hamiltonian Construction

**Goal:** Write down the complete Hamiltonian and identify all relevant interactions and symmetries
**Success Criteria:**

1. [Full Hamiltonian specified: kinetic energy, Coulomb, spin-orbit, hyperfine, external fields, atom-light interaction]
2. [Coupling scheme chosen and justified: LS coupling (light atoms), jj coupling (heavy atoms), or intermediate coupling]
3. [Symmetries identified: parity, rotational invariance, time-reversal, permutation symmetry for identical particles]
4. [Energy scales established: fine structure vs hyperfine vs Zeeman vs Stark; identify the relevant hierarchy]

Plans:

- [ ] 01-01: [Write full Hamiltonian; identify and order all interaction terms by magnitude]
- [ ] 01-02: [Analyze symmetries and conservation laws; determine good quantum numbers]

### Phase 2: Basis Selection and Matrix Elements

**Goal:** Choose an efficient computational basis and evaluate all required matrix elements
**Success Criteria:**

1. [Basis states defined: |n l m_l s m_s> or |n l s j m_j> or configuration-interaction basis]
2. [Angular momentum coupling coefficients computed: Clebsch-Gordan, 3j, 6j, 9j symbols as needed]
3. [Radial integrals evaluated: hydrogen-like analytic, Hartree-Fock numerical, or model potential wavefunctions]
4. [Basis convergence tested: energy eigenvalues stable with respect to basis size truncation]

Plans:

- [ ] 02-01: [Construct basis; compute angular coupling coefficients]
- [ ] 02-02: [Evaluate radial wavefunctions and matrix elements; test convergence]

### Phase 3: Transition Matrix Elements

**Goal:** Compute transition amplitudes and identify allowed and forbidden transitions
**Success Criteria:**

1. [Electric dipole (E1) matrix elements computed in length, velocity, and acceleration gauges]
2. [Selection rules verified: Delta_l = +/-1, Delta_m = 0,+/-1 (E1); Delta_l = 0,+/-2 (E2/M1)]
3. [Oscillator strengths computed and sum rule checked: sum f_{ij} = N_electrons (Thomas-Reiche-Kuhn)]
4. [Gauge invariance verified: length and velocity forms agree to within basis truncation error]
5. [Higher multipole contributions estimated if E1-forbidden: magnetic dipole (M1), electric quadrupole (E2)]

Plans:

- [ ] 03-01: [Compute E1 matrix elements; verify selection rules]
- [ ] 03-02: [Calculate oscillator strengths; check TRK sum rule]
- [ ] 03-03: [Evaluate higher multipole matrix elements for forbidden transitions]

### Phase 4: Scattering and Dynamics

**Goal:** Set up and solve scattering equations or time-dependent dynamics
**Success Criteria:**

1. [Scattering formalism chosen: partial wave expansion, close-coupling, R-matrix, or time-dependent wavepacket]
2. [Phase shifts computed for relevant partial waves; resonance positions and widths identified]
3. [For time-dependent problems: propagation method chosen (Crank-Nicolson, split-operator, RK4) and convergence tested]
4. [Resonances characterized: Feshbach (closed-channel) vs shape resonances; Fano q parameter if applicable]

Plans:

- [ ] 04-01: [Set up scattering equations; compute phase shifts or solve time-dependent equations]
- [ ] 04-02: [Identify and characterize resonances; fit Breit-Wigner or Fano profiles]
- [ ] 04-03: [Test convergence with respect to partial waves, basis size, and time step]

### Phase 5: Observables and Rates

**Goal:** Compute experimentally measurable quantities from the computed matrix elements and phase shifts
**Success Criteria:**

1. [Cross sections computed: differential and total, with partial wave contributions identified]
2. [Transition rates (Einstein A and B coefficients) computed; lifetimes derived]
3. [Line profiles computed: natural linewidth, Doppler broadening, pressure broadening as relevant]
4. [AC Stark shifts computed for relevant trapping/driving laser configurations]

Plans:

- [ ] 05-01: [Compute cross sections from phase shifts; verify optical theorem]
- [ ] 05-02: [Compute transition rates, lifetimes, and branching ratios]

### Phase 6: Benchmarking and Validation

**Goal:** Validate results against known data, sum rules, and independent calculations
**Success Criteria:**

1. [Energy levels compared with NIST Atomic Spectra Database to within expected accuracy of method]
2. [Oscillator strengths compared with published experimental and theoretical values]
3. [Optical theorem verified: sigma_total = (4*pi/k) * Im[f(0)] to numerical precision]
4. [Sum rules satisfied: Thomas-Reiche-Kuhn, and moment sum rules for polarizability]
5. [Unitarity of S-matrix verified: |S_l| = 1 for each partial wave in elastic scattering]

Plans:

- [ ] 06-01: [Compare energy levels and oscillator strengths with NIST data and published calculations]
- [ ] 06-02: [Verify optical theorem, sum rules, and S-matrix unitarity]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with energy level tables, transition rate comparisons, and cross section plots]
2. [Computational method and basis described in sufficient detail for reproduction]
3. [Results compared with prior calculations and experimental measurements]
```

### Mode-Specific Phase Adjustments

**Explore mode:**
- Phase 1: Compare coupling schemes (LS vs jj vs intermediate) and quantify which gives faster convergence for the target atom
- Phase 2: Test multiple basis sets (Slater, Gaussian, B-spline, Sturmian) and benchmark convergence rates for energy levels
- Phase 3: Compute dipole matrix elements in length, velocity, and acceleration gauges to assess basis quality before production
- Phase 4: Try multiple numerical methods (close-coupling, R-matrix, time-dependent wavepacket) for scattering to identify the most efficient approach

**Exploit mode:**
- Phase 1: Use the established coupling scheme for the target atom (e.g., LS for light atoms, jj for heavy)
- Phase 2: Use the standard basis set known to work for this atom/molecule from prior literature
- Phase 3: Compute matrix elements in the preferred gauge directly; skip multi-gauge comparison
- Phase 4: Apply the validated scattering method with known convergence parameters

**Adaptive:** Explore basis sets and coupling schemes in Phases 1-2, then exploit the best method for production spectroscopy and cross sections in Phases 3+.

---

## Standard Verification Checks for AMO

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-amo.md` for AMO-specific verification (selection rule compliance, TRK sum rule, dipole approximation validity, RWA bounds, Rabi normalization, AC Stark shift sign, decoherence rate positivity, optical theorem, Franck-Condon overlaps).

---

## Typical Approximation Hierarchy

| Level                        | Method                        | Captures                                                  | Misses                                                |
| ---------------------------- | ----------------------------- | --------------------------------------------------------- | ----------------------------------------------------- |
| Born approximation           | First-order perturbation      | High-energy scattering, qualitative cross sections        | Resonances, low-energy structure, threshold behavior   |
| Distorted wave Born (DWBA)   | Born with distorted waves     | Effect of long-range Coulomb/static potential              | Channel coupling, resonances                          |
| Close-coupling               | Coupled-channel expansion     | Resonances, channel coupling, threshold effects           | Convergence slow for many channels; core polarization  |
| R-matrix                     | Inner/outer region matching   | Resonances, multichannel scattering, photoionization      | Completeness of inner-region basis                     |
| Full configuration interaction | All electron correlations    | Near-exact for small systems; benchmark accuracy          | Exponential scaling with electron number               |

**When to go beyond each approximation:**

- Born approximation fails at low energies where the scattering length matters
- DWBA fails when channel coupling is strong (near resonances, near threshold)
- Close-coupling requires many channels near ionization threshold; R-matrix is more efficient
- R-matrix inner region must be large enough to contain all bound-state orbitals

---

## Common Pitfalls for AMO Calculations

1. **Rotating wave approximation validity:** Fails when the Rabi frequency approaches the transition frequency (ultrastrong coupling regime, Omega/omega_0 > 0.1). Must use full Hamiltonian without RWA or Floquet theory
2. **Neglecting counter-rotating terms:** Produces errors of order (Omega/omega_0)^2 in transition rates and level shifts. Bloch-Siegert shift is the leading correction
3. **Incorrect dipole matrix elements:** Wrong radial integral normalization or angular momentum coupling coefficient. Cross-check by computing oscillator strength and verifying sum rule
4. **Wrong angular momentum coupling:** j-j vs LS coupling gives different intermediate state structure. For atoms with Z > 30, intermediate coupling (full diagonalization of spin-orbit + Coulomb) is required
5. **Magnetic quantum number errors:** Missing Clebsch-Gordan coefficients or wrong projection quantum numbers in matrix elements. Verify by checking that matrix elements vanish for forbidden Delta_m transitions
6. **Confusing scattering length and cross section:** sigma = 4*pi*a^2 for distinguishable particles but sigma = 8*pi*a^2 for identical bosons. Factor-of-2 errors between identical and distinguishable particles
7. **Neglecting light shifts:** AC Stark effect from off-resonant driving fields shifts energy levels and modifies resonance conditions. Dominant systematic in precision spectroscopy and optical traps
8. **Markov approximation for structured reservoirs:** Standard Lindblad master equation assumes flat spectral density. Fails for photonic crystals, cavity QED near band edges, and strong coupling. Non-Markovian methods (HEOM, process tensor) required
9. **Core polarization neglect:** Valence electron calculations that ignore core polarization underestimate polarizabilities and oscillator strengths for alkali atoms by 10-30%. Use core-polarization potential or all-electron methods

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. AMO projects should populate:

- **Unit System:** Atomic units (hbar = m_e = e = 1) or SI with explicit conversions
- **Fourier Convention:** Physics convention (e^{-iwt} for positive-energy states)
- **Spin Convention:** Coupling scheme (LS vs jj) with good quantum numbers stated
- **State Normalization:** Non-relativistic (<k|k'> = delta^3(k - k')) or relativistic as appropriate

---

## Computational Environment

**Atomic structure:**

- `pyscf` (Python) — Quantum chemistry for atoms: HF, CI, CCSD, multi-reference
- `GRASP` (Fortran) — Relativistic atomic structure: MCDHF method
- `FAC` (C + Python) — Flexible Atomic Code: energy levels, radiative rates, collisional data
- `ARC` (Python) — Alkali Rydberg Calculator: energy levels, matrix elements, Stark maps for alkali atoms

**Quantum optics and dynamics:**

- `QuTiP` (Python) — Quantum Toolbox: master equations, Monte Carlo trajectories, Floquet, optimal control
- `QuantumOptics.jl` (Julia) — Cavity QED, many-body quantum optics
- `C3` (Python) — Quantum optimal control
- `Krotov` (Python) — Krotov's method for quantum optimal control

**Scattering:**

- `Molscat` (Fortran) — Quantum scattering for atom-atom and atom-molecule collisions
- Custom close-coupling codes — for electron-atom and photon-atom processes

**Analysis:**

- `numpy`, `scipy` — Clebsch-Gordan via `scipy.special`, ODE integration for dynamics
- `sympy.physics.quantum` — Symbolic angular momentum algebra
- `matplotlib` — Energy level diagrams, spectra, Stark/Zeeman maps

**Setup:**

```bash
pip install numpy scipy matplotlib qutip arc-alkali-rydberg-calculator pyscf sympy
```

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Foot, *Atomic Physics* | Modern pedagogical treatment | First reference |
| Metcalf & van der Straten, *Laser Cooling and Trapping* | Laser-atom interaction, MOT, optical molasses | Cooling and trapping |
| Bransden & Joachain, *Physics of Atoms and Molecules* | Comprehensive atomic structure and collisions | Detailed calculations |
| Scully & Zubairy, *Quantum Optics* | Quantum theory of light, coherence, squeezed states | Quantum optics theory |
| Steck, *Quantum and Atom Optics* (online text) | Modern atom optics, free reference | Quick reference |
| NIST Atomic Spectra Database (physics.nist.gov/asd) | Experimental energy levels, transition rates | Validation data |

---

## Worked Example: Rabi Oscillations in a Two-Level Atom

**Phase 1 — Setup:** Two-level atom with states |g>, |e> separated by omega_0, driven by near-resonant laser with Rabi frequency Omega and detuning Delta = omega_L - omega_0. Hamiltonian in rotating frame (RWA): H = -(hbar/2)(Delta sigma_z + Omega sigma_x). Conventions: atomic units, rotating wave approximation valid for Omega/omega_0 << 1.

**Phase 2 — Dynamics:** Solve time-dependent Schrodinger equation. Population: P_e(t) = (Omega^2/Omega_R^2) sin^2(Omega_R t/2) where Omega_R = sqrt(Delta^2 + Omega^2). Include spontaneous emission via Lindblad master equation: drho/dt = -i[H,rho] + Gamma(sigma_minus rho sigma_plus - {sigma_plus sigma_minus, rho}/2). Steady state: P_e = (s/2)/(1+s) where s = 2|Omega|^2/(Gamma^2 + 4Delta^2).

**Phase 3 — Validation:** On resonance (Delta=0): P_e oscillates between 0 and 1 at frequency Omega (Rabi flopping). With decay: damped oscillations → steady state P_e = s/(2+2s). Limits: weak drive (Omega << Gamma): P_e ~ Omega^2/Gamma^2 (rate equation regime). Strong drive (Omega >> Gamma): Autler-Townes doublet in fluorescence spectrum. Bloch-Siegert shift (beyond RWA): Delta_BS = Omega^2/(4 omega_0), verify numerically against full (non-RWA) Hamiltonian.

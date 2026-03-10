---
template_version: 1
---

# Nuclear and Particle Physics Project Template

Default project structure for nuclear structure, reaction theory, QCD at low energies, lattice QCD, and effective field theories (chiral perturbation theory, HQET, NRQCD).

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Setup** - Review prior calculations, fix conventions (isospin, CKM, operator basis), identify the process
- [ ] **Phase 2: Effective Theory Construction** - Write effective Lagrangian, identify power counting, enumerate relevant operators
- [ ] **Phase 3: Matrix Elements** - Compute hadronic/nuclear matrix elements (perturbative matching, lattice input, or model calculation)
- [ ] **Phase 4: Radiative and Loop Corrections** - Higher-order corrections, matching between theories at different scales
- [ ] **Phase 5: Phenomenology** - Physical observables (cross sections, decay rates, form factors, structure functions)
- [ ] **Phase 6: Validation and Comparison** - Compare with experimental data, lattice results, or other theoretical approaches
- [ ] **Phase 7: Paper Writing** - Draft manuscript

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Establish conventions, identify process, and catalogue prior results
**Success Criteria:**

1. [Process/observable clearly defined with all quantum numbers specified]
2. [Prior calculations catalogued: perturbative, lattice, phenomenological]
3. [Conventions fixed: isospin, CKM parametrization, operator basis, renormalization scheme]
4. [Power counting identified: chiral order, heavy quark expansion order, alpha_s order]

Plans:

- [ ] 01-01: [Survey literature, identify state of the art]
- [ ] 01-02: [Fix notation, conventions, and operator basis]

### Phase 2: Effective Theory Construction

**Goal:** Write down the effective Lagrangian with all relevant operators at the target order
**Success Criteria:**

1. [Effective Lagrangian written with complete operator basis at target order]
2. [Power counting verified: each operator assigned correct chiral/HQ/alpha_s order]
3. [Symmetry constraints checked: chiral symmetry, heavy quark symmetry, gauge invariance]
4. [Low-energy constants (LECs) identified: which are known, which must be fitted]

Plans:

- [ ] 02-01: [Construct operator basis and effective Lagrangian]
- [ ] 02-02: [Verify symmetry constraints and power counting]

### Phase 3: Matrix Elements

**Goal:** Compute matrix elements of operators between relevant states
**Success Criteria:**

1. [Matrix elements evaluated: analytically, numerically, or from lattice input]
2. [Form factors parametrized with correct analyticity and crossing properties]
3. [Lattice input properly extrapolated: continuum limit, chiral extrapolation, infinite volume]
4. [Uncertainties propagated from LECs and lattice systematics]

Plans:

- [ ] 03-01: [Compute tree-level matrix elements]
- [ ] 03-02: [Include lattice/model input for non-perturbative quantities]

### Phase 4: Radiative and Loop Corrections

**Goal:** Include higher-order corrections and match between effective theories
**Success Criteria:**

1. [Loop corrections computed at target order]
2. [UV divergences cancelled by counterterms; IR divergences handled correctly]
3. [Matching conditions between full and effective theory verified]
4. [Running of Wilson coefficients / LECs computed correctly]

Plans:

- [ ] 04-01: [Compute loop corrections]
- [ ] 04-02: [Perform matching and RG running]

### Phase 5: Phenomenology

**Goal:** Extract physical observables from theoretical expressions
**Success Criteria:**

1. [Observables computed with full uncertainty budget]
2. [Experimental inputs used consistently (PDG values, lattice averages)]
3. [Scale dependence reduced at higher orders (check cancellation)]
4. [Predictions for unmeasured quantities clearly identified]

Plans:

- [ ] 05-01: [Compute observables with uncertainty budget]
- [ ] 05-02: [Parameter fits if applicable (LECs from data)]

### Phase 6: Validation and Comparison

**Goal:** Systematic comparison with data and other theoretical approaches
**Success Criteria:**

1. [Agreement with experimental data quantified (chi-squared, pulls)]
2. [Comparison with lattice results (if applicable)]
3. [Known limits verified: heavy quark limit, chiral limit, SU(3) flavor limit]
4. [Consistency with unitarity, analyticity, crossing symmetry]

Plans:

- [ ] 06-01: [Compare with experimental data]
- [ ] 06-02: [Verify limiting cases and cross-check with other methods]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Complete manuscript with all sections]
2. [All results with full uncertainty budget]
3. [Clear comparison with prior work]
```

### Mode-Specific Phase Adjustments

**Explore mode:**
- Phase 1: Compare automated tools (MadGraph vs Sherpa vs Herwig) for the target process; benchmark cross sections at LO before committing
- Phase 2: Test multiple operator bases and power counting schemes to identify the most efficient formulation
- Phase 3: Evaluate matrix elements with multiple PDF sets (CT18, NNPDF, MSHT20) and compare central values and uncertainties
- Phase 5: Scan a broad range of parameter space to map where the model is viable before precision predictions

**Exploit mode:**
- Phase 1: Use the validated tool chain (e.g., MadGraph + Pythia8 + Delphes) without comparison runs
- Phase 2: Apply the established operator basis and power counting from the literature
- Phase 3: Use the recommended PDF set for the process class and compute matrix elements at the target kinematics only
- Phase 5: Compute observables at the specific parameter points needed for the paper

**Adaptive:** Explore tool selection and PDF sensitivity in Phase 1, then exploit the validated chain for production calculations in Phases 3+.

---

## Standard Verification Checks for Nuclear/Particle Physics

See `references/verification/core/verification-core.md` for universal checks, `references/verification/domains/verification-domain-qft.md` for QFT verification (Ward identities, unitarity, crossing symmetry), and `references/verification/domains/verification-domain-nuclear-particle.md` for nuclear/particle-specific verification (chiral power counting, LEC natural-size bounds, parton sum rules, CKM unitarity, heavy quark symmetry, isospin decomposition).

---

## Approximation Hierarchy

| Level | Chiral PT | HQET/NRQCD | Perturbative QCD | Lattice QCD |
|-------|-----------|------------|-------------------|-------------|
| LO | O(p^2) | O(1/m_Q^0) | O(alpha_s^0) | Quenched |
| NLO | O(p^4) | O(1/m_Q^1) | O(alpha_s^1) | N_f = 2+1 |
| NNLO | O(p^6) | O(1/m_Q^2) | O(alpha_s^2) | N_f = 2+1+1, physical pion mass |
| N3LO | O(p^8) | O(1/m_Q^3) | O(alpha_s^3) | Continuum + infinite volume extrapolated |

**When to use which effective theory:**
- **Chiral PT**: Energies below ~1 GeV, pion/kaon physics, nuclear forces
- **HQET**: Bottom and charm hadrons, heavy-to-light transitions
- **NRQCD**: Quarkonium spectroscopy, production at threshold
- **SCET**: Energetic hadrons in B decays, jet physics
- **Lattice QCD**: Non-perturbative matrix elements, spectrum, form factors

---

## Common Pitfalls

1. **Quenching artifacts**: Quenched lattice results miss sea quark effects. Internal quark loops absent, leading to wrong chiral behavior, wrong eta' mass, and missing unitarity. Always use dynamical fermion results for precision work.

2. **Chiral extrapolation**: Lattice simulations at unphysical pion mass require extrapolation. Naive polynomial extrapolation misses chiral logarithms. Use chiral PT-guided extrapolation with appropriate analytic structure. Check convergence of chiral expansion at the simulated pion masses.

3. **Continuum limit**: Lattice results at finite spacing a contain O(a^n) discretization artifacts (n depends on action). Must extrapolate a -> 0 using at least 3 lattice spacings. Improved actions (Symanzik) reduce leading artifacts.

4. **Operator mixing**: Under renormalization, operators can mix with others of the same quantum numbers. In particular, four-quark operators mix under QCD evolution. Wrong-chirality mixing (e.g., VLL with VLR) produces enhanced matrix elements. Always use the complete operator basis.

5. **Isospin breaking**: Neglecting m_u ≠ m_d and electromagnetic corrections introduces ~1% errors. Critical for precision flavor physics (|V_us|, epsilon'/epsilon) and light hadron spectroscopy.

6. **Scale setting**: Lattice results in lattice units require a physical quantity to set the scale. Different choices (f_pi, Omega baryon mass, t_0) can give different lattice spacings. Scale-setting uncertainty propagates to all dimensionful results.

7. **Finite volume effects**: Lattice simulations in finite box L^3. Exponentially suppressed corrections ~exp(-m_pi * L) for m_pi * L >> 1. Rule of thumb: m_pi * L > 4 for < 1% finite-volume effects. Can be corrected using chiral PT in finite volume.

8. **Power counting violations**: Higher-order terms in chiral PT or HQ expansion may be accidentally enhanced (e.g., by large coefficients, threshold effects, or Goldstone boson loops). Always check numerical convergence, not just formal power counting.

9. **CKM parametrization**: Multiple valid parametrizations exist (Wolfenstein, standard, etc.). Ensure consistent use. The Wolfenstein parametrization truncates at O(lambda^4); higher orders needed for precision CP violation.

---

## Key Tools

| Tool | Purpose | When to Use |
|------|---------|------------|
| **LHAPDF** | Parton distribution functions | DIS, hadron collider processes |
| **FastNLO / APPLgrid** | Fast NLO cross section computation | PDF fits, collider phenomenology |
| **MadGraph5_aMC@NLO** | Automated NLO event generation | Collider processes, signal/background |
| **Herwig / Pythia / Sherpa** | Parton shower Monte Carlo | Event simulation, resummation |
| **QCDSF / MILC / ETMC** | Lattice QCD gauge configurations | Non-perturbative matrix elements |
| **Chroma / Grid / QLUA** | Lattice QCD measurement codes | Correlator computation |
| **HEPfit / CKMfitter / UTfit** | Global electroweak/flavor fits | Phenomenological analysis |
| **FeynCalc / Package-X** | Loop integral evaluation | Perturbative matching, radiative corrections |
| **RunDec / CRunDec** | Running masses and couplings | alpha_s and quark mass evolution |

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Nuclear/particle projects should populate:

- **Metric Signature:** (-,+,+,+) following Peskin & Schroeder or (+,-,-,-) following Bjorken & Drell
- **Fourier Convention:** Physics convention with (2pi) placement specified
- **Gauge Choice:** Feynman gauge, Lorenz gauge, or axial gauge
- **Regularization Scheme:** Dimensional regularization (d = 4 - 2 epsilon) with MS-bar or on-shell
- **Spin Convention:** Isospin convention, CKM parametrization
- **Coupling Convention:** alpha_s = g^2/(4pi) and covariant derivative sign; specify whether amplitudes use g or alpha_s at each vertex
- **Renormalization Scheme:** MS-bar, on-shell, or momentum subtraction — intermediate results (Wilson coefficients, anomalous dimensions) are scheme-dependent

---

## Computational Environment

**Nuclear structure:**

- `NuShellX` — Shell model diagonalization for nuclear spectra
- `HFBTHO` (Fortran) — Hartree-Fock-Bogoliubov with axial deformation
- `BIGSTICK` — Large-scale CI shell model
- `nutbar` (Python) — Nuclear transition matrix elements

**Particle physics:**

- `MadGraph5_aMC@NLO` — Automated NLO cross sections for collider processes
- `Pythia8` (C++ + Python) — Parton shower, hadronization, underlying event
- `Sherpa` — Multi-purpose MC event generator
- `ROOT` (C++ + Python) — Data analysis framework (histograms, fits, I/O)
- `Rivet` (C++) — Analysis preservation, comparison with data

**Nuclear reactions:**

- `TALYS` — Nuclear reaction code: cross sections, angular distributions, spectra
- `FRESCO` (Fortran) — Coupled-channels scattering and reactions

**Analysis:**

- `numpy`, `scipy` — Woods-Saxon potential integration, decay kinematics
- `iminuit` (Python) — Minimization for chi-squared fits to data
- `particle` (Python) — PDG particle data access

**Setup:**

```bash
pip install numpy scipy matplotlib iminuit particle
# MadGraph: download from launchpad.net/mg5amcnlo
```

---

## Bibliography Seeds

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| PDG Review of Particle Physics (pdg.lbl.gov) | Current world averages, mini-reviews | Parameter values, experimental status |
| Schwartz, *QFT and the Standard Model* | Collider phenomenology, EFT, loop calculations | Particle theory |
| Ring & Schuck, *The Nuclear Many-Body Problem* | Nuclear structure: HF, BCS, RPA, shell model | Nuclear theory |
| Wong, *Introductory Nuclear Physics* | Nuclear reactions, decays, fission, fusion | Nuclear phenomenology |
| Campbell, Huston, Stirling, *Hard Interactions of Quarks and Gluons* | QCD at colliders | Collider calculations |
| de Shalit & Feshbach, *Nuclear Physics* (2 vols) | Comprehensive nuclear theory | Reference standard |

---

## Worked Example: B Meson Mixing at NLO in QCD

**Phase 1 — Setup:** B_d^0-Bbar_d^0 mixing via box diagrams with top quark and W boson. Effective Hamiltonian: H_eff = (G_F^2 M_W^2)/(16pi^2) (V_tb V_td*)^2 C(x_t) O where x_t = m_t^2/M_W^2 and O = [bbar gamma_mu (1-gamma_5) d]^2. Conventions: MS-bar, NDR (naive dimensional regularization for gamma_5).

**Phase 2 — Calculation:** Inami-Lim function S_0(x_t) at LO. NLO QCD corrections: eta_B = alpha_s(mu)^{-6/23} [1 + alpha_s(mu)/(4pi) * J_5] where J_5 is the scheme-dependent NLO coefficient. Anomalous dimension of O: gamma_0 = 4, gamma_1 = (-52/3 + ...) in NDR. Run Wilson coefficient from M_W to m_b scale.

**Phase 3 — Validation:** Mass difference Delta_m_d from |M_12| = (G_F^2 M_W^2)/(12pi^2) m_B f_B^2 B_B eta_B S_0(x_t) |V_tb V_td*|^2. With f_B sqrt(B_B) = 216 MeV (lattice), |V_td| from CKM fit: Delta_m_d = 0.507 ps^{-1}. Compare PDG: Delta_m_d = 0.5065(19) ps^{-1}. Dimensional check: [G_F^2 M_W^2 m_B f_B^2] = [energy]^{-4}[energy]^2[energy][energy]^2 = [energy] = [1/time]. Correct.

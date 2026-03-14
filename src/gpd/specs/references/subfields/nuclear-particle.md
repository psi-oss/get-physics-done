---
load_when:
  - "nuclear physics"
  - "particle physics"
  - "cross section"
  - "Standard Model"
  - "QCD"
  - "Higgs"
  - "neutrino"
  - "parton"
tier: 2
context_cost: medium
---

# Nuclear and Particle Physics

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/perturbation-theory.md` (Feynman diagram computation, loop integrals), `references/protocols/lattice-gauge-theory.md` (non-perturbative QCD, hadron spectrum), `references/protocols/effective-field-theory.md` (chiral perturbation theory, HQET, SCET), `references/protocols/phenomenology.md` (likelihoods, global fits, recasting, EFT validity), `references/protocols/scattering-theory.md` (cross sections, partial waves, resonances), `references/protocols/renormalization-group.md` (running couplings, beta functions, asymptotic freedom), `references/protocols/path-integrals.md` (functional methods, instantons, anomalies), `references/protocols/group-theory.md` (gauge symmetry, representations, Clebsch-Gordan), `references/protocols/resummation.md` (Borel summation of QCD perturbative series), `references/protocols/large-n-expansion.md` ('t Hooft limit, 1/N_c expansion), `references/protocols/random-matrix-theory.md` (nuclear level spacings, Dirac operator spectra in QCD).

**Cross Sections and Decay Rates:**

- Differential cross section: d_sigma/d_Omega = |M|^2 / (64*pi^2*s) \* (p_f/p_i) for 2->2 (CM frame)
- Decay rate: Gamma = (1/(2*M)) * integral |M|^2 * d_LIPS (Lorentz-invariant phase space)
- Breit-Wigner resonance: sigma(E) ~ Gamma_i \* Gamma_f / ((E - M_R)^2 + Gamma^2/4)
- Narrow-width approximation: replace Breit-Wigner by delta function when Gamma/M << 1
- Phase space: d_LIPS = prod_f d^3p_f / ((2*pi)^3 * 2*E_f) * (2*pi)^4 \* delta^4(p_i - sum p_f)

**Form Factors and Structure Functions:**

- Electromagnetic form factors: parameterize nucleon matrix elements of current
- Sachs form factors: G_E(Q^2), G_M(Q^2) for proton and neutron
- Deep inelastic scattering: structure functions F_1(x, Q^2), F_2(x, Q^2); Bjorken scaling + logarithmic corrections
- Parton model: F*2(x) = sum_q e_q^2 * x \_ f_q(x); f_q(x) are parton distribution functions

**Parton Distribution Functions (PDFs):**

- DGLAP evolution: Q^2 * d_f/d_Q^2 = (alpha_s / 2*pi) \* P tensor f (splitting functions P_qq, P_qg, P_gq, P_gg)
- PDF sets: CT18, NNPDF4.0, MSHT20; each provides central value + uncertainties (Hessian or MC replicas)
- Sum rules: momentum sum rule integral_0^1 x \* [sum_q (f_q + f_qbar) + f_g] dx = 1
- Small-x: gluon dominance; BFKL evolution; saturation (Color Glass Condensate)

**Effective Theories:**

- **HQET (Heavy Quark Effective Theory):** Expansion in 1/m_Q; heavy quark symmetry (spin + flavor); Isgur-Wise function
- **SCET (Soft-Collinear Effective Theory):** Expansion in lambda = Q_perp/Q; jet physics, threshold resummation
- **Chiral Perturbation Theory (ChPT):** Expansion in p/Lambda_chi and m_q/Lambda_chi; pion physics; SU(2) and SU(3) versions
- **NRQCD:** Non-relativistic expansion for heavy quarkonium; v^2 ~ 0.3 for charmonium, v^2 ~ 0.1 for bottomonium

**Collider Phenomenology:**

- Parton-level cross sections -> hadron-level via PDF convolution: sigma = integral f_a * f_b * sigma-hat _ dx_a _ dx_b
- Jets: anti-k_T algorithm (standard at LHC); cone size R; jet energy calibration
- Missing transverse energy: imbalance in transverse plane; signatures of neutrinos, dark matter candidates
- Background estimation: data-driven methods (ABCD, sideband fits, template methods)

**Phenomenology Workflow:**

- State whether the task is a parameter scan, global fit, recast, reinterpretation, or sensitivity forecast
- Prefer fiducial observables and public likelihoods/covariance matrices over back-solving from a quoted 95% CL number
- Propagate correlated experimental systematics, PDF/scale uncertainties, and nuisance parameters consistently
- In EFT fits, state the operator basis, matching scale, running, truncation order, and kinematic validity cuts

**Nuclear Structure:**

- Shell model: nucleons fill single-particle levels; magic numbers (2, 8, 20, 28, 50, 82, 126)
- Hartree-Fock: self-consistent mean field from nuclear force; Skyrme or Gogny interaction
- Nuclear DFT: energy density functional approach; Skyrme, Gogny, relativistic mean field
- Ab initio: chiral EFT interactions -> many-body methods (coupled cluster, in-medium SRG, quantum MC)

## Key Tools and Software

| Tool                        | Purpose                              | Notes                                                                              |
| --------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------- |
| **MadGraph5_aMC@NLO**       | Automated matrix element generation  | Tree + NLO; SM and BSM; parton-level events                                        |
| **Pythia 8**                | Parton shower + hadronization        | Lund string model; underlying event; standard for LHC                              |
| **Herwig 7**                | Alternative MC event generator       | Angular-ordered shower; cluster hadronization                                      |
| **Sherpa**                  | Multi-purpose MC generator           | Automated NLO; multijet merging (MEPS@NLO)                                         |
| **Geant4**                  | Detector simulation                  | Full simulation of particle interactions with matter; standard for LHC experiments |
| **Delphes**                 | Fast detector simulation             | Parameterized response; useful for phenomenology studies                           |
| **ROOT**                    | Data analysis framework (C++/Python) | Histograms, fitting, I/O; standard in HEP                                          |
| **HepMC3**                  | Event record format                  | Standard interface between generators and detector simulation                      |
| **Rivet**                   | Analysis preservation                | Validated analyses from published papers; comparison with data                     |
| **pyhf**                    | Public likelihood inference          | HistFactory/JSON statistical models; reinterpretation and profiling                |
| **LHAPDF**                  | Parton distribution functions        | Standard PDF interface; all major PDF sets                                         |
| **FastJet**                 | Jet finding algorithms               | anti-k_T, Cambridge/Aachen, k_T; standard for jet physics                          |
| **CheckMATE / MadAnalysis** | BSM reinterpretation                 | Recasting LHC searches for new physics                                             |
| **SModelS**                 | Simplified model constraints         | Database of LHC constraints on BSM                                                 |
| **FeynRules**               | Model file generation                | Define BSM models; generate UFO output for MadGraph                                |
| **SARAH**                   | SUSY model builder                   | Generates model files, RGEs, mass spectra                                          |
| **HEPfit**                  | Global precision fits                | Bayesian/statistical fits combining EW, Higgs, flavor, and BSM observables         |
| **flavio**                  | Flavor and precision phenomenology   | Predictions, likelihoods, and plots for WET/SMEFT-style analyses                   |
| **EOS**                     | Flavor likelihoods and inference     | Predictions, Bayesian inference, and pseudo-event simulation                        |
| **SMEFiT**                  | SMEFT global fits                    | Multi-operator EFT inference with basis rotations and reporting tools              |
| **NuShellX / BIGSTICK**     | Nuclear shell model                  | Large-scale shell model diagonalization                                            |

## Validation Strategies

**Branching Ratio Sum:**

- Sum of all branching ratios must equal 1: sum_i BR_i = 1
- PDG provides measured branching ratios; check consistency
- Partial widths: Gamma_i = BR_i \* Gamma_total

**Mandelstam Variables:**

- For 2 -> 2: s + t + u = m_1^2 + m_2^2 + m_3^2 + m_4^2
- Physical regions: s-channel (s > 0, t < 0), t-channel (t > 0, s < 0), etc.
- Check: computed amplitudes must satisfy crossing symmetry between channels

**Froissart Bound:**

- Total cross section sigma_total(s) <= (pi/m_pi^2) \* ln^2(s/s_0) at high energy
- Any model predicting cross section growing faster than ln^2(s) violates unitarity
- Check: high-energy behavior of computed cross sections

**CKM Unitarity:**

- |V_ud|^2 + |V_us|^2 + |V_ub|^2 = 1 (first row unitarity)
- Experimentally: 0.9985(5), consistent with unitarity
- Check: any model with modified CKM elements must preserve unitarity

**Adler Sum Rule / Gottfried Sum Rule:**

- Adler: integral_0^1 [F_2^(nu*p) - F_2^(nu-bar*p)] dx/x = 2
- Gottfried: integral_0^1 [F_2^p - F_2^n] dx/x = 1/3 + (2/3) \* integral [u-bar - d-bar] dx
- Check: PDF sets must satisfy these sum rules

**Standard Candles:**

- Z boson production: precisely calculated; check MC prediction vs ATLAS/CMS data
- W+jets: important background; validate multi-jet description
- Top quark pair production: known to NNLO; compare with measured cross section
- Drell-Yan: clean theoretical prediction; standard comparison for PDFs

**Likelihoods and Fits:**

- Use the published covariance matrix or public likelihood when available; summary tables are not a substitute
- Distinguish a profile-likelihood limit, a Bayesian credible interval, and a best-fit point; they are not interchangeable outputs
- In EFT fits, inspect operator correlations and flat directions before quoting a "bound" on a single coefficient

## Common Pitfalls

- **Incorrect color factors:** SU(3) group theory: C_F = 4/3, C_A = 3, T_R = 1/2. Misidentifying these changes cross sections by O(1) factors
- **Wrong flux factor:** Cross section formula requires 1/(2*E_A * 2*E_B * |v_A - v_B|) in the lab or 1/(2\*s) in CM (massless). Getting this wrong changes sigma by factors of 4
- **Neglecting PDF uncertainties:** Central PDF set gives only central value. Must propagate PDF uncertainties (Hessian error sets or MC replicas) to get theory error band
- **NLO vs LO K-factors not universal:** K = sigma_NLO / sigma_LO depends on process, kinematics, and scale choice. Do not apply a K-factor from one process to another
- **Forgetting spin averaging for initial state:** Unpolarized cross section requires 1/(2*s_A + 1)/(2*s_B + 1) averaging factor. For gluons: 1/2 from transverse polarizations in d=4 (but 1/(d-2) in dimensional regularization)
- **Infrared safety of observables:** Only IR-safe observables (jets, event shapes) have well-defined perturbative predictions. Particle-level observables (individual hadron spectra) require fragmentation functions
- **Scale variation as theory uncertainty:** Varying mu_R and mu_F by factor of 2 is convention, not a rigorous uncertainty estimate. True error can be larger, especially when NLO corrections are large
- **Comparing to the wrong observable definition:** Detector-level, fiducial, and unfolded results are not interchangeable. Match the published analysis object exactly.
- **One-operator-at-a-time EFT bounds:** Single-coefficient limits can disappear once correlations and flat directions are included in a global fit.
- **Unvalidated recasting:** A reinterpretation that does not reproduce published benchmark efficiencies, cutflows, or SM yields is not yet a trustworthy constraint.

---

## Research Frontiers (2024-2026)

| Frontier | Key question | GPD suitability |
|----------|-------------|-----------------|
| **Neutrino mass mechanism** | Dirac vs Majorana, neutrinoless double-beta decay predictions | Good — nuclear matrix elements + BSM models |
| **Muon g-2 anomaly** | SM prediction vs experiment — is there new physics at 5sigma? | Excellent — multi-loop QED/QCD/EW calculations |
| **Global SMEFT / public-likelihood fits** | How do correlated electroweak, Higgs, top, Drell-Yan, and flavor data constrain multi-operator new physics? | Excellent — EFT matching, likelihood bookkeeping, and public reinterpretation tools fit the workflow well |
| **Nuclear EFT (chiral EFT)** | Systematic nuclear forces from chiral perturbation theory | Good — power counting + many-body methods |
| **Quark-gluon plasma** | QGP properties from heavy-ion collisions, jet quenching, flow | Moderate — requires hydro + transport codes |
| **Dark matter direct detection** | Nuclear response functions for WIMP-nucleus scattering | Good — shell model + EFT matching |
| **Precision flavor physics** | CKM unitarity, CP violation, rare B/K decays | Excellent — EFT matching + lattice inputs |

## Methodology Decision Tree

```
Particle or nuclear?
├── Particle (collider / BSM)
│   ├── Cross section needed? → MadGraph/Sherpa (automated NLO)
│   ├── Decay rate? → Analytic (tree/loop) or heavy quark expansion
│   ├── Flavor observable? → OPE → Wilson coefficients × hadronic matrix elements
│   └── BSM search? → Model implementation (FeynRules/UFO) → signal simulation
├── Nuclear structure
│   ├── Light nuclei (A < 12)? → Ab initio (NCSM, Green's function MC)
│   ├── Medium nuclei (12 < A < 60)? → Shell model (CI)
│   ├── Heavy nuclei? → DFT (Skyrme, Gogny) or relativistic mean field
│   └── Exotic/drip line? → Continuum methods (Gamow shell model)
└── Nuclear reactions
    ├── Low energy? → R-matrix, coupled channels
    ├── Intermediate? → DWBA, Glauber model
    └── High energy? → Eikonal approximation, Regge theory
```

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One process at NLO, or nuclear structure calculation for one nucleus/observable | "NLO QCD corrections to Higgs + jet production with full top mass dependence" |
| **Postdoc** | Multi-process phenomenology, or new EFT development | "Chiral EFT three-body forces in neutron-rich isotopes" |
| **Faculty** | New theoretical framework or definitive experimental comparison | "Complete basis of dimension-8 SMEFT operators and their collider signatures"

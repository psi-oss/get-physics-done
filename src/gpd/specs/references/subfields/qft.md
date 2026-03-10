---
load_when:
  - "quantum field theory"
  - "QFT"
  - "Feynman diagram"
  - "renormalization"
  - "gauge theory"
  - "Standard Model"
  - "propagator"
tier: 2
context_cost: medium
---

# Quantum Field Theory

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/perturbation-theory.md`, `references/protocols/renormalization-group.md`, `references/protocols/path-integrals.md`, `references/protocols/effective-field-theory.md`, `references/protocols/lattice-gauge-theory.md`, `references/protocols/analytic-continuation.md`, `references/protocols/finite-temperature-field-theory.md`, `references/protocols/supersymmetry.md`, `references/protocols/algebraic-qft.md`, `references/protocols/string-field-theory.md`, `references/protocols/conformal-bootstrap.md`, `references/protocols/holography-ads-cft.md`, `references/protocols/asymptotic-symmetries.md`, `references/protocols/generalized-symmetries.md`, `references/protocols/green-functions.md`, `references/protocols/wkb-semiclassical.md`, `references/protocols/resummation.md` (Borel summation, Pade, divergent series), `references/protocols/large-n-expansion.md` ('t Hooft limit, planar diagrams, matrix models).

**Feynman Diagrams and Perturbation Theory:**

- Expand S-matrix in powers of coupling constants
- Feynman rules from the Lagrangian: propagators, vertices, symmetry factors
- Loop integrals via dimensional regularization (d = 4 - 2*epsilon)
- Standard integral reduction: Passarino-Veltman decomposition, integration-by-parts (IBP) identities
- Multi-loop calculations: sector decomposition, Mellin-Barnes representations

**Renormalization:**

- **MS-bar scheme:** Subtract poles in epsilon plus ln(4*pi) - gamma_E; most common in perturbative QCD and electroweak theory
- **On-shell scheme:** Fix parameters to physical masses and couplings; standard for QED and precision electroweak
- **Momentum subtraction (MOM):** Subtract at a specific momentum point; used in lattice QCD matching
- **Wilsonian RG:** Integrate out shells in momentum space; conceptual foundation, used in condensed matter crossover
- **Functional RG (Wetterstein equation):** Exact flow equation for effective average action; non-perturbative applications

**Regularization:**

- **Dimensional regularization:** Standard for gauge theories; preserves gauge invariance. Poles appear as 1/epsilon^n
- **Pauli-Villars:** Introduce heavy regulator fields; breaks gauge invariance for non-Abelian theories
- **Lattice regularization:** Discretize spacetime; gauge-invariant, non-perturbative. Breaks Lorentz invariance (recovered in continuum limit)
- **Zeta-function regularization:** For determinants and Casimir effects
- **Point-splitting:** For composite operators in curved spacetime

**Gauge Theories:**

- **QED:** U(1) gauge theory; alpha ~ 1/137; perturbation theory extremely accurate
- **QCD:** SU(3) color gauge theory; asymptotically free (alpha_s decreases at high energy); confinement at low energy
- **Electroweak:** SU(2)\_L x U(1)\_Y spontaneously broken to U(1)\_EM via Higgs mechanism
- Gauge fixing: Lorenz gauge (covariant), Coulomb gauge (physical), axial gauge (ghost-free), background field gauge (preserves gauge invariance of effective action)
- Faddeev-Popov ghosts: Required in covariant gauges for non-Abelian theories; contribute to loops

**Generalized Symmetries and Defects:**

- A `p`-form symmetry acts on `p`-dimensional operators and couples to a `(p+1)`-form background field
- Center symmetry in pure gauge theory acts on Wilson lines and is explicitly broken by dynamical fundamental matter
- Higher-group symmetry requires mixed transformation laws for ordinary and higher-form background fields
- Non-invertible symmetry requires topological defects with non-group-like fusion; duality language alone is not enough

**Algebraic Quantum Field Theory:**

- Haag-Kastler nets encode local observables region by region and make locality, covariance, and additivity primary structural data
- Modular theory links operator-algebraic structure to vacuum and thermal properties; Bisognano-Wichmann is a standard benchmark rather than a generic identity
- Local relativistic algebras are typically hyperfinite type `III_1`, which is why ordinary finite-subsystem density-matrix intuition fails in continuum QFT
- DHR sectors and conformal nets give rigorous charge and extension data when the structural question is more important than perturbative amplitudes

**Supersymmetric Field Theory:**

- 4d `N=1`: holomorphy, superpotential non-renormalization, anomaly constraints, and controlled soft breaking
- 4d `N=2`: Coulomb/Higgs branches, Seiberg-Witten geometry, BPS spectra, and localization-compatible observables
- 4d `N=4`: exact conformality, S-duality, integrability, and AdS/CFT benchmark structure
- Protected quantities include the Witten index, superconformal index, localized partition functions, and BPS Wilson or defect observables

**Effective Field Theories (EFTs):**

- Organize physics by energy scale: integrate out heavy degrees of freedom
- Power counting: expansion parameter is E/Lambda (energy over cutoff)
- Matching: compute Wilson coefficients by requiring EFT reproduces full theory at matching scale
- Running: RG evolution between scales using anomalous dimensions
- Examples: Fermi theory (from electroweak), chiral perturbation theory (from QCD), HQET (heavy quark), SCET (soft-collinear), NRQCD (non-relativistic QCD)

**Lattice QFT:**

- Wilson gauge action or improved actions (Symanzik, Iwasaki, DBW2)
- Fermion discretizations: Wilson, staggered, domain-wall, overlap (exact chiral symmetry)
- Monte Carlo sampling of path integral via importance sampling
- Signal-to-noise problems at large Euclidean times and for baryons
- Continuum limit: extrapolate a -> 0 guided by Symanzik effective theory

**Path Integral Methods:**

- Functional integral formulation: Z = integral D[phi] exp(i*S[phi])
- Saddle-point/stationary phase approximation for semiclassical limit
- Instantons: classical solutions in Euclidean space; tunneling, vacuum structure, theta parameter
- Schwinger-Dyson equations: exact functional relations between Green's functions

**String Field Theory:**

- Off-shell formulation of string interactions with BRST gauge structure
- Open bosonic cubic SFT, Berkovits WZW-like superstring SFT, and modern `A_infinity` / `L_infinity` formulations
- Benchmark problems: tachyon condensation, marginal deformations, shifted backgrounds, and open/closed couplings
- Verification requires ghost/picture bookkeeping, BPZ cyclicity, and control of level truncation

## Key Tools and Software

| Tool                  | Purpose                                   | Notes                                                             |
| --------------------- | ----------------------------------------- | ----------------------------------------------------------------- |
| **FORM**              | Symbolic algebra for Feynman diagrams     | Handles large expressions; standard for multi-loop; C-like syntax |
| **FeynCalc**          | Mathematica package for Feynman integrals | Dirac algebra, Passarino-Veltman reduction, tensor decomposition  |
| **FeynArts**          | Diagram generation                        | Generates all diagrams for a given process at given loop order    |
| **Package-X**         | One-loop integral evaluation              | Analytic results for all one-loop integrals in 4d                 |
| **FIRE / LiteRed**    | IBP reduction                             | Reduces multi-loop integrals to master integrals                  |
| **MadGraph5_aMC@NLO** | Automated NLO calculations                | Tree + one-loop for SM and BSM; event generation                  |
| **LHAPDF**            | Parton distribution functions             | Standard interface for PDF sets (CT18, NNPDF, MSHT)               |
| **Pythia**            | Parton shower and hadronization           | Event-level Monte Carlo; fragmentation, underlying event          |
| **Sherpa**            | Multi-purpose MC event generator          | Automated NLO, multijet merging                                   |
| **OpenLoops**         | One-loop amplitude provider               | Numerical evaluation via recursion                                |
| **qgraf**             | Diagram generation                        | Generates Feynman diagrams as symbolic output                     |
| **HEPfit**            | Electroweak precision fits                | Global fits to SM and BSM parameters                              |

## Validation Strategies

**Ward Identities:**

- For QED: q_mu * Gamma^mu(p, p+q) = S^{-1}(p+q) - S^{-1}(p) (relates vertex to propagators)
- For QCD: Slavnov-Taylor identities (non-Abelian generalization)
- Any amplitude with a longitudinal gauge boson must vanish for physical processes
- Check: Replace epsilon_mu(k) -> k_mu in any amplitude; result must cancel for gauge-invariant observables

**Unitarity:**

- Optical theorem: 2*Im[M(a->a)] = sum_f integral |M(a->f)|^2 * (phase space)
- Cutkosky rules: discontinuity of loop diagram = product of tree-level amplitudes across the cut
- Check: imaginary parts of amplitudes must be positive (for forward scattering)
- S-matrix unitarity: S^dag S = 1; implies relations between different-order amplitudes

**Gauge Invariance:**

- Physical observables must be independent of gauge-fixing parameter xi
- Check: compute cross section in Feynman gauge (xi=1) and Landau gauge (xi=0); results must agree
- Effective potential must be gauge-invariant at its extrema (Nielsen identity)

**UV Divergence Structure:**

- For renormalizable theories: only a finite number of divergent structures
- Superficial degree of divergence D = 4 - E_b - (3/2)*E_f + ... (depends on external legs)
- Check: divergences in computed amplitudes match expected structure from power counting
- Beta functions: one-loop coefficient is scheme-independent

**Crossing Symmetry:**

- M(a b -> c d) related to M(a c-bar -> b-bar d) by analytic continuation
- Mandelstam variables: s + t + u = sum of squared masses
- Check: crossed amplitudes must satisfy crossing relations

**Decoupling:**

- Heavy particles decouple at low energies (Appelquist-Carazzone theorem)
- Check: taking a particle mass to infinity must reproduce the EFT without that particle

## Common Pitfalls

- **Overlooking symmetry factors in Feynman diagrams:** Each diagram has a combinatorial factor; missing it changes the amplitude. Check: identical particle factors, automorphism group of the diagram
- **Incorrect signs from fermion loops:** Closed fermion loops carry a factor of (-1). Fermion line ordering matters for relative signs between diagrams
- **Confusing MS-bar and on-shell masses:** Mass values differ by O(alpha) corrections. Using the wrong mass definition introduces spurious large logarithms
- **Dropping evanescent operators in dimensional regularization:** Operators that vanish in d=4 can contribute when multiplied by 1/epsilon poles
- **Infrared divergences:** Soft and collinear divergences cancel in inclusive observables (KLN theorem) but must be handled correctly -- incomplete cancellation is a common error
- **Ignoring renormalization group running:** Wilson coefficients evolve between scales; neglecting running introduces logarithmically enhanced errors
- **Wrong normalization of states:** Relativistic normalization <p|p'> = 2E (2pi)^3 delta^3(p-p') vs non-relativistic normalization. Affects cross sections by factors of 2E
- **Forgetting ghost contributions:** In covariant gauges for non-Abelian theories, Faddeev-Popov ghosts contribute to loops. Omitting them violates unitarity
- **Analytic continuation errors:** Minkowski vs Euclidean signature requires careful Wick rotation. Branch cuts must be handled correctly (i*epsilon prescription)

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Amplitudes bootstrap** | Can on-shell methods (BCFW, generalized unitarity) replace Feynman diagrams at high loops? | Arkani-Hamed, Dixon, Bern, Zvi group | Excellent — symbolic algebra intensive |
| **Asymptotic symmetries / celestial amplitudes** | How are infrared soft theorems, large gauge symmetries, and celestial currents encoded in scattering observables? | Strominger, Pasterski, Donnay, Raclariu, Pate | Good — symmetry constraints are strong; full celestial dictionary is still developing |
| **Generalized symmetries / defects** | How do higher-form, higher-group, and non-invertible symmetries constrain phases, anomalies, and operator algebras in QFT? | Komargodski, Cordova, Iqbal, Schafer-Nameki, Gaiotto | Good — strong on defect/anomaly logic; categorical classification is still moving fast |
| **Supersymmetric QFT / protected sectors** | How far can localization, indices, dualities, and superconformal constraints determine strongly coupled dynamics? | Pestun, Rastelli, Razamat, Tachikawa, Komargodski | Excellent — protected observables are highly constrained; unprotected quantities still need explicit control |
| **Asymptotic safety** | Does gravity have a UV fixed point? Compute critical exponents of the gravitational RG | Reuter, Percacci, Eichhorn groups | Good — functional RG, truncation systematics |
| **Conformal bootstrap** | Determine CFT data (dimensions, OPE coefficients) non-perturbatively | Simmons-Duffin, Poland, Rychkov | Excellent — algebraic + numerical optimization |
| **Algebraic QFT / operator algebras** | Which local-net, modular, and superselection structures are universal in relativistic QFT and curved spacetime? | Buchholz, Fewster, Longo, Naaijkens, Verch | Good — structural control is strong; concrete model construction is still hard |
| **String field theory** | Can off-shell string interactions and background shifts be controlled in a formulation that remains computationally practical? | Sen, Zwiebach, Erler, Schnabl, Maccaferri | Good — algebraic and gauge-structure heavy; truncation control is essential |
| **Precision Higgs/EW** | NNLO and N3LO corrections for LHC processes | CERN theory, Mistlberger, Czakon | Good — multi-loop integrals, IBP reduction |
| **Non-perturbative QCD** | Lattice determination of hadron spectrum, form factors, PDFs at physical quark masses | BMW, RBC-UKQCD, MILC, ETM | Moderate — requires lattice infrastructure |
| **EFT for gravitational waves** | Post-Minkowskian expansion for binary inspiral: quantum field theory methods for classical gravity | Bern, Cheung, Porto, Buonanno | Excellent — Feynman diagrams + classical limit |

## Methodology Decision Tree

```
Is there a small expansion parameter?
├── YES (g << 1, alpha << 1, 1/N >> 0)
│   ├── Fixed order sufficient? → Perturbation theory (Feynman diagrams)
│   ├── Large logarithms? → Resum via RG (DGLAP, BFKL, Sudakov)
│   └── Threshold/Coulomb effects? → NRQCD, SCET, or potential methods
├── NO (strong coupling)
│   ├── Lattice feasible? → Lattice QFT (Monte Carlo)
│   ├── Large N? → 1/N expansion, holography
│   ├── Local-observable / modular / type-III question? → Algebraic QFT
│   ├── Stringy off-shell background problem? → String field theory
│   ├── Conformal? → Bootstrap methods
│   └── Topological? → Exact results (instantons, anomalies, index theorems)
└── MIXED (perturbative + non-perturbative)
    ├── Factorizable? → Match perturbative (Wilson coefficients) × non-perturbative (matrix elements)
    └── Not factorizable? → Lattice or model-dependent approaches
```

## Common Collaboration Patterns

- **QFT + Experiment (colliders):** Theorists provide predictions (NLO/NNLO cross sections), experimentalists provide measurements. Comparison constrains BSM physics. Tools: MadGraph, Sherpa → HEPData format.
- **QFT + Cosmology:** EFT of inflation, baryogenesis calculations, dark matter annihilation cross sections. Shared language: Feynman diagrams in curved spacetime.
- **QFT + Condensed Matter:** Shared methods (RG, path integrals, anomalies). Condensed matter provides lattice-like UV completions; QFT provides universal scaling predictions.
- **QFT + Mathematics:** Amplitudes ↔ algebraic geometry (Grassmannians, motivic periods). Anomalies ↔ index theory. TQFTs ↔ knot invariants.

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One complete NLO calculation for a specific process, or one new EFT matching at one-loop | "NLO QCD corrections to pp → ttbar H" |
| **Postdoc** | Multi-process program, new method development, or NNLO calculation | "NNLO corrections to Drell-Yan with fiducial cuts" |
| **Faculty** | New framework, all-orders resummation, or paradigm-shifting approach | "Color-kinematics duality and the double copy for gravitational waves"

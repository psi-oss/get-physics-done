---
template_version: 1
---

# QFT Calculation Project Template

Default project structure for quantum field theory calculations: perturbative amplitudes, cross sections, effective field theory matching, renormalization group analysis, and non-perturbative methods.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Setup** - Review prior calculations, establish conventions, identify the process/observable
- [ ] **Phase 2: Lagrangian and Feynman Rules** - Write down the Lagrangian, derive Feynman rules, identify relevant diagrams
- [ ] **Phase 3: Regularization and Loop Integrals** - Evaluate loop integrals using dimensional regularization, perform integral reduction
- [ ] **Phase 4: Renormalization** - Renormalize divergences in chosen scheme, extract finite physical results
- [ ] **Phase 5: Cross Sections and Observables** - Compute physical observables (cross sections, decay rates, anomalous dimensions)
- [ ] **Phase 6: Limiting Cases and Validation** - Verify known limits, check gauge invariance, test Ward identities
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Establish conventions, identify the process, and catalogue prior results at the target loop order
**Success Criteria:**

1. [Process/observable clearly defined with all external states specified]
2. [Prior calculations at same or lower order catalogued with their results]
3. [Conventions fixed: metric signature, gamma matrix representation, coupling normalization, regularization scheme]
4. [Power counting performed: identify expected UV divergence structure]

Plans:

- [ ] 01-01: [Survey literature for existing calculations of this process]
- [ ] 01-02: [Fix notation and conventions; document in NOTATION_GLOSSARY.md]

### Phase 2: Lagrangian and Feynman Rules

**Goal:** Derive complete set of Feynman rules and enumerate all contributing diagrams at target order
**Success Criteria:**

1. [Lagrangian written with all relevant terms and counterterms]
2. [Feynman rules derived: propagators, vertices, ghost vertices (if non-Abelian)]
3. [All diagrams at target loop order enumerated with symmetry factors]
4. [Diagram generation cross-checked (e.g., qgraf or FeynArts output vs manual enumeration)]

Plans:

- [ ] 02-01: [Write Lagrangian and derive Feynman rules]
- [ ] 02-02: [Generate and enumerate all contributing diagrams]

### Phase 3: Regularization and Loop Integrals

**Goal:** Evaluate all loop integrals, reducing to master integrals where necessary
**Success Criteria:**

1. [All loop integrals expressed in dimensional regularization (d = 4 - 2*epsilon)]
2. [Tensor reduction performed (Passarino-Veltman or IBP)]
3. [Master integrals evaluated or looked up from known results]
4. [UV poles (1/epsilon^n) and IR poles explicitly separated and identified]

Plans:

- [ ] 03-01: [Perform tensor reduction and express in terms of scalar integrals]
- [ ] 03-02: [Evaluate scalar master integrals]
- [ ] 03-03: [Combine diagrams and simplify; identify cancellations]

### Phase 4: Renormalization

**Goal:** Renormalize all divergences and obtain finite physical results in the chosen scheme
**Success Criteria:**

1. [Counterterms determined in chosen scheme (MS-bar / on-shell / MOM)]
2. [All UV divergences cancelled by counterterms]
3. [IR divergences either cancelled in inclusive observable or factored into universal functions]
4. [Running coupling / anomalous dimensions extracted if applicable]
5. [Scheme dependence verified: one-loop beta function is scheme-independent]

Plans:

- [ ] 04-01: [Determine counterterms and perform renormalization]
- [ ] 04-02: [Verify UV finiteness and extract running couplings]

### Phase 5: Cross Sections and Observables

**Goal:** Compute physical observables from renormalized amplitudes
**Success Criteria:**

1. [Amplitude squared computed, summed/averaged over spins and colors]
2. [Phase space integration performed for cross section or decay rate]
3. [Result expressed in terms of physical parameters with numerical values]
4. [Uncertainty estimate from truncation of perturbative series (scale variation)]

Plans:

- [ ] 05-01: [Compute |M|^2 and perform spin/color sums]
- [ ] 05-02: [Integrate over phase space; obtain cross section or decay rate]

### Phase 6: Limiting Cases and Validation

**Goal:** Verify results through independent cross-checks
**Success Criteria:**

1. [Ward identity satisfied: q_mu * Gamma^mu gives expected result]
2. [Gauge invariance: result independent of gauge parameter xi]
3. [Known limits reproduced: soft limit, collinear limit, heavy-mass decoupling]
4. [Crossing symmetry verified where applicable]
5. [Comparison with published results at same order (if available)]

Plans:

- [ ] 06-01: [Check Ward identities and gauge invariance]
- [ ] 06-02: [Verify limiting cases and compare with literature]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with all sections and figures]
2. [All results presented with scheme specification and scale dependence]
3. [Comparison with prior work clearly stated]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 2 splits:** Create parallel plans for different diagram topologies or regularization schemes (e.g., dim-reg vs cutoff). Compare at phase boundary.
- **Phase 3 branches:** If multiple integral reduction strategies exist (IBP vs Mellin-Barnes vs sector decomposition), branch and evaluate. Pick the most efficient.
- **Extra phase:** Add "Phase 3.5: Method Comparison" — evaluate which approach gives fastest convergence and cleanest UV structure. Inform Phase 4 choice.
- **Literature depth:** 15+ papers, including failed approaches and alternative formalisms.

### Exploit Mode
- **Phases 1-2 compressed:** Skip deep literature survey if the process and method are well-known. Go directly from Lagrangian to diagram enumeration in one plan.
- **Phase 3 focused:** Use the standard reduction method (IBP for multi-loop, PV for one-loop). No comparison.
- **Skip Phase 7:** If results feed into a larger project, skip paper writing. Output is SUMMARY.md with verified results.
- **Skip researcher:** If the calculation follows a known pattern (same process at higher order, or same method for new process).

### Adaptive Mode
- Start in explore for Phases 1-3 (method selection).
- Switch to exploit for Phases 4-6 once the integral reduction strategy is chosen and validated.

---

## Standard Verification Checks for QFT

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-qft.md` for QFT-specific verification (Ward identities, unitarity, crossing symmetry).

---

## Typical Approximation Hierarchy

| Level           | Approximation             | Expansion Parameter | Typical Accuracy              |
| --------------- | ------------------------- | ------------------- | ----------------------------- |
| LO (tree-level) | Leading order in coupling | alpha^n             | O(1) estimate; qualitative    |
| NLO (one-loop)  | Next-to-leading order     | alpha^{n+1}         | ~10-30% corrections typical   |
| NNLO (two-loop) | Next-to-next-to-leading   | alpha^{n+2}         | ~few % corrections            |
| N3LO            | Three-loop                | alpha^{n+3}         | Sub-percent for QCD processes |
| Resummed        | All-orders partial sum    | log^n(Q/mu) terms   | Required when logs are large  |

**When to go beyond fixed order:**

- Large logarithms ln(Q/m) >> 1: resum via RG evolution
- Threshold region: resum Sudakov logarithms or Coulomb corrections
- Soft/collinear emissions: SCET or parton shower matching

---

## Common Pitfalls for QFT Calculations

1. **Symmetry factors:** Each diagram has a combinatorial factor from the path integral. Missing it changes the amplitude. Cross-check: diagram generation software (qgraf, FeynArts) assigns symmetry factors automatically
2. **Fermion loop signs:** Closed fermion loops carry (-1). Relative signs between diagrams depend on fermion line routing
3. **MS-bar vs on-shell mass:** Differ by O(alpha) corrections. Using the wrong definition introduces spurious large logarithms
4. **Evanescent operators:** Operators that vanish in d=4 can contribute when multiplied by 1/epsilon poles in dim-reg
5. **IR divergence cancellation:** Soft and collinear divergences cancel in inclusive observables (KLN theorem). Must include real-emission diagrams to cancel virtual IR poles
6. **Ghost contributions:** In covariant gauges for non-Abelian theories, Faddeev-Popov ghost loops must be included. Omitting them violates unitarity
7. **Analytic continuation:** Wick rotation (Minkowski <-> Euclidean) requires correct i\*epsilon prescription. Branch cuts must be tracked
8. **Renormalization scale dependence:** Physical results should have reduced mu-dependence at higher orders. If NLO result has larger mu-dependence than LO, something is wrong
9. **State normalization:** Relativistic normalization <p|p'> = 2E(2pi)^3 delta^3(p-p') vs non-relativistic. Affects cross sections by factors of 2E

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. QFT projects should populate:

- **Metric Signature:** (-,+,+,+) or (+,-,-,-) — this affects ALL propagator signs
- **Fourier Convention:** e^{-ikx} vs e^{+ikx} for positive-energy plane waves
- **Gauge Choice:** Feynman (xi = 1), Lorenz, Coulomb, or axial gauge
- **Regularization Scheme:** Dimensional regularization (d = 4 - 2 epsilon) is standard
- **Renormalization Scheme:** MS-bar, on-shell, or momentum subtraction
- **State Normalization:** Relativistic vs non-relativistic normalization
- **Coupling Convention:** D_mu = d_mu - igA_mu or D_mu = d_mu + igA_mu; and whether perturbative series use g, g^2, g^2/(4pi), or alpha=g^2/(4pi). Mixing coupling definitions introduces factors of 4pi at every vertex.
- **Gamma Matrix Convention:** Dirac, Weyl, or Majorana representation

---

## Computational Environment

**Symbolic computation:**

- `sympy` — Symbolic algebra, gamma matrix traces, Dirac algebra
- `cadabra2` — Tensor algebra with index notation, field theory specialization
- Mathematica with `FeynCalc` — Feynman diagram evaluation, loop integrals, tensor reduction
- `FORM` — High-performance symbolic manipulation for large expressions (thousands of terms)

**Diagram generation and evaluation:**

- `qgraf` — Automatic Feynman diagram generation
- `FeynArts` + `FormCalc` (Mathematica) — Diagram generation + algebraic evaluation
- `Package-X` (Mathematica) — One-loop integrals with full analytic results including IR structure

**Numerical evaluation:**

- `numpy` + `scipy` — Phase space integration, numerical cross sections
- `vegas` (Python) — Adaptive Monte Carlo integration for multi-dimensional phase space
- `LHAPDF` — Parton distribution functions for hadron collider processes
- `LoopTools` — Numerical evaluation of one-loop scalar and tensor integrals

**LaTeX:**

- `axodraw2` or `TikZ-Feynman` — Feynman diagram drawing
- `slashed` package — Dirac slash notation

**Setup:**

```bash
pip install sympy numpy scipy vegas
# For Mathematica users: install FeynCalc via
# Import["https://raw.githubusercontent.com/FeynCalc/feyncalc/master/install.m"]
```

---

## Bibliography Seeds

Every QFT calculation project should cite or consult these references as starting points:

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Peskin & Schroeder, *An Introduction to QFT* | Standard conventions (West Coast metric), Feynman rules, one-loop examples | Convention reference; template calculations |
| Weinberg, *The Quantum Theory of Fields* I-III | Rigorous foundations; symmetry-first derivations | Formal proofs, anomalies, non-perturbative |
| Schwartz, *QFT and the Standard Model* | Modern pedagogical treatment; effective field theory | EFT matching, modern methods |
| Collins, *Foundations of Perturbative QCD* | Factorization proofs, IR structure, TMDs | Hadron collider calculations |
| Smirnov, *Analytic Tools for Feynman Integrals* | Integration-by-parts, Mellin-Barnes, sector decomposition | Multi-loop integral evaluation |
| Ellis, Stirling, Webber, *QCD and Collider Physics* | Cross sections, parton model, jet physics | Phenomenological calculations |

**For specific processes:** Search INSPIRE-HEP for `find t [process name] and tc P` (published, peer-reviewed) to find prior calculations at the target loop order.

---

## Worked Example: Electron Self-Energy at One Loop in QED

A complete 3-phase mini-project illustrating the template:

**Phase 1 — Setup:** Conventions fixed (Peskin & Schroeder: West Coast metric, MS-bar, Feynman gauge). Process: one-loop electron self-energy Sigma(p) in QED. Known result: Sigma = -ie^2 integral [gamma^mu (slashed{k}+m) gamma_mu] / [(p-k)^2 k^2 - m^2] d^dk/(2pi)^d. Prior result catalogued from P&S Chapter 7.

**Phase 2 — Calculation:** One diagram (rainbow). Feynman parametrize, shift momentum, evaluate in d=4-2epsilon. Result: Sigma(p) = (alpha/4pi) * [-slashed{p}(1/epsilon + finite) + 4m(1/epsilon + finite)]. Separate UV pole.

**Phase 3 — Validation:**
- Dimensional check: Sigma has mass dimension 1 (correct — it modifies the inverse propagator which has dimension 1).
- Ward identity: q_mu Gamma^mu(p,p+q) = Sigma(p+q) - Sigma(p) at one loop. Verified.
- Known result: Anomalous magnetic moment g-2 = alpha/(2pi) (Schwinger). Extract from vertex correction (related calculation). Reproduced.
- Gauge invariance: Pole residue of the electron propagator is gauge-independent. Verified by computing in general xi gauge.

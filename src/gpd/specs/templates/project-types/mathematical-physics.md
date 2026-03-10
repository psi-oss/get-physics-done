---
template_version: 1
---

# Mathematical Physics Project Template

Default project structure for mathematical physics: rigorous proofs, exactly solvable models, integrable systems, operator algebras, functional analysis in physics, representation theory applications, topological methods, index theorems, spectral theory, and mathematical structures arising in quantum mechanics and field theory.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Literature and Setup** - Identify the mathematical structure, fix definitions, axioms, and notation
- [ ] **Phase 2: Framework and Definitions** - Establish the mathematical setting (Hilbert space, algebra, manifold), state hypotheses
- [ ] **Phase 3: Analytical Structure** - Analyze spectrum, symmetries, integrability conditions, algebraic properties
- [ ] **Phase 4: Proof/Derivation** - Main theorem or exact solution derivation
- [ ] **Phase 5: Consistency and Limiting Cases** - Verify known special cases, limiting regimes, connections to physical models
- [ ] **Phase 6: Applications** - Apply to physical systems, compute measurable consequences
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting results

## Phase Details

### Phase 1: Literature and Setup

**Goal:** Identify the mathematical structure underlying the physical problem, fix all definitions and axioms, and catalogue known results
**Success Criteria:**

1. [Physical problem translated into a precise mathematical statement (operator equation, algebraic identity, topological invariant, integrable system)]
2. [Axioms and definitions fixed: algebra structure, function spaces, manifold topology, boundary conditions]
3. [Notation established: inner products, norms, operator domains, index conventions documented in NOTATION_GLOSSARY.md]
4. [Prior results catalogued: known theorems, exact solutions, classification results, conjectures]
5. [Proof strategy identified: algebraic, analytic, topological, or constructive approach]

Plans:

- [ ] 01-01: [Survey literature across mathematical and physics journals for existing results and proof techniques]
- [ ] 01-02: [Fix notation and conventions; document in NOTATION_GLOSSARY.md]
- [ ] 01-03: [Identify the precise mathematical formulation and the category of structures involved]

### Phase 2: Framework and Definitions

**Goal:** Establish the mathematical setting rigorously and state all hypotheses
**Success Criteria:**

1. [Mathematical arena specified: Hilbert space, C*-algebra, Lie algebra, fiber bundle, symplectic manifold, or other structure]
2. [Operators defined with precise domains (e.g., D(A) dense in H, A self-adjoint or closed)]
3. [Relevant structures constructed: representations, connections, cohomology groups, spectral sequences]
4. [Key inequalities and embedding theorems established for the function space setting]
5. [Preliminary lemmas proved: density arguments, approximation results, a priori estimates, algebraic identities]

Plans:

- [ ] 02-01: [Define the mathematical arena and all operators/maps with precise domains]
- [ ] 02-02: [Establish function space embeddings, algebraic identities, and a priori estimates]
- [ ] 02-03: [Construct auxiliary structures: representations, connections, cohomology classes]

### Phase 3: Analytical Structure

**Goal:** Analyze the spectrum, symmetries, integrability conditions, and algebraic properties of the mathematical framework
**Success Criteria:**

1. [Spectral properties characterized: discrete vs continuous spectrum, essential spectrum, resolvent estimates, spectral gaps]
2. [Symmetry group identified and its representation theory set up; Casimir operators computed]
3. [Integrability conditions checked: Lax pair, Yang-Baxter equation, inverse scattering data, or commuting Hamiltonians]
4. [Algebraic properties established: commutation relations, central extensions, fusion rules, or operator product structure]
5. [Topological invariants computed: index, Chern number, winding number, or characteristic class]
6. [Obstructions identified: anomalies, deficiency indices, cohomological constraints]

Plans:

- [ ] 03-01: [Characterize spectral properties and resolvent behavior]
- [ ] 03-02: [Analyze symmetry structure and representation-theoretic decomposition]
- [ ] 03-03: [Check integrability conditions or compute topological invariants]
- [ ] 03-04: [Identify obstructions, anomalies, or no-go constraints]

### Phase 4: Proof/Derivation

**Goal:** Prove the main theorem or derive the exact solution
**Success Criteria:**

1. [Main result stated as a precise theorem with all hypotheses explicit]
2. [Proof complete with each logical step justified; no gaps or unverified claims]
3. [For exact solutions: solution constructed explicitly via Bethe ansatz, inverse scattering, algebraic methods, or separation of variables]
4. [Convergence of all series, integrals, and limits established in appropriate topology]
5. [Special function identities verified (cross-check with DLMF or independent computation)]
6. [Uniqueness or classification: characterize the solution space completely]

Plans:

- [ ] 04-01: [State and prove main theorem, or construct exact solution]
- [ ] 04-02: [Verify convergence of all representations in the appropriate function space]
- [ ] 04-03: [Establish uniqueness or classify the solution space]

### Phase 5: Consistency and Limiting Cases

**Goal:** Verify the result against known special cases, limiting regimes, and connections to established physical models
**Success Criteria:**

1. [Known special cases reproduced: free theory, classical limit, non-interacting limit, trivial topology]
2. [Limiting regimes verified: semiclassical limit, weak/strong coupling, thermodynamic limit, continuum limit]
3. [Dimensional consistency: all expressions have correct physical and mathematical dimensions]
4. [Symmetry-dictated identities satisfied: Ward identities, selection rules, index theorems, sum rules]
5. [Connection to physical models: result reduces to known physical predictions in appropriate limits]
6. [Numerical cross-check: independent numerical computation agrees with analytic/exact result]

Plans:

- [ ] 05-01: [Check all known special cases and limiting regimes]
- [ ] 05-02: [Verify symmetry-dictated constraints and index-theoretic identities]
- [ ] 05-03: [Numerical cross-check of analytic/exact results]

### Phase 6: Applications

**Goal:** Apply the rigorous mathematical result to physical systems and compute measurable consequences
**Success Criteria:**

1. [Mathematical results translated to physical observables with units restored]
2. [Specific physical system identified where the result applies (material, model Hamiltonian, field configuration)]
3. [Quantitative predictions derived: energy levels, transition amplitudes, partition functions, transport coefficients]
4. [Predictions compared with experiment or numerical simulation where available]
5. [Domain of validity of the mathematical result mapped to physical parameter ranges]

Plans:

- [ ] 06-01: [Identify physical systems where the result applies; translate to physical observables]
- [ ] 06-02: [Compute quantitative predictions for specific physical models]
- [ ] 06-03: [Compare predictions with experiment or numerical simulation]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with all theorems, proofs, and physical applications]
2. [All assumptions clearly stated; logical dependencies between results mapped]
3. [Comparison with prior work clearly stated]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 1 expanded:** Survey 15+ papers across both mathematical and physics literature. Include failed proof strategies, alternative axiomatizations, and connections to adjacent areas (e.g., number theory, algebraic geometry).
- **Phase 3 branches:** If multiple analytical approaches exist (spectral methods vs algebraic vs topological), pursue two in parallel and compare. Document which gives deeper structural insight.
- **Phase 4 splits:** If the result can be proved by different methods (e.g., analytic vs algebraic vs constructive), attempt two approaches. Compare generalizability.
- **Extra phase:** Add "Phase 3.5: Structure Comparison" — compare algebraic, analytic, and topological characterizations of the same structure. Identify which captures the essential features most cleanly.
- **Literature depth:** 15+ papers, including results from pure mathematics that may not have been applied to the physics context.

### Exploit Mode
- **Phases 1-2 compressed:** If the mathematical framework is well-established (e.g., standard spectral theory on a known operator class), cite standard results and skip detailed framework construction.
- **Phase 3 focused:** Use the known structural results directly. No method comparison.
- **Phase 5 focused:** Check only the most informative limiting cases. Skip exhaustive parameter surveys.
- **Skip Phase 7:** If results feed into a larger project, skip paper writing. Output is SUMMARY.md with theorems and key estimates.
- **Skip researcher:** If the calculation follows a known pattern (same technique applied to a new operator or algebra).

### Adaptive Mode
- Start in explore for Phases 1-3 (choosing the right mathematical framework and proof strategy is critical in mathematical physics).
- Switch to exploit for Phases 4-6 once the framework is established and the proof approach is validated.

---

## Standard Verification Checks for Mathematical Physics

See `references/verification/core/verification-core.md` for universal checks and `references/verification/domains/verification-domain-qft.md` for QFT-specific verification when the mathematical physics problem involves quantum field theory structures.

### Proof Structure Verification

| Check | What to verify |
|-------|---------------|
| Logical completeness | Every step follows from stated hypotheses; no implicit assumptions or circular reasoning |
| Domain consistency | Operators applied only to elements in their domain; unbounded operators not treated as bounded |
| Self-adjointness | Genuine self-adjointness (not merely symmetry) verified before invoking spectral theorem |
| Convergence | Every series, integral, and limit has stated and proved mode of convergence |
| Distributional validity | Operations on distributions (products, compositions) justified; no illegal products |
| Well-posedness | Existence + uniqueness + continuous dependence on data all proved where claimed |

### Algebraic and Topological Verification

| Check | What to verify |
|-------|---------------|
| Representation consistency | Irreducibility, unitarity, and equivalence claims proved; Schur's lemma applied correctly |
| Index theorem application | Hypotheses of index theorem satisfied (ellipticity, compactness, correct symbol class) |
| Topological invariance | Claimed topological invariants verified to be independent of smooth deformations and metric choice |
| Bundle triviality | Global vs local properties distinguished; transition functions consistent on overlaps |
| Algebraic identities | Jacobi identity, associativity, and other structural axioms verified for constructed algebras |
| Anomaly cancellation | If gauge symmetry is claimed, check for quantum anomalies that could obstruct it |

### Special Function and Exact Solution Verification

| Check | What to verify |
|-------|---------------|
| DLMF cross-check | All special function identities verified against DLMF (https://dlmf.nist.gov) |
| Branch conventions | Branch cuts for multi-valued functions explicitly specified and consistent throughout |
| Bethe ansatz completeness | All solutions of Bethe equations accounted for; string hypothesis justified or avoided |
| Integrability | Yang-Baxter equation or zero-curvature condition verified; Lax pair compatibility checked |
| Connection formulae | Analytic continuation and connection formulae verified across Stokes lines and branch cuts |

---

## Typical Approximation Hierarchy

| Level | Approximation | Method | Domain of Validity |
|-------|--------------|--------|-------------------|
| Exact | Closed-form solution | Bethe ansatz, inverse scattering, algebraic construction, separation of variables | Integrable models, special potentials, high-symmetry configurations |
| Rigorous asymptotic | Leading order + error bound | WKB with connection formulae, steepest descent, matched asymptotics | Parameter in stated limit; error bound proved |
| Formal asymptotic | Perturbation series (uncontrolled) | Rayleigh-Schrodinger, Lindstedt-Poincare, formal semiclassical | Small parameter, but no rigorous error bound |
| Numerical | Discretized solution | Spectral methods, FEM, exact diagonalization, Monte Carlo | Bounded domains, finite system size |
| Topological/index-theoretic | Exact integer invariant | Atiyah-Singer, Chern-Gauss-Bonnet, TKNN | Invariant is exact but gives limited quantitative information |

**When to escalate rigor:**

- Formal perturbation series divergent: characterize Borel summability or resurgent structure
- Weak solution obtained: bootstrap to classical regularity if data permits
- Numerical agreement: use as motivation to seek analytic proof, not as substitute
- Non-commuting limits identified: prove each order separately, then characterize the interchange

---

## Common Pitfalls for Mathematical Physics

1. **Strong vs weak convergence:** Confusing strong and weak convergence in Hilbert space leads to incorrect limit arguments. Weak convergence does not preserve norms; a weakly convergent sequence can have a norm strictly greater than the limit. Always specify the topology
2. **Unbounded operator domains:** Applying an unbounded operator to a vector outside its domain is undefined, not merely approximate. Domain specification is part of the definition of the operator, not a technicality
3. **Stone-von Neumann theorem misapplication:** The theorem guarantees uniqueness of irreducible representations of the Weyl relations only for finitely many degrees of freedom. It fails for quantum field theory (infinitely many degrees of freedom), where inequivalent representations proliferate
4. **Incorrect Borel summation:** Borel summability requires the Borel transform to be analytic in a neighborhood of the positive real axis. Singularities on the positive real axis (renormalons, instantons) obstruct Borel summability and require lateral resummation or resurgent methods
5. **Deficiency indices for self-adjoint extensions:** A symmetric operator with unequal deficiency indices (n_+, n_-) has no self-adjoint extension. Equal deficiency indices n_+ = n_- give a U(n)-family of extensions, each with different physics (different boundary conditions). Ignoring this leads to ambiguous spectra
6. **Wrong analytic continuation in integrable models:** Integrable models solved by Bethe ansatz require careful analytic continuation between different regimes (e.g., antiferromagnet to ferromagnet, or finite size to thermodynamic limit). The string hypothesis for Bethe roots can fail, and root distributions can change topology
7. **Global vs local bundle properties:** A connection that is locally flat (zero curvature) may still have nontrivial holonomy if the base manifold has nontrivial fundamental group. Confusing local triviality with global triviality misses topological physics (Aharonov-Bohm effect, topological insulators, Berry phase)
8. **Non-commuting limits:** lim_{a->0} lim_{b->0} f(a,b) != lim_{b->0} lim_{a->0} f(a,b) is common. Examples: epsilon->0 and N->infinity in regularized sums, hbar->0 and t->infinity in semiclassical dynamics. Each order of limits must be justified independently
9. **Exchange of limits without justification:** Interchanging summation, integration, differentiation, or operator limits requires justification (dominated convergence, uniform convergence, Fubini). The interchange failing is often where the physics is

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Mathematical physics projects should populate:

- **Function Spaces:** L^2(Omega), H^k(Omega) = W^{k,2}(Omega), H^k_0(Omega) (zero boundary values), D'(Omega) (distributions). Specify the measure, domain Omega, and boundary regularity
- **Inner Product Convention:** <f, g> = integral f*(x) g(x) dx (conjugate-linear in first argument, physics convention) or integral f(x) g*(x) dx (math convention). Pick one and be consistent
- **Operator Domains:** D(A) explicitly stated for unbounded operators. Specify closure, core, and essential self-adjointness
- **Algebraic Conventions:** Lie bracket [X, Y] = XY - YX; commutator vs anticommutator notation; graded structures specify the grading
- **Topological Conventions:** Orientation of manifolds, choice of atlas, bundle trivialization conventions, characteristic class normalization
- **Fourier Convention:** f-hat(k) = integral f(x) e^{-ikx} dx or (2pi)^{-n/2} integral f(x) e^{-ikx} dx. Affects Plancherel theorem normalization
- **Green's Function Convention:** (-Delta + m^2) G(x,y) = delta(x-y) vs (Delta - m^2) G = -delta. Sign convention must be consistent with operator definition
- **Branch Cut Convention:** Standard cuts for log(z) along (-infinity, 0], for z^alpha along chosen ray. Document departures from standard choice
- **Asymptotic Notation:** f ~ g means f/g -> 1; f = O(g) means |f| <= C|g|; f = o(g) means f/g -> 0. Specify the limit point

---

## Computational Environment

**Symbolic computation:**

- `sympy` — Symbolic algebra, ODE/PDE solving, special functions, series expansions, Lie algebra computations
- `SageMath` — Algebraic geometry, number theory, combinatorics, exact arithmetic, homological algebra
- `GAP` — Computational group theory, representation theory, character tables, Lie algebra structure
- `Singular` — Commutative algebra, algebraic geometry, Groebner bases, singularity theory
- Mathematica — Comprehensive special function library, integral transforms, asymptotic expansion, algebraic manipulation

**Special function reference and numerical verification:**

- DLMF (https://dlmf.nist.gov) — Definitive reference for special function identities, asymptotics, and numerical methods
- `mpmath` (Python) — Arbitrary-precision special function evaluation for numerical verification
- `arb` / `Flint` — Rigorous ball arithmetic for verified numerics with error bounds

**Numerical methods:**

- `numpy` + `scipy` — Numerical linear algebra, ODE integration, quadrature, sparse eigenvalue problems
- `FEniCS` / `Firedrake` — Finite element PDE solvers for verification of analytic results
- `Dedalus` — Spectral methods for PDEs, useful for asymptotic verification

**Proof assistants:**

- `Lean4` + `Mathlib` — Formal verification of mathematical proofs; growing library of analysis and algebra
- `Coq` — Interactive theorem prover for formalized mathematics

**Setup:**

```bash
pip install sympy numpy scipy mpmath
# For SageMath: conda install -c conda-forge sage
# For GAP: see https://www.gap-system.org/Download/
# For Singular: see https://www.singular.uni-kl.de/
# For Lean4: see https://leanprover.github.io/lean4/doc/setup.html
```

---

## Bibliography Seeds

Every mathematical physics project should cite or consult these references as starting points:

| Reference | What it provides | When to use |
|-----------|-----------------|-------------|
| Reed & Simon, *Methods of Modern Mathematical Physics* I-IV | Functional analysis, self-adjoint operators, spectral theory, scattering theory | Foundation for any rigorous operator/spectral problem |
| Zinn-Justin, *Quantum Field Theory and Critical Phenomena* | Path integrals, instantons, large-order perturbation theory, resurgence | Non-perturbative methods, Borel summability, saddle-point analysis |
| Baxter, *Exactly Solved Models in Statistical Mechanics* | Transfer matrices, Bethe ansatz, Yang-Baxter equation, eight-vertex model | Integrable lattice models, exact solutions, combinatorial identities |
| Kato, *Perturbation Theory for Linear Operators* | Analytic perturbation theory, stability of spectra, asymptotic expansions of eigenvalues | Spectral perturbation, operator convergence, resonance theory |
| Nakahara, *Geometry, Topology and Physics* | Fiber bundles, characteristic classes, index theorems, anomalies | Topological methods in physics, gauge theory geometry, Berry phase |
| Brezis, *Functional Analysis, Sobolev Spaces and PDEs* | Sobolev spaces, weak solutions, variational methods, compact embeddings | PDE well-posedness, regularity theory, variational principles |
| Bender & Orszag, *Advanced Mathematical Methods for Scientists and Engineers* | WKB, matched asymptotics, boundary layers, divergent series, Stokes phenomenon | Asymptotic analysis, singular perturbation, connection formulae |
| Dunford & Schwartz, *Linear Operators* I-III | Comprehensive functional analysis and spectral theory | Deep operator theory, spectral measures, semigroups |

**For specific topics:** Search MathSciNet (zbMATH) for rigorous results and arXiv math-ph for recent developments. For integrable systems, check the Journal of Statistical Physics and Communications in Mathematical Physics.

---

## Worked Example: Index Theorem for the 1D Dirac Operator with a Kink

A complete 3-phase mini-project illustrating the template:

**Phase 1 -- Setup:** Problem: compute the index of the 1D Dirac operator D = i*sigma_1 * d/dx + sigma_3 * m(x) on L^2(R, C^2), where m(x) is a kink profile interpolating between m(-infinity) = -m_0 and m(+infinity) = +m_0. This is the Jackiw-Rebbi model. Known result: the operator has exactly one normalizable zero mode, and ind(D) = 1. Goal: prove this rigorously via the Callias index theorem and verify by explicit construction.

**Phase 2 -- Framework and Proof:** D is a Fredholm operator (proved by showing m(x) -> +/- m_0 gives D essential spectrum bounded away from zero). The Callias index theorem applies: ind(D) = (1/2)[sign(m(+infinity)) - sign(m(-infinity))] = (1/2)[1 - (-1)] = 1. Separately, construct the zero mode explicitly: psi_0(x) = N * exp(-integral_0^x m(x') dx') * (1, 0)^T. Normalizability verified since m(x) -> m_0 > 0 as x -> +infinity and m(x) -> -m_0 < 0 as x -> -infinity, so the exponential decays in both directions.

**Phase 3 -- Consistency and Applications:**
- Topological protection: the zero mode count depends only on the asymptotic values of m(x), not the detailed profile. Verified by deforming m(x) continuously without changing the asymptotics; the zero mode persists.
- Limiting cases: as m_0 -> infinity (sharp kink), the zero mode localizes to x = 0 and becomes delta-function-like. As m_0 -> 0, the zero mode delocalizes and the gap closes, consistent with the Fredholm condition failing.
- Numerical cross-check: discretize D on a lattice with 1000 sites, diagonalize with scipy.linalg.eigh. One eigenvalue at E = 0 to machine precision (10^{-14}), all others at |E| > m_0. Eigenvector matches the analytic psi_0(x).
- Physical application: the Jackiw-Rebbi zero mode is the prototype for fermion fractionalization in polyacetylene (Su-Schrieffer-Heeger model) and domain wall fermions in lattice gauge theory.

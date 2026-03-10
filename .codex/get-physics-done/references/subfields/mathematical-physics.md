---
load_when:
  - "mathematical physics"
  - "rigorous proof"
  - "functional analysis"
  - "differential geometry"
  - "operator algebra"
  - "spectral theory"
  - "axiomatic QFT"
tier: 2
context_cost: medium
---

# Mathematical Physics

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/algebraic-qft.md`, `references/protocols/group-theory.md`, `references/protocols/topological-methods.md`, `references/protocols/symmetry-analysis.md`, `references/protocols/generalized-symmetries.md`, `references/protocols/string-field-theory.md`, `references/protocols/conformal-bootstrap.md`, `references/protocols/holography-ads-cft.md`, `references/protocols/bethe-ansatz.md` (integrable systems, Yang-Baxter equation), `references/protocols/random-matrix-theory.md` (spectral statistics, universality classes), `references/protocols/resummation.md` (Borel summation, asymptotic analysis), `references/protocols/large-n-expansion.md` (saddle-point methods, matrix models).

**Rigorous Proofs in Physics:**

- Constructive quantum field theory: prove existence of interacting QFTs in lower dimensions (d=2, d=3)
- Operator algebra approach: C\*-algebras, von Neumann algebras for quantum mechanics and QFT
- Axiomatic QFT: Wightman axioms (fields), Haag-Kastler axioms (local algebras); reconstruction theorems
- Osterwalder-Schrader reconstruction: Euclidean QFT -> Minkowski QFT via analytic continuation (reflection positivity)

**Functional Analysis:**

- Hilbert spaces: self-adjoint operators have spectral theorem; unbounded operators require careful domain specification
- Spectral theory: point spectrum (eigenvalues), continuous spectrum, essential spectrum
- Sobolev spaces: W^{k,p} for weak solutions of PDEs; trace theorems for boundary values
- Distribution theory: delta functions, principal values; tempered distributions for Fourier analysis
- Compact operators: spectral theory; Fredholm alternative; trace class and Hilbert-Schmidt operators

**Differential Geometry:**

- Manifolds, tangent/cotangent bundles, tensor fields
- Connections and curvature: Riemann tensor, Ricci tensor, Weyl tensor
- Fiber bundles: principal bundles for gauge theories; associated bundles for matter fields
- Characteristic classes: Chern classes, Pontryagin classes; relate topology to geometry
- Symplectic geometry: phase space, Hamiltonian mechanics, Poisson brackets, canonical transformations

**Algebraic Topology in Physics:**

- Homotopy groups: pi_1 for vortices and dislocations; pi_2 for monopoles; pi_3 for instantons
- Homology and cohomology: de Rham cohomology relates differential forms to topology
- Index theorems: Atiyah-Singer relates analytic index (zero modes) to topological index
- K-theory: classification of topological phases of matter (ten-fold way); vector bundle classification
- TQFT (Topological Quantum Field Theory): Chern-Simons theory, knot invariants (Jones polynomial), anyons

**Representation Theory:**

- Lie groups and Lie algebras: SU(N), SO(N), Sp(N) for gauge theories
- Representations classify particles: spin from SU(2), color from SU(3), flavor multiplets
- Young tableaux: systematic construction of SU(N) representations; tensor products, branching rules
- Clifford algebras: spinor representations; gamma matrices; Dirac equation
- Infinite-dimensional: Virasoro algebra (conformal field theory), Kac-Moody algebras (WZNW models), W-algebras

**Integrable Systems:**

- Classical: Liouville integrability (N conserved quantities in involution for N degrees of freedom)
- Lax pair: L-dot = [M, L]; eigenvalues of L are conserved; isospectral flow
- Bethe ansatz: exact solution of integrable quantum chains (XXX, XXZ, Hubbard at certain parameters)
- Yang-Baxter equation: R_12 * R_13 * R_23 = R_23 * R_13 * R_12; consistency condition for integrability
- Inverse scattering transform: "Fourier transform" for nonlinear integrable PDEs (KdV, NLS, sine-Gordon)

**Conformal Field Theory:**

- In d=2: infinite-dimensional Virasoro symmetry; central charge c classifies theories
- Minimal models: finite number of primary fields; exactly solvable (Ising: c=1/2, tri-critical Ising: c=7/10)
- Operator product expansion (OPE): phi_i(z) * phi_j(0) ~ sum_k C_ijk * z^{h_k - h_i - h_j} \* phi_k(0)
- Modular invariance: torus partition function must be invariant under SL(2,Z); constrains the spectrum
- In d>2: conformal bootstrap; crossing symmetry + unitarity constrain operator dimensions and OPE coefficients

**Homotopy Algebra and String Field Theory:**

- BV, `A_infinity`, and `L_infinity` structures organize gauge invariance and interactions
- Worldsheet BRST cohomology controls the admissible state space
- BPZ cyclicity and symplectic structures replace ordinary local field-theory intuition
- Background shifts are encoded algebraically through shifted products and differential operators

**Algebraic QFT and Operator Algebras:**

- Haag-Kastler nets organize local observables by spacetime region rather than by pointlike fields
- Tomita-Takesaki theory, modular automorphisms, and modular conjugations encode intrinsic operator-algebraic dynamics
- Von Neumann factor types matter physically: local relativistic algebras are typically type `III`, so naive tensor-factor and density-matrix intuition fails
- DHR sectors, conformal nets, and subfactor inclusions provide rigorous charge and extension data in low-dimensional or highly structured theories

## Key Tools and Software

| Tool                      | Purpose                                  | Notes                                                              |
| ------------------------- | ---------------------------------------- | ------------------------------------------------------------------ |
| **SageMath**              | General mathematical computation         | Group theory, topology, differential geometry, number theory       |
| **GAP**                   | Computational group theory               | Finite groups, representations; character tables                   |
| **Macaulay2**             | Commutative algebra / algebraic geometry | Grobner bases, sheaf cohomology                                    |
| **SnapPy**                | 3-manifold topology                      | Hyperbolic 3-manifolds; knot invariants                            |
| **MAGMA**                 | Computational algebra                    | Group theory, number theory, algebraic geometry; commercial        |
| **Lean / Coq / Isabelle** | Proof assistants                         | Formalize mathematical proofs; growing use in mathematical physics |
| **xAct**                  | Tensor computer algebra (Mathematica)    | Differential geometry, perturbation theory                         |
| **Cadabra**               | Tensor algebra for field theory          | GR, SUGRA, string theory; Python interface                         |
| **SageManifolds**         | Differential geometry (SageMath)         | Manifolds, metrics, connections, curvature                         |
| **LiE**                   | Lie group computations                   | Representations, branching rules, tensor products                  |
| **ATLAS of Lie Groups**   | Structure theory of Lie groups           | Representations, Kazhdan-Lusztig polynomials                       |

## Validation Strategies

**Proof Structure:**

- Verify all hypotheses explicitly stated; check boundary cases and edge cases
- Dimensional counting: does the theorem produce objects of the correct type (e.g., a p-form, not a (p+1)-form)?
- Check all quantifiers: "for all" vs "there exists"; common source of errors
- Verify logical chain: each step must follow from previous steps and stated hypotheses
- Check converses: is the converse true? If not, is the theorem stated in the strongest form?

**Index Theorem Verification:**

- Atiyah-Singer: ind(D) = integral ch(V) \* Td(M) (analytic index = topological index)
- Check: count zero modes of Dirac operator and compare with topological integral
- Gauss-Bonnet (simplest case): integral R dA = 2*pi*chi(M) where chi is Euler characteristic

**Topological Invariant Computation:**

- Chern numbers: must be integers; computed via integration of curvature forms
- Winding numbers: must be integers; computed via contour integrals
- Check: any computed topological invariant must be an integer (or rational number for fractional cases like fractional quantum Hall)

**Representation Theory Checks:**

- Dimension formulas: Weyl dimension formula gives exact dimension of irreducible representation
- Character orthogonality: sum_g chi_R(g) * chi_S(g)^* = |G| \* delta_RS
- Branching rules: dimension must be preserved when decomposing under subgroup
- Tensor product: sum of dimensions in decomposition = product of original dimensions

**Exact Integrability Verification:**

- Lax pair: verify that [L, M] = L-dot reproduces equations of motion
- Yang-Baxter: verify R-matrix satisfies YBE explicitly (algebraic check)
- Bethe ansatz: verify that Bethe equations are satisfied for known solutions
- Conserved quantities: verify Poisson brackets {I_m, I_n} = 0 for classical systems; [Q_m, Q_n] = 0 for quantum

## Common Pitfalls

- **Assuming analyticity without proof:** Interchange of limits, differentiation under integral sign, term-by-term integration of series all require justification. Dominated convergence theorem, uniform convergence, etc.
- **Conflating formal and convergent series:** Perturbation series in QFT are typically asymptotic, not convergent. Borel summability may or may not apply
- **Ignoring domains of unbounded operators:** The Hamiltonian H is unbounded; its domain is not all of Hilbert space. Self-adjoint ≠ symmetric for unbounded operators (requires matching domains of H and H^dag)
- **Wrong application of Stokes' theorem:** Requires orientability, correct manifold-with-boundary structure, and sufficient regularity of the forms. Boundary contributions are frequently forgotten
- **Topological obstructions:** Global existence of objects (e.g., gauge fields) may require patching; transition functions encode topology. Cannot always choose "nice" coordinates globally (hairy ball theorem, etc.)
- **Confusing Lie group and Lie algebra:** Lie algebra determines local behavior; global properties (topology, center, fundamental group) require the group. su(2) ≅ so(3) as algebras, but SU(2) ≠ SO(3) as groups (SU(2) is simply connected)
- **Non-commutativity of operations:** Limits, integrals, derivatives, and infinite sums do not always commute. Each interchange is a theorem with hypotheses that must be checked
- **Incorrectly using classification theorems:** Classification of, e.g., finite simple groups, topological manifolds, or semisimple Lie algebras applies under specific conditions. Ensure your object satisfies all hypotheses

---

## Research Frontiers (2024-2026)

| Frontier | Key question | GPD suitability |
|----------|-------------|-----------------|
| **Amplitudes and geometry** | Amplituhedron, associahedron, tropical geometry for scattering | Excellent — algebraic/combinatorial |
| **Resurgence and trans-series** | Non-perturbative completion of asymptotic series, Borel-Écalle theory | Excellent — formal series analysis |
| **Topological phases classification** | Cobordism conjecture, beyond group cohomology for SPT phases | Good — algebraic topology + physics |
| **Generalized symmetries and defects** | How do higher-form, higher-group, and non-invertible structures reorganize anomaly, duality, and defect data? | Gaiotto, Cordova, Schafer-Nameki, Bhardwaj | Good — category/topology heavy; concrete physical realization should be stated explicitly |
| **Conformal bootstrap (rigorous)** | Rigorous bounds on CFT data, optimal transport methods | Excellent — optimization + analysis |
| **AQFT and operator algebras** | Which modular, local-net, and factor-type structures are universal in relativistic QFT and curved spacetime? | Excellent — theorem-heavy and structurally constrained |
| **String field theory and homotopy algebra** | How should BV, `A_infinity`, and `L_infinity` structures encode consistent open/closed superstring interactions? | Excellent — algebraic plus computational |
| **Integrable systems** | Exact solutions for Yang-Baxter, Bethe ansatz for new models | Excellent — algebraic + computational |
| **Quantum groups and categories** | Tensor categories for anyons, modular functors, TQFT | Good — algebraic structures |

## Methodology Decision Tree

```
What type of mathematical physics?
├── Exact solutions
│   ├── Integrable system? → Bethe ansatz, inverse scattering, Yang-Baxter
│   ├── Symmetry-based? → Representation theory, Casimir operators
│   └── Topological? → Index theorems, characteristic classes, cobordism
├── Rigorous results
│   ├── Existence/uniqueness? → Functional analysis, PDE theory
│   ├── Bounds? → Variational methods, convexity, monotonicity
│   └── Classification? → Group theory, category theory, K-theory
├── Formal methods
│   ├── Perturbative? → Asymptotic analysis, Borel summation, resurgence
│   ├── Non-perturbative? → Instanton calculus, saddle-point methods
│   └── Algebraic? → Operator algebras, AQFT, vertex algebras, BRST cohomology, string field theory
└── Computational
    ├── Symbolic? → Computer algebra (Mathematica, SageMath, GAP)
    ├── Numerical verification? → High-precision arithmetic (mpmath, FLINT)
    └── Enumerative? → Generating functions, asymptotic counting
```

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One rigorous result or exact solution for a specific model | "Borel summability of the phi^4 perturbation series in d=0" |
| **Postdoc** | New connection between mathematical structures and physics | "Resurgent structure of the Mathieu equation and applications to WKB" |
| **Faculty** | New framework unifying disparate areas | "Cobordism classification of symmetry-protected topological phases"

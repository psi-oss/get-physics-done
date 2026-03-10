<overview>
Hypothesis-driven research is about intellectual discipline, not bureaucratic process. The predict-derive-verify cycle forces you to think about expected physical behavior before computing, producing clearer understanding and catching errors that purely mechanical calculation would miss.

**Principle:** If you can state "in this limit, the answer must behave as X" before deriving, hypothesis-driven research improves the result.

**Key insight:** Hypothesis-driven work is fundamentally heavier than standard tasks -- it requires 2-3 execution cycles (PREDICT -> DERIVE -> VERIFY/REFINE), each with literature checks, derivations, numerical evaluations, and potential debugging. Hypothesis-driven research gets dedicated plans to ensure full context is available throughout the cycle.
</overview>

<when_to_use_hypothesis_driven>

## When Hypothesis-Driven Research Improves Quality

**Hypothesis-driven candidates (create a hypothesis-driven plan):**

- Calculations with known limiting cases to check against
- Derivations where symmetry constrains the answer's form
- Numerical computations with analytical benchmarks
- Results that must satisfy conservation laws or sum rules
- Problems where dimensional analysis constrains the scaling
- Phase diagrams where topology is known from general arguments
- Transport coefficients with Onsager relations or other exact constraints

**Skip hypothesis-driven approach (use standard plan with `type="auto"` tasks):**

- Purely exploratory parameter sweeps
- Data processing and formatting
- Setting up computational infrastructure
- Literature compilation and review
- Straightforward evaluations of known formulas
- One-off utility calculations

**Heuristic:** Can you state `in the limit of X, this must equal Y` before deriving?
-> Yes: Create a hypothesis-driven plan
-> No: Use standard plan, add verification after if needed
</when_to_use_hypothesis_driven>

<hypothesis_driven_plan_structure>

## Hypothesis-Driven Plan Structure

Each hypothesis-driven plan investigates **one physical question** through the full PREDICT-DERIVE-VERIFY cycle.

```markdown
---
phase: XX-name
plan: NN
type: hypothesis-driven
---

<objective>
[What physical question and why]
Purpose: [What understanding the prediction-first approach ensures]
Output: [Validated result with verified limiting behavior]
</objective>

<context>
@.gpd/PROJECT.md
@.gpd/ROADMAP.md
@relevant/derivations/files.py
</context>

<hypothesis>
  <name>[Physical quantity or relation being computed]</name>
  <files>[derivation file, verification script]</files>
  <predictions>
    [Expected behavior stated BEFORE calculation]
    Limits: parameter -> value => result -> expected form
    Symmetries: what constraints the answer must satisfy
    Scaling: how the result must depend on key parameters
  </predictions>
  <derivation>[How to derive/compute once predictions are stated]</derivation>
</hypothesis>

<verification>
[Numerical checks, limiting case evaluation, comparison with known results]
</verification>

<success_criteria>

- Predictions stated and committed before derivation
- Derivation/calculation completed
- All predicted limits verified (or discrepancy understood and resolved)
- All 2-3 commits present
  </success_criteria>

<output>
After completion, create SUMMARY.md with:
- PREDICT: What behavior was expected, why
- DERIVE: What calculation was performed, key steps
- VERIFY: Which predictions confirmed, which required revision
- REFINE: What was learned from any mismatches
- Commits: List of commits produced
</output>
```

**One physical question per hypothesis-driven plan.** If questions are trivial enough to batch, they're trivial enough to skip the hypothesis-driven approach -- use a standard plan and add checks after.
</hypothesis_driven_plan_structure>

<execution_flow>

## Predict-Derive-Verify Cycle

This is the physics analogue of Test-Driven Development. Just as TDD demands you write a failing test before implementation, hypothesis-driven research demands you state expected behavior before computing. The discipline is the same: prediction before production.

**PREDICT - State expected behavior:**

1. Identify all accessible limiting cases (weak coupling, high temperature, large N, etc.)
2. Determine symmetry constraints on the result's form
3. Check dimensional analysis for scaling behavior
4. Look up known results that the answer must reproduce in some limit
5. Write these predictions down explicitly and concretely
6. Commit: `verify({phase}-{plan}): define expected limits for [quantity]`

**DERIVE - Perform the calculation:**

1. Carry out the derivation or numerical computation
2. No skipping steps, no "it's obvious" -- write it out
3. Check the result against each stated prediction
4. If predictions are all satisfied: the result is validated
5. Commit: `calc({phase}-{plan}): derive [quantity]`

**VERIFY/REFINE (if mismatch):**

1. If a prediction fails, this is the most valuable moment in the research
2. Either the calculation has an error -- find it and fix it
3. Or the physical intuition was wrong -- revise understanding and document why
4. Both outcomes produce insight that blind calculation would have missed
5. Run all checks again after any correction
6. Only commit if changes made: `simplify({phase}-{plan}): correct [quantity] and update understanding`

**Result:** Each hypothesis-driven plan produces 2-3 atomic commits.
</execution_flow>

<prediction_quality>

## Good Predictions vs Bad Predictions

**Test behavior in known limits, not just existence of output:**

- Good: "In the T -> infinity limit, the free energy must reduce to -NkT ln(V/lambda^3)"
- Bad: "The free energy should be some function of temperature"
- Predictions should catch real errors

**One physical property per prediction:**

- Good: Separate predictions for q->0 limit, zone boundary behavior, equal mass limit
- Bad: Single prediction "the dispersion should look right"

**Quantitative when possible:**

- Good: "Conductivity must diverge as sigma ~ 1/(T - T_c)^s with s = 1.3 in 3D"
- Bad: "Conductivity should increase near T_c"
- Good: "At q = 0, the optical branch frequency must be omega = sqrt(2k/mu)"
- Bad: "There should be an optical branch"

**Based on physical reasoning, not curve fitting:**

- Good: Predict from symmetry, conservation laws, known exact results, dimensional analysis
- Bad: Predict by extrapolating from a plot of similar-looking data
  </prediction_quality>

<prediction_sources>

## Where Predictions Come From

When forming predictions before calculation, draw from these sources (roughly ordered by reliability):

**1. Exact constraints (must hold, no exceptions):**

- Conservation laws (energy, momentum, charge, probability)
- Sum rules (f-sum rule, optical sum rule, Friedel sum rule)
- Ward identities and exact relations between Green's functions
- Thermodynamic identities (Maxwell relations, Gibbs-Duhem)

**2. Symmetry constraints (must hold if symmetry is present):**

- Time-reversal: Onsager reciprocal relations
- Spatial symmetry: selection rules, degeneracies
- Gauge invariance: transversality of response functions
- Particle-hole symmetry: constraints on self-energy at half-filling

**3. Known limiting cases (must reproduce in appropriate limit):**

- Non-interacting limit: free particle/field results
- Classical limit: Boltzmann distribution, equipartition
- High-temperature expansion: leading terms known
- Weak-coupling perturbation theory: lowest-order results

**4. Dimensional analysis and scaling:**

- Result must have correct dimensions
- Near critical points: scaling hypothesis constrains exponent relations
- In renormalizable theories: RG constrains functional form

**5. Physical intuition (should hold, but may surprise):**

- Monotonicity expectations (resistivity increases with temperature in metals)
- Stability requirements (positive compressibility, positive specific heat)
- Causality (retarded response functions are analytic in upper half-plane)

If a prediction from category 1-2 fails, the calculation is almost certainly wrong.
If a prediction from category 3-4 fails, investigate carefully -- could be the calculation or the limiting procedure.
If a prediction from category 5 fails, you may have discovered something interesting.
</prediction_sources>

<framework_setup>

## Computation Framework Setup (If None Exists)

When executing a hypothesis-driven plan but no computation environment is configured, set it up as part of the PREDICT phase:

**1. Detect project type:**

```bash
# Python scientific computing
if [ -f pyproject.toml ] || [ -f requirements.txt ]; then echo "python"; fi

# Julia
if [ -f Project.toml ]; then echo "julia"; fi

# Mathematica notebooks
if ls *.nb 1>/dev/null 2>&1; then echo "mathematica"; fi

# LaTeX project
if [ -f main.tex ] || ls *.tex 1>/dev/null 2>&1; then echo "latex"; fi
```

**2. Install minimal framework:**
| Project | Framework | Install |
|---------|-----------|---------|
| Python | numpy + scipy + matplotlib | `pip install numpy scipy matplotlib` |
| Python (symbolic) | sympy | `pip install sympy` |
| Python (testing) | pytest | `pip install pytest` |
| Julia | standard library | Built-in (LinearAlgebra, DifferentialEquations) |
| LaTeX | texlive | Platform-dependent |

**3. Create verification script template if needed:**

- Python: `tests/test_limits.py` with pytest structure for checking limiting cases
- Jupyter: notebook with dedicated "Verification" section
- LaTeX: separate `appendix_checks.tex` for limiting case analysis

**4. Verify setup:**

```bash
# Run empty verification suite - should pass with 0 checks
pytest tests/              # Python
julia test/runtests.jl     # Julia
latexmk -pdf main.tex      # LaTeX compiles
```

**5. Create first prediction file:**
Follow project conventions for verification location:

- `tests/test_[quantity]_limits.py` for numerical checks
- `verification/` directory for analytical checks
- Inline assertions in computation scripts

Framework setup is a one-time cost included in the first hypothesis-driven plan's PREDICT phase.
</framework_setup>

<error_handling>

## Error Handling

**Prediction already satisfied before derivation (analogous to test passing in RED phase):**

- Result may already be known -- check if you're re-deriving something established
- Prediction may be too weak (not actually testing anything)
- Sharpen the prediction or acknowledge the result is already established

**Derivation contradicts a prediction:**

- This is the MOST VALUABLE outcome -- do not brush past it
- First suspect: algebraic or numerical error in the derivation
- Second suspect: error in taking the limit (non-commuting limits, singular perturbation)
- Third suspect: physical intuition was wrong -- document the surprise
- Do NOT proceed until the discrepancy is resolved or understood

**Multiple predictions contradict each other:**

- Stop and investigate immediately
- May indicate inconsistent approximations
- May indicate a subtle physical effect (anomaly, spontaneous symmetry breaking)
- Resolution often produces the most interesting insight

**Numerical verification fails within tolerance:**

- Check convergence (is the numerical result converged?)
- Check the analytical prediction (did you drop subleading terms that matter?)
- Tighten or loosen tolerance with physical justification
  </error_handling>

<commit_pattern>

## Commit Pattern for Hypothesis-Driven Plans

Hypothesis-driven plans produce 2-3 atomic commits (one per phase):

```
verify(08-02): define expected limits for optical conductivity

- Drude weight must equal pi*n*e^2/m at zero frequency
- f-sum rule: integral of Re[sigma]*omega = pi*n*e^2/(2m)
- DC limit must match Boltzmann transport result
- High-frequency tail must decay as 1/omega^2

calc(08-02): derive optical conductivity from Kubo formula

- Evaluated current-current correlator in RPA
- Drude peak at omega=0 with correct spectral weight
- Interband transitions produce absorption above gap
- All predicted limits satisfied

simplify(08-02): simplify conductivity expression using spectral representation (optional)

- Rewrote in terms of spectral function A(k, omega)
- Cleaner separation of intraband and interband contributions
- All limits still satisfied
```

**Comparison with standard plans:**

- Standard plans: 1 commit per task, 2-4 commits per plan
- Hypothesis-driven plans: 2-3 commits for single physical question

Both follow same format: `{type}({phase}-{plan}): {description}`

**Benefits:**

- Each commit independently revertable
- Predictions committed BEFORE derivation: proof of intellectual discipline
- Clear history showing which limits were checked
- Git bisect works: if a later calculation breaks a limit, find where
  </commit_pattern>

<context_budget>

## Context Budget

Hypothesis-driven plans target **~40% context usage** (lower than standard plans' ~50%).

Why lower:

- PREDICT phase: state expected behavior, look up known results, potentially check literature
- DERIVE phase: perform calculation, evaluate at each predicted limit, potentially iterate on errors
- VERIFY/REFINE phase: compare against predictions, investigate mismatches, revise understanding

Each phase involves reading references, running computations, analyzing output. The back-and-forth is inherently heavier than linear task execution.

Single physical question focus ensures full rigor throughout the cycle.
</context_budget>

<examples>

### Example: Hydrogen Atom Fine Structure

```markdown
---
phase: 03-relativistic
plan: 01
type: hypothesis-driven
---

<objective>
Compute the fine structure correction to hydrogen energy levels.

Purpose: Hypothesis-driven approach ensures we catch sign errors and factor-of-2 mistakes
by checking against known exact results before and after.
Output: Fine structure formula validated against Dirac equation exact result.
</objective>

<hypothesis>
  <name>Fine structure energy correction</name>
  <files>derivations/fine_structure.py, tests/test_fine_structure_limits.py</files>
  <predictions>
    1. Non-relativistic limit (alpha -> 0): correction vanishes, recover Bohr levels
    2. Degeneracy: levels with same j but different l must be degenerate (to this order)
    3. Sign: correction must be NEGATIVE (relativistic effects lower the energy)
    4. Scaling: correction goes as alpha^4 * m * c^2 (order alpha^2 relative to Bohr)
    5. Ground state (n=1, j=1/2): must match Dirac result expanded to O(alpha^4)
    6. l-dependence: for fixed n, lower j means more negative correction (more time near nucleus)
  </predictions>
  <derivation>
    Compute three contributions: relativistic kinetic energy, spin-orbit coupling, Darwin term.
    Sum and simplify using hydrogen wavefunctions.
  </derivation>
</hypothesis>
```

### Example: BCS Gap Equation

```markdown
---
phase: 02-superconductivity
plan: 02
type: hypothesis-driven
---

<objective>
Solve the BCS gap equation self-consistently.

Purpose: Stating limiting behavior first catches common errors in the self-consistency loop
(wrong density of states, incorrect cutoff treatment).
Output: Gap function Delta(T) validated against known BCS results.
</objective>

<hypothesis>
  <name>Temperature-dependent superconducting gap</name>
  <files>derivations/bcs_gap.py, tests/test_bcs_limits.py</files>
  <predictions>
    1. T = 0: Delta(0) = (2*hbar*omega_D/e) * exp(-1/(N(0)*V)) (BCS result, note the factor of 2/e)
    2. T -> T_c: Delta(T) ~ sqrt(1 - T/T_c) (mean-field critical exponent beta = 1/2)
    3. T_c relation: 2*Delta(0)/(k_B*T_c) = 3.528 (universal BCS ratio)
    4. For T > T_c: Delta = 0 (normal state)
    5. Delta(T) is monotonically decreasing for 0 < T < T_c
    6. Weak coupling: result independent of cutoff details (only depends on N(0)*V)
  </predictions>
  <derivation>
    Solve gap equation self-consistently at each temperature using Newton's method.
    Use logarithmic mesh near T_c for resolution of square-root behavior.
  </derivation>
</hypothesis>
```

</examples>

<why_predict_first>

## Why Predict Before You Compute

The predict-derive-verify cycle is the physics analogue of test-driven development. The parallel is exact:

| TDD (Software)         | Hypothesis-Driven (Physics)                                                   |
| ---------------------- | ----------------------------------------------------------------------------- |
| Write failing test     | State expected limiting behavior                                              |
| Implement to pass      | Perform derivation/calculation                                                |
| Test passes            | Predicted limits verified                                                     |
| Test fails -> fix code | Limit violated -> fix derivation                                              |
| Simplify               | Simplify/generalize result                                                    |
| Red                    | Prediction stated, not yet verified (the "test" exists but hasn't been "run") |
| Green                  | Derivation matches all predictions                                            |
| Simplify               | Simplify expression, improve numerical method, generalize                     |

**The deeper parallel — Red-Green-Simplify → Predict-Compute-Validate:**

```
RED (TDD)                           RED (Physics)
─────────                           ─────────────
Write test that fails               State: "In limit g→0, Σ(ω) must vanish"
Test is executable and specific      Prediction is quantitative and falsifiable
Test defines the contract            Prediction defines the physics

GREEN (TDD)                         GREEN (Physics)
──────────                          ──────────────
Write minimal code to pass          Perform derivation / run computation
Code is ugly but correct             Result may be unsimplified but correct
All tests pass                       All predicted limits verified

SIMPLIFY (TDD)                      SIMPLIFY (Physics)
──────────────                      ──────────────────
Clean up code, extract patterns     Simplify expressions, identify structure
Tests still pass after cleanup       Limits still hold after simplification
Improve maintainability              Improve physical transparency
```

**Why this ordering matters:**

1. **Catches errors mechanically.** A sign error in a self-energy calculation might produce a "reasonable-looking" answer. But if you predicted that Im[Sigma] < 0 for retarded Green's functions (required by causality), you catch the sign flip immediately.

2. **Prevents circular reasoning.** Without predictions, it's tempting to rationalize any answer: "oh, the energy goes UP with coupling? That must be because..." Stating the expectation first forces honesty.

3. **Builds physical understanding.** The act of forming predictions requires engaging with the physics deeply -- what ARE the known limits? What DOES symmetry constrain? This understanding persists even if the calculation is later superseded.

4. **Makes debugging tractable.** When a 3-page derivation gives the wrong answer, knowing WHICH limiting case fails narrows the search to specific terms or steps.

5. **Documents the reasoning.** Future readers (including future AI sessions) can see not just what was computed, but what physical reasoning validated it.

6. **Creates a "test suite" for the physics.** Just as a software test suite catches regressions when code changes, the set of verified predictions catches errors when approximation schemes change, parameters are updated, or the calculation is extended.

**The discipline is simple:** Never compute without first asking "what must the answer look like?"

**See also:** `references/verification/core/verification-core.md` — prediction patterns (limiting cases, symmetry constraints, conservation laws) map directly to the verification checks used to validate results.
</why_predict_first>

<subfield_prediction_patterns>

## Prediction Patterns by Subfield

Concrete examples of what to predict before computing, organized by physics domain.

### Quantum Field Theory

```
Before computing a Feynman diagram:
1. UV behavior: How does the integral diverge? (power counting: D = 4 - E_ext - ...)
2. IR behavior: Is there an IR divergence? (massless particles, soft/collinear)
3. Gauge invariance: Does the result satisfy the Ward identity?
4. Crossing symmetry: Related to other diagrams by s ↔ t ↔ u?
5. Optical theorem: Imaginary part = sum over cuts (Cutkosky rules)
6. Decoupling: Heavy particles (M → ∞) must decouple from low-energy physics
7. Renormalization: Counterterms have the form of existing Lagrangian terms

Example prediction set for electron self-energy at one loop:
- Divergence: logarithmic (not quadratic — chiral symmetry protects mass)
- Σ(p̸ = m) → mass renormalization δm ~ α m log(Λ/m)
- Gauge dependence: Σ depends on gauge parameter ξ, but pole position is gauge-independent
- Low-energy: Σ → 0 as α → 0 (reduces to free propagator)
```

### Condensed Matter Physics

```
Before computing a phase diagram:
1. Known phases: What phases must exist? (e.g., paramagnetic at high T, ordered at low T)
2. Symmetry breaking: Order parameter symmetry determines universality class
3. Mean-field critical exponents: β=1/2, γ=1, ν=1/2 (deviations = fluctuation effects)
4. Mermin-Wagner: No spontaneous breaking of continuous symmetry in d ≤ 2 at T > 0
5. Goldstone modes: Number = dim(G) - dim(H) for G → H symmetry breaking
6. Response functions: Kramers-Kronig, sum rules, spectral positivity

Example prediction set for Hubbard model:
- Half-filling: Mott insulator for U/t >> 1 (charge gap ~ U)
- Weak coupling: metallic (Fermi liquid) for U/t << 1
- Particle-hole symmetry at half-filling: μ = U/2
- Luttinger theorem: Fermi surface volume = electron density (in metallic phase)
- Antiferromagnetic order: Néel state at half-filling for large U/t (d > 2)
```

### General Relativity / Cosmology

```
Before computing a spacetime metric or cosmological observable:
1. Newtonian limit: Weak-field, slow-motion must give Newton's gravity
2. Birkhoff's theorem: Spherically symmetric vacuum → Schwarzschild
3. Energy conditions: Weak/strong/dominant/null (which does your source satisfy?)
4. Singularity theorems: If energy conditions hold, geodesic incompleteness expected
5. Asymptotic flatness: Metric → Minkowski at spatial infinity (isolated systems)
6. ADM mass/energy: Total energy from asymptotic behavior must be positive

Example prediction set for gravitational wave emission:
- Quadrupole formula: Leading order is h ~ (G/c^4)(1/r) d²I/dt²
- Power: P ~ (G/c^5) ⟨...I...⟩ ~ (v/c)^5 × (Gm/rc^2) × luminosity scale
- Frequency: f_GW = 2 f_orbital (for circular binary)
- Chirp: frequency increases as orbit decays (df/dt > 0)
- Post-Newtonian: corrections in powers of (v/c)^2 ~ (Gm/rc^2)
```

### Statistical Mechanics

```
Before computing a partition function or thermodynamic quantity:
1. High-T: Z → (number of states) × e^{-βE_avg}, entropy → k_B ln(Ω)
2. Low-T: Z → g_0 e^{-βE_0}, dominated by ground state degeneracy g_0
3. Equipartition: Each quadratic degree of freedom contributes k_BT/2 to energy
4. Third law: S → 0 (or S → k_B ln g_0) as T → 0
5. Extensivity: F, S, U scale linearly with N in thermodynamic limit
6. Stability: C_V ≥ 0, κ_T ≥ 0 (mechanical and thermal stability)
7. Maxwell relations: ∂S/∂V|_T = ∂P/∂T|_V, etc.

Example prediction set for quantum spin chain:
- Lieb-Schultz-Mattis: Half-integer spin per unit cell → gapless or degenerate ground state
- Marshall sign rule (antiferromagnet): Ground state coefficients have definite sign pattern
- Total spin: [H, S_total] = 0 → energy eigenstates have good total S quantum number
- Finite-size: E_0(L) = e_0 L + (πv_s c)/(6L) + ... (CFT prediction for 1D critical systems)
```

### Atomic and Molecular Physics

```
Before computing energy levels or transition rates:
1. Hydrogen-like scaling: E_n ~ -Z²/(2n²) in atomic units
2. Selection rules: ΔL = ±1, ΔM = 0, ±1 (electric dipole)
3. Sum rules: Thomas-Reiche-Kuhn f-sum rule: Σ_n f_{0n} = Z (oscillator strengths)
4. Variational bound: Any trial wavefunction gives E ≥ E_0 (exact ground state)
5. Virial theorem: ⟨T⟩ = -⟨V⟩/2 (Coulomb potential)
6. Koopmans' theorem: Ionization energy ≈ -orbital energy (in Hartree-Fock)
7. Hund's rules: Ground state term determined by S, L, J maximization rules
```

</subfield_prediction_patterns>

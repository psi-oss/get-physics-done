---
load_when:
  - "verification"
  - "dimensional analysis"
  - "limiting cases"
  - "symmetry check"
  - "conservation law"
  - "physical plausibility"
  - "cancellation detection"
tier: 1
context_cost: large
---

# Verification Core — Universal Physics Checks

Dimensional analysis, limiting cases, symmetry, conservation laws, order-of-magnitude estimation, and physical plausibility. These checks catch ~60% of all physics errors and apply to every subfield.

**Load when:** Always — these are the non-negotiable checks for any physics calculation.

**Related files:**
- `references/verification/core/verification-quick-reference.md` — compact checklist (default entry point)
- `references/verification/core/verification-numerical.md` — convergence, statistical validation, numerical stability
- `../domains/verification-domain-qft.md` — QFT, particle, GR, mathematical physics
- `../domains/verification-domain-condmat.md` — condensed matter, quantum information, AMO
- `../domains/verification-domain-statmech.md` — statistical mechanics, cosmology, fluids
- `../audits/verification-gap-analysis.md` — coverage matrix: which defense layers catch which error classes

---

<core_principle>
**Existence != Correctness**

A calculation existing does not mean the physics is right. Verification must check:

1. **Exists** - Result is present (equation derived, code runs, number produced)
2. **Dimensionally consistent** - All terms have matching dimensions; units propagate correctly
3. **Physically plausible** - Result is the right order of magnitude, has correct sign, obeys known constraints
4. **Cross-validated** - Agrees with independent methods, known limits, conservation laws, and literature

Levels 1-3 can often be checked programmatically. Level 4 requires deeper analysis and sometimes human judgment.

**Level 5: External Oracle** — Result verified by an independent computational system (SymPy, numpy, or other CAS/numerical library) whose output is shown in VERIFICATION.md. This is the strongest form of verification because it breaks the LLM self-consistency loop: the LLM cannot hallucinate a correct CAS output.

Every VERIFICATION.md MUST include at least one Level 5 check — an executed code block with actual output. See `references/verification/core/computational-verification-templates.md` for copy-paste-ready templates.
</core_principle>

> **Key companion document:** See `../errors/llm-physics-errors.md` for the catalog of 104 LLM-specific physics error classes with detection strategies and traceability matrix.

<dimensional_analysis>

## Dimensional Analysis Verification

The most fundamental physics check. If dimensions don't match, the result is certainly wrong.

**Principle:** Every term in an equation must have the same dimensions. Every argument of a transcendental function (exp, log, sin, etc.) must be dimensionless.

**Automated checks:**

```python
# Using sympy.physics.units or pint
from sympy.physics.units import Dimension
from sympy.physics.units.systems import SI

def check_dimensions(lhs_dim, rhs_dim):
    """Verify both sides of an equation have matching dimensions."""
    if lhs_dim != rhs_dim:
        raise DimensionError(
            f"Dimensional mismatch: LHS has {lhs_dim}, RHS has {rhs_dim}"
        )
```

**Manual verification protocol:**

1. Write dimensions of every quantity in the expression using base dimensions [M], [L], [T], [Q], [Theta]
2. Verify each additive term has identical dimensions
3. Verify all exponents, arguments of exp/log/sin/cos are dimensionless
4. Check that defined constants carry their correct dimensions (e.g., hbar has [M L^2 T^{-1}])

**Concrete examples by subfield:**

### QFT dimensional analysis

```
Electron self-energy Sigma(p):
  - [Sigma] = [mass] = [M] (in natural units, [energy])
  - At one loop: Sigma ~ alpha * m * log(Lambda/m)
  - alpha is dimensionless, m has [M], log is dimensionless
  - Common error: writing Sigma ~ alpha * Lambda (linear divergence has wrong structure for Dirac fermion)

QED vertex correction Gamma^mu(p, p'):
  - [Gamma^mu] = [dimensionless] (same as bare vertex gamma^mu in natural units)
  - Must be: Gamma^mu = gamma^mu F_1(q^2) + (i*sigma^{mu nu}*q_nu / 2m) F_2(q^2)
  - F_1, F_2 are dimensionless form factors
  - q^2/m^2 is dimensionless argument

Vacuum energy density:
  - [rho_vac] = [energy/volume] = [M L^{-1} T^{-2}] = [M^4] in natural units
  - Naive QFT: rho ~ Lambda^4 / (16*pi^2) -> [M^4]
  - Observed: rho ~ (2.3 meV)^4 -- 120 orders of magnitude smaller
```

### Condensed matter dimensional analysis

```
Conductivity sigma:
  - [sigma] = [Omega^{-1} m^{-1}] = [Q^2 T / (M L^3)]
  - Drude: sigma = n e^2 tau / m -> [L^{-3}][Q^2][T][M^{-1}] = [Q^2 T / (M L^3)]
  - Quantum of conductance: e^2/h -> [Q^2 T / (M L^2)] = [Omega^{-1}]

Superfluid density rho_s:
  - [rho_s] = [M / (L T^2)] (London penetration depth: lambda_L^2 = m c^2 / (4*pi n_s e^2))
  - Must vanish at T_c and equal total density at T = 0

Magnetic susceptibility chi:
  - [chi] = [dimensionless] (SI: chi = M/H, both [A/m])
  - Curie law: chi = C/T -> C has dimensions [Kelvin] = [Theta]
  - Pauli: chi ~ mu_B^2 N(E_F) -> [J/T]^2 [J^{-1} m^{-3}] = [J T^{-2} m^{-3}] ...
    must check with mu_0 factor for SI consistency
```

### Cosmology dimensional analysis

```
Friedmann equation:
  H^2 = (8*pi*G/3)*rho
  - [H] = [T^{-1}], [H^2] = [T^{-2}]
  - [G rho] = [M^{-1} L^3 T^{-2}] * [M L^{-3}] = [T^{-2}]

Hubble parameter today:
  H_0 ~ 70 km/s/Mpc -> verify: [L T^{-1} L^{-1}] = [T^{-1}]
  H_0 ~ 2.3e-18 s^{-1} -> Hubble time t_H ~ 4.4e17 s ~ 14 Gyr

Power spectrum P(k):
  - [P(k)] = [L^3] (3D), defined via <delta(k)delta(k')> = (2*pi)^3 delta^3(k-k') P(k)
  - Dimensionless: Delta^2(k) = k^3 P(k) / (2*pi^2)
  - Common confusion: the exponent is n_s - 1 in Delta^2(k), but n_s - 4 in P(k),
    because Delta^2(k) = k^3 P(k)/(2*pi^2). Always verify which spectrum is being parameterized.
```

**Common dimensional pitfalls:**

| Pitfall                                   | Example                                               | Detection                    |
| ----------------------------------------- | ----------------------------------------------------- | ---------------------------- |
| Missing factors of c                      | E = m instead of E = mc^2                             | [E] = [M] vs [M L^2 T^{-2}]  |
| Missing factors of hbar                   | omega vs E                                            | [T^{-1}] vs [M L^2 T^{-2}]   |
| Natural units leaking into SI expressions | Setting c=1 then plugging into SI formula             | Dimensions don't close       |
| Confusing angular frequency and frequency | omega = 2*pi*f, different dimensions if units assumed | Check 2*pi factors           |
| Temperature vs energy                     | k_B*T vs T                                            | [M L^2 T^{-2}] vs [Theta]    |
| Metric signature convention               | g^{00} = +1 vs -1 flips sign of energy                | Check (-,+,+,+) vs (+,-,-,-) |
| Fourier transform convention              | Factors of 2*pi in momentum-space expressions         | Check integral dk/(2*pi) vs integral dk |
| Gaussian vs SI electrodynamics            | Factor of 4*pi*epsilon_0 present or absent            | e^2 vs e^2/(4*pi*epsilon_0)  |

**When to apply:**

- Every derived equation (non-negotiable)
- Every numerical expression before evaluation
- When converting between unit systems

</dimensional_analysis>

<limiting_cases>

## Limiting Case Verification

A correct general result must reproduce known special cases. If it doesn't, something is wrong.

**Principle:** Take your general result and apply physically meaningful limits. The result must reduce to the known expression for that regime.

**Standard limiting cases by domain:**

### Classical limit (hbar -> 0)

```
Quantum result -> Classical result
- Quantum partition function -> Boltzmann partition function
- Schrodinger equation -> Hamilton-Jacobi equation (via WKB)
- Commutators -> Poisson brackets (times i*hbar)
- Bose-Einstein/Fermi-Dirac -> Maxwell-Boltzmann
```

### Non-relativistic limit (v/c -> 0, or c -> infinity)

```
Relativistic result -> Non-relativistic result
- E = gamma*m*c^2 -> m*c^2 + p^2/(2m)
- Dirac equation -> Pauli equation -> Schrodinger equation
- Klein-Gordon -> Schrodinger (for positive-energy sector)
- Relativistic dispersion -> p^2/(2m)
```

### Weak-coupling limit (g -> 0)

```
Interacting result -> Free/non-interacting result
- Full propagator -> Free propagator
- Interacting ground state energy -> sum of single-particle energies
- Scattering amplitude -> Born approximation
- RG beta function -> one-loop result
```

### Large-N limit

```
Finite-N result -> Analytical large-N result
- Matrix model -> saddle-point
- SU(N) gauge theory -> planar diagrams
- Statistical mechanics -> mean-field
```

### Thermodynamic limits

```
T -> 0: System should reach ground state
T -> infinity: Equipartition, maximum entropy
N -> infinity: Thermodynamic limit, extensive quantities scale with N
```

### Continuum limit (lattice spacing a -> 0)

```
Lattice result -> Continuum result
- Lattice dispersion 2(1-cos(ka))/a^2 -> k^2
- Wilson fermions -> Dirac fermions (doubler-free)
- Lattice gauge theory -> continuum Yang-Mills
- Key: physical quantities must be independent of a in the continuum limit
- Renormalization: bare couplings flow with a to keep physics fixed
```

### Strong-coupling limit (g -> infinity)

```
Interacting result -> Strong-coupling result
- Lattice gauge theory -> strong-coupling expansion (confinement manifest)
- Hubbard model (U/t -> infinity) -> Heisenberg model (t-J model)
- AdS/CFT: strong-coupling field theory -> classical gravity
- BCS -> BEC crossover: weak coupling BCS -> strong coupling BEC
```

### Geometric/spatial limits

```
r -> 0: Short-distance behavior (UV)
r -> infinity: Long-distance behavior (IR)
d -> 1, 2, 3, 4: Specific dimensionality results
Flat space limit: Curved space -> Minkowski (R_{mu nu rho sigma} -> 0)
Homogeneous limit: Spatially varying -> uniform (k -> 0 of response functions)
Single-site limit: Lattice -> isolated site (hopping t -> 0)
```

### Adiabatic / sudden limits

```
Slow perturbation (omega -> 0): Adiabatic theorem, system follows instantaneous eigenstate
Fast perturbation (omega -> infinity): Sudden approximation, state unchanged
Intermediate: Full time-dependent perturbation theory required
Born-Oppenheimer: m_e/M -> 0, electrons follow nuclei adiabatically
```

**Verification protocol:**

```python
def verify_limiting_case(general_result, limit_params, expected_limit):
    """
    Apply limit to general result and compare with known expression.

    Args:
        general_result: Symbolic expression for the general case
        limit_params: Dict of {symbol: limit_value} e.g., {hbar: 0, c: oo}
        expected_limit: Known result in the limiting regime
    """
    limited = general_result
    for param, value in limit_params.items():
        limited = sympy.limit(limited, param, value)
    limited = sympy.simplify(limited)
    expected = sympy.simplify(expected_limit)
    assert limited == expected, (
        f"Limiting case failed:\n"
        f"  General result in limit: {limited}\n"
        f"  Expected: {expected}"
    )
```

**When to apply:**

- After every derivation of a general formula
- When extending known results to new regimes
- When combining results from different approximation schemes

</limiting_cases>

<symmetry_verification>

## Symmetry Verification

Physical results must respect the symmetries of the theory. Broken symmetries indicate errors (or genuine physics that must be explained).

**Principle:** If the Lagrangian/Hamiltonian has a symmetry, physical observables must reflect that symmetry unless spontaneous or explicit breaking is expected and understood.

**Key symmetries to verify:**

### Gauge invariance

```
- Electromagnetic: Results independent of gauge choice (Coulomb, Lorenz, axial, etc.)
- Non-Abelian: Results independent of gauge-fixing parameter xi
- Observable quantities must be gauge-invariant
- Green's functions can be gauge-dependent (but Ward identities constrain them)
```

**Check:** Compute the same observable in two different gauges. Results must agree.

### Lorentz/Poincare invariance

```
- Scalar quantities must transform as scalars
- 4-vectors must transform correctly under boosts and rotations
- Cross sections must be Lorentz-invariant (when expressed in invariant variables s, t, u)
- No preferred frame artifacts in final results
```

**Check:** Express result in manifestly covariant form. If you can't, suspect an error.

### CPT symmetry

```
- C (charge conjugation): Particle <-> antiparticle
- P (parity): x -> -x
- T (time reversal): t -> -t
- CPT combined: Always conserved in local QFT
```

### Discrete symmetries

```
- Parity: Check even/odd behavior under spatial inversion
- Time reversal: Check behavior under t -> -t
- Particle exchange: Bosonic (symmetric) vs Fermionic (antisymmetric) wavefunctions
```

### Conformal symmetry

```
At critical points and in CFTs:
- Scale invariance: Correlation functions are power laws
- Conformal Ward identities constrain 2-point and 3-point functions completely
- Unitarity bounds on scaling dimensions: Delta >= (d-2)/2 for scalars
- Central charge c > 0 (2D), a-theorem a_UV > a_IR (4D)
```

### Internal symmetries

```
- Flavor symmetry: SU(2) isospin, SU(3) flavor
- Chiral symmetry: Left-right decomposition
- Global U(1): Charge conservation, baryon number, lepton number
- Supersymmetry (if applicable): Boson-fermion mass degeneracy, non-renormalization theorems
```

**Verification protocol:**

```python
def verify_symmetry(expression, transformation, expected_behavior="invariant"):
    """
    Apply symmetry transformation and check behavior.

    Args:
        expression: The physics expression to check
        transformation: Dict mapping {old_symbol: new_expression}
        expected_behavior: "invariant", "covariant", "sign_flip", "phase"
    """
    transformed = expression.subs(transformation)
    transformed = sympy.simplify(transformed)
    original = sympy.simplify(expression)

    if expected_behavior == "invariant":
        assert transformed == original
    elif expected_behavior == "sign_flip":
        assert transformed == -original
    elif expected_behavior == "phase":
        ratio = sympy.simplify(transformed / original)
        assert abs(ratio) == 1  # Phase factor
```

**When to apply:**

- After constructing any Lagrangian or Hamiltonian
- After computing scattering amplitudes or cross sections
- When results look frame-dependent or gauge-dependent
- When particle-antiparticle results differ unexpectedly

</symmetry_verification>

<conservation_laws>

## Conservation Law Verification

Conserved quantities must actually be conserved by your calculation. Violations indicate either errors or new physics that must be justified.

**Principle:** For every continuous symmetry (Noether's theorem), there is a conserved current. Check that your results respect all expected conservation laws.

**Fundamental conservation laws:**

| Conserved Quantity | Associated Symmetry  | When Violated                      |
| ------------------ | -------------------- | ---------------------------------- |
| Energy             | Time translation     | Never (in closed systems)          |
| Momentum           | Space translation    | External fields present            |
| Angular momentum   | Rotational symmetry  | Non-central forces                 |
| Electric charge    | U(1)\_EM gauge       | Never (exactly)                    |
| Baryon number      | U(1)\_B global       | Sphaleron processes, GUT           |
| Lepton number      | U(1)\_L global       | Neutrino oscillations, GUT         |
| Color charge       | SU(3) gauge          | Never (confinement)                |
| CPT                | Lorentz + QFT axioms | Never (in local QFT)               |
| Probability        | Unitarity            | Truncation errors, non-Hermitian H |

**Numerical conservation checks:**

```python
def verify_energy_conservation(trajectory, hamiltonian, tolerance=1e-8):
    """Check energy is conserved along a trajectory."""
    energies = [hamiltonian(state) for state in trajectory]
    E0 = energies[0]
    max_drift = max(abs(E - E0) / abs(E0) for E in energies)
    assert max_drift < tolerance, (
        f"Energy conservation violated: max relative drift = {max_drift:.2e}"
    )

def verify_probability_conservation(density_matrix_trajectory, tolerance=1e-10):
    """Check Tr(rho) = 1 throughout evolution."""
    for t, rho in density_matrix_trajectory:
        trace = np.trace(rho)
        assert abs(trace - 1.0) < tolerance, (
            f"Probability not conserved at t={t}: Tr(rho) = {trace}"
        )

def verify_current_conservation(j_mu, spacetime_grid, tolerance=1e-8):
    """Check d_mu j^mu = 0 (continuity equation)."""
    divergence = compute_4divergence(j_mu, spacetime_grid)
    max_violation = np.max(np.abs(divergence))
    assert max_violation < tolerance, (
        f"Current conservation violated: max |d_mu j^mu| = {max_violation:.2e}"
    )

def verify_unitarity(S_matrix, tolerance=1e-10):
    """Check S^dagger S = I (probability conservation in scattering)."""
    product = S_matrix.conj().T @ S_matrix
    identity = np.eye(S_matrix.shape[0])
    deviation = np.max(np.abs(product - identity))
    assert deviation < tolerance, (
        f"Unitarity violated: max |S^dag S - I| = {deviation:.2e}"
    )
```

**Analytical conservation checks:**

1. Compute the time derivative of the supposedly conserved quantity
2. Use equations of motion to simplify
3. Verify the result is exactly zero (or zero up to the expected anomaly)

**When to apply:**

- Every numerical simulation (energy, momentum, particle number)
- Every scattering calculation (unitarity, crossing symmetry)
- Every quantum evolution (probability conservation, norm preservation)
- When adding interactions (check which conservation laws survive)

</conservation_laws>

<order_of_magnitude>

## Order-of-Magnitude Estimation

Before trusting a detailed calculation, estimate the answer to within a factor of 10. If the detailed result differs by orders of magnitude from the estimate, something is likely wrong.

**Principle:** Physics problems usually have a natural scale set by the relevant dimensionful parameters. The answer should be within an order of magnitude of this natural scale.

**Estimation techniques:**

### Dimensional analysis estimation

```
Given the relevant parameters, construct the unique combination with the right dimensions.

Example: Ground state energy of hydrogen
- Relevant parameters: m_e, e, hbar
- Energy has dimensions [M L^2 T^{-2}]
- Unique combination: m_e * e^4 / hbar^2 ~ 27 eV (Hartree)
- Actual: 13.6 eV (factor of 2 from detailed calculation)
```

### Characteristic scale estimation

```
Identify the characteristic scales of the problem:
- Length: Bohr radius a_0 = hbar^2 / (m_e * e^2) ~ 0.5 Angstrom
- Energy: Hartree E_h = m_e * e^4 / hbar^2 ~ 27 eV
- Time: hbar / E_h ~ 2.4e-17 s

Any atomic physics result should be expressible as a dimensionless number times the
appropriate power of these scales.
```

### Fermi estimation

```
Break the problem into factors you can estimate individually:

Example: Mean free path of a photon in the Sun's core
- Density: ~150 g/cm^3
- Temperature: ~15 million K -> mostly ionized hydrogen
- Cross section: Thomson ~ 6.65e-25 cm^2
- Number density: 150 / m_p ~ 9e25 cm^{-3}
- Mean free path: 1 / (n * sigma) ~ 1 / (9e25 * 6.65e-25) ~ 0.02 cm
```

**Verification protocol:**

```python
def order_of_magnitude_check(detailed_result, estimate, max_orders=2):
    """
    Check that detailed result is within max_orders of magnitude of estimate.
    """
    if estimate == 0 or detailed_result == 0:
        return  # Can't compare orders of magnitude with zero

    log_ratio = abs(np.log10(abs(detailed_result / estimate)))
    status = "pass" if log_ratio < max_orders else "FAIL"
    print(f"{status} Order-of-magnitude: detailed={detailed_result:.2e}, "
          f"estimate={estimate:.2e}, ratio=10^{log_ratio:.1f}")
```

**When to apply:**

- Before starting any detailed calculation (set expectations)
- After completing a calculation (sanity check)
- When a result "feels wrong" but you can't immediately see the error
- When presenting results to collaborators (builds confidence)

</order_of_magnitude>

<physical_plausibility>

## Physical Plausibility Checks

Even if a calculation is internally consistent, the result must make physical sense.

**Principle:** Physics imposes constraints beyond dimensional analysis. Masses must be positive, probabilities must be between 0 and 1, entropy must increase, and so on.

**Universal plausibility checks:**

| Check                               | Condition                                    | If Violated                 |
| ----------------------------------- | -------------------------------------------- | --------------------------- |
| Positivity of energy (ground state) | E_0 >= E_min (for bounded-below systems)     | Check for sign errors       |
| Probability bounds                  | 0 <= P <= 1 for all probabilities            | Check normalization         |
| Entropy direction                   | S >= 0, dS/dt >= 0 (isolated system)         | Check second law compliance |
| Causality                           | No superluminal signaling                    | Check light cone structure  |
| Stability                           | Perturbations don't grow unboundedly         | Check eigenvalue signs      |
| Hermiticity                         | Observables have real expectation values      | Check operator adjoint      |
| Positivity of cross sections        | sigma >= 0                                   | Check phase space factors   |
| Correct high/low temperature limits | C_V -> 0 as T -> 0, equipartition as T -> inf | Check statistical mechanics |
| Correct asymptotic behavior         | Wavefunctions -> 0 at infinity (bound states) | Check boundary conditions   |
| Spectral properties                 | Eigenvalues of Hermitian operators are real   | Check numerical precision   |

**Domain-specific plausibility:**

### Quantum mechanics

```
- Expectation values of positive operators must be positive
- Uncertainty relations satisfied: Dx Dp >= hbar/2
- Wavefunction normalizable (for bound states)
- Energy eigenvalues bounded below (for stable systems)
- Transition probabilities sum to <= 1
```

### Thermodynamics

```
- Heat capacity C_V >= 0 (stability)
- Compressibility kappa >= 0 (mechanical stability)
- Free energy F = U - TS must be minimized at equilibrium
- Phase transitions: Clausius-Clapeyron relation satisfied
- Third law: S -> 0 (or constant) as T -> 0
```

### Electrodynamics

```
- Poynting vector gives correct energy flow direction
- Radiation pattern has correct multipole structure
- Far-field falls off as 1/r
- Near-field has correct singularity structure
- Optical theorem satisfied (for scattering)
```

### Particle physics

```
- Cross sections positive and finite (after renormalization)
- Decay rates Gamma >= 0
- Branching ratios sum to 1
- Mandelstam variables satisfy s + t + u = sum(m^2)
- Froissart bound respected at high energy
```

**When to apply:**

- After every calculation before reporting results
- When results are surprising or unexpected
- When working in unfamiliar regimes
- As a final sanity check before publication

</physical_plausibility>

<in_execution_validation>

## In-Execution Validation Patterns

Validate intermediate results during plan execution -- catching errors as they happen rather than after all tasks are complete.

**Core Principle: Validate as you go, not after the fact.** Every task that produces a result should validate that result before the next task consumes it. Errors propagate and compound -- a sign error in task 1 becomes an unrecoverable mess by task 5.

### Validation Hierarchy

Apply in order of diagnostic power (cheapest and most informative first):

1. **Dimensional Analysis (Every Result):** Before moving to the next task, verify dimensions of all new expressions.
2. **Special Values (When Available):** Test expressions at known points before using them in subsequent calculations.
3. **Symmetry Checks (Before Building on Result):** Verify the result has the symmetries it must have before proceeding.
4. **Numerical Sanity (For Computational Tasks):** After generating numerical results, check before saving.

### When to Validate

| After This                       | Validate This                              | How                               |
| -------------------------------- | ------------------------------------------ | --------------------------------- |
| Deriving an equation             | Dimensions of every new expression         | Count [M], [L], [T] powers        |
| Computing an integral            | Special values, limiting cases             | Substitute known parameter values |
| Writing numerical code           | Test on trivially solvable case            | Compare to analytical result      |
| Solving an eigenvalue problem    | Spectrum properties (real, bounded, trace) | Numerical checks                  |
| Computing a correlation function | Symmetry properties, asymptotics           | Check specific limits             |
| Performing a Fourier transform   | Parseval's theorem, reality conditions     | Numerical cross-check             |

### Validation Failure Protocol

When a validation check fails during execution:

1. **Stop the current task.** Do not proceed to the next task.
2. **Record the failure** in the SUMMARY with details (expected, obtained, magnitude of discrepancy).
3. **Attempt to diagnose** using the deviation rules (Rule 4: add missing steps).
4. **If fixable within scope:** Fix, re-validate, continue.
5. **If not fixable:** Complete the current task with the failure noted, flag in SUMMARY as blocking.

</in_execution_validation>

## Analytical Derivation Checklist

- [ ] Dimensional analysis: all terms match
- [ ] Limiting cases: reduces to known results in appropriate limits
- [ ] Symmetries: result respects all symmetries of the theory
- [ ] Conservation laws: derived expression conserves expected quantities
- [ ] Sign conventions: consistent throughout (metric signature, Fourier transform convention, etc.)
- [ ] Index structure: all tensor indices properly contracted
- [ ] Boundary conditions: satisfied by the solution
- [ ] Order-of-magnitude: result is the expected scale

## Paper-Ready Result Checklist

- [ ] All applicable checks passed (see domain-specific files)
- [ ] Significant figures: reported precision matches actual uncertainty
- [ ] Error bars: statistical and systematic separated
- [ ] Chi-squared / goodness of fit: reported for all fits
- [ ] Literature comparison: agreement or explained disagreement with prior work
- [ ] Units stated: every dimensional quantity has explicit units
- [ ] Conventions stated: metric signature, normalization, etc.
- [ ] Code/data available: results are reproducible by others

## When to Require Human Verification

Some physics checks can't be fully automated. Flag these for human review:

**Always human:**

- Physical interpretation of results (does the physics make sense?)
- Choice of approximation scheme (is the method appropriate?)
- Assessment of systematic errors (what have we neglected?)
- Novel results that disagree with literature (error or discovery?)
- Sign of interference terms (constructive vs destructive)
- Topological considerations (winding numbers, Berry phases)
- Renormalization scheme dependence of intermediate quantities

**Human if uncertain:**

- Whether a divergence is physical or an artifact
- Whether symmetry breaking is spontaneous or due to a bug
- Phase transition order (requires careful finite-size scaling analysis)
- Whether numerical noise is masking a real signal
- Interpretation of degenerate solutions

## Adversarial Verification (Red Team Check)

For results with HIGH physics impact, spawn a lightweight "red team" check:
- Goal: Find an error in this result
- Try: wrong limiting case, dimensional inconsistency, sign error, missing factor
- Try: convention mismatch, boundary condition error, approximation breakdown
- Try: construct a counterexample where the result gives unphysical predictions
- Report: Either a specific error found, or "no error found after N checks"

## Cancellation Detection

When a computed result is anomalously small compared to individual contributing terms, this signals either a symmetry-enforced cancellation or a sign error.

**Protocol:**

1. **Compute the cancellation ratio:** R = |final_result| / max(|individual_terms|)
2. **If R < 1e-4, this is likely a symmetry-enforced cancellation.** Investigate before trusting the result.
3. **Identify the enforcing mechanism:**
   - Ward identity (gauge symmetry)
   - Conservation law (Noether symmetry)
   - Selection rule (discrete symmetry)
   - Supersymmetric cancellation (boson-fermion)
   - Topological protection
4. **If no symmetry explanation exists, suspect a sign error in one of the canceling terms.**
5. **Verify by perturbing:** Break the expected symmetry slightly and check that the result becomes O(perturbation). If it doesn't, the cancellation is accidental and likely wrong.

**Quantitative thresholds:**

| Cancellation Ratio R | Interpretation | Action |
|---|---|---|
| R > 0.1 | Normal; no special concern | Standard verification |
| 1e-4 < R < 0.1 | Moderate cancellation | Identify mechanism; verify analytically |
| R < 1e-4 | Extreme cancellation | Must identify symmetry or suspect error |
| R < 1e-10 | Almost certainly symmetry-protected | Ward identity or exact cancellation required |

## See Also

- `references/verification/core/verification-quick-reference.md` -- Compact checklist (default entry point)
- `references/verification/core/verification-numerical.md` -- Convergence testing, statistical validation, numerical stability
- `../domains/verification-domain-qft.md` -- QFT, particle physics, GR, mathematical physics
- `../domains/verification-domain-condmat.md` -- Condensed matter, quantum information, AMO
- `../domains/verification-domain-statmech.md` -- Statistical mechanics, cosmology, fluids
- `../errors/llm-physics-errors.md` -- Catalog of 101 LLM-specific error classes with detection strategies

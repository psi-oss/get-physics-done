---
template_version: 1
---

> **Context:** This template is for the `map-theory` workflow — analyzing an EXISTING research project
> to understand its current state. For pre-project literature research, see `templates/research-project/`.

# Theoretical Framework Template

Template for `.planning/analysis/THEORETICAL_FRAMEWORK.md` - captures the conceptual and theoretical organization of the physics.

**Purpose:** Document how the physics is organized at a conceptual level. Map the theoretical structure - what theories, what approximations, what mathematical objects. Complements STRUCTURE.md (which shows physical file locations and code layout).

---

## File Template

```markdown
# Theoretical Framework

**Analysis Date:** [YYYY-MM-DD]

## Theory Overview

**Overall:** [Framework name: e.g., "Perturbative QCD at NLO", "Classical N-body gravity with PN corrections", "Lattice QCD with Wilson fermions"]

**Key Characteristics:**

- [Characteristic 1: e.g., "Lorentz-invariant field theory"]
- [Characteristic 2: e.g., "Perturbative expansion in alpha_s"]
- [Characteristic 3: e.g., "Continuum limit extrapolation required"]

## Theoretical Layers

[Describe the conceptual layers and their relationships]

**[Layer Name]:**

- Purpose: [What this layer of theory does]
- Contains: [Types of mathematical objects: e.g., "Lagrangian density, Feynman rules, renormalization group equations"]
- Depends on: [What it assumes: e.g., "gauge symmetry, locality"]
- Used by: [What builds on it: e.g., "cross-section calculations, decay rate predictions"]

**[Layer Name]:**

- Purpose: [What this layer does]
- Contains: [Mathematical objects]
- Depends on: [Assumptions]
- Used by: [What builds on it]

## Approximation Hierarchy

[Describe the chain of approximations from first principles to the working equations]

**[Approximation Level] (e.g., "Exact Theory"):**

- Description: [What the exact/starting theory is]
- Mathematical form: [e.g., "Full path integral of QCD"]
- Status: [e.g., "Not directly solvable"]

**[Approximation Level] (e.g., "Leading Order"):**

- Description: [What approximation is made]
- Validity: [When this is a good approximation]
- Error estimate: [e.g., "O(alpha_s^2) corrections neglected"]
- Breaks down when: [Conditions where this fails]

**[Approximation Level] (e.g., "Numerical Implementation"):**

- Description: [Discretization or truncation used]
- Validity: [Parameter regime]
- Error estimate: [Systematic uncertainty]
- Breaks down when: [Conditions]

## Key Mathematical Objects

[Core mathematical structures used throughout the analysis]

**[Object Name]:**

- Definition: [What it represents physically and mathematically]
- Examples: [e.g., "Green's functions G^(n), self-energy Sigma(p)"]
- Properties: [e.g., "Satisfies Ward identities, analytic in upper half-plane"]

**[Object Name]:**

- Definition: [What it represents]
- Examples: [Concrete examples]
- Properties: [Key properties and symmetries]

## Symmetries and Conservation Laws

[What symmetries constrain the physics]

**[Symmetry]:**

- Type: [e.g., "Continuous global symmetry", "Discrete gauge symmetry"]
- Consequence: [e.g., "Conserved current J^mu, Ward identity"]
- Status: [e.g., "Exact", "Broken by anomaly", "Approximate to O(m_q/Lambda)"]

## Parameter Space

[Key parameters of the theory and their physical meaning]

**[Parameter]:**

- Symbol: [e.g., "alpha_s"]
- Physical meaning: [e.g., "Strong coupling constant"]
- Typical range: [e.g., "0.1 - 0.3 depending on energy scale"]
- How determined: [e.g., "Extracted from Z-pole measurements"]

## Regime of Validity

**Energy/length scales:** [e.g., "Valid for Q >> Lambda_QCD ~ 200 MeV"]
**Coupling requirements:** [e.g., "Perturbative expansion requires alpha_s(Q) << 1"]
**Other conditions:** [e.g., "Assumes thermodynamic equilibrium", "Neglects finite-size effects"]

## Connections to Experiment

**Observable quantities:**

- [Observable]: [How computed from theory]
- [Observable]: [How computed from theory]

**Measurable predictions:**

- [Prediction]: [Theoretical value +/- uncertainty]

---

_Theoretical framework analysis: [date]_
_Update when major theoretical assumptions change_
```

<good_examples>

```markdown
# Theoretical Framework

**Analysis Date:** 2025-06-15

## Theory Overview

**Overall:** Post-Newtonian Binary Inspiral with Gravitational Wave Emission

**Key Characteristics:**

- Weak-field, slow-motion expansion of general relativity
- Point-particle approximation for compact objects
- Radiation reaction via balance equations
- Matched asymptotic expansion (near zone / far zone)

## Theoretical Layers

**General Relativity (exact):**

- Purpose: Fundamental theory of gravity
- Contains: Einstein field equations, geodesic equation, stress-energy tensor
- Depends on: Equivalence principle, diffeomorphism invariance
- Used by: Everything below

**Post-Newtonian Expansion:**

- Purpose: Systematic weak-field slow-motion approximation to GR
- Contains: PN-expanded metric, equations of motion, energy flux
- Depends on: v/c << 1 and GM/(rc^2) << 1
- Used by: Waveform generation, orbital evolution

**Waveform Generation:**

- Purpose: Compute gravitational wave strain h(t) at detector
- Contains: Multipolar post-Minkowskian formalism, radiative moments
- Depends on: Post-Newtonian source moments, matching to far zone
- Used by: Data analysis templates, parameter estimation

**Orbital Dynamics:**

- Purpose: Evolve binary orbit under radiation reaction
- Contains: Orbital energy E(v), angular momentum L(v), flux F(v)
- Depends on: Balance equations dE/dt = -F
- Used by: Waveform phasing, merger time estimation

## Approximation Hierarchy

**Exact GR:**

- Description: Full nonlinear Einstein equations for two-body problem
- Mathematical form: G_mu_nu = 8 pi T_mu_nu with point-particle stress-energy
- Status: No closed-form solution; requires numerical relativity for strong field

**Post-Newtonian (3.5PN):**

- Description: Expansion in v/c to order (v/c)^7 beyond Newtonian
- Validity: Orbital separation r >> GM/c^2 (well before merger)
- Error estimate: O((v/c)^8) ~ 10^-4 for early inspiral, O(1) near ISCO
- Breaks down when: Binary separation approaches ~6M (ISCO)

**Quadrupole Formula (Leading Order):**

- Description: Lowest-order gravitational radiation, Newtonian orbits
- Validity: Very early inspiral, v/c < 0.1
- Error estimate: 1PN corrections are ~(v/c)^2 ~ 1-10%
- Breaks down when: Comparable mass binaries in late inspiral

## Key Mathematical Objects

**Post-Newtonian Metric:**

- Definition: g_mu_nu = eta_mu_nu + h_mu_nu expanded in powers of 1/c
- Examples: g_00 = -1 + 2U/c^2 - 2U^2/c^4 + ... , g_0i = -4V_i/c^3 + ...
- Properties: Satisfies harmonic gauge condition, recovers Schwarzschild in one-body limit

**Radiative Multipole Moments:**

- Definition: Source moments I_L, J_L related to matter distribution, radiative moments U_L, V_L at infinity
- Examples: Mass quadrupole I_ij, current quadrupole J_ij
- Properties: Related by matching in buffer zone; U_ij = I_ij^(2) + nonlinear corrections

**Gravitational Wave Strain:**

- Definition: Transverse-traceless perturbation h_ij^TT at distance r
- Examples: h\_+ = (1/r) _ (2 mu v^2 x / c^4) _ (harmonics), h_x similarly
- Properties: Two polarizations, falls off as 1/r, frequency is twice orbital frequency

## Symmetries and Conservation Laws

**Poincare Invariance:**

- Type: Global symmetry of asymptotically flat spacetime
- Consequence: Conserved ADM mass, linear momentum, angular momentum
- Status: Exact for isolated system

**Circular Orbit Symmetry:**

- Type: Helical Killing vector (approximate)
- Consequence: Simplifies PN expansion; quasi-circular orbit assumption
- Status: Approximate; broken by radiation reaction (adiabatic approximation)

**Parity:**

- Type: Discrete symmetry under spatial inversion
- Consequence: Even-parity (mass) and odd-parity (current) moments separate
- Status: Exact in GR (no parity violation)

## Parameter Space

**Total Mass M:**

- Symbol: M = m_1 + m_2
- Physical meaning: Total gravitational mass of binary
- Typical range: 2 - 200 solar masses (stellar to intermediate)
- How determined: Chirp mass from GW frequency evolution

**Symmetric Mass Ratio:**

- Symbol: nu = m_1 m_2 / M^2
- Physical meaning: Measures asymmetry; nu = 1/4 for equal mass
- Typical range: 0 < nu <= 1/4
- How determined: Amplitude corrections and higher harmonics

**Orbital Velocity Parameter:**

- Symbol: x = (G M omega / c^3)^(2/3)
- Physical meaning: Gauge-invariant PN expansion parameter
- Typical range: 0.01 (early inspiral) to ~0.2 (near merger)
- How determined: Instantaneous GW frequency

## Regime of Validity

**Energy/length scales:** Valid for orbital separation r >> 6 GM/c^2 (well outside ISCO)
**Coupling requirements:** PN expansion parameter x = (v/c)^2 << 1, practically x < 0.2
**Other conditions:** Assumes adiabatic inspiral (timescale separation between orbital and radiation-reaction), neglects tidal effects (valid for black holes, approximate for neutron stars)

## Connections to Experiment

**Observable quantities:**

- Gravitational wave strain h(t): Computed from radiative moments at detector location
- GW frequency evolution df/dt: Determined by energy balance equation
- Number of orbital cycles in band: Integral of frequency evolution from f_low to f_ISCO

**Measurable predictions:**

- Chirp mass: Extracted from leading-order frequency evolution with ~0.1% precision
- Mass ratio: Extracted from higher-order PN phase corrections with ~10% precision
- Luminosity distance: Extracted from strain amplitude with ~30% precision

---

_Theoretical framework analysis: 2025-06-15_
_Update when major theoretical assumptions change_
```

</good_examples>

<guidelines>
**What belongs in THEORETICAL_FRAMEWORK.md:**
- Overall theoretical framework (what theory, what regime)
- Conceptual layers of the theory and their relationships
- Approximation hierarchy from exact to working equations
- Key mathematical objects and their properties
- Symmetries and conservation laws
- Parameter space and physical meaning
- Regime of validity and breakdown conditions
- Connection to observables and experiment

**What does NOT belong here:**

- Exhaustive file listings (that's STRUCTURE.md)
- Computational methods and codes (that's METHODS.md)
- Detailed derivations (defer to notes/papers)
- Specific numerical results (those belong in research logs)

**File paths ARE welcome:**
Include file paths to derivation notebooks, code implementations, or reference papers. Use backtick formatting: `derivations/pn_expansion.nb`. This makes the framework document actionable for GPD when planning.

**When filling this template:**

- Identify the fundamental theory and state it precisely
- Trace the approximation chain from exact to computational
- List all assumptions explicitly (these become failure modes)
- Note where each approximation breaks down
- Keep descriptions conceptual but precise in physics language

**Useful for research planning when:**

- Extending calculations to higher order (what needs to change?)
- Checking consistency (are approximations compatible?)
- Identifying where to improve (which approximation dominates error?)
- Understanding scope (what questions can this framework answer?)
- Onboarding to a new calculation (what is the starting point?)
  </guidelines>

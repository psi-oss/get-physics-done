---
template_version: 1
---

<!-- Analysis findings only — conventions AS FOUND in an existing project.
     For the project's CANONICAL conventions (used during execution), see STATE.md Convention Lock
     and .planning/CONVENTIONS.md (the authoritative convention catalog). -->

> **Context:** This template is for the `map-theory` workflow — analyzing an EXISTING research project
> to understand its current state. It is NOT the project's convention authority.

# Conventions Analysis Template

Template for `.planning/analysis/CONVENTIONS-AUDIT.md` — captures notation, sign conventions, unit systems, and index placement rules as found in existing code and papers.

**Purpose:** Document how physics is currently written in an existing project being analyzed. This is a read-only analysis artifact. The project's canonical conventions are set in `.planning/CONVENTIONS.md` and tracked via STATE.md's Convention Lock.

---

## File Template

```markdown
# Conventions

**Analysis Date:** [YYYY-MM-DD]

## Metric and Signature

**Metric signature:**

- [e.g., "Mostly plus (-,+,+,+)" or "Mostly minus (+,-,-,-)"]
- [Reference: e.g., "Following Misner, Thorne, Wheeler"]

**Metric notation:**

- [e.g., "g_mu_nu for spacetime metric, gamma_ij for spatial metric"]
- [e.g., "eta_mu_nu = diag(-1,+1,+1,+1) for Minkowski"]

## Unit System

**Natural units:**

- [e.g., "c = hbar = 1 unless explicitly restored"]
- [e.g., "G = 1 in geometric units; G restored in final expressions"]

**Dimensional conventions:**

- [e.g., "Mass in solar masses M_sun, distance in Mpc, time in seconds"]
- [e.g., "Energy in GeV, cross sections in pb"]

**Conversion factors used:**

- [e.g., "1 GeV^-1 = 0.197 fm"]
- [e.g., "G M_sun / c^2 = 1.476 km"]

## Index Conventions

**Spacetime indices:**

- [e.g., "Greek letters mu, nu, rho, sigma = 0,1,2,3"]
- [e.g., "Latin letters i, j, k = 1,2,3 for spatial indices"]

**Internal/group indices:**

- [e.g., "Latin letters a, b, c for gauge group (SU(3) color)"]
- [e.g., "Capital letters A, B for spinor indices"]

**Multi-index notation:**

- [e.g., "L = i_1 i_2 ... i_l for STF multi-indices"]

**Summation convention:**

- [e.g., "Einstein summation on repeated upper/lower indices"]
- [e.g., "Spatial sums use delta_ij; no distinction between upper and lower spatial indices in flat background"]

## Sign Conventions

**Curvature tensors:**

- [e.g., "Riemann: R^rho_sigma_mu_nu = partial_mu Gamma^rho_nu_sigma - partial_nu Gamma^rho_mu_sigma + ..."]
- [e.g., "Ricci: R_mu_nu = R^rho_mu_rho_nu (contraction on first and third indices)"]
- [e.g., "Einstein equations: G_mu_nu = 8 pi G T_mu_nu (positive on right-hand side)"]

**Fourier transform:**

- [e.g., "f(t) = integral dw/(2pi) f_tilde(w) e^{-i w t}"]
- [e.g., "f_tilde(w) = integral dt f(t) e^{+i w t}"]

**Covariant derivative:**

- [e.g., "nabla_mu V^nu = partial_mu V^nu + Gamma^nu_mu_rho V^rho"]

**Action principle:**

- [e.g., "S = integral d^4x sqrt(-g) L, with equations of motion from delta S = 0"]

## Notation Standards

**Vectors and tensors:**

- [e.g., "Bold for 3-vectors: **v**, components v^i"]
- [e.g., "No bold for 4-vectors, written as V^mu"]
- [e.g., "Hat for unit vectors: n-hat"]

**Derivatives:**

- [e.g., "Overdot for time derivative: x-dot = dx/dt"]
- [e.g., "Partial derivatives: partial_mu or partial/partial x^mu"]
- [e.g., "Superscript (n) for nth time derivative: I_ij^(n)"]

**Special functions and operators:**

- [e.g., "STF projection denoted by angle brackets: <ij> = STF part of ij"]
- [e.g., "Trace-free: T_{<ij>} = T_{ij} - (1/3) delta_{ij} T_{kk}"]

**Perturbation theory:**

- [e.g., "Superscript (n) for nth-order perturbation: h^(1)_mu_nu"]
- [e.g., "Subscript PN for post-Newtonian order: E_2PN"]

## Labeling Conventions

**Particle/body labels:**

- [e.g., "Bodies labeled 1, 2 with m_1 >= m_2 by convention"]
- [e.g., "Relative coordinates: r = x_1 - x_2, center of mass: X = (m_1 x_1 + m_2 x_2)/M"]

**Coupling constants:**

- [e.g., "alpha_s for strong coupling, alpha = e^2/(4 pi) for QED"]
- [e.g., "G for Newton's constant, kappa = 8 pi G for gravitational coupling"]

**Coordinate systems:**

- [e.g., "Harmonic coordinates for PN calculations"]
- [e.g., "Boyer-Lindquist for Kerr black hole"]
- [e.g., "(r, theta, phi) for spherical, (rho, z, phi) for cylindrical"]

## Comments and Documentation

**When to annotate equations:**

- [e.g., "Always note the PN order of each term"]
- [e.g., "Always cite the source equation number for non-trivial results"]
- [e.g., "Note which convention is used if it differs from the project default"]

**Reference format:**

- [e.g., "Author (year), Eq. (N) for published results"]
- [e.g., "Derivation in derivations/filename.nb for our own results"]

**Code-physics correspondence:**

- [e.g., "Variable names in code match notation: `mass_ratio_nu` for nu, `pn_parameter_x` for x"]
- [e.g., "All dimensionful quantities carry units in variable name: `distance_mpc`, `mass_msun`"]

---

_Convention analysis: [date]_
_Update when conventions change_
```

<good_examples>

```markdown
# Conventions

**Analysis Date:** 2025-06-15

## Metric and Signature

**Metric signature:**

- Mostly plus (-,+,+,+)
- Following Blanchet, Living Reviews in Relativity (2014)

**Metric notation:**

- g_mu_nu for full spacetime metric
- eta_mu_nu = diag(-1,+1,+1,+1) for Minkowski background
- h_mu_nu for metric perturbation: g_mu_nu = eta_mu_nu + h_mu_nu

## Unit System

**Natural units:**

- G = c = 1 throughout derivations
- Factors of G and c restored in final numerical expressions and in code

**Dimensional conventions:**

- Mass in solar masses (M_sun) for astrophysical quantities
- Mass in kg for SI expressions
- Distance in Mpc for cosmological, meters for local

**Conversion factors used:**

- G M_sun / c^2 = 1476.625 m
- G M_sun / c^3 = 4.925491 x 10^-6 s
- 1 Mpc = 3.0857 x 10^22 m

## Index Conventions

**Spacetime indices:**

- Greek mu, nu, rho, sigma, lambda = 0,1,2,3
- Latin i, j, k, l, m = 1,2,3 for spatial

**Multi-index notation:**

- L = i_1 i_2 ... i_l for symmetric trace-free (STF) multi-indices
- |L| = l denotes the number of indices
- Angle brackets <L> denote STF projection

**Summation convention:**

- Einstein summation on repeated spacetime indices (one up, one down)
- Spatial repeated indices summed with delta_ij (no up/down distinction in flat background)

## Sign Conventions

**Curvature tensors:**

- Riemann: R^alpha_beta_mu_nu = partial_mu Gamma^alpha_nu_beta - partial_nu Gamma^alpha_mu_beta + Gamma^alpha_mu_lambda Gamma^lambda_nu_beta - Gamma^alpha_nu_lambda Gamma^lambda_mu_beta
- Ricci tensor: R_mu_nu = R^alpha_mu_alpha_nu (trace on 1st and 3rd indices)
- Ricci scalar: R = g^mu_nu R_mu_nu
- Einstein equations: G_mu_nu + Lambda g_mu_nu = (8 pi G / c^4) T_mu_nu

**Fourier transform:**

- Time to frequency: f_tilde(f) = integral_{-inf}^{+inf} dt f(t) e^{+2 pi i f t}
- Frequency to time: f(t) = integral\_{-inf}^{+inf} df f_tilde(f) e^{-2 pi i f t}
- NOTE: Uses physicist frequency f (Hz), not angular frequency omega

**Gravitational wave strain:**

- h_+ - i h_x = sum_{l,m} h_{lm} \* _{-2}Y\_{lm}(theta, phi)
- Positive h\_+ stretches along x-axis, compresses along y-axis

## Notation Standards

**Vectors and tensors:**

- Bold for 3-vectors: **x**, **v**, **n**
- Components without bold: x^i, v^i, n^i
- Hat for unit vectors: **n** = **x** / |**x**|

**Derivatives:**

- Overdot for coordinate time derivative: v^i = dx^i/dt
- Superscript (n) for nth time derivative: I_ij^{(n)} = d^n I_ij / dt^n
- Partial derivative: partial_mu or comma notation T_{mu,nu} (rarely used)
- Covariant derivative: nabla_mu or semicolon notation T_{mu;nu}

**Post-Newtonian labeling:**

- nPN means order (v/c)^{2n} beyond leading Newtonian
- E.g., "3PN energy" means energy through O(v^6/c^6) relative corrections

## Labeling Conventions

**Binary system:**

- Bodies labeled A = 1, 2 with m_1 >= m_2 (heavier body is "1")
- Total mass: M = m_1 + m_2
- Reduced mass: mu = m_1 m_2 / M
- Symmetric mass ratio: nu = mu / M = m_1 m_2 / M^2
- Mass difference: delta = (m_1 - m_2) / M
- Relative separation: r = |**x_1** - **x_2**|, relative velocity: **v** = **v_1** - **v_2**

**PN expansion parameter:**

- x = (G M omega / c^3)^{2/3} (gauge-invariant, preferred)
- gamma = G M / (r c^2) (coordinate-dependent, used in intermediate steps)
- v = (G M omega)^{1/3} in G = c = 1 units

**Coordinate system:**

- Harmonic (de Donder) gauge throughout: partial_nu(sqrt(-g) g^{mu nu}) = 0
- Center-of-mass frame: m_1 **x_1** + m_2 **x_2** = 0

## Comments and Documentation

**When to annotate equations:**

- Every equation in derivation notebooks must note its PN order
- Results from literature must cite author, year, and equation number
- Convention-sensitive quantities (Riemann sign, Fourier sign) must note which convention

**Code-physics correspondence:**

- `nu` or `symmetric_mass_ratio` for nu
- `x` or `pn_x` for the PN parameter x
- `total_mass_msun` for M in solar masses (always with unit suffix)
- `distance_mpc` for luminosity distance in Mpc

---

_Convention analysis: 2025-06-15_
_Update when conventions change_
```

</good_examples>

<guidelines>
**What belongs in CONVENTIONS.md:**
- Metric signature choice
- Unit system and dimensional conventions
- Index naming and placement rules
- Sign conventions for curvature, Fourier transforms, etc.
- Notation standards for vectors, derivatives, perturbation theory
- Labeling conventions for particles, coordinates, parameters
- Code-to-physics variable name mapping

**What does NOT belong here:**

- Theoretical framework (that's THEORETICAL_FRAMEWORK.md)
- Computational methods (that's METHODS.md)
- Specific results or derivations (defer to notebooks)
- Project file structure (that's STRUCTURE.md)

**When filling this template:**

- Check existing derivation notebooks and papers for notation
- Identify the metric signature from the Lagrangian or action
- Note all sign conventions explicitly (these are the #1 source of errors)
- Be prescriptive: "Use (-,+,+,+)" not "Sometimes (+,-,-,-) is used"
- Note deviations: "Reference X uses opposite Fourier convention; multiply by -1 when comparing"
- Keep under ~200 lines total

**Useful for research planning when:**

- Writing new derivations (match existing notation)
- Comparing with literature (identify convention differences)
- Implementing equations in code (correct variable mapping)
- Debugging sign errors (check against documented conventions)
- Onboarding (understand notation at a glance)

**Why this matters:**
Sign and convention errors are among the most common and hardest-to-find bugs in physics calculations. A wrong metric signature propagates silently through every equation. A different Fourier convention flips signs in frequency-domain quantities. Documenting conventions explicitly prevents these errors.
</guidelines>

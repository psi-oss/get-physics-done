---
template_version: 1
---

# Conventions Ledger Template

Template for `.gpd/CONVENTIONS.md` — persistent, append-only record of all physics conventions adopted across the project lifetime.

**Purpose:** Single source of truth for every convention that could cause a cross-phase inconsistency. Read by the consistency checker to verify current-phase work against ALL accumulated conventions, not just adjacent phases.

**Convention selection by project type:**

| Convention Section | QFT | Cond. Matter | GR/Cosmo | Stat. Mech | AMO | Classical Mech | Nuclear |
|---|---|---|---|---|---|---|---|
| Metric Signature | Required | — | Required | — | — | — | — |
| Fourier Convention | Required | Required | Required | If response fn | Required | — | Required |
| Field Normalization | Required | Sometimes | — | — | — | — | Required |
| Gauge Choice | Required | Sometimes | Required | — | — | — | Required |
| Unit System | Required | Required | Required | Required | Required | Required | Required |
| Lattice Convention | If lattice | Required | — | Required | — | — | If lattice |
| Spin Convention | Sometimes | Required | — | Required | Required | — | Required |
| Coordinate Convention | — | — | Required | — | — | Required | — |
| Ensemble | — | Sometimes | — | Required | — | — | — |
| Regularization Scheme | Required | — | — | — | — | — | Required |
| Coupling Convention | Required | Sometimes | — | — | Sometimes | — | Required |
| Renormalization Scheme | Required | — | — | — | — | — | Required |
| Levi-Civita Sign | Required | — | Required | — | — | — | Required |
| Generator Normalization | Required | — | — | — | — | — | Required |
| Covariant Derivative Sign | Required | Sometimes | Required | — | — | — | Required |
| Gamma Matrix Convention | Required | — | — | — | — | — | Required |
| Creation/Annihilation Order | Required | Sometimes | — | Sometimes | Required | — | Required |

Populate sections marked "Required" for your project type. Sections marked "—" can be omitted. "Sometimes" means include only if relevant to your specific calculation.

**Relationship to other files:**

- `research-map/CONVENTIONS.md` is an analysis snapshot produced by `/gpd:map-research` — it documents what conventions ARE in existing work
- `CONVENTIONS.md` (this file) is prescriptive and persistent — it documents what conventions MUST BE followed going forward
- `NOTATION_GLOSSARY.md` lists every symbol; CONVENTIONS.md records the choices that govern how those symbols behave (signs, factors, normalizations)

---

## File Template

```markdown
# Conventions Ledger

**Project:** [project name]
**Created:** [YYYY-MM-DD]
**Last updated:** [YYYY-MM-DD] (Phase [N])

> This file is append-only for convention entries. When a convention changes, add a new
> entry with the updated value and mark the old entry as superseded. Never delete entries.

---

## Spacetime

### Metric Signature

| Field            | Value                                                                                |
| ---------------- | ------------------------------------------------------------------------------------ |
| **Convention**   | [e.g., Mostly plus: eta = diag(-1, +1, +1, +1)]                                      |
| **Introduced**   | Phase [N]                                                                            |
| **Rationale**    | [e.g., Matches Peskin & Schroeder, standard in particle physics]                     |
| **Dependencies** | Propagator signs, Wick rotation direction, stress-energy sign                        |
| **Test value**   | p^2 = -m^2 for on-shell timelike particle (mostly-plus) OR p^2 = +m^2 (mostly-minus) |

### Coordinate System

| Field            | Value                                                        |
| ---------------- | ------------------------------------------------------------ |
| **Convention**   | [e.g., Harmonic/de Donder gauge, Boyer-Lindquist, Cartesian] |
| **Introduced**   | Phase [N]                                                    |
| **Rationale**    | [reason]                                                     |
| **Dependencies** | Christoffel symbol expressions, boundary condition forms     |

### Index Positioning

| Field            | Value                                                                                                                  |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Greek mu,nu = 0,1,2,3 spacetime; Latin i,j,k = 1,2,3 spatial; Einstein summation on repeated upper-lower pairs] |
| **Introduced**   | Phase [N]                                                                                                              |
| **Rationale**    | [reason]                                                                                                               |
| **Dependencies** | All tensor equations, contraction rules                                                                                |

### Curvature Sign

| Field            | Value                                                                                                                              |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., R^rho_sigma_mu_nu = d_mu Gamma^rho_nu_sigma - d_nu Gamma^rho_mu_sigma + Gamma Gamma - Gamma Gamma; Ricci = R^rho_mu_rho_nu] |
| **Introduced**   | Phase [N]                                                                                                                          |
| **Rationale**    | [e.g., Follows Wald / MTW / Carroll]                                                                                               |
| **Dependencies** | Einstein equations sign, Ricci scalar sign, stress-energy coupling sign                                                            |
| **Test value**   | For a 2-sphere of radius a: R = 2/a^2 (positive)                                                                                   |

---

## Quantum Mechanics

### Fourier Convention

| Field            | Value                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., f_tilde(k) = integral dx f(x) e^{-ikx}; f(x) = integral dk/(2pi) f_tilde(k) e^{+ikx}] |
| **Introduced**   | Phase [N]                                                                                    |
| **Rationale**    | [e.g., Physics convention; plane wave e^{i(kx - wt)} for positive-energy particle]           |
| **Dependencies** | Propagator expressions, Green's function signs, convolution theorem form                     |
| **Test value**   | FT of delta(x) = 1; FT of 1 = 2pi delta(k)                                                   |

### Commutation Relations

| Field            | Value                                                                        |
| ---------------- | ---------------------------------------------------------------------------- |
| **Convention**   | [e.g., [x, p] = i hbar; [a, a^dag] = 1; {psi, psi^dag} = delta]              |
| **Introduced**   | Phase [N]                                                                    |
| **Rationale**    | [reason]                                                                     |
| **Dependencies** | Uncertainty relations, creation/annihilation algebra, propagator definitions |

### Time Ordering

| Field            | Value                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| **Convention**   | [e.g., T{A(t1) B(t2)} = theta(t1-t2) A(t1)B(t2) +/- theta(t2-t1) B(t2)A(t1); minus for fermions] |
| **Introduced**   | Phase [N]                                                                                        |
| **Rationale**    | [reason]                                                                                         |
| **Dependencies** | Feynman propagator definition, Wick's theorem signs                                              |

### State Normalization

| Field            | Value |
| ---------------- | ----- |
| **Convention**   | [e.g., `<k\|k'> = (2π)³ 2E_k δ³(k - k')` relativistic; or `<k\|k'> = δ³(k - k')` non-relativistic] |
| **Introduced**   | Phase [N] |
| **Rationale**    | [reason] |
| **Dependencies** | Completeness relation form, cross-section formulas, decay rate prefactors |
| **Test value**   | Completeness: `1 = ∫ d³k/(2π)³ 1/(2E_k) \|k><k\|` (relativistic) |

---

## Field Theory

### Gauge Choice

| Field            | Value                                                                    |
| ---------------- | ------------------------------------------------------------------------ |
| **Convention**   | [e.g., Feynman gauge (xi = 1), Lorenz gauge, Coulomb gauge, axial gauge] |
| **Introduced**   | Phase [N]                                                                |
| **Rationale**    | [reason]                                                                 |
| **Dependencies** | Propagator form, ghost sector, Ward identity form                        |

### Covariant Derivative and Gauge Coupling

| Field            | Value                                                                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., D_mu = partial_mu - i g A_mu (particle physics); or D_mu = partial_mu + i e A_mu (QED with e > 0)] |
| **Introduced**   | Phase [N]                                                                                                 |
| **Rationale**    | [reason]                                                                                                  |
| **Dependencies** | Field strength definition, vertex Feynman rules, beta function sign                                       |
| **Test value**   | [D_mu, D_nu] = -i g F_mu_nu (for D = d - igA convention)                                                  |

### Regularization Scheme

| Field            | Value                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------ |
| **Convention**   | [e.g., Dimensional regularization in d = 4 - 2 epsilon dimensions; mu is the MS-bar scale] |
| **Introduced**   | Phase [N]                                                                                  |
| **Rationale**    | [e.g., Preserves gauge invariance, standard for perturbative QFT]                          |
| **Dependencies** | Loop integral results, gamma_E and log(4pi) treatment, evanescent operators                |

### Renormalization Scheme and Scale

| Field            | Value                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., MS-bar at scale mu; or on-shell at p^2 = m^2; or momentum subtraction at p^2 = -mu^2]    |
| **Introduced**   | Phase [N]                                                                                       |
| **Rationale**    | [reason]                                                                                        |
| **Dependencies** | Beta function coefficients, anomalous dimensions, finite parts of counterterms                  |
| **Test value**   | [e.g., One-loop beta function coefficient b_0 = (11 C_A - 4 T_F n_f) / (3 * (4pi)^2) in MS-bar] |

### Coupling Convention

| Field            | Value                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., alpha_s = g^2/(4pi); Lagrangian uses g, amplitudes use g, beta function for alpha_s] |
| **Introduced**   | Phase [N]                                                                                   |
| **Rationale**    | [reason]                                                                                    |
| **Dependencies** | Perturbative series counting, loop-factor conventions, Feynman rule extraction              |

### Gamma Matrix Convention

| Field            | Value                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Dirac representation; {gamma^mu, gamma^nu} = 2 g^{mu nu}; gamma^5 = i gamma^0 gamma^1 gamma^2 gamma^3] |
| **Introduced**   | Phase [N]                                                                                                     |
| **Rationale**    | [reason]                                                                                                      |
| **Dependencies** | Trace identities, charge conjugation matrix, spinor completeness relations                                    |

### Levi-Civita Sign

| Field            | Value                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------ |
| **Convention**   | [e.g., epsilon^{0123} = +1 (Peskin & Schroeder); or epsilon^{0123} = -1 (Weinberg)]        |
| **Introduced**   | Phase [N]                                                                                  |
| **Rationale**    | [reason]                                                                                   |
| **Dependencies** | Dual field strength definition, axial anomaly sign, topological charge sign                |
| **Test value**   | epsilon^{0123} epsilon_{0123} = -1 (mostly-plus) or +1 (mostly-minus); F_dual = (1/2) epsilon F |

### Generator Normalization

| Field            | Value                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Tr(T^a T^b) = delta^{ab}/2 (fundamental, standard); or Tr(T^a T^b) = delta^{ab}]    |
| **Introduced**   | Phase [N]                                                                                   |
| **Rationale**    | [reason]                                                                                    |
| **Dependencies** | Casimir values, color factor extraction, beta function coefficients, Fierz identities       |
| **Test value**   | SU(3) fundamental: C_F = 4/3 with Tr = delta/2; C_F = 8/3 with Tr = delta                   |

### Creation/Annihilation Order

| Field            | Value                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------ |
| **Convention**   | [e.g., Normal ordering :...: puts all a^dag left of a; Wick contraction defined relative to normal ordering] |
| **Introduced**   | Phase [N]                                                                                                    |
| **Rationale**    | [reason]                                                                                                     |
| **Dependencies** | Vacuum energy subtraction, Wick's theorem, Green's function definitions, propagator signs                    |
| **Test value**   | :a a^dag: = a^dag a; <0|T{phi(x) phi(y)}|0> = <0|:phi(x) phi(y):|0> + contraction                           |

---

## Statistical Mechanics

### Ensemble

| Field            | Value                                                                                               |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Canonical (N, V, T fixed); Grand canonical (mu, V, T fixed); Microcanonical (E, V, N fixed)] |
| **Introduced**   | Phase [N]                                                                                           |
| **Rationale**    | [reason]                                                                                            |
| **Dependencies** | Partition function form, fluctuation relations, thermodynamic potential                             |

### Temperature Convention

| Field            | Value                                                                  |
| ---------------- | ---------------------------------------------------------------------- |
| **Convention**   | [e.g., beta = 1/(k_B T) with k_B explicit; or beta = 1/T with k_B = 1] |
| **Introduced**   | Phase [N]                                                              |
| **Rationale**    | [reason]                                                               |
| **Dependencies** | Boltzmann weights, free energy definition, entropy dimensions          |
| **Test value**   | Z = Tr(e^{-beta H}); F = -T ln Z = -(1/beta) ln Z                      |

### Partition Function Normalization

| Field            | Value                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Z = sum_states e^{-beta E_n}; or Z = (1/N!) integral d^{3N}p d^{3N}q / h^{3N} e^{-beta H} for identical particles] |
| **Introduced**   | Phase [N]                                                                                                                 |
| **Rationale**    | [reason]                                                                                                                  |
| **Dependencies** | Entropy extensivity, chemical potential, Gibbs paradox resolution                                                         |

### Order Parameter Convention

| Field            | Value                                                                          |
| ---------------- | ------------------------------------------------------------------------------ |
| **Convention**   | [e.g., Magnetization m = (1/N) sum_i S_i; or m = <phi> for field theory]       |
| **Introduced**   | Phase [N]                                                                      |
| **Rationale**    | [reason]                                                                       |
| **Dependencies** | Susceptibility definition, Binder cumulant form, critical exponent definitions |

---

## Numerical and Computational

### Unit System in Code

| Field            | Value                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Natural units (hbar = c = k_B = 1) in all code; SI restored only in final output/plots] |
| **Introduced**   | Phase [N]                                                                                      |
| **Rationale**    | [reason]                                                                                       |
| **Dependencies** | All numerical prefactors, comparison with analytical results, plot axis labels                 |
| **Test value**   | [e.g., Hydrogen ground state energy = -0.5 in atomic units, -13.6 eV in SI]                    |

### Discretization Convention

| Field            | Value                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| **Convention**   | [e.g., Forward Euler, Verlet, RK4; spatial: finite difference O(dx^2), spectral, finite element] |
| **Introduced**   | Phase [N]                                                                                        |
| **Rationale**    | [reason]                                                                                         |
| **Dependencies** | Convergence order, stability conditions (CFL), symplecticity                                     |

### Boundary Conditions

| Field            | Value                                                                        |
| ---------------- | ---------------------------------------------------------------------------- |
| **Convention**   | [e.g., Periodic in x,y,z; Dirichlet at r = R_max; outgoing-wave at infinity] |
| **Introduced**   | Phase [N]                                                                    |
| **Rationale**    | [reason]                                                                     |
| **Dependencies** | Allowed wavevectors, finite-size effects, Ewald summation applicability      |

### Grid/Lattice Convention

| Field            | Value                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Site-centered; lattice spacing a = 1; L sites per direction; momentum k_n = 2 pi n / L] |
| **Introduced**   | Phase [N]                                                                                      |
| **Rationale**    | [reason]                                                                                       |
| **Dependencies** | Brillouin zone definition, continuum limit, Fourier transform normalization on lattice         |

### Random Number and Sampling

| Field            | Value                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| **Convention**   | [e.g., Mersenne Twister with seed recorded per run; Metropolis acceptance min(1, e^{-beta Delta E})] |
| **Introduced**   | Phase [N]                                                                                            |
| **Rationale**    | [reason]                                                                                             |
| **Dependencies** | Reproducibility, detailed balance, error estimation                                                  |

---

## Convention Changes

> When a convention must change (e.g., switching from natural to SI units for a numerical
> section), record the change here. The old entry above stays; a new entry is added with
> a reference back.

| Change ID | Convention | Old Value  | New Value | Changed In | Reason                     | Conversion                                                           |
| --------- | ---------- | ---------- | --------- | ---------- | -------------------------- | -------------------------------------------------------------------- |
| [CHG-001] | [which]    | [previous] | [new]     | Phase [N]  | [why the change is needed] | [conversion factor or procedure to translate old-convention results] |

---

## Cross-Convention Compatibility Notes

> Record any known interactions between conventions that produce subtle factors.
> These are the "gotchas" that cause cross-phase errors.

| Convention A                 | Convention B                | Interaction                 | Factor / Sign                                                                    | Example                                                                   |
| ---------------------------- | --------------------------- | --------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| [e.g., Metric (-,+,+,+)]     | [e.g., FT sign e^{-ikx}]    | [Propagator pole structure] | [e.g., Feynman propagator = i/(p^2 - m^2 + i epsilon) with p^2 = -E^2 + p_vec^2] | [e.g., Wrong metric sign flips epsilon prescription]                      |
| [e.g., Coupling D = d - igA] | [e.g., alpha_s = g^2/(4pi)] | [Vertex Feynman rule]       | [e.g., Vertex = -ig gamma^mu T^a]                                                | [e.g., Using D = d + igA gives vertex = +ig, flipping interference terms] |

---

## Machine-Readable Convention Tests

```yaml
# Parseable by consistency checker for automated validation
convention_tests:
  metric_propagator:
    metric: "mostly_plus"  # (-,+,+,+)
    propagator: "i/(k²-m²+iε)"
    compatible: true
    test: "k=(1,0,0,0), m=1 → propagator = i/(1-1+iε) = i/iε"
  fourier_creation:
    fourier: "integral_dk_eikx"
    creation: "exp(-ikx)"
    compatible: true
  units_check:
    system: "natural"
    hbar: 1
    c: 1
    energy_mass_same_dim: true
  coupling_vertex:
    coupling: "alpha_s=g^2/(4pi)"
    covariant_derivative: "D=d-igA"
    vertex_rule: "-ig*gamma^mu*T^a"
    compatible: true
    test: "QED vertex with e>0, D=d+ieA: vertex = +ie*gamma^mu; check sign in Coulomb potential"
  coupling_beta_function:
    coupling: "alpha_s=g^2/(4pi)"
    scheme: "MSbar"
    one_loop_b0: "(11*C_A - 4*T_F*n_f) / (3*(4*pi)^2)"
    test: "SU(3), n_f=6: b0 = (33-24)/(48*pi^2) = 9/(48*pi^2)"
  renormalization_scheme:
    scheme: "MSbar"
    subtraction: "poles_plus_log4pi_minus_gammaE"
    compatible: true
    test: "One-loop self-energy: Sigma_MSbar = Sigma_bare - (alpha/4pi)(1/eps - gamma_E + ln(4pi))*(...)"
  levi_civita_sign:
    epsilon_0123: "+1"
    metric: "mostly_plus"
    test: "epsilon^{0123} epsilon_{0123} = -1 (with mostly-plus metric); F_dual^{mu nu} = (1/2) epsilon^{mu nu rho sigma} F_{rho sigma}"
  generator_normalization:
    trace_convention: "delta_over_2"
    test: "SU(3) fundamental: C_F = (N^2-1)/(2N) = 4/3 with Tr(T^a T^b) = delta^{ab}/2"
  covariant_derivative:
    sign: "minus"
    definition: "D_mu = partial_mu - ig A_mu"
    compatible: true
    test: "[D_mu, D_nu] = -ig F_{mu nu}; vertex rule = -ig gamma^mu T^a"
  gamma_matrix:
    representation: "Dirac"
    clifford: "{gamma^mu, gamma^nu} = 2*g^{mu nu}"
    gamma5: "i*gamma^0*gamma^1*gamma^2*gamma^3"
    test: "Tr(gamma^mu gamma^nu) = 4*g^{mu nu}; Tr(gamma^5) = 0"
  creation_annihilation:
    ordering: "normal"
    definition: ":a^dag a: = a^dag a"
    test: "<0|:phi^2:|0> = 0 (normal ordering subtracts vacuum expectation)"
```

**Purpose:** Enables the consistency checker to run test values programmatically rather than parsing prose descriptions.

---

_Conventions ledger created: [date]_
_Last updated: [date] (Phase [N])_
```

<lifecycle>

**Creation:** During project initialization, after PROJECT.md

- Pre-populate spacetime and quantum sections from PROJECT.md notation conventions
- Leave sections blank if not yet relevant (e.g., no field theory section for a classical mechanics project)
- Mark as "[Not yet established]" rather than guessing

**Appending:** During phase transitions

- Extract new conventions from phase SUMMARY.md and CONTEXT.md
- Add convention change entries if any convention was modified
- Add cross-convention compatibility notes when subtle interactions are discovered

**Reading:** By consistency checker at every milestone audit

- Read ALL entries (not just recent ones)
- Check current phase work against every accumulated convention
- Flag any convention that was established in phase M but not followed in phase N (for any M < N)

**Reading:** By executor during phase work

- Check active conventions before writing any equation
- Verify that new expressions are compatible with all listed conventions
- Consult cross-convention compatibility notes when combining results from different domains

</lifecycle>

<guidelines>

**What belongs in CONVENTIONS.md:**

- Every choice that has a "the other sign/factor/normalization would also be valid" alternative
- Every choice where getting it wrong produces a silently incorrect result (not a crash)
- Every choice that affects how expressions look in more than one phase

**What does NOT belong here:**

- Results and derived expressions (those go in SUMMARY.md)
- Symbol definitions without ambiguity (those go in NOTATION_GLOSSARY.md)
- Methodology decisions (those go in DECISIONS.md and CONTEXT.md)

**Test values are critical:**

Every convention entry SHOULD include a test value: a concrete numerical or algebraic check that verifies the convention is being followed. The consistency checker uses these test values for semantic verification.

Examples of good test values:

- Metric signature: "On-shell timelike: p^2 = -m^2 in mostly-plus"
- Fourier convention: "FT[delta(x)] = 1"
- Normalization: "integral |psi|^2 dx = 1 for single particle"
- Coupling: "One-loop vertex correction proportional to -alpha_s"

**Convention changes require conversion procedures:**

When a convention changes, the entry in the Convention Changes table MUST include the explicit conversion factor or procedure. This enables the consistency checker to verify that old-convention results imported into new-convention phases are correctly translated.

**Cross-convention compatibility notes prevent subtle errors:**

The most insidious bugs come from interactions between independently correct conventions. Two conventions can each be self-consistent but produce wrong results when combined. Document every such interaction as it is discovered.

**Keep it append-only:**

Never delete convention entries. Mark superseded entries with a reference to the change entry. This enables the consistency checker to trace the full history and verify that transitions were handled correctly.

</guidelines>

<extensibility>

**Adding new categories:**

This template covers common physics convention categories. Projects may need additional categories. Add them following the same structure:

```markdown
## [Category Name]

### [Convention Name]

| Field            | Value                                                |
| ---------------- | ---------------------------------------------------- |
| **Convention**   | [precise statement]                                  |
| **Introduced**   | Phase [N]                                            |
| **Rationale**    | [why this choice]                                    |
| **Dependencies** | [what other conventions or expressions this affects] |
| **Test value**   | [concrete check that this convention holds]          |
```

Examples of additional categories that specific projects might need:

- **Condensed Matter:** Brillouin zone convention, band structure gauge, Berry phase sign
- **General Relativity:** ADM vs covariant decomposition, conformal factor sign, extrinsic curvature sign
- **Fluid Dynamics:** Reynolds decomposition convention, turbulence model constants, stress tensor sign
- **Optics:** Electric field phase convention, Jones matrix convention, Stokes parameter definition
- **Nuclear/Particle:** Isospin convention, CKM parametrization, CP phase convention

</extensibility>

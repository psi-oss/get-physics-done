---
template_version: 1
---
# Requirements Template

Template for `.gpd/REQUIREMENTS.md` — checkable research requirements that define "done."

<template>

```markdown
# Requirements: [Research Project Title]

**Defined:** [date]
**Core Research Question:** [from PROJECT.md]

## Primary Requirements

Requirements for the main research deliverable. Each maps to roadmap phases.

### Derivations

- [ ] **DERV-01**: [e.g., Derive effective Lagrangian to one-loop order in coupling g]
- [ ] **DERV-02**: [e.g., Show Ward identities are satisfied at each order]
- [ ] **DERV-03**: [e.g., Obtain renormalization group equations for all couplings]

### Calculations

- [ ] **CALC-01**: [e.g., Evaluate Feynman diagrams contributing to the self-energy at 2-loop]
- [ ] **CALC-02**: [e.g., Numerically solve coupled ODEs for order parameter as function of temperature]
- [ ] **CALC-03**: [e.g., Compute spectral function from Green's function data]

### Simulations

- [ ] **SIMU-01**: [e.g., Run Monte Carlo simulation for N=10^4 particles at 5 temperature points]
- [ ] **SIMU-02**: [e.g., Achieve statistical error below 1% on energy per particle]

### Validations

- [ ] **VALD-01**: [e.g., Reproduce known result from Ref. [X] in appropriate limit]
- [ ] **VALD-02**: [e.g., Verify numerical results converge with increasing grid resolution]
- [ ] **VALD-03**: [e.g., Cross-check analytic and numerical results agree within error bars]

### [Category N]

- [ ] **[CAT]-01**: [Requirement description]
- [ ] **[CAT]-02**: [Requirement description]

## Follow-up Requirements

Deferred to future work or follow-up paper. Tracked but not in current roadmap.

### [Category]

- **[CAT]-01**: [Requirement description]
- **[CAT]-02**: [Requirement description]

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Topic   | Reason                                                                           |
| ------- | -------------------------------------------------------------------------------- |
| [Topic] | [Why excluded: e.g., requires non-perturbative methods beyond current framework] |
| [Topic] | [Why excluded: e.g., experimental data not yet available for comparison]         |

## Accuracy and Validation Criteria

Standards that results must meet before being considered complete.

| Requirement | Accuracy Target                | Validation Method                           |
| ----------- | ------------------------------ | ------------------------------------------- |
| [CALC-01]   | [e.g., 4 significant figures]  | [e.g., Compare with Ref. [X] Table 2]       |
| [SIMU-01]   | [e.g., Statistical error < 1%] | [e.g., Bootstrap error estimation]          |
| [DERV-01]   | [e.g., Exact analytic result]  | [e.g., Check limiting cases and symmetries] |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase                | Status  |
| ----------- | -------------------- | ------- |
| DERV-01     | Phase 2: Formalism   | Pending |
| CALC-01     | Phase 3: Calculation | Pending |
| SIMU-01     | Phase 3: Calculation | Pending |
| VALD-01     | Phase 4: Validation  | Pending |
| [REQ-ID]    | Phase [N]            | Pending |

**Coverage:**

- Primary requirements: [X] total
- Mapped to phases: [Y]
- Unmapped: [Z] (warning)

---

_Requirements defined: [date]_
_Last updated: [date] after [trigger]_
```

</template>

<guidelines>

**Requirement Format:**

- ID: `[CATEGORY]-[NUMBER]` (DERV-01, CALC-02, SIMU-03, VALD-01)
- Description: Precise, testable, atomic — a physicist can verify completion
- Checkbox: Only for primary requirements (follow-up requirements are not yet actionable)

**Categories:**

- Derive from the nature of the research project
- Keep consistent with physics domain conventions
- Typical: Derivations, Calculations, Simulations, Validations, Analysis, Comparisons, Paper

**Primary vs Follow-up:**

- Primary: Committed scope, will be in roadmap phases, needed for current paper
- Follow-up: Acknowledged but deferred, not in current roadmap, future paper material
- Moving Follow-up to Primary requires roadmap update

**Out of Scope:**

- Explicit exclusions with reasoning
- Prevents "why didn't you compute X?" later
- Topics outside the energy/length/time scale, beyond current approximation, or requiring unavailable data

**Accuracy and Validation Criteria:**

- Every quantitative result needs a defined accuracy target
- Every result needs a validation method (limiting case, literature comparison, numerical convergence)
- Be specific: "4 significant figures" not "high accuracy"

**Traceability:**

- Empty initially, populated during roadmap creation
- Each requirement maps to exactly one phase
- Unmapped requirements = roadmap gap

**Status Values:**

- Pending: Not started
- In Progress: Phase is active
- Complete: Requirement verified against accuracy criteria
- Blocked: Waiting on prerequisite result or external data

</guidelines>

<evolution>

**After each phase completes:**

1. Mark covered requirements as Complete
2. Update traceability status
3. Note any requirements that changed scope or accuracy targets

**After roadmap updates:**

1. Verify all primary requirements still mapped
2. Add new requirements if scope expanded
3. Move requirements to follow-up/out of scope if descoped

**Requirement completion criteria:**

- Requirement is "Complete" when:
  - Derivation/calculation is finished
  - Result meets accuracy criteria
  - Validation method confirms correctness
  - Result is documented with intermediate steps

</evolution>

<example>

```markdown
# Requirements: Topological Phase Transitions in 2D Spin Models

**Defined:** 2025-03-15
**Core Research Question:** Does the BKT transition survive in the presence of long-range interactions decaying as 1/r^alpha?

## Primary Requirements

### Derivations

- [ ] **DERV-01**: Derive RG flow equations for vortex fugacity and stiffness with 1/r^alpha coupling
- [ ] **DERV-02**: Identify fixed point structure and determine critical alpha_c
- [ ] **DERV-03**: Show standard BKT results recovered in alpha -> infinity limit

### Calculations

- [ ] **CALC-01**: Numerically solve RG flow equations for alpha in [1.5, 4.0] at 20 points
- [ ] **CALC-02**: Compute critical temperature T_c(alpha) curve
- [ ] **CALC-03**: Extract correlation length exponent nu(alpha) near transition

### Simulations

- [ ] **SIMU-01**: Monte Carlo simulation of XY model with long-range coupling, L = 16, 32, 64, 128
- [ ] **SIMU-02**: Finite-size scaling analysis to extract T_c for alpha = 2.0, 2.5, 3.0, 3.5
- [ ] **SIMU-03**: Measure helicity modulus jump at T_c to confirm BKT universality class

### Validations

- [ ] **VALD-01**: Reproduce standard BKT transition temperature for alpha -> infinity (short-range) limit
- [ ] **VALD-02**: Verify RG equations reduce to Kosterlitz (1974) in short-range limit
- [ ] **VALD-03**: Cross-check T_c(alpha) from RG and Monte Carlo agree within error bars

## Follow-up Requirements

### Extended Analysis

- **EXTD-01**: Compute entanglement entropy scaling near critical point
- **EXTD-02**: Study effect of disorder on long-range BKT transition
- **EXTD-03**: Extend to 3D systems

## Out of Scope

| Topic                     | Reason                                                           |
| ------------------------- | ---------------------------------------------------------------- |
| Quantum phase transitions | Classical model only; quantum version is separate paper          |
| Dynamics near transition  | Equilibrium properties only; dynamics requires different methods |
| Exact diagonalization     | System sizes too small for meaningful finite-size scaling        |

## Accuracy and Validation Criteria

| Requirement | Accuracy Target                         | Validation Method                      |
| ----------- | --------------------------------------- | -------------------------------------- |
| CALC-01     | 6 significant figures in T_c            | Convergence with RG truncation order   |
| CALC-02     | Error < 0.5% on T_c curve               | Compare independent RG implementations |
| SIMU-01     | Statistical error < 0.3% on energy      | Bootstrap with 1000 resamples          |
| SIMU-02     | T_c uncertainty < 1%                    | Finite-size scaling collapse quality   |
| VALD-01     | Match Kosterlitz (1974) T_c to 4 digits | Direct comparison                      |

## Traceability

| Requirement | Phase                | Status  |
| ----------- | -------------------- | ------- |
| DERV-01     | Phase 2: Formalism   | Pending |
| DERV-02     | Phase 2: Formalism   | Pending |
| DERV-03     | Phase 2: Formalism   | Pending |
| CALC-01     | Phase 3: Calculation | Pending |
| CALC-02     | Phase 3: Calculation | Pending |
| CALC-03     | Phase 3: Calculation | Pending |
| SIMU-01     | Phase 3: Calculation | Pending |
| SIMU-02     | Phase 3: Calculation | Pending |
| SIMU-03     | Phase 4: Validation  | Pending |
| VALD-01     | Phase 4: Validation  | Pending |
| VALD-02     | Phase 4: Validation  | Pending |
| VALD-03     | Phase 4: Validation  | Pending |

**Coverage:**

- Primary requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---

_Requirements defined: 2025-03-15_
_Last updated: 2025-03-15 after initial definition_
```

</example>

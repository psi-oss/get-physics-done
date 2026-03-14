# Witten Index of Orbifold Daughters of N=4 SYM

## What This Is

Non-perturbative lattice computation of the Witten index for Z_k orbifold daughter theories of N=4 super Yang-Mills, using the CKKU (Cohen-Kaplan-Katz-Unsal) lattice construction built on top of Catterall's public SUSY lattice code. The target theory is the Z_3 orbifold of SU(6) yielding an SU(2)^3 quiver gauge theory with bi-fundamental matter.

## Core Research Question

Can the Witten index of Z_k orbifold daughter theories of N=4 SYM be computed non-perturbatively using the CKKU lattice construction?

## Scoping Contract Summary

### Contract Coverage

- Witten index Tr(-1)^F for SU(2)^3 quiver: Novel lattice computation with quantified systematic errors
- SUSY Ward identity convergence: Must demonstrate restoration in continuum limit
- False progress to reject: Witten index numbers without Ward identity verification or continuum limit study

### User Guidance To Preserve

- **User-stated observables:** Witten index Tr(-1)^F for the orbifold daughter theory; SUSY Ward identity violations vs. lattice spacing
- **User-stated deliverables:** Witten index values with systematic errors, Ward identity convergence analysis, modified lattice code, publication-quality plots (Witten index vs. volume, Ward identity convergence vs. lattice spacing, continuum extrapolation)
- **Must-have references / prior outputs:** CKKU original papers; Catterall's papers and public code
- **Stop / rethink conditions:** Severe sign problem preventing signal extraction; Ward identities not converging with lattice refinement → pivot to different observable

### Scope Boundaries

**In scope**

- Implement Z_3 orbifold of SU(6) → SU(2)^3 quiver on the lattice via CKKU construction
- Build on Catterall's public SUSY lattice code
- Compute Witten index Tr(-1)^F for the orbifold daughter theory
- Numerical Monte Carlo simulations on local workstation / small cluster
- Verify SUSY Ward identities and continuum limit convergence
- Continuum limit extrapolation with systematic error analysis
- Cross-check consistency with parent N=4 SYM via orbifold equivalence

**Out of scope**

- Large N or large k studies requiring HPC-scale resources
- Dynamical questions (real-time evolution, transport)
- Theories beyond the orbifold daughter of N=4 SYM
- Comparison with experiment

### Active Anchor Registry

- REF-01: CKKU (Cohen-Kaplan-Katz-Unsal) orbifold lattice construction papers
  - Why it matters: Defines the lattice formulation for the orbifold construction
  - Carry forward: planning | execution | writing
  - Required action: read | use | cite
- REF-02: Catterall's papers and public code for lattice N=4 SYM
  - Why it matters: Provides the computational foundation code being extended
  - Carry forward: planning | execution | writing
  - Required action: read | use | cite

### Carry-Forward Inputs

- Catterall's public SUSY lattice code as computational starting point

### Skeptical Review

- **Weakest anchor:** Fermion sign problem manageability for the orbifold theory at small k, N
- **Unvalidated assumptions:** SUSY restoration in continuum limit for the daughter theory; orbifold equivalence holding at the lattice level for small N
- **Competing explanation:** Sign problem could be severe enough to prevent reliable Witten index extraction
- **Disconfirming observation:** Ward identities not decreasing with lattice refinement; severe sign problem preventing signal extraction even at smallest volumes
- **False progress to reject:** Witten index values without verified SUSY Ward identities; results without continuum limit extrapolation study

### Open Contract Questions

- Optimal lattice volumes for balancing cost vs. finite-volume effects
- Whether the sign problem is qualitatively different for the orbifold vs. parent theory
- Which specific Ward identities are most diagnostic

## Research Questions

### Answered

(None yet — investigate to answer)

### Active

- [ ] What is the Witten index of the SU(2)^3 quiver theory from Z_3 orbifold of SU(6)?
- [ ] Does SUSY restore in the continuum limit for the orbifold daughter theory on the lattice?
- [ ] Is the sign problem manageable for the orbifold theory at small k, N?
- [ ] Are the results consistent with parent N=4 SYM via orbifold equivalence?

### Out of Scope

- Large-N behavior — requires HPC resources beyond current scope
- Real-time dynamics — equilibrium properties only
- Quantum gravity connections — pure gauge theory investigation

## Research Context

### Physical System

Z_3 orbifold of N=4 SU(6) super Yang-Mills theory. The orbifold projection yields an SU(2)^3 quiver gauge theory with bi-fundamental matter fields connecting adjacent gauge nodes. The parent theory has maximal (N=4) supersymmetry; the orbifold daughter preserves reduced SUSY.

### Theoretical Framework

Lattice gauge theory with supersymmetry. The CKKU construction provides a lattice regularization that preserves a subset of the supercharges exactly, with the full SUSY algebra expected to restore in the continuum limit. The formulation uses a topological twist of N=4 SYM.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --------- | ------ | ------ | ----- |
| Orbifold order | k | 3 | Z_3 orbifold |
| Parent gauge group | SU(kN) | SU(6) | k=3, N=2 |
| Daughter gauge group | SU(N)^k | SU(2)^3 | Quiver structure |
| Lattice coupling | beta | To be determined | Controls lattice spacing |
| Lattice volume | L^4 | Small (workstation-scale) | Multiple volumes needed |
| Lattice spacing | a | Multiple values | For continuum extrapolation |

### Known Results

- N=4 SYM on the lattice via CKKU/Catterall construction — established
- SUSY Ward identities verified for parent N=4 SYM — Catterall et al.
- Orbifold equivalence between parent and daughter theories — Kovtun-Unsal-Yaffe / Bershadsky-Johansen

### What Is New

Novel non-perturbative computation of the Witten index for orbifold daughter theories of N=4 SYM. No existing lattice calculation of this quantity for these theories.

### Target Venue

To be determined.

### Computational Environment

Local workstation / small cluster. CPUs, possibly a few GPUs. Exploratory-scale Monte Carlo runs.

## Notation and Conventions

See `.gpd/CONVENTIONS.md` for all notation and sign conventions.
See `.gpd/NOTATION_GLOSSARY.md` for symbol definitions.

## Unit System

Lattice units (a = 1 in simulation; physical scale set by lattice coupling beta).

## Requirements

See `.gpd/REQUIREMENTS.md` for the detailed requirements specification.

## Key References

- REF-01: CKKU (Cohen-Kaplan-Katz-Unsal) orbifold lattice construction — defines the formulation
- REF-02: Catterall's papers and public code for lattice N=4 SYM — computational foundation

## Constraints

- **Computational resources**: Local workstation / small cluster — limits lattice volumes and statistics
- **Sign problem**: Fermion sign problem severity unknown a priori — may limit achievable precision
- **Code base**: Building on Catterall's existing public code — must understand and extend, not rewrite

## Key Decisions

| Decision | Rationale | Outcome |
| -------- | --------- | ------- |
| Z_3 orbifold of SU(6) as target theory | Tests k > 2 while remaining computationally accessible on workstation | Approved |
| CKKU lattice construction | Standard formulation for lattice N=4 SYM with exact subset of SUSY | Approved |
| Build on Catterall's code | Established, tested implementation to extend rather than rewrite | Approved |
| Pivot if sign problem severe | Ward identities or sign problem may block Witten index → switch observable | Contingency |

---

_Last updated: 2026-03-13 after initialization_

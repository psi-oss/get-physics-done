# Requirements: Witten Index of Orbifold Daughters of N=4 SYM

**Defined:** 2026-03-13
**Core Research Question:** Can the Witten index of Z_k orbifold daughter theories of N=4 SYM be computed non-perturbatively using the CKKU lattice construction?

## Primary Requirements

### Code Development

- [ ] **CODE-01**: Obtain and validate Catterall-Schaich lattice N=4 SYM code; reproduce published SU(2) Ward identities and Pfaffian phase on 4^4 lattice
- [ ] **CODE-02**: Implement Z_3 orbifold projection of SU(6) → SU(2)^3 quiver gauge structure with bi-fundamental matter in the CKKU framework
- [ ] **CODE-03**: Verify Q-exactness is preserved under the orbifold projection algebraically and numerically (Ward identity check)

### Feasibility

- [ ] **FEAS-01**: Measure Pfaffian phase distribution ⟨cos(α)⟩ for the SU(2)^3 daughter theory on 2^4 lattice — go/no-go gate for Witten index computation
- [ ] **FEAS-02**: Validate orbifold daughter code in free-field limit (g → 0) where analytical results exist
- [ ] **FEAS-03**: Measure Pfaffian phase scaling with volume — compute ⟨cos(α)⟩ on L=2 and L=4; if it degrades exponentially with volume, trigger pivot
- [ ] **FEAS-04**: Verify flat direction stability under the μ^2 deformation for the daughter theory — scalar eigenvalue distribution must remain bounded during MC evolution
- [ ] **FEAS-05**: Measure autocorrelation times for key observables (bosonic action, Pfaffian phase, scalar norms) on the daughter theory — if τ_int > 500 trajectories, simulation strategy needs revision
- [ ] **FEAS-06**: Test CG convergence for the quiver-structured Dirac operator — if condition number κ(D†D) is orders of magnitude worse than parent, assess preconditioning options

### Witten Index

- [ ] **WIDX-01**: Implement periodic fermion boundary conditions for Tr(-1)^F computation in the twisted lattice formulation
- [ ] **WIDX-02**: Compute Witten index via exact Pfaffian ratio Pf(M_PBC)/Pf(M_APBC) on L=2 lattice for SU(2)^3 daughter
- [ ] **WIDX-03**: Compute Witten index on L=4 lattice and verify volume independence (topological invariance)

### Validation

- [ ] **VALD-01**: Verify SUSY Ward identity convergence toward continuum limit at 3+ lattice spacings for the daughter theory
- [ ] **VALD-02**: Check β-independence (temporal extent) and μ-independence (soft SUSY-breaking mass) of the Witten index
- [ ] **VALD-03**: Monitor Z_3 center symmetry order parameter to test orbifold equivalence conditions
- [ ] **VALD-04**: Cross-check parent N=4 SYM results at 2+ couplings to verify code reproduces published static potential and Coulomb coefficient
- [ ] **VALD-05**: Verify orbifold equivalence: compare Z_3-neutral observables of daughter with parent SU(6) expectations (quantify 1/N^2 deviations)
- [ ] **VALD-06**: Check coupling independence of Witten index — compute at 2+ values of the 't Hooft coupling λ; index must be λ-independent
- [ ] **VALD-07**: Verify Witten index is close to an integer (within statistical error) — non-integer result signals methodology error or insufficient statistics
- [ ] **VALD-08**: Validate daughter theory free-field spectrum matches analytical quiver field content (correct DOF count per site)

### Deliverables

- [ ] **DLVR-01**: Publication-quality plots: Witten index vs. lattice volume, Ward identity convergence vs. lattice spacing, continuum limit extrapolation

## Triggers and Decision Gates

| Trigger | Condition | Action |
|---|---|---|
| Sign problem fatal | ⟨cos(α)⟩ < 0.1 on L=2 | Pivot to different observable (e.g., static potential, anomalous dimensions) |
| Sign problem marginal | 0.1 < ⟨cos(α)⟩ < 0.5 on L=2 | Investigate complex Langevin or increased N as mitigation |
| Ward identity failure | Violations not decreasing with lattice refinement after 3+ spacings | Stop production; diagnose whether Q-exactness was broken by orbifold |
| Flat direction runaway | Scalar eigenvalues growing secularly during MC | Increase μ; if persists at large μ, investigate admissibility condition |
| Non-integer Witten index | \|W - round(W)\| > 3σ after full statistics | Review BC implementation; check Pfaffian computation; increase statistics |
| Orbifold equivalence broken | Z_3 order parameter nonzero with > 5σ significance | Proceed with daughter-only analysis; do not rely on parent cross-checks |

## Follow-up Requirements

### Extended Analysis

- **EXTD-01**: Compute Witten index for Z_2 orbifold of SU(4) → SU(2)^2 (preserves N=2 SUSY; simpler validation case)
- **EXTD-02**: Explore larger N (SU(3)^3 from Z_3 of SU(9)) to quantify 1/N^2 corrections
- **EXTD-03**: Investigate other topological observables (e.g., 't Hooft flux sectors)
- **EXTD-04**: Port code to GPU for production-scale runs at larger volumes

## Out of Scope

| Topic | Reason |
|---|---|
| Large N or large k studies | Requires HPC-scale resources beyond workstation |
| Dynamical questions (real-time, transport) | Equilibrium properties only |
| Theories beyond orbifold daughters of N=4 SYM | Focused scope |
| Comparison with experiment | Pure theory investigation |
| L ≥ 8 exact Pfaffian | Infeasible: memory > 1 TB |

## Accuracy and Validation Criteria

| Requirement | Accuracy Target | Validation Method |
|---|---|---|
| CODE-01 | Match published SU(2) Ward identity to 2σ | Compare with Catterall-Schaich (arXiv:1505.03135) |
| FEAS-01 | ⟨cos(α)⟩ measured to ±0.05 | 1000+ configurations with exact Pfaffian |
| WIDX-02 | Witten index within 0.5 of nearest integer | Exact Pfaffian on all configurations |
| WIDX-03 | L=2 and L=4 indices agree within 2σ | Volume independence check |
| VALD-01 | Ward identity violations decrease monotonically | 3+ lattice spacings, linear fit in a^2 |
| VALD-02 | W(β₁) = W(β₂) within 2σ | 2+ temporal extents |
| VALD-06 | W(λ₁) = W(λ₂) within 2σ | 2+ coupling values |

## Contract Coverage

| Requirement | Decisive Output / Deliverable | Anchor / Benchmark | Prior Inputs | False Progress To Reject |
|---|---|---|---|---|
| CODE-01 | Validated parent code | Catterall-Schaich published results | Catterall public code | Code runs but doesn't reproduce benchmarks |
| CODE-02 | Modified quiver code | CKKU construction papers | Parent code | Code compiles but field content is wrong |
| FEAS-01 | Pfaffian phase measurement | — (novel) | Parent phase measurements | Phase measured but on too few configs |
| WIDX-02 | Witten index value (L=2) | — (novel) | Pfaffian phase study | Index without Ward identity verification |
| WIDX-03 | Volume independence check | Topological invariance | L=2 result | Single volume without comparison |
| VALD-01 | Ward identity convergence | Parent theory Ward identities | — | Violations measured but not extrapolated |
| DLVR-01 | Publication plots | — | All numerical results | Plots without systematic error budget |

## Traceability

| Requirement | Phase | Status |
|---|---|---|
| CODE-01 | TBD | Pending |
| CODE-02 | TBD | Pending |
| CODE-03 | TBD | Pending |
| FEAS-01 | TBD | Pending |
| FEAS-02 | TBD | Pending |
| FEAS-03 | TBD | Pending |
| FEAS-04 | TBD | Pending |
| FEAS-05 | TBD | Pending |
| FEAS-06 | TBD | Pending |
| WIDX-01 | TBD | Pending |
| WIDX-02 | TBD | Pending |
| WIDX-03 | TBD | Pending |
| VALD-01 | TBD | Pending |
| VALD-02 | TBD | Pending |
| VALD-03 | TBD | Pending |
| VALD-04 | TBD | Pending |
| VALD-05 | TBD | Pending |
| VALD-06 | TBD | Pending |
| VALD-07 | TBD | Pending |
| VALD-08 | TBD | Pending |
| DLVR-01 | TBD | Pending |

**Coverage:**

- Primary requirements: 21 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 21

---

_Requirements defined: 2026-03-13_
_Last updated: 2026-03-13 after initial definition_

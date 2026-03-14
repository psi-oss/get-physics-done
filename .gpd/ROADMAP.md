# Roadmap: Witten Index of Orbifold Daughters of N=4 SYM

## Overview

Non-perturbative lattice computation of the Witten index for the Z_3 orbifold daughter of N=4 SU(6) SYM using the CKKU construction, building on Catterall's public code. 6 sequential phases with a hard GO/NO-GO gate at Phase 3 (sign problem feasibility). All phases on the critical path.

## Phases

- [ ] **Phase 1: Setup & Parent Theory Validation** - Obtain code, reproduce SU(2) N=4 SYM benchmarks
- [ ] **Phase 2: Orbifold Implementation** - Z_3 projection to SU(2)^3 quiver, verify Q-exactness
- [ ] **Phase 3: Sign Problem Feasibility** - Pfaffian phase measurement — GO/NO-GO gate
- [ ] **Phase 4: Witten Index Computation** - Periodic BCs, exact Pfaffian ratio on L=2,4
- [ ] **Phase 5: Systematic Validation** - Ward identities, parameter independence, orbifold equivalence
- [ ] **Phase 6: Analysis & Publication** - Plots, error budget, manuscript

## Phase Details

### Phase 1: Setup & Parent Theory Validation

**Goal:** Catterall-Schaich code obtained, compiled, and validated against published SU(2) N=4 SYM benchmarks
**Depends on:** Nothing (entry point)
**Requirements:** CODE-01, VALD-04, VALD-08
**Contract coverage:** DLV-03 (code foundation); REF-01, REF-02 (CKKU papers, Catterall code); FP-01/FP-02 enforced (no production without validation)
**Success Criteria:**

1. Code compiles and runs on local workstation; runtime profiled for SU(2) on L=2 and L=4
2. SU(2) bosonic action Ward identity matches published value within 2σ (Catterall-Schaich, arXiv:1505.03135)
3. Pfaffian phase for SU(2) confirmed real positive (known result)
4. Computational cost characterized: wall-clock per RHMC trajectory at target parameters
5. Free-field limit of SU(2) code reproduces known analytical results

Plans:

- [ ] 01-01: [TBD — created during /gpd:plan-phase]

### Phase 2: Orbifold Implementation

**Goal:** Z_3 orbifold projection implemented, producing SU(2)^3 quiver with bi-fundamental matter; Q-exactness preserved
**Depends on:** Phase 1
**Requirements:** CODE-02, CODE-03, FEAS-02, VALD-08
**Contract coverage:** DLV-03 (modified code); REF-01 (CKKU construction); forbidden proxy: unvalidated code modifications
**Success Criteria:**

1. Gauge group decomposed from SU(6) into SU(2)^3 with correct quiver structure (3 nodes, bi-fundamental links)
2. Field content matches Z_3 orbifold daughter: N=1 SUSY with bi-fundamental chiral multiplets and cubic superpotential
3. Q-exactness verified: S = Q(Λ) holds algebraically after projection
4. Free-field limit (g → 0) reproduces analytical partition function for the quiver theory
5. Removing Z_3 projection recovers parent theory Phase 1 results (regression test)

Plans:

- [ ] 02-01: [TBD — created during /gpd:plan-phase]

### Phase 3: Sign Problem Feasibility (GO/NO-GO)

**Goal:** Pfaffian phase ⟨cos(α)⟩ measured for SU(2)^3 daughter on L=2; hard decision gate
**Depends on:** Phase 2
**Requirements:** FEAS-01, FEAS-03, FEAS-04, FEAS-05, FEAS-06
**Contract coverage:** OBS-02 (Ward identity violations); ACT-01 prerequisite; FP-01/FP-02 enforced (explicit sign tracking required)

**Decision Gate:**
- **GO:** ⟨cos(α)⟩ ≥ 0.1 on L=2 → proceed to Phase 4
- **CAUTION:** 0.05 ≤ ⟨cos(α)⟩ < 0.1 → assess with increased statistics
- **NO-GO:** ⟨cos(α)⟩ < 0.05 → pivot to different observable or method

**Success Criteria:**

1. Pfaffian computed exactly (not stochastically) on L=2 for SU(2)^3 daughter
2. ⟨cos(α)⟩ measured with ≥ 1000 configurations; GO/NO-GO determined at 3σ confidence
3. Pfaffian phase histogram produced (narrow = mild, broad = severe)
4. Flat direction stability verified: scalar eigenvalues bounded during MC evolution
5. Autocorrelation times and CG convergence characterized for the daughter theory

Plans:

- [ ] 03-01: [TBD — created during /gpd:plan-phase]

### Phase 4: Witten Index Computation

**Goal:** Witten index computed via exact Pfaffian ratio on L=2 and L=4 for SU(2)^3 daughter
**Depends on:** Phase 3 (GO)
**Requirements:** WIDX-01, WIDX-02, WIDX-03, VALD-07
**Contract coverage:** DLV-01 (Witten index values); DLV-04 (plots); OBS-01 (Witten index); ACT-02 (volume stability); FP-01/FP-02 enforced
**Success Criteria:**

1. Periodic fermion BCs implemented in temporal direction for Tr(-1)^F
2. Witten index W = Pf(M_PBC)/Pf(M_APBC) computed exactly on L=2 with full statistics
3. W on L=4 computed and compared to L=2 (volume independence check)
4. W close to an integer within statistical error (|W - round(W)| < 3σ)
5. β-independence checked at 2+ temporal extents

Plans:

- [ ] 04-01: [TBD — created during /gpd:plan-phase]

### Phase 5: Systematic Validation

**Goal:** Results validated through Ward identities, coupling/volume/β independence, and orbifold equivalence cross-check
**Depends on:** Phase 3 (GO), Phase 4
**Requirements:** VALD-01, VALD-02, VALD-03, VALD-05, VALD-06
**Contract coverage:** DLV-02 (Ward identity convergence); OBS-02 (Ward identity violations); ACT-01 (convergence check); ACT-03 (orbifold equivalence); REF-01/REF-02 used
**Success Criteria:**

1. Ward identity violations measured at 3+ lattice spacings; monotonic decrease toward zero confirmed
2. Witten index independent of 't Hooft coupling λ at 2+ values (coupling independence)
3. Z_3 center symmetry order parameter measured; orbifold equivalence status assessed
4. μ-independence of W verified (soft SUSY-breaking mass extrapolation)
5. Consistency between daughter W and parent N=4 SYM expectations via orbifold equivalence

Plans:

- [ ] 05-01: [TBD — created during /gpd:plan-phase]

### Phase 6: Analysis & Publication

**Goal:** Publication-quality plots, error budget, and manuscript draft
**Depends on:** Phase 4, Phase 5
**Requirements:** DLVR-01
**Contract coverage:** DLV-01, DLV-02, DLV-04 (all deliverables finalized); CLM-01 (novel computation claim established)
**Success Criteria:**

1. Complete error budget: statistical + systematic (volume, coupling, discretization)
2. Publication-quality plots: W vs. volume, Ward identity convergence vs. a, continuum extrapolation, Pfaffian phase distribution
3. Quantitative comparison to orbifold equivalence prediction with χ² or equivalent
4. Full reproducibility documentation (parameters, algorithms, code provenance)
5. Manuscript structured for target venue (JHEP/PRD/PoS Lattice)

Plans:

- [ ] 06-01: [TBD — created during /gpd:plan-phase]

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 1. Setup & Parent Validation | 0/TBD | Not started | - |
| 2. Orbifold Implementation | 0/TBD | Not started | - |
| 3. Sign Problem Feasibility | 0/TBD | Not started | - |
| 4. Witten Index Computation | 0/TBD | Not started | - |
| 5. Systematic Validation | 0/TBD | Not started | - |
| 6. Analysis & Publication | 0/TBD | Not started | - |

# Requirements: ML-Optimized Modular Bootstrap at Finite c

**Defined:** 2026-04-09
**Core Research Question:** Can ML-optimized modular-bootstrap searches in the finite-central-charge window 1 < c <= 8/7 reproduce or sharpen the established Virasoro gap constraints without overclaiming exact CFT existence?

## Primary Requirements

### Derivations

- [ ] **DERV-01**: Write the finite-c Virasoro torus-partition-function problem in a single convention set, including the definition of Delta_gap and the meaning of c
- [ ] **DERV-02**: Translate the 2016, 2023 integrality, 2023 geometry, and 2026 ML results into directly comparable observables and assumptions

### Calculations

- [ ] **CALC-01**: Extract the benchmark finite-c gap claims and c ranges from arXiv:1608.06241, arXiv:2308.08725, arXiv:2308.11692, and arXiv:2604.01275
- [ ] **CALC-02**: Specify the ML-search diagnostics that must accompany any candidate-spectrum statement, including truncation uncertainty and residual language

### Analysis

- [ ] **ANLY-01**: Identify what would count as genuine finite-c improvement over the 2016 benchmark and what would only be a proxy
- [ ] **ANLY-02**: Define how integrality and geometric constraints can act as non-ML cross-checks

### Validations

- [ ] **VALD-01**: Verify that every benchmark statement in the project is traceable to a cited source with aligned conventions
- [ ] **VALD-02**: Verify that any future candidate-spectrum claim is labeled as candidate unless a stronger proof standard is met
- [ ] **VALD-03**: Check that the convention ledger distinguishes central charge c from any unrelated unit or kinematic notation

## Follow-up Requirements

### Numerical Execution

- **NUMR-01**: Reproduce at least one published finite-c benchmark curve inside the workspace
- **NUMR-02**: Implement an optimizer or fast-bootstrap pipeline that can scan 1 < c <= 8/7 reproducibly
- **NUMR-03**: Test whether integrality can be imposed during, not after, the search

## Out of Scope

| Topic | Reason |
| ----- | ------ |
| Exact proof of new CFT existence in this pass | No reproduced numerical or analytic proof pipeline yet |
| Large-c black-hole constraints | Different asymptotic regime and different physical interpretation |
| Non-Virasoro chiral algebra classification | Separate bootstrap program |

## Accuracy and Validation Criteria

| Requirement | Accuracy Target | Validation Method |
| ----------- | --------------- | ----------------- |
| CALC-01 | Exact arXiv source alignment for every benchmark claim | Source-by-source literature comparison |
| CALC-02 | Diagnostic checklist captures all mandatory caveats | Human review against 2026 ML paper and 2023 non-ML checks |
| VALD-01 | Zero uncited benchmark statements in the final synthesis | Manual audit of each claim |
| VALD-02 | No exact-CFT language without decisive proof | Overclaim review |

## Contract Coverage

| Requirement | Decisive Output / Deliverable | Anchor / Benchmark / Reference | Prior Inputs / Baselines | False Progress To Reject |
| ----------- | ----------------------------- | ------------------------------ | ------------------------ | ------------------------ |
| DERV-01 | Convention ledger and scope note | arXiv:1608.06241 | `GPD/project_contract.json` | Mixing inconsistent definitions of c or Delta_gap |
| CALC-01 | Benchmark gap comparison note | arXiv:1608.06241, arXiv:2308.08725, arXiv:2308.11692, arXiv:2604.01275 | Literature abstracts and formulas | Uncited or convention-mismatched benchmark claims |
| ANLY-01 | False-progress checklist | arXiv:2604.01275 | 2016 and 2023 benchmark chain | Treating low loss as exact CFT evidence |
| VALD-02 | Overclaim audit | Entire anchor registry | Diagnostic checklist | Upgrading candidates to established theories |

## Traceability

| Requirement | Phase | Status |
| ----------- | ----- | ------ |
| DERV-01 | Phase 2: Finite-c benchmarks and conventions | Pending |
| DERV-02 | Phase 4: Candidate-spectrum and gap-constraint synthesis | Pending |
| CALC-01 | Phase 1: Literature and contract anchoring | Pending |
| CALC-02 | Phase 3: ML-optimized workflow design | Pending |
| ANLY-01 | Phase 4: Candidate-spectrum and gap-constraint synthesis | Pending |
| ANLY-02 | Phase 5: Validation, uncertainties, and continuation plan | Pending |
| VALD-01 | Phase 5: Validation, uncertainties, and continuation plan | Pending |
| VALD-02 | Phase 5: Validation, uncertainties, and continuation plan | Pending |
| VALD-03 | Phase 2: Finite-c benchmarks and conventions | Pending |

**Coverage:**

- Primary requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---

_Requirements defined: 2026-04-09_
_Last updated: 2026-04-09 after project initialization_

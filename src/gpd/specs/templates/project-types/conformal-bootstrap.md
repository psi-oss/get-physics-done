---
template_version: 1
---

# Conformal Bootstrap Project Template

Default project structure for conformal bootstrap and CFT data extraction: crossing equations, symmetry-sector bookkeeping, conformal blocks, semidefinite programming, extremal spectrum extraction, and analytic cross-checks.

---

## Default Roadmap Phases

```markdown
## Phases

- [ ] **Phase 1: Target CFT and Conventions** - Define the model, external operators, symmetry representations, and benchmark data
- [ ] **Phase 2: Crossing System Setup** - Write the OPE decomposition, crossing equations, and gap assumptions
- [ ] **Phase 3: Conformal Blocks and Numerical Pipeline** - Generate conformal blocks, derivative basis, and solver inputs
- [ ] **Phase 4: Bootstrap Bounds and Scans** - Compute exclusion curves, islands, or kinks and verify convergence
- [ ] **Phase 5: Spectrum Extraction and Analytic Cross-Checks** - Extract operator data and compare with analytic bootstrap, RG, or known exact results
- [ ] **Phase 6: Validation and Interpretation** - Verify crossing residuals, sector assignments, and physical interpretation
- [ ] **Phase 7: Paper Writing** - Draft manuscript presenting methods, bounds, and extracted CFT data

## Phase Details

### Phase 1: Target CFT and Conventions

**Goal:** Fix the target universality class or CFT, identify the correlators to study, and lock every normalization that affects crossing equations
**Success Criteria:**

1. [Target theory specified: e.g. 3D Ising, O(N), boundary CFT in AdS/CFT, or 2D minimal model]
2. [External operators and symmetry representations identified]
3. [Conventions fixed: block normalization, two-point function normalization, cross-ratios, spacetime dimension, spin parity]
4. [Benchmark data catalogued: known dimensions, protected operators, Monte Carlo or RG values, exact 2D data where applicable]

Plans:

- [ ] 01-01: [Survey the literature for the target CFT and identify the standard bootstrap setup]
- [ ] 01-02: [Lock conventions and benchmark values in NOTATION_GLOSSARY.md or CONVENTIONS.md]

### Phase 2: Crossing System Setup

**Goal:** Derive the full crossing system with correct sector bookkeeping and admissible gap assumptions
**Success Criteria:**

1. [Crossing equations written explicitly for the chosen correlator basis]
2. [OPE channels decomposed into the correct symmetry sectors]
3. [Identity operator included with the fixed normalization]
4. [Unitarity bounds and any imposed gaps stated with the correct dependence on spacetime dimension]
5. [Mixed-correlator assumptions documented when multiple external operators are used]

Plans:

- [ ] 02-01: [Write the crossing equations and OPE channel decomposition]
- [ ] 02-02: [Define gap assumptions and representation labels for each sector]

### Phase 3: Conformal Blocks and Numerical Pipeline

**Goal:** Build a reproducible pipeline for conformal blocks and semidefinite constraints
**Success Criteria:**

1. [Conformal blocks validated in the diagonal and OPE limits]
2. [Derivative basis around the crossing-symmetric point fixed with explicit `Lambda` values]
3. [Numerical pipeline documented: block tables, spin truncation, SDP input generation, solver precision]
4. [A reproducible configuration exists for every run that will be quoted later]

Plans:

- [ ] 03-01: [Generate or import conformal blocks and verify basic limits]
- [ ] 03-02: [Assemble SDP inputs and document precision / truncation settings]

### Phase 4: Bootstrap Bounds and Scans

**Goal:** Compute rigorous bounds or exclusion regions and verify they are numerically stable
**Success Criteria:**

1. [Bounds, islands, or kinks obtained for the chosen observables]
2. [Convergence in `Lambda` and solver precision demonstrated]
3. [Sensitivity to spin truncation or basis choice measured and bounded]
4. [Excluded and allowed regions clearly separated and recorded]

Plans:

- [ ] 04-01: [Run coarse scans to locate kinks, islands, or exclusion boundaries]
- [ ] 04-02: [Refine around the target region and perform convergence studies]

### Phase 5: Spectrum Extraction and Analytic Cross-Checks

**Goal:** Extract approximate operator data where appropriate and compare with complementary methods
**Success Criteria:**

1. [Extremal functional or equivalent extraction yields a stable approximate spectrum when applicable]
2. [Protected operators appear at their exact dimensions]
3. [Extracted low-lying dimensions and OPE coefficients agree with known benchmarks within quoted uncertainty]
4. [Analytic bootstrap, epsilon expansion, large-spin expansion, RG, or exact 2D results used as cross-checks where relevant]

Plans:

- [ ] 05-01: [Extract operator data from the boundary solution]
- [ ] 05-02: [Compare with analytic bootstrap, RG, Monte Carlo, or exact results]

### Phase 6: Validation and Interpretation

**Goal:** Establish that the result is physically and numerically trustworthy, and interpret what the bootstrap actually proved
**Success Criteria:**

1. [Crossing residuals or functional positivity checks are at the stated numerical tolerance]
2. [OPE convergence or truncation error is characterized honestly]
3. [Representation assignments for singlet, traceless, antisymmetric, current, and stress-tensor sectors are verified]
4. [The result is clearly labeled as rigorous bound, approximate spectrum extraction, or analytic estimate]
5. [Physical interpretation stated: critical exponents, universality class, holographic implication, or comparison to experiment/simulation]

Plans:

- [ ] 06-01: [Run final validation checks on crossing, sector bookkeeping, and protected operators]
- [ ] 06-02: [Translate CFT data into physical interpretation and literature comparison]

### Phase 7: Paper Writing

**Goal:** Produce publication-ready manuscript

See paper templates: `templates/paper/manuscript-outline.md`, `templates/paper/figure-tracker.md`, `templates/paper/cover-letter.md` for detailed paper artifacts.

**Success Criteria:**

1. [Manuscript complete with explicit conventions, solver settings, and convergence evidence]
2. [Figures clearly distinguish rigorous bounds from approximate spectrum extraction]
3. [Comparison with prior bootstrap, RG, Monte Carlo, or exact results clearly stated]
```

---

## Mode-Specific Phase Adjustments

### Explore Mode
- **Phase 1 expanded:** Compare single-correlator, mixed-correlator, analytic bootstrap, and RG approaches before locking the main route.
- **Phase 2 branches:** Try multiple correlator systems or symmetry assumptions in parallel if the literature is ambiguous.
- **Phase 4 expanded:** Scan multiple `Lambda` values and gap assumptions to understand how robust the island or kink is.
- **Extra phase option:** Add "Phase 4.5: Approach Comparison" if numerical and analytic bootstrap are both plausible primary methods.

### Exploit Mode
- **Phase 1 compressed:** Use the standard correlator setup already established in the literature.
- **Phase 3 focused:** Choose the existing block generator and SDP workflow without method comparison.
- **Phase 5 focused:** Extract only the operator data needed for the project goal; skip exploratory spectrum mining.
- **Skip Phase 7:** If results feed into a larger project, write `SUMMARY.md` instead of a full manuscript.

### Adaptive Mode
- Start in explore for Phases 1-3 if the correlator choice or symmetry sector is unsettled.
- Switch to exploit once the crossing system and numerical controls are validated.

---

## Standard Verification Checks for Conformal Bootstrap

See `references/verification/domains/verification-domain-mathematical-physics.md` for CFT/bootstrap verification and `references/verification/core/verification-core.md` for universal checks.

- Crossing equations include the identity operator and correct sector decomposition.
- Scalar, current, and stress-tensor dimensions satisfy the correct unitarity or protection conditions.
- Bounds converge under increases in `Lambda` and solver precision.
- Truncated OPE tests are labeled as diagnostics, not as rigorous proofs of crossing.
- Extracted spectra reproduce the crossing constraints to the quoted tolerance.

---

## Common Pitfalls for Bootstrap Projects

1. **Missing the identity operator:** A bootstrap system without the identity block is malformed from the start.
2. **Wrong spacetime dimension:** Unitarity bounds and conformal blocks depend on `d`; reusing a 4D setup for a 3D problem is a real failure mode.
3. **Sector misassignment:** Singlet, traceless-symmetric, antisymmetric, current, and stress-tensor sectors cannot be swapped without changing the physics.
4. **Normalization drift:** Different conformal block or two-point normalization conventions change OPE coefficients and can silently corrupt comparisons.
5. **No `Lambda` convergence study:** A bound or island quoted at one derivative order is not enough for a serious claim.
6. **Confusing rigorous bounds with extracted spectra:** Exclusion regions are rigorous; extremal-functional spectra are approximate.
7. **Treating a truncated OPE sum as a proof of crossing:** It is only a convergence diagnostic unless the full bootstrap machinery is used.
8. **Ignoring protected operators:** The current and stress tensor provide the strongest low-lying consistency checks in many systems.

---

## Default Conventions

See `templates/conventions.md` for the full conventions ledger template. Bootstrap projects should populate:

- **Spacetime dimension:** `d = 2`, `3`, `4`, etc.
- **External operators:** names, symmetry representations, and assumed ordering in correlators
- **Cross-ratio convention:** `(u, v)` and `(z, zbar)` definitions
- **Conformal block convention:** global / Virasoro / superconformal, plus normalization choice
- **Two-point normalization:** normalization fixing the identity OPE coefficient
- **Derivative order:** `Lambda`, derivative basis, and crossing-symmetric expansion point
- **Spin truncation:** which spins are included explicitly and what asymptotic assumptions are made
- **Gap assumptions:** sector-by-sector lower bounds or isolated operators
- **Solver precision:** arbitrary precision settings, stopping thresholds, and reproducibility notes

---

## Computational Environment

**Core tools:**

- `SDPB` - Standard semidefinite-programming solver for numerical bootstrap
- `pyCFTBoot` or equivalent scripts - Generate bootstrap functionals and SDP input data
- `mpmath` / `numpy` / `scipy` - High-precision numerics, interpolation, diagnostic checks
- `matplotlib` - Exclusion curves, islands, and convergence plots

**Optional complementary tools:**

- Symbolic algebra for analytic bootstrap manipulations
- Cluster or batch-job tooling for large `Lambda` scans
- Reproducible config files capturing gaps, sectors, precision, and scan ranges

**Setup:**

```bash
pip install numpy scipy mpmath matplotlib
# Install SDPB separately according to your platform.
```

---

## Bibliography Seeds

Every conformal bootstrap project should start from a small canonical set of references:

| Reference | What it provides | When to use |
|-----------|------------------|-------------|
| Simmons-Duffin, *The Conformal Bootstrap* | Standard modern overview of bootstrap logic and numerics | First orientation and conventions |
| Poland, Rychkov, Vichi, *The Conformal Bootstrap: Theory, Numerical Techniques, and Applications* | Broad review of methods and applications | Method selection and literature map |
| Simmons-Duffin, *A Semidefinite Program Solver for the Conformal Bootstrap* | SDPB methodology and numerical precision issues | Numerical implementation |
| Kos, Poland, Simmons-Duffin, Vichi (3D Ising / O(N) papers) | Canonical benchmark islands and precision data | Benchmark comparisons |
| Caron-Huot, Lorentzian inversion-formula papers | Analytic bootstrap cross-checks at large spin | Analytic comparison |


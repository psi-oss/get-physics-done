---
template_version: 1
purpose: Project-wide uncertainty ledger tracking all numerical quantities and their uncertainties
---

# Uncertainty Budget Template

Template for `.gpd/analysis/UNCERTAINTY-BUDGET.md` -- tracks all numerical quantities, their uncertainties, and how uncertainties propagate through multi-step calculations.

**Purpose:** Central registry of uncertainties across the research project. Prevents silent accumulation of untracked errors, documents which uncertainty dominates the final result, and provides propagation rules for combining quantities across phases.

**Relationship to other files:**

- `PARAMETERS.md` lists parameter values and systematic uncertainties; UNCERTAINTY-BUDGET.md tracks how those uncertainties propagate through calculations
- `CONVENTIONS.md` records the unit system; all uncertainty values here must be in the project's convention
- Phase SUMMARY.md files report per-phase uncertainties; UNCERTAINTY-BUDGET.md aggregates them project-wide
- `state.json` field `propagated_uncertainties` mirrors a compact subset of this table for quick access

---

## File Template

```markdown
# Uncertainty Budget

**Project**: [PROJECT_NAME]
**Last Updated**: [YYYY-MM-DD]

## Summary

- Total tracked quantities: [N]
- Quantities with verified uncertainties: [M]
- Dominant uncertainty source: [description]

## Uncertainty Registry

| ID | Quantity | Symbol | Value | Uncertainty | Type | Source Phase | Propagation | Downstream | Verified |
|----|----------|--------|-------|-------------|------|-------------|-------------|------------|----------|
| U-01 | [name] | [symbol] | [val] | [+/- delta] | stat/sys/trunc | Phase [N] | [formula] | Phase [M], [K] | [yes/no] |

### Type Classification

- **statistical** (stat): From finite sampling, Monte Carlo, measurement noise
- **systematic** (sys): From model assumptions, approximations, calibration
- **truncation** (trunc): From series truncation, basis set incompleteness, grid spacing

## Propagation Rules

When quantities are combined, uncertainties propagate as:

### Independent Uncertainties

- Sum/difference: delta(A +/- B) = sqrt(delta_A^2 + delta_B^2)
- Product/ratio: delta(A * B) / |A * B| = sqrt((delta_A / A)^2 + (delta_B / B)^2)
- Power: delta(A^n) = |n| * A^(n-1) * delta_A

### Correlated Uncertainties

| Quantity A | Quantity B | Correlation | Source |
|-----------|-----------|-------------|--------|
| [A] | [B] | [rho_AB] | [shared approximation/data] |

## Dominant Uncertainty Analysis

Rank quantities by their impact on final results:

| Final Result | Dominant Uncertainty | Contribution | Phase |
|-------------|---------------------|-------------|-------|
| [result] | [quantity] | [% of total] | [N] |
```

<lifecycle>

**Creation:** After ROADMAP.md, when first numerical quantities appear

- Initialize with fundamental parameter uncertainties from PARAMETERS.md
- Set up uncertainty IDs (U-01, U-02, ...) matching result IDs where applicable
- Mark all as unverified initially

**Appending:** After each phase that produces numerical results

- Add new quantities from phase SUMMARY.md
- Update propagation formulas when quantities are combined
- Recalculate dominant uncertainty analysis
- Update `propagated_uncertainties` in state.json

**Reading:** By executor and verifier during phase work

- Check that incoming quantities carry their uncertainties
- Verify propagation is consistent with the rules documented here
- Flag any quantity used without an uncertainty estimate

**Reading:** By consistency checker at milestone audits

- Verify all intermediate results in state.json have corresponding uncertainty entries
- Check that correlated quantities are identified
- Verify dominant uncertainty analysis is up to date

</lifecycle>

<guidelines>

**What belongs in UNCERTAINTY-BUDGET.md:**

- Every numerical quantity that carries an uncertainty
- Propagation formulas showing how uncertainties combine
- Correlation information between quantities sharing common sources
- Dominant uncertainty ranking for final results
- Verification status of each uncertainty estimate

**What does NOT belong here:**

- Derivation details (those live in phase SUMMARY.md files)
- Parameter values without uncertainties (those go in PARAMETERS.md)
- Notation definitions (those go in NOTATION_GLOSSARY.md)
- Systematic uncertainty sources without quantification (those go in PARAMETERS.md Systematic Uncertainties table)

**When filling this template:**

- Start by listing all quantities from PARAMETERS.md that have uncertainties
- For each calculation, write the explicit propagation formula
- Identify correlated quantities early -- shared approximations or shared data are the usual sources
- Update the dominant uncertainty analysis whenever a new result is produced
- The `/gpd:error-propagation` workflow automates tracking across phases
- The `/gpd:sensitivity-analysis` workflow identifies which parameters matter most

**Why uncertainty tracking matters:**

- Prevents claiming precision that doesn't exist
- Identifies where to invest effort (reduce the dominant uncertainty, not the subdominant one)
- Enables honest error bars on final results
- Catches sign errors and factor-of-two mistakes via consistency checks
- Required for any publication-quality physics result

</guidelines>

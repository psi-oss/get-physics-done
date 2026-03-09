# VALIDATION.md Template (methodology focus)

````markdown
# Validation and Cross-Checks

**Analysis Date:** [YYYY-MM-DD]

## Analytic Cross-Checks

**Limiting Cases Verified:**

- [Limit]: [Expected result] -> [Obtained result]: [Match? Yes/No]
  - File: `[path]`

**Limiting Cases NOT Verified:**

- [Limit]: [What should be checked, expected behavior]

**Symmetry Checks:**

- [Symmetry]: [Ward identity / Selection rule verified?]
  - File: `[path]`

**Sum Rules / Consistency Relations:**

- [Relation]: [Satisfied?]
  - File: `[path]`

## Numerical Validation

**Convergence Tests:**

- [Computation]: [Converged? How tested?]
  - Script: `[path]`
  - Grid/parameter study: [Details]

**Stability Analysis:**

- [Computation]: [Stable under parameter variation?]
  - Script: `[path]`

**Precision and Error Control:**

- [Computation]: [Error estimate, tolerance used]
  - File: `[path]`

## Comparison with Literature

**Reproduced Results:**

- [Result from Ref. X]: [Reproduced? Agreement level?]
  - Comparison in: `[path]`

**Discrepancies:**

- [Result]: [What disagrees, possible reasons]
  - File: `[path]`

## Internal Consistency

**Cross-Method Verification:**

- [Quantity computed two ways]: [Agreement?]
  - Method A: `[path]`
  - Method B: `[path]`

**Self-Consistency:**

- [e.g., "Detailed balance satisfied"]: [Checked?]
  - File: `[path]`

## Thermodynamic Consistency (if applicable)

**Maxwell Relations:**

- [Relation]: [Verified? e.g., (dS/dV)_T = (dP/dT)_V]
  - File: `[path]`

**Response Function Positivity:**

- Specific heat C_v > 0: [Checked?]
- Susceptibility chi > 0: [Checked?]
- Compressibility kappa > 0: [Checked?]

**Fluctuation-Dissipation:**

- [FDT relation]: [Verified?]
  - File: `[path]`

## Anomalies and Topological Properties (if applicable)

**Anomaly Checks:**

- [Anomaly type]: [Present? Correctly accounted for? Anomaly coefficient?]
  - File: `[path]`

**Anomaly Matching:**

- UV description <-> IR description: [Matching verified?]
  - File: `[path]`

**Topological Invariants:**

- [Invariant]: [Value (must be integer), method of computation]
  - File: `[path]`

## Test Suite

**Existing Tests:**

- `[test file]`: [What it tests]
  - Coverage: [What aspects are covered]

**Run Commands:**

```bash
[command]              # Run all tests
[command]              # Run specific test suite
[command]              # Run with verbose output
```

**Test Patterns:**

```python
[Show actual test pattern from the project]
```

**Missing Tests:**

- [What should be tested but isn't]

## Reproducibility

**Random Seeds:**

- [Fixed / Not fixed]: [Where set]
  - File: `[path]`

**Platform Dependence:**

- [Any known platform-dependent results]

**Version Pinning:**

- [Are dependency versions pinned?]
  - File: `[path]`

---

_Validation analysis: [date]_
````

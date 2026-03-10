# CONVENTIONS.md Template (methodology focus)

```markdown
# Derivation Quality Analysis

**Analysis Date:** [YYYY-MM-DD]

## Derivation Inventory

**[Derivation Name]:**
- Result: [Key equation derived]
- File: `[path]` (Sec. X, Eqs. Y-Z)
- Method: [e.g., Variational, perturbative, exact, numerical]
- Starting point: [What is assumed/given]
- Key steps: [Critical intermediate steps]
- Status: [Complete / Incomplete / Sketch only]

## Approximations Made

**[Approximation Name]:**
- What is neglected: [Specific terms or effects]
- Justification given: [Quote or summarize the stated reason]
- Justification quality: [Strong / Adequate / Weak / Missing]
- Parameter controlling approximation: [e.g., "epsilon = m/M << 1"]
- Estimated error: [Order of neglected terms, if stated]
- File: `[path]` (near Eq. X)

## Assumptions Catalog

**Explicit Assumptions:**
- [Assumption]: [Where stated, what depends on it]
  - File: `[path]`

**Implicit Assumptions:**
- [Assumption]: [Not stated but used, where it enters]
  - File: `[path]`
  - Risk: [What breaks if this assumption fails]

## Mathematical Rigor Assessment

**[Derivation/Section]:**
- Rigor level: [Rigorous / Physicist-standard / Heuristic / Hand-wavy]
- Issues:
  - [Specific issue, e.g., "interchange of limit and integral not justified"]
  - [e.g., "convergence of series assumed but not proven"]
- File: `[path]`

## Dimensional Analysis

**Consistency Checks:**
- [Equation]: [Dimensionally consistent? Units check?]
  - File: `[path]` (Eq. X)

**Dimensional Anomalies:**
- [Issue]: [Where dimensions appear inconsistent or unclear]
  - File: `[path]`

## Sign and Factor Conventions

**Sign Choices:**
- [Convention]: [e.g., "Metric signature (-,+,+,+)", "Fourier transform with e^{-iwt}"]
  - Consistent throughout: [Yes / No - specify conflicts]

**Factor Tracking:**
- [Factors of 2pi, factors of i, etc.]: [Tracked correctly?]
  - Known issues: `[path]` (Eq. X)

## Notation Consistency

**Consistent Usage:**
- [Symbol]: [Always means the same thing? Any overloading?]

**Conflicts:**
- [Symbol conflict]: [e.g., "k used for both wavevector and Boltzmann constant in different sections"]
  - Files: `[path1]`, `[path2]`

---

*Derivation quality analysis: [date]*
```

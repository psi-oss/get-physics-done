---
template_version: 1
type: experimental-comparison
---

# Experimental Comparison Template

Template for systematic comparison of theoretical predictions with experimental or observational data.

---

## File Template

```markdown
---
comparison_verdicts:
  - subject_id: claim-id
    subject_kind: claim|deliverable|acceptance_test|reference|artifact|other
    subject_role: decisive|supporting|supplemental
    reference_id: ref-id
    comparison_kind: benchmark|prior_work|experiment|cross_method|baseline
    metric: relative_error | chi2_ndof | pull
    threshold: "<= 2 sigma"
    verdict: pass | tension | fail | inconclusive
    recommended_action: "[what to do next]"
---

# Experimental Comparison: [Observable/Quantity]

**Date:** [YYYY-MM-DD]
**Theory source:** [Phase/derivation that produced the prediction]
**Data sources:** [Experiments/observations being compared against]

## Data Source Metadata

| Source | Experiment/Observatory | Year | Observable | Conditions | Systematic Uncertainties | Reference |
|--------|----------------------|------|------------|------------|-------------------------|-----------|
| [label] | [name] | [year] | [what was measured] | [energy, temperature, etc.] | [dominant systematics] | [paper] |
| [label] | [name] | [year] | [what was measured] | [conditions] | [dominant systematics] | [paper] |

### Data Quality Notes

- [Source 1]: [Any known issues, retractions, or updates to the data]
- [Source 2]: [Whether data is published or preliminary]

## Unit Conversion Checklist

Before comparing, verify all quantities are in consistent units:

- [ ] Energy units: [GeV / MeV / eV / J / K] — conversion factor: [value]
- [ ] Length units: [fm / nm / Angstrom / m] — conversion factor: [value]
- [ ] Cross section units: [pb / fb / mb / cm^2] — conversion factor: [value]
- [ ] Temperature units: [K / J / eV] — k_B factor: [value]
- [ ] Dimensionless ratios: [verify numerator and denominator use same conventions]
- [ ] Natural units restoration: [which factors of hbar, c, k_B need restoring]

## Comparison Table

| Quantity | Theory | Experiment | Exp. Uncertainty | Theory Uncertainty | Pull (sigma) | Status |
|----------|--------|------------|------------------|-------------------|--------------|--------|
| [name] | [value] | [value] | [stat +/- sys] | [truncation + param] | [|th-exp|/sigma_combined] | [agree/tension/disagree] |
| [name] | [value] | [value] | [stat +/- sys] | [truncation + param] | [pull] | [status] |

**Pull definition:** pull = |theory - experiment| / sqrt(sigma_theory^2 + sigma_exp^2)

**Status classification:**
- **agree**: pull < 2
- **tension**: 2 <= pull < 3
- **disagree**: pull >= 3

## Statistical Analysis

### Global Fit Quality

- **Chi-squared:** [value]
- **Degrees of freedom:** [N]
- **Chi-squared / DOF:** [value]
- **p-value:** [value]
- **Interpretation:** [Good fit / marginal / poor fit]

### Individual Pulls

| Observable | Pull (sigma) | Direction | Systematic dominated? |
|-----------|-------------|-----------|----------------------|
| [name] | [value] | [theory above/below] | [yes/no] |

### Correlations

[If experimental data has correlated uncertainties, document the correlation matrix or its source]

## Systematic Corrections

| Correction | Magnitude | Applied to | Method | Reference |
|-----------|-----------|-----------|--------|-----------|
| [e.g., Finite-size effects] | [estimate] | [theory] | [extrapolation method] | [source] |
| [e.g., Detector acceptance] | [estimate] | [experiment] | [simulation] | [source] |
| [e.g., Higher-order terms] | [estimate] | [theory] | [scale variation / known N+1 LO] | [source] |
| [e.g., Continuum limit] | [estimate] | [theory/lattice] | [a -> 0 extrapolation] | [source] |

## Discrepancy Classification

For any tension or disagreement (pull >= 2), classify the root cause:

| Discrepancy | Pull | Root Cause Hierarchy | Resolution |
|-------------|------|---------------------|------------|
| [observable] | [sigma] | 1. Unit/convention error? [checked: yes/no] | [action] |
| | | 2. Missing correction? [e.g., radiative, finite-size] | [action] |
| | | 3. Approximation breakdown? [validity check] | [action] |
| | | 4. Experimental issue? [reanalysis, updated data] | [action] |
| | | 5. Genuine new physics? [only after 1-4 exhausted] | [action] |

### Root Cause Hierarchy

Always investigate discrepancies in this order:

1. **Convention/unit mismatch** — Most common. Check every conversion factor.
2. **Missing systematic correction** — Radiative corrections, finite-size, continuum limit, detector effects.
3. **Approximation validity** — Is the expansion parameter actually small? Are we in the right regime?
4. **Experimental reanalysis** — Has the data been updated? Are there known issues?
5. **New physics** — Only conclude this after exhausting 1-4. Extraordinary claims require extraordinary evidence.

## Figures

### Theory vs Experiment Plot

[Plot with theory prediction (band for uncertainty) overlaid on experimental data points (with error bars). Include residual plot below.]

### Pull Distribution

[Histogram of pulls. Should be approximately Gaussian with mean 0 and width 1 for a good fit.]

## Summary

**Overall agreement:** [Excellent / Good / Fair / Poor]
**Key tensions:** [List any pulls > 2 sigma]
**Missing data:** [What experimental measurements would most constrain the theory]
**Recommended actions:** [What to do about any disagreements]

---

_Comparison date: [YYYY-MM-DD]_
_Theory: [phase/version]_
_Data: [sources with years]_
```

---

## Guidelines

**Before comparing:**
- Verify unit conventions match between theory and experiment
- Check whether experimental data has been superseded by newer measurements
- Identify whether experimental uncertainties are statistical, systematic, or combined
- Determine if experimental data has correlated uncertainties

**Uncertainty combination:**
- Theory uncertainty: truncation error (scale variation, higher-order estimate) + parametric uncertainty
- Experimental uncertainty: statistical + systematic (add in quadrature if independent)
- Combined for pull: sqrt(sigma_th^2 + sigma_exp^2) only if independent

**Common mistakes:**
- Comparing theory at one loop with experiment that requires two loops for meaningful comparison
- Ignoring correlated experimental uncertainties in chi-squared calculation
- Using outdated PDG/experimental values when updated measurements exist
- Forgetting radiative corrections when comparing with precision data
- Comparing lattice results at finite spacing/volume with continuum experimental values

When the comparison is decisive for a contract-backed claim or deliverable, the `comparison_verdicts` block is required. It is the machine-readable answer to "did the decisive output pass its benchmark?".

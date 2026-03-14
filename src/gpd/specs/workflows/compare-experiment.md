<purpose>
Systematically compare theoretical predictions with experimental or observational data. Handles unit conversion, uncertainty propagation, statistical testing, and discrepancy analysis.

Called from /gpd:compare-experiment command. Produces COMPARISON.md with quantified agreement metrics.

Agreement between theory and experiment must be quantified. "Looks about right" is not physics. The comparison must state: (1) what decisive output or contract target was predicted, (2) what was measured, (3) what the uncertainties are on both sides, (4) whether the agreement is statistically significant, and (5) if not, what the discrepancy tells us.
</purpose>

<required_reading>
Read these files using the file_read tool:
- {GPD_INSTALL_DIR}/templates/paper/experimental-comparison.md -- Template for systematic theory-experiment comparison (data source metadata, unit conversion checklist, pull calculation, discrepancy classification, root cause hierarchy)
</required_reading>

<process>

## 0. Load Project Context

Load project state and conventions to ensure correct unit systems and sign conventions:

- Run:

```bash
INIT=$(gpd init progress --include state)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

- Parse JSON for: `commit_docs`, `state_exists`, `project_exists`, `current_phase`
- **If `state_exists` is true:** Read `.gpd/state.json` to extract `convention_lock` for unit system, metric signature, and Fourier conventions. Extract active approximations and their validity ranges from state. Load `intermediate_results` from state for any previously computed quantities.
- **If `state_exists` is false** (standalone usage): Proceed with explicit convention declarations required from user via ask_user (unit system, sign conventions, normalization)

Convention context is critical for theory-experiment comparison: unit mismatches and convention mismatches are the two most common sources of discrepancy.

**Convention verification** (if project exists):

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — unit mismatches between theory and experiment are the #1 source of false discrepancies"
  echo "$CONV_CHECK"
fi
```

## 1. Identify What to Compare

If the project is contract-backed, first resolve the comparison target against the approved contract:
- `subject_id`
- `subject_kind` (`claim`, `deliverable`, `acceptance_test`, or artifact)
- `subject_role` (`decisive`, `supporting`, `supplemental`)
- `reference_id` for the benchmark / prior-work / data anchor
- the pass condition or tolerance that makes this comparison decisive

Do not write a generic comparison report without this mapping when a decisive comparison target exists.

### 1a. Theoretical predictions

For each prediction, establish:

- **Quantity predicted:** Name, symbol, definition
- **Predicted value or functional form:** Expression or numerical table
- **Theoretical uncertainties:** From truncation, approximation, numerical precision
- **Conventions:** Units, normalization, sign conventions
- **Regime of validity:** Where the prediction is expected to hold

### 1b. Experimental data

For each measurement, establish:

- **Quantity measured:** Name, definition, what detector/apparatus
- **Measured values:** Central values with error bars
- **Statistical uncertainties:** From measurement statistics
- **Systematic uncertainties:** From calibration, background, modeling
- **Conventions:** Units, normalization, binning, acceptance corrections
- **Conditions:** Temperature, pressure, energy, other experimental parameters

Use ask_user if data source is ambiguous:

1. **Data source** -- Published paper | Our own measurements | Database (PDG, NIST, etc.) | Simulation (lattice, MD, etc.)
2. **Data format** -- CSV/table | Digitized from plot | API/database query | File path
3. **Uncertainty treatment** -- Statistical only | Statistical + systematic (separate) | Combined | Correlated uncertainties

## 2. Unit Conversion and Convention Matching

**This step catches the most common theory-experiment comparison errors.**

### 2a. Unit alignment

Ensure theory and experiment use the same units:

```python
# Common unit conversion pitfalls in physics:
# - eV vs Kelvin: 1 eV = 11604.5 K
# - eV vs cm^{-1}: 1 eV = 8065.54 cm^{-1}
# - Gaussian vs SI electromagnetism: factor of 4*pi*epsilon_0
# - Natural units to SI: restore factors of hbar, c, k_B
# - Energy vs frequency: E = hbar * omega (not h * nu !)
# - Cross-section: barn (1e-24 cm^2) vs fm^2 (1e-26 cm^2) vs GeV^{-2}
# - Decay width vs lifetime: Gamma = hbar / tau
```

Document every conversion applied.

### 2b. Convention matching

Check that theory and experiment use the same conventions:

| Convention               | Theory       | Experiment   | Conversion needed? |
| ------------------------ | ------------ | ------------ | ------------------ |
| Normalization            | {convention} | {convention} | {yes/no}           |
| Phase convention         | {convention} | {convention} | {yes/no}           |
| Fourier transform        | {convention} | {convention} | {yes/no}           |
| Cross-section definition | {convention} | {convention} | {yes/no}           |

### 2c. Acceptance and efficiency corrections

Experimental data often includes detector acceptance and efficiency:

- Is the data already corrected? (Unfolded to particle level)
- If not: apply theory-side smearing/cuts to match detector level
- Document what corrections are applied on which side

## 3. Perform the Comparison

### 3a. Point-by-point comparison

```python
import numpy as np

# For each data point:
for i in range(len(data)):
    x_exp = data[i]['x']
    y_exp = data[i]['y']
    dy_exp = data[i]['uncertainty']  # total: stat + syst combined
    y_theory = theory_prediction(x_exp)
    dy_theory = theory_uncertainty(x_exp)

    # Pull: (theory - experiment) / combined_uncertainty
    dy_combined = np.sqrt(dy_exp**2 + dy_theory**2)
    pull = (y_theory - y_exp) / dy_combined

    print(f"x={x_exp:.4f}  exp={y_exp:.6f}+/-{dy_exp:.6f}  "
          f"theory={y_theory:.6f}+/-{dy_theory:.6f}  pull={pull:.2f}")
```

### 3b. Global fit quality

```python
# Chi-squared test
chi2 = 0
for i in range(len(data)):
    dy_combined = np.sqrt(data[i]['uncertainty']**2 + theory_uncertainty(data[i]['x'])**2)
    chi2 += ((theory_prediction(data[i]['x']) - data[i]['y']) / dy_combined)**2

ndof = len(data) - n_free_params
chi2_reduced = chi2 / ndof
p_value = 1 - scipy.stats.chi2.cdf(chi2, ndof)

print(f"chi2/ndof = {chi2:.1f}/{ndof} = {chi2_reduced:.2f}")
print(f"p-value = {p_value:.4f}")
```

### 3c. Statistical interpretation

| chi2/ndof | p-value | Interpretation                             |
| --------- | ------- | ------------------------------------------ |
| ~ 1       | > 0.05  | Good agreement                             |
| >> 1      | < 0.01  | Significant discrepancy                    |
| << 1      | > 0.99  | Overfitting or overestimated uncertainties |

### 3d. Residual analysis

```python
# Check for systematic patterns in residuals:
# - Trending residuals suggest missing physics (wrong functional form)
# - Oscillating residuals suggest discretization artifacts
# - Constant offset suggests normalization error
# - Growing residuals suggest wrong scaling / missing terms
```

## 4. Discrepancy Analysis

If the comparison shows significant disagreement:

### 4a. Classify the discrepancy

| Type                | Signature                           | Likely Cause                                                      |
| ------------------- | ----------------------------------- | ----------------------------------------------------------------- |
| Constant offset     | All pulls have same sign            | Normalization error, missing constant term, unit conversion error |
| Constant factor     | Ratio theory/experiment is constant | Missing factor of 2, pi, or convention mismatch                   |
| Wrong slope         | Discrepancy grows with parameter    | Wrong power law, missing logarithmic corrections                  |
| Wrong curvature     | Discrepancy is quadratic            | Missing next-order correction                                     |
| Localized           | Discrepancy only in one region      | Approximation breakdown, phase transition, resonance              |
| Oscillatory         | Periodic discrepancy pattern        | Interference effect, aliasing, finite-size oscillation            |
| Statistical scatter | Random, no pattern                  | Underestimated uncertainties                                      |

### 4b. Root cause investigation

1. **Check units again** -- Most theory-experiment discrepancies are unit errors
2. **Check conventions** -- Second most common: different normalization or phase convention
3. **Check data processing** -- Binning, acceptance, background subtraction
4. **Check approximations** -- Is the theoretical prediction valid in this regime?
5. **Check for missing physics** -- Higher-order corrections, finite-size effects, interactions neglected

### 4c. Quantify the tension

```python
# Number of sigma tension:
tension_sigma = abs(theory_central - exp_central) / np.sqrt(theory_unc**2 + exp_unc**2)

# Interpretation:
# < 1 sigma: consistent
# 1-2 sigma: mild tension, not significant
# 2-3 sigma: interesting tension, warrants investigation
# 3-5 sigma: significant discrepancy
# > 5 sigma: discovery-level discrepancy
```

## 5. Generate Comparison Report

Write COMPARISON.md:

```markdown
---
date: { YYYY-MM-DD }
theory_source: { derivation/computation path }
data_source: { experiment/measurement reference }
overall_agreement: good | tension | discrepancy
chi2_ndof: { value }
p_value: { value }
max_tension_sigma: { value }
comparison_verdicts:
  - subject_id: claim-id
    subject_kind: claim|deliverable|acceptance_test|artifact
    subject_role: decisive|supporting|supplemental
    reference_id: ref-id
    comparison_kind: benchmark|prior_work|experiment|cross_method|baseline
    metric: chi2_ndof | relative_error | pull
    threshold: "<= 2 sigma"
    verdict: pass | tension | fail | inconclusive
    recommended_action: { what to do next }
---

# Theory-Experiment Comparison

## Quantities Compared

| Quantity | Theory          | Experiment      | Units   |
| -------- | --------------- | --------------- | ------- |
| {name}   | {value +/- unc} | {value +/- unc} | {units} |

## Unit Conversions Applied

{Document all conversions}

## Convention Matching

{Document all convention alignments}

## Point-by-Point Comparison

| x   | y_theory | dy_theory | y_exp   | dy_exp | Pull   | Status       |
| --- | -------- | --------- | ------- | ------ | ------ | ------------ |
| {x} | {value}  | {unc}     | {value} | {unc}  | {pull} | {OK/TENSION} |

## Global Fit Quality

- chi2 / ndof = {value}
- p-value = {value}
- Assessment: {good agreement / tension / discrepancy}

## Residual Analysis

{Systematic patterns, trends, outliers}

## Discrepancy Analysis (if applicable)

- **Type:** {classification}
- **Magnitude:** {N sigma}
- **Likely cause:** {root cause analysis}
- **Resolution path:** {what to investigate}

## Figures

- `{path}`: Theory vs experiment overlay
- `{path}`: Pull distribution
- `{path}`: Residuals vs parameter

## Conclusions

{Summary of agreement/disagreement and its significance}
```

The `comparison_verdicts` block is the authoritative machine-readable ledger. The tables and prose explain it; they do not replace it.

Save to:

- **Phase-scoped** (if running within a phase context and `phase_dir` is set): `${phase_dir}/COMPARISON-{slug}.md`
- **Standalone** (no phase context):

```bash
mkdir -p .gpd/analysis
```

Write to `.gpd/analysis/comparison-{slug}.md`

## 6. Generate Comparison Figures

Create scripts for standard comparison plots:

1. **Theory vs experiment overlay** -- data points with error bars, theory curve with uncertainty band
2. **Pull distribution** -- histogram of (theory-exp)/sigma, should be standard normal
3. **Residual plot** -- (theory-exp) vs parameter, looking for systematic trends
4. **Ratio plot** -- theory/experiment vs parameter (for normalizations)

Write final comparison figures, tables, and helper scripts to stable workspace roots. Default to `artifacts/comparisons/{slug}/` unless the project already has a clearer durable home such as `figures/`, `data/`, or `scripts/`. Do not place final comparison figures, tables, or scripts under `.gpd/`.

## 7. Present Results and Route

If good agreement:

```
## Theory-Experiment Comparison: Good Agreement

chi2/ndof = {value}, p-value = {value}
Maximum tension: {N} sigma at {parameter value}

Theory predictions are consistent with experimental data.
Ready for: `/gpd:write-paper` (Results section)
```

If discrepancy:

```
## Theory-Experiment Comparison: {N}-sigma Discrepancy Found

chi2/ndof = {value}, p-value = {value}

### Discrepancy Details
{Classification and magnitude}

### Suggested Investigation
- `/gpd:debug` -- investigate the discrepancy
- `/gpd:limiting-cases` -- check if the prediction is valid in this regime
- Check experimental systematic uncertainties
- Compute next-order theoretical corrections
```

## 8. Commit Comparison Report

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${COMPARISON_OUTPUT_PATH}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: theory-experiment comparison for {slug}" \
  --files "${COMPARISON_OUTPUT_PATH}"
```

Where `${COMPARISON_OUTPUT_PATH}` is the path chosen in step 5 (phase-scoped or standalone).

</process>

<output>
COMPARISON.md written to `.gpd/analysis/comparison-{slug}.md` with full quantified comparison.
</output>

<success_criteria>

- [ ] Theoretical predictions identified with uncertainties
- [ ] Experimental data loaded with uncertainties (stat + syst)
- [ ] Unit conversions documented and applied
- [ ] Convention matching verified
- [ ] Point-by-point comparison performed with pulls
- [ ] Global chi-squared computed with p-value
- [ ] Residual analysis performed for systematic patterns
- [ ] Discrepancies classified and quantified (in sigma)
- [ ] Root cause analysis for any significant discrepancy
- [ ] Comparison report generated
- [ ] Contract-backed comparisons include `comparison_verdicts` keyed by subject ID / reference ID
- [ ] Comparison figures generated (or scripts provided)
- [ ] Comparison report committed (if commit_docs enabled)
- [ ] Results routed appropriately (paper writing or debugging)
</success_criteria>

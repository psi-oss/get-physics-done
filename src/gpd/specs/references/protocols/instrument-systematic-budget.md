---
load_when:
  - "systematic uncertainty"
  - "calibration"
  - "instrument uncertainty"
  - "noise floor"
  - "gain stability"
  - "drift"
  - "uncertainty budget"
  - "GUM"
  - "Type A"
  - "Type B"
  - "calibration traceability"
  - "measurement uncertainty"
  - "instrument error"
  - "systematic error budget"
tier: 2
context_cost: medium
---

# Instrument Systematic Budget Protocol

Every experimental measurement carries systematic uncertainties from the instrument, the environment, and the measurement procedure itself. Building a rigorous uncertainty budget is the discipline of accounting for all these contributions, quantifying each one, understanding their correlations, and combining them into a total systematic uncertainty. The GUM (Guide to the Expression of Uncertainty in Measurement, JCGM 100:2008) is the international standard for this process.

**Core discipline:** A measurement without a complete uncertainty budget is not a measurement — it is a number. The difference between "we measured the cross section to 3%" and "we think the cross section is about this" is whether someone systematically identified, quantified, and combined every source of uncertainty. LLMs are dangerous here because they tend to list a few obvious systematics while missing subtle ones that dominate the error budget.

## Related Protocols

- `statistical-inference.md` — Frequentist/Bayesian treatment of systematic uncertainties as nuisance parameters; profiling vs marginalization
- `numerical-computation.md` — Numerical precision, truncation, and convergence errors that contribute to the uncertainty budget
- `monte-carlo.md` — Monte Carlo propagation of uncertainties through complex measurement models
- `derivation-discipline.md` — Dimensional analysis and limiting-case checks applied to uncertainty expressions

---

## Step 1: Identify All Systematic Sources

Before quantifying anything, systematically enumerate every source of uncertainty. The most common error is missing a source entirely — no amount of careful quantification can fix an incomplete list.

### Type A vs Type B Classification (GUM)

| Classification | Definition | How Evaluated | Examples |
|---------------|-----------|---------------|----------|
| **Type A** | Evaluated by statistical analysis of repeated observations | Standard deviation of the mean from N measurements | Repeated readings, measurement scatter, noise characterization |
| **Type B** | Evaluated by other means: calibration certificates, manufacturer specs, published data, physical reasoning | Professional judgment, rectangular/triangular/Gaussian distributions | Calibration uncertainty, resolution limit, environmental sensitivity, material purity |

**CRITICAL: Type A and Type B are NOT the same as "random" and "systematic."** A Type A evaluation can characterize a systematic effect (e.g., measuring the drift rate by repeated observations), and a Type B evaluation can describe a random contribution (e.g., manufacturer-specified noise figure).

### Master Checklist of Systematic Sources

Work through every category. For each source, record: exists? (Y/N), magnitude estimate, evaluation type (A/B), distribution shape, correlated with other sources?

| Category | Specific Source | Typical Magnitude | Often Missed? |
|----------|----------------|-------------------|---------------|
| **Calibration** | Wavelength/energy scale offset | 0.01–1% | No |
| | Scale nonlinearity | 0.01–0.5% | Yes |
| | Calibration standard uncertainty | Per certificate | No |
| | Calibration drift since last cal | 0.01–1%/year | Yes |
| | Interpolation between cal points | Varies | Yes |
| **Detector/Sensor** | Gain/efficiency uncertainty | 0.1–5% | No |
| | Nonlinearity (saturation, dead time) | 0.1–10% | Sometimes |
| | Dark current / noise floor | Instrument-specific | No |
| | Crosstalk between channels | 0.01–1% | Yes |
| | Aging / radiation damage | Cumulative | Yes |
| | Dead time (counting experiments) | τ × rate | Sometimes |
| **Environmental** | Temperature sensitivity | 0.001–1%/K | Sometimes |
| | Pressure dependence | 0.01–1%/atm | Yes |
| | Humidity effects | 0.01–0.5%/% RH | Yes |
| | Vibration / mechanical coupling | Varies | Sometimes |
| | Electromagnetic interference (EMI) | 0.001–1% | Yes |
| | Stray light / background radiation | 0.01–5% | Sometimes |
| **Sample** | Positioning / alignment | 0.01–1% | Sometimes |
| | Sample purity / composition | 0.1–5% | Sometimes |
| | Sample preparation reproducibility | 0.1–5% | Yes |
| | Self-absorption / matrix effects | 0.1–10% | Yes |
| **Method** | Model/formula approximations | Varies | Yes |
| | Fitting bias (model-dependent) | Varies | Yes |
| | Normalization / reference standard | 0.1–5% | Sometimes |
| | Numerical truncation in analysis | 10⁻⁶–10⁻³ | Yes |
| **Operator** | Reading resolution / digitization | ½ least significant digit | No |
| | Trigger/threshold setting | 0.01–1% | Sometimes |
| | Subjective judgments (peak picking) | 0.1–5% | Yes |

**Common LLM Error:** Listing 3–4 obvious sources (calibration, detector efficiency, temperature) and declaring the budget complete. A real budget typically has 10–30 identified sources, even if most are negligible. The discipline is in the completeness of the search, not the length of the final list.

---

## Step 2: Classification Framework

Organize identified sources by experiment type. The dominant systematics differ dramatically between measurement techniques.

### Systematic Sources by Experiment Type

#### Spectroscopy (Optical, X-ray, NMR, Mass Spec)

| Source | Typical Impact | Evaluation Method |
|--------|---------------|-------------------|
| Wavelength/frequency calibration | 0.001–0.1% | Type B: calibration certificate + known reference lines |
| Line shape model (Voigt vs Gaussian vs Lorentzian) | 0.1–5% on width/area | Type A: fit residuals with different models |
| Detector linearity | 0.05–2% | Type B: manufacturer spec; Type A: linearity test with attenuators |
| Spectral resolution / bandpass | Sets floor on width measurements | Type B: instrument specification |
| Stray light / order contamination | 0.01–1% | Type A: measurement with blank; Type B: manufacturer spec |
| Self-absorption (optically thick samples) | 0–50%+ | Type A: dilution series; Type B: calculated from cross section × path length |
| Background subtraction | 0.1–5% | Type A: multiple background measurements; sensitivity to fitting range |
| Reference spectrum uncertainty | Per database | Type B: published uncertainties (NIST, HITRAN) |

#### Scattering (Neutron, X-ray, Light Scattering)

| Source | Typical Impact | Evaluation Method |
|--------|---------------|-------------------|
| Incident flux normalization | 0.5–5% | Type A: monitor counts; Type B: monitor efficiency |
| Detector efficiency vs angle/energy | 1–10% | Type B: manufacturer + simulation; Type A: known standard |
| Sample transmission / multiple scattering | 1–20% | Type B: calculation from sample thickness and cross sections |
| Empty container subtraction | 0.1–5% | Type A: measured; sensitivity to normalization |
| Absorption correction | 0.5–10% | Type B: calculated; uncertainty from geometry and composition |
| Resolution function | Broadens features | Type B: instrument geometry; Type A: vanadium/reference measurement |
| Incoherent scattering background | 0.1–10% | Type B: from composition; Type A: high-Q measurement |
| Beam polarization (if applicable) | 0.1–5% | Type A: polarization measurement |

#### Calorimetry (DSC, ITC, Bomb Calorimetry)

| Source | Typical Impact | Evaluation Method |
|--------|---------------|-------------------|
| Heat capacity of reference | 0.1–1% | Type B: certified reference material uncertainty |
| Baseline stability / drift | 0.05–2% | Type A: repeated empty runs; drift rate measurement |
| Thermal contact resistance | 0.1–5% | Type A: reproducibility with reloading; Type B: modeling |
| Sample mass measurement | 0.01–0.5% | Type B: balance calibration certificate |
| Heating rate uniformity | 0.01–1% | Type A: repeated runs at different rates |
| Atmosphere control (oxidation, moisture) | 0–10% | Type A: runs under different atmospheres |
| Enthalpy calibration (indium, sapphire) | 0.1–2% | Type B: certified values; Type A: repeated measurements |
| Pan / crucible contribution | 0.05–1% | Type A: empty pan subtraction; reproducibility |

#### Counting Experiments (Particle, Nuclear, Photon Counting)

| Source | Typical Impact | Evaluation Method |
|--------|---------------|-------------------|
| Dead time correction | τ × rate (can be >10% at high rates) | Type A: two-source method; Type B: electronics spec |
| Detection efficiency | 1–10% | Type B: simulation + calibration source; Type A: cross-calibration |
| Pile-up / coincidence summing | Rate-dependent, 0.1–5% | Type B: analytical formula; Monte Carlo simulation |
| Background rate uncertainty | √N_bg limited | Type A: long background measurements |
| Geometric efficiency (solid angle) | 0.1–5% | Type B: geometry measurement + calculation |
| Source self-attenuation | 0.1–10% for extended sources | Type B: calculated from source properties |
| Energy threshold / trigger efficiency | 0.1–5% near threshold | Type A: threshold scan; Type B: simulation |
| Timing resolution (if TOF) | Varies | Type B: electronics spec; Type A: prompt peak measurement |

---

## Step 3: Quantification of Individual Sources

For each identified source, assign a numerical standard uncertainty u_i.

### 3a. From Calibration Certificates

Calibration certificates report expanded uncertainty U = k × u with a coverage factor k (usually k = 2 for 95% confidence).

**To extract standard uncertainty:**
```
u = U / k
```

**Verification:** Check that the certificate states:
- [ ] Coverage factor k (if not stated, assume k = 2, but flag this)
- [ ] Confidence level (should be ~95% for k = 2)
- [ ] Calibration date and recommended recalibration interval
- [ ] Traceability statement (chain to national/international standards)
- [ ] Environmental conditions during calibration

**Common LLM Error:** Using the expanded uncertainty U directly as the standard uncertainty u. This overstates the calibration contribution by a factor of 2 (for k = 2). Conversely, if the certificate states u without specifying it is a standard uncertainty, verify whether it is already divided by k.

### 3b. From Manufacturer Specifications

Manufacturer specs often state accuracy as "± a" without specifying a distribution or confidence level. The GUM convention:

| Specification Format | Assumed Distribution | Standard Uncertainty |
|---------------------|---------------------|---------------------|
| "± a" with no further info | Rectangular (uniform) | u = a / √3 |
| "± a at 95% confidence" | Gaussian | u = a / 2 |
| "± a at 99% confidence" | Gaussian | u = a / 2.576 |
| "± a% of reading ± b digits" | Sum of proportional + fixed | u = √((a% × reading / √3)² + (b × resolution / √3)²) |
| "within a to b" (asymmetric) | Rectangular on [a, b] | u = (b − a) / (2√3), midpoint = (a + b)/2 |

**Common LLM Error:** Treating "± a" as a Gaussian 1σ uncertainty. Unless the manufacturer explicitly states a confidence level, this is wrong — the GUM default is a rectangular distribution, giving u = a/√3 ≈ 0.577a, not u = a.

### 3c. From Repeated Measurements (Type A)

If the effect is measured N times with results {x_1, ..., x_N}:

```
Mean: x_bar = (1/N) Σ x_i
Standard deviation: s = √[(1/(N-1)) Σ (x_i - x_bar)²]
Standard uncertainty of mean: u = s / √N
```

**Minimum N:** The GUM recommends N ≥ 10 for a reliable Type A evaluation. For N < 10, the Student-t distribution should be used (effective degrees of freedom ν = N − 1), which broadens the interval.

### 3d. From Environmental Sensitivity Measurements

Measure the output at two or more environmental conditions to determine a sensitivity coefficient:

```
Sensitivity coefficient: c_env = Δy / Δ(env. variable)
Uncertainty contribution: u_env = |c_env| × u(env. variable)
```

where u(env. variable) is the uncertainty in the environmental variable during the actual measurement (e.g., temperature stability ± 0.5 K gives u_T = 0.5/√3 K for rectangular, or 0.5 K for Gaussian).

---

## Step 4: Correlation Assessment

Systematic uncertainties are often correlated — failing to account for correlations can either overestimate or underestimate the combined uncertainty, sometimes by factors of 2 or more.

### Common Sources of Hidden Correlations

| Correlation Source | Example | Effect if Ignored |
|-------------------|---------|-------------------|
| **Shared calibration standard** | Same reference used for two instruments | Underestimates uncertainty (correlation > 0) |
| **Common environmental exposure** | Both measurements in same room | Underestimates if additive, can overestimate if subtractive |
| **Same model/formula used** | Both analyses use same theoretical correction | Correlated model error cancels poorly |
| **Same operator** | Systematic reading bias applies to both | Underestimates |
| **Same data reanalyzed** | Different cuts on same dataset | Strong positive correlation |
| **Ratio of two measurements** | Signal/reference with same detector | Partial cancellation (correlation reduces ratio uncertainty) |
| **Background subtraction** | Signal and background measured with same detector in different conditions | Can be positive or negative depending on mechanism |

### Constructing the Correlation Matrix

For n sources, construct the n × n correlation matrix r_ij where:
- r_ii = 1 (diagonal)
- r_ij = r_ji (symmetric)
- |r_ij| ≤ 1

**When you cannot measure the correlation directly:**

| Knowledge Available | Assign |
|-------------------|--------|
| Sources are physically independent (different instruments, different principles) | r = 0 |
| Sources share a common cause but you cannot quantify the coupling | r = +1 (conservative) or r = −1 (if subtractive), then check sensitivity |
| Partial common cause, rough estimate available | Assign estimated r, then vary ±0.2 to check sensitivity |
| Repeated measurements of same quantity by same method | r → 1 for systematic component, r = 0 for statistical component |

**CRITICAL:** If the combined uncertainty changes by more than 10% when r_ij is varied from 0 to 1, the correlation matters and must be properly evaluated — not just assumed.

### Verification

- [ ] All pairs of sources checked for common cause
- [ ] Correlation matrix is positive semi-definite (all eigenvalues ≥ 0)
- [ ] Sensitivity of combined uncertainty to assumed correlations tested (vary r_ij ±0.2)
- [ ] For cross-experiment combinations, systematic correlations documented explicitly

---

## Step 5: Budget Combination

### 5a. Uncorrelated Sources (Simplest Case)

If all n systematic sources are independent and the measurement model is y = f(x_1, ..., x_n), the combined standard uncertainty is:

```
u_c² = Σ_i (∂f/∂x_i)² × u_i²  =  Σ_i c_i² × u_i²
```

where c_i = ∂f/∂x_i are sensitivity coefficients.

For a direct measurement with additive systematics: u_c = √(u_1² + u_2² + ... + u_n²).

### 5b. Correlated Sources (General Case)

With correlations:

```
u_c² = Σ_i Σ_j c_i × c_j × u_i × u_j × r_ij
```

Written in matrix form: u_c² = c^T V c, where V_ij = u_i × u_j × r_ij is the covariance matrix.

**Common LLM Error:** Always combining in quadrature (assuming r_ij = 0 for all i ≠ j). If two dominant sources are 100% correlated, the combined uncertainty is their linear sum, not their quadrature sum:

```
Wrong:  u_c = √(u_1² + u_2²)     [e.g., √(3² + 4²) = 5]
Correct: u_c = u_1 + u_2           [e.g., 3 + 4 = 7, if r = +1]
```

This is a 40% difference for comparable-magnitude sources.

### 5c. Dominant Source Identification

After computing u_c, calculate the fractional contribution of each source:

```
Fraction_i = (c_i × u_i)² / u_c²   (for uncorrelated case)
```

| Fraction | Interpretation | Action |
|----------|---------------|--------|
| > 50% | **Dominant source** — drives the total uncertainty | This is where effort to reduce uncertainty should focus |
| 10–50% | **Significant** — contributes meaningfully | Worth reducing if feasible |
| 1–10% | **Minor** — contributes at margins | Only address if dominant sources are already at their floor |
| < 1% | **Negligible** — can be documented and set aside | Include in budget for completeness, but no further effort needed |

**Rule of thumb:** If the dominant source contributes >80% of u_c², reducing all other sources to zero would only reduce u_c by ~10%. Focus effort on the dominant source.

### 5d. Monte Carlo Method (Non-Gaussian / Nonlinear Cases)

When the measurement model f(x_1, ..., x_n) is nonlinear or the input distributions are non-Gaussian, the GUM Supplement 1 (JCGM 101:2008) recommends Monte Carlo propagation:

1. Assign probability distributions to each input x_i (Gaussian, rectangular, triangular, etc.)
2. Draw M random samples from each distribution (M ≥ 10⁶)
3. Evaluate y = f(x_1, ..., x_n) for each draw
4. The output distribution of y gives the combined uncertainty directly (use the standard deviation, or report the shortest 95% coverage interval for asymmetric cases)

**When to use Monte Carlo instead of GUM linear propagation:**
- Measurement model has significant curvature (∂²f/∂x_i² × u_i is not negligible)
- Input distributions are asymmetric or bounded
- Output distribution is expected to be non-Gaussian
- Sensitivity coefficients ∂f/∂x_i cannot be computed analytically

### 5e. Expanded Uncertainty

Report the expanded uncertainty U = k × u_c, where:

| Coverage Factor k | Coverage Probability (Gaussian) | Use When |
|-------------------|-------------------------------|----------|
| k = 1 | 68.3% | Internal documentation, intermediate calculations |
| k = 2 | 95.4% | **Standard reporting** (GUM default) |
| k = 3 | 99.7% | Safety-critical, regulatory compliance |
| k = t_ν,0.95 | 95% (Student-t) | Effective degrees of freedom ν_eff < 30 (use Welch-Satterthwaite) |

**Welch-Satterthwaite effective degrees of freedom:**

```
ν_eff = u_c⁴ / Σ_i (c_i⁴ × u_i⁴ / ν_i)
```

where ν_i is the degrees of freedom for each source (ν_i = N_i − 1 for Type A; ν_i → ∞ for well-known Type B).

---

## Step 6: Calibration Traceability

A measurement is only as good as its calibration chain. Traceability means an unbroken chain of comparisons, each with stated uncertainties, from the measurement result back to SI standards (or other recognized references).

### The Traceability Chain

```
SI realization (national metrology institute: NIST, PTB, NPL, ...)
  ↓  uncertainty: u_SI
Primary reference standard
  ↓  uncertainty: u_primary
Secondary / transfer standard
  ↓  uncertainty: u_transfer
Working standard (in-lab reference)
  ↓  uncertainty: u_working
Instrument under calibration
  ↓  uncertainty: u_instrument
Measurement result
```

**Each link adds uncertainty.** The total calibration uncertainty is (assuming independent links):

```
u_cal = √(u_SI² + u_primary² + u_transfer² + u_working² + u_instrument²)
```

### Documentation Requirements

For each calibration in the chain, record:

| Item | Required | Why |
|------|----------|-----|
| Calibration certificate number | Yes | Traceability audit trail |
| Calibrating laboratory accreditation | Yes | ISO/IEC 17025 accreditation ensures competence |
| Calibration date | Yes | Determines if still valid |
| Recalibration interval | Yes | Tells you when the next cal is due |
| Environmental conditions during calibration | Yes | Lab conditions may differ from measurement conditions |
| Expanded uncertainty U and coverage factor k | Yes | Needed to extract standard uncertainty |
| Traceability statement | Yes | Which national standard? Which SI realization? |
| Calibration method / procedure | Recommended | Allows assessment of whether the cal method matches your use case |

### Recalibration Intervals

| Instrument Type | Typical Interval | Factors That Shorten Interval |
|----------------|-----------------|------------------------------|
| Reference standards (weights, gauge blocks) | 1–5 years | Heavy use, harsh environment |
| Electronic instruments (DMM, oscilloscope) | 6–12 months | Temperature cycling, transport, aging components |
| Optical instruments (spectrometer, laser) | 3–12 months | Alignment sensitivity, source aging |
| Sensors (thermocouples, pressure transducers) | 3–12 months | Exposure to extreme conditions, drift-prone technology |
| Dimensional (micrometers, calipers) | 6–12 months | Wear from use |

**Between calibrations:** The uncertainty grows. A conservative model: u_drift(t) = u_cal × (1 + α × t/t_cal), where α is a drift coefficient and t_cal is the calibration interval. If the instrument is used near the end of a calibration interval, this contribution can be significant.

**Common LLM Error:** Treating calibration as a one-time event. Calibration uncertainty is not a fixed number — it includes the certificate uncertainty PLUS any drift since the last calibration. An instrument calibrated 11 months ago on a 12-month cycle has more uncertainty than one calibrated last week.

---

## Step 7: Mitigation and Monitoring

After building the budget, the final step is reducing the dominant sources and monitoring for unexpected changes.

### Mitigation Strategies by Source Type

| Source Type | Mitigation Strategy | Expected Improvement |
|-------------|--------------------|---------------------|
| **Calibration drift** | More frequent calibration; use self-calibrating instruments; bracket measurements with calibration checks | 2–10× reduction in drift contribution |
| **Temperature sensitivity** | Temperature-controlled enclosure; measure temperature and apply correction; differential measurement (sample vs reference) | 5–100× reduction |
| **Detector nonlinearity** | Operate in linear range; apply measured nonlinearity correction; use attenuators to stay in range | 2–10× reduction |
| **Background/stray light** | Improve shielding; modulate signal (lock-in detection); measure and subtract background | 2–100× reduction |
| **Sample positioning** | Use kinematic mounts; motorized stages with encoders; average over multiple positions | 2–5× reduction |
| **Operator bias** | Automate readings; blinded analysis; multiple operators | 2–5× reduction |
| **Model error** | Use higher-order corrections; compare multiple models; validate against known standards | Problem-dependent |

### Drift Monitoring with Control Charts

For critical measurements, maintain a control chart: plot a reference measurement (e.g., calibration check standard) over time.

**Shewhart chart rules (any one triggers investigation):**
1. One point beyond 3σ from the mean
2. Two of three consecutive points beyond 2σ on the same side
3. Four of five consecutive points beyond 1σ on the same side
4. Eight consecutive points on the same side of the mean
5. Six consecutive points trending monotonically (up or down)

**What to plot:** Measure a stable reference standard at regular intervals (daily, weekly, per-run). Plot the measured value with its uncertainty bar. The control limits are set from the first ~20 measurements after calibration.

**When a rule triggers:** Stop measurements, investigate the root cause (drift, contamination, mechanical shift, software update, environmental change), recalibrate if needed, and document the event with corrective action.

### Periodic Budget Review

The uncertainty budget is a living document. Review it when:
- A new calibration reveals unexpected drift
- Environmental conditions change (new lab, seasonal variation)
- The measurement procedure changes (new software, new operator, new sample type)
- A control chart flags an out-of-control condition
- The measurement is applied to a new range of the measurand (extrapolation beyond calibration range)

---

## Common LLM Error Patterns

| Error Pattern | LLM Symptom | Detection | Consequence |
|--------------|-------------|-----------|-------------|
| **Incomplete source enumeration** | Lists 3–4 obvious sources, ignores environmental/correlation/method contributions | Compare against master checklist (Step 1); count sources | Missing dominant systematic; budget underestimates total uncertainty |
| **Type A/B = random/systematic** | States "Type A uncertainties are random and Type B are systematic" | GUM Section 3: Type A/B refers to evaluation method, not the nature of the uncertainty | Misclassification of sources; incorrect distribution assignment |
| **Rectangular → Gaussian confusion** | Uses u = a for manufacturer "± a" spec instead of u = a/√3 | Check if confidence level is stated; if not, use rectangular | Overestimates calibration uncertainty by factor of √3 |
| **Ignoring correlations** | Adds all sources in quadrature without checking for shared causes | Ask: "Do any two sources share a calibration, environment, or data?" | Can underestimate combined uncertainty by up to factor of 2 for equal dominant sources |
| **Static calibration assumption** | Uses calibration certificate value without accounting for time since calibration | Check calibration date vs measurement date; ask about drift data | Underestimates uncertainty for measurements near end of calibration interval |
| **Expanded ↔ standard confusion** | Mixes U (expanded, k = 2) and u (standard) in the same sum | Check: are all u_i at the same confidence level before combining? | Factor-of-2 error in combined uncertainty if one U is used where u is needed |
| **Sensitivity coefficient = 1** | Assumes c_i = ∂f/∂x_i = 1 for all sources instead of computing the actual partial derivative | Check measurement model: is the measurand a simple sum of inputs? | Wrong weighting of uncertainty sources; can be orders of magnitude off for nonlinear models |
| **Neglecting digitization** | Ignores the resolution of the readout (ADC, display digits) | For a display resolution of δ, u_resolution = δ/(2√3) | Matters when the reading resolution approaches the measurement precision |

---

## Worked Example: UV-Vis Absorption Spectroscopy

**Problem:** Measure the molar absorptivity ε of a dye at its absorption maximum (λ_max ≈ 520 nm) using Beer-Lambert law: A = ε × c × l, so ε = A / (c × l). Report ε with a complete uncertainty budget.

**Setup:** UV-Vis spectrophotometer, 1 cm quartz cuvette, dye solution of known concentration c = 2.50 × 10⁻⁵ mol/L.

### Wrong Approach (Common LLM Error)

"The absorbance reads A = 0.625 ± 0.003 (standard deviation of 5 readings). The concentration is c = 2.50 × 10⁻⁵ mol/L ± 1%. The path length is l = 1.000 cm ± 0.001 cm. Propagating in quadrature:

u(ε)/ε = √((0.003/0.625)² + (0.01)² + (0.001/1.000)²) = √(0.0048² + 0.01² + 0.001²) = 0.0112

ε = 25,000 ± 280 L/(mol·cm)."

**Why this is wrong:**
1. Only includes three sources — misses wavelength calibration, detector linearity, temperature, stray light, cuvette quality
2. The "± 1%" on concentration is used without stating whether it is a standard uncertainty or an expanded uncertainty
3. Path length uncertainty ignores cuvette window parallelism and positioning reproducibility
4. No assessment of whether the absorbance is in the linear range of the detector
5. No correlation assessment (e.g., if the same cuvette is used for blank and sample, cuvette path length error partially cancels)

### Correct Approach

**Step 1: Full Source Identification**

| Source | Affects | Type | Distribution | u_i (relative) |
|--------|---------|------|-------------|-----------------|
| 1. Absorbance repeatability | A | A | Gaussian (5 readings) | 0.48% |
| 2. Wavelength calibration | A (via ε(λ) slope) | B | Gaussian (certificate) | 0.20% |
| 3. Photometric accuracy | A | B | Rectangular (manufacturer) | 0.29% |
| 4. Detector nonlinearity | A | B | Rectangular (manufacturer) | 0.17% |
| 5. Stray light | A | B | Rectangular (manufacturer) | 0.15% |
| 6. Cuvette path length | l | B | Rectangular (manufacturer) | 0.058% |
| 7. Cuvette positioning reproducibility | l | A | Gaussian (10 repositionings) | 0.10% |
| 8. Solution concentration | c | B | Gaussian (gravimetric prep) | 0.50% |
| 9. Temperature coefficient of ε | ε | B | Rectangular (± 2 K × 0.1%/K) | 0.12% |
| 10. Blank subtraction (solvent absorbance) | A | A | Gaussian (3 blank readings) | 0.08% |

**Step 2: Quantification Details**

Source 1 (Repeatability): 5 readings: A = {0.624, 0.626, 0.623, 0.627, 0.625}. Mean = 0.625, s = 0.00158, u_1 = s/√5 = 0.00071 → 0.48/0.625 = 0.11% ... wait, let me recalculate: u_1/A = 0.00071/0.625 = 0.11%. But with t-factor for ν = 4: t_0.95 = 2.776, so this matters for coverage factor later.

Actually: u_1 = 0.00071 → relative = 0.114%. I listed 0.48% above using s rather than s/√N. Let me correct the table:

| Source | u_i (relative) | ν_i |
|--------|----------------|-----|
| 1. Absorbance repeatability | s/√5 = 0.114% | 4 |
| 2. Wavelength cal: certificate states U = ± 0.5 nm (k = 2), so u_λ = 0.25 nm. Near λ_max, dA/dλ ≈ 0. But measured at 520 nm, slope of spectrum gives dε/dλ ≈ −100 L/(mol·cm·nm) at the flank. If measuring exactly at peak, sensitivity is near zero. Assume we are at peak: c_2 × u_λ = 0.25 nm × |dε/dλ|/ε. At peak dε/dλ ≈ 0, so | 0.00% (at peak; up to 0.5% on flank) | ∞ |
| 3. Photometric accuracy: manufacturer states "± 0.005 A" at A = 0.625. Rectangular: u_3 = 0.005/√3 = 0.00289 → 0.00289/0.625 = 0.46% | 0.46% | ∞ |
| 4. Detector nonlinearity: spec "< 0.3% for A < 1.0." Rectangular: u_4 = 0.003/√3 = 0.17% | 0.17% | ∞ |
| 5. Stray light: spec "< 0.1% T at 340 nm." At 520 nm, estimate < 0.05% T. Effect on A ≈ 0.05%/(T × ln10). T = 10^(−0.625) = 0.237, so δA ≈ 0.0005/(0.237 × 2.303) = 0.0009. u_5 = 0.0009/√3 = 0.00052 → 0.083%. | 0.083% | ∞ |
| 6. Cuvette path length: manufacturer spec "10.00 ± 0.01 mm" → u_6 = 0.01/√3 = 0.0058 mm → 0.058% | 0.058% | ∞ |
| 7. Cuvette repositioning: 10 trials, s = 0.001 A → u_7 = 0.001/√10 = 0.000316 → 0.051% | 0.051% | 9 |
| 8. Concentration: prepared gravimetrically, uncertainty analysis gives u(c)/c = 0.50% (dominated by volumetric flask tolerance, Type B, rectangular on "Class A ± 0.05 mL in 100 mL") | 0.50% | ∞ |
| 9. Temperature: lab ± 2 K, literature dε/dT = −0.1%/K for this dye. u_T = 2/√3 = 1.15 K. u_9 = 0.1% × 1.15 = 0.115% | 0.115% | ∞ |
| 10. Blank subtraction: 3 readings, s = 0.0005, u_10 = 0.0005/√3 = 0.00029 → 0.046% | 0.046% | 2 |

**Step 3: Correlation Check**

- Sources 1, 7, 10 share the same detector → potential correlation. However, 1 is repeatability of sample, 7 is repositioning, 10 is blank measurement. The detector systematic (Source 3) is already separated. These Type A evaluations capture different variability. Treat as uncorrelated.
- Sources 3, 4, 5 all arise from the detector/optics → potentially correlated. However, they describe different physical effects (absolute accuracy, nonlinearity, stray light). Conservative: set r_{3,4} = r_{3,5} = r_{4,5} = 0.5 and check sensitivity.
- Source 6 (cuvette) and Source 7 (repositioning) are correlated (same cuvette). But Source 6 is the absolute path length while Source 7 is the repositioning variability. They contribute to different aspects. Treat as uncorrelated.

**Step 4: Combination**

For the measurement model ε = A/(c × l), all sensitivity coefficients are ±1 in relative terms (c_i = 1 for all sources expressed as relative uncertainties, since ε is the product/quotient of the inputs).

**Uncorrelated combination (all r = 0):**

u_c/ε = √(0.114² + 0.00² + 0.46² + 0.17² + 0.083² + 0.058² + 0.051² + 0.50² + 0.115² + 0.046²) %

= √(0.013 + 0 + 0.212 + 0.029 + 0.0069 + 0.0034 + 0.0026 + 0.25 + 0.013 + 0.0021) %

= √(0.531) % = 0.73%

**With correlations (r_{3,4} = r_{3,5} = r_{4,5} = 0.5):**

Additional terms: 2 × 0.5 × (0.46 × 0.17 + 0.46 × 0.083 + 0.17 × 0.083) × 10⁻⁴

= 2 × 0.5 × (0.0782 + 0.0382 + 0.0141) × 10⁻⁴ = 0.1305 × 10⁻⁴ → relative: +0.013 percentage-points-squared

u_c/ε = √(0.531 + 0.013) % = √(0.544) % = 0.74%

**Sensitivity check:** Correlation changed result from 0.73% to 0.74% — not significant. Uncorrelated assumption is acceptable here.

**Step 5: Dominant Source Identification**

| Source | Fraction of u_c² |
|--------|-------------------|
| 8. Concentration | 47% — **DOMINANT** |
| 3. Photometric accuracy | 40% — **DOMINANT** |
| 4. Detector nonlinearity | 5.5% |
| 9. Temperature | 2.5% |
| 1. Repeatability | 2.4% |
| All others combined | 2.6% |

**Conclusion:** The budget is dominated by concentration preparation uncertainty and photometric accuracy. Improving any other source will not meaningfully reduce the total uncertainty.

**Step 6: Report**

Using Welch-Satterthwaite with dominant sources having ν → ∞: ν_eff is large, so k = 2 is appropriate.

```
ε = 25,000 ± 370 L/(mol·cm)   (k = 2, 95% coverage)
```

or equivalently: ε = (2.500 ± 0.037) × 10⁴ L/(mol·cm).

**To improve:** (1) Prepare concentration more carefully (gravimetric preparation of stock solution with ≤ 0.1% uncertainty). (2) Use a photometric accuracy-certified instrument or validate linearity with neutral density filters.

---

## Verification Checklist

Before finalizing any uncertainty budget:

- [ ] All systematic sources identified using master checklist (Step 1); no category left blank without justification
- [ ] Each source classified as Type A or Type B with correct interpretation (evaluation method, NOT random vs systematic)
- [ ] Type B sources: distribution shape explicitly stated (rectangular, Gaussian, triangular) with justification
- [ ] Manufacturer specs converted correctly (÷√3 for rectangular, ÷k for expanded Gaussian)
- [ ] Calibration certificates: standard uncertainty extracted (U/k), not expanded uncertainty used directly
- [ ] Calibration traceability chain documented with unbroken links to SI or recognized standards
- [ ] Time since last calibration assessed for drift contribution
- [ ] Environmental sensitivities measured or estimated with explicit sensitivity coefficients
- [ ] All pairs of sources checked for correlations; correlation matrix constructed if any are non-zero
- [ ] Sensitivity of combined result to assumed correlations tested (vary r ± 0.2)
- [ ] Sensitivity coefficients c_i = ∂f/∂x_i computed from actual measurement model, not assumed to be 1
- [ ] Dominant sources identified (top 1–3 contributing >80% of u_c²)
- [ ] Combined uncertainty u_c computed using correct formula (quadrature for uncorrelated; full covariance for correlated)
- [ ] Coverage factor k stated with justification (k = 2 for Gaussian with ν_eff > 30; Student-t otherwise)
- [ ] Expanded uncertainty U = k × u_c reported with coverage probability
- [ ] Measurement result + uncertainty has correct units and significant figures (u_c to at most 2 significant figures)
- [ ] Limiting case check: if one source dominates overwhelmingly, u_c ≈ that source's contribution
- [ ] Budget documented as a table with every source, value, distribution, degrees of freedom, and contribution

---
load_when:
  - "measurement reproducibility"
  - "run-to-run"
  - "apparatus stability"
  - "cross-lab"
  - "measurement protocol"
  - "Allan variance"
  - "drift monitoring"
  - "round-robin"
  - "interlaboratory comparison"
  - "repeatability"
  - "measurement agreement"
  - "instrument stability"
  - "experimental reproducibility"
tier: 2
context_cost: medium
---

# Measurement Reproducibility Protocol

A measurement that cannot be reproduced is not a measurement — it is an anecdote. Physical measurements face challenges that computational results do not: apparatus drift, environmental sensitivity, operator technique, and sample variability. This protocol provides a systematic framework for establishing that a physical measurement is reproducible at every level, from internal consistency within a single run to agreement across independent laboratories.

**Core discipline:** The history of physics is littered with irreproducible results — cold fusion, superluminal neutrinos, anomalous magnetic moments later traced to systematic effects. Every step below exists because experimentalists have learned, often painfully, that a single measurement under a single set of conditions proves very little.

## Related Protocols

- `statistical-inference.md` — Hypothesis testing, chi-squared goodness of fit, confidence intervals used throughout this protocol
- `numerical-computation.md` — Error budgets and convergence testing; the computational analog of measurement uncertainty analysis
- `monte-carlo.md` — Monte Carlo uncertainty propagation for complex measurement functions
- `derivation-discipline.md` — Dimensional analysis and limiting-case checks applicable to measurement equations

---

## Reproducibility Levels

| Level | Physical Measurement | Computational Analog |
|-------|---------------------|---------------------|
| Internal consistency | Readings within one run agree | Bit-for-bit reproduction |
| Repeatability | Independent runs on same apparatus agree | Same-seed reproduction |
| Reproducibility | Different apparatus/lab agree | Different-platform agreement |
| Method independence | Different measurement methods agree | Cross-method validation |

Each level subsumes the previous. A measurement that fails internal consistency cannot be trusted at the repeatability level. A measurement that passes repeatability but fails cross-apparatus comparison has an uncharacterized systematic. Progress through these levels in order.

---

## Step 1: Single-Run Internal Consistency

Before trusting any measurement, verify that the apparatus is producing self-consistent data within a single measurement session.

### 1a. Repeated readings

Take N repeated readings of the same quantity under nominally identical conditions within one run. Compute:

- **Sample mean:** x_bar = (1/N) sum(x_i)
- **Sample standard deviation:** s = sqrt(sum((x_i - x_bar)^2) / (N-1))
- **Standard error of the mean:** s_m = s / sqrt(N)

**Minimum:** N >= 10 readings per measurement point. Fewer readings cannot reliably estimate the variance.

### 1b. Chi-squared test for consistency

If each reading x_i has known uncertainty sigma_i, compute:

```
chi^2 = sum((x_i - x_bar)^2 / sigma_i^2)
```

with N-1 degrees of freedom. Expected value: chi^2 / dof ~ 1.

| chi^2 / dof | Diagnosis |
|-------------|-----------|
| 0.5 - 1.5 | Consistent — uncertainties correctly estimated |
| < 0.5 | Uncertainties overestimated (conservative but suspicious) |
| 1.5 - 3.0 | Possible unaccounted scatter — investigate |
| > 3.0 | Inconsistent — systematic effect or underestimated uncertainty |

### 1c. Drift monitoring

Plot readings vs. time (or sequential index). Apply a linear fit x(t) = a + b*t and test whether b is significantly nonzero (|b| > 2*sigma_b).

**Common drift sources:**
- Thermal equilibration (exponential approach to steady state — first 5-10 minutes often unusable)
- Component aging (laser power decay, detector gain drift)
- Environmental cycles (HVAC, day/night temperature cycles, tidal effects in precision gravity experiments)

**Protocol:** If drift is detected:
1. Extend warm-up period until readings stabilize
2. If drift persists, fit and subtract the trend, then add the drift uncertainty to the error budget
3. If drift rate changes unpredictably, the measurement is not under control — fix the apparatus before proceeding

### 1d. Outlier detection

**Chauvenet's criterion:** Reject reading x_i if the probability of obtaining a deviation |x_i - x_bar| / s or larger is less than 1/(2N). For N = 10, reject if |x_i - x_bar| > 1.96s. For N = 100, reject if |x_i - x_bar| > 2.81s.

**Grubbs test (preferred for small N):** Compute G = max(|x_i - x_bar|) / s. Compare to the critical value from Grubbs' table at the chosen significance level (typically alpha = 0.05). If G > G_critical, the most extreme point is an outlier.

**Critical rule:** Never discard outliers silently. Document every excluded point, the criterion used, and the physical reason if known (e.g., "power supply glitch at t = 47 s, confirmed by voltage monitor log"). If more than ~5% of readings are outliers, the measurement is not under control.

---

## Step 2: Run-to-Run Reproducibility

Same apparatus, same conditions, different measurement sessions separated by at least one complete shutdown-restart cycle.

### 2a. Protocol

1. **Minimum 3 independent runs** (5 preferred for critical measurements)
2. Each run includes full apparatus warm-up, calibration, and measurement sequence
3. Runs should span at least 2-3 different days to capture day-to-day environmental variation
4. Record environmental conditions (temperature, humidity, barometric pressure) for each run

### 2b. Expected variation

Run-to-run results should agree within the combined uncertainty of each individual run. For runs with individual uncertainties sigma_1, sigma_2, ..., sigma_N, the consistency test is:

```
chi^2 = sum((x_i - x_weighted_mean)^2 / sigma_i^2)
```

with N-1 degrees of freedom. If chi^2 / dof > 1, there is excess scatter — a run-to-run systematic that was not captured in the single-run uncertainty.

### 2c. Allan variance for stability characterization

The Allan variance sigma_A^2(tau) characterizes measurement stability as a function of averaging time tau:

```
sigma_A^2(tau) = (1 / (2(M-1))) sum((x_bar_{i+1}(tau) - x_bar_i(tau))^2)
```

where x_bar_i(tau) is the average of readings in the i-th time bin of duration tau, and M is the number of bins.

**Interpreting the Allan deviation plot (log sigma_A vs. log tau):**

| Slope | Noise type | Physical source |
|-------|-----------|-----------------|
| -1/2 | White noise | Random measurement noise (averaging helps) |
| 0 | Flicker (1/f) noise | Electronic drift, thermal fluctuations (averaging stops helping) |
| +1/2 | Random walk | Environmental drift, mechanical creep (averaging hurts) |
| +1 | Linear drift | Systematic trend (must be corrected) |

**The Allan deviation minimum** defines the optimal averaging time. Averaging beyond this point INCREASES uncertainty due to drift. This is one of the most important diagnostics in precision measurement — it tells you exactly when to stop averaging.

### 2d. Diagnosis of excess scatter

If run-to-run scatter exceeds single-run uncertainty:

1. **Check calibration reproducibility** — Is the calibration procedure producing different results each session?
2. **Check environmental logs** — Correlate excess scatter with temperature, humidity, vibration data
3. **Check sample condition** — Is the sample degrading, oxidizing, or being contaminated between runs?
4. **Inflate uncertainty** — If the source cannot be identified, add an empirical "run-to-run" systematic: sigma_rtr = sqrt(s_runs^2 - sigma_single_run^2), where s_runs is the observed run-to-run standard deviation

---

## Step 3: Operator Dependence

Same apparatus, different operators performing the measurement independently.

### 3a. Why this matters

Operator dependence reveals:
- **Procedure ambiguities** — Steps that seem clear to the developer but are interpreted differently by others
- **Tacit knowledge** — Unwritten tricks (alignment by eye, "feeling" when a contact is good, knowing which knob to jiggle)
- **Training gaps** — Insufficient documentation of critical steps

### 3b. Protocol

1. **At least 2 independent operators** for any measurement that will be published or used for decision-making
2. Each operator receives the same written procedure — no verbal coaching
3. **Blind analysis preferred:** Operators do not see each other's results until both are complete
4. Compare results using the same chi-squared consistency test as Step 2

### 3c. Diagnosing operator discrepancies

If operators disagree beyond combined uncertainties:

| Discrepancy Source | Diagnostic | Resolution |
|-------------------|------------|------------|
| Alignment procedure | Operators photograph their alignment | Add alignment tolerance to procedure; quantify sensitivity |
| Reading interpretation | Operators record raw instrument output | Automate reading (digital acquisition vs. analog readout) |
| Sample preparation | Operators document preparation steps with photos | Standardize preparation; add quantitative criteria (surface roughness, cleanliness spec) |
| Timing/sequence | Operators record timestamps | Add explicit timing requirements to protocol |

---

## Step 4: Environmental Sensitivity

Physical measurements exist in the real world. Temperature, humidity, vibration, and electromagnetic interference can all affect results.

### 4a. Control-Characterize-Correct hierarchy

For each environmental variable:

1. **Control** (best): Regulate the variable to within tolerance (e.g., temperature-controlled enclosure at 20.0 +/- 0.1 C)
2. **Characterize** (acceptable): Monitor the variable, measure the sensitivity coefficient, add to error budget
3. **Correct** (use with caution): Apply a correction based on measured environmental conditions — requires a validated model of the dependence

### 4b. Sensitivity coefficients

For each environmental variable E, measure the sensitivity:

```
c_E = partial(x) / partial(E)
```

by deliberately varying E while holding everything else constant. The contribution to measurement uncertainty is:

```
sigma_E = |c_E| * Delta_E
```

where Delta_E is the range of environmental variation during the measurement.

### 4c. Environmental monitoring requirements

| Variable | Minimum monitoring | Typical sensitivity |
|----------|-------------------|-------------------|
| Temperature | +/- 0.1 C, logged every 60 s | 10-100 ppm/K for most materials |
| Humidity | +/- 2% RH, logged every 300 s | Affects hygroscopic samples, some electronics |
| Vibration | Accelerometer on optical table, logged continuously | Affects interferometry, AFM, precision balances |
| EM interference | Spectrum analyzer survey at setup; periodic checks | Affects sensitive amplifiers, SQUIDs, lock-in measurements |
| Barometric pressure | +/- 0.1 hPa, logged every 300 s | Affects gas-phase measurements, precision balances |

### 4d. Environmental correlation analysis

After collecting multiple runs with environmental logs, compute the correlation coefficient between measurement results and environmental variables:

```
r = cov(x, E) / (sigma_x * sigma_E)
```

If |r| > 0.5, the environmental variable is a significant contributor to measurement variability. Either control it better or apply a correction.

---

## Step 5: Cross-Apparatus Agreement

Same measurement performed on different instruments, ideally in different laboratories.

### 5a. Round-robin comparison protocol

1. **Prepare a stable reference sample** (or transfer standard) that can be shipped between labs
2. **Each lab measures independently** using their own calibrated apparatus and documented procedure
3. **Report: measured value, combined uncertainty, apparatus description, environmental conditions**
4. **Evaluate consistency** using the methods below

### 5b. E_n number for proficiency testing (ISO 13528)

The E_n number quantifies agreement between laboratory result x_lab and a reference value x_ref:

```
E_n = (x_lab - x_ref) / sqrt(U_lab^2 + U_ref^2)
```

where U_lab and U_ref are expanded uncertainties (k=2, i.e., 95% coverage).

| E_n | Interpretation |
|-----|---------------|
| |E_n| <= 1.0 | Satisfactory — results agree within combined uncertainty |
| 1.0 < |E_n| <= 2.0 | Questionable — investigate possible systematics |
| |E_n| > 2.0 | Unsatisfactory — significant discrepancy requiring resolution |

### 5c. Diagnosing discrepancies

When cross-apparatus results disagree (|E_n| > 1):

| Source | Diagnostic | Resolution |
|--------|------------|------------|
| Calibration | Compare calibration standards traceably to SI | Recalibrate against common reference standard |
| Method difference | Different measurement principles (e.g., 4-wire vs. 2-wire resistance) | Identify and correct for known method biases |
| Sample difference | Sample may have changed during transport | Use multiple transfer standards; verify stability before and after |
| Environmental | Different lab environments | Apply environmental corrections using measured sensitivity coefficients |
| Definition mismatch | Labs measuring slightly different quantities (e.g., DC vs. AC resistance) | Align measurand definitions precisely |

### 5d. Birge ratio

For N laboratories reporting values x_i +/- sigma_i, the Birge ratio is:

```
R_B = sqrt(chi^2 / (N-1))
```

where chi^2 is computed against the weighted mean. R_B ~ 1 indicates consistent uncertainties. R_B >> 1 indicates either underestimated uncertainties or unresolved systematics across labs. The PDG (Particle Data Group) convention: if R_B > 1, inflate all uncertainties by R_B before computing the world average.

---

## Step 6: Measurement Protocol Documentation

A measurement is only reproducible if someone else can reproduce it from the documentation alone.

### 6a. Required elements

Every measurement protocol must document:

1. **Measurand definition** — Exactly what physical quantity is being measured, under what conditions (temperature, pressure, sample state)
2. **Apparatus description** — Manufacturer, model, serial number, firmware version, calibration date and certificate number
3. **Sample preparation** — Source, purity, preparation steps, storage conditions, handling precautions
4. **Measurement procedure** — Step-by-step instructions sufficient for a competent operator who has never performed this measurement:
   - Warm-up and stabilization time
   - Calibration procedure (standards used, acceptance criteria)
   - Measurement sequence (number of readings, integration time, averaging)
   - Data acquisition settings (sampling rate, filters, gain)
5. **Environmental conditions** — Required range, monitored variables, logging frequency
6. **Data analysis** — Equations used, software and version, corrections applied, uncertainty evaluation method

### 6b. Measurement protocol template

```
MEASUREMENT PROTOCOL: [Title]
Version: [X.Y]  Date: [YYYY-MM-DD]  Author: [Name]

1. MEASURAND
   Quantity: [e.g., "DC electrical resistivity of sample X at 20 C"]
   Units: [SI units]
   Expected range: [order of magnitude estimate]

2. APPARATUS
   Instrument: [Manufacturer Model, S/N, Firmware]
   Calibration: [Date, Certificate #, Standard used]
   Accessories: [Probes, fixtures, cables — with part numbers]

3. SAMPLE
   Material: [Composition, supplier, lot number]
   Preparation: [Steps, with quantitative criteria]
   Condition: [Storage, handling, any pre-treatment]

4. ENVIRONMENT
   Temperature: [Controlled to X +/- Y C / Monitored]
   Humidity: [Range / Controlled / Not critical]
   Other: [Vibration, EMI, pressure as applicable]

5. PROCEDURE
   5.1 Power on instrument, wait [N] minutes for thermal stability
   5.2 Perform calibration using [standard], verify [criterion]
   5.3 Mount sample per [diagram/photo reference]
   5.4 Acquire [N] readings at [interval], total acquisition time [T]
   5.5 Record environmental conditions from monitors
   5.6 Repeat Steps 5.3-5.5 for [M] independent measurements

6. DATA ANALYSIS
   6.1 Apply corrections: [list with equations]
   6.2 Compute mean and standard error
   6.3 Evaluate systematic uncertainties: [list sources]
   6.4 Construct error budget per [reference to this protocol]

7. ACCEPTANCE CRITERIA
   - chi^2/dof within [0.5, 2.0] for internal consistency
   - Drift rate < [threshold] per hour
   - No more than [X]% outliers by Grubbs test
```

---

## Common LLM Error Patterns

| Error Pattern | LLM Symptom | Detection | Consequence |
|--------------|-------------|-----------|-------------|
| Single-run extrapolation | Reports one measurement as definitive without run-to-run data | Ask: "How many independent runs?" If the answer is 1, the result is anecdotal | Systematic effects hidden by single-run luck |
| Ignoring drift | Averages all readings without checking for time trends | Plot readings vs. time; fit linear trend | Drift biases the mean; underestimates uncertainty |
| Undersampling | Takes 3-5 readings and reports standard error | s/sqrt(N) with N=3 has ~40% uncertainty on the uncertainty itself | Reported uncertainty is unreliable; confidence intervals are meaningless |
| Conflating precision and accuracy | Reports small standard error as evidence of correct result | Small scatter does not rule out systematic bias; requires cross-apparatus comparison | Precise but wrong — the most dangerous kind of error |
| Missing environmental controls | Ignores temperature, humidity, vibration effects | Ask for environmental monitoring data; if absent, results may depend on uncontrolled conditions | Irreproducible results that vary with weather, time of day, lab location |
| Protocol-free reproduction | Claims "reproducible" without documenting procedure | Ask for the written protocol; if it exists only in the operator's head, it is not reproducible | Only the original operator can reproduce the result — effectively irreproducible |
| Allan variance misinterpretation | Claims "longer averaging always reduces uncertainty" | Check Allan deviation slope; if positive at long tau, averaging is making things worse | Optimal averaging time exceeded; drift dominates |
| Ignoring operator dependence | Assumes all operators get the same result | Ask if multiple operators have performed the measurement; if not, operator bias is uncharacterized | Results may depend on who runs the experiment |

---

## Worked Example: Measuring Sample Resistivity

**Problem:** Measure the DC electrical resistivity of a copper alloy sample using the four-point probe method. Establish internal consistency, run-to-run reproducibility, and uncertainty budget through 5 independent measurement runs.

### Step 1: Single-Run Internal Consistency (Run 1)

Take 20 repeated resistance readings at fixed probe position and current (100 mA DC):

```
Reading:  1     2     3     4     5     6     7     8     9    10
R (mOhm): 1.2347 1.2351 1.2349 1.2353 1.2348 1.2350 1.2352 1.2346 1.2351 1.2349

Reading: 11    12    13    14    15    16    17    18    19    20
R (mOhm): 1.2350 1.2348 1.2354 1.2349 1.2351 1.2347 1.2350 1.2352 1.2349 1.2351
```

**Statistics:**
- Mean: R_bar = 1.23498 mOhm
- Standard deviation: s = 0.00021 mOhm
- Standard error: s_m = s / sqrt(20) = 0.000047 mOhm

**Drift check:** Linear fit to R vs. reading number gives slope b = 0.000001 mOhm/reading, sigma_b = 0.000002 mOhm/reading. Since |b| < 2*sigma_b, no significant drift detected.

**Outlier check (Grubbs test):** Most extreme reading: R_13 = 1.2354. G = |1.2354 - 1.23498| / 0.00021 = 2.0. Critical value for N=20 at alpha=0.05: G_crit = 2.71. Since G < G_crit, no outliers.

**Internal consistency: PASS**

### Step 2: Run-to-Run Reproducibility (5 Independent Runs)

Each run on a different day, with full instrument warm-up and recalibration:

```
| Run | Date       | T_lab (C) | R_bar (mOhm) | s_m (mOhm) | N_readings |
|-----|------------|-----------|---------------|-------------|------------|
| 1   | 2026-03-01 | 20.3      | 1.23498       | 0.000047    | 20         |
| 2   | 2026-03-03 | 20.1      | 1.23512       | 0.000051    | 20         |
| 3   | 2026-03-05 | 20.5      | 1.23478       | 0.000044    | 20         |
| 4   | 2026-03-08 | 19.8      | 1.23525       | 0.000049    | 20         |
| 5   | 2026-03-10 | 20.4      | 1.23489       | 0.000046    | 20         |
```

**Weighted mean:** R_wm = 1.23500 mOhm

**Chi-squared consistency test:**
```
chi^2 = sum((R_i - R_wm)^2 / s_m_i^2)
      = (0.02/0.047)^2 + (0.12/0.051)^2 + (0.22/0.044)^2 + (0.25/0.049)^2 + (0.11/0.046)^2
      = 0.18 + 5.53 + 25.0 + 26.0 + 5.72
      = 62.4
```

With 4 degrees of freedom, chi^2/dof = 15.6. **This is far too large** — run-to-run scatter exceeds single-run uncertainty by a factor of ~4.

### Step 3: Diagnose Excess Scatter

The run-to-run variation (standard deviation of the 5 means: s_runs = 0.00018 mOhm) is much larger than the typical single-run standard error (~0.000047 mOhm). There is a systematic effect varying between runs.

**Temperature correlation:**
Plot R_bar vs. T_lab:

```
T (C):    19.8   20.1   20.3   20.4   20.5
R (mOhm): 1.23525 1.23512 1.23498 1.23489 1.23478
```

Strong negative correlation: r = -0.99. The temperature coefficient is:

```
c_T = Delta R / Delta T = (1.23478 - 1.23525) / (20.5 - 19.8) = -0.00067 mOhm/C
```

This corresponds to a temperature coefficient of alpha = c_T / R = -0.00054 /C, which is reasonable for copper alloys (bulk copper: +0.0039 /C for resistivity; this alloy has the opposite sign at this composition, consistent with Nordheim's rule near the resistivity maximum).

### Step 4: Apply Temperature Correction

Correct all readings to the reference temperature T_ref = 20.0 C:

```
R_corr = R_meas + c_T * (T_ref - T_meas)
```

```
| Run | R_meas (mOhm) | T_meas (C) | R_corr (mOhm) | s_m (mOhm) |
|-----|---------------|------------|----------------|-------------|
| 1   | 1.23498       | 20.3       | 1.23518        | 0.000047    |
| 2   | 1.23512       | 20.1       | 1.23519        | 0.000051    |
| 3   | 1.23478       | 20.5       | 1.23512        | 0.000044    |
| 4   | 1.23525       | 19.8       | 1.23512        | 0.000049    |
| 5   | 1.23489       | 20.4       | 1.23516        | 0.000046    |
```

**After correction:** s_runs = 0.000034 mOhm, now comparable to single-run uncertainties. Chi^2/dof = 1.8 — acceptable.

### Step 5: Allan Variance Analysis

From the 100 total readings (5 runs x 20), compute Allan deviation at different averaging times (each reading taken at 5 s intervals within a run):

```
| tau (s) | sigma_A (mOhm) | Slope (log-log) |
|---------|----------------|-----------------|
| 5       | 0.00021        | ---             |
| 10      | 0.00015        | -0.49           |
| 25      | 0.00010        | -0.46           |
| 50      | 0.000075       | -0.42           |
| 100     | 0.000065       | -0.21 (flattening) |
```

The Allan deviation decreases as tau^{-1/2} (white noise) up to ~50 s, then flattens — indicating the onset of flicker noise. **Optimal averaging time: ~60-100 s per reading.** Averaging beyond 100 s provides diminishing returns.

### Step 6: Construct Error Budget and Final Result

Convert resistance to resistivity using sample geometry: rho = R * A / L, where A = cross-sectional area, L = probe spacing.

```
Resistivity at 20.0 C: rho = 1.7003 x 10^{-8} Ohm.m

Error budget:
  Statistical (std error of corrected mean):      +/- 0.0015 x 10^{-8}   (0.09%)
  Temperature correction residual:                +/- 0.0010 x 10^{-8}   (0.06%)
  Probe geometry (caliper uncertainty):            +/- 0.0085 x 10^{-8}   (0.50%)
  Current source accuracy (0.02%):                 +/- 0.0034 x 10^{-8}   (0.20%)
  Contact resistance (4-wire, verified < 1 mOhm): +/- 0.0005 x 10^{-8}   (0.03%)
  ---------------------------------------------------------------
  Total (quadrature):                              +/- 0.0095 x 10^{-8}   (0.56%)

Final result: rho = (1.700 +/- 0.010) x 10^{-8} Ohm.m at 20.0 C
```

### Verification Checks

- **Dimensional check:** [R] = Ohm, [A] = m^2, [L] = m, so [rho] = Ohm.m. Correct.
- **Magnitude check:** Pure copper resistivity is 1.68 x 10^{-8} Ohm.m at 20 C. Our alloy sample at 1.70 x 10^{-8} Ohm.m is slightly higher, consistent with alloying increasing resistivity (Nordheim's rule). PASS.
- **Dominant uncertainty:** Probe geometry (0.50%) dominates. This is typical for four-point probe measurements — to improve, use a more precisely machined probe fixture or a different method (e.g., van der Pauw).
- **Temperature sensitivity identified and corrected:** The initial chi^2/dof = 15.6 was resolved by identifying and correcting a temperature-dependent systematic, reducing to chi^2/dof = 1.8. The correction is physically motivated and the coefficient is consistent with known material properties.
- **Allan variance confirms averaging strategy:** White noise regime extends to ~60 s, consistent with the 100 s total acquisition time per run (20 readings at 5 s). No evidence of drift within runs.

---

## Verification Checklist

Before finalizing any physical measurement result:

- [ ] At least 10 repeated readings taken per measurement point (Step 1a)
- [ ] Chi-squared consistency test performed on within-run readings (Step 1b)
- [ ] Time-series plotted and drift assessed with linear fit (Step 1c)
- [ ] Outlier detection applied with documented criterion (Step 1d)
- [ ] At least 3 independent runs performed on different occasions (Step 2a)
- [ ] Run-to-run consistency tested (chi^2/dof near 1) (Step 2b)
- [ ] Allan variance computed to identify optimal averaging time (Step 2c)
- [ ] Excess scatter diagnosed and attributed (Step 2d)
- [ ] At least 2 independent operators for critical measurements (Step 3b)
- [ ] Environmental variables monitored and sensitivity coefficients measured (Step 4b)
- [ ] Environmental corrections applied where significant (Step 4d)
- [ ] Cross-apparatus comparison performed for published results (Step 5a)
- [ ] E_n numbers computed for interlaboratory comparisons (Step 5b)
- [ ] Complete measurement protocol documented (Step 6a)
- [ ] Error budget constructed with all sources identified (Worked Example Step 6)
- [ ] Dominant uncertainty source identified and mitigation path noted
- [ ] Final result includes value, uncertainty, conditions (temperature, pressure), and method

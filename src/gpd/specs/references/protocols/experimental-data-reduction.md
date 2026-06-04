---
load_when:
  - "background subtraction"
  - "dead time"
  - "pile-up"
  - "efficiency correction"
  - "detector response"
  - "data reduction"
  - "raw counts"
  - "calibration correction"
  - "acceptance correction"
  - "detector efficiency"
  - "spectral analysis"
  - "count rate"
  - "instrument data"
  - "experimental data"
tier: 2
context_cost: medium
---

# Experimental Data Reduction Protocol

Experimental data reduction is the chain of corrections that transforms raw instrument output into physics-ready results. Every correction introduces systematic uncertainty, and every omitted correction introduces bias. LLMs are particularly dangerous here because they often treat data reduction as simple arithmetic — subtract background, divide by efficiency, done — while ignoring the order-dependent, correlated, and nonlinear nature of real corrections.

**Core discipline:** Raw detector counts are not physics. The path from counts to a cross section, flux, or spectrum requires dead-time correction, background subtraction, efficiency correction, acceptance correction, and calibration — in the correct order, with uncertainties propagated through every step. Getting one step wrong can shift a result by factors, not percents.

## Related Protocols

- `statistical-inference.md` — Likelihood construction, hypothesis testing, and upper limits on corrected data; systematic uncertainties as nuisance parameters
- `numerical-computation.md` — Convergence testing for unfolding algorithms and numerical calibration interpolation
- `monte-carlo.md` — Monte Carlo simulation of detector response, acceptance, and background estimation
- `order-of-limits.md` — Non-commuting limits in extrapolation (e.g., bin width → 0 vs. statistics → ∞)

---

## Step 1: Raw Data Inspection

Before applying any correction, examine the raw data for pathologies that no correction can fix.

### 1a. Data quality checks

| Check | What to Look For | Action if Found |
|-------|-----------------|-----------------|
| **Saturation** | Flat-topped peaks, count rate plateau at high flux | Flag saturated regions; do NOT correct — re-measure at lower flux or shorter exposure |
| **Gaps and dropouts** | Missing time bins, dead channels, zero-count regions | Distinguish real zeros from instrumental gaps; mask dead channels |
| **Rate anomalies** | Sudden jumps or drops in count rate vs. time | Check for beam trips, HV trips, source changes; excise affected intervals |
| **Overflow/underflow** | ADC overflow bins, negative values from pedestal subtraction | Identify dynamic range limits; exclude overflowed bins |
| **Periodic artifacts** | Peaks at power-line frequency (50/60 Hz), microphonics | Identify and filter; do NOT subtract — filtering is the correct treatment |
| **Baseline drift** | Slow variation in pedestal or background level | Fit time-dependent baseline before peak extraction |

### 1b. Data inventory

Record and verify BEFORE proceeding:

- [ ] Total live time (not wall-clock time — see Step 2)
- [ ] Number of channels, bins, or pixels and their calibration
- [ ] Trigger conditions and prescale factors
- [ ] Environmental conditions (temperature, pressure, magnetic field) that affect detector response
- [ ] Normalization quantities (beam current integral, monitor counts, luminosity)

**Common LLM Error:** Treating the data file as ground truth. Raw data files often contain known artifacts (hot pixels, dead channels, pedestal offsets) documented in run logs. Always ask: "What does the run log say about this data?"

---

## Step 2: Dead Time and Pile-up Corrections

Dead time is the interval after each detected event during which the detector cannot register another event. Pile-up occurs when multiple events overlap within the detector's resolving time.

### 2a. Dead-time models

| Model | Formula | When It Applies |
|-------|---------|-----------------|
| **Non-extending (paralyzable)** | n_true = n_obs / (1 - n_obs × tau) | Detector resets after fixed time tau regardless of new events (e.g., Geiger-Mueller counter, scaler with fixed dead time) |
| **Extending (non-paralyzable)** | n_true = -ln(1 - n_obs × tau) / tau | Each new event during dead time restarts the dead period (e.g., pulse-shaping amplifier, retriggerable electronics) |
| **Generalized** | Numerical solution required | Real detectors are often intermediate between the two extremes |

where n_obs is the observed count rate (counts/time), n_true is the true count rate, and tau is the dead time per event.

**CRITICAL:** The non-extending and extending formulas give the same result to first order in n_obs × tau, but diverge dramatically at high rates:

- Non-extending: n_obs → 1/tau as n_true → infinity (saturation)
- Extending: n_obs → 0 as n_true → infinity (paralysis — detector appears dead at very high rates)

If n_obs × tau > 0.2, the distinction matters and must be determined empirically (e.g., two-source method).

### 2b. Pile-up correction

For detectors that integrate energy (e.g., scintillators, semiconductor detectors):

| Effect | Consequence | Correction |
|--------|-------------|------------|
| **Pulse pile-up** | Two events merge into one event with summed energy | Measure pile-up spectrum shape; subtract or deconvolve |
| **Tail pile-up** | Event sits on the tail of a previous pulse | Baseline restoration in signal processing; correct offline via pulse shape analysis |
| **Random summing** | Two uncorrelated events produce a sum peak | Sum peak rate = 2 × tau_pile × n₁ × n₂ where n₁, n₂ are individual peak rates |

### 2c. Dead-time uncertainty

The dead time tau itself has uncertainty. Propagate it:

```
sigma(n_true) / n_true = sqrt[ (sigma(n_obs)/n_obs)^2 + (n_true × sigma(tau))^2 / (1 - n_obs × tau)^2 ]
```

(for the non-extending model). At high rates, the second term dominates — the dead-time uncertainty, not counting statistics, limits the measurement.

**Verification checks:**
- [ ] Dead-time model (extending vs non-extending) is stated and justified
- [ ] Fractional dead time (n_obs × tau) is reported; if > 20%, model choice is validated empirically
- [ ] Corrected rate is higher than observed rate (dead time always causes undercounting)
- [ ] At low rates (n_obs × tau << 1), correction is negligible (sanity check)

---

## Step 3: Background Estimation and Subtraction

### 3a. Background estimation methods

| Method | How It Works | When to Use | Danger |
|--------|-------------|-------------|--------|
| **Sideband** | Measure in signal-free regions adjacent to the signal window | Clean sidebands exist; background shape is smooth | Assumes background shape in signal region matches sidebands |
| **Same detector, source removed** | Dedicated background run with identical conditions minus the source | Source can be removed cleanly | Conditions may differ (beam-off backgrounds differ from beam-on) |
| **Monte Carlo** | Simulate background processes and normalize to data | Complex backgrounds with multiple components | Simulation must be validated against data in control regions |
| **Analytical model** | Fit a functional form (polynomial, exponential) in sidebands, extrapolate | Background has known functional form | Model choice biases the result; check with alternative models |
| **Time-correlated** | Use timing to separate prompt signal from delayed background | Signal and background have different time profiles | Requires good timing resolution and understanding of all timing components |

### 3b. Signal-to-background ratio

The signal-to-background ratio (S/B) determines the sensitivity of the result to background estimation errors:

```
sigma(S) / S = sqrt[ 1/S + (1 + 1/alpha)/(S × (1 + 1/(S/B))) ]
```

where alpha = T_signal / T_background is the ratio of on-source to off-source exposure times.

| S/B Regime | Implication |
|-----------|-------------|
| S/B > 10 | Background subtraction uncertainty is subdominant; focus on other systematics |
| 1 < S/B < 10 | Background method matters; use multiple methods and compare |
| S/B < 1 | Result is background-dominated; background systematic is likely the leading uncertainty |
| S/B < 0.1 | Extreme care required; result is essentially a small difference of large numbers |

### 3c. Negative bins after subtraction

After background subtraction, some bins may have negative content. This is physically expected from statistical fluctuations.

**Wrong:** Setting negative bins to zero. This biases the total integral upward.

**Correct:** Keep negative bins. They are valid statistical fluctuations. When fitting the subtracted spectrum, use the full Poisson likelihood (or the correct likelihood for the difference of two Poisson-distributed quantities), not a Gaussian approximation that breaks for small or negative values.

For the difference of two Poisson observations (N_on events in signal region, N_off events in background region with normalization alpha):

```
N_signal = N_on - alpha × N_off
Var(N_signal) = N_on + alpha^2 × N_off
```

**Verification checks:**
- [ ] Background estimation method is stated and justified
- [ ] Signal-to-background ratio is reported
- [ ] Background systematic uncertainty is estimated (vary method, vary sideband region, vary fit model)
- [ ] Negative bins after subtraction are preserved (not clipped to zero)
- [ ] Control regions validate that the background model describes data outside the signal window

---

## Step 4: Efficiency and Acceptance Corrections

### 4a. Types of efficiency

| Efficiency | Definition | Typical Determination |
|-----------|-----------|----------------------|
| **Intrinsic detector efficiency** | P(detector registers event \| event hits detector) | Calibration source, known cross section, or Monte Carlo |
| **Geometric acceptance** | Fraction of solid angle (or phase space) covered by detector | Geometry calculation or Monte Carlo ray tracing |
| **Trigger efficiency** | P(event passes trigger \| event recorded by detector) | Tag-and-probe with unbiased triggers |
| **Reconstruction efficiency** | P(event passes analysis cuts \| event triggered) | Monte Carlo with data-driven corrections |
| **Combined efficiency** | Product of all above (only if uncorrelated) | Full Monte Carlo chain; verify factorization |

### 4b. Applying efficiency corrections

The corrected count in bin i is:

```
N_corrected_i = N_observed_i / epsilon_i
```

where epsilon_i is the total efficiency in bin i.

**CRITICAL:** Efficiency is generally a function of the measured quantity (energy, angle, position). Using a single average efficiency is wrong unless the efficiency is flat over the relevant range.

**Uncertainty propagation:**

```
sigma(N_corrected_i) / N_corrected_i = sqrt[ (sigma(N_obs_i)/N_obs_i)^2 + (sigma(epsilon_i)/epsilon_i)^2 ]
```

This is valid ONLY if the efficiency uncertainty is uncorrelated between bins. If the efficiency uncertainty is correlated (e.g., from a common normalization), it must be treated as a correlated systematic — not added in quadrature bin-by-bin.

### 4c. Unfolding vs. bin-by-bin correction

When the detector response smears events between bins (finite energy resolution, angular resolution), a simple bin-by-bin efficiency correction is insufficient:

| Method | When to Use | Complexity |
|--------|-------------|------------|
| **Bin-by-bin correction** | Resolution much smaller than bin width; minimal bin migration | Simple division |
| **Matrix inversion** | Small number of bins; well-conditioned response matrix | Direct but amplifies statistical noise |
| **Iterative Bayesian (D'Agostini)** | Moderate migration; regularization needed | Iterative; converges but can over-regularize |
| **SVD unfolding** | Large matrix; need to control regularization explicitly | Truncate small singular values; regularization parameter must be chosen |
| **TUnfold / Tikhonov** | Standard in particle physics | Curvature regularization; L-curve or scan for regularization strength |

**Common LLM Error:** Applying bin-by-bin efficiency correction when there is significant bin migration. If the detector resolution is comparable to or larger than the bin width, events migrate between bins and bin-by-bin correction gives a biased result. Check the response matrix diagonal dominance before choosing the method.

**Verification checks:**
- [ ] Efficiency is determined as a function of the relevant kinematic variables (not a single number)
- [ ] Efficiency uncertainty is separated into correlated and uncorrelated components
- [ ] Bin migration is assessed; if resolution ~ bin width, unfolding is used instead of bin-by-bin correction
- [ ] Corrected result does not have unphysical features (negative values, impossible spikes) from noise amplification in unfolding
- [ ] Closure test: apply full correction chain to Monte Carlo pseudo-data and recover the known input

---

## Step 5: Calibration Application

### 5a. Types of calibration

| Calibration | What It Maps | Common Sources |
|------------|-------------|---------------|
| **Energy calibration** | ADC channel → energy (keV, MeV) | Known radioactive lines, X-ray fluorescence, beam energy |
| **Wavelength calibration** | Pixel/channel → wavelength (nm, Angstrom) | Spectral lamps (Hg, Ar, Ne), laser lines |
| **Time calibration** | TDC channel → time (ns, ps) | Precision pulser, known time-of-flight distances |
| **Position calibration** | Channel/pixel → spatial coordinate | Survey data, alignment tracks, known geometry |
| **Gain calibration** | Equalize response across channels/pixels | Flat-field illumination, pulser scan |

### 5b. Interpolation between calibration points

Calibration is measured at discrete points. Between them:

| Method | When Appropriate | Danger |
|--------|-----------------|--------|
| **Linear interpolation** | Calibration is nearly linear between points | Introduces piecewise-linear artifacts |
| **Polynomial fit** | Smooth, monotonic calibration curve | High-degree polynomials oscillate (Runge phenomenon) |
| **Spline** | Many calibration points, smooth curve expected | Can oscillate between sparse points |
| **Physics-based model** | Calibration follows a known functional form (e.g., Bragg equation, Birks' law) | Model must be validated; don't extrapolate beyond calibration range |

**CRITICAL: Never extrapolate calibration beyond the measured range.** If data extends beyond the last calibration point, the calibration is unknown there. Flag these regions, do not silently extrapolate.

### 5c. Calibration uncertainty propagation

The calibration introduces correlated uncertainty across the spectrum. If the energy calibration is E = a + b × ch + c × ch²:

```
sigma(E)^2 = sigma(a)^2 + ch^2 × sigma(b)^2 + ch^4 × sigma(c)^2
             + 2 × ch × cov(a,b) + 2 × ch^2 × cov(a,c) + 2 × ch^3 × cov(b,c)
```

This uncertainty is correlated between bins — a shift in the calibration parameter moves ALL bins coherently. Treat as a correlated systematic, not an independent per-bin uncertainty.

### 5d. Time-dependent calibration (gain drift)

Detectors drift. If calibration changes during the measurement:

1. Divide data into time intervals short enough that calibration is stable within each interval
2. Apply per-interval calibration
3. Combine calibrated spectra (not raw spectra)

**Verification checks:**
- [ ] Calibration points span the full data range (no extrapolation)
- [ ] Residuals of calibration fit are small and show no systematic pattern
- [ ] Calibration uncertainty is propagated as a correlated systematic
- [ ] Time stability of calibration is verified (compare start-of-run to end-of-run calibration)
- [ ] Non-linearity is characterized if relevant (differential vs. integral non-linearity)

---

## Step 6: Systematic Uncertainty Propagation

### 6a. Tracking uncertainties through the correction chain

Each correction step introduces uncertainty. The final uncertainty is NOT the quadrature sum of individual step uncertainties unless the steps are uncorrelated — and they rarely are.

**Correct approach:** Propagate uncertainties through the full chain by varying each source:

1. Shift dead-time parameter by +/- 1 sigma; redo Steps 2-5; record variation in final result
2. Shift background model by +/- 1 sigma; redo Steps 3-5; record variation
3. Shift efficiency by +/- 1 sigma; redo Steps 4-5; record variation
4. Shift calibration by +/- 1 sigma; redo Step 5; record variation

The total systematic uncertainty is obtained from the covariance matrix of all variations.

### 6b. Correlation structure

| Correlation Type | Example | Treatment |
|-----------------|---------|-----------|
| **Bin-to-bin correlated** | Overall normalization, calibration shift | Single nuisance parameter; shifts all bins together |
| **Bin-to-bin anti-correlated** | Calibration tilt (one end up, other down) | Shape nuisance parameter |
| **Bin-to-bin uncorrelated** | Statistical efficiency uncertainty per bin | Add in quadrature per bin |
| **Between-dataset correlated** | Common calibration source, same detector | Correlated nuisance parameter in combined fit |

### 6c. Uncertainty budget table

Present the final uncertainty budget as a table:

| Source | Type | Magnitude (%) | Correlation |
|--------|------|---------------|-------------|
| Counting statistics | Statistical | varies by bin | Uncorrelated |
| Dead time (tau) | Systematic | X% | Correlated (normalization) |
| Background model | Systematic | X% | Partially correlated |
| Detector efficiency | Systematic | X% | Correlated + uncorrelated components |
| Energy calibration | Systematic | X% | Correlated (shape) |
| Acceptance | Systematic | X% | Correlated |
| **Total** | | X% | From full covariance matrix |

**Common LLM Error:** Quoting a single total uncertainty without separating statistical and systematic components, and without reporting correlations. A result of "42.3 +/- 2.1" is incomplete — is the 2.1 statistical, systematic, or combined? Are there correlations with other measurements?

**Verification checks:**
- [ ] Each correction step has an associated systematic uncertainty
- [ ] Correlations between uncertainty sources are identified
- [ ] Full covariance matrix is constructed (not just diagonal errors)
- [ ] Dominant uncertainty is identified and discussed
- [ ] Uncertainty budget table is provided

---

## Step 7: Final Result Extraction

### 7a. Combining all corrections

The full correction chain, applied in order:

```
N_physics = (N_raw / LiveTimeFraction - B) / (epsilon × A × Phi)
```

where:
- N_raw = raw counts
- LiveTimeFraction = live time / total time (from dead-time correction)
- B = background (estimated and subtracted)
- epsilon = detection efficiency
- A = geometric acceptance
- Phi = normalization (beam flux, luminosity, monitor counts)

**CRITICAL: Order matters.** Dead-time correction must precede background subtraction (background rates are also affected by dead time). Efficiency correction must follow background subtraction (background events have different efficiency than signal events). Getting the order wrong introduces bias.

### 7b. Correct ordering of corrections

| Order | Step | Why This Order |
|-------|------|---------------|
| 1 | Dead-time correction | Affects ALL events equally (detector effect, not physics) |
| 2 | Background subtraction | Background rate is now correctly estimated (after dead-time correction) |
| 3 | Efficiency correction | Applies only to signal events (background already subtracted) |
| 4 | Acceptance correction | Geometric factor for signal |
| 5 | Calibration | Converts to physical units |
| 6 | Normalization | Divide by flux/luminosity to get cross section, yield, etc. |

### 7c. Reporting format

Final results must include:

1. **Central value** with statistical and systematic uncertainties separated: sigma_stat and sigma_syst
2. **Bin-by-bin values** with the full covariance matrix (or at minimum, a breakdown of correlated vs. uncorrelated uncertainties)
3. **Data tables** in machine-readable format (HEPData, CSV) for comparison and reuse
4. **All corrections applied**, listed explicitly with their magnitudes
5. **Assumptions** that went into each correction (detector model, background model, efficiency model)

### 7d. Comparison-ready output

For the result to be usable by others:

- [ ] Physical units are stated and consistent
- [ ] Bin centers, edges, and widths are specified (not just centers)
- [ ] Normalization convention is stated (per unit energy, per unit solid angle, per nucleon, etc.)
- [ ] Is the result per-bin or integrated? Per-event or rate?
- [ ] Corrections for detector effects are applied (result is at "truth level," not "detector level")

---

## Common LLM Error Patterns (Cross-Referenced)

| Error Pattern | LLM Symptom | Detection | Correct Treatment |
|--------------|-------------|-----------|-------------------|
| Wrong dead-time model | Applies non-extending formula to extending detector (or vice versa) | Check if detector resets or extends dead time on new event; verify with two-source test | Identify detector type from documentation; at high rates, use empirical calibration |
| Background subtracted before dead-time correction | Subtracts background from raw counts | Check order of operations; dead time affects signal AND background equally | Always correct for dead time first; then subtract background from dead-time-corrected rates |
| Average efficiency used for non-flat efficiency | Divides total counts by a single efficiency number | Check if efficiency varies over the spectrum; plot epsilon(E) | Use bin-by-bin efficiency; if migration is significant, use unfolding |
| Calibration extrapolated beyond range | Applies calibration polynomial outside measured calibration points | Check if data range exceeds calibration range | Flag uncalibrated regions; do not silently extrapolate |
| Negative bins clipped to zero | Sets negative post-subtraction bins to zero "because counts can't be negative" | Check if any bins were modified after subtraction | Keep negative bins; they are valid statistical fluctuations; use correct likelihood |
| Correlated systematics added in quadrature | Treats calibration uncertainty as independent per bin | Check if uncertainty source (calibration, normalization) affects all bins | Treat as correlated nuisance parameter; propagate through full chain |
| Efficiency applied to background | Divides total (signal + background) by signal efficiency | Check if efficiency correction was applied before or after background subtraction | Subtract background first; then apply signal efficiency to the subtracted signal |
| Unfolding without regularization | Inverts response matrix directly | Check for noise amplification and oscillating solution | Use regularized unfolding (SVD, Tikhonov); validate regularization strength with L-curve or closure test |

---

## Worked Example: Gamma-Ray Counting Experiment

**Problem:** A gamma-ray detector counts events from a radioactive source. In a T = 300 s measurement, the detector registers N_raw = 45,000 counts in the photopeak region of interest. A background measurement (source removed, same geometry) of T_bg = 600 s gives N_bg = 12,000 counts in the same region. The detector has a dead time of tau = 5 microseconds (non-extending type). The photopeak efficiency at this energy is epsilon = 0.23 +/- 0.01. What is the source activity (decays/s) in this photopeak?

### Wrong Approach (Common LLM Errors)

"The signal count is 45,000 - 12,000/2 = 39,000 events in 300 s. The activity is 39,000 / (300 x 0.23) = 565 decays/s. The uncertainty is sqrt(45,000) / (300 x 0.23) = 3.1 decays/s."

**Why this is wrong:**

1. **Dead-time correction omitted.** At n_obs = 45,000/300 = 150 Hz, the fractional dead time is n_obs x tau = 150 x 5e-6 = 7.5 x 10^-4 — small here, but the approach doesn't even check.
2. **Background scaled by time ratio but dead-time correction not applied to background rate.** The background measurement also has dead time.
3. **Uncertainty uses sqrt(N_raw) only** — ignores background subtraction uncertainty, efficiency uncertainty, and dead-time uncertainty.
4. **Efficiency uncertainty not propagated** — sigma(epsilon)/epsilon = 0.01/0.23 = 4.3%, which dominates over the statistical error.

### Correct Approach

**Step 1: Dead-time correction (both signal and background measurements)**

Signal measurement:
```
n_obs_signal = 45000 / 300 = 150.0 Hz
n_true_signal = 150.0 / (1 - 150.0 x 5e-6) = 150.0 / 0.99925 = 150.11 Hz
N_corrected_signal = 150.11 x 300 = 45,034 counts
```

Background measurement:
```
n_obs_bg = 12000 / 600 = 20.0 Hz
n_true_bg = 20.0 / (1 - 20.0 x 5e-6) = 20.0 / 0.99990 = 20.002 Hz
N_corrected_bg = 20.002 x 600 = 12,001 counts
```

Dead-time correction is small here (0.075% for signal, 0.01% for background) but must be checked systematically — at higher rates it becomes dominant.

**Step 2: Background subtraction**

Scale background to signal measurement time:
```
alpha = T_signal / T_bg = 300 / 600 = 0.5
N_signal = N_corrected_signal - alpha x N_corrected_bg
         = 45034 - 0.5 x 12001 = 45034 - 6000.5 = 39,033.5 counts
```

Variance (Poisson statistics on both measurements):
```
Var(N_signal) = N_corrected_signal + alpha^2 x N_corrected_bg
              = 45034 + 0.25 x 12001 = 45034 + 3000.3 = 48,034
sigma_stat(N_signal) = sqrt(48034) = 219.2 counts
```

Signal-to-background ratio: S/B = 39034 / 6001 = 6.5 (comfortable regime).

**Step 3: Efficiency correction and activity**

```
Activity = N_signal / (T_signal x epsilon)
         = 39034 / (300 x 0.23) = 39034 / 69 = 565.7 decays/s
```

**Step 4: Full uncertainty propagation**

Statistical uncertainty:
```
sigma_stat(A) = sigma_stat(N_signal) / (T x epsilon) = 219.2 / 69 = 3.2 decays/s
```

Efficiency systematic:
```
sigma_eff(A) = A x sigma(epsilon)/epsilon = 565.7 x 0.01/0.23 = 24.6 decays/s
```

Dead-time systematic (assume sigma(tau) = 0.5 microseconds):
```
Propagate through the full chain: shift tau by +/- 0.5 us, redo Steps 1-3.
At these low rates, the effect is < 0.04 decays/s — negligible.
```

**Step 5: Final result**

```
Activity = 565.7 +/- 3.2 (stat) +/- 24.6 (syst) decays/s
```

The efficiency uncertainty (4.3%) dominates over counting statistics (0.56%). Improving the measurement precision requires better efficiency calibration, not longer counting time.

**Step 6: Verification**

- [ ] **Dimensional check:** [counts] / ([s] x [dimensionless]) = [counts/s] = [decays/s] (with efficiency as probability) ✓
- [ ] **Limiting case (no background):** If N_bg = 0, result is 45034 / 69 = 652.7 decays/s. With background subtracted, 565.7 < 652.7 ✓
- [ ] **Limiting case (perfect efficiency):** If epsilon = 1, activity = 39034 / 300 = 130.1 decays/s. Since epsilon = 0.23 < 1, true activity = 130.1 / 0.23 = 565.7 > 130.1 ✓ (efficiency correction increases the result, as it must)
- [ ] **Limiting case (no dead time):** At these low rates, dead-time correction is < 0.1% — result barely changes ✓
- [ ] **Physical sense:** 566 decays/s at 23% efficiency gives ~130 detected events/s, consistent with 150 Hz observed (the rest is background at ~20 Hz) ✓
- [ ] **Dominant uncertainty identified:** Efficiency (4.3%) >> statistics (0.56%) >> dead time (negligible). To improve, calibrate the detector efficiency more precisely ✓

---

## Verification Checklist

Before finalizing any data reduction result:

- [ ] Raw data inspected for saturation, gaps, anomalies, and baseline drift
- [ ] Live time (not wall-clock time) used for rate calculations
- [ ] Dead-time model identified (extending vs non-extending) and justified
- [ ] Dead-time correction applied BEFORE background subtraction
- [ ] Fractional dead time reported; if > 20%, model validated empirically
- [ ] Background estimation method stated and justified
- [ ] Background systematic estimated by varying method/model/region
- [ ] Signal-to-background ratio reported
- [ ] Negative bins after subtraction preserved (not clipped to zero)
- [ ] Efficiency determined as function of relevant variables (not single average)
- [ ] Bin migration assessed; unfolding used if resolution ~ bin width
- [ ] Calibration spans the full data range (no extrapolation)
- [ ] Calibration uncertainty propagated as correlated systematic
- [ ] Corrections applied in correct order (dead time → background → efficiency → acceptance → calibration → normalization)
- [ ] Each systematic uncertainty source identified with magnitude
- [ ] Correlations between systematic sources documented
- [ ] Uncertainty budget table provided with statistical and systematic components separated
- [ ] Final result includes full covariance matrix or correlation information
- [ ] Closure test performed on Monte Carlo pseudo-data (correction chain recovers known input)
- [ ] Result reported in physical units with explicit normalization convention

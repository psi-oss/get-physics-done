---
load_when:
  - "Bayesian inference"
  - "parameter estimation"
  - "likelihood"
  - "posterior"
  - "chi-squared"
  - "confidence interval"
  - "credible interval"
  - "hypothesis test"
  - "p-value"
  - "model selection"
  - "upper limit"
  - "Feldman-Cousins"
  - "profile likelihood"
  - "systematic uncertainty"
  - "Bayes factor"
  - "nested sampling"
  - "maximum likelihood"
  - "Fisher information"
  - "goodness of fit"
tier: 2
context_cost: medium
---

# Statistical Inference Protocol for Physics

Statistical inference is where physics meets data. Every experimental result, observational constraint, and phenomenological fit depends on correct statistical methodology. LLMs are particularly dangerous here because statistical reasoning is subtle — a plausible-sounding but wrong statistical statement can invalidate an entire analysis.

**Core discipline:** The difference between "we discovered a new particle" and "we had a statistical fluctuation" is often a factor of 2 in how the significance was computed. Every step below exists because statisticians and physicists have made these errors in published papers.

## Related Protocols

- `numerical-computation.md` — Convergence testing for MCMC chains and numerical integration
- `monte-carlo.md` — MCMC sampling algorithms (Metropolis, cluster updates) for simulation; this protocol covers MCMC for inference
- `order-of-limits.md` — Non-commuting limits in asymptotic statistics (large sample → continuous, Gaussian → Poisson transitions)
- `random-matrix-theory.md` — RMT distributions for spectral statistics, Tracy-Widom for extreme eigenvalues, Marcenko-Pastur for covariance matrices

---

## Step 1: Identify the Statistical Framework

Before any calculation, explicitly state which statistical framework is being used:

| Framework | When to Use | Key Quantity | Interpretation |
|-----------|------------|--------------|----------------|
| **Frequentist** | Pre-specified hypothesis test, coverage guarantee needed | p-value, confidence interval | "If we repeated the experiment N times, X% of intervals would contain the true value" |
| **Bayesian** | Parameter estimation with prior knowledge, model comparison | Posterior, credible interval, Bayes factor | "Given the data, there is X% probability the parameter lies in this interval" |
| **Information-theoretic** | Model selection, complexity penalty | AIC, BIC, DIC | "This model balances fit quality and complexity" |

**CRITICAL: Never mix frameworks in the same analysis without explicit justification.** Computing a "Bayesian p-value" or interpreting a confidence interval as a probability of the parameter being in the interval are category errors.

### Common LLM Error: Framework Confusion

**Wrong:** "The 95% confidence interval [2.1, 3.7] means there is a 95% probability the true value is between 2.1 and 3.7."

**Correct:** "The 95% confidence interval [2.1, 3.7] means that if we repeated this measurement many times, 95% of the intervals constructed this way would contain the true value. For a probabilistic statement about the parameter, use a Bayesian credible interval with an explicit prior."

---

## Step 2: Likelihood Construction

The likelihood function L(θ|data) = P(data|θ) is the foundation of both frequentist and Bayesian inference.

### 2a. Choose the correct probability model

| Data Type | Correct Distribution | Common LLM Error |
|-----------|---------------------|-------------------|
| Counting events (N < ~20) | **Poisson** | Using Gaussian approximation (√N errors) when N is small |
| Counting with known total | **Binomial** | Using Poisson when the total is fixed |
| Continuous measurements | **Gaussian** (if justified) | Assuming Gaussian without checking (heavy tails, asymmetry) |
| Ratio of counts | **Ratio of Poissons** | Propagating errors as if ratio is Gaussian |
| Histogram with few counts | **Poisson per bin** | Using χ² with Gaussian errors per bin |

### 2b. Handle systematic uncertainties

Systematic uncertainties are NOT additional Gaussian errors added in quadrature. They are nuisance parameters in the likelihood.

**Correct treatment:**

```
L(μ, θ_syst | data) = L_stat(μ, θ_syst | data) × L_constraint(θ_syst)
```

where θ_syst are nuisance parameters and L_constraint encodes what we know about them (calibration measurements, auxiliary data, theoretical constraints).

**Profiling** (frequentist): Maximize L over θ_syst for each value of μ → profile likelihood L_p(μ).
**Marginalization** (Bayesian): Integrate out θ_syst with a prior → marginal posterior P(μ|data).

**Common LLM Error:** Adding systematic and statistical uncertainties in quadrature as if they were independent Gaussian errors. This is only valid when: (a) the systematic is well-modeled as Gaussian, (b) it is uncorrelated with the statistical uncertainty, and (c) the analysis is in the Gaussian regime. In particle physics searches with few events, this is almost never valid.

---

## Step 3: Parameter Estimation

### 3a. Maximum Likelihood Estimation (MLE)

1. Construct -2 ln L(θ) (the negative log-likelihood, factor of 2 by convention)
2. Minimize to find θ_hat (the MLE)
3. Compute the Fisher information matrix: I_ij = -∂²ln L/∂θ_i∂θ_j evaluated at θ_hat
4. Covariance matrix: C = I^{-1}
5. Approximate 1σ errors: σ_i = √(C_ii)

**Verification checks:**
- [ ] The minimum is a true minimum (Hessian is positive definite at θ_hat)
- [ ] The MLE is within the physical region (masses are positive, branching ratios ≤ 1)
- [ ] Profile likelihood contours are smooth (no secondary minima)
- [ ] Fisher information approximation is valid (check by comparing Δ(-2lnL) = 1 contour with the Fisher ellipse)

### 3b. Bayesian Parameter Estimation

1. Specify the prior P(θ) — DOCUMENT the choice and sensitivity to it
2. Compute the posterior P(θ|data) ∝ L(data|θ) × P(θ)
3. Sample from the posterior using MCMC (see Step 5)
4. Report credible intervals (central, highest posterior density, or equal-tailed)

**Prior selection discipline:**

| Prior Type | When Appropriate | Danger |
|-----------|-----------------|--------|
| Flat/uniform | Uninformative, parameter has natural scale | Not invariant under reparameterization |
| Jeffrey's | Maximally uninformative, invariant | Can be improper (non-normalizable) |
| Log-uniform | Scale parameter (mass, cross section) | Zero not included |
| Informative (Gaussian) | Previous measurement constrains parameter | Must cite the source; don't double-count data |
| Truncated | Physical bounds (mass > 0, 0 ≤ p ≤ 1) | Sharp boundaries can create artifacts |

**Common LLM Error:** "We use a flat prior because we have no prior information." A flat prior on θ is NOT flat on f(θ). For example, a flat prior on mass m is an informative prior on m². Always check that results are not dominated by the prior — compare posterior width to prior width.

---

## Step 4: Hypothesis Testing

### 4a. Frequentist Hypothesis Testing

**The Neyman-Pearson framework:**

1. Define H₀ (null hypothesis) and H₁ (alternative)
2. Choose a test statistic t(data)
3. Compute the distribution of t under H₀
4. The p-value = P(t ≥ t_observed | H₀)
5. Compare to significance threshold α (typically 0.05 for evidence, 2.87×10⁻⁷ for discovery in particle physics)

**CRITICAL: The p-value is NOT the probability that H₀ is true.** It is the probability of observing data at least as extreme as what was seen, ASSUMING H₀ is true.

**The look-elsewhere effect (trials factor):**

If you search for a signal at multiple locations (e.g., scanning a mass spectrum for a bump), the probability of finding a fluctuation ANYWHERE increases. The global p-value is:

p_global ≈ p_local × N_trials (Bonferroni, conservative)

or more precisely via the Gross-Vitells formula for continuous search regions:

p_global ≈ p_local + <N(u₀)> × e^{-u₀²/2}

where u₀ is the local significance and <N(u₀)> is the expected number of upward crossings.

**Common LLM Error:** Reporting a local significance of 3.5σ as a discovery without accounting for the look-elsewhere effect. After correction, a local 3.5σ in a wide mass scan might be only 2σ globally.

### 4b. Bayesian Model Comparison

The Bayes factor between models M₁ and M₂:

B₁₂ = P(data|M₁) / P(data|M₂)

where P(data|M) = ∫ L(data|θ,M) P(θ|M) dθ is the evidence (marginal likelihood).

| Bayes Factor | Interpretation |
|-------------|----------------|
| B₁₂ > 100 | Decisive evidence for M₁ |
| 10 < B₁₂ < 100 | Strong evidence for M₁ |
| 3 < B₁₂ < 10 | Substantial evidence for M₁ |
| 1 < B₁₂ < 3 | Weak evidence for M₁ |
| B₁₂ ≈ 1 | Inconclusive |

**Common LLM Error:** Computing the Bayes factor without noting its sensitivity to the prior. The evidence integral ∫ L P(θ) dθ depends on the prior volume — a wider prior penalizes a model even if it fits the data well. This is the Bayesian Occam's razor, but it means the Bayes factor is ONLY meaningful if the priors are physically motivated.

---

## Step 5: MCMC Sampling

When the posterior is high-dimensional or non-Gaussian, sample it with MCMC.

### Convergence diagnostics (MANDATORY — not optional)

| Diagnostic | What It Checks | Threshold |
|-----------|---------------|-----------|
| **Gelman-Rubin R-hat** | Between-chain vs within-chain variance | R-hat < 1.01 for all parameters |
| **Effective sample size (N_eff)** | Independent samples accounting for autocorrelation | N_eff > 100 per parameter (>1000 preferred) |
| **Trace plots** | Visual stationarity of chains | No trends, no stuck periods |
| **Autocorrelation** | Mixing speed | Autocorrelation drops to <0.1 within ~100 steps |

**Common LLM Error:** "We ran 10,000 MCMC steps so we have 10,000 independent samples." NO — with autocorrelation length τ, the effective sample size is N_eff = N / (2τ). For a poorly mixing chain, τ can be 1000+, giving only 5 effective samples from 10,000 steps.

### Algorithm selection

| Algorithm | When to Use | Strengths | Weaknesses |
|-----------|------------|-----------|------------|
| Metropolis-Hastings | Simple, low dimension | Easy to implement | Slow mixing in high dimensions |
| Hamiltonian MC (NUTS) | Moderate to high dimension | Efficient exploration, auto-tuned | Requires gradient of log-posterior |
| Nested sampling | Evidence computation + posterior | Direct evidence estimate | Slower for pure parameter estimation |
| Affine-invariant (emcee) | Moderate dimension, correlated posteriors | No tuning needed, parallelizable | Poor with multimodal distributions |

---

## Step 6: Upper Limits and Sensitivity

When no signal is observed, set an upper limit on the signal strength.

### CLs Method (particle physics standard)

The CLs method modifies the standard frequentist limit to avoid excluding signal hypotheses to which the experiment has no sensitivity:

CLs(μ) = CLs+b(μ) / CLb

where CLs+b = P(q ≥ q_obs | signal + background) and CLb = P(q ≥ q_obs | background only).

The 95% CLs upper limit is the value of μ where CLs = 0.05.

**Common LLM Error:** Using CLs+b directly as the exclusion criterion. This can exclude signal hypotheses even when the experiment has a downward fluctuation in background — the limit is too aggressive and has less than nominal coverage.

### Feldman-Cousins (unified approach)

Constructs confidence intervals that automatically transition from upper limits (no signal) to two-sided intervals (significant signal). Uses likelihood ratio ordering:

R(x|μ) = P(x|μ) / P(x|μ_best)

**When to use:** Non-Gaussian problems near physical boundaries (e.g., neutrino mass, which must be ≥ 0).

---

## Step 7: Model Selection

### Information criteria

| Criterion | Formula | Use When |
|-----------|---------|----------|
| **AIC** | -2 ln L_max + 2k | Large sample, comparing non-nested models |
| **BIC** | -2 ln L_max + k ln(n) | Large sample, penalizes complexity more |
| **DIC** | Effective parameters from posterior | Bayesian, hierarchical models |

where k = number of parameters, n = number of data points.

**Common LLM Error:** Using AIC or BIC when the models are nested. For nested models, use the likelihood ratio test (Wilks' theorem: -2 Δln L follows χ² with Δk degrees of freedom, IF the null hypothesis is not on the boundary of the parameter space).

**Wilks' theorem failure:** If the null hypothesis is on the boundary (e.g., testing whether a mass is zero, or whether a mixing angle is zero), the asymptotic distribution is NOT χ² — it is a mixture of χ² distributions. This is one of the most common errors in BSM physics searches.

---

## Common LLM Error Patterns (Cross-Referenced)

| Error Pattern | LLM Symptom | Detection | Error Class |
|--------------|-------------|-----------|-------------|
| Confidence/credible confusion | States "95% probability parameter is in [a,b]" for a frequentist CI | Check if prior was used; if not, it's a CI not a credible interval | NEW |
| Wrong degrees of freedom | Uses χ²/dof with wrong dof count | Count: dof = N_data - N_parameters. Verify constraints counted | #12 (partial) |
| Poisson treated as Gaussian | Uses √N errors when N < 20 | Check if any bin has < 20 events | NEW |
| Ignoring look-elsewhere | Reports local significance as global | Check if signal location was pre-specified or scanned | NEW |
| Prior-dominated posterior | Posterior width ≈ prior width | Compare posterior to prior; if similar, data is uninformative | NEW |
| Uncoverged MCMC | Reports posterior from short chains | Check R-hat, N_eff, trace plots | #27 (convergence) |
| Wilks' theorem misapplied | Uses χ² distribution at parameter boundary | Check if null hypothesis is interior or boundary | NEW |
| Correlated systematics added in quadrature | Treats correlated systematics as independent | Check correlation matrix; profile or marginalize properly | #12 (partial) |

---

## Worked Example: Counting Experiment with Background

**Problem:** An experiment observes N = 7 events in a signal region. The expected background is b = 3.2 ± 0.5 events. What is the significance of the excess? What is the upper limit on the signal if we don't claim discovery?

### Wrong Approach (Common LLM Error)

"The excess is 7 - 3.2 = 3.8 events. With √7 = 2.65 statistical error, the significance is 3.8/2.65 = 1.4σ."

**Why this is wrong:**
1. Uses √N (Gaussian) errors for N = 7 (should be Poisson)
2. Ignores the systematic uncertainty on the background
3. Significance computation uses the wrong test statistic

### Correct Approach

**Step 1:** Likelihood with Poisson statistics and background uncertainty:

L(μ, b | N, b_obs) = Poisson(N | μ + b) × Gaussian(b_obs | b, σ_b)

where μ is the signal strength, b is the true background (nuisance parameter), b_obs = 3.2 is the background estimate, σ_b = 0.5.

**Step 2:** Profile likelihood ratio test statistic:

q₀ = -2 ln [L(μ=0, b_hat_0) / L(μ_hat, b_hat)]

where (μ_hat, b_hat) is the global MLE and b_hat_0 is the conditional MLE of b with μ fixed to 0.

**Step 3:** Compute numerically:
- Global MLE: μ_hat = 3.72, b_hat = 3.28
- Conditional MLE (μ=0): b_hat_0 = 3.20 (background absorbs nothing; N=7 vs b=3.2)
- L(0, 3.20) = Poisson(7|3.2) × Gaussian(3.2|3.2, 0.5) = 0.0611 × 0.7979 = 0.0488
- L(3.72, 3.28) = Poisson(7|7.0) × Gaussian(3.2|3.28, 0.5) = 0.1490 × 0.7945 = 0.1184
- q₀ = -2 ln(0.0488/0.1184) = -2 × (-0.886) = 1.773

**Step 4:** p-value from asymptotic distribution (Wilks' theorem, boundary case):
- Since μ ≥ 0, the distribution of q₀ under H₀ is ½δ(0) + ½χ²(1)
- p-value = ½ × P(χ²(1) > 1.773) = ½ × 0.183 = 0.092
- Significance ≈ 1.3σ

**Step 5:** Verification
- [ ] **Dimensional check:** All quantities are dimensionless (counts and rates) ✓
- [ ] **Limiting case (large N):** For N → large, this reduces to Gaussian significance (N-b)/√(b+σ²_b) = (7-3.2)/√(3.2+0.25) = 3.8/1.86 = 2.0σ. The exact result (1.3σ) is smaller because Poisson statistics are less significant than Gaussian for small N ✓
- [ ] **Limiting case (σ_b → 0):** Without background uncertainty, Poisson p-value P(N≥7|3.2) = 0.040, significance ≈ 1.8σ. Adding σ_b reduces significance ✓
- [ ] **Physical sense:** 7 events on 3.2 background is a ~2× fluctuation — not dramatic. 1.3σ is reasonable ✓

### Upper Limit (if not claiming discovery)

Using the CLs method with the same profile likelihood framework:

For each signal hypothesis μ:
- Compute CLs+b(μ) = P(q_μ ≥ q_μ_obs | μ+b)
- Compute CLb = P(q_μ ≥ q_μ_obs | b only)
- CLs(μ) = CLs+b / CLb

Scanning μ from 0 to 15, the 95% CLs upper limit is approximately μ < 8.2 events.

**Verification:** The expected upper limit (median, background-only) is ~6.5 events. Observed limit (8.2) is higher because the data fluctuated up. This is consistent — the observed limit should be ≥ expected when data exceeds background.

---

## Verification Checklist

Before finalizing any statistical result:

- [ ] Statistical framework (frequentist/Bayesian) explicitly stated
- [ ] Probability model matches data type (Poisson for counts, Gaussian justified if used)
- [ ] Systematic uncertainties treated as nuisance parameters (not added in quadrature unless justified)
- [ ] For frequentist: p-value correctly interpreted (not probability of hypothesis)
- [ ] For frequentist searches: look-elsewhere effect accounted for
- [ ] For Bayesian: prior explicitly stated and sensitivity checked
- [ ] For MCMC: convergence diagnosed (R-hat < 1.01, N_eff reported)
- [ ] Degrees of freedom correct in χ² tests
- [ ] Wilks' theorem applicability checked (parameter not on boundary)
- [ ] Upper limits use appropriate method (CLs or Feldman-Cousins for bounded parameters)
- [ ] Results compared to expected sensitivity (observed limit vs expected limit)
- [ ] Error bars have correct interpretation (1σ, 2σ, or 68%, 95%)

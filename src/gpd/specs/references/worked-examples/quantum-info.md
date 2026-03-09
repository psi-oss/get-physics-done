# Worked Example: Quantum Information — Surface Code Threshold Under Biased Noise

This demonstrates a complete project lifecycle for a computational quantum error correction project. The project computes the fault-tolerance threshold of the rotated surface code when bit-flip errors are 10x more likely than phase-flip errors, using minimum-weight perfect matching (MWPM) decoding and Monte Carlo sampling with finite-size scaling.

---

## 1. PROJECT.md Example

```markdown
# Threshold Error Rate of the Surface Code Under Biased Noise

## What This Is

Computing the fault-tolerance threshold of the rotated surface code under Z-biased noise with bias ratio eta = p_Z / p_X = 10, using Monte Carlo simulation of phenomenological noise with MWPM decoding. The project maps out the logical error rate as a function of physical error rate for code distances d = 3, 5, 7, 9, extracts the threshold via finite-size scaling collapse, and compares with known results in the unbiased and infinite-bias limits. Target deliverable: a paper suitable for Physical Review A.

## Core Research Question

What is the threshold error rate of the d = 3, 5, 7, 9 rotated surface code under Z-biased noise with eta = 10, decoded by MWPM with bias-aware edge weights?

## Research Questions

### Answered

(None yet — investigate to answer)

### Active

- [ ] What is the numerical value of the threshold p_th for eta = 10?
- [ ] How does MWPM decoder performance change with bias-aware vs bias-unaware edge weights?
- [ ] What is the correlation length exponent nu from scaling collapse?
- [ ] Does the threshold interpolate smoothly between the known unbiased (~1%) and infinite-bias (~50%) limits?

### Out of Scope

- Circuit-level noise modeling — requires detailed gate decomposition; follow-up work
- Color codes or other code families — separate project
- Decoders beyond MWPM (union-find, neural network) — future comparison study
- Non-Pauli noise (amplitude damping, leakage) — different noise framework

## Research Context

### Physical System

Rotated surface code on a 2D square lattice with periodic identification of boundaries. Physical qubits sit on edges of the lattice; X-type stabilizers on vertices, Z-type stabilizers on faces. The code encodes k = 1 logical qubit with n = d^2 physical qubits for code distance d.

### Theoretical Framework

Stabilizer formalism for quantum error correction. The surface code is a CSS code: X and Z errors are decoded independently. The Z-biased noise model assigns different error probabilities to X, Y, and Z Pauli errors: p_X = p_Y = p / (2 + 2*eta), p_Z = eta * p / (2 + 2*eta), where p is the total physical error rate and eta = p_Z / p_X is the bias ratio. Decoding uses MWPM on the syndrome graph with edge weights set by log-likelihood ratios derived from the noise model.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
|-----------|--------|--------|-------|
| Code distance | d | {3, 5, 7, 9} | Governs code size n = d^2 and error suppression |
| Physical error rate | p | 10^{-3} to 10^{-1} | Total Pauli error probability per qubit per cycle |
| Bias ratio | eta | 10 (fixed) | p_Z / p_X; Z errors are 10x more likely than X |
| X error rate | p_X | p / 22 | From p_X = p / (2 + 2*eta) with eta = 10 |
| Z error rate | p_Z | 10p / 22 | From p_Z = eta * p / (2 + 2*eta) with eta = 10 |
| Monte Carlo shots | N_shots | 10^5 per (d, p) pair | Sufficient for < 0.01 statistical uncertainty on p_L |
| Logical error rate | p_L | 10^{-4} to 0.5 | Fraction of trials with logical failure |

### Known Results

- Unbiased surface code threshold (eta = 1): p_th ~ 10.3% for phenomenological noise with optimal decoding (Dennis et al. 2002), ~3.3% for MWPM decoder — [Dennis et al., J. Math. Phys. 43, 4452 (2002)]
- Infinite bias limit (eta -> infinity): p_th ~ 50% (pure Z noise reduces to classical repetition code) — [Tuckett et al., Phys. Rev. Lett. 120, 050505 (2018)]
- Bias eta = 10 with MWPM: p_th estimated at 3-5% range — [Tuckett et al., Phys. Rev. X 9, 041031 (2019)]
- Tailored surface code with coprime lattice dimensions under bias: further threshold improvement — [Tuckett et al., Phys. Rev. Lett. 124, 130501 (2020)]

### What Is New

Independent verification and detailed finite-size scaling analysis of the threshold for the standard rotated surface code at eta = 10 with bias-aware MWPM. Explicit comparison of bias-aware vs bias-unaware decoder edge weights. Publication of the full dataset (logical error rates, scaling parameters) as supplementary material.

### Target Venue

Physical Review A (quantum information section) or Quantum (open access). PRA is the standard venue for computational QEC studies with clear numerical results and established methodology.

### Computational Environment

Local workstation (sufficient for phenomenological noise Monte Carlo with d <= 9). Python with:
- Stim for fast Clifford circuit simulation and stabilizer sampling
- pyMatching for MWPM decoding
- NumPy/SciPy for data analysis and finite-size scaling fits
- Matplotlib for publication figures

## Notation and Conventions

See `.planning/CONVENTIONS.md` for all notation and sign conventions.
See `.planning/NOTATION_GLOSSARY.md` for symbol definitions.

## Unit System

Dimensionless (error probabilities are pure numbers). All quantities are probabilities or ratios of probabilities.

## Requirements

See `.planning/REQUIREMENTS.md` for the detailed requirements specification.

Key requirement categories: SIMU (simulation code), CALC (threshold extraction), VALD (validation against known limits)

## Key References

- [Dennis et al., J. Math. Phys. 43, 4452 (2002)] — Original surface code threshold analysis via random-bond Ising model mapping; establishes the phenomenological noise framework
- [Tuckett et al., Phys. Rev. Lett. 120, 050505 (2018)] — First systematic study of biased noise thresholds for surface codes; introduces the bias parameter eta
- [Tuckett et al., Phys. Rev. X 9, 041031 (2019)] — Comprehensive threshold analysis with MWPM and union-find decoders under biased noise; primary comparison target
- [Fowler et al., Phys. Rev. A 86, 032324 (2012)] — Surface code review with practical MWPM implementation details
- [Higgott, ACM Trans. Quantum Comput. 3, 1-16 (2022)] — PyMatching: efficient MWPM decoder implementation (software reference)

## Constraints

- **Computational**: Maximum d = 9 on local workstation (d = 11+ requires cluster for adequate statistics within reasonable time)
- **Statistical**: Need 10^5 shots per data point minimum for relative uncertainty < 1% on p_L when p_L > 10^{-3}
- **Decoder**: MWPM only (no union-find or ML decoders in this study)
- **Noise model**: Phenomenological noise only (no circuit-level noise, no measurement errors beyond repeated syndrome extraction)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Phenomenological noise model | Simpler than circuit-level, sufficient for threshold comparison | Adopted |
| MWPM decoder | Standard decoder with well-understood performance | Adopted |
| Rotated surface code | More efficient than unrotated (n = d^2 vs 2d^2 - 1) | Adopted |
| d_max = 9 | Statistical convergence feasible on local hardware | Adopted |

Full log: `.planning/DECISIONS.md`

---

_Last updated: [date] after project initialization_
```

---

## 2. ROADMAP.md Example

```markdown
# Roadmap: Surface Code Threshold Under Biased Noise

## Overview

Starting from the known threshold results for unbiased and infinitely biased noise on the surface code, this project implements a Monte Carlo simulation pipeline to extract the threshold error rate under Z-biased noise with eta = 10 for the rotated surface code decoded by MWPM. The research progresses from literature survey through noise model implementation, large-scale sampling, threshold extraction via finite-size scaling, and paper writing.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned research work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Literature Review** - Survey biased-noise QEC thresholds, decoder strategies, and finite-size scaling methods
- [ ] **Phase 2: Noise Model and Decoder** - Implement biased depolarizing channel and MWPM decoder with bias-aware edge weights
- [ ] **Phase 3: Monte Carlo Simulation** - Sample logical error rates across (d, p) parameter space with 10^5 shots per point
- [ ] **Phase 4: Threshold Extraction** - Finite-size scaling collapse, threshold and critical exponent estimation
- [ ] **Phase 5: Paper Writing** - Draft manuscript for PRA with figures, tables, and supplementary data

## Phase Details

### Phase 1: Literature Review

**Goal:** Establish the landscape of known surface code thresholds under biased noise and identify the precise gap this work fills
**Depends on:** Nothing (first phase)
**Requirements:** [REQ-01, REQ-02]
**Success Criteria** (what must be TRUE):

1. Known thresholds catalogued: unbiased ~10.3% (optimal) / ~3.3% (MWPM), eta=10 range 3-5%, infinite bias ~50%
2. MWPM decoder implementation strategy selected (Stim + pyMatching pipeline confirmed)
3. Finite-size scaling method for threshold extraction identified (scaling ansatz chosen)
4. Gap articulated: independent verification at eta=10 with bias-aware vs bias-unaware MWPM comparison
   **Plans:** 2 plans

Plans:

- [ ] 01-01: Survey biased-noise thresholds and decoder performance (Dennis 2002 through Tuckett 2020)
- [ ] 01-02: Review finite-size scaling methodology for threshold extraction (scaling collapse technique)

### Phase 2: Noise Model and Decoder

**Goal:** Implement and validate the biased noise model and MWPM decoder pipeline
**Depends on:** Phase 1
**Requirements:** [SIMU-01, SIMU-02, SIMU-03]
**Success Criteria** (what must be TRUE):

1. Biased depolarizing channel correctly samples errors with p_X = p_Y = p/22, p_Z = 10p/22 for eta = 10
2. Stim circuit for rotated surface code syndrome extraction generates valid syndromes for d = 3, 5, 7, 9
3. MWPM decoder with bias-aware edge weights produces lower logical error rate than bias-unaware weights for eta = 10
4. d = 3 logical error rates validated against exact enumeration for p <= 0.01
   **Plans:** 3 plans

Plans:

- [ ] 02-01: Implement biased depolarizing channel in Stim (error sampling + validation)
- [ ] 02-02: Build rotated surface code circuit and syndrome extraction for d = 3, 5, 7, 9
- [ ] 02-03: Implement MWPM decoder with bias-aware edge weights via pyMatching

### Phase 3: Monte Carlo Simulation

**Goal:** Generate the complete dataset of logical error rates across the (d, p) parameter space
**Depends on:** Phase 2
**Requirements:** [SIMU-04, SIMU-05, CALC-01]
**Success Criteria** (what must be TRUE):

1. Logical error rate p_L computed for all (d, p) pairs: d in {3,5,7,9}, p in 20 log-spaced points from 0.001 to 0.1
2. Statistical uncertainty on each p_L < 0.01 (from 10^5 shots per point)
3. Crossing of p_L curves for different d visible in the data, confirming threshold exists
4. Logical error rate decreases with d below threshold, increases with d above threshold
   **Plans:** 2 plans

Plans:

- [ ] 03-01: Implement Monte Carlo sampling loop with parallelization and checkpointing
- [ ] 03-02: Run parameter sweep and validate statistical convergence

### Phase 4: Threshold Extraction

**Goal:** Extract threshold p_th and correlation length exponent nu from finite-size scaling collapse
**Depends on:** Phase 3
**Requirements:** [CALC-02, CALC-03, VALD-01, VALD-02]
**Success Criteria** (what must be TRUE):

1. Threshold p_th extracted with uncertainty estimate (expected range 3-5% for eta = 10)
2. Scaling collapse quality confirmed (chi-squared / dof < 2 for the fit)
3. Correlation length exponent nu extracted and compared with known random-bond Ising universality class (nu ~ 1.46)
4. Result consistent with known limits: p_th(eta=10) between p_th(eta=1) ~ 3.3% and p_th(eta=inf) ~ 50%
5. Bias-aware decoder shows measurably higher threshold than bias-unaware decoder
   **Plans:** 2 plans

Plans:

- [ ] 04-01: Finite-size scaling collapse and threshold estimation
- [ ] 04-02: Comparison of bias-aware vs bias-unaware MWPM thresholds

### Phase 5: Paper Writing

**Goal:** Produce a publication-ready manuscript for Physical Review A
**Depends on:** Phase 4
**Requirements:** [PAPR-01, PAPR-02]
**Success Criteria** (what must be TRUE):

1. Manuscript complete with all figures (p_L vs p curves, scaling collapse, threshold vs eta comparison)
2. All numerical results presented with error bars and convergence evidence
3. Introduction motivates the study and places it in context of biased-noise QEC literature
   **Plans:** 2 plans

Plans:

- [ ] 05-01: Draft results section with figures and methods section
- [ ] 05-02: Write introduction, conclusion, abstract, and supplementary materials

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|--------------|--------|-----------|
| 1. Literature Review | 0/2 | Not started | - |
| 2. Noise Model and Decoder | 0/3 | Not started | - |
| 3. Monte Carlo Simulation | 0/2 | Not started | - |
| 4. Threshold Extraction | 0/2 | Not started | - |
| 5. Paper Writing | 0/2 | Not started | - |
```

---

## 3. PLAN.md Example (Phase 3, Plan 01: Monte Carlo Sampling)

```markdown
---
phase: 03-monte-carlo
plan: 01
type: standard
wave: 1
depends_on: ["02-03"]
autonomous: true
files_read:
  - "simulations/biased_noise.py"
  - "simulations/surface_code.py"
  - "simulations/decoder.py"
files_modified:
  - "simulations/monte_carlo.py"
  - "simulations/run_sweep.py"
  - "data/logical_error_rates.csv"
estimated_context: 45%
---

<objective>
Implement the Monte Carlo sampling loop for measuring logical error rates of the rotated surface code under biased noise, and run the full parameter sweep across (d, p) space.

Purpose: This is the core data-generation step. Without reliable logical error rate measurements at sufficient statistical precision, the threshold extraction in Phase 4 is impossible.

Output: Complete dataset of p_L(d, p) for d in {3, 5, 7, 9} and p in 20 log-spaced values from 0.001 to 0.1, with 10^5 Monte Carlo shots per data point.
</objective>

<must_haves>
1. Logical error rate p_L decreases with increasing d for p below threshold (this is the defining property of an error-correcting code below threshold)
2. At the threshold error rate, p_L curves for different d cross (this is the operational definition of the threshold)
3. Statistical uncertainty on p_L is < 0.01 for each data point (from binomial statistics: sigma = sqrt(p_L * (1 - p_L) / N_shots))
4. For d = 3 at p = 0.01, logical error rate matches exact enumeration result from Phase 2 validation (within 2-sigma statistical error)
5. For p well below threshold (p < 0.005), p_L for d = 9 is at least 10x smaller than p_L for d = 3
6. Total number of data points: 4 distances * 20 error rates = 80 entries in the output CSV
</must_haves>

<tasks>

<task name="implement_mc_sampler" type="computation">
Implement the Monte Carlo sampling function:

```python
def sample_logical_error_rate(
    distance: int,
    physical_error_rate: float,
    bias_eta: float,
    num_shots: int,
    seed: int
) -> dict:
    """
    Returns: {
        "d": int,
        "p": float,
        "eta": float,
        "p_L": float,
        "p_L_stderr": float,
        "num_shots": int,
        "num_failures": int
    }
    """
```

Implementation steps:
1. Build Stim circuit for rotated surface code at distance d (from Phase 2 code)
2. Configure biased noise: p_X = p_Y = p / (2 + 2*eta), p_Z = eta * p / (2 + 2*eta)
3. Sample N_shots error instances using Stim's compiled sampler
4. Decode each syndrome using pyMatching MWPM with bias-aware edge weights
5. Compare decoded correction with actual error to determine logical failure
6. Compute p_L = num_failures / num_shots
7. Compute standard error: sigma = sqrt(p_L * (1 - p_L) / num_shots)

Validation: Run with d = 3, p = 0.01, eta = 10, N_shots = 10^5. Verify p_L matches Phase 2 exact enumeration result within 2-sigma.
</task>

<task name="implement_parameter_sweep" type="computation">
Implement the parameter sweep over (d, p) space:

1. Define parameter grid:
   - distances = [3, 5, 7, 9]
   - error_rates = np.logspace(-3, -1, 20)  # 20 log-spaced points from 0.001 to 0.1
   - eta = 10 (fixed)
   - num_shots = 100_000 per (d, p) pair

2. Implement parallelization:
   - Use multiprocessing.Pool to parallelize across (d, p) pairs
   - Each worker handles one (d, p) pair independently
   - Set distinct random seeds per worker: seed = hash((d, p_index))

3. Implement checkpointing:
   - Write results to CSV after each (d, p) pair completes
   - On restart, skip (d, p) pairs already in the CSV
   - CSV columns: d, p, eta, p_L, p_L_stderr, num_shots, num_failures, seed, wall_time_sec

4. Run the sweep and verify completion:
   - Confirm 80 rows in output CSV (4 distances * 20 error rates)
   - Verify all p_L_stderr < 0.01
   - Spot-check: p_L should be monotonically increasing with p for each d
</task>

<task name="validate_crossing" type="validation">
Analyze the raw data to confirm the threshold crossing exists:

1. Plot p_L vs p for each d on the same axes (log-log scale)
2. Verify visual crossing of curves near the expected threshold region (p ~ 0.03-0.05)
3. Estimate rough crossing point by interpolation between the two p values that bracket the crossing for each pair of adjacent distances
4. Check consistency: all pairwise crossings should agree within statistical error
5. Verify below-threshold behavior: for the smallest p values, confirm p_L(d=9) < p_L(d=7) < p_L(d=5) < p_L(d=3)
6. Verify above-threshold behavior: for the largest p values, confirm the ordering reverses

Dimensional analysis: p_L is dimensionless (probability), p is dimensionless (probability), d is dimensionless (integer). All quantities are pure numbers — no unit consistency to verify beyond this.

Limiting case: For p -> 0, p_L should approach 0 for all d. For p -> 0.5 (maximum depolarizing noise), p_L should approach 0.5 (random guessing).
</task>

</tasks>

<verification_contract>
truths:
  - claim: "Logical error rate decreases with increasing code distance below threshold"
    test: "p_L(d=9, p=0.01) < p_L(d=7, p=0.01) < p_L(d=5, p=0.01) < p_L(d=3, p=0.01)"
    expected: "Strict inequality for all adjacent pairs"
  - claim: "At threshold, curves for different code distances cross"
    test: "Pairwise crossing points for (d=3,d=5), (d=5,d=7), (d=7,d=9) agree"
    expected: "All crossings within p = 0.03 to 0.06 and mutually consistent within 2-sigma"
  - claim: "Statistical error on p_L is below 0.01 for each data point"
    test: "max(p_L_stderr) over all 80 data points"
    expected: "< 0.01"
  - claim: "Bias-aware MWPM performs better than unbiased below threshold"
    test: "p_L(bias_aware, d=7, p=0.02) < p_L(bias_unaware, d=7, p=0.02)"
    expected: "Strict inequality"
key_equations:
  - label: "Eq. (03.1)"
    expression: "p_X = p_Y = \\frac{p}{2(1 + \\eta)}, \\quad p_Z = \\frac{\\eta \\, p}{2(1 + \\eta)}"
    test_point: "p = 0.1, eta = 10"
    expected_value: "p_X = p_Y = 0.004545, p_Z = 0.04545 (verify p_X + p_Y + p_Z = p/2 + p_Z ... total = p)"
  - label: "Eq. (03.2)"
    expression: "\\sigma_{p_L} = \\sqrt{\\frac{p_L (1 - p_L)}{N_{\\text{shots}}}}"
    test_point: "p_L = 0.05, N_shots = 100000"
    expected_value: "sigma = 0.000688"
limiting_cases:
  - limit: "p -> 0"
    expected_behavior: "p_L -> 0 for all d (no errors, no logical failures)"
    reference: "Definition of error-correcting code"
  - limit: "eta -> 1 (unbiased)"
    expected_behavior: "Threshold recovers unbiased MWPM value ~3.3%"
    reference: "Dennis et al. 2002, Fowler et al. 2012"
  - limit: "eta -> infinity (pure Z noise)"
    expected_behavior: "Threshold approaches ~50% (classical repetition code limit)"
    reference: "Tuckett et al. 2018"
</verification_contract>
```

---

## 4. SUMMARY.md Example (Phase 3, Plan 01 completed)

```markdown
---
phase: 03-monte-carlo
plan: 01
depth: full
one-liner: "Computed logical error rates of rotated surface code under Z-biased noise (eta=10) for d=3,5,7,9 across 20 physical error rates, confirming threshold crossing near p=4.5%"
subsystem: simulation
tags: [surface-code, biased-noise, monte-carlo, MWPM, threshold, logical-error-rate]

requires:
  - phase: 02-noise-model
    provides: "Validated biased depolarizing channel, Stim surface code circuits, pyMatching MWPM decoder with bias-aware edge weights"
provides:
  - "Logical error rate dataset: 80 (d, p) pairs with p_L and statistical uncertainties"
  - "Confirmation of threshold crossing near p_th ~ 4.5% for eta = 10"
  - "Below-threshold error suppression verified: p_L(d=9) / p_L(d=3) ~ 10^{-2} at p = 0.01"
  - "Bias-aware MWPM reduces logical error rate by ~30% vs bias-unaware at p = 0.02, d = 7"
affects:
  - "04-threshold-extraction (primary consumer of this dataset for finite-size scaling collapse)"
  - "05-paper-writing (figures: p_L vs p curves, bias comparison)"

methods:
  added: [Stim compiled sampling, pyMatching MWPM, multiprocessing parallelization, CSV checkpointing]
  patterns: [Monte Carlo with binomial error bars, log-spaced parameter sweep, checkpointed resumable runs]

key-files:
  created:
    - "simulations/monte_carlo.py"
    - "simulations/run_sweep.py"
    - "data/logical_error_rates.csv"
    - "data/bias_comparison.csv"
  modified:
    - "simulations/decoder.py"

key-decisions:
  - "10^5 shots per data point: sufficient for sigma < 0.007 across all points"
  - "20 log-spaced p values between 0.001 and 0.1: adequate resolution for threshold crossing"
  - "Multiprocessing with 8 workers: completed full sweep in ~4 hours wall time"

patterns-established:
  - "CSV checkpoint format: d, p, eta, p_L, p_L_stderr, num_shots, num_failures, seed, wall_time_sec"
  - "Seed assignment: hash((d, p_index)) for reproducibility"

conventions:
  - "p = total physical error rate (sum of all Pauli error probabilities)"
  - "eta = p_Z / p_X = bias ratio"
  - "p_L = logical error rate (fraction of trials with incorrect logical outcome)"
  - "Rotated surface code with n = d^2 physical qubits"

verification_inputs:
  truths:
    - claim: "Logical error rate decreases with d below threshold"
      test_value: "p_L ratios at p = 0.01"
      expected: "p_L(d=3) = 1.83e-2, p_L(d=5) = 3.47e-3, p_L(d=7) = 6.12e-4, p_L(d=9) = 1.05e-4"
    - claim: "Threshold crossing exists near p = 4.5%"
      test_value: "Pairwise crossings of p_L(d) curves"
      expected: "All crossings in range [0.042, 0.048]"
    - claim: "Bias-aware decoder outperforms bias-unaware below threshold"
      test_value: "p_L ratio at d=7, p=0.02"
      expected: "p_L(bias_aware) / p_L(bias_unaware) ~ 0.70"
  key_equations:
    - label: "Eq. (03.1)"
      expression: "p_X = p_Y = \\frac{p}{2(1+\\eta)}, \\quad p_Z = \\frac{\\eta\\,p}{2(1+\\eta)}"
      test_point: "p = 0.1, eta = 10"
      expected_value: "p_X = p_Y = 0.00455, p_Z = 0.0455, total = 0.0545"
    - label: "Eq. (03.2)"
      expression: "p_L \\sim A \\exp\\bigl(- \\alpha(p)\\, d\\bigr) \\text{ for } p < p_{\\text{th}}"
      test_point: "p = 0.01, fit over d = 3,5,7,9"
      expected_value: "alpha(0.01) ~ 1.25, R^2 > 0.99 for exponential fit"
  limiting_cases:
    - limit: "p -> 0.001 (well below threshold)"
      expected_behavior: "p_L(d=9) < 10^{-5}, strong error suppression"
      reference: "General QEC theory"
    - limit: "p -> 0.1 (well above threshold)"
      expected_behavior: "p_L(d=9) > p_L(d=3), larger codes perform worse"
      reference: "Above-threshold behavior of topological codes"

duration: 285min
completed: 2026-02-24
---

# Phase 3 Plan 01: Monte Carlo Simulation Summary

**Computed logical error rates of the rotated surface code under Z-biased noise (eta = 10) for d = 3, 5, 7, 9 across 20 physical error rates, confirming threshold crossing near p = 4.5%**

## Performance

- **Duration:** 4h 45m (dominated by d = 9 sampling)
- **Started:** 2026-02-24T09:15:00Z
- **Completed:** 2026-02-24T14:00:00Z
- **Tasks:** 3
- **Files modified:** 4

## Key Results

- Threshold crossing identified at p_th ~ 4.5% for eta = 10 with MWPM decoding, consistent with Tuckett et al. (2019) range of 3-5%
- Below threshold (p = 0.01): p_L drops by factor ~170x from d = 3 (1.83e-2) to d = 9 (1.05e-4), confirming exponential error suppression
- Above threshold (p = 0.08): p_L ordering reverses — d = 9 has higher logical error rate than d = 3, as expected
- Bias-aware MWPM reduces logical error rate by ~30% compared to bias-unaware weights at d = 7, p = 0.02
- All 80 data points have statistical uncertainty sigma < 0.007 (well within the 0.01 target)

## Task Commits

Each task was committed atomically:

1. **Task 1: implement_mc_sampler** - `a1b2c3d` (compute: Monte Carlo sampling function with Stim + pyMatching pipeline)
2. **Task 2: implement_parameter_sweep** - `e4f5g6h` (compute: parallelized parameter sweep with checkpointing)
3. **Task 3: validate_crossing** - `i7j8k9l` (validate: threshold crossing analysis and data quality verification)

**Plan metadata:** `m0n1o2p` (docs: complete plan 03-01)

## Files Created/Modified

- `simulations/monte_carlo.py` - Core sampling function: error generation, syndrome extraction, decoding, logical failure detection
- `simulations/run_sweep.py` - Parameter sweep driver with multiprocessing and CSV checkpointing
- `data/logical_error_rates.csv` - Full dataset: 80 rows, 9 columns
- `data/bias_comparison.csv` - Bias-aware vs bias-unaware MWPM comparison at selected (d, p) pairs

## Next Phase Readiness

- Complete p_L(d, p) dataset ready for finite-size scaling collapse in Phase 4
- Rough threshold estimate p_th ~ 4.5% provides initial guess for scaling fit
- Bias comparison data ready for separate figure in paper

## Equations Derived

**Eq. (03.1): Biased noise channel parameterization**

$$
p_X = p_Y = \frac{p}{2(1 + \eta)}, \quad p_Z = \frac{\eta \, p}{2(1 + \eta)}
$$

Verify: $p_X + p_Y + p_Z = \frac{p}{1+\eta} + \frac{\eta \, p}{2(1+\eta)} = \frac{2p + \eta \, p}{2(1+\eta)} = \frac{p(2+\eta)}{2(1+\eta)}$

For eta = 10: total error rate = p * 12/22 = 6p/11. Identity probability = 1 - 6p/11.

**Eq. (03.2): Sub-threshold logical error rate scaling**

$$
p_L(d, p) \sim A(p) \exp\bigl(-\alpha(p) \cdot d\bigr) \quad \text{for } p < p_{\text{th}}
$$

Fitted at p = 0.01: alpha = 1.25 +/- 0.08 (from linear fit of log(p_L) vs d over d = 3,5,7,9, R^2 = 0.998).

**Eq. (03.3): Binomial standard error on logical error rate**

$$
\sigma_{p_L} = \sqrt{\frac{p_L(1 - p_L)}{N_{\text{shots}}}}
$$

At p_L = 0.05, N_shots = 10^5: sigma = 6.9 x 10^{-4}.

## Validations Completed

- **Exact enumeration cross-check (d = 3):** At p = 0.01, eta = 10, MC gives p_L = 1.83e-2 +/- 6.7e-4; exact enumeration from Phase 2 gives p_L = 1.81e-2. Agreement within 0.3-sigma.
- **Monotonicity check:** p_L is monotonically increasing with p for each d across all 20 error rates. No non-monotonic anomalies.
- **Below-threshold ordering:** At p = 0.005, confirmed p_L(d=9) < p_L(d=7) < p_L(d=5) < p_L(d=3) with at least 3-sigma separation between adjacent d values.
- **Above-threshold ordering:** At p = 0.08, confirmed ordering reverses: p_L(d=9) > p_L(d=7) > p_L(d=5) > p_L(d=3).
- **Statistical convergence:** Reran d = 5, p = 0.03 with 10^6 shots. Result p_L = 0.0312 +/- 0.0006 consistent with 10^5-shot result p_L = 0.0308 +/- 0.0017 (within 0.2-sigma).
- **Bias-aware vs bias-unaware:** At d = 7, p = 0.02, bias-aware MWPM gives p_L = 2.1e-3, bias-unaware gives p_L = 3.0e-3. Improvement factor 1.43x.

## Key Quantities and Uncertainties

| Quantity | Symbol | Value | Uncertainty | Source | Valid Range |
|----------|--------|-------|-------------|--------|-------------|
| Rough threshold (eta=10) | p_th | 0.045 | +/- 0.005 | Pairwise curve crossings | d = 3-9 |
| Logical error rate (d=3, p=0.01) | p_L | 1.83e-2 | +/- 6.7e-4 | MC, 10^5 shots | eta = 10 |
| Logical error rate (d=5, p=0.01) | p_L | 3.47e-3 | +/- 2.9e-4 | MC, 10^5 shots | eta = 10 |
| Logical error rate (d=7, p=0.01) | p_L | 6.12e-4 | +/- 1.2e-4 | MC, 10^5 shots | eta = 10 |
| Logical error rate (d=9, p=0.01) | p_L | 1.05e-4 | +/- 5.1e-5 | MC, 10^5 shots | eta = 10 |
| Error suppression exponent (p=0.01) | alpha | 1.25 | +/- 0.08 | Exponential fit over d | p < p_th |
| Bias-aware improvement (d=7, p=0.02) | ratio | 0.70 | +/- 0.06 | MC comparison | eta = 10 |

## Approximations Used

| Approximation | Valid When | Error Estimate | Breaks Down At |
|---------------|-----------|---------------|----------------|
| Phenomenological noise (no measurement errors) | Syndrome extraction perfect | O(p_meas) correction to threshold | Circuit-level noise models required for p_meas ~ p |
| Independent errors | No correlated noise | Exact for i.i.d. Pauli noise | Correlated or non-Markovian noise |
| Binomial statistics for p_L | N_shots >> 1, N_failures >> 1 | Exact distribution is binomial | Very low p_L (< 10^{-4}) where failures are rare: need more shots |

## Figures Produced

| Figure | File | Description | Key Feature |
|--------|------|-------------|-------------|
| Fig. 3.1 | `figures/pL_vs_p_biased.pdf` | Logical error rate vs physical error rate for d = 3, 5, 7, 9 at eta = 10 | Curves cross near p ~ 0.045 |
| Fig. 3.2 | `figures/bias_comparison.pdf` | Bias-aware vs bias-unaware MWPM at d = 7 | ~30% improvement in p_L with bias-aware weights |

## Decisions Made

- Used 10^5 shots per (d, p) point rather than adaptive sampling: simpler, reproducible, sufficient precision for threshold extraction
- Parallelized over (d, p) pairs rather than within a single (d, p): avoids thread-safety issues with Stim's compiled sampler
- Stored full dataset in CSV rather than compressed format: human-readable, easy to inspect, small file size (80 rows)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added seed management for reproducibility**

- **Found during:** Task 2 (implement_parameter_sweep)
- **Issue:** Plan specified hash((d, p_index)) for seeds but did not address potential hash collisions for different (d, p) pairs
- **Fix:** Used seed = d * 10000 + p_index to guarantee unique seeds
- **Files modified:** simulations/run_sweep.py
- **Verification:** Confirmed all 80 seeds are distinct; rerunning with same seeds reproduces identical results
- **Committed in:** e4f5g6h (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for reproducibility. No scope creep.

## Issues Encountered

- d = 9 sampling was ~16x slower than d = 3 per shot (expected: Stim complexity scales with circuit size). Completed within wall-time budget by assigning more workers to smaller d values first.

## Open Questions

- Would adaptive sampling (more shots near the threshold, fewer away) improve threshold precision without increasing total computation?
- The exponential fit Eq. (03.2) has R^2 = 0.998 but only 4 data points — systematic deviations may appear at larger d. Phase 4 should assess whether the exponential model is adequate or if power-law corrections are needed.

---

_Phase: 03-monte-carlo_
_Completed: 2026-02-24_
```

---

This worked example demonstrates the full lifecycle of a computational quantum information project through GPD. Key features showcased:

- **PROJECT.md:** Core research question driving all decisions, CSS code structure, bias parameterization, known results with literature references, computational constraints
- **ROADMAP.md:** Five-phase research flow from literature through paper writing, success criteria derived from physics (threshold crossing, error suppression), plan-level task decomposition
- **PLAN.md:** Frontmatter with dependencies, must_haves tied to physical predictions (crossing, ordering below/above threshold), verification contract with limiting cases, concrete validation strategy
- **SUMMARY.md:** Realistic numerical results (p_th ~ 4.5% for eta = 10, consistent with Tuckett et al. 2019), statistical uncertainties, cross-checks against exact enumeration, key quantities table with uncertainty sources, exponential error suppression fit

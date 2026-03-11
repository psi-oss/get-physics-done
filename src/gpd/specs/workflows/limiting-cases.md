<purpose>
Systematically identify all relevant limiting cases for a physics result and verify that each limit is correctly recovered. This is the single most powerful verification tool in theoretical physics.

Called from /gpd:limiting-cases command. Produces LIMITING-CASES.md report.

Every new result must reduce to known results in appropriate limits. If it doesn't, the new result is wrong (or the known result is wrong, which is rare but possible). There are no exceptions to this principle.
</purpose>

<process>

## 0. Load Project Context

Load project state and conventions to identify applicable limits:

- Run:

```bash
INIT=$(gpd init phase-op --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

- **If init succeeds** (non-empty JSON with `state_exists: true`): Extract `convention_lock` for unit system and sign conventions. Extract `intermediate_results` from state for previously verified expressions. Extract active approximations and their validity ranges — these define the limits to check.
- **If init fails or `state_exists` is false** (standalone usage): Proceed with explicit convention declarations required from user via ask_user.

Active approximations from the project state directly inform which limits are most important to verify (e.g., if a perturbative approximation is active, the free-theory limit g→0 is mandatory).

**Convention verification** (if project exists):

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — review before checking limits"
  echo "$CONV_CHECK"
fi
```

Limiting case checks depend on conventions — e.g., the sign of k^2 = m^2 vs k^2 = -m^2 in the non-relativistic limit depends on metric signature.

## 1. Identify the Result(s) to Check

Scan the target for the main physics results:

```bash
# Final expressions, key results
grep -n "result\|final\|=.*\\\\frac\|=.*\\\\sqrt\|=.*\\\\sum\|=.*\\\\int\|E\s*=\|Z\s*=\|sigma\s*=\|Gamma\s*=" "$TARGET_FILE" 2>/dev/null

# Named equations
grep -n "\\\\label\|\\\\tag\|# Eq\." "$TARGET_FILE" 2>/dev/null
```

For each result, identify:

- What physical quantity it represents
- What parameters it depends on
- What the physical system is

## 2. Identify All Relevant Limits

For each result, systematically enumerate limits organized by physics domain:

### Universal Limits (check for every result)

| Limit           | Parameter            | Expected Behavior                 |
| --------------- | -------------------- | --------------------------------- |
| Free theory     | coupling g -> 0      | Reduce to non-interacting result  |
| Classical       | hbar -> 0            | Reduce to classical expression    |
| Static          | omega -> 0 or v -> 0 | Reduce to time-independent result |
| Single particle | N -> 1               | Reduce to one-body problem        |

### Thermodynamic Limits

| Limit            | Parameter                               | Expected Behavior                 |
| ---------------- | --------------------------------------- | --------------------------------- |
| High temperature | T -> infinity (beta -> 0)               | Classical equipartition           |
| Low temperature  | T -> 0 (beta -> infinity)               | Ground state dominance            |
| Thermodynamic    | N -> infinity, V -> infinity, N/V fixed | Intensive quantities well-defined |
| Ideal gas        | interactions -> 0                       | PV = NkT or quantum ideal gas     |
| Dilute           | density -> 0                            | Ideal gas behavior                |

### Quantum Mechanical Limits

| Limit            | Parameter                | Expected Behavior                        |
| ---------------- | ------------------------ | ---------------------------------------- |
| Non-relativistic | v/c -> 0 or E << mc^2    | Schrodinger equation                     |
| Semiclassical    | large quantum numbers    | Correspondence principle                 |
| Weak field       | perturbation -> 0        | Unperturbed result + linear correction   |
| Strong field     | perturbation -> infinity | Known strong-coupling result (if exists) |
| Harmonic         | anharmonicity -> 0       | Equally spaced levels                    |

### Field Theory Limits

| Limit            | Parameter           | Expected Behavior               |
| ---------------- | ------------------- | ------------------------------- |
| Tree level       | hbar -> 0 or g -> 0 | Classical field theory          |
| Free field       | all couplings -> 0  | Free propagators, no scattering |
| Non-relativistic | p << mc             | Schrodinger field theory        |
| Low energy       | E << Lambda         | Effective field theory          |
| Large N          | N -> infinity       | Saddle point / mean field       |
| Abelian          | gauge group -> U(1) | QED-like result                 |

### Condensed Matter Limits

| Limit           | Parameter              | Expected Behavior      |
| --------------- | ---------------------- | ---------------------- |
| Continuum       | lattice spacing a -> 0 | Continuum field theory |
| Single-site     | hopping -> 0           | Atomic limit           |
| Mean-field      | d -> infinity          | Saddle point exact     |
| Non-interacting | U -> 0                 | Band structure         |
| Half-filling    | n = 1                  | Particle-hole symmetry |

### Gravitational / Relativistic Limits

| Limit            | Parameter               | Expected Behavior    |
| ---------------- | ----------------------- | -------------------- |
| Newtonian        | weak field, slow motion | Newton's gravity     |
| Flat spacetime   | G -> 0                  | Special relativity   |
| Non-relativistic | v << c                  | Galilean invariance  |
| Schwarzschild    | spherical symmetry      | Known exact solution |
| Cosmological     | large scales            | FRW metric           |

### Spatial / Geometric Limits

| Limit           | Parameter     | Expected Behavior                          |
| --------------- | ------------- | ------------------------------------------ |
| 1D              | d = 1         | Often exactly solvable                     |
| 2D              | d = 2         | Special features (BKT, conformal symmetry) |
| Large distance  | r -> infinity | Asymptotic behavior (decay, scattering)    |
| Short distance  | r -> 0        | UV behavior, contact terms                 |
| Infinite volume | L -> infinity | No finite-size effects                     |

## 3. Select Applicable Limits

Not all limits apply to every result. Select based on:

1. **What parameters does the result depend on?** Only limits involving those parameters are relevant.
2. **What is the physical system?** Domain-specific limits apply.
3. **What is known?** Only check limits where the answer is independently established.

Present the selected limits:

```
## Limiting Cases for {Result Name}

Selected {N} applicable limits:

| # | Limit | Parameter | Known Result | Source |
|---|-------|-----------|--------------|--------|
| 1 | {limit} | {param -> value} | {known expression} | {textbook/paper} |
| 2 | ... | ... | ... | ... |
```

Use ask_user if:

- Unsure which limits are known for this system
- Multiple conventions for the known result exist
- Need user to provide the expected limiting expression

## 4. Verify Each Limit

For each selected limit:

### 4a. Analytical verification (preferred)

1. Write out the full expression
2. Take the limit analytically (Taylor expand, set parameter to limiting value)
3. Simplify
4. Compare with known result
5. Check: Do they match exactly? If not, what is the discrepancy?

### 4b. Numerical verification (when analytical is intractable)

```python
# Template for numerical limit check
import numpy as np

def result_function(params):
    """The result being checked."""
    ...

def known_limit(params):
    """The known limiting expression."""
    ...

# Approach the limit systematically
param_values = [1.0, 0.1, 0.01, 0.001, 0.0001]
for val in param_values:
    computed = result_function({..., limit_param: val})
    expected = known_limit({..., limit_param: val})
    ratio = computed / expected
    rel_error = abs(computed - expected) / abs(expected)
    print(f"param={val:.0e}  computed={computed:.10f}  expected={expected:.10f}  ratio={ratio:.10f}  rel_err={rel_error:.2e}")

# Expected: ratio -> 1 and rel_error -> 0 as param -> limiting value
# Red flags: ratio not approaching 1, oscillating, or diverging
```

### 4c. Classify the result

| Status          | Meaning                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| EXACT MATCH     | Analytical limit reproduces known result identically                    |
| NUMERICAL MATCH | Converges to known result within numerical precision                    |
| CORRECT ORDER   | Leading term matches; subleading terms expected to differ               |
| DISCREPANCY     | Does not match -- error in derivation or in known result identification |
| DIVERGENT       | Limit does not exist (may be physical or may indicate error)            |
| CANNOT CHECK    | Limit is intractable analytically and numerically                       |

## 5. Diagnose Failures

For any limit that fails:

1. **Characterize the discrepancy:**

   - Wrong by a constant factor? (Suggests normalization or combinatorial error)
   - Wrong sign? (Suggests convention mismatch or parity error)
   - Wrong functional form? (Suggests wrong starting point or missed contribution)
   - Divergent where finite expected? (Suggests regularization issue)

2. **Localize the error:**

   - At which step in the derivation does the limit first fail?
   - Binary search: check intermediate expressions in the same limit

3. **Suggest cause:**
   - Common: missing factor of 2 from spin, wrong Fourier convention, missing Jacobian
   - Domain-specific: missing symmetry factor, wrong boundary condition, missed diagram

## 6. Generate Report

Write LIMITING-CASES.md:

```markdown
---
target: { phase or file }
date: { YYYY-MM-DD }
results_checked: { N }
limits_checked: { M }
limits_passed: { K }
limits_failed: { F }
status: all_passed | failures_found
---

# Limiting Cases Report

## Results Analyzed

| #   | Result | Expression   | Location    |
| --- | ------ | ------------ | ----------- |
| 1   | {name} | {brief form} | {file:line} |

## Limits Verified

| #   | Result   | Limit        | Parameter        | Expected | Obtained   | Status      |
| --- | -------- | ------------ | ---------------- | -------- | ---------- | ----------- |
| 1   | {result} | {limit name} | {param -> value} | {known}  | {computed} | MATCH       |
| 2   | {result} | {limit name} | {param -> value} | {known}  | {computed} | DISCREPANCY |

## Failed Limits

### Failure {N}: {Result} in {Limit}

- **Parameter:** {param -> value}
- **Expected:** {expression from known result}
- **Obtained:** {expression from our result in this limit}
- **Discrepancy:** {factor of 2, wrong sign, wrong power, etc.}
- **Likely cause:** {what went wrong}
- **Location of error:** {where in the derivation the limit first fails}

## Summary

- Results checked: {N}
- Total limits applicable: {M}
- Passed: {K}
- Failed: {F}
- Cannot check: {C}
- {Overall assessment}
```

## Singular Limit Handling

Many physics limits are singular: the result is qualitatively different depending on the order in which limits are taken, or the limiting expression is distributional rather than pointwise convergent. These require special treatment.

### Non-Commuting Limits

When two parameters approach limits simultaneously, the order matters. The result can change qualitatively.

**Protocol:**
1. Take limit A first, then limit B: compute lim_B lim_A f(A, B)
2. Take limit B first, then limit A: compute lim_A lim_B f(A, B)
3. Compare: if results differ, the limits do not commute
4. Identify the physical regime: which ordering corresponds to the physical situation?
5. Document both orderings and state which one is used and why

**Common non-commuting limits:**
- Thermodynamic limit (N → ∞) vs zero temperature (T → 0): SSB only appears if N → ∞ taken first
- Infrared limit (k → 0) vs massless limit (m → 0): IR divergences depend on ordering
- Continuum limit (a → 0) vs infinite volume (L → ∞): finite-size artifacts vs discretization artifacts
- External field → 0 vs volume → ∞: spontaneous magnetization requires V → ∞ first

### Distributional Limits

When the limiting expression involves delta functions or other distributions, pointwise comparison is meaningless.

**Protocol:**
1. Do not compare functions pointwise; compare their action on test functions
2. Compute moments: integral x^n f_epsilon(x) dx for several n
3. Verify moments converge to the expected values of the limiting distribution
4. For delta-function limits: verify normalization (integral f_epsilon dx → 1) and localization (width → 0)
5. Check that derivatives of the limiting distribution match: f_epsilon' should approach delta' in the distributional sense

**Examples:**
- sin(Nx)/(pi*x) → delta(x) as N → ∞ (Dirichlet kernel)
- (1/sqrt(2*pi*sigma^2)) exp(-x^2/(2*sigma^2)) → delta(x) as sigma → 0
- epsilon/(x^2 + epsilon^2)/pi → delta(x) as epsilon → 0 (Lorentzian representation)

### Stokes Phenomena

Asymptotic expansions can change form discontinuously as the direction of approach in the complex plane varies.

**Protocol:**
1. Identify the anti-Stokes lines where exponentially small terms switch on/off
2. Track the Stokes multiplier (typically ±i) across each anti-Stokes line
3. Verify the asymptotic expansion in each sector of the complex plane independently
4. Check: the exact function is continuous across Stokes lines, even though its asymptotic representation changes
5. For physical problems: determine which sector of the complex plane the physical parameter lies in

**Common contexts:**
- WKB approximation near turning points
- Airy function asymptotics (oscillatory vs exponentially decaying sectors)
- Gamma function asymptotics (Stirling's formula plus exponentially small corrections)
- Resurgent asymptotics in quantum mechanics and QFT

### Thermodynamic Limit Subtleties

The limit N → ∞, V → ∞ with N/V fixed introduces subtleties that can invalidate naive interchange of limits with differentiation or integration.

**Protocol:**
1. Verify that the free energy density f = F/V has a well-defined limit as V → ∞
2. Check that differentiation commutes with the thermodynamic limit: does (∂f/∂T)_V computed at finite V converge to the derivative of the limiting f?
3. At phase transitions: the free energy is non-analytic in the thermodynamic limit but analytic at finite V. Finite-size rounding near T_c must be accounted for
4. For first-order transitions: the Maxwell construction (equal-area rule) applies only in the thermodynamic limit; at finite V, metastable states have finite lifetime
5. For spontaneous symmetry breaking: the order parameter is zero at finite V (by symmetry) but nonzero in the thermodynamic limit. Take V → ∞ before removing the symmetry-breaking field

Ensure output directory exists:

```bash
mkdir -p .gpd/analysis
```

Save to:

- Phase target: `${phase_dir}/LIMITING-CASES.md`
- File target: `.gpd/analysis/limits-{slug}.md`

## 7. Present Results and Route

If all pass:

```
## Limiting Cases: All {M} limits verified

{Result} correctly reduces to known expressions in all checked limits.
Confidence: HIGH
```

If failures found:

```
## Limiting Cases: {F}/{M} limits failed

{List failures with discrepancy character}

Suggested next steps:
- `/gpd:debug` -- investigate the failing limit(s)
- `/gpd:dimensional-analysis` -- check for dimensional errors near the failure
- Review derivation at {location} where the limit first diverges from expectation
```

**Commit the report:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${OUTPUT_PATH}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: limiting cases verification — ${phase_slug:-standalone}" \
  --files "${OUTPUT_PATH}"
```

Where `${OUTPUT_PATH}` is the path where LIMITING-CASES.md was written.

</process>

<output>
LIMITING-CASES.md written with full verification results.
</output>

<success_criteria>

- [ ] All results in target identified
- [ ] Applicable limits enumerated systematically by domain
- [ ] Known limiting expressions identified with sources
- [ ] Each limit verified analytically or numerically
- [ ] Discrepancies characterized (factor, sign, form, divergence)
- [ ] Failures localized to specific derivation steps
- [ ] Report generated with full results table
- [ ] Failed limits diagnosed with likely causes
- [ ] Next steps suggested for any failures
</success_criteria>

---
load_when:
  - "verification priority"
  - "high risk errors"
  - "what to check first"
tier: 1
context_cost: small
---

# Verification Gap Summary

Compact summary of HIGH-risk and CRITICAL error classes from the full `references/verification/audits/verification-gap-analysis.md`. Load this for routine verification prioritization; load the full file only for deep audits.

**Current catalog:** 104 total error classes. The detailed layer-coverage counts below still come from the 2026-02-23 101-class audit snapshot in `references/verification/audits/verification-gap-analysis.md`; classes #102-104 were added afterward and are not yet folded into those aggregate counts.

## CRITICAL Risk (0-1 reliable layers)

| # | Error Class | Detection | Mitigation |
|---|---|---|---|
| 11 | Hallucinated identities | L2b IDENTITY_CLAIM tagging (weak) + L5 literature check | Verify EVERY non-trivial identity against 2+ sources |
| 13 | Boundary condition hallucination | L0 plan-checker (weak) + L5 spot-check | Substitute boundary values explicitly; never trust "standard" BCs |

## HIGH Risk (1 reliable layer, plausible-looking results)

| # | Error Class | Why Dangerous | Key Check |
|---|---|---|---|
| 3 | Green's function confusion | Retarded vs time-ordered agree at T=0; diverge at finite T | L5 5.14 (spectral/analytic structure) |
| 5 | Incorrect asymptotic expansions | Leading term correct; subleading wrong | L5 limiting cases + coefficient verification |
| 9 | Thermal field theory errors | Matsubara sums give finite but wrong results; KMS violation subtle | L5 5.13/5.14 (**skipped in exploratory/quick**) |
| 17 | Correlation/response confusion | Identical at T=0; differs at finite T | L5 5.14 (**skipped in exploratory/quick**) |
| 21 | Branch cut errors | Wrong Riemann sheet gives finite spectral function | L5 analytic continuation check |
| 42 | Missing anomalies | Classical conservation holds; quantum anomaly is additional | L5 5.15 (**skipped in exploratory/quick**) |
| 52 | NR constraint violation | Constraint-violating modes grow exponentially | L2b + L5 constraint monitoring |
| 63 | GW template mismatch | Wrong waveform template biases parameter estimation | L5 literature + waveform cross-check |
| 71 | Missing Berry phase | Geometric phase invisible in perturbation theory | L5 topological check |
| 72 | NR gauge mode leakage | Gauge violation grows undetected | L2b monitor + L5 constraint check |
| 76 | Debye length resolution | Under-resolved screening produces wrong transport | L2b grid check + L5 resolution verification |
| 77 | Kinetic vs fluid regime mismatch | Using fluid model in collisionless regime | L0 regime check + L5 domain verification |
| 87 | Wrong reconnection topology | Sweet-Parker vs Petschek: 5 orders of magnitude error | L5 literature + scaling check |

## Still-Uncataloged HIGH-Risk Gaps

These gaps remain outside the current 104-class catalog but are still worth tracking:

| Gap | Description | Why Dangerous |
|---|---|---|
| Cross-phase error propagation | Uncertainty from phase N not tracked into phase N+1 | Error bars on final result are underestimated; conclusions may not survive uncertainty |

## Profile-Dependent Coverage Warning

| Profile | L5 Checks | Error Classes Unprotected |
|---|---|---|
| deep-theory / review | All 15 | None |
| numerical / paper-writing | All 15 | None |
| exploratory (contract gate + all applicable decisive/falsifying checks) | phase-dependent | Risk now depends on whether the right phase-specific checks are surfaced, not on a hardcoded reduced floor |
| quick (3-check) | 5.1,5.3,5.10 | ~81 classes lose ONLY defense |

**Bottom line:** In exploratory/quick profiles, classes #3, #9, #17, #42 (all HIGH risk) have **zero** reliable coverage. Always run full verification for publishable results.

## See Also

- `references/verification/audits/verification-gap-analysis.md` — 101-class audit baseline plus notes about the current 104-class catalog
- `../errors/llm-physics-errors.md` — Index to the 4-part error catalog
- `../core/verification-quick-reference.md` — 14-check verification checklist
- `../core/verification-core.md` — Universal verification procedures

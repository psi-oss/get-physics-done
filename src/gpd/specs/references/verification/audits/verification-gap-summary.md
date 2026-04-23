---
load_when:
  - "verification priority"
  - "high risk errors"
  - "what to check first"
tier: 1
context_cost: small
---

# Verification Gap Summary

Compact current-state prioritization for the verification surfaces that deserve the most attention first.

Use this file for routine verification prioritization. Use `verification-gap-analysis.md` for the current coverage architecture, and the error catalog files for class-level detail.

## Current Verification Floor

- The live verifier registry is **19 checks**: `5.1`-`5.14` universal plus `5.15`-`5.19` contract-aware.
- For publishable work, the real floor is not "some small checklist." It is the **full relevant universal coverage plus every contract-aware check required by the plan**.
- Executor post-step guards, convention checks, and inter-wave gates are early tripwires, not substitutes for final verification.
- The machine-readable `ERROR_CLASS_COVERAGE` currently maps 20 focused error classes. The table below extends current priorities beyond that subset using executor guards, traceability docs, and domain-specific protocols.
- If `workflow.verifier` is false in config, `execute-phase` skips phase verification regardless of profile.
- Every `VERIFICATION.md` still requires at least one executed code block with actual output; prioritization guidance does not replace computational evidence.

## Special-Attention Error Classes

These classes are worth surfacing early because they produce plausible-looking outputs, hide in setup assumptions, or tend to survive shallow review. Some entries come directly from the machine-readable coverage map; others are current advisory priorities derived from executor guards, domain checklists, and the broader error catalog.

| # | Error class | Why it is dangerous | Prioritize first |
|---|---|---|---|
| 3 | Green's function confusion | Retarded, advanced, and time-ordered objects can look superficially consistent | `5.11`, `5.13`, response-function protocols |
| 5 | Incorrect asymptotic expansions | Leading behavior can look right while subleading structure is wrong | `5.3`, `5.15` when the contract names a decisive limit |
| 9 | Thermal field theory errors | Finite-temperature mistakes often stay finite and numerically plausible | `5.13`, `5.14`, finite-temperature protocols |
| 11 | Hallucinated identities | False identities often look authoritative and propagate everywhere | `5.2`, explicit `IDENTITY_CLAIM` tagging, literature anchors |
| 13 | Boundary condition hallucination | Wrong BCs can make the whole derivation look clean but solve the wrong problem | `5.3`, explicit BC declarations, problem-setup review |
| 17 | Correlation / response confusion | Static and dynamical objects can agree in trivial limits but diverge where it matters | `5.11`, `5.13`, response-function protocols |
| 21 | Branch cut / analytic continuation errors | Wrong sheets can still generate smooth, finite answers | `5.11`, `5.13`, analytic-continuation protocols |
| 42 | Missing anomalies / topology | Classical consistency checks can pass while the quantum or topological story is still wrong | topological / anomaly guards, domain checklist, decisive literature or benchmark anchors |
| 52 | NR constraint violation | Evolutions can look smooth while constraint-breaking modes grow | `5.5`, `5.8`, NR constraint monitors |
| 63 | GW template mismatch | Waveforms can fit locally while biasing inferred parameters badly | `5.2`, `5.6`, benchmark reproduction |
| 71 | Missing Berry phase | Adiabatic calculations can miss geometric content entirely | `5.3`, domain checklist, decisive comparison target |
| 72 | NR gauge mode leakage | Gauge artifacts can masquerade as physical signals | `5.5`, NR gauge/constraint monitoring |
| 76 | Debye length resolution | Under-resolution can create convincing but wrong plasma transport | `5.5`, resolution studies, domain-specific guards |
| 77 | Kinetic vs fluid regime mismatch | The wrong model family can still produce tidy numerics | plan regime checks, `5.6`, decisive benchmark or literature anchor |
| 87 | Wrong reconnection topology | Smooth solutions can still be wrong by orders of magnitude in rate scaling | `5.6`, `5.8`, reconnection-specific scaling checks |

## Current Interpretation Of "Critical"

The shipped references do not maintain a dated zero-layer or one-layer "CRITICAL" table.

Operationally, the two setup-sensitive classes that deserve special skepticism are:

- `#11` hallucinated identities
- `#13` boundary condition hallucination

They are not singled out because the current system has no defenses. They are singled out because their early defenses are lightweight and the wrong setup can survive surprisingly far downstream.

## Still Missing As A First-Class Catalog Surface

| Gap | Why it still matters |
|---|---|
| Cross-phase error propagation | Uncertainty and approximation drift can compound across phases even when each phase looks locally consistent |
| Broader machine-readable coverage | Current `ERROR_CLASS_COVERAGE` maps only a focused subset of the 104-class catalog, so some priority guidance remains advisory instead of registry-backed |

## Profile Warning

| Profile | Current expectation |
|---|---|
| deep-theory / review | Run the full universal registry plus every required contract-aware check |
| numerical / paper-writing | Still run the full relevant registry; emphasize convergence, statistics, benchmark anchors, and manuscript-facing evidence |
| exploratory | Compress optional depth only; do **not** waive decisive-anchor, forbidden-proxy, direct-vs-proxy, or contract-critical checks |
| quick | Intentionally narrow. Useful for fast sanity checks, not for publication-grade verification |

**Note:** In `verify-work`, `autonomy=yolo` may skip optional cross-checks and literature comparison, but it must still keep contract-critical anchors and decisive benchmarks.

**Bottom line:** if the result is intended to survive publication, handoff, or downstream reuse, run the full relevant verifier registry and the required contract-aware checks. Do not treat quick or lightly scoped exploration as final verification.

## See Also

- `verification-gap-analysis.md` — current coverage architecture
- `../errors/llm-physics-errors.md` — full 104-class catalog
- `../errors/llm-errors-traceability.md` — traceability index into the error catalog
- `../core/verification-quick-reference.md` — conceptual 14-check quick checklist
- `../core/verification-core.md` — universal verification procedures

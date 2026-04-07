# End-to-End Physics Test Report

Tested on branch `integration/runtime-observability-flow-paper` using a real Schwarzschild metric derivation project.

## Test Problem

Derive the Schwarzschild solution to Einstein's vacuum field equations for a static, spherically symmetric spacetime, starting from the general metric ansatz through Christoffel symbols, Ricci tensor, and vacuum equations to the final metric.

## Results: 17/17 Sub-Tests Passed

### 1. Project Initialization and State

- Fresh project correctly reports `state_exists=False`, `integrity_status=degraded`
- State auto-populates 19 top-level keys on first save (convention_lock, continuation, session, etc.)
- ROADMAP.md correctly detected

### 2. Paper Quality Scoring

- Full Schwarzschild paper scores **97.54/100** (PRL-adjusted), `publication_ready`
- One minor flag: 2 symbols not defined at first use (10/12 satisfied)
- Minimal input correctly scores **11.06/100** with 4 blocking issues
- PRL-specific `abstract_broad_significance` bonus correctly applied

### 3. Bibliography System

- 5 BibTeX entries generated from CitationSource objects (Schwarzschild 1916, Einstein 1915, Misner-Thorne-Wheeler 1973, Hawking 1973)
- Key deduplication works: `schwarzschild1916` and `schwarzschild1916a`
- German umlauts preserved
- Audit reports: 5 total, 5 resolved, 3 unverified (no canonical IDs), 2 partial

### 4. Verification Tools

- **Dimensional analysis**: Correctly validates `[M][L]^2[T]^-2 = [M][L]^2[T]^-2` and catches `energy != momentum`
- **Limiting cases**: Documents 4 limits (M->0, weak field, r->infinity, G->0). Smart suggestion: "Consider non-relativistic limit (c -> infinity)"
- **Symmetry check**: Matches SO(3) to `rotational`, parity, Lorentz invariance. Correctly leaves time-translation as unmatched (Killing vector, not in standard list)

### 5. Convention System

- GR defaults loaded: `natural_units=natural`, `metric_signature=mostly-plus`, `fourier_convention=physics`
- `(-,+,+,+)` correctly normalized to `mostly-plus`
- GR vs QFT diff: 2 critical differences (metric_signature, fourier_convention)
- ASSERT_CONVENTION mechanism catches `(+,-,-,-)` vs `(-,+,+,+)` mismatches

## Critique

### Strengths

1. **Convention system is production-ready for real physics.** The ASSERT_CONVENTION mechanism catches exactly the sign-convention errors that plague GR/QFT papers. The GR vs QFT diff is immediately useful.

2. **Paper quality scoring is meaningful.** 97.54/100 for a well-structured derivation paper with one minor symbol-definition gap is a reasonable score. The blocker detection (missing citations, incomplete verification) is correct.

3. **Bibliography audit pipeline is thorough.** Resolution tracking, key deduplication, author sanitization, and the verified/unverified/partial classification are all correct.

4. **All verification tools return structured, schema-versioned output.** This is good for downstream automation.

5. **State system degrades gracefully.** Missing files produce clear diagnostics, not crashes.

### Weaknesses

1. **No bridge from raw LaTeX to paper quality scoring.** The `PaperQualityInput` requires pre-parsed structured data (equation counts, figure counts, etc.), not LaTeX. A real workflow needs someone (agent or human) to extract this metadata first. `validate_tex_draft` was claimed in RES-541 PR but does not exist on this branch.

2. **Dimensional analysis requires manual `[M][L][T]` annotation.** It cannot parse actual physics expressions like `E = mc^2` or `r_s = 2GM/c^2`. For a physics copilot, this is a significant gap — the tool should understand physics notation, not just bracket notation.

3. **Limiting case and symmetry tools are documentary, not computational.** They record what the user says, classify it against a taxonomy, and suggest strategies, but they don't actually compute limits or verify symmetries. Status is always `documented` or `requires_verification`, never `verified`.

4. **Convention normalization is lossy.** `(-,+,+,+)` becomes `mostly-plus` with no way to recover the original notation. Some subfields use non-standard conventions that don't map to the canonical labels.

5. **API naming is inconsistent across modules.** The actual function names differ significantly from what documentation and test scripts expect (see table below). This suggests the API has evolved without updating the public documentation surface.

### API Naming Gaps

| Expected (from docs/tests) | Actual |
|---|---|
| `load_effective_config` | `load_config` |
| `load_state` / `save_state` | `state_load` / `save_state_json` |
| `start_session` / `log_event` | `ensure_session` / `observe_event` |
| `record_trace_event` | `trace_start` + `trace_log` |
| `load_command` | `get_command` (from registry) |
| `get_agents` | `list_agents` + `get_agent` |
| `run_health_checks` | `run_health` |
| `CostLedger` | `build_cost_summary` |
| `ProofReviewOrchestrator` | `resolve_manuscript_proof_review_status` |
| `get_recovery_advice(symptom)` | `build_recovery_advice(cwd=...)` |

### Suggestions

1. Add a `tex_to_quality_input()` function that parses raw LaTeX into `PaperQualityInput`.
2. Add symbolic expression parsing for dimensional analysis (even basic regex for `G`, `M`, `c`, `hbar`).
3. Add a `verify_limit()` function that can numerically evaluate a limit (at least for polynomial/rational expressions).
4. Stabilize the public API names — either update docs to match reality, or add aliases for the documented names.
5. Add a convention round-trip test: `set → get → set` should preserve the original notation.

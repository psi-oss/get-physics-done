---
tier: 1
context_cost: small
---

# Cross-Phase Error Propagation Protocol

How uncertainties propagate through multi-step physics calculations across GPD phases. This protocol is consumed by verify-phase.md (uncertainty_propagation_check step), verify-work.md (cross_phase_uncertainty_audit step), and execute-plan.md (Uncertainty Budget section in SUMMARY.md).

## The Problem

Multi-phase physics calculations accumulate uncertainties at each step. Without explicit tracking, downstream phases inherit central values stripped of their uncertainty context. Three failure modes:

1. **Silent precision loss**: Phase N reports x = 1.234 ± 0.05 but Phase N+1 uses x = 1.234 as exact.
2. **Catastrophic cancellation** (Error #102): Phase N+1 computes y ≈ x, then uses (y - x) as a "small parameter" — but (y - x) may be smaller than the combined uncertainties.
3. **Functional Jacobian omission** (Error #103): Field redefinitions across phases drop the measure factor in path integrals.

## Uncertainty Budget Declaration (Executor Responsibility)

Every SUMMARY.md "Key Results" section must include an **Uncertainty Budget** subsection. For each key result:

```markdown
### Uncertainty Budget

| Quantity | Central Value | Uncertainty | Relative | Method | Dominant Input |
|----------|--------------|-------------|----------|--------|----------------|
| m_eff    | 2.31 GeV     | ± 0.08 GeV  | 3.5%     | quadrature | bare coupling g |
| Tc       | 1.47 Tc_QCD  | ± 0.12      | 8.2%     | Monte Carlo (1000 samples) | lattice spacing a |
| c (central charge) | 1 | exact | 0% | symmetry argument | N/A |
```

**Method** is one of:
- `quadrature` — standard Gaussian error propagation δf = √(Σ (∂f/∂xᵢ · δxᵢ)²)
- `Monte Carlo` — sampled input distribution, report N_samples
- `analytic` — exact formula for propagated uncertainty
- `bootstrap` — resampling-based estimate
- `exact` — result is exact (symmetry, integer quantum number, theorem)
- `estimated` — order-of-magnitude estimate only (flag for future refinement)

**Dominant Input** identifies which upstream uncertainty contributes most. This enables targeted improvement: if the dominant input comes from Phase N-2, improving Phase N-1 won't help.

## Verification Checks

### 1. Uncertainty Declared (Warning if missing)

Every numerical result used by downstream phases must have an uncertainty. Exact results must state why they are exact.

### 2. Uncertainty Consumed (Blocker if missing for final results)

When a phase uses a value from a prior phase, the SUMMARY.md or computation files must reference the uncertainty, not just the central value.

Test: search for the central value in the consuming phase. If found without any ± or uncertainty reference within the same equation/paragraph, flag it.

### 3. Propagation Method Stated (Warning if missing)

The consuming phase must state how uncertainties were combined. "Assumed quadrature" is acceptable; silence is not.

### 4. Catastrophic Cancellation Check (Blocker)

For any subtraction of two quantities with comparable magnitudes:

```python
def check_cancellation(a, da, b, db):
    """Check for catastrophic cancellation in (a - b)."""
    diff = abs(a - b)
    d_diff = (da**2 + db**2)**0.5
    if diff == 0:
        return "BLOCKER: exact cancellation, difference is zero"
    rel = d_diff / diff
    if rel > 1.0:
        return f"BLOCKER: relative uncertainty {rel:.1%} > 100% — result is noise"
    if rel > 0.5:
        return f"WARNING: relative uncertainty {rel:.1%} — marginal significance"
    return f"OK: relative uncertainty {rel:.1%}"
```

### 5. Amplification Factor Tracking

For chains of N phases, track the cumulative uncertainty amplification:

```
A_N = δ(final result) / δ(initial input)
```

If A_N > 10 for any input uncertainty, flag for review — the calculation may need restructuring (analytic cancellation, resummation, or different variable choice).

## Phase Handoff Format

When a phase provides quantities consumed by downstream phases, the SUMMARY.md "provides" frontmatter key should include uncertainty metadata:

```yaml
provides:
  - name: effective_mass
    value: 2.31
    uncertainty: 0.08
    unit: GeV
    method: quadrature
    dominant_input: bare_coupling
  - name: central_charge
    value: 1
    uncertainty: 0
    method: exact
    note: "Protected by conformal symmetry"
```

This structured format enables automated uncertainty propagation checks in verify-phase.md.

## When Uncertainty Tracking Is N/A

- Phase 1 of a project (no inherited quantities)
- Purely analytic phases producing exact symbolic results
- Literature review or methodology phases with no numerical outputs
- Phases that define conventions or notation (no computed quantities)

In these cases, note "Uncertainty propagation: N/A" with the reason.

## Related Error Classes

- **#102**: Catastrophic cancellation in propagated quantities
- **#103**: Functional Jacobian errors in field-theoretic transformations
- **#104**: IR safety violations in cross-phase observable definitions

See `references/verification/errors/llm-errors-extended.md` for full detection strategies and examples.

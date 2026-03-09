---
name: gpd-regression-check
description: Re-verify all previously verified truths to catch regressions after changes
argument-hint: "[phase number to limit scope, or empty for all]"
allowed-tools:
  - read_file
  - shell
  - glob
  - grep
  - write_file
---

<!-- Platform: Claude Code. Tool names and @ includes are platform-specific. -->
<!-- allowed-tools listed are Claude Code tool names. Other platforms use different tool interfaces. -->

<objective>
Re-verify all previously verified physics truths across completed phases to detect regressions introduced by later work. Changes in one phase can silently break results in earlier phases through notation drift, convention changes, approximation regime violations, or modified shared artifacts.

**Why a dedicated command:** Phase verification happens once at completion. Subsequent phases may introduce changes that invalidate prior results -- a redefined symbol, a tightened approximation, a modified shared calculation. Without periodic regression checking, these silent breakages accumulate until the research narrative is internally inconsistent.

**The principle:** Every truth marked VERIFIED in a phase's VERIFICATION.md should remain verifiable against the current project state. If it doesn't, something changed that invalidated the original verification.

Output: `.planning/REGRESSION-REPORT.md` with re-check results, regressions flagged with severity and affected phases, and recommended fixes.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/regression-check.md
</execution_context>

<context>
Scope: $ARGUMENTS (optional)
- If a number (e.g., "3"): re-check truths only for that phase
- If empty: re-check truths across all completed phases

@.planning/STATE.md
@.planning/ROADMAP.md
</context>

<process>
Execute the regression-check workflow from @{GPD_INSTALL_DIR}/workflows/regression-check.md end-to-end.
Preserve all workflow gates (discovery, extraction, re-verification, cross-phase consistency, report generation).

The regression check evaluates previously verified truths across these dimensions:

1. **Equation integrity** -- Do equations from prior phases still hold given any subsequent modifications to shared derivations or definitions?
2. **Dimensional consistency** -- Do all verified expressions still have correct dimensions given any convention changes in later phases?
3. **Limiting cases** -- Do previously verified limits still hold given parameter regime changes in later work?
4. **Artifact integrity** -- Do referenced artifacts (derivations, notebooks, data files) still exist and contain the expected content?
5. **Cross-phase notation** -- Are symbols used in verified truths still defined the same way across the project?
6. **Approximation validity** -- Are approximation regimes assumed in verified truths still valid given parameters explored in later phases?

## Severity Classification

- **CRITICAL** -- A verified truth is now demonstrably false (equation wrong, dimension mismatch, limit fails). Blocks all downstream work that depends on this truth.
- **MAJOR** -- A verified truth cannot be re-confirmed (supporting artifact missing, referenced derivation modified). Must be re-verified before conclusions are drawn.
- **MINOR** -- A verified truth still holds but with caveats (notation inconsistency, approximation near regime boundary). Should be resolved before publication.
- **NOTE** -- Observation for the record (e.g., "truth still holds but the supporting derivation was refactored").
  </process>

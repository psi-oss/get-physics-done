---
name: gpd:regression-check
description: Re-verify all previously verified claims and checks to catch regressions after changes
argument-hint: "[phase number to limit scope, or empty for all]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - find_files
  - search_files
  - file_write
  - task
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Re-verify all previously verified physics claims and checks across completed phases to detect regressions introduced by later work. Changes in one phase can silently break results in earlier phases through notation drift, convention changes, approximation regime violations, or modified shared artifacts.

**Why a dedicated command:** Phase verification happens once at completion. Subsequent phases may introduce changes that invalidate prior results -- a redefined symbol, a tightened approximation, a modified shared calculation. Without periodic regression checking, these silent breakages accumulate until the research narrative is internally inconsistent.

**The principle:** Every claim or check marked VERIFIED in a phase's VERIFICATION.md should remain verifiable against the current project state. If it doesn't, something changed that invalidated the original verification.

Output: `.gpd/REGRESSION-REPORT.md` with re-check results, regressions flagged with severity and affected phases, and recommended fixes.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/regression-check.md
</execution_context>

<context>
Scope: $ARGUMENTS (optional)
- If a number (e.g., "3"): re-check verified results only for that phase
- If empty: re-check verified results across all completed phases

@.gpd/STATE.md
@.gpd/ROADMAP.md
</context>

<process>
Execute the regression-check workflow from @{GPD_INSTALL_DIR}/workflows/regression-check.md end-to-end.
Preserve all workflow gates (discovery, extraction, re-verification, cross-phase consistency, report generation).

The regression check evaluates previously verified results across these dimensions:

1. **Equation integrity** -- Do equations from prior phases still hold given any subsequent modifications to shared derivations or definitions?
2. **Dimensional consistency** -- Do all verified expressions still have correct dimensions given any convention changes in later phases?
3. **Limiting cases** -- Do previously verified limits still hold given parameter regime changes in later work?
4. **Artifact integrity** -- Do referenced artifacts (derivations, notebooks, data files) still exist and contain the expected content?
5. **Cross-phase notation** -- Are symbols used in verified results still defined the same way across the project?
6. **Approximation validity** -- Are approximation regimes assumed in verified results still valid given parameters explored in later phases?

## Severity Classification

- **CRITICAL** -- A verified result is now demonstrably false (equation wrong, dimension mismatch, limit fails). Blocks all downstream work that depends on it.
- **MAJOR** -- A verified result cannot be re-confirmed (supporting artifact missing, referenced derivation modified). Must be re-verified before conclusions are drawn.
- **MINOR** -- A verified result still holds but with caveats (notation inconsistency, approximation near regime boundary). Should be resolved before publication.
- **NOTE** -- Observation for the record (e.g., "the result still holds but the supporting derivation was refactored").
  </process>

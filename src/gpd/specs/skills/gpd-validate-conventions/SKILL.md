---
name: gpd-validate-conventions
description: Validate convention consistency across all phases
argument-hint: "[phase number to limit scope, or empty for all]"
allowed-tools:
  - read_file
  - shell
  - grep
  - glob
---

<!-- Platform: Claude Code. Tool names and @ includes are platform-specific. -->
<!-- allowed-tools listed are Claude Code tool names. Other platforms use different tool interfaces. -->

<objective>
Validate that physics conventions (metric signature, Fourier convention, natural units, gauge choice, etc.) are used consistently across all completed phases. Detects convention drift where a symbol or convention is redefined in a later phase without updating earlier references.

Routes to the validate-conventions workflow which handles:

- Loading the convention lock from state.json
- Scanning all phase artifacts for convention usage
- Cross-checking consistency between phases
- Reporting any mismatches or drift
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/validate-conventions.md
</execution_context>

<context>
Scope: $ARGUMENTS (optional)
- If a number (e.g., "3"): validate conventions only for that phase
- If empty: validate conventions across all completed phases

@.planning/STATE.md
@.planning/ROADMAP.md
</context>

<process>
Execute the validate-conventions workflow from @{GPD_INSTALL_DIR}/workflows/validate-conventions.md end-to-end.

The workflow checks:

1. **Convention lock completeness** -- Are all relevant conventions explicitly locked in state.json?
2. **Cross-phase consistency** -- Are locked conventions used consistently in all phase artifacts?
3. **Symbol redefinition** -- Is any symbol defined differently in different phases?
4. **Approximation compatibility** -- Are approximation regimes consistent with convention choices?
</process>

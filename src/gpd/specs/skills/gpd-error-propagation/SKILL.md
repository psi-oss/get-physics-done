---
name: gpd-error-propagation
description: Track how uncertainties propagate through multi-step calculations across phases
argument-hint: "[--target quantity] [--phase-range start:end]"
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
  - glob
  - grep
  - ask_user
---

<!-- Platform: Claude Code. Tool names and @ includes are platform-specific. -->
<!-- allowed-tools listed are Claude Code tool names. Other platforms use different tool interfaces. -->

<objective>
Systematic uncertainty propagation through a derivation chain. Traces how input uncertainties flow through intermediate results to final quantities, identifies dominant error sources, and produces error budgets.

**Why a dedicated command:** Physics calculations are chains of transformations. Each intermediate quantity carries uncertainty from its inputs. Without systematic propagation, the final error bars are either absent (bad) or guessed (worse). This command makes the error budget explicit and identifies where to invest effort for maximum precision improvement.

**The principle:** Every final result depends on input parameters with uncertainties. The error budget decomposes the total uncertainty into contributions from each input, ranked by magnitude. If 90% of the uncertainty comes from one parameter, improving the others is wasted effort.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/error-propagation.md
</execution_context>

<context>
Target: $ARGUMENTS

@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<process>
Execute the error-propagation workflow from @{GPD_INSTALL_DIR}/workflows/error-propagation.md end-to-end.

## 1. Parse Target

Extract target quantity and phase range from $ARGUMENTS. If empty, prompt for target.

## 2. Execute Workflow

Follow the workflow steps: map the derivation chain, classify error sources (statistical, systematic, parametric, truncation, numerical), compute sensitivity coefficients, handle correlated uncertainties, and build the error budget.

## 3. Generate Report

Write ERROR-BUDGET.md per the workflow specification. Save to:
- Phase target: `.planning/phases/XX-name/ERROR-BUDGET.md`
- Project-wide: `.planning/analysis/error-budget-{target}.md`

## 4. Present Results

Show dominant error sources, ranked contributions, and recommendations for precision improvement.
</process>

<success_criteria>

- [ ] Derivation chain mapped from inputs to target
- [ ] All error sources classified (statistical, systematic, parametric, truncation, numerical)
- [ ] Sensitivity coefficients computed for each input parameter
- [ ] Correlated uncertainties handled (or correlation bounds computed)
- [ ] Error budget table with ranked contributions
- [ ] Dominant error source identified with recommendation
- [ ] Monte Carlo cross-check for non-linear propagation (if applicable)
- [ ] Report generated with full budget tables
- [ ] Phase boundary conventions checked for consistency
      </success_criteria>

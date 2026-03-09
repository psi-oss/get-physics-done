---
name: gpd-sensitivity-analysis
description: Systematic sensitivity analysis -- which parameters matter most and how uncertainties propagate
argument-hint: "[--target quantity] [--params p1,p2,...] [--method analytical|numerical]"
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
Determine which input parameters most strongly affect output quantities. Compute partial derivatives, condition numbers, and rank parameters by sensitivity. Identifies which measurements or calculations would most improve final results.

**Why a dedicated command:** Physics models often have many parameters, but results are typically dominated by a few. Before investing effort in high-precision determination of all parameters, identify which ones actually matter. A parameter with sensitivity coefficient 0.01 can be known to 10% without affecting the result, while one with coefficient 5.0 needs sub-percent precision.

**The principle:** Sensitivity analysis answers "where should I invest my effort?" It maps the parameter space into regions of high and low impact on observables, identifies phase transitions and critical thresholds, and reveals which directions in parameter space are stiff (high sensitivity) vs. sloppy (low sensitivity).
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md
</execution_context>

<context>
Target: $ARGUMENTS

@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<process>
Execute the sensitivity-analysis workflow from @{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md end-to-end.

## 1. Parse Arguments

Extract from $ARGUMENTS: `--target` quantity, `--params` list, `--method` (analytical|numerical). If insufficient, prompt for target observable and parameters.

## 2. Execute Workflow

Follow the workflow steps: identify parameters and observables, select sensitivity method (local/Morris/Sobol/analytical based on parameter count), compute sensitivity coefficients, rank parameters (stiff vs sloppy), identify critical thresholds and regime boundaries.

## 3. Generate Report

Write SENSITIVITY.md per the workflow specification. Save to:
- Phase target: `.planning/phases/XX-name/SENSITIVITY.md`
- Project-wide: `.planning/analysis/sensitivity-{target}.md`

## 4. Present Results

Show ranked sensitivity table, stiff/sloppy classification, critical thresholds, and recommendations for effort prioritization.
</process>

<success_criteria>

- [ ] All parameters and observables identified
- [ ] Sensitivity method selected with justification
- [ ] Sensitivity coefficients computed for each parameter
- [ ] Parameters ranked by importance (stiff vs. sloppy)
- [ ] Critical thresholds and regime boundaries identified
- [ ] Interaction effects assessed (for Sobol/Morris)
- [ ] Recommendations given for effort prioritization
- [ ] Report generated with ranked sensitivity table
- [ ] Dimensionless coefficients used throughout
      </success_criteria>

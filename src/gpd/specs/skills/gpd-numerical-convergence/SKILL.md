---
name: gpd-numerical-convergence
description: Systematic convergence testing for numerical physics computations
argument-hint: "[phase number or file path]"
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
  - grep
  - glob
  - ask_user
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for non-Claude runtimes. -->

<objective>
Perform systematic convergence tests on numerical computations in a physics project. Identifies all numerical parameters, varies them systematically, determines convergence rates, applies Richardson extrapolation where applicable, and assesses numerical trustworthiness.

**Why a dedicated command:** Numerical physics results are only meaningful if they are converged. A ground-state energy computed on a 10-point grid might differ from the converged value by 50%. Without systematic convergence testing, numerical results are uncontrolled approximations masquerading as answers.

**The principle:** Every numerical result depends on discretization parameters (grid size, time step, basis size, sample count, cutoff). A result is converged when further refinement changes it by less than the stated tolerance. If convergence has not been demonstrated, the result carries no error bars and cannot be trusted.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/numerical-convergence.md
</execution_context>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3"): test convergence for all numerical results in phase 3
- If a file path: test convergence for computations in that file
- If empty: prompt for target
  </context>

<process>
Execute the numerical-convergence workflow from @{GPD_INSTALL_DIR}/workflows/numerical-convergence.md end-to-end.

## 1. Parse Target

Interpret $ARGUMENTS: phase number (test all numerical results in that phase), file path (test computations in that file), or empty (prompt for target).

## 2. Execute Workflow

Follow the workflow steps: identify numerical computations, classify methods, design convergence tests with geometric refinement sequences, estimate convergence rates, apply Richardson extrapolation, assess convergence grades (A through F), and check for special issues (stiffness, cancellation, critical slowing).

## 3. Generate Report

Write CONVERGENCE.md per the workflow specification. Save to:
- Phase target: `.planning/phases/XX-name/CONVERGENCE.md`
- File target: `.planning/analysis/convergence-{slug}.md`

## 4. Present Results

Show convergence grades, error estimates, and recommendations for non-converged results.

**For comprehensive verification** (dimensional analysis + limiting cases + symmetries + convergence), use `$gpd-verify-work`.
</process>

<success_criteria>

- [ ] All numerical computations in target identified
- [ ] Numerical parameters cataloged for each computation
- [ ] Expected convergence behavior stated for each method
- [ ] Convergence tests designed with geometric refinement sequences
- [ ] Tests executed (or test scripts generated if too expensive to run)
- [ ] Convergence rates estimated from data
- [ ] Richardson extrapolation applied where appropriate
- [ ] Convergence grades assigned (A through F)
- [ ] Error estimates provided
- [ ] Special issues identified (stiffness, cancellation, critical slowing)
- [ ] Report generated with full data tables
- [ ] Recommendations given for non-converged results
      </success_criteria>

---
name: gpd-parameter-sweep
description: Systematic parameter sweep with parallel execution and result aggregation
argument-hint: "[phase] [--param name --range start:end:steps] [--adaptive] [--log]"
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
  - glob
  - grep
  - ask_user
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Execute a systematic parameter sweep: vary one or more parameters across a range, collect results, and produce summary tables and data. Uses wave-based parallelism for independent parameter values.

**Why a dedicated command:** Parameter sweeps are the workhorse of computational physics — mapping phase diagrams, finding critical points, checking universality, validating scaling laws. But sweeps done ad hoc lead to wasted compute (uniform grids in boring regions), missed features (phase transitions between grid points), and disorganized results (scattered output files). This command structures the sweep from design through execution to analysis.

**The principle:** A well-designed sweep puts points where the physics is, not on a uniform grid. It monitors convergence during execution, refines near interesting features, and produces structured output that downstream analysis can consume.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/parameter-sweep.md
</execution_context>

<context>
Phase: $ARGUMENTS

@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<process>
Execute the parameter-sweep workflow from @{GPD_INSTALL_DIR}/workflows/parameter-sweep.md end-to-end.

## 1. Parse Arguments

Extract from $ARGUMENTS: phase number, `--param` name, `--range` start:end:steps, `--adaptive` flag, `--log` flag. If insufficient, prompt for sweep parameters.

## 2. Execute Workflow

Follow the workflow steps: define parameter space (sweep/fixed params, observables, constraints), select grid type (uniform/log/Chebyshev/adaptive/Latin Hypercube), design wave structure for parallel execution, run sweep with convergence monitoring, and apply adaptive refinement if `--adaptive`.

## 3. Generate Report

Write SWEEP-{slug}.md and data files per the workflow specification. Save to:
- Phase target: `.planning/phases/XX-name/SWEEP-{slug}.md` + data files
- Standalone: `.planning/analysis/sweep-{slug}/`

## 4. Present Results

Show detected features (phase boundaries, extrema, scaling laws), data summary, and convergence status at each point.
</process>

<success_criteria>

- [ ] Parameter space fully defined (sweep params, fixed params, ranges, scaling)
- [ ] Grid type selected with justification (uniform, log, adaptive, etc.)
- [ ] Wave structure designed for parallel execution
- [ ] Sweep executed with convergence monitoring
- [ ] Adaptive refinement applied near interesting features (if --adaptive)
- [ ] Phase boundaries, extrema, and scaling laws identified
- [ ] Machine-readable data files produced (CSV, JSON)
- [ ] Summary report with detected features and visualizations
- [ ] Convergence verified at representative points
      </success_criteria>

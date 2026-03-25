---
name: gpd:execute-phase
description: Execute all plans in a phase with wave-based parallelization
argument-hint: "<phase-number> [--gaps-only]"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md"]
  state: "phase_planned"
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - find_files
  - search_files
  - shell
  - task
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Execute all plans in a phase using wave-based parallel execution.

Orchestrator stays lean: discover plans, analyze dependencies, group into waves, spawn subagents, collect results. Each subagent loads the full execute-plan context and handles its own plan.

**Execution scope:** Each plan may involve any combination of:

- **Derivations** -- analytic calculations, symbolic manipulations, proof steps
- **Calculations** -- numerical computations, parameter sweeps, optimization
- **Numerical implementations** -- writing simulation code, solvers, integrators
- **Data analysis** -- processing simulation output, statistical analysis, fitting
- **Figure generation** -- plots, phase diagrams, schematic illustrations
- **LaTeX writing** -- manuscript sections, appendices, supplementary material

Context budget: ~15% orchestrator, 100% fresh per subagent.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/execute-phase.md
@{GPD_INSTALL_DIR}/references/ui/ui-brand.md
</execution_context>

<context>
Phase: $ARGUMENTS

**Flags:**

- `--gaps-only` -- Execute only gap closure plans (plans with `gap_closure: true` in frontmatter). Use after verify-work creates fix plans.

@GPD/ROADMAP.md
@GPD/STATE.md
</context>

<inline_guidance>

## Error Recovery

- **Subagent failure:** If a subagent fails or produces an empty/invalid result, do NOT silently continue. Re-read the PLAN.md task, check if the task was well-specified, and retry with clarified instructions. If it fails again, mark the task as blocked and continue with independent tasks.
- **Derivation dead end:** When an analytical approach hits an obstruction (integral diverges, series doesn't converge, symmetry argument fails), stop and record what was tried and why it failed. Consider: (1) different regularization, (2) different variable/representation, (3) known result from literature as cross-check. Do not push through without understanding why.
- **Numerics don't converge:** Check in this order: (1) units and dimensions of all inputs, (2) boundary/initial conditions, (3) grid resolution or step size, (4) algorithm suitability for the problem's stiffness or oscillatory character. Log the convergence behavior (error vs iteration/grid size) before changing approach.
- **Sign or factor errors:** When intermediate results disagree with expectations, trace backward through each step rather than adjusting by hand. A sign error usually indicates a missed minus from integration by parts, a commutator, or a Fourier convention mismatch.

## Physics-Specific Execution Tips

- **Dimensional consistency after each task:** Before moving to the next task, verify that all new expressions have correct dimensions. This catches errors cheapest when they are fresh.
- **Check approximation validity:** After obtaining numerical values, verify that the parameter regime still satisfies the assumptions made in the plan (e.g., coupling constant still small, temperature still above the scale where quantum corrections matter).
- **Watch for convention mismatches:** When combining results from different tasks or literature, verify sign conventions (metric signature, Fourier transform convention, commutator vs anticommutator), unit systems (natural units, Gaussian, SI), and index placement.
- **Record intermediate results:** Write key intermediate expressions to the SUMMARY.md as they are obtained, not just the final answer. This aids debugging and enables partial-result recovery.

## Inter-wave Verification Gates

Between waves, the orchestrator can run lightweight verification on the just-completed wave's SUMMARY.md outputs (dimensional consistency, convention checks, and other class-specific scans). This is controlled by `execution.review_cadence`, together with the phase classification rules in the full workflow:

- `"dense"` — always run the bounded inter-wave review gates
- `"adaptive"` (default) — run the gates when the completed wave created or challenged decisive downstream evidence, baseline selection, or fanout-critical results
- `"sparse"` — skip routine inter-wave gates unless the wave raised a failed sanity check, anchor gap, or dependency warning

Cost: ~2-5k tokens per gate. Catches sign errors and convention drift before they propagate to downstream waves.

## Partial Completion and Resumption

- If execution is interrupted (context limit, user stop, crash), the completed task SUMMARY.md files are already written.
- On resumption, the orchestrator detects which plans already have SUMMARY.md files and skips them.
- To force re-execution of a completed plan, delete or rename its SUMMARY.md before re-running `/gpd:execute-phase`.
- The orchestrator applies returned shared-state updates after each successfully completed plan, so by the time a wave completes `STATE.md` already reflects that plan-level progress.

</inline_guidance>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read the file at {GPD_INSTALL_DIR}/workflows/execute-phase.md — this contains the complete step-by-step instructions. Do NOT improvise. Follow the workflow file exactly.

Execute the workflow end-to-end.
Preserve all workflow gates (wave execution, checkpoint handling, verification, state updates, routing).
</process>

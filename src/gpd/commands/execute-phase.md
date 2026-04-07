---
name: gpd:execute-phase
description: Execute all plans in a phase with wave-based parallelization
argument-hint: "<phase-number> [--gaps-only]"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md"]
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

<!-- Tool names and @ includes are runtime-specific; the installer rewrites paths for your runtime. -->

<objective>
Execute all phase plans with wave-based parallelization.

The orchestrator discovers plans, groups them into waves, spawns subagents, and collects results while each subagent owns its own plan.

Plans may cover derivations, calculations, numerical implementations, data analysis, figure generation, or LaTeX writing.

Context budget: ~15% orchestrator, fresh context per subagent.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/execute-phase.md
</execution_context>

<context>
Phase: $ARGUMENTS

**Flags:**

- `--gaps-only` -- Execute only gap-closure plans (`gap_closure: true`). Use after `verify-work` creates fix plans.

Shared-state updates land after each completed plan, so the orchestrator keeps the shared execution ledger current by wave end.
</context>

<inline_guidance>

## Error Recovery

- **Subagent failure:** Re-read the `PLAN.md` task, clarify it, and retry; if it still fails, mark the task blocked and continue.
- **Derivation dead end:** Stop, record what failed, and try a different representation, regularization, or cross-check.
- **Numerics don't converge:** Check units, boundary conditions, resolution, and algorithm fit before changing approach.
- **Sign or factor errors:** Trace backward through each step rather than adjusting by hand.

## Physics-Specific Execution Tips

- **Dimensional consistency:** Verify dimensions before moving to the next task.
- **Approximation validity:** Check that the parameter regime still matches the plan.
- **Convention mismatches:** Verify sign conventions, unit systems, and index placement when combining results.
- **Intermediate results:** Write key expressions to `SUMMARY.md` as they are obtained.

## Inter-wave Verification Gates

Between waves, the orchestrator can run lightweight verification on the completed wave's `SUMMARY.md` outputs. This is controlled by `execution.review_cadence` and the phase classification rules in the full workflow:

- `"dense"` — always run the gates
- `"adaptive"` (default) — run the gates when the wave created or challenged decisive downstream evidence
- `"sparse"` — skip routine gates unless the wave raised a failed sanity check, anchor gap, or dependency warning

Cost: ~2-5k tokens per gate. Catches sign errors and convention drift before they propagate.

## Partial Completion and Resumption

- If execution is interrupted, completed `SUMMARY.md` files remain written.
- On resumption, the orchestrator skips plans that already have `SUMMARY.md`.
- To force re-execution, delete or rename the relevant `SUMMARY.md`.
- Shared-state updates land after each completed plan, so `STATE.md` stays current by wave end.

</inline_guidance>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read {GPD_INSTALL_DIR}/workflows/execute-phase.md first and follow it exactly.

Execute the workflow end-to-end and preserve all gates (wave execution, checkpoint handling, verification, state updates, routing).
</process>

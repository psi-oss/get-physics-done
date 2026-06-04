---
name: gpd:super-checker
description: Iterative multi-critic review loop — Agent A produces a result, N independent critics fact-check it in parallel, a meta-critic synthesizes the critiques into a complete review, Agent A revises, and the loop repeats until convergence or the loop limit is reached
argument-hint: "<task description or artifact> [--critics N] [--loops N]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
  - task
  - ask_user
help:
  group: Validation and analysis
  order: 285
  compact_description: Iterative multi-critic review-revision loop until convergence
  display_signature: gpd:super-checker <task or artifact> [--critics N] [--loops N]
  examples:
    - gpd:super-checker "Derive the ground-state energy of the quantum harmonic oscillator"
    - gpd:super-checker "Verify the one-loop beta function for QCD" --critics 5
    - gpd:super-checker "Check the numerical result in GPD/phases/03-simulation/RESULTS.md" --loops 3
  notes:
    - Default critics N=3, default loops N=5.
    - The loop exits early when the meta-critic finds no substantive criticisms.
    - The final response includes the converged result and any remaining concerns.
  root_detail_order: 125
---

<objective>
Run an iterative multi-critic review-revision loop on any physics task or artifact.

Agent A (gpd-result-solver) produces the initial result. N independent critics
(gpd-result-critic) review it simultaneously. The meta-critic (gpd-meta-critic)
synthesizes the critiques into a complete review and decides whether revision is
needed. If so, Agent A revises and the loop repeats. The loop exits on convergence
or after reaching the loop limit.

The workflow owns the loop logic, agent spawning, convergence check, and final
summary. This wrapper owns the public command surface and argument parsing.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/super-checker.md
</execution_context>

<context>
Task or artifact: $ARGUMENTS

Parse from arguments:
- The task description or artifact path (everything before any flags)
- `--critics N` — number of independent critic agents per round (default: 3)
- `--loops N` — maximum review-revision cycles (default: 5)
</context>

<process>
Follow the included super-checker workflow end-to-end.

Keep these command-surface invariants visible while delegating loop mechanics
to the workflow:

- Agent A is spawned as `subagent_type="gpd-result-solver"` and reads its role from
  `{GPD_AGENTS_DIR}/gpd-result-solver.md` before producing or revising a result.
- Critics are spawned in parallel as `subagent_type="gpd-result-critic"`.
- The meta-critic is spawned as `subagent_type="gpd-meta-critic"`.
- Model resolution: `gpd resolve-model gpd-result-solver`, `gpd-result-critic`, `gpd-meta-critic`.
- Convergence: exit the loop when the meta-critic returns `status: converged`.
- The final response includes the result text, loop count, convergence status,
  and any remaining concerns from the meta-critic.
</process>

<success_criteria>
- [ ] Arguments parsed: task/artifact, critics count, loop limit
- [ ] Agent A produced an initial result
- [ ] Each review round: N critics ran in parallel, meta-critic synthesized
- [ ] Loop exited on convergence or loop limit
- [ ] Final result, loop count, convergence status, and remaining concerns presented
</success_criteria>

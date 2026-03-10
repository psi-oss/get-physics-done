---
name: gpd:quick
description: Execute a quick research task with GPD guarantees (atomic commits, state tracking) but skip optional agents
argument-hint: ""
context_mode: project-required
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
Execute small, ad-hoc research tasks with GPD guarantees (atomic commits, STATE.md tracking) while skipping optional agents (research, plan-checker, verifier).

Quick mode is the same system with a shorter path:

- Spawns gpd-planner (quick mode) + gpd-executor(s)
- Skips gpd-phase-researcher, gpd-plan-checker, gpd-verifier
- Quick tasks live in `.gpd/quick/` separate from planned phases
- Updates STATE.md "Quick Tasks Completed" table (NOT ROADMAP.md)

Use when: You know exactly what to do and the task is small enough to not need research or verification.

Typical quick tasks in physics research:

- Quick calculation (evaluate an integral, check an order-of-magnitude estimate)
- Quick dimensional analysis check (verify units of a new expression)
- Quick literature lookup (find a specific constant, formula, or reference)
- Quick plot generation (visualize a function, overlay data sets)
- Quick sanity check (verify a sign, confirm a symmetry argument, test a special case)
- Quick unit conversion (switch between natural units and SI)
- Quick error propagation (estimate uncertainty in a derived quantity)
- Quick numerical spot-check (evaluate a formula at known parameter values)
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/quick.md
</execution_context>

<context>
@.gpd/STATE.md
</context>

<inline_guidance>

## When to Use Quick vs Full Workflow

**Use `/gpd:quick` for:**

- Single calculation (evaluate an integral, compute a coefficient, check an identity)
- Formula or factor verification (is the prefactor 1/2 or 1/4?)
- Dimensional analysis of a specific expression
- Order-of-magnitude estimate or scaling argument
- Quick numerical spot-check at known parameter values
- Small self-contained tasks with a clear one-step answer

**Use full workflow (`/gpd:plan-phase` + `/gpd:execute-phase`) for:**

- Multi-step derivations where intermediate results feed into later steps
- Numerical pipelines requiring convergence testing and parameter sweeps
- Work that must be traceable to requirements (REQ-IDs)
- Anything that might produce results cited in a paper

## Rigor Expectations in Quick Mode

Quick mode skips research and verification agents, but the physics must still be correct:

- State assumptions and approximations even for quick tasks
- Include dimensional analysis for any new expression produced
- If a quick task reveals unexpected complexity, stop and promote it to a full phase with `/gpd:add-phase` or `/gpd:insert-phase`

</inline_guidance>

<process>
Execute the quick workflow from @{GPD_INSTALL_DIR}/workflows/quick.md end-to-end.
Preserve all workflow gates (validation, task description, planning, execution, state updates, commits).
</process>

---
name: gpd:plan-phase
description: Create detailed execution plan for a phase (PLAN.md) with verification loop
argument-hint: "[phase] [--research] [--skip-research] [--gaps] [--skip-verify] [--light] [--inline-discuss]"
context_mode: project-required
agent: gpd-planner
requires:
  files: ["GPD/ROADMAP.md", "GPD/STATE.md"]
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
  - task
  - web_fetch
  - mcp__context7__*
---

<!-- Tool names and @ includes are runtime-specific; the installer rewrites paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may expose different tool interfaces. -->

<objective>
Create executable phase prompts (`PLAN.md`) for a research phase with built-in research and verification.

Default flow: research if needed → plan → verify → done.

Each plan should cover the mathematical approach, computational strategy, validation plan, and approximation scheme.

The orchestrator parses arguments, validates the phase, researches the domain unless skipped, spawns `gpd-planner`, verifies with `gpd-plan-checker`, iterates until pass or max iterations, and presents results.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/plan-phase.md
@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md
@{GPD_INSTALL_DIR}/references/ui/ui-brand.md
</execution_context>

<context>
Phase number: $ARGUMENTS (optional; auto-detects the next unplanned phase if omitted)

**Flags:**

- `--research` -- Re-research even if `RESEARCH.md` exists
- `--skip-research` -- Skip research and plan directly
- `--gaps` -- Gap-closure mode (`VERIFICATION.md`, no research)
- `--skip-verify` -- Skip the verification loop
- `--light` -- Produce contract-plus-constraints plans only

Normalize the phase input in step 2 before any directory lookups.
</context>

<inline_guidance>

## What Makes a Good Physics Plan

- **Atomic tasks:** Each task should produce one verifiable result; split any task that mixes outcomes.
- **Verification:** Each task must state how to check its output, including dimensional analysis, limiting cases, comparison with known results, or symmetry checks.
- **Explicit formalism:** Specify the framework, notation, and unit system up front.
- **Approximation scheme:** State what is neglected, the validity regime, and the error estimate.
- **Expected limits:** List the limits the final result must reproduce.
- **Notation locked:** Define all notation so subagents do not drift mid-phase.

## Common Failure Modes

- **Plans too large:** More than 8-10 tasks usually means the plan should be split.
- **Missing checks:** Derivation-only plans let intermediate errors propagate.
- **Unclear success criteria:** Say what result is expected and how it is checked.
- **Implicit assumptions:** Unstated approximations lead to inconsistent choices.
- **Notation drift:** Explicit conventions prevent symbol reuse.

## Quick Checklist Before Approving a Plan

- [ ] Does the plan specify the **formalism**?
- [ ] Is the **approximation scheme** explicit?
- [ ] Is there a **validation strategy** for each major result?
- [ ] Are **expected limiting cases** listed?
- [ ] Are tasks small enough for one subagent each?
- [ ] If the phase is numerical, are sweeps, convergence studies, and error budgets planned?
- [ ] If the phase has competing predictions, does it use a predict → derive → verify structure?

## Domain-Aware Planning

The planner automatically selects a **domain blueprint** based on the phase's physics:

| Domain keywords | Blueprint applied |
|----------------|-------------------|
| amplitude, Feynman, loop, renormalization | QFT: diagrams → integrals → renormalization → observables |
| Hamiltonian, order parameter, phase diagram | Condensed matter: symmetries → mean-field → fluctuations → response |
| partition function, critical exponent, Ising | Statistical mechanics: parallel analytical + numerical |
| spacetime, metric, gravitational wave | GR/cosmology: gauge choice first → constraints throughout |
| atom-light, Rabi, cavity, detuning | AMO: rotating frame → RWA validity check → master equation |
| convergence, finite element, PDE | Numerical: mandatory convergence study → production |
| matching, Wilson coefficient, EFT | EFT: power counting first → operator basis → matching |

The planner also adapts to the **project stage**: discovery, initial planning, gap closure, and revision.

</inline_guidance>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read the file at {GPD_INSTALL_DIR}/workflows/plan-phase.md — this contains the complete step-by-step instructions. Do NOT improvise. Follow the workflow file exactly.

Execute the workflow end-to-end.
Preserve all workflow gates (validation, research, planning, verification loop, routing).
</process>

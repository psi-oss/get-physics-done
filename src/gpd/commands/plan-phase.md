---
name: gpd:plan-phase
description: Create detailed execution plan for a phase (PLAN.md) with verification loop
argument-hint: "[phase] [--research] [--skip-research] [--gaps] [--skip-verify] [--light] [--inline-discuss]"
context_mode: project-required
agent: gpd-planner
requires:
  files: [".gpd/ROADMAP.md", ".gpd/STATE.md"]
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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Create executable phase prompts (PLAN.md files) for a research-project phase with integrated research and verification.

**Default flow:** Research (if needed) -> Plan -> Verify -> Done

**Planning scope:** Each plan should address:

- **Mathematical approach** -- formalism, representation, notation conventions
- **Computational strategy** -- algorithms, numerical methods, computational tools
- **Validation plan** -- analytic limits, symmetry checks, benchmark comparisons
- **Approximation scheme** -- what is being neglected, regime of validity, error estimates

**Orchestrator role:** Parse arguments, validate phase, research domain (unless skipped), spawn gpd-planner, verify with gpd-plan-checker, iterate until pass or max iterations, present results.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/plan-phase.md
@{GPD_INSTALL_DIR}/references/ui/ui-brand.md
</execution_context>

<context>
Phase number: $ARGUMENTS (optional -- auto-detects next unplanned phase if omitted)

**Flags:**

- `--research` -- Force re-research even if RESEARCH.md exists
- `--skip-research` -- Skip research, go straight to planning
- `--gaps` -- Gap closure mode (reads VERIFICATION.md, skips research)
- `--skip-verify` -- Skip verification loop
- `--light` -- Produce simplified plans: contract + constraints + high-level approach only (no code snippets, no detailed implementation steps)

Normalize phase input in step 2 before any directory lookups.
</context>

<inline_guidance>

## What Makes a Good Physics Plan

- **Atomic tasks:** Each task should produce one verifiable result (one integral evaluated, one limit checked, one plot generated). If a task description contains "and", split it.
- **Verification at every step:** Each task must state how to verify its output -- dimensional analysis, limiting case, comparison with known result, or symmetry check.
- **Dimensional analysis required:** Every task that produces an equation must include a dimensional consistency check as part of its success criteria.
- **Explicit formalism:** Specify the mathematical framework upfront (path integral vs canonical quantization, Lagrangian vs Hamiltonian, momentum space vs position space, natural units vs SI).
- **Approximation scheme stated:** Name what is being neglected, the regime of validity, and how to estimate the error introduced.
- **Expected limiting cases:** List which limits the final result must reproduce (free theory, classical limit, non-relativistic limit, known exact solutions).
- **Notation locked:** Define all notation in the plan so subagents cannot introduce conflicting conventions mid-phase.

## Common Failure Modes

- **Plans too large:** A plan with more than 8-10 tasks is usually trying to do too much. Split into multiple plans within the phase.
- **Missing verification steps:** If the plan goes derivation -> derivation -> derivation with no checks in between, intermediate errors will propagate silently.
- **Unclear success criteria:** "Derive the partition function" is not a success criterion. "Obtain Z(T) and verify it reproduces the known high-T limit Z ~ T^N" is.
- **Implicit assumptions:** Plans that don't state approximations will have subagents make their own choices, leading to inconsistencies.
- **Notation drift:** Without explicit conventions, different tasks may use the same symbol for different quantities.

## Quick Checklist Before Approving a Plan

- [ ] Does the plan specify the **formalism** (Lagrangian, Hamiltonian, path integral, etc.)?
- [ ] Is the **approximation scheme** explicit (mean field, perturbative to order N, saddle point, etc.)?
- [ ] Is there a **validation strategy** for each major result (not just at the end)?
- [ ] Are **expected limiting cases** listed with the values/behaviors they should reproduce?
- [ ] Are tasks **small enough** that a single subagent can complete each one without context overflow?
- [ ] If the phase involves **numerical experiments**, are parameter sweeps, convergence studies, and error budgets planned? (See `/gpd:parameter-sweep`, `/gpd:sensitivity-analysis`, `gpd-experiment-designer` agent)
- [ ] If the phase has **competing predictions or regime-dependent behavior**, is a hypothesis-driven plan structure used? (predict → derive → verify cycle; see `hypothesis-driven-research.md` reference in gpd-planner)

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

The planner also adapts to the **project stage**: discovery (vague idea → structured research), initial planning (domain blueprints), gap closure (targeted verification fixes), and revision (4 types: targeted fix, diagnostic, structural, supplementary).

</inline_guidance>

<process>
**CRITICAL: First, read the full workflow file using the file_read tool:**
Read the file at {GPD_INSTALL_DIR}/workflows/plan-phase.md — this contains the complete step-by-step instructions. Do NOT improvise. Follow the workflow file exactly.

Execute the workflow end-to-end.
Preserve all workflow gates (validation, research, planning, verification loop, routing).
</process>

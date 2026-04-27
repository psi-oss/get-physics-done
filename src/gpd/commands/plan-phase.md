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
---

<objective>
Create executable phase prompts for a research phase.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/plan-phase.md
</execution_context>

<context>
Phase number: $ARGUMENTS (optional; auto-detects the next unplanned phase if omitted)
Canonical contract schema and hard validation rules are enforced later by the staged planner and checker handoffs; every proof-bearing plan must surface the theorem statement, named parameters, hypotheses, quantifier/domain obligations, and intended conclusion clauses visibly enough that a later audit can detect missing coverage.

**Flags:**

- `--research` -- Re-research even if `RESEARCH.md` exists
- `--skip-research` -- Skip research and plan directly
- `--gaps` -- Gap-closure mode (`VERIFICATION.md`, no research)
- `--skip-verify` -- Skip non-proof plan checker verification after planning; proof-bearing plans still require checker review or an equivalent main-context audit
- `--light` -- Produce contract-plus-constraints plans only

Normalize the phase input before any directory lookups.
</context>

<process>
Follow the included workflow file exactly.
</process>

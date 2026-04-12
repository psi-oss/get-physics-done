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
Produce an executable phase prompt for the current research phase.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/plan-phase.md
</execution_context>

<context>
Phase number: $ARGUMENTS (optional, defaults to the next unplanned phase)

**Flags:**

- `--research` — Force re-research even when `RESEARCH.md` already exists
- `--skip-research` — Skip research and go straight to planning
- `--gaps` — Gap-closure mode (`VERIFICATION.md`, no research)
- `--skip-verify` — Skip the verification loop
- `--light` — Emit only the contract and constraint plan
- `--inline-discuss` — Capture the 2-3 most critical decisions inline instead of running `gpd:discuss-phase` for simple work
</context>

<process>
Read the workflow file defined above.
Follow the included workflow file exactly.
</process>

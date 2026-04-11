---
name: gpd:discover
description: Run discovery phase to investigate methods, literature, and approaches before planning
argument-hint: "[phase or topic] [--depth quick|medium|deep]"
context_mode: project-aware
requires:
  files: ["GPD/ROADMAP.md"]
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
  - web_search
  - web_fetch
---


<objective>
Run a standalone discovery investigation for a research phase. Surveys the physics landscape: what is known, what methods exist, what approximations are valid, what data is available.

`--depth quick` (`depth: quick`) is verification-only and returns without writing `RESEARCH.md`. Produces RESEARCH.md for `--depth medium` or `--depth deep`, which informs subsequent planning via gpd:plan-phase.

**Use this when:**

- You want to investigate before planning (survey methods, check literature)
- You need to assess feasibility of a phase approach
- You want deeper discovery than plan-phase provides automatically
- You need to resolve ambiguous or contradictory information in the literature

**Depth levels:**

- `quick` (Level 1): Verify a formula, check a convention, confirm a known result (2-5 min)
- `medium` (Level 2): Choose between methods, explore a regime, compare approaches (15-30 min)
- `deep` (Level 3): Novel problems, contradictory literature, foundational choices (1+ hour)
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/discover.md
</execution_context>

<context>
Phase or topic: $ARGUMENTS

@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Read `@{GPD_INSTALL_DIR}/workflows/discover.md` with `file_read` first.
Execute the workflow end-to-end and keep depth behavior and persistence rules unchanged.
Do not duplicate workflow internals in this wrapper.
</process>

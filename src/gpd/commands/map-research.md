---
name: gpd:map-research
description: Map existing research project — theoretical framework, computations, conventions, and open questions
argument-hint: "[optional: specific area to map, e.g., 'hamiltonian' or 'numerics' or 'perturbation-theory']"
context_mode: projectless
allowed-tools:
  - file_read
  - ask_user
  - shell
  - find_files
  - search_files
  - file_write
  - task
---

<objective>
Map an existing physics research project using parallel gpd-research-mapper agents.

Orchestrator role: validate the focus area, then hand off to the workflow-owned staged init, mapper fanout, and artifact gating.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/map-research.md
</execution_context>

<context>
Focus area: $ARGUMENTS (optional - if provided, tells the workflow which subsystem, theory sector, or computational domain to emphasize)

Project state is loaded by the workflow if it already exists; this wrapper does not duplicate discovery logic.
</context>

<process>
Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/map-research.md`.
Do not duplicate staged init, mapper fanout, or return routing here.
</process>

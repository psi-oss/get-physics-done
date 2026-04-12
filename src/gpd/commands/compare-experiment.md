---
name: gpd:compare-experiment
description: Systematically compare theoretical predictions with experimental or observational data
argument-hint: "[prediction or dataset to compare]"
context_mode: project-aware
requires:
  files: ["GPD/ROADMAP.md"]
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - web_search
  - web_fetch
  - ask_user
---


<objective>
Systematically compare theoretical predictions with experimental or observational data.
</objective>

<context>
Comparison target: $ARGUMENTS

Interpretation:

- If a prediction name: compare that specific theoretical prediction with data
- If a dataset path: compare theoretical model against that dataset
- If a phase number: compare all predictions from that phase with available data
- If empty: prompt for comparison target

Discovery hint: find artifacts/ results/ data/ figures/ simulations/ paper/ -maxdepth 4. Treat `GPD/**` as internal provenance only.

</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compare-experiment.md
</execution_context>

<process>
Follow `@{GPD_INSTALL_DIR}/workflows/compare-experiment.md` exactly.
</process>

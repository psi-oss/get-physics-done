---
name: gpd:export
description: Export research results to HTML, LaTeX, or ZIP package
argument-hint: "[--format html|latex|zip|all] [--commit]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
---


<objective>
Export research results into shareable formats. Collects key results, equations, derivations, and figures from all completed phases and packages them for external consumption.

**Formats:**

- `html`: Standalone HTML with MathJax equations, structured results, and figures
- `latex`: LaTeX document with derivations as appendices, ready for journal submission scaffold
- `zip`: Package of scripts, data files, derivations, and a README for reproducibility
- `all`: Generate all formats

Use this when sharing results with collaborators, preparing for publication, or archiving a milestone.

</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/export.md
</execution_context>

<context>
Format and commit intent: $ARGUMENTS (optional -- if not provided, ask user)

@GPD/PROJECT.md
@GPD/ROADMAP.md
@GPD/STATE.md
</context>

<process>
Execute the included export workflow end-to-end.
The workflow owns loading, format resolution, generation, file writing, and reporting.
Write files to `exports/`.
Files written to exports/ are reported by the workflow.
Do not commit generated exports unless `$ARGUMENTS` includes `--commit`.
</process>

<success_criteria>

- [ ] Export workflow executed as the authority for export mechanics
- [ ] Requested format from `$ARGUMENTS` handed to workflow-owned resolution
- [ ] Workflow-owned output and reporting contract preserved
- [ ] Text export commit skipped unless `--commit` was explicitly requested
</success_criteria>

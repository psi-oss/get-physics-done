---
name: gpd:export
description: Export research results to HTML, LaTeX, or ZIP package
argument-hint: "[--format html|latex|zip|all]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

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
Format: $ARGUMENTS (optional -- if not provided, ask user)

@.gpd/PROJECT.md
@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>
Execute the export workflow from @{GPD_INSTALL_DIR}/workflows/export.md end-to-end.

## Step 1: Load Project Context

Read PROJECT.md, ROADMAP.md, and all SUMMARY.md files from completed phases.

## Step 2: Determine Format

Parse --format from $ARGUMENTS. If not specified, ask user.

## Step 3: Generate Export

Route to appropriate generator (html, latex, zip, or all).

## Step 4: Write Output

Write files to `exports/`.

## Step 5: Report

Display file locations, sizes, and instructions for each format.
</process>

<success_criteria>

- [ ] Project context loaded (PROJECT.md, ROADMAP.md, all SUMMARYs)
- [ ] Format determined (from args or user choice)
- [ ] Export generated in requested format(s)
- [ ] Key results and equations included
- [ ] Files written to exports/
- [ ] File locations reported to user
      </success_criteria>

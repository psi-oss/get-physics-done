---
template_version: 1
---

<!-- Used by: write-paper workflow for tracking figure generation status. -->

# Figure Tracker Template

Template for `.gpd/paper/FIGURE_TRACKER.md` — registry of all figures for the manuscript with source data, dependencies, and status.

---

## File Template

```markdown
---
figure_registry:
  - id: fig-main
    label: "Fig. 1"
    kind: figure
    role: smoking_gun|benchmark|comparison|sanity_check|publication_polish|other
    path: paper/figures/fig-main.pdf
    contract_ids: [claim-id, deliverable-id]
    decisive: true
    has_units: true
    has_uncertainty: true
    referenced_in_text: true
    caption_self_contained: true
    colorblind_safe: true
    comparison_sources:
      - .gpd/comparisons/main-benchmark-COMPARISON.md
---

# Figure Tracker: [Paper Title]

**Total figures:** [N planned, M complete]
**Target journal:** [journal — affects figure format requirements]

## Format Requirements

- **File format:** [e.g., PDF (vector) for line plots, PNG/TIFF (300+ dpi) for raster]
- **Column width:** [e.g., single-column: 3.375 in / 8.6 cm; double-column: 6.75 in / 17.1 cm]
- **Font size:** [e.g., axis labels >= 8 pt after scaling to column width]
- **Color:** [e.g., colorblind-safe palette; distinguish by line style as well as color]
- **Style file:** [path to matplotlib style or plotting script, if any]

## Figure Registry

### Fig. 1: [Short descriptive title]

**Caption:** [Draft caption — should be self-contained: a reader should understand the figure from the caption alone]

| Field        | Value                                                 |
| ------------ | ----------------------------------------------------- |
| Type         | [Line plot / Scatter / Heatmap / Diagram / Schematic] |
| Role         | [smoking_gun / benchmark / comparison / sanity_check / publication_polish] |
| Source phase | [Phase X]                                             |
| Source file  | [path/to/plotting_script.py or notebook]              |
| Data file(s) | [path/to/data.csv, path/to/data2.json]                |
| Dependencies | [e.g., "Requires Phase 3 simulation output"]          |
| Equations    | [e.g., "Plots Eq. (03.8) vs numerical data"]          |
| Parameters   | [e.g., "N = 24, 28, 32; T/J = 0.1 to 5.0"]            |
| Size         | [Single-column / Double-column]                       |
| Status       | [Planned / Data ready / Draft / Polished / Final]     |
| Last updated | [YYYY-MM-DD]                                          |

**Notes:** [Any special considerations: insets, subpanels (a,b,c), log scale, etc.]

---

### Fig. 2: [Short descriptive title]

**Caption:** [Draft caption]

| Field        | Value                           |
| ------------ | ------------------------------- |
| Type         | [type]                          |
| Source phase | [Phase X]                       |
| Source file  | [path]                          |
| Data file(s) | [path(s)]                       |
| Dependencies | [dependencies]                  |
| Equations    | [relevant equations]            |
| Parameters   | [parameter values shown]        |
| Size         | [Single-column / Double-column] |
| Status       | [status]                        |
| Last updated | [YYYY-MM-DD]                    |

**Notes:** [notes]

---

### Fig. 3: [Short descriptive title]

[Same structure as above]

---

## Table Registry

### Table I: [Short descriptive title]

**Caption:** [Draft caption]

| Field        | Value                                             |
| ------------ | ------------------------------------------------- |
| Source phase | [Phase X]                                         |
| Source file  | [path/to/script or data file]                     |
| Dependencies | [e.g., "Requires converged results from Phase 3"] |
| Columns      | [List column headers: e.g., "N, T_c, nu, chi^2"]  |
| Status       | [Planned / Data ready / Draft / Final]            |
| Last updated | [YYYY-MM-DD]                                      |

---

## Dependency Graph

[Which figures depend on which data/computation:]

| Figure  | Depends on Data From | Blocked By         |
| ------- | -------------------- | ------------------ |
| Fig. 1  | [Phase 2 derivation] | [Nothing — ready]  |
| Fig. 2  | [Phase 3 simulation] | [Phase 3 complete] |
| Fig. 3  | [Phase 3 + Phase 4]  | [Phase 4 complete] |
| Table I | [Phase 3 numerics]   | [Phase 3 complete] |

## Progress Summary

| Figure  | Data Ready | Script Written | Draft Plot | Polished | Final |
| ------- | ---------- | -------------- | ---------- | -------- | ----- |
| Fig. 1  | [ ]        | [ ]            | [ ]        | [ ]      | [ ]   |
| Fig. 2  | [ ]        | [ ]            | [ ]        | [ ]      | [ ]   |
| Fig. 3  | [ ]        | [ ]            | [ ]        | [ ]      | [ ]   |
| Table I | [ ]        | [ ]            | [ ]        | [ ]      | [ ]   |
```

<guidelines>

**When to create this file:**

- At the start of the paper-writing phase
- Can be started earlier during calculation phases to plan what figures are needed

**Figure planning:**

- Every key result should have a corresponding figure or table
- Plan figures before writing — the narrative follows the figures
- Each figure must trace to a source phase and data file (no orphaned plots)
- Draft captions early — they clarify what the figure needs to show

**Status values:**

- `Planned` — know what the figure should show, no data yet
- `Data ready` — computation complete, data files exist
- `Draft` — initial plot created, not publication-quality
- `Polished` — formatted for journal, proper fonts/colors/labels
- `Final` — approved for submission, no further changes

**Common figure types in physics papers:**

- Comparison plot: theory prediction vs numerical/experimental data with error bars
- Phase diagram: parameter space map showing different phases/regimes
- Convergence plot: quantity vs resolution/system size showing convergence
- Feynman diagrams: for perturbative calculations (use TikZ-Feynman or JaxoDraw)
- Schematic: system setup, geometry, or conceptual diagram
- Data collapse: finite-size scaling collapse demonstrating universality

**Best practices:**

- Use consistent style across all figures (shared matplotlib style file or LaTeX preamble)
- Always include error bars or uncertainty bands on data points
- Label axes with quantity name, symbol, AND units: e.g., "Temperature $T/J$"
- Use colorblind-safe palettes (e.g., Okabe-Ito, viridis)
- Ensure readability at single-column width — test by printing at actual size
- Vector format (PDF/EPS) for line plots; raster (PNG, 300+ dpi) only for heatmaps/images
- Keep the `figure_registry` frontmatter in sync with decisive roles, contract IDs, and comparison artifact links so paper-quality scoring can verify the right figures automatically

</guidelines>

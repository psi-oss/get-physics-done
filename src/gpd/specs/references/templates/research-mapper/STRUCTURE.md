# STRUCTURE.md Template (computation focus)

````markdown
# Project Structure

**Analysis Date:** [YYYY-MM-DD]

## Directory Layout
```

[project-root]/
+-- [dir]/ # [Purpose]
+-- [dir]/ # [Purpose]
+-- [file] # [Purpose]

```

## Directory Purposes

**[Directory Name]:**
- Purpose: [What lives here]
- Contains: [Types of files: .tex, .py, .nb, .dat, etc.]
- Key files: `[important files]`

## Key File Locations

**Theory / Derivations:**
- `[path]`: [What physics it contains]

**Computation / Numerics:**
- `[path]`: [What it computes]

**Data / Results:**
- `[path]`: [What data, format, provenance]

**Figures / Visualization:**
- `[path]`: [What it plots]

**Configuration / Parameters:**
- `[path]`: [What parameters it defines]

## Document Dependency Graph

**LaTeX Structure:**
- Main file: `[path]`
- Inputs/Includes:
  - `[path]`: [Content]
  - `[path]`: [Content]
- Bibliography: `[path]`
- Style/Class files: `[path]`

**Computation Dependencies:**
- `[script A]` produces `[data file]`
- `[script B]` reads `[data file]`, produces `[result/figure]`
- `[notebook]` reads `[result]`, produces `[figure for paper]`

## Naming Conventions

**Files:**
- [Pattern]: [Example]
  - e.g., "LaTeX sections: `sec_[topic].tex`; Python modules: `[physics_concept].py`"

**Variables in Code:**
- [Pattern]: [Example]
  - e.g., "Hamiltonians: `H_[descriptor]`; wavefunctions: `psi_[label]`"

**LaTeX Labels:**
- [Pattern]: [Example]
  - e.g., "Equations: `eq:[section]:[name]`; Figures: `fig:[name]`; Sections: `sec:[name]`"

## Where to Add New Content

**New Derivation:**
- LaTeX: `[path]` (add new section following existing pattern)
- Supporting computation: `[path]`
- Tests/checks: `[path]`

**New Observable / Computation:**
- Implementation: `[path]`
- Unit test: `[path]`
- Results: `[path]`
- Figure: `[path]`

**New Dataset:**
- Raw data: `[path]`
- Processing script: `[path]`
- Processed output: `[path]`

**New Limiting Case / Cross-Check:**
- Analytic check: `[path]`
- Numerical verification: `[path]`

## Build and Execution

**LaTeX Compilation:**
```bash
[command]              # Compile main document
[command]              # Full build with bibliography
```

**Running Computations:**

```bash
[command]              # Main computation
[command]              # Specific analysis
```

**Generating Figures:**

```bash
[command]              # Regenerate all figures
```

## Special Directories

**[Directory]:**

- Purpose: [What it contains]
- Generated: [Yes/No]
- Committed: [Yes/No]

---

_Structure analysis: [date]_
````

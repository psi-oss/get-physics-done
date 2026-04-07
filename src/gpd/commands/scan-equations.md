---
name: gpd:scan-equations
description: Extract all equations and variables from a LaTeX document
argument-hint: "[LaTeX file path]"
context_mode: project-aware
requires:
  files: []
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
---


<objective>
Parse a LaTeX document and extract all equations, variables, and their relationships. Generates an inventory of the mathematical content suitable for verification, review, or further analysis.

**Why a dedicated command:** Before verifying equations, you need a clean extraction pass. LaTeX equation parsing is non-trivial — nested environments, custom macros, split equations, and mixed notation all require careful handling. This command provides the extraction layer that other verification commands build on.

**The principle:** Know what equations you have before you verify them. The scan produces a structured inventory: each equation with its LaTeX, type (definition, relation, constraint), line number, nearby citations, and extracted variables with their descriptions.
</objective>

<context>
LaTeX file: $ARGUMENTS

Interpretation:

- If a file path: scan that LaTeX file
- If empty: search for .tex files in paper/, artifacts/, or current directory

```bash
find paper/ artifacts/ . -maxdepth 3 -name "*.tex" 2>/dev/null | head -10
```
</context>

<process>
1. **Locate LaTeX source**: Find the target .tex file.

2. **Scan equations**: Extract all equation environments with:
   - Equation number/label
   - Raw LaTeX content
   - Equation type (definition, relation, inequality, constraint, identity)
   - Line number in source
   - Surrounding context (text before/after)
   - Nearby citations

3. **Extract variables**: For each equation, identify:
   - Variable symbols and their descriptions
   - Units where stated
   - Constraints or bounds
   - Which equations each variable appears in

4. **Generate output**:
   - Write equation inventory to `artifacts/equation-inventory.md`
   - Include summary statistics
   - Flag any parsing issues or unusual notation

5. **Report**: Print summary — number of equations by type, variables found, any warnings.
</process>

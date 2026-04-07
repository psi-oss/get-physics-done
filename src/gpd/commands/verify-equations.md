---
name: gpd:verify-equations
description: Extract and verify equations from a LaTeX paper using LVP (Literature Verification Pipeline)
argument-hint: "[LaTeX file path]"
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
---


<objective>
Scan a LaTeX document, extract all equations, and run the LVP (Literature Verification Pipeline) to verify each equation against literature, check for typos, test limiting cases, and build an equation dependency graph.

**Why a dedicated command:** Equation verification requires specialized parsing of LaTeX notation, cross-referencing with published literature, automated symbolic checking, and systematic limiting-case analysis. Manual checking is error-prone and incomplete. LVP automates the 8-stage verification flow used by PSI for paper verification.

**The principle:** Every equation in a physics paper must be traceable to literature or derivation, parsed into executable form, checked for notational consistency, and tested against known limiting cases. The verification report flags potential typos, parsing failures, and consistency issues for human review.
</objective>

<context>
LaTeX file: $ARGUMENTS

Interpretation:

- If a file path: verify equations in that LaTeX file
- If a directory: find the main .tex file and verify it
- If empty: search for .tex files in paper/, artifacts/, or current directory

Locate the LaTeX source:

```bash
find paper/ artifacts/ . -maxdepth 3 -name "*.tex" 2>/dev/null | head -10
```
</context>

<process>
1. **Locate LaTeX source**: Find the target .tex file from the argument or project structure.

2. **Extract equations**: Use the equation scanner to find all equation environments:
   - `\begin{equation}...\end{equation}`
   - `\begin{align}...\end{align}`
   - `$$...$$` and `\[...\]`
   - Inline `$...$` with significant content

3. **For each equation, run verification stages**:
   a. **Literature search**: Check citations near the equation, search arXiv for matches
   b. **Parse to SymPy**: Convert LaTeX to executable Python/SymPy, using literature context to resolve ambiguities
   c. **Typo detection**: Compare notation against literature versions, flag sign/coefficient/exponent differences
   d. **Limiting cases**: Test known limits (variable → 0, 1, ∞) against expected behavior
   e. **Approximation checks**: Verify stated approximations (leading order, Taylor, asymptotic)
   f. **Dependency graph**: Map which equations depend on which others

4. **Generate report**: Produce a per-equation verification report with:
   - Status: PASS, WARN, FAIL, NEEDS_REVIEW
   - Literature matches with arXiv links
   - Parsing result (success/failure with error details)
   - Typo flags with suggestions
   - Limiting case results
   - Dependency relationships

5. **Write output**: Save the verification report to `artifacts/lvp-report.md` and optionally generate a Jupyter notebook for interactive debugging at `artifacts/equation_verification.ipynb`.

6. **Summary**: Print overall statistics — total equations, parse success rate, potential typos, issues requiring attention.
</process>

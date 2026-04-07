---
name: gpd:check-citations
description: Verify citations and cross-reference equations with their literature sources
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
  - web_search
  - web_fetch
---


<objective>
Extract citations from a LaTeX paper, resolve them to arXiv/DOI entries, and cross-reference each equation with its cited sources. Identifies equations lacking citations, citations that don't match their claimed content, and potential attribution gaps.

**Why a dedicated command:** Citation correctness is a major source of errors in physics papers. Equations are often attributed to the wrong paper, cited with incorrect notation conventions from the source, or presented without any attribution when they should have one. Automated checking catches these systematically.

**The principle:** Every non-trivial equation should either be derived in the paper or properly cited. This command maps the citation graph: which equations cite which papers, whether those papers actually contain the claimed equation, and whether the notation matches.
</objective>

<context>
LaTeX file: $ARGUMENTS

Interpretation:

- If a file path: check citations in that LaTeX file
- If empty: search for .tex files in paper/, artifacts/, or current directory

```bash
find paper/ artifacts/ . -maxdepth 3 -name "*.tex" -o -name "*.bib" 2>/dev/null | head -10
```
</context>

<process>
1. **Locate sources**: Find the .tex file and any .bib files.

2. **Extract citations**: Parse all `\cite{}`, `\citep{}`, `\citet{}` commands and map them to bibliography entries.

3. **Resolve to arXiv/DOI**: For each citation:
   - Extract arXiv ID if present in .bib
   - Search arXiv API for paper metadata
   - Note title, authors, year

4. **Map equations to citations**: For each equation, find citations within ±3 lines of context. Build an equation→citation graph.

5. **Identify gaps**:
   - Equations with no nearby citations that aren't derived in-text
   - Citations referenced but not in bibliography
   - Bibliography entries never cited

6. **Cross-reference check**: Where possible, verify that the cited paper actually contains a version of the claimed equation.

7. **Generate report**: Write to `artifacts/citation-report.md` with:
   - Citation inventory with resolution status
   - Equation-to-citation mapping
   - Gaps and issues flagged
   - Suggestions for missing attributions
</process>

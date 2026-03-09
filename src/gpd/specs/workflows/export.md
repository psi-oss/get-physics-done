<purpose>
Export research results into shareable formats. Collects key results, equations, derivations, and figures from all completed phases and packages them for external consumption. Supports HTML (with MathJax), LaTeX (journal-ready scaffold), ZIP (reproducibility package), or all formats.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="load_context">
**Load project context:**

Read:

- `.planning/PROJECT.md` -- project title, description, conventions
- `.planning/ROADMAP.md` -- phase structure and status
- `.planning/STATE.md` -- current position

```bash
ROADMAP=$(gpd roadmap analyze)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd roadmap analyze failed: $ROADMAP"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract: `project_title`, `milestone`, completed phases list, total phase count.

**If no completed phases:**

```
╔══════════════════════════════════════════════════════════════╗
║  ERROR                                                       ║
╚══════════════════════════════════════════════════════════════╝

No completed phases found. Nothing to export.

Complete at least one phase before exporting:
  $gpd-execute-phase <phase-number>
```

Exit.
</step>

<step name="collect_results">
**Scan all completed phase directories for exportable content:**

For each completed phase:

1. Read all SUMMARY.md files:

```bash
gpd summary-extract {path} --field one_liner --field key_results --field equations --field key_files
```

2. Collect:

   - **Key results** -- equations, numerical values, qualitative findings
   - **Equations** -- all numbered equations from derivations
   - **Scripts** -- `*.py`, `*.jl`, `*.m`, `*.nb` files
   - **Data files** -- `*.csv`, `*.json`, `*.dat`, `*.h5`
   - **Figures** -- `*.png`, `*.pdf`, `*.svg` in phase directories
   - **Convention changes** -- from SUMMARY.md `affects` fields

3. Also collect VERIFICATION.md results for validation summary.

Store collected items grouped by phase.
</step>

<step name="determine_format">
**Parse format from arguments:**

Parse `--format` from $ARGUMENTS.

| Argument                    | Format      |
| --------------------------- | ----------- |
| `--format html` or `html`   | HTML only   |
| `--format latex` or `latex` | LaTeX only  |
| `--format zip` or `zip`     | ZIP only    |
| `--format all` or `all`     | All formats |
| (none)                      | Ask user    |

**If no format specified, ask:**

```
╔══════════════════════════════════════════════════════════════╗
║  CHECKPOINT: Decision Required                               ║
╚══════════════════════════════════════════════════════════════╝

Export format:

1. **html**  -- Standalone HTML with MathJax equations and structured results
2. **latex** -- LaTeX document scaffold ready for journal submission
3. **zip**   -- Reproducibility package (scripts, data, derivations, README)
4. **all**   -- Generate all formats

──────────────────────────────────────────────────────────────
→ Select: 1 / 2 / 3 / 4
──────────────────────────────────────────────────────────────
```

</step>

<step name="create_export_dir">
**Create export directory:**

```bash
mkdir -p .planning/exports
```

</step>

<step name="generate_html">
**If format is `html` or `all`:**

Write `.planning/exports/results.html`:

Structure:

```html
<!doctype html>
<html>
  <head>
    <title>{project_title} -- Research Results</title>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
      body {
        font-family: "Computer Modern", Georgia, serif;
        max-width: 900px;
        margin: 0 auto;
        padding: 2em;
      }
      h1 {
        border-bottom: 2px solid #333;
      }
      h2 {
        color: #444;
        margin-top: 2em;
      }
      table {
        border-collapse: collapse;
        width: 100%;
        margin: 1em 0;
      }
      th,
      td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
      }
      th {
        background-color: #f5f5f5;
      }
      .equation {
        margin: 1em 2em;
        padding: 0.5em;
        background: #fafafa;
        border-left: 3px solid #ccc;
      }
      .phase {
        margin: 2em 0;
        padding: 1em;
        border: 1px solid #eee;
        border-radius: 4px;
      }
      .verification {
        padding: 0.5em 1em;
        border-radius: 4px;
      }
      .passed {
        background: #e8f5e9;
      }
      .warning {
        background: #fff3e0;
      }
      .failed {
        background: #ffebee;
      }
    </style>
  </head>
  <body>
    <h1>{project_title}</h1>
    <p><em>Generated: {YYYY-MM-DD} | Milestone: {milestone_name}</em></p>

    <h2>Summary</h2>
    <p>{project description from PROJECT.md}</p>

    <h2>Results by Phase</h2>
    {For each completed phase:}
    <div class="phase">
      <h3>Phase {N}: {Name}</h3>
      <p>{one_liner from SUMMARY.md}</p>
      <h4>Key Results</h4>
      <ul>
        {key results as list items}
      </ul>
      <h4>Equations</h4>
      {equations wrapped in \(...\) or \[...\] for MathJax}
    </div>

    <h2>Conventions</h2>
    {Convention table from PROJECT.md and affects fields}

    <h2>Verification Summary</h2>
    {Aggregate verification results}
  </body>
</html>
```

</step>

<step name="generate_latex">
**If format is `latex` or `all`:**

Write `.planning/exports/results.tex`:

Structure:

```latex
\documentclass[12pt,a4paper]{article}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{physics}
\usepackage{hyperref}
\usepackage{booktabs}
\usepackage{graphicx}

\title{{project_title}}
\author{[Author Name]}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
{Project description from PROJECT.md -- placeholder for user to refine}
\end{abstract}

\section{Introduction}
% Generated scaffold -- fill in motivation and context

\section{Methods}
% Generated from phase descriptions and approaches

{For each completed phase:}
\subsection{Phase {N}: {Name}}
{One-liner description}

\subsubsection{Key Results}
\begin{itemize}
{key results as \item entries}
\end{itemize}

{Equations as \begin{equation} blocks}

\section{Results}
% Aggregate key findings across all phases

\section{Discussion}
% Placeholder for interpretation

\section{Conclusion}
% Placeholder for summary

\appendix
{For each phase with detailed derivations:}
\section{Phase {N}: {Name} -- Derivation Details}
{Detailed derivation content from SUMMARY.md}

\end{document}
```

Also write `.planning/exports/results.bib` if any citations found in SUMMARY files.
</step>

<step name="generate_zip">
**If format is `zip` or `all`:**

Collect all exportable files:

1. All scripts (`*.py`, `*.jl`, `*.m`, `*.nb`) from completed phase directories
2. All data files (`*.csv`, `*.json`, `*.dat`, `*.h5`) from completed phase directories
3. All SUMMARY.md files
4. PROJECT.md and ROADMAP.md
5. VERIFICATION.md files

Write `.planning/exports/README.md`:

```markdown
# {project_title} -- Reproducibility Package

## Contents

- `scripts/` -- Computation scripts by phase
- `data/` -- Output data files by phase
- `summaries/` -- Research summary for each plan
- `PROJECT.md` -- Project description and conventions
- `ROADMAP.md` -- Research phase structure

## Phase Index

{Table: phase number, name, status, scripts included, data included}

## Reproduction Instructions

{For each phase with scripts: how to run them, dependencies, expected outputs}

## Generated

Date: {YYYY-MM-DD}
Tool: GPD (Get Physics Done)
```

Copy collected files into the exports directory structure:

```bash
mkdir -p .planning/exports/scripts .planning/exports/data .planning/exports/summaries
# Copy scripts, data, SUMMARYs from phase directories into exports/
cp .planning/PROJECT.md .planning/exports/PROJECT.md 2>/dev/null
cp .planning/ROADMAP.md .planning/exports/ROADMAP.md 2>/dev/null
# Copy phase scripts/data/summaries into their respective subdirectories
```

Create the ZIP:

```bash
cd .planning/exports && zip -r results.zip README.md scripts/ data/ summaries/ PROJECT.md ROADMAP.md 2>/dev/null
```

If no zip utility available, create a tar.gz instead:

```bash
cd .planning/exports && tar -czf results.tar.gz README.md scripts/ data/ summaries/ PROJECT.md ROADMAP.md 2>/dev/null
```

</step>

<step name="report">
**Present export summary:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > EXPORT COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Project:** {project_title}
**Phases exported:** {N} completed phases
**Formats:** {list of formats generated}

| File | Size | Format |
|------|------|--------|
| .planning/exports/results.html | {size} | HTML + MathJax |
| .planning/exports/results.tex | {size} | LaTeX |
| .planning/exports/results.bib | {size} | BibTeX |
| .planning/exports/results.zip | {size} | ZIP package |

### Notes

- **HTML:** Open in any browser. Equations render via MathJax (requires internet).
- **LaTeX:** Compile with `pdflatex results.tex`. Fill in [Author Name] and placeholder sections.
- **ZIP:** Self-contained reproducibility package with README.

───────────────────────────────────────────────────────────────

**Also available:**
- `$gpd-write-paper` -- draft a full paper from research results
- `$gpd-progress` -- check research progress

───────────────────────────────────────────────────────────────
```

</step>

<step name="commit_exports">
**Commit text-based exports (not binary archives):**

Commit the HTML and LaTeX exports. Do NOT commit ZIP/tar.gz archives (binary artifacts that bloat git).

```bash
# Only commit text-format exports
PRE_CHECK=$(gpd pre-commit-check --files .planning/exports/results.html .planning/exports/results.tex .planning/exports/results.bib 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: export research results" \
  --files .planning/exports/results.html .planning/exports/results.tex .planning/exports/results.bib
```

The `commit` CLI respects `commit_docs` from config internally — if disabled, the commit is automatically skipped.
</step>

</process>

<anti_patterns>

- Don't export incomplete phases -- only include phases with at least one SUMMARY.md
- Don't hardcode MathJax version -- use latest CDN URL
- Don't skip the verification summary -- collaborators need to know what's validated
- Don't include raw planning artifacts (PLAN.md, RESEARCH.md) in exports -- those are internal
- Don't overwrite existing exports without noting it
- Don't generate empty sections -- omit sections with no content
- Don't commit ZIP/tar.gz archives to git -- they are binary artifacts
  </anti_patterns>

<success_criteria>
Export is complete when:

- [ ] Project context loaded (PROJECT.md, ROADMAP.md, all SUMMARYs)
- [ ] Format determined (from args or user choice)
- [ ] Only completed phases with SUMMARYs included
- [ ] Key results and equations extracted and formatted
- [ ] Export generated in requested format(s)
- [ ] Files written to .planning/exports/
- [ ] File locations and sizes reported to user
- [ ] Format-specific instructions provided
- [ ] Text exports committed (if commit_docs enabled)

</success_criteria>

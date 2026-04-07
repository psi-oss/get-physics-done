---
name: gpd:arxiv-submission
description: Prepare a paper for arXiv submission with validation and packaging
argument-hint: "[paper directory path]"
context_mode: project-required
requires:
  files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex"]
review-contract:
  review_mode: publication
  schema_version: 1
  required_outputs:
    - arxiv-submission.tar.gz
  required_evidence:
    - compiled manuscript
    - manuscript-root bibliography audit
    - manuscript-root artifact manifest
    - latest peer-review review ledger
    - latest peer-review referee decision
  blocking_conditions:
    - missing project state
    - missing manuscript
    - missing manuscript-root artifact manifest
    - missing manuscript-root bibliography audit
    - missing compiled manuscript
    - missing conventions
    - missing latest staged peer-review decision evidence
    - unresolved publication blockers
    - latest staged peer-review recommendation blocks submission packaging
    - degraded review integrity
  preflight_checks:
    - command_context
    - project_state
    - manuscript
    - artifact_manifest
    - bibliography_audit
    - bibliography_audit_clean
    - compiled_manuscript
    - conventions
    - publication_blockers
    - review_ledger
    - review_ledger_valid
    - referee_decision
    - referee_decision_valid
    - publication_review_outcome
    - manuscript_proof_review
  conditional_requirements:
    - when: theorem-bearing manuscripts are present
      required_evidence:
        - cleared manuscript proof review for theorem-bearing manuscripts
      blocking_conditions:
        - missing or stale manuscript proof review for theorem-bearing manuscripts
      blocking_preflight_checks:
        - manuscript_proof_review
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
---


<objective>
Prepare a completed paper for arXiv submission. Handles the full submission pipeline: LaTeX validation, figure embedding, bibliography flattening, file packaging, and metadata generation.

**Why a dedicated command:** arXiv has specific requirements (no subdirectories in uploads, .bbl instead of .bib, specific figure formats, 00README.XXX for multi-file submissions). Getting these wrong means rejected submissions and wasted time. This command automates the tedious compliance steps.

Output: A submission-ready tarball and checklist of manual steps remaining.

The workflow's preflight gate checks the explicit paper target, the manuscript-root artifact gates, the compiled manuscript, unresolved publication blockers, the latest staged review decision, and for theorem-bearing manuscripts a cleared manuscript proof-review status before packaging begins.
In strict mode that bibliography gate is semantic: `BIBLIOGRAPHY-AUDIT.json` must also pass `bibliography_audit_clean`, not merely exist.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/arxiv-submission.md
@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md
@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md
@{GPD_INSTALL_DIR}/templates/paper/artifact-manifest-schema.md
@{GPD_INSTALL_DIR}/templates/paper/bibliography-audit-schema.md
@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md
@{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md
</execution_context>

<context>
Paper directory: $ARGUMENTS (optional; when omitted, resolve only from `paper/`, `manuscript/`, or `draft/` manuscript roots)

@GPD/STATE.md
</context>

<process>
Apply the loaded artifact-manifest, bibliography-audit, review-ledger, referee-decision, and peer-review reliability documents literally when validating packaging readiness. Do not invent fallback review heuristics, blank `manuscript_path` placeholders, or ad hoc manuscript-root authority rules. Do not invent hidden fields or placeholder `manuscript_path` fallbacks when repairing review artifacts.

## 1. Locate Paper

Resolve the paper directory from the explicit argument when provided. Otherwise inspect only the documented manuscript roots `paper/`, `manuscript/`, and `draft/`, and use the manuscript-root artifact gates to decide which root is active:

- `ARTIFACT-MANIFEST.json` identifies the canonical manuscript entry point when present.
- `BIBLIOGRAPHY-AUDIT.json` must live beside that resolved manuscript root before packaging and must be semantically clean (`bibliography_audit_clean`).
- `PAPER-CONFIG.json` / `gpd paper-build` may refresh the manuscript and bibliography audit for that same root.
- Do not scan arbitrary `*.tex` files or rely on wildcard-based discovery.

If no manuscript root is found, suggest `gpd:write-paper` first.

## 2. Validate LaTeX

If `PAPER-CONFIG.json` exists in the paper directory, refresh the derived manuscript first:

```bash
gpd paper-build "{paper_dir}/PAPER-CONFIG.json" --output-dir "{paper_dir}"
```

```bash
cd {paper_dir} && pdflatex -interaction=nonstopmode {manuscript_stem}.tex 2>&1 | tail -20
bibtex {manuscript_stem} 2>&1 | tail -10
pdflatex -interaction=nonstopmode {manuscript_stem}.tex 2>&1 | tail -5
pdflatex -interaction=nonstopmode {manuscript_stem}.tex 2>&1 | tail -5
```

Check for:
- Undefined references
- Missing citations
- Overfull hboxes (warnings, not errors)
- Missing figures

## 3. Flatten for arXiv

**3a. Flatten \input and \include:**

```bash
# Recursive resolution of \input{file} and \include{file}
# For each \input{X} or \include{X}:
#   1. Resolve path (try X, X.tex)
#   2. Read file contents
#   3. Replace the \input/\include line with file contents
#   4. Recurse into the inserted content for nested \input
# WARNING: \include adds \clearpage — preserve this behavior
```

**3b. Inline bibliography:**

```bash
# Find \bibliography{refs} command
# Replace with contents of refs.bbl (must exist from compilation step)
# Remove \bibliographystyle{} line
# Verify: grep for remaining \bibliography commands
```

**3c. Figure format validation:**

```bash
# Check each file in \includegraphics:
# - No TIFF files (arXiv rejects)
# - EPS files: verify embedded fonts
# - PNG/JPG: minimum 150 DPI for figures, 300 DPI for text
# - PDF figures: add \pdfoutput=1 to first line of the manuscript entrypoint
```

**3d. Metadata checks:**

```bash
# Abstract length: extract abstract, count characters. Warn if > 1920
# Title: verify no LaTeX commands in title (arXiv metadata field)
# File size: total package < 50MB, individual files < 10MB
# \pdfoutput=1: verify present on first line if using PDF figures
```

**3e. Ancillary files:**

```bash
# If computational scripts exist: create anc/ directory
# Move: scripts, data files, notebooks
# Add anc/README.md with execution instructions
```

**3f. Clean auxiliary files:**

- Remove auxiliary files (.aux, .log, .out, .toc, .blg, .brf, .synctex.gz)

## 4. Generate Metadata

Create `00README.XXX` if multi-file:

```
{topic_specific_stem}.tex -- Main LaTeX file
figures/       -- Figure files
```

## 5. Package

```bash
mkdir -p arxiv-submission/
# Copy flattened files
tar czf arxiv-submission.tar.gz -C arxiv-submission .
```

## 6. Checklist

Present submission checklist:

```
## arXiv Submission Ready

**Package:** arxiv-submission.tar.gz ({size})
**Files:** {count} files

### Pre-submission Checklist
- [ ] Paper compiles without errors
- [ ] All figures render correctly
- [ ] Bibliography is complete (.bbl included)
- [ ] Abstract is under 1920 characters
- [ ] Title contains no LaTeX commands
- [ ] Author list is correct
- [ ] arXiv category selected (e.g., hep-th, cond-mat.str-el)
- [ ] License selected (typically CC BY 4.0)

### Manual Steps
1. Go to https://arxiv.org/submit
2. Upload arxiv-submission.tar.gz
3. Verify PDF renders correctly in preview
4. Add metadata (title, abstract, authors, categories)
5. Submit
```

</process>

<success_criteria>

- [ ] Paper located and validated
- [ ] LaTeX compiles without errors
- [ ] Bibliography flattened to .bbl
- [ ] Figures in arXiv-compatible formats
- [ ] Submission tarball created (not committed — binary artifact)
- [ ] Submission manifest committed
- [ ] *.tar.gz added to .gitignore
- [ ] Metadata file generated
- [ ] Pre-submission checklist presented
      </success_criteria>

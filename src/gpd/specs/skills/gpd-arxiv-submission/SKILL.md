---
name: gpd-arxiv-submission
description: Prepare a paper for arXiv submission with validation and packaging
argument-hint: "[paper directory path]"
requires:
  files: ["paper/*.tex"]
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
  - grep
  - glob
---

<!-- Platform: Claude Code. Tool names and @ includes are platform-specific. -->
<!-- allowed-tools listed are Claude Code tool names. Other platforms use different tool interfaces. -->

<objective>
Prepare a completed paper for arXiv submission. Handles the full submission pipeline: LaTeX validation, figure embedding, bibliography flattening, file packaging, and metadata generation.

**Why a dedicated command:** arXiv has specific requirements (no subdirectories in uploads, .bbl instead of .bib, specific figure formats, 00README.XXX for multi-file submissions). Getting these wrong means rejected submissions and wasted time. This command automates the tedious compliance steps.

Output: A submission-ready tarball and checklist of manual steps remaining.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/arxiv-submission.md
</execution_context>

<context>
Paper directory: $ARGUMENTS (optional, defaults to `paper/` or `manuscript/`)

@.planning/STATE.md
</context>

<process>
Execute the arxiv-submission workflow from @{GPD_INSTALL_DIR}/workflows/arxiv-submission.md end-to-end.

## 1. Locate Paper

Find the paper directory from $ARGUMENTS or search for `main.tex` in `paper/`, `manuscript/`, `draft/`. If no paper found, suggest `$gpd-write-paper` first.

## 2. Execute Workflow

Follow the workflow steps: LaTeX validation, bibliography flattening, figure format checking, \input resolution, metadata verification, ancillary file packaging.

## 3. Package and Present

Generate `arxiv-submission.tar.gz` and present the pre-submission checklist with remaining manual steps.
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

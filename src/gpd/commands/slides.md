---
name: gpd:slides
description: Create presentation slides from a GPD project or the current folder
argument-hint: "[topic, talk title, audience, or source path]"
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Create a presentation deck tailored to the user's source material, audience, and delivery format.

This command works from either:

- an active GPD project, or
- the current folder's papers, notes, figures, code, data, or existing slide assets

It should first establish the presentation brief, then produce a concrete slide structure and deck source files in a user-visible `slides/` directory.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/slides.md
</execution_context>

<context>
Presentation request: $ARGUMENTS

Scan the workspace for likely source material:

```bash
ls -d .gpd paper manuscript draft slides presentation deck figures data notebooks docs 2>/dev/null
find . -maxdepth 2 \( -name "*.tex" -o -name "*.md" -o -name "*.ipynb" -o -name "*.csv" -o -name "*.json" -o -name "*.pdf" -o -name "*.png" -o -name "*.svg" -o -name "*.pptx" -o -name "*.odp" -o -name "*.key" \) 2>/dev/null | head -120
```

If a GPD project exists, use it:

@.gpd/PROJECT.md
@.gpd/ROADMAP.md
@.gpd/STATE.md
</context>

<process>

## 1. Inspect Context

Identify the best available source material in the current workspace before asking questions.

## 2. Establish the Presentation Brief

Ask a compact set of high-leverage questions for any missing requirements, including:

- presentation goal and takeaway
- audience and technical level
- talk length or target slide count
- output format/toolchain (for example Beamer, native deck, markdown-based slides)
- template, branding, or existing slide deck constraints
- whether to refresh, update, or skip any existing slide artifacts
- emphasis (paper, derivation, data, code, demo, project status)
- level of verbosity, speaker notes, appendix/backups, and citation density

## 3. Execute the Slides Workflow

Follow the slides workflow from `@{GPD_INSTALL_DIR}/workflows/slides.md` end-to-end.

## 4. Write Deliverables

Create or update `slides/` artifacts for the selected format and report exactly what was produced.
</process>

<success_criteria>
- [ ] Relevant project or folder context identified
- [ ] Missing presentation requirements clarified with the user
- [ ] Presentation brief written with audience, scope, and format locked
- [ ] Slide outline created with a clear narrative arc
- [ ] Existing slide outputs handled explicitly (refresh, update, or skip)
- [ ] Deck source files written to `slides/`
- [ ] Any compile/render limitations or unresolved assumptions clearly reported
</success_criteria>

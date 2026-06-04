---
name: gpd:historical-roast
description: Roast a manuscript or artifact through the source-backed voice and priorities of one historical physicist or a comma-separated panel
argument-hint: '"<historical physicist[, physicist...]>" [target]'
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - web_search
  - web_fetch
  - ask_user
help:
  group: Writing and publication
  order: 445
  compact_description: Produce a source-backed, in-character historical-physicist roast under `GPD/historical-roast/`
  display_signature: 'gpd:historical-roast "<historical physicist[, physicist...]>" [target]'
  detail_signature: 'gpd:historical-roast "<historical physicist[, physicist...]>" [target]'
  examples:
    - 'gpd:historical-roast "Emmy Noether" paper/main.tex'
    - 'gpd:historical-roast "Noether, Feynman, Dirac" draft/main.md'
  notes:
    - 'The first argument is one roaster spec: either one historical physicist or a comma-separated panel.'
    - 'Do not use separate `--reviewer` or `--panel` flags; panel mode is inferred from commas in the roaster spec.'
    - 'Historical voice is allowed to be lively, but the review must first build source-backed dossiers.'
  root_detail_order: 253
---

<objective>
Produce a lightweight historical-physicist roast of a manuscript or artifact.

The first semantic argument is a single roaster spec: one historical physicist name or a comma-separated list of names. More than one comma-separated name activates panel mode. Any remaining argument text is the optional roast target. If no target is supplied, try to use the current project manuscript from `paper/`, `manuscript/`, `draft/`, or `GPD/publication/*/manuscript`; otherwise ask for a specific target path.

This is an auxiliary creative roast, not the formal staged `gpd:peer-review` decision workflow. Make it useful, pointed, and a little fun: each review should feel recognizably inspired by the named physicist's documented public style and scientific instincts, while staying grounded in sources and the target artifact.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/historical-roast.md
</execution_context>

<context>
Arguments: $ARGUMENTS
</context>

<process>
Follow the included historical-roast workflow exactly. The workflow owns reviewer-spec parsing, source-backed dossier creation, target resolution, artifact writing, and the in-character roast format.
</process>

<success_criteria>
- [ ] Roaster spec parsed from one argument, with panel mode inferred only from comma-separated names
- [ ] Unsupported `--reviewer` or `--panel` flags rejected with a corrected invocation
- [ ] Target artifact resolved from the remaining arguments or from the current project manuscript family
- [ ] Web search or web fetch used before writing each historical dossier
- [ ] One dossier per named physicist written under `GPD/historical-roast/`
- [ ] Final roast written under `GPD/historical-roast/`
- [ ] Report uses source-backed historical voice without pretending to quote or resurrect the person
- [ ] Final answer lists the written files and the strongest action items from the roast
</success_criteria>

---
name: gpd:settings
description: Configure GPD workflow toggles, tier models, and physics research preferences
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Interactive configuration of GPD workflow agents, runtime-specific tier model overrides, and physics research preferences via multi-question prompt.

Routes to the settings workflow which handles:

- Config existence ensuring
- Current settings reading and parsing
- Interactive prompt covering research profile, runtime-specific tier models, physics conventions, and workflow toggles
- Config merging and writing
- Confirmation display with quick command references
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/settings.md
</execution_context>

<process>
**Follow the settings workflow** from `@{GPD_INSTALL_DIR}/workflows/settings.md`.

The workflow handles all logic including:

1. Config file creation with defaults if missing
2. Current config reading
3. Interactive settings presentation with pre-selection, covering:
   - **Research profile**: deep-theory / numerical / exploratory / review / paper-writing
   - **Tier models for the active runtime**: leave unchanged / use runtime defaults / configure explicit tier-1, tier-2, tier-3 model strings
   - **Unit conventions**: natural / natural thermal / SI / CGS / atomic / lattice / custom
   - **Metric signature**: mostly-minus / mostly-plus / Euclidean / N/A
   - **Fourier convention**: physics / mathematics / symmetric / N/A
   - **Numerical precision**: single / double / quad / arbitrary
   - **Preferred tools**: Python, Mathematica, Julia, C/C++, Fortran, MATLAB, SymPy, Maple, FORM, Cadabra, xAct
   - **Plan researcher**: on / off
   - **Plan checker**: on / off
   - **Execution verifier**: on / off
   - **Inter-wave verification**: auto / always / never
   - **Parallel execution**: on / off
   - **Git branching**: none / per-phase / per-milestone
4. Runtime-aware model guidance when explicit tier models are requested:
   - **Claude Code**: aliases like `opus`, `sonnet`, `haiku` or pinned full names
   - **Codex**: the exact Codex model string, e.g. `gpt-5.4`
   - **Gemini CLI**: the exact Gemini model name, e.g. `gemini-2.5-pro`
   - **OpenCode**: a full `provider/model` id
5. Answer parsing and config merging
6. File writing
7. Confirmation display with current settings summary and quick command references
   </process>

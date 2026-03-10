---
name: gpd:settings
description: Configure GPD workflow toggles and physics research preferences
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Interactive configuration of GPD workflow agents and physics research preferences via multi-question prompt.

Routes to the settings workflow which handles:

- Config existence ensuring
- Current settings reading and parsing
- Interactive prompt covering research profile, physics conventions, and workflow toggles
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
   - **Coordinate system default**: Cartesian / spherical / cylindrical / covariant (user can always override per-problem)
   - **Unit conventions**: SI / natural (hbar=c=1) / Gaussian / geometric (G=c=1) / custom
   - **Metric signature**: mostly-plus (-,+,+,+) / mostly-minus (+,-,-,-)
   - **Numerical precision**: float32 / float64 / float128 / arbitrary
   - **Notation style**: index / abstract-index / coordinate-free / mixed
   - **Plan checker**: on / off (validates plans before execution)
   - **Verification agent**: on / off (cross-checks derivations with independent methods)
   - **Inter-wave verification**: auto / always / never (dimensional + convention checks between waves)
   - **Parallel execution**: on / off (execute wave plans in parallel)
   - **Literature agent**: on / off (auto-searches for relevant references)
   - **Dimensional analysis check**: on / off (validates dimensions at each step)
4. Answer parsing and config merging
5. File writing
6. Confirmation display with current settings summary and quick command references
   </process>

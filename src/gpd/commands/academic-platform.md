---
name: gpd:academic-platform
description: Configure and manage GPD academic platform mode with credit grants and artifact capture
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Enable, configure, and monitor academic platform mode for institutional GPD deployments.

Academic mode adds:
- **Credit budget tracking** — set a credit grant and track usage across sessions
- **Full event logging** — every agent invocation logged with credit metadata
- **Artifact provenance** — all outputs tracked with reproducibility metadata
- **Budget guards** — prevent runaway costs by gating expensive operations

Routes to the academic-platform workflow which handles:
- Enabling/disabling academic mode
- Setting and adjusting credit budgets
- Viewing credit usage summaries
- Managing artifact capture settings
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/academic-platform.md
</execution_context>

<process>
**Follow the academic-platform workflow** from `@{GPD_INSTALL_DIR}/workflows/academic-platform.md`.

The workflow handles all logic including:

1. Current mode detection and status display
2. Interactive configuration for:
   - **Platform mode**: standard / academic
   - **Credit budget**: integer grant amount or unlimited
   - **Artifact capture**: on / off
3. Credit usage summary with per-agent breakdowns
4. Artifact inventory with provenance details
5. Budget adjustment and reset operations
</process>

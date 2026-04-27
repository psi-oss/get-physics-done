---
name: gpd:update
description: Update GPD to latest version with changelog display
context_mode: global
allowed-tools:
  - shell
  - ask_user
---


<objective>
Check for GPD updates, install if available, and display what changed.
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/update.md
</execution_context>

<process>
Follow the included update workflow exactly.
   </process>

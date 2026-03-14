---
name: gpd:update
description: Update GPD to latest version with changelog display
context_mode: global
allowed-tools:
  - shell
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Check for GPD updates, install if available, and display what changed.

Routes to the update workflow which handles:

- Version detection (local vs global installation)
- Package version checking
- Changelog fetching and display
- User confirmation with clean install warning
- Update execution and cache clearing
- Restart reminder
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/update.md
</execution_context>

<process>
**Follow the update workflow** from `@{GPD_INSTALL_DIR}/workflows/update.md`.

The workflow handles all logic including:

1. Installed version detection (local/global)
2. Latest version checking via package registry
3. Version comparison
4. Changelog fetching and extraction
5. Clean install warning display
6. User confirmation
7. Update execution
8. Cache clearing
   </process>

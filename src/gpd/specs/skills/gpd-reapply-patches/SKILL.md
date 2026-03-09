---
name: gpd-reapply-patches
description: Reapply local modifications after a GPD update
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
  - glob
  - grep
  - ask_user
---

<!-- Platform: Claude Code. Tool names and @ includes are platform-specific. -->
<!-- allowed-tools listed are Claude Code tool names. Other platforms use different tool interfaces. -->

<objective>
After a GPD update wipes and reinstalls files, this command merges user's previously saved local modifications back into the new version. Uses intelligent comparison to handle cases where the upstream file also changed.

In the physics research context, "patches" include corrections to calculation templates, custom notation conventions, modified validation checks, and personalized workflow adjustments.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/reapply-patches.md
</execution_context>

<process>
Follow the reapply-patches workflow: @{GPD_INSTALL_DIR}/workflows/reapply-patches.md
</process>

<success_criteria>

- [ ] All backed-up patches processed
- [ ] User modifications merged into new version
- [ ] Physics-specific content (conventions, signs, units) preserved correctly
- [ ] Conflicts resolved with user input
- [ ] Status reported for each file
</success_criteria>

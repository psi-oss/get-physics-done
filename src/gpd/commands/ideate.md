---
name: gpd:ideate
description: Launch a structured ideation session through interactive intake and launch approval
argument-hint: "[topic, question, or domain] [--preset fast|balanced|deep]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
  - ask_user
---


<objective>
Launch an ideation session cleanly: gather the scientific problem or open discussion space, clarify the desired outcome, capture the constraints and anchors that must stay visible, and show an editable launch summary before any ideation begins.

Phase 1 of `gpd:ideate` is launch-surface only. It does **not** run the multi-agent ideation loop yet, does **not** write durable artifacts, and does **not** auto-ingest project state unless the user explicitly asks for specific context.
</objective>

<context>
Ideation seed: $ARGUMENTS

Interpretation:

- If `$ARGUMENTS` contains a topic, question, or domain, treat it as the initial ideation seed.
- If `$ARGUMENTS` includes `--preset fast|balanced|deep`, use that as the initial execution preference unless the user changes it.
- If `$ARGUMENTS` is empty, start with a blank intake and ask what scientific problem, domain, or open-ended discussion space the user wants to explore.
- Existing `GPD/` project files are optional supporting context only. Do not read them unless the user explicitly asks for specific files or artifacts to be included.
</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/ideate.md
</execution_context>

<process>
Execute the ideate workflow from @{GPD_INSTALL_DIR}/workflows/ideate.md end-to-end.

Keep the wrapper thin. Preserve the workflow-owned gates:

- plain-English launch orientation
- one dense intake prompt
- adaptive clarification only where needed
- editable launch/config summary
- explicit `Start ideation / Adjust launch / Review raw context / Stop here` approval loop

Phase 1 stops after the launch summary is approved or the user stops. Do not invent the later multi-agent round engine, do not claim that a durable ideation session was created, and do not write files unless a later workflow phase explicitly adds that behavior.
</process>

<success_criteria>

- [ ] `gpd:ideate` starts projectlessly from any folder
- [ ] The workflow owns the interactive intake and launch-summary loop
- [ ] Existing project context remains opt-in rather than auto-loaded
- [ ] The user can approve, adjust, review raw context, or stop cleanly
- [ ] No durable artifacts are created in this phase

</success_criteria>

---
name: gpd:ideate
description: Run projectless multi-agent ideation through interactive intake, bounded rounds, and user review
argument-hint: "[topic, question, or domain] [--preset fast|balanced|deep]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
  - ask_user
  - task
---


<objective>
Run an ideation session cleanly: gather the scientific problem or open discussion space, clarify the desired outcome, capture the constraints and anchors that must stay visible, show an editable launch summary, and then guide bounded multi-agent ideation rounds with explicit user review gates.

Keep `gpd:ideate` projectless and lightweight. It should not auto-ingest project state unless the user explicitly asks for specific context, and it should not claim durable session storage, resumable ideation state, or other later-phase persistence features. Keep orchestration in memory for this phase and do not promise durable ideation storage.
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

Keep the wrapper thin. The execution context owns round orchestration, worker fan-out, synthesis, and user gating. Preserve the workflow-owned gates:

- plain-English launch orientation
- one dense intake prompt
- adaptive clarification only where needed
- editable launch/config summary
- explicit `Start ideation / Adjust launch / Review raw context / Stop here` approval loop
- bounded ideation rounds across configurable agents
- per-round synthesis and user review before continuing
- explicit round-boundary options such as `Continue`, `Add my thoughts`, `Adjust configuration`, `Review raw round`, and `Pause or stop`

Do not claim durable ideation session storage, resumable ideation state, tagging, imported-document handling, or other later-phase persistence systems unless a later workflow phase explicitly adds them. The phase-2 contract is an in-memory session, not a durable ideation artifact system.
</process>

<success_criteria>

- [ ] `gpd:ideate` starts projectlessly from any folder
- [ ] The workflow owns the interactive intake, launch summary, round execution, and round-review loop
- [ ] Bounded multi-agent rounds happen behind explicit user checkpoints
- [ ] Existing project context remains opt-in rather than auto-loaded
- [ ] The user can continue, add thoughts, adjust configuration, review the raw round, or stop cleanly
- [ ] No durable ideation session files, resumable state, or later-phase persistence systems are required in this phase

</success_criteria>

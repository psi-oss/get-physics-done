---
name: gpd:ideate
description: Run projectless multi-agent ideation through interactive intake, bounded rounds, temporary subgroups, and user review
argument-hint: "[topic, question, or domain] [--preset fast|balanced|deep]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
  - ask_user
  - task
---


<objective>
Run an ideation session cleanly: gather the scientific problem or open discussion space, clarify the desired outcome, capture the constraints and anchors that must stay visible, show an editable launch summary, and then guide bounded multi-agent ideation rounds with explicit user review gates and optional temporary subgroup loops.

Keep `gpd:ideate` projectless and lightweight. It should not auto-ingest project state unless the user explicitly asks for specific context, and it should not claim durable session storage, resumable ideation state, or other later-phase persistence features. Keep orchestration in memory for this phase and do not promise durable ideation storage, subgroup transcripts, subgroup session promotion, or a separate subgroup launch surface.
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
- structured end-of-session summary with an explicit what-next prompt
- explicit round-boundary options such as `Continue`, `Add my thoughts`, `Adjust configuration`, `Review raw round`, and `Pause or stop`
- any temporary bounded subgrouping offered only as an `Adjust configuration` choice at that existing round gate, with parent-owned, bounded, fileless, summary-only rejoin behavior
- subgroup rejoin routed back through that existing round-boundary control surface rather than transcript replay or a promoted subgroup session

Do not claim durable ideation session storage, resumable ideation state, subgroup transcripts, subgroup promotion, tagging, imported-document handling, or other later-phase persistence systems unless a later workflow phase explicitly adds them. Do not promise durable subgroup transcripts, promotion, spawn contracts, resumable subgroup persistence, or dedicated ideation state. The contract here is an in-memory session routed through the existing round-boundary controls, not a durable ideation artifact system.
</process>

<success_criteria>

- [ ] `gpd:ideate` starts projectlessly from any folder
- [ ] The workflow owns the interactive intake, launch summary, round execution, and round-review loop
- [ ] Bounded multi-agent rounds happen behind explicit user checkpoints
- [ ] Existing project context remains opt-in rather than auto-loaded
- [ ] The user can continue, add thoughts, adjust configuration, review the raw round, or stop cleanly
- [ ] The user can launch a temporary bounded subgroup from the round boundary and rejoin through a subgroup summary
- [ ] Stopping the session produces a structured summary and an explicit what-next prompt with relevant follow-up suggestions
- [ ] No durable ideation session files, resumable state, or later-phase persistence systems are required in this phase

</success_criteria>

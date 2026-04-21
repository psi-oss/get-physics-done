---
name: gpd:ideate
description: Run a projectless conversational multi-agent research session to explore, pressure-test, and refine a direction before durable project work
argument-hint: "[topic, question, or domain] [--preset fast|balanced|deep]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
  - ask_user
  - task
---


<objective>
Run `gpd:ideate` as a projectless conversational multi-agent research session for exploring, pressure-testing, and refining a research direction before deciding whether it should become durable project work.

Keep the contract lightweight and non-durable. Existing project files, notes, and artifacts are opt-in context only and must not be auto-ingested unless the user explicitly asks for specific context. Do not claim or imply `RESEARCH.md`, `GPD/ideation/`, durable ideation artifacts, resumable session state, transcript storage or replay, session ids, subgroup promotion into durable sessions, `resume-work`, staged init, artifact freshness gating, or other persistence-heavy `research-phase` semantics. Phase 0 locks that product boundary only; it does not redesign the current workflow-owned round structure.
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
- structured end-of-session summary with an explicit what-next prompt, relevant suggested GPD actions, and allowance for non-GPD next steps
- explicit round-boundary options such as `Continue`, `Add my thoughts`, `Adjust configuration`, `Review raw round`, and `Pause or stop`
- any temporary bounded subgrouping offered only as an `Adjust configuration` choice at that existing round gate, with parent-owned, bounded, fileless, summary-only rejoin behavior
- subgroup rejoin routed back through that existing round-boundary control surface rather than transcript replay or a promoted subgroup session

Do not claim durable ideation session storage, resumable ideation state, subgroup transcripts, subgroup promotion, tagging, imported-document handling, or other later-phase persistence systems unless a later workflow phase explicitly adds them. Do not promise durable subgroup transcripts, promotion, spawn contracts, resumable subgroup persistence, or dedicated ideation state. The contract here is an in-memory session routed through the existing round-boundary controls, not a durable ideation artifact system.
</process>

<success_criteria>

- [ ] `gpd:ideate` is defined as a projectless conversational multi-agent research session rather than a persistence-backed ideation surface
- [ ] The command can start from any folder without requiring project initialization or durable session setup
- [ ] Existing project files and prior GPD state remain opt-in context instead of auto-loaded session state
- [ ] The session stays non-durable: no `RESEARCH.md`, no `GPD/ideation/`, no durable ideation artifact directory, no resumable ideation state, and no transcript storage or replay are required
- [ ] The command does not import `research-phase` semantics such as staged init, artifact gating, or `resume-work`
- [ ] Multi-agent contributions help the user explore, pressure-test, and refine a direction before they choose whether to move into a durable GPD workflow
- [ ] Phase 0 preserves the existing workflow-owned round mechanics instead of redesigning them here

</success_criteria>

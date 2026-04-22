---
name: gpd:agentic-discussion
description: Run a projectless transcript-first multi-agent research discussion to explore, pressure-test, and refine a direction before durable project work
argument-hint: "[topic, question, or domain] [--preset fast|balanced|deep]"
context_mode: projectless
allowed-tools:
  - file_read
  - shell
  - ask_user
  - task
---


<objective>
Run `gpd:agentic-discussion` as a projectless conversational multi-agent research session for exploring, pressure-testing, and refining a research direction before deciding whether it should become durable project work.

Keep the visible experience transcript-first: show agent contributions directly, keep clean turns open by default with a short natural handoff, and treat synthesis or recap as secondary unless the user asks for it or a blocker or routing decision makes it necessary.

Keep the contract lightweight and non-durable. Existing project files, notes, and artifacts are opt-in context only and must not be auto-ingested unless the user explicitly asks for specific context. Do not claim or imply `RESEARCH.md`, `GPD/ideation/`, durable ideation artifacts, resumable session state, transcript storage or replay, session ids, promotion of temporary internal branches into durable sessions, `resume-work`, staged init, artifact freshness gating, or other persistence-heavy workflow semantics.
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

Keep the wrapper thin and public-facing. The execution context owns orchestration details, worker fan-out, synthesis, and any internal control flow. Describe the command as a live conversational session that helps the user explore a topic with multiple research perspectives, surfaces the discussion as agent-first transcript turns, continues naturally after clean turns, and wraps up with takeaways or next moves only when useful.

Do not center or enumerate internal approval loops, bounded rounds, review gates, branch-specific coordination, moderator-style menu handoffs, or other workflow-specific control surfaces in the public command contract. Do not claim durable ideation session storage, resumable ideation state, transient branch transcripts, promotion of temporary internal branches, tagging, imported-document handling, or other persistence systems unless a later workflow explicitly adds them. The contract here is an in-memory conversational research session, not a durable ideation artifact system.
</process>

<success_criteria>

- [ ] `gpd:agentic-discussion` is defined as a projectless conversational multi-agent research session rather than a persistence-backed ideation surface
- [ ] The command can start from any folder without requiring project initialization or durable session setup
- [ ] Existing project files and prior GPD state remain opt-in context instead of auto-loaded session state
- [ ] The session stays non-durable: no `RESEARCH.md`, no `GPD/ideation/`, no durable ideation artifact directory, no resumable ideation state, and no transcript storage or replay are required
- [ ] The command does not import staged setup, artifact gating, `resume-work`, or similar persistence-heavy workflow semantics
- [ ] Multi-agent contributions help the user explore, pressure-test, and refine a direction before they choose whether to move into a durable GPD workflow
- [ ] Clean turns read like an agent-first discussion transcript rather than a visible moderator/menu loop
- [ ] Clean turns continue by default with a short natural handoff, while synthesis or recap stays request-driven or exception-driven
- [ ] The public wrapper does not foreground internal approval loops, bounded rounds, review gates, temporary branch coordination, or other workflow-specific control surfaces

</success_criteria>

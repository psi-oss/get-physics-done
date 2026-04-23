---
name: gpd:route
description: Decide whether a scope change is a new phase, a revision, a new milestone, or a milestone completion
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - ask_user
---


<objective>
Answer the implicit question "should this be a new phase, a new milestone, a revision of the existing one, or complete + new?" — a recurring product decision point the user has to make whenever scope changes.

Rather than guessing, ask three focused questions:

1. Is the ranking / prior conclusion frozen?
2. Are you extending the scope or revising the same result?
3. Are you adding a new deliverable layer or changing prior conclusions?

Then print exactly one recommended next command (`gpd:add-phase`, `gpd:revise-phase`, `gpd:new-milestone`, or `gpd:complete-milestone` followed by `gpd:new-milestone`).

This is the single-purpose sibling of `gpd:suggest-next`. `suggest-next` infers the best next command from current project state; `route` infers it from the user's intent when that intent is about scope.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/route.md
</execution_context>

<context>
@GPD/STATE.md
@GPD/ROADMAP.md
</context>

<process>
Follow `{GPD_INSTALL_DIR}/workflows/route.md`. It:

1. Reads the current milestone + active phase from state.
2. Asks three `ask_user` questions (or accepts pre-provided answers via `--frozen=yes|no`, `--change=extend|revise`, `--layer=new|change`).
3. Maps the three answers to one recommendation.
4. Emits a `## > Next Up` block with the recommended command and a one-line rationale.
</process>

<success_criteria>

- [ ] Current milestone + phase surfaced from state
- [ ] Three routing questions asked (or pre-provided)
- [ ] Exactly one recommended command returned
- [ ] Rationale mentions which answers drove the decision
  </success_criteria>

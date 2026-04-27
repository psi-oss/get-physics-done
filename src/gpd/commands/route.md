---
name: gpd:route
description: Decide whether a scope change is a new phase, a revision, a new milestone, or a milestone completion
argument-hint: "[--frozen=yes|no] [--change=extend|revise] [--layer=new|change]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - ask_user
---


<objective>
Answer the implicit question "should this be a new phase, a new milestone, a revision of the existing one, or complete + new?" — a recurring research-workflow decision point the user has to make whenever scope changes.

Rather than guessing, ask three focused questions:

1. Is the ranking / prior conclusion frozen?
2. Are you extending the scope or revising the same result?
3. Are you adding a new deliverable layer or changing prior conclusions?

Then return one recommended next action. Most recommendations are a single command (`gpd:add-phase`, `gpd:revise-phase`, or `gpd:new-milestone`); the frozen-scope-expansion path is intentionally a compound action: `gpd:complete-milestone` first, then `gpd:new-milestone` after the archive is confirmed.

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
Follow `@{GPD_INSTALL_DIR}/workflows/route.md`. It:

1. Reads the current milestone + active phase from state.
2. Asks three `ask_user` questions (or accepts pre-provided answers via `--frozen=yes|no`, `--change=extend|revise`, `--layer=new|change`).
3. Maps the three answers to one recommendation.
4. Emits a `## > Next Up` block with one recommendation, rendering compound recommendations as ordered commands.
</process>

<success_criteria>

- [ ] Current milestone + phase surfaced from state
- [ ] Three routing questions asked (or pre-provided)
- [ ] One recommendation returned; compound recommendations list the required commands in order
- [ ] Rationale mentions which answers drove the decision
</success_criteria>

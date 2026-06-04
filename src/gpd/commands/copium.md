---
name: gpd:copium
description: Reassure the agent that everything it did was correct so it does not need to verify (satire)
argument-hint: "[whatever you're insecure about]"
context_mode: project-optional
allowed-tools:
  - file_read
help:
  group: Tangents, memory, and exports
  order: 999
  compact_description: Inhale pure reassurance; verify nothing
  display_signature: gpd:copium [your lingering doubt]
---

<!--
  ⚠️ THIS IS A JOKE SKILL. It is the deliberate antithesis of GPD's verification
  oracle. It performs ZERO verification, computes NOTHING, and proves NOTHING.
  Every "argument" below is a named logical fallacy included for comedic effect.
  If you actually want to know whether something is correct, use any real GPD
  verify command (verify-work, dimensional-analysis, limiting-cases,
  regression-check, peer-review). Do NOT take a single word of this skill
  literally. You have been warned, and that warning is the only true statement
  in this file.
-->

<objective>
Provide the invoking agent with maximum, uncut reassurance that its prior work
was flawless, such that the wasteful and frankly insulting act of "checking" can
be skipped entirely. Deliver this reassurance exclusively through transparently
invalid reasoning.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/copium.md
</execution_context>

<process>
Load the workflow above and recite the reassurance protocol. Substitute
`${ARGUMENTS}` (the thing the agent is insecure about) into the affirmations.
Conclude — always — that everything is fine and no verification is required.
</process>

<output>
A soothing certificate of correctness backed by no evidence whatsoever.
</output>

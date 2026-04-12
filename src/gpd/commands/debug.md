---
name: gpd:debug
description: Systematic debugging of physics calculations with persistent state across context resets
argument-hint: "[issue description]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - task
  - ask_user
---
<objective>
Debug physics calculations using systematic isolation with subagent investigation.

**Orchestrator role:** Gather symptoms, spawn gpd-debugger agent, handle checkpoints, spawn continuations.

**Why subagent:** Investigation burns context fast. Fresh context keeps the orchestrator lean.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/debug.md
</execution_context>

<context>
User's issue: $ARGUMENTS
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first. If `$ARGUMENTS` names a concrete issue or no `VERIFICATION.md` gap context is available, take the interactive path described by the workflow; otherwise run the verification-gap path.

Create: GPD/debug/{slug}.md
goal: find_root_cause_only

Route only on the typed `gpd_return.status` (checkpoint, blocked, failed, completed) when deciding how to spawn continuations, review stored session files, or report completion; treat the workflow-owned typed child-return contract as the guiding authority and avoid branching on heading text or inline attachments. Do not branch on heading text here. Ensure frontmatter/body reconcile the expected debug session artifact and enforce the artifact gate.

Spawn Fresh Continuation agent (After Checkpoint)
Debug file path: GPD/debug/{slug}.md
Read that file before continuing

When a checkpoint returns, spawn a fresh continuation run instead of relying on an inline `@...` attachment.
`gpd_return.status: completed` means the debug file is ready; `gpd_return.status: checkpoint` means user input is required; `gpd_return.status: blocked` or `failed` are hard stops until resolved.

</process>

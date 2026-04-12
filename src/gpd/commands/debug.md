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
Read the workflow file defined above with `file_read` first.

If `$ARGUMENTS` names a concrete issue or no `VERIFICATION.md` gap context is available, run the interactive path:

1. Check active sessions with `ls GPD/debug/*.md 2>/dev/null | grep -v resolved | head -5`.
2. If sessions exist and no issue was supplied, ask whether to resume one or start a new issue.
3. For a new issue, ask only for missing essentials: expected result, actual result, discrepancy type, regime, and checks already tried.
4. Spawn one fresh `gpd-debugger` subagent with the issue summary, evidence, attempted checks, and goal `find_root_cause_or_fix`.
5. Route only on the typed `gpd_return` envelope: present checkpoints to the user, report blocked/failed runs, or read the returned session file for completed diagnoses.
6. Ask whether to apply the fix, continue debugging, or pause with the session file.

Otherwise follow the workflow end-to-end for verification-gap debugging.


```text
task(
  subagent_type="gpd-debugger",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.\n\nCreate: GPD/debug/{slug}.md\nRead that file before continuing",
  description="Debug {slug}"
)

task(
  subagent_type="gpd-debugger",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.\n\nDebug file path: GPD/debug/{slug}.md\nRead that file before continuing",
  description="Continue debug {slug}"
)
```

gpd_return.status: checkpoint
Spawn Fresh Continuation agent (After Checkpoint)
gpd_return.status: blocked` or `failed
frontmatter/body reconcile the expected debug session artifact
goal: find_root_cause_only
Do not branch on heading text here.
instead of relying on an inline `@...` attachment.
workflow-owned typed child-return contract
spawn a fresh continuation run
gpd_return.status: completed
Debug spawn contract: read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions; Create: GPD/debug/{slug}.md
Read that file before continuing; Debug file path: GPD/debug/{slug}.md
Read that file before continuing; verify the expected debug session artifact gate.

</process>

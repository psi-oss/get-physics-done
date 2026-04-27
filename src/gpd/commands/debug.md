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
Route a physics debugging request into the workflow-owned debugging orchestrator.

This wrapper owns the public command surface and request text. The workflow owns workspace bootstrap, active-session handling, symptom gathering, `gpd-debugger` delegation, typed child-return routing, checkpoint continuation, and next-step presentation.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/debug.md
</execution_context>

<context>
User's issue: $ARGUMENTS

Debug session artifact: `GPD/debug/{slug}.md`

</context>

<process>
Follow @{GPD_INSTALL_DIR}/workflows/debug.md end-to-end.

Keep these command-surface invariants visible while delegating mechanics to the workflow:

- The workflow resolves `DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger)` and spawns `subagent_type="gpd-debugger"`.
- Debugger prompts start by asking the child to read `{GPD_AGENTS_DIR}/gpd-debugger.md` for its role and instructions.
- New and continued runs are diagnosis-first with `goal: find_root_cause_only`.
- Continuations are file-backed: the child reads `GPD/debug/{slug}.md` before continuing instead of relying on an inline `@...` attachment.
- The workflow routes only on the typed `gpd_return.status` envelope and verifies the debug session artifact before treating a root cause as confirmed.

</process>

<success_criteria>

- [ ] Debug workflow executed as the authority for mechanics
- [ ] `gpd-debugger` delegation remains diagnosis-first and file-backed
- [ ] Typed child-return status, checkpoint continuation, and artifact verification follow the workflow contract
      </success_criteria>

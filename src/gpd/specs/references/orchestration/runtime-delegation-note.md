# Runtime Delegation Note

Use `@{GPD_INSTALL_DIR}/references/orchestration/agent-delegation.md` as the authoritative delegation contract.

For any runtime handoff, preserve these canonical rules:

- Spawn a fresh subagent for the task below.
- This is a one-shot handoff: `status: checkpoint` stops for the user. Do not make the child wait in place.
- fresh-continuation ownership stays with the main orchestrator after a child checkpoint.
- If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model.
- This is the empty-model omission rule.
- artifact gate: If the task produces files, verify the expected artifacts on disk before marking the handoff complete.
- Always pass `readonly=false` for file-producing agents.

If native subagent spawning is unavailable, execute sequentially in the main context with the same gates.

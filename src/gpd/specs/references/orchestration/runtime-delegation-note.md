# Runtime Delegation Note

Use the canonical delegation contract in `references/orchestration/agent-delegation.md`: spawn a fresh one-shot handoff subagent, omit empty `model` values, set `readonly=false` for file-producing handoffs, require checkpoint returns instead of in-run waiting, and verify expected artifacts on disk before accepting success.


Spawn a fresh subagent for the task below. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents.

This is a one-shot handoff:

Do not make the child wait in place.

If the task produces files, verify the expected artifacts on disk before marking the handoff complete.

Return `status: checkpoint` for handoffs that require user input.

The orchestrator owns any fresh continuation handoff.

# Runtime Delegation Note

Use the canonical delegation contract in `references/orchestration/agent-delegation.md`: spawn a fresh one-shot subagent, omit empty `model` values, set `readonly=false` for file-producing handoffs, require checkpoint returns instead of in-run waiting, and verify expected artifacts on disk before accepting success.

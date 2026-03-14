# Agent Delegation Reference

This document defines the standardized pattern for spawning GPD agents across runtimes.

## task() Delegation Block

Every agent spawn in a workflow uses this pattern:

```
# Resolve model for this agent role
AGENT_MODEL=$(gpd resolve-model gpd-{agent})

# Spawn agent
task(
  subagent_type="gpd-{agent}",
  model="{AGENT_MODEL}",    # Omit if AGENT_MODEL is empty
  prompt="First, read {GPD_AGENTS_DIR}/gpd-{agent}.md for your role and instructions.\n\n{task_prompt}",
  description="{short description}"
)
```

## Runtime Alternatives

| Method | Agent Spawn Method |
|--------|-------------------|
| **Subagent spawning** | `task(subagent_type="gpd-{agent}", model="{model}", prompt="...")` or equivalent; omit `model` when it resolves empty |
| **Skill invocation** | Invoke `/gpd:{agent}` — the installer adapts the command surface for your runtime |
| **Tool discovery** | Agents are registered as callable tools via SKILL.md discovery |
| **Fallback** | Execute the agent's SKILL.md instructions sequentially in the main context |

> The installer translates agent references to the correct format for your runtime. Source files use the generic `task()` pattern.

## Rules

1. **Always resolve model first:** `gpd resolve-model gpd-{agent}`
2. **If model is null or empty:** Omit the `model` parameter from task(). The runtime will use its default model.
3. **Agent instructions path:** `{GPD_AGENTS_DIR}/gpd-{agent}.md` (resolved by installer per runtime)
4. **gpd path:** `bin/gpd CLI` (relative to project root, runtime-agnostic)
5. **Never hardcode runtime-specific paths** — use `{GPD_INSTALL_DIR}` for specs assets and `{GPD_AGENTS_DIR}` for agent prompts.
6. **Fresh context:** task() spawns agents in a fresh context window. The agent cannot see the orchestrator's conversation. All context must be passed via the prompt.
7. **Do not use `@...` references inside task() prompt strings.** They do not load files for subagents. Pass explicit `<files_to_read>` instructions or inline the content.
8. **Assign an explicit write scope for every subagent.** Parallel agents must not share writable files. Prefer `file_edit` for targeted changes, and re-read the file immediately before writing.

## Delegation Contract

Every runtime-specific delegation surface must preserve these workflow semantics, even when the spawn mechanism differs:

1. **Fresh context:** The subagent starts without hidden access to the orchestrator's conversation.
2. **Model semantics:** The `model` parameter is omitted when `gpd resolve-model` returns empty.
3. **Write-scope isolation:** Parallel subagents get disjoint writable targets.
4. **Blocking completion semantics:** The orchestrator treats the handoff as incomplete until artifacts or structured return data are present.
5. **Return-envelope parity:** The subagent must return the same machine-readable outcome shape the shared workflows expect.

If a runtime cannot satisfy these invariants with native subagents, fall back to a sequential main-context execution that still preserves the same write scope, artifact checks, and return-envelope discipline.

## Prompt Contract Addendum

For file-producing or state-sensitive tasks, include an explicit handoff contract inside the spawned prompt:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write | direct
  allowed_paths:
    - relative/path/owned/by/this/agent
expected_artifacts:
  - relative/path/the/orchestrator/must_verify
shared_state_policy: return_only | direct
</spawn_contract>
```

Use the fields this way:

- `write_scope.mode`: `scoped_write` for normal subagents with isolated artifact ownership. Use `direct` only when the subagent is explicitly allowed to mutate canonical shared state.
- `write_scope.allowed_paths`: concrete writable targets for this handoff. Parallel agents must not overlap here.
- `expected_artifacts`: contract-native deliverables, comparison ledgers, or other concrete artifacts the orchestrator must verify before trusting the handoff.
- `shared_state_policy`: `return_only` when shared project state must be returned in the structured envelope and applied by the orchestrator. Use `direct` only when the workflow explicitly delegates shared-state ownership.

If the task does not produce files, still state the `shared_state_policy` and the required structured return envelope.

## Platform Note Template

Add this before any task() call in a workflow:

```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. If subagent spawning is unavailable, execute these steps sequentially in the main context.
```

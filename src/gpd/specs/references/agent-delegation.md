# Agent Delegation Reference

This document defines the standardized pattern for spawning GPD agents across runtimes.

## Task() Delegation Block

Every agent spawn in a workflow uses this pattern:

```
# Resolve model for this agent role
AGENT_MODEL=$(gpd resolve-model gpd-{agent} --raw)

# Spawn agent
Task(
  subagent_type="gpd-{agent}",
  model="{AGENT_MODEL}",    # Omit if resolved to null
  prompt="First, read {GPD_AGENTS_DIR}/gpd-{agent}.md for your role and instructions.\n\n{task_prompt}",
  description="{short description}"
)
```

## Runtime Alternatives

| Method | Agent Spawn Method |
|--------|-------------------|
| **Subagent spawning** | `Task(subagent_type="gpd-{agent}", model="{model}", prompt="...")` or equivalent |
| **Skill invocation** | Invoke `$gpd-{agent}` skill — the agent's SKILL.md is auto-discovered |
| **Tool discovery** | Agents are registered as callable tools via SKILL.md discovery |
| **Fallback** | Execute the agent's SKILL.md instructions sequentially in the main context |

> The installer translates agent references to the correct format for your runtime. Source files use the generic `Task()` pattern.

## Rules

1. **Always resolve model first:** `gpd resolve-model gpd-{agent} --raw`
2. **If model is null or empty:** Omit the `model` parameter from Task(). The runtime will use its default model.
3. **Agent instructions path:** `{GPD_AGENTS_DIR}/gpd-{agent}.md` (resolved by installer per runtime)
4. **gpd path:** `bin/gpd CLI` (relative to project root, runtime-agnostic)
5. **Never hardcode runtime-specific paths** — use `{GPD_INSTALL_DIR}` for specs assets and `{GPD_AGENTS_DIR}` for agent prompts.
6. **Fresh context:** Task() spawns agents in a fresh context window. The agent cannot see the orchestrator's conversation. All context must be passed via the prompt.

## Platform Note Template

Add this before any Task() call in a workflow:

```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `Task()` call to your runtime's agent spawning mechanism. If `model` resolved to `null`, omit it. If subagent spawning is unavailable, execute these steps sequentially in the main context.
```

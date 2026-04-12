# Agent Delegation Reference

canonical delegation contract for spawned GPD agents. Workflows should reference this file instead of restating the rules.

## Delegation Invariants

Delegation Contract

1. **One-shot handoff:** A spawned subagent runs once. If it needs human input, it returns `status: checkpoint` and stops.
2. **Artifact gate:** Reported success is provisional until every `expected_artifacts` entry is verified on disk.
3. **Fresh continuation ownership:** The orchestrator presents the checkpoint, must not wait for the user inside the same handoff, and must spawn a fresh continuation handoff when needed.

## task() Delegation Block

Every agent spawn in a workflow uses this pattern:

```
# Resolve model for this agent role
AGENT_MODEL=$(gpd resolve-model gpd-{agent})

# Spawn agent — readonly=false is REQUIRED for file-producing agents
task(
  subagent_type="gpd-{agent}",
  model="{AGENT_MODEL}",    # Omit if AGENT_MODEL is empty
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-{agent}.md for your role and instructions.\n\n{task_prompt}",
  description="{short description}"
)
```

## Runtime Alternatives

| Method | Agent Spawn Method |
|--------|-------------------|
| **Subagent spawning** | `task(subagent_type="gpd-{agent}", model="{model}", readonly=false, prompt="...")` or equivalent; omit `model` when it resolves empty |
| **Projected command surface** | Invoke the runtime's installed GPD command or agent action surface. For example, some runtimes expose `gpd:{agent}` slash commands. |
| **Tool discovery** | Agents may appear on the runtime's discoverable action/tool surface after installation |
| **Fallback** | Execute the installed agent prompt instructions sequentially in the main context |

> The installer projects agent references onto the correct runtime-specific command/tool surface. Source files use the generic `task()` pattern.

## Authoring Rules

1. **Return-envelope parity:** Preserve the shared return envelope across native and fallback runtimes.
2. **Success-path artifact gate:** Verify expected artifacts before accepting success.
3. **Blocking completion semantics:** Treat checkpoints and missing artifacts as blocking until resolved.
4. **Write-scope isolation:** Assign disjoint write scopes to parallel agents.
5. **Write access:** Always pass `readonly=false` for file-producing agents.
   Always set `readonly=false` for file-producing agents.
6. **Model semantics:** If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model.
7. **Agent instructions path:** `{GPD_AGENTS_DIR}/gpd-{agent}.md` (resolved by installer per runtime)
8. **gpd CLI surface:** author plain `gpd ...` in source prompts. The installer rewrites shell calls to the runtime-managed GPD CLI bridge during install; source prompts must stay runtime-agnostic.
9. **Never hardcode runtime-specific paths** — use `{GPD_INSTALL_DIR}` for specs assets and `{GPD_AGENTS_DIR}` for agent prompts, and let the installer project shell `gpd` calls onto the correct runtime bridge.
10. **Fresh context:** task() spawns agents in a fresh context window. The agent cannot see the orchestrator's conversation. All context must be passed via the prompt.
11. **Do not use `@...` references inside task() prompt strings.** They do not load files for subagents. Pass explicit `<files_to_read>` instructions or inline the content.
12. **Assign an explicit write scope for every subagent.** Parallel agents must not share writable files. Prefer `file_edit` for targeted changes, and re-read the file immediately before writing.

If a runtime cannot satisfy these invariants with native subagents, fall back to a sequential main-context execution that still preserves the same write scope, artifact checks, and return-envelope discipline.

For GPD-owned runtime surfaces, use the effective installed runtime rather than a merely active but uninstalled higher-priority runtime. This applies to `gpd resolve-model`, runtime-native command rendering, and other installer-backed workflow surfaces.

## Artifact Recovery Protocol

Subagent file writes can silently fail on any runtime. Treat this as a normal operating condition, not an edge case.

**After every file-producing subagent completes, the orchestrator MUST:**

1. **Verify expected artifacts exist on disk** using `file_read` or `ls`. Do not trust the subagent's claim that it wrote them.
2. **If artifacts are missing but the subagent returned content:**
   - Extract the file content from the subagent's response text (structured return envelope, inline content, or quoted output).
   - Write the files directly in the main orchestrator context using the main context's Write/Edit tools.
   - This is the primary recovery path and should succeed because the main context's file tools are not affected by the subagent persistence bug.
3. **If artifacts are missing and the subagent returned no usable content:**
   - Re-execute the subagent's task in the main orchestrator context (not via task tool) following the same prompt and write scope.
   - This is the fallback described in the Platform Note Template.
4. **Never silently proceed** with missing artifacts. Every `expected_artifacts` entry must exist on disk before the orchestrator marks the handoff as complete.

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

Add this concise note before any task() call in a workflow:

```
> **Runtime delegation:** Follow `references/orchestration/agent-delegation.md`; use the fresh one-shot handoff pattern, omit empty `model`, set `readonly=false` for file-producing agents, and verify expected artifacts before accepting success.
```

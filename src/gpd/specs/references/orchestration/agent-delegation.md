# Agent Delegation Reference

canonical delegation contract for spawned GPD agents. Workflows should reference this file instead of restating the rules.

## Delegation Invariants

Delegation Contract

1. **One-shot handoff:** A spawned subagent runs once. If it needs human input, it returns `status: checkpoint` and stops.
2. **Artifact gate:** Reported success is provisional until every `expected_artifacts` entry is verified on disk.
3. **Fresh continuation ownership:** The orchestrator presents the checkpoint, must not wait for the user inside the same handoff, and must spawn a fresh continuation handoff when needed.

## task() Delegation Block

Every agent spawn in a workflow uses this pattern:

Do not use `@...` references inside task() prompt strings.
Always set `readonly=false` for file-producing agents.
Always pass `readonly=false` for file-producing agents.
Assign an explicit write scope for every subagent.
Fresh context:
Model semantics:
Write access:
Write-scope isolation:
Blocking completion semantics:
Success-path artifact gate:
Return-envelope parity:
write_scope:

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
Do not use `@...` references inside task() prompt strings.
Always set `readonly=false` for file-producing agents.
Always pass `readonly=false` for file-producing agents.
Assign an explicit write scope for every subagent.
Fresh context:
Model semantics:
Write access:
Write-scope isolation:
Blocking completion semantics:
Success-path artifact gate:
Return-envelope parity:
write_scope:

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

1. **Return-envelope parity:** Preserve the structured return envelope across native and fallback runtimes so orchestrators see the same fields.
2. **Artifact verification:** Treat every `expected_artifacts` entry as provisional until its file is verified; missing artifacts block success.
3. **Fallback recovery:** If verification fails, extract the content from the subagent response or rerun the handoff in the main context before marking the artifact as complete.
4. **Write-scope isolation:** Assign disjoint `write_scope.allowed_paths` in `task()` so parallel agents never overlap writable files.
5. **File-producing access:** Always pass `readonly=false` for file-producing agents and omit `model` when it resolves to `null`/empty so runtimes choose their default.
6. **Runtime-agnostic prompts:** Point subagents to `{GPD_AGENTS_DIR}/gpd-{agent}.md` and author plain `gpd ...` calls; let installers rebind them to runtime bridges without hardcoding runtime-specific paths.
7. **Fresh contexts:** Each `task()` runs in a fresh context with no view of the orchestrator’s conversation; pass every needed anchor explicitly.
8. **No `@` references:** Do not embed `@...` references inside `task()` prompts — pass explicit `<files_to_read>` hints or inline the required content instead.

If a runtime cannot satisfy these invariants with native subagents, fall back to a sequential main-context execution that preserves the same write scope, artifact checks, and return-envelope discipline.

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
  mode: scoped_write | direct
  allowed_paths:
    - relative/path/owned/by/this/agent
expected_artifacts:
  - relative/path/the/orchestrator/must_verify
shared_state_policy: return_only | direct
</spawn_contract>
Do not use `@...` references inside task() prompt strings.
Always set `readonly=false` for file-producing agents.
Always pass `readonly=false` for file-producing agents.
Assign an explicit write scope for every subagent.
Fresh context:
Model semantics:
Write access:
Write-scope isolation:
Blocking completion semantics:
Success-path artifact gate:
Return-envelope parity:
write_scope:

```

Use the fields this way:

- `write_scope.mode`: `scoped_write` for normal subagents with isolated artifact ownership. Use `direct` only when the subagent is explicitly allowed to mutate canonical shared state.
- `write_scope.allowed_paths`: concrete writable targets for this handoff. Parallel agents must not overlap here.
- `expected_artifacts`: contract-native deliverables, comparison ledgers, or other concrete artifacts the orchestrator must verify before trusting the handoff.
- `shared_state_policy`: `return_only` when shared project state must be returned in the structured envelope and applied by the orchestrator. Use `direct` only when the workflow explicitly delegates shared-state ownership.

If the task does not produce files, still state the `shared_state_policy` and the required structured return envelope.

## Platform Note Template

Add this concise note before any task() call in a workflow:

Do not use `@...` references inside task() prompt strings.
Always set `readonly=false` for file-producing agents.
Always pass `readonly=false` for file-producing agents.
Assign an explicit write scope for every subagent.
Fresh context:
Model semantics:
Write access:
Write-scope isolation:
Blocking completion semantics:
Success-path artifact gate:
Return-envelope parity:
write_scope:

```
> **Runtime delegation:** Follow the Delegation Invariants and Authoring Rules above; keep the one-shot handoff pattern, omit empty `model`, and let the orchestrator verify expected artifacts before trusting success.
Do not use `@...` references inside task() prompt strings.
Always set `readonly=false` for file-producing agents.
Always pass `readonly=false` for file-producing agents.
Assign an explicit write scope for every subagent.
Fresh context:
Model semantics:
Write access:
Write-scope isolation:
Blocking completion semantics:
Success-path artifact gate:
Return-envelope parity:
write_scope:

```

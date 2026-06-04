<purpose>
Iterative multi-critic review-revision loop. Agent A produces a result; N
independent critics review it in parallel; the meta-critic synthesizes and
decides whether revision is needed; Agent A revises; repeat until convergence
or the loop limit.
</purpose>

<process>

## 0. Parse Arguments

Extract from `$ARGUMENTS`:
- `TASK` — everything before flags; this is the task description or artifact path.
- `N_CRITICS` — value after `--critics` (default: 3).
- `MAX_LOOPS` — value after `--loops` (default: 5).

```bash
TASK=""
N_CRITICS=3
MAX_LOOPS=5

for token in $ARGUMENTS; do
  case "$prev_token" in
    --critics) N_CRITICS="$token"; prev_token=""; continue ;;
    --loops)   MAX_LOOPS="$token";  prev_token=""; continue ;;
  esac
  case "$token" in
    --critics|--loops) prev_token="$token" ;;
    *) TASK="${TASK:+$TASK }$token" ;;
  esac
done
```

Validate: if `TASK` is empty, stop with:

```
ERROR: super-checker requires a task description or artifact path.
Usage: gpd:super-checker <task or artifact> [--critics N] [--loops N]
```

Resolve agent models:

```bash
SOLVER_MODEL=$(gpd resolve-model gpd-result-solver)
CRITIC_MODEL=$(gpd resolve-model gpd-result-critic)
META_MODEL=$(gpd resolve-model gpd-meta-critic)
```

Establish a scoped run workspace for this invocation. Each spawned agent writes
its return into a dedicated artifact under this directory, and the orchestrator
reads it back. This keeps every loop's intermediate result, critiques, and
meta-review durable and auditable instead of living only in transient memory.

```bash
RUN_DIR="GPD/super-checker/run-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR"
```

Announce:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > SUPER-CHECKER
 Task:    {TASK}
 Critics: {N_CRITICS} per round
 Loops:   up to {MAX_LOOPS}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 1. Agent A — Initial Result

Spawn Agent A to produce the first result:

```
* Spawning Agent A (initial)...
```

```
RESULT=$(
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-result-solver.md for your role.

<task>
{TASK}
</task>

Produce a complete, well-reasoned result. Be thorough: show your work,
state assumptions, and flag any caveats or open questions.

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - \"{RUN_DIR}/loop-0/result.md\"
expected_artifacts:
  - \"{RUN_DIR}/loop-0/result.md\"
shared_state_policy: return_only
</spawn_contract>

Write your complete result to {RUN_DIR}/loop-0/result.md and also return it in <result>...</result> tags.",
  subagent_type="gpd-result-solver",
  model="{SOLVER_MODEL}",
  readonly=false,
  description="Agent A: initial result for super-checker"
)
)
```

If the spawn fails, stop with `ERROR: Agent A failed to produce an initial result.`

Extract `CURRENT_RESULT` from the solver return text (everything in
`<result>...</result>` tags, or the full return if no tags are present).

Set `LOOP=0`, `CONVERGED=false`, `LAST_META_REVIEW=""`.

## 2. Review-Revision Loop

Repeat while `LOOP < MAX_LOOPS`:

Increment: `LOOP=$((LOOP + 1))`

Announce:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 LOOP {LOOP}/{MAX_LOOPS} — Spawning {N_CRITICS} critics in parallel...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step A: Spawn N Critics in Parallel

Spawn `N_CRITICS` independent critic agents simultaneously (use parallel task
spawning if the runtime supports it; otherwise spawn sequentially and collect).
Each critic receives the task and the current result but NOT the other critics'
outputs.

Critic prompt template (instantiate for each critic i from 1 to N_CRITICS):

```
CRITIC_{i}_RETURN=$(
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-result-critic.md for your role.

You are Critic {i} of {N_CRITICS}. Your review is INDEPENDENT — do not
reference other critics.

<task>
{TASK}
</task>

<result_to_review>
{CURRENT_RESULT}
</result_to_review>

Find all faults: errors, omissions, unsupported claims, logical flaws,
dimensional inconsistencies, unjustified approximations, missing caveats.
Be specific and cite the exact claim or line you are critiquing.

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - \"{RUN_DIR}/loop-{LOOP}/critic-{i}.md\"
expected_artifacts:
  - \"{RUN_DIR}/loop-{LOOP}/critic-{i}.md\"
shared_state_policy: return_only
</spawn_contract>

Write your critique to {RUN_DIR}/loop-{LOOP}/critic-{i}.md and also return it as your response text.",
  subagent_type="gpd-result-critic",
  model="{CRITIC_MODEL}",
  readonly=false,
  description="Critic {i}/{N_CRITICS}: loop {LOOP}"
)
)
```

Collect all critic returns into `CRITIC_RETURNS`.

### Step B: Spawn the Meta-Critic

Announce:

```
* Meta-critic synthesizing {N_CRITICS} reviews...
```

Assemble the collected critic outputs into `CRITICS_TEXT`:

```
Critic 1 review:
{CRITIC_1_RETURN}

Critic 2 review:
{CRITIC_2_RETURN}

... (all critics)
```

```
META_RETURN=$(
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-meta-critic.md for your role.

You are the meta-critic. You have received {N_CRITICS} independent reviews.

<task>
{TASK}
</task>

<current_result>
{CURRENT_RESULT}
</current_result>

<independent_reviews>
{CRITICS_TEXT}
</independent_reviews>

Synthesize the reviews. Identify themes. Evaluate each critique (is it
valid, trivial, or incorrect?). Write a complete review that Agent A will
use to revise its result. Then decide: does the result need substantive
revision, or is it acceptable?

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - \"{RUN_DIR}/loop-{LOOP}/meta-review.md\"
expected_artifacts:
  - \"{RUN_DIR}/loop-{LOOP}/meta-review.md\"
shared_state_policy: return_only
</spawn_contract>

Write your complete review to {RUN_DIR}/loop-{LOOP}/meta-review.md and also return it as your response text.",
  subagent_type="gpd-meta-critic",
  model="{META_MODEL}",
  readonly=false,
  description="Meta-critic: loop {LOOP}"
)
)
```

Store `LAST_META_REVIEW="$META_RETURN"`.

### Step C: Check for Convergence (Step 4.5)

Parse the meta-critic return for its convergence decision. The meta-critic
returns either:

- `STATUS: CONVERGED` — no substantive criticisms remain → exit the loop.
- `STATUS: NEEDS_REVISION` — substantive issues exist → continue.

If `STATUS: CONVERGED` (or the meta-critic text clearly states no substantive
criticisms remain):

```
✓ Converged after {LOOP} loop(s). No substantive criticisms remain.
```

Set `CONVERGED=true` and break out of the loop.

### Step D: Agent A Revises (only if LOOP < MAX_LOOPS)

If revision is needed and `LOOP < MAX_LOOPS`:

Announce:

```
* Agent A revising (loop {LOOP})...
```

```
RESULT=$(
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-result-solver.md for your role.

You previously produced a result for this task. A panel of critics reviewed
it, and the meta-critic has written a complete review. Revise your result
to address all substantive criticisms.

<task>
{TASK}
</task>

<your_previous_result>
{CURRENT_RESULT}
</your_previous_result>

<complete_review_from_meta_critic>
{META_RETURN}
</complete_review_from_meta_critic>

Produce an improved result that fully addresses every substantive
criticism. Do not merely patch — rethink and strengthen where needed.
Show your revised work clearly.

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - \"{RUN_DIR}/loop-{LOOP}/result.md\"
expected_artifacts:
  - \"{RUN_DIR}/loop-{LOOP}/result.md\"
shared_state_policy: return_only
</spawn_contract>

Write your revised result to {RUN_DIR}/loop-{LOOP}/result.md and also return it in <result>...</result> tags.",
  subagent_type="gpd-result-solver",
  model="{SOLVER_MODEL}",
  readonly=false,
  description="Agent A: revision {LOOP}"
)
)
```

Extract `CURRENT_RESULT` from the new solver return.

End of loop body. If `LOOP == MAX_LOOPS` and `CONVERGED=false`, break.

## 3. Final Summary

Announce:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > SUPER-CHECKER COMPLETE
 Loops completed: {LOOP}/{MAX_LOOPS}
 Converged: {CONVERGED}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Present to the user:

1. **Final result** — `CURRENT_RESULT` (the last result produced by Agent A).

2. **Summary** — `{LOOP}` review loop(s) completed.
   - If `CONVERGED=true`: "Converged — no substantive criticisms remain."
   - If `CONVERGED=false`: "Did not converge within `{MAX_LOOPS}` loops. Consider
     re-running with `--loops N` for more cycles."

3. **Remaining concerns** — Extract the `REMAINING_CONCERNS` section from
   `LAST_META_REVIEW`. If the meta-critic found no remaining concerns, say
   "No remaining concerns."

</process>

<success_criteria>
- [ ] Arguments parsed correctly (task, critics, loops)
- [ ] Agent A produced an initial result before any review
- [ ] Each loop: N critics ran, meta-critic synthesized
- [ ] Convergence check fired on every loop; early exit when converged
- [ ] Final result, loop count, convergence status, and remaining concerns presented
</success_criteria>

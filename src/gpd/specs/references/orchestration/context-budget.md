<overview>
Context windows are finite (~200k tokens, ~80% usable before the runtime compresses). Research workflows that ignore context pressure produce degraded results: missed signs, sloppy limits, forgotten conventions. Managing context is part of research discipline, not an engineering detail.

**Core principle:** A fresh context with the right files loaded outperforms a saturated context with everything accumulated. Plan segmentation, strategic `/clear`, and proactive handoffs are research quality tools.

**Key numbers:**

- Total window: ~200k tokens
- Usable before compression: ~160k tokens (80%)
- Statusline shows scaled usage: 100% = 80% real = compression imminent
- After compression: prior context is summarized, detail is lost

**Related:** For per-agent pressure thresholds (GREEN/YELLOW/ORANGE/RED), see `references/orchestration/context-pressure-thresholds.md`. For the canonical threshold table, see `references/orchestration/agent-infrastructure.md` §Context Pressure Management.
  </overview>

<budget_allocation>

## Context Budget by Workflow

Different workflows consume context at different rates. Use these targets to plan segmentation.

| Workflow                      | Target Budget    | Why                                               |
| ----------------------------- | ---------------- | ------------------------------------------------- |
| Standard plan execution       | ~50% per plan    | Linear task sequence, moderate file reads         |
| Hypothesis-driven plan        | ~40% per plan    | PREDICT-DERIVE-VERIFY cycle is inherently heavier |
| Literature review             | ~60% per session | Heavy web fetching and synthesis                  |
| Debugging session             | ~50% per session | Iterative read-modify-test cycles                 |
| Phase planning (orchestrator) | ~40%             | Spawns subagents; main context stays lean         |
| Paper writing                 | ~50% per section | Large reference reads + iterative drafting        |

**Rule of thumb:** If a plan will touch >5 files or produce >3 derivation steps, budget ~50% and segment if needed.
</budget_allocation>

<context_consumption>

## What Consumes Context

**Heavy consumers (watch these):**

| Activity                        | Approximate Cost   | Notes                          |
| ------------------------------- | ------------------ | ------------------------------ |
| Reading a large derivation file | 2-8k tokens        | Scales with file length        |
| Full PLAN.md read               | 1-3k tokens        | Complex plans with many tasks  |
| Lengthy symbolic derivation     | 5-15k tokens       | Multi-step algebra accumulates |
| Numerical output + analysis     | 3-10k tokens       | Data tables, convergence logs  |
| Literature search results       | 5-15k tokens       | Web fetch results are verbose  |
| Error investigation cycle       | 3-8k per iteration | Read-diagnose-fix-verify loops |
| Tool call overhead              | ~0.5k per call     | Adds up over many calls        |

**Light consumers:**

| Activity             | Approximate Cost |
| -------------------- | ---------------- |
| Reading STATE.md     | 0.5-1k tokens    |
| Short config reads   | 0.2-0.5k tokens  |
| Git operations       | 0.3-1k tokens    |
| Simple bash commands | 0.2-0.5k tokens  |

**Subagent advantage:** Each subagent (gpd-executor, gpd-planner, etc.) gets a fresh context window. The orchestrator's context stays lean. This is why `../../workflows/execute-plan.md` routes non-interactive work to subagents.
</context_consumption>

<pressure_signs>

## Signs of Context Pressure

**Early warning (50-65% statusline):**

- You've read many files but haven't started the core derivation yet
- Multiple large reference documents loaded
- Several error-fix-retry cycles completed

**Moderate pressure (65-80% statusline):**

- Derivation steps are getting longer with more intermediate algebra
- You're re-reading files you read earlier (may indicate compression already happened)
- Responses feel like they're missing context from earlier in the conversation

**Critical (80-95% statusline):**

- Compression is imminent or has already occurred
- Risk of losing derivation context, parameter values, sign conventions
- Quality of physics reasoning may degrade

**Emergency (95%+ / skull icon):**

- Context will compress imminently
- Save state NOW via `/gpd:pause-work`
- Do NOT start new derivations or calculations
  </pressure_signs>

<segmentation_guidelines>

## Plan Segmentation Strategy

Plans should be sized to fit within context budget. Segment when a plan would exceed ~50% of usable context.

**Indicators a plan needs segmentation:**

- More than 6-8 substantive tasks
- Multiple independent derivations that don't share intermediate results
- Tasks that each require reading different large reference files
- Numerical computations with extensive output analysis
- Mix of symbolic derivation and numerical verification

**How to segment:**

1. **By natural physics boundaries:** Separate derivation from numerical verification. Separate independent observables.
2. **By dependency structure:** Tasks that share intermediate results stay together. Independent tasks can split.
3. **By checkpoint placement:** Checkpoints are natural segment boundaries -- verification checkpoints especially.
4. **By file scope:** Tasks touching the same files stay together. Different file sets can split.

**Segment boundary protocol:**

- Each segment produces committed, self-contained results
- Later segments can read committed files from earlier segments via `@context` references
- SUMMARY.md for each segment captures key results, parameter values, and conventions

**Anti-pattern:** Don't segment so aggressively that each segment lacks the context to verify its own physics. A derivation + its limiting case check should be in the same segment.
</segmentation_guidelines>

<clear_and_resume>

## When to /clear and Resume

**Always /clear between:**

- Phase planning and phase execution (orchestrator context vs executor context)
- Completing one plan and starting the next
- Literature review and derivation work
- Debugging session and resumption of normal execution

**Consider /clear when:**

- Statusline shows >65% (moderate pressure)
- You've finished a logical unit of work (completed a derivation, verified a result)
- You're about to start a task requiring heavy file reads
- Error investigation consumed significant context

**Before /clear, always:**

1. Commit all work in progress
2. Update STATE.md with current position
3. If mid-plan: create `.continue-here.md` via `/gpd:pause-work`
4. Ensure intermediate results are saved to files (not just in conversation memory)

**After /clear:**

1. `/gpd:resume-work` restores full context from STATE.md and .continue-here.md
2. Re-read only the files needed for the next unit of work
3. Do NOT re-read files from completed work unless needed for reference

**The goal:** Start each work unit with a fresh, focused context containing exactly what's needed.
</clear_and_resume>

<planning_for_context>

## Planning with Context in Mind

When creating plans (via /gpd:plan-phase), consider context budget:

**Plan-level considerations:**

- Each plan should target ~50% context usage (40% for hypothesis-driven)
- If a phase has extensive work, split into multiple plans rather than one large plan
- Assign waves so independent plans execute in parallel subagents (each gets fresh context)

**Task-level considerations:**

- Front-load `@context` file reads -- read what you need early, not repeatedly
- Group related tasks that share context (same derivation, same files)
- Place verification tasks immediately after the derivation they verify
- Don't scatter related checks across distant tasks

**Context-aware plan structure:**

```
Plan 1 (wave 1): Core derivation + immediate verification
  - Tasks share the same intermediate results
  - ~50% context budget

Plan 2 (wave 1): Independent numerical computation
  - Different files, different methods
  - Parallel with Plan 1 (separate subagent = fresh context)

Plan 3 (wave 2): Synthesis requiring results from Plans 1+2
  - Reads committed results from earlier plans
  - Fresh context for synthesis work
```

**Flag in plan frontmatter:** If a plan is estimated to be context-heavy, note it:

```yaml
context_note: "Heavy - multiple long derivations. Consider splitting if >6 tasks."
```

</planning_for_context>

<execution_awareness>

## Context Awareness During Execution

During plan execution, monitor context usage:

**After each task:**

1. Glance at statusline context percentage
2. If >50%: assess remaining work volume
3. If remaining work is heavy AND context >60%: consider proactive pause

**Proactive pause protocol:**

1. Commit current task's work
2. Note completed tasks and remaining tasks
3. Create `.continue-here.md` with derivation state, parameter values, intermediate results
4. Recommend `/clear` + `/gpd:resume-work`

**Never do when context is heavy:**

- Start a new multi-step derivation
- Read large reference files "just in case"
- Begin error investigation that may require multiple iterations
- Start numerical experiments with uncertain convergence
  </execution_awareness>

<agent_context_profiles>

## Context Consumption by Agent Type

Different GPD agents have different context profiles:

| Agent                | Typical Usage | Why                                           |
| -------------------- | ------------- | --------------------------------------------- |
| gpd-executor         | 40-70%        | Executes tasks, reads files, runs derivations |
| gpd-planner          | 30-50%        | Reads research + state, produces plans        |
| gpd-phase-researcher | 40-60%        | Web searches, literature, synthesis           |
| gpd-plan-checker     | 20-30%        | Reads plans, checks against goals             |
| gpd-verifier         | 30-50%        | Reads results, runs validation checks         |
| gpd-debugger         | 50-80%        | Iterative investigation, heavy reads          |
| gpd-paper-writer     | 50-70%        | Large reference reads + iterative drafting    |

**Implication for orchestrators:** When spawning subagents, the orchestrator context stays lean (~20-30%). Subagent work does NOT consume orchestrator context. This is a key architectural advantage -- use subagents for heavy work.
</agent_context_profiles>

<worked_examples>

## Worked Examples: Token Estimates

### Example 1: One-Loop QFT Calculation

A typical one-loop QFT calculation (setup + regularization + renormalization + limiting cases):

| Step | Token Cost | Cumulative |
|------|-----------|------------|
| Read STATE.md + PLAN.md + conventions | ~2k | 2k |
| Review and set up Lagrangian, Feynman rules | ~3k | 5k |
| Compute one-loop diagram(s) + dim reg | ~8-12k | 13-17k |
| Renormalization + counterterms | ~5-8k | 18-25k |
| Limiting case checks (2-3 limits) | ~5-7k | 23-32k |
| Write SUMMARY.md + commit | ~3k | 26-35k |

**Total: ~28-35k tokens.** Fits comfortably in one segment (~50% budget).

### Example 2: Two-Loop Calculation

A two-loop calculation requiring multiple integral evaluations:

| Step | Token Cost | Cumulative |
|------|-----------|------------|
| Setup + Feynman rules + diagram enumeration | ~5k | 5k |
| Evaluate 3-5 two-loop integrals (IBP, Feynman params) | ~20-30k | 25-35k |
| UV subdivergence handling + renormalization | ~10-15k | 35-50k |
| Combine results + limiting cases | ~8-10k | 43-60k |
| Numerical cross-checks + SUMMARY | ~5-10k | 48-70k |

**Total: ~55-70k tokens.** Exceeds 50% budget — should be split into two segments:
- Segment A: Diagram enumeration + integral evaluation
- Segment B: Renormalization + verification + synthesis

### Example 3: Numerical Validation Phase

A numerical validation phase (implement + run + analyze convergence):

| Step | Token Cost | Cumulative |
|------|-----------|------------|
| Read analytical results from prior phase | ~3-5k | 3-5k |
| Write numerical implementation | ~8-12k | 11-17k |
| Run convergence tests (3-5 grid sizes) | ~5-8k | 16-25k |
| Analyze convergence, fit scaling | ~5-8k | 21-33k |
| Compare with analytical limits | ~3-5k | 24-38k |
| SUMMARY + plots description | ~3k | 27-41k |

**Total: ~30-40k tokens.** Fits in one segment unless the implementation is unusually complex.

</worked_examples>

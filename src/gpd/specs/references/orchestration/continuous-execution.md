# Continuous Execution Mode

Standard protocol for multi-phase execution with structured review checkpoints. Controls whether the assistant pauses between phases or auto-advances, and where human approval is required regardless of execution mode.

## Execution Modes

GPD supports three execution modes, each mapped to an `autonomy` setting in `GPD/config.json`:

| Execution Mode                   | Autonomy Setting | Behavior                                                                 |
| -------------------------------- | ---------------- | ------------------------------------------------------------------------ |
| **Manual** (default)             | `supervised`     | Pause after every phase. User explicitly invokes each next step.         |
| **Continuous**                   | `yolo`           | Auto-advance through phases without pause unless a hard checkpoint fires.|
| **Continuous-with-checkpoints**  | `balanced`       | Auto-advance through safe phases; pause at structured review boundaries. |

### Manual Mode (`supervised`)

Every phase completion pauses. The assistant prints the status block (see Checkpoint Pause Format below) and waits for the user to invoke the next command. This is the safest mode for exploratory or high-stakes research where every intermediate result needs human judgment.

### Continuous Mode (`yolo`)

The assistant auto-advances through all phases that do not hit a hard checkpoint. Hard checkpoints still pause execution even in continuous mode. The assistant never skips a hard checkpoint.

### Continuous-with-Checkpoints Mode (`balanced`)

This is an explicit opt-in after the user leaves the default `supervised` posture. The assistant auto-advances through phases that are safe to continue (see Safe Auto-Advance Phases below). At structured checkpoint boundaries, execution pauses for review. This balances throughput with research quality control.

## Safe Auto-Advance Phases

The following phase transitions are eligible for auto-advance in `balanced` or `yolo`. In `supervised`, they still pause because the default posture is manual review:

- **Literature review completion** -> next phase (results are additive, not load-bearing for correctness)
- **Formalism setup completion** -> execution phases (conventions and notation are committed, verifiable from artifacts)
- **Numerical validation completion** -> next phase (convergence and correctness are machine-checkable)
- **Inter-wave transitions within a phase** (handled by execute-phase wave logic, not this protocol)

These phases produce artifacts that are either machine-verifiable or do not gate downstream correctness.

## Hard Checkpoint Types

These checkpoints require human review regardless of execution mode. Even `yolo` pauses here.
Treat these labels as phase-level review categories layered on top of the lower-level checkpoint reasons used elsewhere in GPD; they do not replace the canonical `human-verify`, `decision`, or `human-action` checkpoint taxonomy.

### `plan-review`

**Fires after:** Plan generation for a new phase (`gpd:plan-phase` completion).

**Why required:** The plan determines the entire research direction for the phase. Approving a flawed plan wastes all downstream computation.

**What to review:** Phase plan structure, task decomposition, dependency ordering, scope alignment with project goals, whether the plan addresses the phase GOAL from the roadmap.

### `experiment-review`

**Fires after:** Experiment design completion or first load-bearing result in an execution phase.

**Why required:** Experimental parameters, approximation choices, and regime selections are research-direction decisions that require domain judgment.

**What to review:** Parameter choices, approximation justification, whether the experimental setup tests the right hypothesis, whether control cases are included.

### `paper-outline-review`

**Fires after:** Paper outline or draft structure generation.

**Why required:** The narrative structure of a paper determines how results are presented and which arguments are emphasized. Structural problems caught early save major rewrites.

**What to review:** Section ordering, argument flow, which results are highlighted, whether the story is coherent, whether all key results have a home in the outline.

### `final-output-review`

**Fires after:** Milestone completion, paper draft completion, or any terminal output artifact.

**Why required:** Final outputs leave the research pipeline. Quality, correctness, and completeness must be verified before marking work as done.

**What to review:** Complete artifact set, consistency between text and figures, bibliography completeness, all verification evidence, whether the output meets the project contract.

## Checkpoint Pause Format

When execution pauses at a checkpoint, the assistant prints a structured status block:

```
+============================================================+
|  PHASE CHECKPOINT: {checkpoint_type}                       |
+============================================================+

Completed: Phase {N} -- {phase_name}
Status:    All plans passed, verification passed

Why paused: {checkpoint_type} requires human review before
            continuing. {one-sentence reason specific to this
            checkpoint type}

Key artifacts to review:
  - {artifact_path_1} ({description})
  - {artifact_path_2} ({description})

Next command:
  {exact command surfaced by the workflow}

--------------------------------------------------------------
```

The status block always includes:
1. **Current phase completed** -- which phase just finished and its pass/fail status
2. **Why execution paused** -- the specific checkpoint type and a human-readable reason
3. **Key artifacts to review** -- file paths the reviewer should inspect before approving
4. **Next command** -- the exact runtime or terminal command to continue, such as `gpd:plan-phase {N+1}`, `gpd:complete-milestone`, or `gpd resume` for read-only recovery before re-entering the runtime

## Continuation Protocol

The pause block should always surface the exact next command for the current workflow state.

If you leave the runtime and need a read-only recovery snapshot first, use:

```bash
gpd resume
```

The recovery command:
1. Reads `STATE.md` and `ROADMAP.md` to infer the current project position
2. Determines the next action (plan next phase, execute next phase, complete milestone, etc.)
3. Helps you re-enter the correct runtime command with fresh state

There is no need to rely on conversation history before continuing. `gpd resume` loads fresh state from disk, and the runtime pause block should name the exact follow-up command when you are ready to continue.

## Integration with Autonomy Modes

The mapping between autonomy modes and execution behavior:

| Autonomy    | Between-phase behavior              | Hard checkpoints | Soft checkpoints           |
| ----------- | ----------------------------------- | ---------------- | -------------------------- |
| `supervised`| Always pause                        | Always pause     | Always pause               |
| `balanced`  | Auto-advance safe phases            | Always pause     | Pause per `review_cadence` |
| `yolo`      | Auto-advance all phases             | Always pause     | Auto-continue              |

**`review_cadence` interaction:** Within the `balanced` mode, `review_cadence` controls the density of soft checkpoints (wave-level review gates). `dense` inserts more wave-boundary pauses; `sparse` reduces them. Hard checkpoints are never affected by `review_cadence`.

**`checkpoint_after_n_tasks` interaction:** This config value controls task-level checkpoints within plan execution. It operates independently of the phase-level checkpoint protocol defined here. Both systems can fire checkpoints; neither overrides the other.

## Continuation Routing Decision Tree

After phase completion, the orchestrator evaluates:

```
1. Is autonomy == supervised?
   YES -> pause (manual mode, always pause)

2. Is there a pending hard checkpoint for the next action?
   (e.g., next phase needs plan-review, or milestone is complete
    and needs final-output-review)
   YES -> pause with checkpoint status block

3. Is autonomy == balanced AND is the next phase safe to auto-advance?
   YES -> auto-advance to next phase
   NO  -> pause with checkpoint status block

4. Is autonomy == yolo?
   YES -> auto-advance to next phase
```

This tree is evaluated in the `offer_next` step of the execute-phase workflow. See `{GPD_INSTALL_DIR}/workflows/execute-phase.md` for the concrete implementation.

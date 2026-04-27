# route — scope-change router

## Purpose

Decide whether a user's intended scope change should be executed as:

- `gpd:add-phase` or `gpd:insert-phase` — new work that extends the current milestone
- `gpd:revise-phase` — revision of a specific prior phase's conclusions
- `gpd:new-milestone` — start a new milestone on an already-closed one
- `gpd:complete-milestone` followed by `gpd:new-milestone` — ranking is frozen, scope expansion belongs to a fresh milestone

## Decision matrix

The routing is a function of three answers:

| Ranking frozen? | Change type | Deliverable layer | Recommendation |
|---|---|---|---|
| no  | extend | new layer    | `gpd:add-phase`            |
| no  | extend | change prior | `gpd:revise-phase`         |
| no  | revise | *            | `gpd:revise-phase`         |
| yes | extend | new layer    | `gpd:complete-milestone` then `gpd:new-milestone` |
| yes | extend | change prior | `gpd:revise-phase` (unfreeze first) |
| yes | revise | *            | `gpd:revise-phase` (unfreeze first) |

"Unfreeze first" means: document the scope change in the milestone's REQUIREMENTS.md or PROJECT.md note before running the revise, because a revision inside a frozen ranking may invalidate the milestone archive.

## Process

<process>

<step name="load_state" priority="first">
Read authoritative state:

```bash
STATE=$(gpd --raw state get --include position,continuation)
ROADMAP=$(gpd --raw roadmap analyze)
```

Extract:

- `current_milestone` — either the active milestone version, or `none` if the last milestone was completed and no new roadmap exists
- `current_phase` / `current_phase_name` — the last active phase, or `none` if inactive
- `adaptive_approach_locked` — whether the ranking signal is already locked (see `suggest.py:_has_adaptive_lock_signal`)
</step>

<step name="ask_frozen">
Ask: "Is the ranking / prior conclusion frozen for this milestone?"

Accept any of:
- explicit `--frozen=yes` / `--frozen=no` flag
- `ask_user` with options `Yes — ranking is frozen` / `No — still in play`
- if `adaptive_approach_locked` is `true` and no explicit answer given, default to `yes` but confirm

Store as `FROZEN` (yes|no).
</step>

<step name="ask_change_type">
Ask: "Are you extending scope or revising the same result?"

Options:
- `Extend` — new calculations or deliverables that build on prior work
- `Revise` — the same conclusion needs to change (new data, wrong assumption, etc.)

Accept `--change=extend|revise` to skip the prompt. Store as `CHANGE`.
</step>

<step name="ask_layer">
Ask: "Does this add a new deliverable layer, or change prior conclusions?"

Options:
- `New layer` — a parameter sweep on top of a derived model, a numerical check on top of an analytic result, a comparison plot on top of verified data, or a manuscript section on top of completed phases
- `Change prior` — the prior phase's output needs to move

Accept `--layer=new|change`. Store as `LAYER`.
</step>

<step name="decide">
Apply the decision matrix above. Produce:

- `RECOMMENDATION` — the exact command(s) the user should run next
- `RATIONALE` — one sentence explaining which answers drove the choice

**No active milestone override:** If `current_milestone=none`, do not recommend `gpd:add-phase` because there is no active milestone to extend. For `CHANGE=extend`, recommend `gpd:new-milestone`. For `CHANGE=revise` or `LAYER=change`, recommend `gpd:revise-phase` and state that the revision may invalidate the archived milestone.

When the recommendation is compound (`complete-milestone` + `new-milestone`), emit both commands separately in the `## > Next Up` block. Do not chain them into a single call — the user must confirm between them.
</step>

<step name="render">
Emit:

```
## > Next Up

Current milestone: ${current_milestone}
Current phase:     ${current_phase_name} (${current_phase})

Answers: frozen=${FROZEN}, change=${CHANGE}, layer=${LAYER}

Recommendation: ${RECOMMENDATION}
Why: ${RATIONALE}

<sub>Start a fresh context window, then run the command(s) above.</sub>
```

If the recommendation is `gpd:complete-milestone` + `gpd:new-milestone`, render both on separate lines with the note:

> Run `gpd:complete-milestone` first, confirm the archive, then run `gpd:new-milestone`.
</step>

</process>

<success_criteria>

- [ ] State-driven context line present (current milestone + phase)
- [ ] All three routing answers collected (via prompt or flag)
- [ ] Exactly one recommendation returned; if the recommendation is compound, the ordered command sequence is rendered explicitly
- [ ] Rationale names the driving answers

</success_criteria>

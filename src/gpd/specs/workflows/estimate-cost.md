<purpose>
Estimate token usage and API cost for executing research phases. Produces a formatted cost report showing per-phase breakdown, agent type distribution, and cost ranges across model tiers. Helps researchers understand spend before committing to expensive execution runs.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="init_context">
**Load project context:**

```bash
INIT=$(gpd init progress --include roadmap,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `project_exists`, `roadmap_exists`, `phases`, `phase_count`, `completed_count`.

**File contents (from --include):** `roadmap_content`, `config_content`.

If `project_exists` is false (no `.planning/` directory):

```
No planning structure found.

Run $gpd-new-project to start a new research project.
```

Exit.

If `roadmap_exists` is false:

```
No ROADMAP.md found. Cannot estimate costs without a roadmap.

Run $gpd-new-project or $gpd-new-milestone to create one.
```

Exit.
</step>

<step name="parse_scope">
**Determine estimation scope from $ARGUMENTS:**

- If $ARGUMENTS is a number (e.g., "3", "2.1"): scope = that phase number
- If $ARGUMENTS is "all": scope = "all"
- If $ARGUMENTS is empty or "remaining": scope = "remaining"

Default: `remaining`
</step>

<step name="read_profile">
**Determine active model profile:**

Parse `config_content` for `model_profile` field. Default: `review`.

The profile determines which tier each agent uses. Simplified summary (see `references/model-profiles.md` for the full 16-agent table):

| Profile       | Executor       | Verifier | Planner | Researcher     |
| ------------- | -------------- | -------- | ------- | -------------- |
| deep-theory   | tier-1         | tier-1   | tier-1  | tier-1         |
| numerical     | tier-2         | tier-1   | tier-1  | tier-1         |
| exploratory   | tier-2         | tier-2   | tier-1  | tier-1         |
| review        | tier-2         | tier-1   | tier-1  | tier-2         |
| paper-writing | tier-1         | tier-2   | tier-1  | tier-2         |

The `cost-estimate` CLI command reads the full profile table and computes per-agent costs. This summary is for quick reference only.

</step>

<step name="run_estimate">
**Get cost estimate from gpd CLI:**

```bash
ESTIMATE=$(gpd cost-estimate "$SCOPE")
```

This returns JSON with:

- `scope`: "phase", "remaining", or "all"
- `estimated_tokens`: total token count
- `estimated_agent_spawns`: total agent spawn count
- `estimated_cost_usd`: cost breakdown by tier (`tier-1`, `tier-2`, `tier-3`)
- `agent_type_counts`: agents by type (executor, verifier, researcher)
- `phases`: per-phase breakdown (for multi-phase scopes)
- `pricing_reference`: per-million-token rates
- `breakdown`: per-plan detail (for single phase)

If error in response, display the error message and exit.
</step>

<step name="present_report">
**Format and present the cost report.**

**For single phase scope:**

```
# Cost Estimate: Phase {N} — {Name}

**Plans:** {count} ({count with plans} planned, {count without} unplanned)
**Agent spawns:** {total}

## Plan Breakdown

| Plan            | Type     | Wave | Agents | Est. Tokens |
|-----------------|----------|------|--------|-------------|
| {plan-file}     | execute  | 1    | 2      | 65,000      |
| {plan-file}     | research | 1    | 3      | 85,000      |

## Agent Distribution

| Agent Type  | Spawns | Default Tier ({profile}) |
|-------------|--------|--------------------------|
| executor    | 2      | tier-2                   |
| verifier    | 2      | tier-1                   |
| researcher  | 1      | tier-2                   |

## Estimated Cost

| Tier   | $/M input | $/M output | Est. Cost (input) |
|--------|-----------|------------|--------------------|
| tier-1 | $15.00    | $75.00     | ${tier-1 cost}     |
| tier-2 | $3.00     | $15.00     | ${tier-2 cost}     |
| tier-3 | $0.25     | $1.25      | ${tier-3 cost}     |

**Active profile:** {profile} — agents use mixed tiers (see table above)
**Realistic estimate:** ${tier-2 cost} – ${tier-1 cost} depending on profile

> Estimates are input-token-only. Actual cost includes output tokens (typically 1.5–3x input cost).
> Unplanned phases use heuristic: ~130K tokens, 4 agent spawns.
```

**For multi-phase scope (remaining/all):**

```
# Cost Estimate: {Remaining|Full Project}

**Phases:** {estimated_phases} of {total_phases} {(remaining unfinished)|total}
**Total agent spawns:** {total}

## Phase Breakdown

| Phase | Name                          | Plans | Status   | Est. Tokens | Est. Cost (tier-2) |
|-------|-------------------------------|-------|----------|-------------|---------------------|
| 1     | Analytical Setup              | 2     | complete | —           | —                   |
| 2     | Numerical Validation          | 3     | partial  | 195,000     | $0.59               |
| 3     | Parameter Sweep               | 0     | planned  | 130,000     | $0.39               |

(For scope=remaining, completed phases show "—" for cost. For scope=all, show all.)

## Aggregate Cost

| Tier   | $/M input | $/M output | Est. Total (input) |
|--------|-----------|------------|--------------------|
| tier-1 | $15.00    | $75.00     | ${tier-1 total}    |
| tier-2 | $3.00     | $15.00     | ${tier-2 total}    |
| tier-3 | $0.25     | $1.25      | ${tier-3 total}    |

**Active profile:** {profile}
**Realistic estimate:** ${tier-2 total} – ${tier-1 total} depending on profile

## Agent Distribution (aggregate)

| Agent Type  | Total Spawns |
|-------------|--------------|
| executor    | {count}      |
| verifier    | {count}      |
| researcher  | {count}      |

> Estimates are input-token-only. Actual cost includes output tokens (typically 1.5–3x input cost).
> Unplanned phases use heuristic: ~130K tokens, 4 agent spawns.
> Phase estimates are based on plan count and type. Actual usage varies with task complexity.
```

</step>

<step name="actual_cost_tracking">
## Actual Cost Tracking

After each agent spawn completes, record usage to `.planning/cost-log.json`:

```json
{
  "entries": [
    {
      "timestamp": "2026-02-22T10:30:00Z",
      "phase": 3,
      "plan": 1,
      "agent_type": "gpd-executor",
      "model": "opus",
      "input_tokens": 45000,
      "output_tokens": 12000,
      "estimated_cost_usd": 1.23,
      "duration_seconds": 180
    }
  ],
  "totals": {
    "input_tokens": 450000,
    "output_tokens": 120000,
    "estimated_cost_usd": 12.50,
    "agent_spawns": 15
  }
}
```

**View cost summary:** `$gpd-estimate-cost all` shows cumulative spend vs estimates.

Note: Token counts must be extracted from Task tool return metadata. If not available, estimate from context usage percentage x 200K.
</step>

<step name="notes">
**Append contextual notes:**

- If any phases have 0 plans: "**Note:** {N} phases have no plans yet. Estimates use heuristic (~130K tokens per phase). Run `$gpd-plan-phase` for accurate estimates."
- If profile is `deep-theory`: "**Note:** deep-theory profile uses tier-1 for most agents. Expect costs near the tier-1 column."
- If profile is `review` (default): "**Note:** review profile uses tier-1 for verification agents, tier-2 for execution. Expect costs between tier-2 and tier-1 columns."
  </step>

</process>

<success_criteria>

- [ ] Scope correctly parsed (phase number, remaining, or all)
- [ ] Cost estimate retrieved via gpd cost-estimate command
- [ ] Per-phase breakdown displayed with token counts
- [ ] Agent type distribution shown
- [ ] All three tier costs displayed with active profile highlighted
- [ ] Unplanned phases flagged with heuristic notice
- [ ] Output tokens caveat included
- [ ] Profile-specific notes appended
- [ ] Clean ASCII table formatting

</success_criteria>

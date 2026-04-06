<purpose>
Configure and manage an academic-only GPD platform deployment with credit grants, full log capture, and artifact provenance tracking. Academic mode enforces budget-aware execution and enhanced observability suitable for institutional use.
</purpose>

<core_principle>
Academic mode adds a credit and audit layer on top of standard GPD workflows. Every agent invocation, artifact, and decision is logged with provenance metadata. Credit budgets gate expensive operations before they start, preventing runaway costs in grant-funded research.
</core_principle>

<required_reading>
Read GPD/config.json to check current platform_mode and credit settings.
Read GPD/STATE.md to understand project context.
</required_reading>

<process>

<step name="check_mode" priority="first">
Load config and verify academic mode:

```bash
CONFIG=$(gpd config get academic)
PLATFORM_MODE=$(echo "$CONFIG" | gpd json get .platform_mode --default "standard")
```

If `platform_mode` is not `academic`, offer to enable it:
- Set `platform_mode` to `academic`
- Ask for `credit_budget` (integer, or null for unlimited)
- Confirm `artifact_capture` is enabled (default: true)
</step>

<step name="credit_status">
Display current credit usage:

```bash
BUDGET=$(gpd config get credit_budget)
USED=$(gpd config get credit_used)
```

Show:
- Credit budget: `$BUDGET` (or "unlimited")
- Credits used: `$USED`
- Credits remaining: `$BUDGET - $USED` (or "unlimited")
- Artifact capture: enabled/disabled
</step>

<step name="session_logging">
Academic mode automatically:

1. **Logs every agent invocation** with credit cost estimate to `GPD/academic/events.jsonl`
2. **Captures all artifacts** with provenance metadata to `GPD/academic/artifacts.jsonl`
3. **Enforces budget checks** before spawning expensive agents (tier-1 models)
4. **Records session summaries** with credit breakdowns

Events include:
- `agent_invocation` — agent name, tier, estimated credit cost
- `artifact_produced` — file path, type, producing agent, provenance chain
- `checkpoint_reached` — phase/plan progress with cumulative credit usage
- `budget_warning` — when remaining credits drop below 20% of budget
- `budget_exhausted` — when credits are fully consumed
</step>

<step name="artifact_provenance">
Each captured artifact records:

- **Who** created it (agent name, model tier)
- **When** it was created (ISO timestamp)
- **From what** inputs (source files, reference papers, prior results)
- **With what** parameters (model config, seeds, numerical settings)
- **Reproducibility** hints (enough info to recreate the artifact)

This supports institutional audit requirements and research reproducibility standards.
</step>

<step name="budget_management">
Budget management operations:

**Set budget:**
```bash
gpd config set credit_budget 1000
```

**Check remaining:**
```bash
gpd config get academic
```

**Reset usage counter:**
```bash
gpd config set credit_used 0
```

When budget is exhausted, GPD will:
1. Refuse to spawn new agents
2. Allow read-only operations (show, progress, export)
3. Display clear message about budget status and how to increase it
</step>

</process>

<output_format>
When reporting academic platform status, show:

```
Academic Platform Status
========================
Mode:              academic
Credit Budget:     {budget} (or unlimited)
Credits Used:      {used}
Credits Remaining: {remaining}
Artifact Capture:  {enabled/disabled}
Events Logged:     {count}
Artifacts Tracked: {count}
```
</output_format>

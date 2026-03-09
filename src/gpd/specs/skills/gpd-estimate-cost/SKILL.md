---
name: gpd-estimate-cost
description: Estimate token usage and API cost for phases of the current research project
argument-hint: "[phase-number | remaining | all]"
allowed-tools:
  - read_file
  - shell
  - grep
  - glob
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Estimate the token usage and API cost for executing research phases. Shows per-phase and per-agent-type breakdowns with cost ranges across model tiers.

Use this to understand the cost implications before executing phases, especially for large projects or expensive tier-1 profiles.

**Scopes:**

- `<phase-number>` — Estimate a single phase (e.g., `$gpd-estimate-cost 3`)
- `remaining` (default) — Estimate all unfinished phases
- `all` — Estimate the entire project including completed phases
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/estimate-cost.md
</execution_context>

<context>
Scope: $ARGUMENTS (optional — defaults to "remaining")

@.planning/ROADMAP.md
@.planning/config.json
</context>

<process>
Execute the estimate-cost workflow from @{GPD_INSTALL_DIR}/workflows/estimate-cost.md end-to-end.

## Step 1: Init Context

```bash
INIT=$(gpd init progress --include roadmap,config)
```

Extract from init JSON: `project_exists`, `roadmap_exists`, `phases`, `phase_count`.

**If `project_exists` is false:**

```
No planning structure found.

Run $gpd-new-project to start a new research project.
```

Exit.

## Step 2: Parse Scope

Determine scope from $ARGUMENTS:

- If a number (e.g., "3", "2.1"): single phase mode
- If "all": full project mode
- If empty or "remaining": remaining phases mode

## Step 3: Run Cost Estimation

```bash
ESTIMATE=$(gpd cost-estimate "$SCOPE")
```

## Step 4: Read Config for Profile

Extract `model_profile` from config to show which tier mapping applies.

## Step 5: Present Report

Format the JSON output into a readable cost report with tables and tier breakdown.
</process>

<success_criteria>

- [ ] Scope correctly parsed (phase/remaining/all)
- [ ] Cost estimate retrieved from gpd CLI
- [ ] Per-phase breakdown shown with token counts
- [ ] Agent type distribution displayed
- [ ] Cost shown for all three tiers with active profile highlighted
- [ ] Typical ranges noted for unplanned phases
- [ ] Clear, formatted ASCII report
- [ ] Mention `gpd cost-track` for logging actual usage and `gpd cost-report` for comparing estimated vs actual
      </success_criteria>

<purpose>
Execute a systematic parameter sweep over one or two parameters, computing a specified quantity at each point (or grid point) in the parameter space. Leverages wave-based parallel execution from execute-phase.md to evaluate independent parameter values concurrently, then aggregates results into structured data and a summary report.

Called from gpd:parameter-sweep command. References wave-based execution patterns from execute-phase.md.
</purpose>

<core_principle>
A parameter sweep is the physicist's workhorse for mapping out how a system responds across a regime. Each parameter value is an independent computation -- perfect for parallel execution. The sweep produces a data table, not just a single number, and the table itself is the deliverable: it reveals phase transitions, crossovers, resonances, and extrema that no single-point calculation can find.

**The contract:** Every sweep point must use identical methodology. The only thing that changes between points is the parameter value. If the computation method must change across the range (e.g., different approximation schemes for different regimes), that is a multi-sweep problem and must be documented explicitly.
</core_principle>

<process>

<step name="initialize" priority="first">
Load current-workspace context with a workspace-locked bootstrap:

```bash
INIT=$(gpd --raw init progress --include state,roadmap,config --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `executor_model`, `verifier_model`, `commit_docs`, `autonomy`, `research_mode`, `parallelization`, `project_exists`, `state_exists`, `roadmap_exists`.

**Mode-aware behavior:**
- `research_mode=explore`: Broad parameter ranges, fine grid resolution, include secondary parameters. Spawn experiment-designer agent to validate sweep design.
- `research_mode=exploit`: Tight ranges around known values, coarse grid, primary parameters only.
- `research_mode=adaptive`: Start with coarse grid, refine adaptively around interesting regions.
- `autonomy=supervised` (default): Show the sweep design and ask for approval before generating plans.
- `autonomy=balanced`: Execute automatically unless the design exceeds context budget, has more than 100 grid points, or changes scope materially; only then pause for user approval.
- `autonomy=yolo`: Execute the sweep without pausing.

Run centralized command-context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context parameter-sweep "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

If `state_exists` is true, read `STATE.md` for project conventions, unit system, and active approximations. If `state_exists` is false, proceed in standalone/current-workspace mode with one explicit computation anchor plus explicit `--param` and `--range` inputs supplied by the user. Standalone/current-workspace runs still keep all GPD-authored outputs under `GPD/sweeps/` rooted at the invoking workspace.

**Convention verification** (if project exists):

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — parameter ranges may use inconsistent units"
  echo "$CONV_CHECK"
fi
```

Resolve authoritative phase context only after the target computation anchor is known. If the resolved target is a current-workspace phase number, run:

```bash
PHASE_INIT=$(gpd --raw init phase-op --include state,config "{phase_number}")
if [ $? -ne 0 ]; then
  echo "ERROR: phase initialization failed: $PHASE_INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Use that follow-up phase init only when the phase number is authoritative for this run. If the user supplied a bare phase number but no initialized current-workspace project owns it, stop and require a computation anchor instead of inventing `phase_dir` or `phase_slug`.
When `PHASE_INIT` succeeds, parse `phase_found`, `phase_dir`, `phase_number`, and `phase_slug` from that payload and use them as the only authority for phase-backed writes.

If no authoritative phase is resolved, keep `phase_found=false`, stay in current-workspace mode, and do not invent `GPD/phases/XX-sweep`.
</step>

<step name="define_sweep_parameters">
Parse command arguments for sweep definition. If arguments are incomplete, prompt the user interactively.

**Required information:**

| Field                | Source                            | Example                                     |
| -------------------- | --------------------------------- | ------------------------------------------- |
| Parameter name(s)    | `--param` flag or user prompt     | `temperature`, `coupling_constant`          |
| Range                | `--range` flag or user prompt     | `0.1:10.0:20` (start:end:steps)             |
| Observable           | User prompt                       | "ground state energy", "correlation length" |
| Computation anchor   | Existing phase plan, file path, notebook/script, or explicit description | `3`, `scripts/self_energy.py`, `mesh-study.ipynb`, or inline description |
| Scale                | Linear or logarithmic             | `--log` for logarithmic spacing             |

**1D sweep:**

```
--param temperature --range 0.1:10.0:20
```

Generates 20 values of temperature from 0.1 to 10.0 (linearly spaced by default, logarithmically if `--log`).

**2D sweep:**

```
--param temperature --range 0.1:10.0:10 --param coupling --range 0.01:1.0:10
```

Generates a 10x10 grid (100 points total). Each (temperature, coupling) pair is an independent computation.

**Parameter generation:**

```python
import numpy as np

if scale == "log":
    values = np.logspace(np.log10(start), np.log10(end), steps)
else:
    values = np.linspace(start, end, steps)

# For 2D: cartesian product
if param_2:
    grid = [(v1, v2) for v1 in values_1 for v2 in values_2]
```

**Display sweep plan:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PARAMETER SWEEP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Parameter: {name}
Range: {start} to {end} ({steps} points, {linear|logarithmic})
Observable: {quantity to compute}
Total computations: {N}
Adaptive refinement: {enabled|disabled}

{For 2D:}
Parameter 1: {name1} -- {start1} to {end1} ({steps1} points)
Parameter 2: {name2} -- {start2} to {end2} ({steps2} points)
Grid: {steps1} x {steps2} = {total} points
```

If `autonomy=supervised`, show this plan and ask for confirmation before generating plans. Otherwise continue automatically unless the balanced-mode pause conditions are met.

Derive a durable artifact location for the sweep outputs:

```bash
SWEEP_SLUG="{slug derived from parameter names and observable}"
if [ "${phase_found}" = "true" ]; then
  SWEEP_PHASE_DIR="${phase_dir}"
  SWEEP_PHASE_KEY="${phase_number}-${phase_slug}"
  SWEEP_DOC_DIR="${SWEEP_PHASE_DIR}"
  SWEEP_ROOT="GPD/sweeps/${SWEEP_PHASE_KEY}/${SWEEP_SLUG}"
else
  SWEEP_PHASE_DIR=""
  SWEEP_PHASE_KEY=""
  SWEEP_DOC_DIR="GPD/sweeps/${SWEEP_SLUG}"
  SWEEP_ROOT="GPD/sweeps/${SWEEP_SLUG}"
fi
SWEEP_RESULTS_DIR="${SWEEP_ROOT}/results"
mkdir -p "${SWEEP_DOC_DIR}" "${SWEEP_RESULTS_DIR}"
```

Keep all GPD-authored sweep artifacts under `GPD/sweeps/`. For authoritative phase-backed runs, internal plan and SUMMARY docs may still live under `${SWEEP_PHASE_DIR}` while durable machine-readable outputs live under `${SWEEP_ROOT}`. For standalone/current-workspace runs, keep both docs and datasets under the same `${SWEEP_ROOT}` tree. Do not invent `GPD/phases/XX-sweep`. Do not write durable sweep datasets to `artifacts/`.
</step>

<step name="generate_sweep_plans">
For each parameter value (or combination in 2D), create a plan from the computation template. Each plan is a self-contained unit that:

1. Sets the parameter to its specific value
2. Executes the computation identically to all other plans
3. Records the result in a structured format

**Plan generation:**

For each sweep point `i` with parameter value `p_i`:

Write `${SWEEP_DOC_DIR}/sweep-{PADDED_INDEX}-PLAN.md`:

```markdown
---
wave: {wave_number}
interactive: false
depends_on: []
sweep_index: {i}
sweep_param: {param_name}
sweep_value: {p_i}
{For 2D:}
sweep_param_2: {param_name_2}
sweep_value_2: {p_i_2}
files_modified:
  - ${SWEEP_DOC_DIR}/sweep-{PADDED_INDEX}-SUMMARY.md
  - ${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json
contract:
  schema_version: 1
  scope:
    question: "What does {observable} evaluate to at {param_name}={p_i}?"
  context_intake:
    must_read_refs: [ref-sweep-anchor]
    must_include_prior_outputs: ["Phase-level sweep baseline"]
    user_asserted_anchors: ["The observable stays within the approved regime"]
  claims:
    - id: claim-sweep-point
      statement: "{observable} computed at {param_name}={p_i}"
      deliverables: [deliv-sweep-point]
      acceptance_tests: [test-sweep-point]
      references: [ref-sweep-anchor]
  deliverables:
    - id: deliv-sweep-point
      kind: dataset
      path: ${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json
      description: "Recorded sweep result for this parameter point"
      must_contain: ["{observable}", "{param_name}", "status"]
  references:
    - id: ref-sweep-anchor
      kind: other
      locator: "{approved sweep observable or baseline anchor}"
      role: must_consider
      why_it_matters: "Keeps the sweep point tied to the approved observable, regime, and comparison path."
      applies_to: [claim-sweep-point]
      must_surface: true
      required_actions: [compare]
  acceptance_tests:
    - id: test-sweep-point
      subject: claim-sweep-point
      kind: existence
      procedure: "Check that the result file contains the configured parameter values, computed observable, and status."
      pass_condition: "Result file exists, encodes the requested point, and records {observable} for downstream comparison."
      evidence_required: [deliv-sweep-point, ref-sweep-anchor]
  forbidden_proxies:
    - id: fp-sweep-point
      subject: claim-sweep-point
      proxy: "Recording a number without regime checks or parameter metadata."
      reason: "Would allow false progress by logging an uninterpretable sweep point."
  uncertainty_markers:
    weakest_anchors: ["Numerical stability at this sweep point"]
    disconfirming_observations: ["The observable falls outside the valid regime or fails the comparison anchor"]
---

<objective>
Compute {observable} at {param_name} = {p_i}.
{For 2D: and {param_name_2} = {p_i_2}.}
</objective>

<task id="1" name="set_parameters">
Set {param_name} = {p_i} in the computation context.
{For 2D: Set {param_name_2} = {p_i_2}.}
Verify parameter is within the valid regime for the computation method.
</task>

<task id="2" name="compute">
{Computation template -- identical across all sweep points.}
Record the computed value of {observable} with uncertainty if available.
</task>

<task id="3" name="record_result">
Write results to `${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json`:

{
"sweep_index": {i},
"{param_name}": {p_i},
{For 2D: "{param_name_2}": {p_i_2},}
"{observable}": {computed_value},
"uncertainty": {uncertainty_or_null},
"status": "completed",
"notes": "{any anomalies or warnings}"
}

Create SUMMARY.md with the standard template.
</task>
```

**Wave assignment:**

All sweep plans are independent (no dependencies), so they go in the same wave. However, if there are more than 10 parameter points, batch them into waves of 5-8 plans each to manage resource usage:

```python
WAVE_SIZE = 8  # max plans per wave (tunable based on computation cost)
n_waves = ceil(total_points / WAVE_SIZE)

for i, point in enumerate(sweep_points):
    wave = (i // WAVE_SIZE) + 1
    # assign wave number to plan frontmatter
```

**Display plan summary:**

```
Generated {N} sweep plans across {M} wave(s):

| Wave | Plans | Parameter Range |
|------|-------|-----------------|
| 1 | sweep-001 to sweep-008 | {param} = {start} to {val_8} |
| 2 | sweep-009 to sweep-016 | {param} = {val_9} to {val_16} |
| ... | ... | ... |
```

</step>

<step name="execute_sweep">
Execute the sweep plans using wave-based parallel execution following the execute-phase.md pattern.

**For each wave:**

1. **Create wave checkpoint:**

   ```bash
   if [ "${phase_found}" = "true" ]; then
     WAVE_CHECKPOINT="gpd-checkpoint-sweep-${phase_number}-wave-${WAVE_NUM}-$(date +%s)"
     if git rev-parse --verify "refs/tags/${WAVE_CHECKPOINT}" >/dev/null 2>&1; then
       WAVE_CHECKPOINT="${WAVE_CHECKPOINT}-$$"
     fi
     if ! git tag "${WAVE_CHECKPOINT}"; then
       echo "ERROR: failed to create sweep checkpoint tag ${WAVE_CHECKPOINT}" >&2
       exit 1
     fi
   fi
   ```

2. **Spawn executor agents for all plans in the wave:**

   Follow the same task() spawning pattern as execute-phase.md step `execute_waves`.
   @{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

   ```
   task(
     subagent_type="gpd-executor",
     model="{executor_model}",
     readonly=false,
     prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

       <objective>
       Execute sweep plan {plan_number}: compute {observable} at {param_name} = {p_i}.
       Write result to ${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json.
       Create SUMMARY.md. Return state updates in your response -- do NOT write STATE.md directly.
       </objective>

       <spawn_contract>
       write_scope:
         mode: scoped_write
         allowed_paths:
           - ${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json
           - ${SWEEP_DOC_DIR}/sweep-{PADDED_INDEX}-SUMMARY.md
       expected_artifacts:
         - ${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json
         - ${SWEEP_DOC_DIR}/sweep-{PADDED_INDEX}-SUMMARY.md
       shared_state_policy: return_only
       </spawn_contract>

       <context_hint>code-heavy</context_hint>
       <phase_class>numerical</phase_class>

       <files_to_read>
       Read these files at execution start using the file_read tool:
       - Workflow: {GPD_INSTALL_DIR}/workflows/execute-plan.md
       - Summary template: {GPD_INSTALL_DIR}/templates/summary.md
       - Plan: ${SWEEP_DOC_DIR}/sweep-{PADDED_INDEX}-PLAN.md
       - State: GPD/STATE.md (only when `state_exists: true`)
       - Config: GPD/config.json (if exists)
       </files_to_read>

       <success_criteria>
       - [ ] Parameter set to specified value
       - [ ] Computation executed with identical methodology to other sweep points
       - [ ] Result written to ${SWEEP_RESULTS_DIR}/point-{PADDED_INDEX}.json
       - [ ] Uncertainty estimated if applicable
       - [ ] SUMMARY.md created
       - [ ] State updates returned (NOT written to STATE.md directly) only when authoritative phase-backed persistence is actually in scope
       </success_criteria>
     "
   )
   ```

3. **Wait for all agents in wave to complete.**

   **If any executor agent fails to spawn or returns an error:** Record the sweep point as failed (null result) in `${SWEEP_RESULTS_DIR}/point-{INDEX}.json` with `"status": "agent_failed"`. Continue with remaining points in the wave. Report failed points in the wave summary. Do not abort the entire sweep for individual point failures.

4. **Spot-check results:**

   For each completed plan:

   - Verify `${SWEEP_RESULTS_DIR}/point-{INDEX}.json` exists and contains valid JSON
   - Check `status` field is `"completed"`
   - Verify the observable value is a finite number (not NaN, not Inf)
   - Check `${SWEEP_DOC_DIR}/sweep-{INDEX}-SUMMARY.md` exists

   If any spot-check fails, follow the `wave_failure_handling` pattern from execute-phase.md.

5. **Report wave completion:**

   ```
   Wave {N} complete: {count} sweep points computed
   Range: {param} = {first_value} to {last_value}
   Results: {count_succeeded} succeeded, {count_failed} failed
   ```

6. **Proceed to next wave.**
   </step>

<step name="collect_results">
After all waves complete, aggregate results from individual JSON files into a unified data table.

**1. Read all result files:**

```bash
ls "${SWEEP_RESULTS_DIR}/point-*.json" | sort -V
```

For each file, parse the JSON and extract: parameter value(s), observable, uncertainty, status.

**2. Build data table:**

```python
results = []
for point_file in sorted(glob(f"{SWEEP_RESULTS_DIR}/point-*.json")):
    with open(point_file) as f:
        data = json.load(f)
    if data["status"] == "completed":
        results.append(data)
    else:
        # Record failed points with null result
        results.append({**data, observable: None})
```

**3. Save aggregated results:**

Write `${SWEEP_ROOT}/sweep-results.json`:

```json
{
  "metadata": {
    "param_name": "{name}",
    "param_range": [start, end],
    "param_steps": N,
    "param_scale": "linear|logarithmic",
    "observable": "{quantity}",
    "total_points": N,
    "completed_points": M,
    "failed_points": K,
    "timestamp": "YYYY-MM-DDTHH:MM:SSZ"
  },
  "data": [
    {
      "index": 0,
      "{param_name}": value,
      "{observable}": result,
      "uncertainty": error_or_null
    },
    ...
  ]
}
```

For 2D sweeps, include both parameter names and values in each data entry, plus:

```json
{
  "metadata": {
    "param_1_name": "{name1}",
    "param_1_range": [start1, end1],
    "param_1_steps": N1,
    "param_2_name": "{name2}",
    "param_2_range": [start2, end2],
    "param_2_steps": N2,
    "grid_size": [N1, N2],
    ...
  }
}
```

**4. Generate markdown summary table:**

Write `${SWEEP_DOC_DIR}/SWEEP-SUMMARY.md`:

```markdown
---
param: {name}
range: [{start}, {end}]
steps: {N}
observable: {quantity}
completed: {M}/{N}
status: completed | checkpoint | failed
---

# Parameter Sweep: {observable} vs {param_name}

## Sweep Configuration

| Property   | Value                  |
| ---------- | ---------------------- |
| Parameter  | {name}                 |
| Range      | {start} to {end}       |
| Points     | {N}                    |
| Scale      | {linear / logarithmic} |
| Observable | {quantity}             |
| Completed  | {M}/{N}                |

## Results

| {param_name} | {observable} | uncertainty |
| ------------ | ------------ | ----------- |
| {val_1}      | {result_1}   | {err_1}     |
| {val_2}      | {result_2}   | {err_2}     |
| ...          | ...          | ...         |

{For 2D sweeps, format as a matrix if feasible, otherwise as a flat table with both parameter columns.}

## Identified Features

{Analyze the data for notable features:}

### Extrema

- **Maximum:** {observable} = {value} at {param} = {location} +/- {uncertainty}
- **Minimum:** {observable} = {value} at {param} = {location} +/- {uncertainty}

### Transitions / Crossovers

{Identify regions where the observable changes rapidly:}

- **Rapid change near {param} = {value}:** {observable} changes by {amount} over {delta_param}
  Possible: {phase transition | resonance | crossover | divergence}

### Monotonicity

- {Monotonically increasing | decreasing | non-monotonic} over the full range
- {If non-monotonic: location and nature of turning points}

### Asymptotic Behavior

- **{param} -> {start}:** {observable} ~ {limiting form}
- **{param} -> {end}:** {observable} ~ {limiting form}

## Data Files

- `${SWEEP_ROOT}/sweep-results.json` -- structured data (all points)
- `${SWEEP_RESULTS_DIR}/point-NNN.json` -- individual point results
```

</step>

<step name="adaptive_refinement">
**Only if `--adaptive` flag is set.** Skip this step otherwise.

Analyze the collected results to identify regions needing finer sampling, then generate and execute additional sweep points.

**1. Compute numerical derivatives:**

```python
import numpy as np

params = np.array([d[param_name] for d in results])
values = np.array([d[observable] for d in results])

# First derivative (central differences)
dydx = np.gradient(values, params)

# Second derivative
d2ydx2 = np.gradient(dydx, params)

# Relative rate of change
rel_change = np.abs(dydx) / (np.abs(values) + epsilon)
```

**2. Identify refinement regions:**

A region needs refinement if any of:

| Criterion               | Threshold                              | Physics interpretation                         |
| ----------------------- | -------------------------------------- | ---------------------------------------------- |
| Large first derivative  | \|dy/dx\| > 3 \* median(\|dy/dx\|)     | Rapid change -- possible transition            |
| Large second derivative | \|d2y/dx2\| > 3 \* median(\|d2y/dx2\|) | Curvature -- possible extremum or inflection   |
| Non-monotonic segment   | Sign change in dy/dx                   | Turning point -- needs precise location        |
| Large gap in results    | Failed point between successful ones   | Missing data in potentially interesting region |

**3. Generate refined parameter values:**

For each identified region:

```python
# Add points between existing values in the region
idx_start, idx_end = region_bounds
local_params = params[idx_start:idx_end+1]
refined = np.linspace(local_params[0], local_params[-1], 2 * len(local_params) - 1)
new_points = [p for p in refined if p not in params]
```

**4. Display refinement plan:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > ADAPTIVE REFINEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Identified {K} regions needing finer sampling:

| Region | {param_name} range | Reason | New points |
|--------|-------------------|--------|------------|
| 1 | {a} to {b} | {rapid change / extremum / ...} | {N1} |
| 2 | {c} to {d} | {reason} | {N2} |

Total additional points: {sum}

Refine {K} regions ({sum} additional points)? [Y/n/e]  (Enter = Y; e opens freeform to tune the region selection)
```

**Edit branch:** If the user chooses `e`, collect revised region-selection or grid-size instructions, update the refinement table and total point count, and re-present the updated `[Y/n/e]` prompt once before generating refinement plans. Do not treat the edit text itself as approval.

**5. Generate and execute refinement plans:**

Follow the same plan generation and execution pattern from `generate_sweep_plans` and `execute_sweep`. Assign refinement plans to new wave numbers continuing from the last wave.

**6. Merge refined results:**

```python
# Load original results
with open(f"{SWEEP_ROOT}/sweep-results.json") as f:
    original = json.load(f)

# Load refinement results
for point_file in refinement_files:
    with open(point_file) as f:
        new_data = json.load(f)
    original["data"].append(new_data)

# Sort by parameter value
original["data"].sort(key=lambda d: d[param_name])

# Update metadata
original["metadata"]["total_points"] = len(original["data"])
original["metadata"]["completed_points"] = sum(1 for d in original["data"] if d.get("status") == "completed")
original["metadata"]["adaptive_refinement"] = True
original["metadata"]["refinement_regions"] = K
original["metadata"]["refinement_points_added"] = sum_new_points
```

Write updated `${SWEEP_ROOT}/sweep-results.json` and regenerate `${SWEEP_DOC_DIR}/SWEEP-SUMMARY.md` with the merged data. Mark refined regions in the summary table:

```markdown
| {param_name}  | {observable} | uncertainty | note      |
| ------------- | ------------ | ----------- | --------- |
| {val}         | {result}     | {err}       |           |
| {val_refined} | {result}     | {err}       | _refined_ |
```

Re-run feature identification on the merged dataset.
</step>

<step name="commit_and_present">
Apply project state updates and commits only when authoritative phase-backed persistence is actually in scope.

- If `phase_found` is true and executor plans returned state updates, apply them through the canonical `gpd apply-return-updates` bridge before touching `GPD/STATE.md`.
- If `phase_found` is false, do not mutate `STATE.md` or `state.json`, do not tag a checkpoint, and do not run a standalone docs commit. The workflow stops after writing the `GPD/sweeps/` artifacts.
- Even in phase-backed mode, include `GPD/STATE.md` in commit/pre-commit file lists only when the state-update bridge actually changed it.

**Phase-backed commit example:**

```bash
if [ "${phase_found}" = "true" ] && [ "${commit_docs}" = "true" ]; then
  PRE_CHECK=$(gpd pre-commit-check --files "${SWEEP_ROOT}/sweep-results.json" "${SWEEP_DOC_DIR}/SWEEP-SUMMARY.md" "${SWEEP_RESULTS_DIR}" 2>&1) || true
  echo "$PRE_CHECK"

  gpd commit \
    "data(phase-${phase_number}): parameter sweep - ${OBSERVABLE} vs ${PARAM_NAME}" \
    --files "${SWEEP_ROOT}/sweep-results.json" "${SWEEP_DOC_DIR}/SWEEP-SUMMARY.md" "${SWEEP_RESULTS_DIR}"
fi
```

**Present final results:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PARAMETER SWEEP COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**{observable}** vs **{param_name}**
Range: {start} to {end} ({total_points} points{, including {refined} refined})
Completed: {M}/{N}

### Key Findings

{From SWEEP-SUMMARY.md Identified Features section:}
- {Maximum/minimum location and value}
- {Phase transitions or crossovers}
- {Asymptotic behavior}

### Output Files

- `${SWEEP_ROOT}/sweep-results.json` -- structured data
- `${SWEEP_DOC_DIR}/SWEEP-SUMMARY.md` -- sweep report with tables
- `${SWEEP_RESULTS_DIR}/` -- individual point data

---

## Next Steps

- **Visualize:** Plot the sweep data to inspect features
- **Refine:** `gpd:parameter-sweep {phase} --adaptive` -- add points near interesting features
- **Converge:** `gpd:numerical-convergence {phase}` -- verify convergence at key points
- **Branch:** `gpd:branch-hypothesis` -- investigate features with different methods

---
```

</step>

</process>

<failure_handling>

- **Single sweep point fails:** Record as failed in results (null observable), continue with remaining points. Report in SWEEP-SUMMARY.md under a "Failed Points" section.
- **Entire wave fails:** Follow execute-phase.md wave_failure_handling. Offer: continue (skip failed wave), retry wave, or stop.
- **Computation method breaks in part of range:** This indicates the method has a limited validity regime. Record which points failed and why. Suggest splitting into sub-sweeps with different methods for different regimes.
- **All points return identical values:** Either the parameter does not affect the observable (physically meaningful -- document this), or the parameter is not being set correctly (bug -- investigate).
- **NaN or Inf results:** Flag immediately. Common causes: division by zero at special parameter values, overflow at large parameters, underflow at small parameters. Exclude from feature analysis but report prominently.
- **Non-physical results (negative energies where forbidden, probabilities > 1, etc.):** Flag with physics interpretation. May indicate approximation breakdown at that parameter value.

</failure_handling>

<success_criteria>

- [ ] Sweep parameters defined (name, range, steps, scale)
- [ ] Observable identified and computation template established
- [ ] Plans generated for all parameter points with correct wave assignments
- [ ] Plans executed via wave-based parallelism (batched if >10 points)
- [ ] Individual results collected from each sweep point
- [ ] Results aggregated into sweep-results.json
- [ ] SWEEP-SUMMARY.md generated with data table
- [ ] Features identified (extrema, transitions, crossovers, asymptotic behavior)
- [ ] Adaptive refinement executed if --adaptive (regions identified, refined, merged)
- [ ] Failed points documented with reasons
- [ ] Phase-backed runs apply returned state updates only through the canonical bridge
- [ ] Standalone/current-workspace runs stop after writing GPD-owned sweep artifacts under `GPD/sweeps/`
- [ ] User presented with key findings and next steps

</success_criteria>

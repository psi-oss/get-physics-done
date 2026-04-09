<purpose>

Start a new research milestone cycle for an existing project. Uses staged init to load milestone context, gathers milestone goals from MILESTONE-CONTEXT.md or conversation, updates PROJECT.md and STATE.md, optionally runs a task-local parallel literature survey, defines scoped research objectives with REQ-IDs, and hands off to the roadmapper through a fresh typed continuation with freshness checks. Continuation equivalent of new-project.

</purpose>

<required_reading>

Read all files referenced by the invoking prompt's execution_context before starting.

</required_reading>

<process>

## 1. Bootstrap and Load Context

```bash
INIT=$(gpd --raw init new-milestone --stage milestone_bootstrap)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  exit 1
fi
```

Parse JSON for: `researcher_model`, `synthesizer_model`, `roadmapper_model`, `commit_docs`, `autonomy`, `research_mode`, `research_enabled`, `current_milestone`, `current_milestone_name`, `project_exists`, `roadmap_exists`, `state_exists`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `platform`.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause for user confirmation after requirements gathering and before roadmap generation.
- `autonomy=balanced` (default): Execute the full pipeline automatically and pause only if milestone scope is ambiguous or requirements conflict with prior work.
- `autonomy=yolo`: Execute full pipeline, skip optional research step, auto-approve roadmap, but do NOT skip phase-level contract coverage and anchor visibility.
- `research_mode=explore`: Broader research survey for new milestone, consider alternative approaches, include speculative phases.
- `research_mode=exploit`: Focused research on direct extensions of prior milestone, lean phase structure.
- `research_mode=balanced` (default): Use the standard research depth for the milestone and keep the default anchor and contract coverage unless the milestone needs broader or narrower review.
- `research_mode=adaptive`: Reuse a focused path only when prior milestones already provide decisive evidence or an explicit approach lock. Otherwise refresh broader gap analysis before narrowing the new milestone.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context new-milestone "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Treat `project_contract` as the authoritative machine-readable project contract only when `project_contract_gate.authoritative` is true. Keep `project_contract_load_info` and `project_contract_validation` visible as gate inputs, and treat `project_contract` as visible-but-non-authoritative when the gate is blocked.

Treat init as staged:
- Use this bootstrap init for milestone identity and contract gate state only.
- Run a survey/objectives init before milestone scoping and treat that refresh as the source of truth for carry-forward reference intake, artifact snapshots, and prior-project file context.
- Run a fresh late-stage init immediately before roadmapping and treat that later init as the source of truth for the final handoff.

**If `roadmap_exists` is true:** Note — existing ROADMAP.md will be replaced by this milestone's roadmap.

Load project files:

- Read PROJECT.md (existing project, answered questions, decisions)
- Read MILESTONES.md (if exists — may not exist for first milestone)
- Read STATE.md (if `state_exists` — pending items, blockers)
- Check for MILESTONE-CONTEXT.md (from milestone discussion)
- Keep `project_contract_load_info` and `project_contract_validation` visible while gathering goals, determining milestone version, and reviewing roadmap coverage; do not assume `project_contract` is authoritative unless `project_contract_gate.authoritative` is true.
- If `project_contract_gate.authoritative` is false, checkpoint with the user and repair the stored contract before using it for milestone scope.

Refresh the survey/objectives stage before gathering milestone goals:

```bash
SURVEY_INIT=$(gpd --raw init new-milestone --stage survey_objectives)
if [ $? -ne 0 ]; then
  echo "ERROR: survey/objectives init failed: $SURVEY_INIT"
  exit 1
fi
```

Parse JSON for: `researcher_model`, `synthesizer_model`, `roadmapper_model`, `commit_docs`, `autonomy`, `research_mode`, `research_enabled`, `current_milestone`, `current_milestone_name`, `project_exists`, `roadmap_exists`, `state_exists`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifact_files`, `reference_artifacts_content`, `literature_review_files`, `literature_review_count`, `research_map_reference_files`, `research_map_reference_count`, `derived_convention_lock`, `derived_convention_lock_count`, `derived_intermediate_results`, `derived_intermediate_result_count`, `derived_approximations`, `derived_approximation_count`, `project_content`, `state_content`, `milestones_content`, `platform`.

Treat `active_reference_context` and `effective_reference_intake` from this survey/objectives init as binding carry-forward context even when `project_contract` is empty or blocked.

Before defining scope, inspect these carry-forward inputs and keep them visible through milestone planning:
- `effective_reference_intake.must_read_refs`
- `effective_reference_intake.must_include_prior_outputs`
- `effective_reference_intake.user_asserted_anchors`
- `effective_reference_intake.known_good_baselines`
- `effective_reference_intake.context_gaps`
- `effective_reference_intake.crucial_inputs`
- `contract_intake`

If `reference_artifact_files` is non-empty, read the listed reference artifacts or use `reference_artifacts_content` as a compact fallback.

## 2. Gather Milestone Goals

**If MILESTONE-CONTEXT.md exists:**

- Use research directions and scope from milestone discussion
- Present summary for confirmation

**If no context file:**

- Present what was accomplished in the last milestone
- Ask: "What do you want to investigate next?"
- Use ask_user to explore: new phenomena, extended parameter regimes, additional observables, paper targets, peer review responses

**Research milestones typically focus on one of:**

- **Analytical extension:** Push derivations to new regimes, higher orders, or related systems
- **Numerical validation:** Implement and benchmark against analytical predictions
- **Phenomenological exploration:** Map out parameter space, identify new phases or transitions
- **Paper preparation:** Draft manuscript, prepare figures, write supplementary material
- **Peer review response:** Address referee comments, perform additional calculations

## 3. Determine Milestone Version

- Parse last version from MILESTONES.md
- Suggest next version (v1.0 -> v1.1 for incremental, v2.0 for major new direction)
- Confirm with user

## 4. Update PROJECT.md

Add/update:

```markdown
## Current Milestone: v[X.Y] [Name]

**Goal:** [One sentence describing milestone focus]

**Target results:**

- [Result 1]
- [Result 2]
- [Result 3]
```

Update Active research questions section and "Last updated" footer.

## 5. Update project state

Update STATE.md position fields via gpd (ensures state.json sync):

```bash
gpd state patch \
  "--Status" "Defining objectives" \
  "--Last Activity" "$(date +%Y-%m-%d)"

gpd state add-decision \
  --phase "0" \
  --summary "Started milestone v[X.Y]: [Name]" \
  --rationale "New milestone cycle"
```

Keep Accumulated Context section from previous milestone.

## 6. Cleanup and Commit

Delete MILESTONE-CONTEXT.md if exists (consumed).
Honor `planning.commit_docs` from init internally when deciding whether milestone artifacts are committed.

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/PROJECT.md GPD/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: start milestone v[X.Y] [Name]" --files GPD/PROJECT.md GPD/STATE.md
```

## 7. Literature Survey Decision

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

ask_user: "Survey the research landscape for new investigations before defining objectives?"

- "Survey first (Recommended)" — Discover new results, methods, and open problems for NEW directions
- "Skip survey" — Go straight to objectives

**Persist choice to config** (so future `gpd:plan-phase` honors it):

```bash
# If "Survey first": persist true
gpd config set workflow.research true

# If "Skip survey": persist false
gpd config set workflow.research false
```

**If "Survey first":**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> SURVEYING RESEARCH LANDSCAPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>>> Spawning 4 literature scouts in parallel...
  -> Known Results, Methods, Framework, Pitfalls
```

```bash
mkdir -p GPD/literature
```

Spawn 4 parallel gpd-project-researcher agents. Each uses this template with dimension-specific fields:
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

**Common structure for all 4 scouts:**

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>Literature Survey — {DIMENSION} for [new research direction].</research_type>

<milestone_context>
SUBSEQUENT MILESTONE — Extending research in [new direction] building on existing results.
{EXISTING_CONTEXT}
Focus ONLY on what's needed for the NEW research questions.
</milestone_context>

<question>{QUESTION}</question>

<project_context>[PROJECT.md summary]</project_context>

<downstream_consumer>{CONSUMER}</downstream_consumer>

<quality_gate>{GATES}</quality_gate>

<output>
Write to: GPD/literature/{FILE}
Use template: {GPD_INSTALL_DIR}/templates/research-project/{FILE}
</output>

<return_contract>
This is a one-shot handoff. Return a typed `gpd_return` envelope with `status` and `files_written`.
Route on `gpd_return.status` and `gpd_return.files_written`, not on the human-readable handoff text.
If you need user input, return `status: checkpoint` and stop; do not wait inside the same run.
Treat `GPD/literature/{FILE}` as fresh only when the file exists on disk and the same path appears in `gpd_return.files_written`.
</return_contract>
", subagent_type="gpd-project-researcher", model="{researcher_model}", readonly=false, description="{DIMENSION} survey")
```

Add this contract inside each spawned scout prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/literature/{FILE}
expected_artifacts:
  - GPD/literature/{FILE}
shared_state_policy: return_only
</spawn_contract>
```

Each scout contract is task-local. Do not widen the write scope or reuse a shared survey contract across dimensions.
Treat each scout as a one-shot handoff: if it needs user input, it must return `status: checkpoint` and stop, not wait in place.
Treat `gpd_return.status` and `gpd_return.files_written` as the only freshness signal for a scout result.

**Dimension-specific fields:**

| Field            | Prior Work                                                             | Methods                                                                     | Computational                                                                       | Pitfalls                                                                             |
| ---------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| EXISTING_CONTEXT | Existing validated results (DO NOT re-research): [from PROJECT.md]     | Existing methods (already used): [from PROJECT.md]                          | Existing computational framework: [from PROJECT.md or research map]                 | Focus on pitfalls specific to EXTENDING these results                                |
| QUESTION         | What new results have appeared for [new direction]? What is now known? | What methods are appropriate for [new calculations]?                        | What computational extensions are needed for [new regime]?                          | Common mistakes when extending [existing results] to [new regime]?                   |
| CONSUMER         | Specific results with references, conditions, assumptions              | Methods with computational cost, scaling, known limitations                 | Algorithms, software, integration with existing code, resource estimates            | Warning signs, prevention strategy, which phase should address it                    |
| GATES            | References specific, conditions stated, relevance explained            | Methods specific to this physics domain, cost noted, limitations identified | Algorithms defined with convergence criteria, versions current, dependencies mapped | Pitfalls specific to this extension, numerical issues covered, prevention actionable |
| FILE             | PRIOR-WORK.md                                                          | METHODS.md                                                                  | COMPUTATIONAL.md                                                                    | PITFALLS.md                                                                          |

Before trusting the scout handoff, route on `gpd_return.status` and `gpd_return.files_written`, then re-read the expected output files from disk and count only artifacts that actually exist. Do not trust the runtime handoff status by itself.

**If `gpd_return.status: completed`:** verify that the expected `GPD/literature/{FILE}` path is readable on disk and named in `gpd_return.files_written`. If the same path already existed before this handoff, it only counts as fresh output when it appears in `gpd_return.files_written`.

**If `gpd_return.status: checkpoint`:** present the checkpoint, collect the user's input, and spawn a fresh continuation for the same scout dimension. Do not let the original scout run continue after the checkpoint.

**If `gpd_return.status: blocked`:** surface the blocker, work with the user to resolve it, and spawn a fresh continuation once the blocker is resolved.

**If `gpd_return.status: failed`:** surface the failure details, retry only the missing scout once in the same task-local write scope if the artifact is absent, and stop the survey path if freshness still cannot be proven.

**If any research agent fails to spawn or returns an error:** Verify which required scout artifacts exist (`PRIOR-WORK.md`, `METHODS.md`, `COMPUTATIONAL.md`, `PITFALLS.md`). Retry only the missing scout tasks once with the same task-local write scope. If any required research file is still missing after the retry, STOP this survey path and present the missing artifacts. Do not synthesize from incomplete scout output and do not continue the milestone on partial survey results.

**Artifact gate:** If a scout reports success but its `expected_artifacts` entry (`GPD/literature/{FILE}`) is missing, treat that scout as incomplete. Retry only the missing scout once in the same task-local write scope. If the artifact is still missing, stop the survey path. Do not substitute main-context research for the missing scout and do not continue with a partial survey.

After all 4 complete and required artifacts are present, spawn synthesizer:

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-research-synthesizer.md for your role and instructions.

<task>
Synthesize literature survey outputs into SUMMARY.md.
</task>

<files_to_read>
Read these files using the file_read tool:
- GPD/PROJECT.md
- GPD/state.json
- GPD/config.json
- GPD/MILESTONES.md (if exists, skip if not found)
- GPD/literature/PRIOR-WORK.md
- GPD/literature/METHODS.md
- GPD/literature/COMPUTATIONAL.md
- GPD/literature/PITFALLS.md
- GPD/literature/SUMMARY.md (if re-synthesizing an existing survey)
- Files named in `effective_reference_intake.must_include_prior_outputs` when they exist
- Files named in `reference_artifact_files` when they exist and are relevant to summary coverage
</files_to_read>

<survey_context>
Project content: {project_content}
State content: {state_content}
Milestones content: {milestones_content}
Contract intake: {contract_intake}
Active references: {active_reference_context}
Effective reference intake: {effective_reference_intake}
Reference artifacts: {reference_artifacts_content}
</survey_context>

<output>
Write to: GPD/literature/SUMMARY.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/SUMMARY.md
Do NOT commit — the orchestrator handles commits.
</output>

<return_contract>
This is a one-shot handoff. Return a typed `gpd_return` envelope with `status` and `files_written`.
Route on `gpd_return.status` and `gpd_return.files_written`, not on the human-readable handoff text.
If you need user input, return `status: checkpoint` and stop; do not wait inside the same run.
Treat `GPD/literature/SUMMARY.md` as fresh only when the file exists on disk and the same path appears in `gpd_return.files_written`.
</return_contract>
", subagent_type="gpd-research-synthesizer", model="{synthesizer_model}", readonly=false, description="Synthesize literature survey")
```

Add this contract inside the spawned synthesizer prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/literature/SUMMARY.md
expected_artifacts:
  - GPD/literature/SUMMARY.md
shared_state_policy: return_only
</spawn_contract>
```

This synthesizer contract is task-local. Do not reuse survey write scopes or widen the summary handoff.

**If the synthesizer agent fails to spawn or returns an error:** Retry once if `GPD/literature/SUMMARY.md` is missing. If the summary artifact is still missing after the retry, STOP and surface the blocker. Do not fabricate a fallback summary in the main context, do not infer survey conclusions from partial files, and do not display or commit from a preexisting summary without a fresh `gpd_return.files_written` proof.

**If `gpd_return.status: checkpoint`:** Present the checkpoint, collect the user's input, and spawn a fresh continuation for the synthesizer after the response.

**If `gpd_return.status: blocked`:** Present the blocker, work with the user to resolve it, and spawn a fresh continuation once the blocker is resolved.

**If `gpd_return.status: failed`:** Present the failure details, ask whether to retry the same continuation once or stop, and do not infer success from preexisting files.

**Artifact gate:** If the synthesizer reports `gpd_return.status: completed`, verify that `GPD/literature/SUMMARY.md` is readable and named in `gpd_return.files_written`. If the summary artifact is missing from disk or from `gpd_return.files_written`, treat the handoff as incomplete. Retry the synthesizer once if the summary file is still missing. If it remains missing, stop and review the missing inputs. Do not create SUMMARY.md in the main context from partial scout output or from a stale summary that was not named in the fresh return.

Display key findings from SUMMARY.md:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> LITERATURE SURVEY COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**New results:** [from SUMMARY.md]
**Recommended methods:** [from SUMMARY.md]
**Watch Out For:** [from SUMMARY.md]
```

**Commit literature survey:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/literature/PRIOR-WORK.md GPD/literature/METHODS.md GPD/literature/COMPUTATIONAL.md GPD/literature/PITFALLS.md GPD/literature/SUMMARY.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: complete literature survey" --files GPD/literature/PRIOR-WORK.md GPD/literature/METHODS.md GPD/literature/COMPUTATIONAL.md GPD/literature/PITFALLS.md GPD/literature/SUMMARY.md
```

**If "Skip survey":** Continue to Step 8.

## 8. Define Research Objectives

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> DEFINING RESEARCH REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Read PROJECT.md: core research question, current milestone goals, answered questions (what is established).
Read `active_reference_context` and `effective_reference_intake` before drafting objectives so contract-critical anchors, prior outputs, baselines, and unresolved gaps carry forward explicitly.

**If literature survey exists:** Read METHODS.md and PRIOR-WORK.md, extract available approaches and known results.

Present objectives by category:

```
## [Category 1: e.g., Analytical Extensions]
**Essential:** Objective A, Objective B
**Extended:** Objective C, Objective D
**Literature notes:** [any relevant notes]
```

**If no survey:** Gather objectives through conversation. Ask: "What are the key results you need to establish for [new direction]?" Clarify, probe for related calculations, group into categories.

**Scope each category** via ask_user (multiSelect: true):

- "[Objective 1]" — [brief description]
- "[Objective 2]" — [brief description]
- "None for this milestone" — Defer entire category

Track: Selected -> this milestone. Unselected essential -> future. Unselected extended -> out of scope.

**Identify gaps** via ask_user:

- "No, survey covered it" — Proceed
- "Yes, let me add some" — Capture additions

**Generate REQUIREMENTS.md:**

- Current Objectives grouped by category (checkboxes, REQ-IDs)
- Future Objectives (deferred)
- Out of Scope (explicit exclusions with reasoning)
- Traceability section (empty, filled by roadmap)

**REQ-ID format:** `[CATEGORY]-[NUMBER]` (ANAL-01, NUMR-02). Continue numbering from existing.

**Objective quality criteria:**

Good research objectives are:

- **Specific and testable:** "Compute the spectral gap as a function of coupling g in the range g in [0.1, 10]" (not "Study the spectrum")
- **Result-oriented:** "Derive expression for X" (not "Think about Z")
- **Atomic:** One calculation or result per objective (not "Derive and validate the phase diagram")
- **Independent:** Minimal dependencies on other objectives

Present FULL objectives list for confirmation:

```
## Milestone v[X.Y] Research Objectives

### [Category 1: Analytical Extensions]
- [ ] **ANAL-04**: Extend the perturbative result to next-to-leading order
- [ ] **ANAL-05**: Derive the crossover scaling function near the critical point

### [Category 2: Numerical Validation]
- [ ] **NUMR-03**: Benchmark NLO correction against Monte Carlo at N=32

Does this capture the research program? (yes / adjust)
```

If "adjust": Return to scoping.

**Commit objectives:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: define milestone v[X.Y] objectives" --files GPD/REQUIREMENTS.md
```

## 9. Create Roadmap

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> CREATING RESEARCH ROADMAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>>> Spawning roadmapper...
```

**Starting phase number:** Read MILESTONES.md for last phase number. Continue from there (v1.0 ended at phase 5 -> v1.1 starts at phase 6).

**Roadmap handoff staging:** run a fresh late-stage init immediately before the roadmapper handoff and treat it as the source of truth for roadmap assembly.

```bash
ROADMAPPER_INIT=$(gpd --raw init new-milestone --stage roadmap_authoring)
if [ $? -ne 0 ]; then
  echo "ERROR: roadmap init failed: $ROADMAPPER_INIT"
  exit 1
fi
```

Parse JSON for: `roadmapper_model`, `commit_docs`, `autonomy`, `current_milestone`, `current_milestone_name`, `roadmap_exists`, `state_exists`, `planning_exists`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifact_files`, `reference_artifacts_content`, `literature_review_files`, `literature_review_count`, `requirements_content`, `roadmap_content`, `state_content`, `project_content`, `milestones_content`, `platform`.

Use the bootstrap init for milestone identity and contract gating. Use this late-stage init for the final handoff and do not reuse stale roadmapping inputs from the survey/objective loop.

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-roadmapper.md for your role and instructions.

<files_to_read>
Read these files using the file_read tool before proceeding:
- GPD/PROJECT.md
- GPD/state.json
- GPD/config.json
- GPD/MILESTONES.md (if exists, skip if not found)
- GPD/REQUIREMENTS.md
- GPD/literature/SUMMARY.md (if exists, skip if not found)
- Files named in `effective_reference_intake.must_include_prior_outputs` when they exist
- Files named in `reference_artifact_files` when they exist and are relevant to anchor coverage
</files_to_read>

<milestone_context>
Current milestone: {current_milestone}
Milestone name: {current_milestone_name}
Project content: {project_content}
State content: {state_content}
Milestones content: {milestones_content}
Requirements content: {requirements_content}
Roadmap content: {roadmap_content}
Reference artifacts: {reference_artifacts_content}
</milestone_context>

<contract_context>
Project contract: {project_contract}
Project contract gate: {project_contract_gate}
Project contract validation: {project_contract_validation}
Project contract load info: {project_contract_load_info}
Contract intake: {contract_intake}
Active references: {active_reference_context}
Effective reference intake: {effective_reference_intake}
Reference artifacts: {reference_artifacts_content}
</contract_context>

<continuation_context>
This is a fresh continuation handoff for the current milestone roadmap. Carry forward the approved objectives, requirement traceability, prior survey findings, and any unresolved context gaps. Edit the existing roadmap files in place and return a fresh typed `gpd_return` envelope.
</continuation_context>

<instructions>
Create research roadmap for milestone v[X.Y]:
1. Start phase numbering from [N]
2. Derive phases from THIS MILESTONE's objectives, the approved project contract only when `project_contract_gate.authoritative` is true, and the effective reference intake
3. Map every objective to exactly one phase
4. For each phase, include explicit contract coverage in ROADMAP.md showing decisive contract items, anchor coverage, required prior outputs, and forbidden proxies advanced by that phase
5. Treat `must_read_refs`, `must_include_prior_outputs`, `user_asserted_anchors`, `known_good_baselines`, and `crucial_inputs` as binding milestone context, and surface unresolved `context_gaps`
6. Derive 2-5 success criteria per phase (concrete, verifiable results)
7. Validate 100% objective coverage and surface all contract-critical items touched by this milestone
8. Write files immediately (ROADMAP.md, STATE.md, update REQUIREMENTS.md traceability) while preserving existing `GPD/state.json` fields, especially `project_contract`
9. Return a typed `gpd_return` envelope with `status` and `files_written`; treat existing files as stale unless the same paths appear in `gpd_return.files_written`
10. Do not rely on runtime completion text alone
11. If `gpd_return.status` is `checkpoint`, `blocked`, or `failed`, handle each case separately and do not display or commit until a fresh `SUMMARY.md` proof is available
12. Route freshness on the canonical `gpd_return` envelope, using both `status` and `files_written`

</instructions>
", subagent_type="gpd-roadmapper", model="{roadmapper_model}", readonly=false, description="Create research roadmap")
```

Add this contract inside the spawned roadmapper prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/ROADMAP.md
    - GPD/STATE.md
    - GPD/REQUIREMENTS.md
expected_artifacts:
  - GPD/ROADMAP.md
  - GPD/STATE.md
  - GPD/REQUIREMENTS.md
shared_state_policy: direct
</spawn_contract>
```

This roadmapper contract is task-local. Do not widen the write scope or reuse it outside this handoff.

**Handle return:**

**If the roadmapper agent fails to spawn or returns an error:** Treat the handoff as incomplete. Surface partial writes only as diagnostics. Do not fall back to any preexisting ROADMAP.md, STATE.md, or REQUIREMENTS.md content. Ask the user whether to retry this continuation or stop. If the user retries, spawn a fresh continuation handoff that includes the current objectives, the current milestone context, and any revision notes.

**If `gpd_return.status: checkpoint`:** Present the checkpoint, collect user input, and spawn a fresh roadmapper continuation after the user responds.

**If `gpd_return.status: blocked`:** Present the blocker, work with the user to resolve it, and spawn a fresh continuation once the blocker is resolved.

**If `gpd_return.status: failed`:** Present the failure details, ask whether to retry the same continuation once or stop, and do not infer success from preexisting files.

**Artifact gate:** If the roadmapper reports `gpd_return.status: completed`, verify that `GPD/ROADMAP.md`, `GPD/STATE.md`, and `GPD/REQUIREMENTS.md` are readable and named in `gpd_return.files_written`. If any expected artifact was already present before this handoff, it only counts as fresh output when the same path appears in `gpd_return.files_written`. If any expected artifact is missing from disk or from `gpd_return.files_written`, treat the handoff as incomplete and request a fresh continuation. Do not trust runtime completion text alone.

**One-shot freshness rule:** the only proof of success is a completed typed return naming the updated files. Existing files on disk are stale unless the same paths appear in `gpd_return.files_written` from this run.

**If `gpd_return.status: completed`:** Read ROADMAP.md only after the fresh file proof is satisfied, then present the roadmap inline:

```
## Proposed Research Roadmap

**[N] phases** | **[X] objectives mapped** | Contract coverage surfaced

| # | Phase | Goal | Objectives | Contract Coverage | Success Criteria |
|---|-------|------|------------|-------------------|------------------|
| [N] | [Name] | [Goal] | [REQ-IDs] | [claims / anchors] | [count] |

### Phase Details

**Phase [N]: [Name]**
Goal: [goal]
Objectives: [REQ-IDs]
Contract coverage: [decisive outputs, anchors, forbidden proxies]
Success criteria:
1. [criterion]
2. [criterion]
```

**Ask for approval** via ask_user:

- "Approve" — Commit and continue
- "Adjust phases" — Tell me what to change
- "Review full file" — Show raw ROADMAP.md

**If "Adjust":** Get notes, then respawn the roadmapper with a revision continuation handoff:

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

  ```
  task(prompt="First, read {GPD_AGENTS_DIR}/gpd-roadmapper.md for your role and instructions.

  <continuation>
  This is a continuation of the current roadmap handoff, not a fresh brainstorm.

  User feedback on roadmap:
  [user's notes]

  Current artifact snapshot:
  - GPD/ROADMAP.md
  - GPD/STATE.md
  - GPD/REQUIREMENTS.md

  Read the existing roadmap and requirements before editing.
  Edit files in place.
  Return a fresh typed `gpd_return` envelope with `status` and `files_written`.
  </continuation>
  ", subagent_type="gpd-roadmapper", model="{roadmapper_model}", readonly=false, description="Revise roadmap")
  ```

  **If the revision roadmapper agent fails to spawn or returns an error:** Treat the revision as incomplete. Do not compare old file contents as proof of success. Ask whether to retry the same continuation once or stop. If retrying, use a fresh continuation handoff that includes the current roadmap, requirements, and user notes.

- Present revised roadmap
- Loop until user approves (**maximum 3 revision iterations** - after 3, commit the current version with user's notes recorded as open questions in ROADMAP.md, and note: "Roadmap committed after 3 revision rounds. Further adjustments via `gpd:add-phase` or `gpd:remove-phase`.")

**If "Review full file":** Display raw `cat GPD/ROADMAP.md`, then re-ask.

**Commit roadmap** (after approval or auto mode):

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/ROADMAP.md GPD/STATE.md GPD/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: create milestone v[X.Y] roadmap ([N] phases)" --files GPD/ROADMAP.md GPD/STATE.md GPD/REQUIREMENTS.md
```

## 10. Done

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> MILESTONE INITIALIZED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Milestone v[X.Y]: [Name]**

| Artifact       | Location                    |
|----------------|-----------------------------|
| Project        | `GPD/PROJECT.md`      |
| Literature     | `GPD/literature/`     |
| Objectives     | `GPD/REQUIREMENTS.md`   |
| Roadmap        | `GPD/ROADMAP.md`      |

**[N] phases** | **[X] objectives** | Ready to investigate

## >> Next Up

**Phase [N]: [Phase Name]** — [Goal]
```
</process>

<success_criteria>

- [ ] PROJECT.md updated with Current Milestone section
- [ ] STATE.md reset for new milestone
- [ ] MILESTONE-CONTEXT.md consumed and deleted (if existed)
- [ ] Literature survey completed (if selected) — 4 parallel agents, milestone-aware
- [ ] Objectives gathered and scoped per category
- [ ] REQUIREMENTS.md created with REQ-IDs
- [ ] gpd-roadmapper spawned with staged continuation context
- [ ] Roadmap files written immediately (not draft)
- [ ] User feedback incorporated (if any)
- [ ] ROADMAP.md phases continue from previous milestone
- [ ] All commits made (if planning docs committed)
- [ ] User knows next step: `gpd:discuss-phase [N]`

**Atomic commits:** Each phase commits its artifacts immediately.
</success_criteria>

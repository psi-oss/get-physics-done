<purpose>

Start a new research milestone cycle for an existing project. Loads project context, gathers milestone goals (from MILESTONE-CONTEXT.md or conversation), updates PROJECT.md and STATE.md, optionally runs parallel literature survey, defines scoped research objectives with REQ-IDs, spawns the roadmapper to create phased execution plan, and commits all artifacts. Continuation equivalent of new-project.

</purpose>

<required_reading>

Read all files referenced by the invoking prompt's execution_context before starting.

</required_reading>

<process>

## 1. Initialize and Load Context

```bash
INIT=$(gpd init new-milestone)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  exit 1
fi
```

Parse JSON for: `researcher_model`, `synthesizer_model`, `roadmapper_model`, `commit_docs`, `autonomy`, `research_mode`, `research_enabled`, `current_milestone`, `current_milestone_name`, `project_exists`, `roadmap_exists`, `state_exists`, `project_contract`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifact_files`, `reference_artifacts_content`.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause for user confirmation after requirements gathering and before roadmap generation.
- `autonomy=balanced` (default): Execute the full pipeline automatically and pause only if milestone scope is ambiguous or requirements conflict with prior work.
- `autonomy=yolo`: Execute full pipeline, skip optional research step, auto-approve roadmap, but do NOT skip phase-level contract coverage and anchor visibility.
- `research_mode=explore`: Broader research survey for new milestone, consider alternative approaches, include speculative phases.
- `research_mode=exploit`: Focused research on direct extensions of prior milestone, lean phase structure.
- `research_mode=adaptive`: Reuse a focused path only when prior milestones already provide decisive evidence or an explicit approach lock. Otherwise refresh broader gap analysis before narrowing the new milestone.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context new-milestone "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Treat `project_contract` as the authoritative machine-readable project contract when present. Treat `active_reference_context` and `effective_reference_intake` as binding carry-forward context even when `project_contract` is empty.

Before defining scope, inspect these carry-forward inputs and keep them visible through milestone planning:
- `effective_reference_intake.must_read_refs`
- `effective_reference_intake.must_include_prior_outputs`
- `effective_reference_intake.user_asserted_anchors`
- `effective_reference_intake.known_good_baselines`
- `effective_reference_intake.context_gaps`
- `effective_reference_intake.crucial_inputs`

**If `roadmap_exists` is true:** Note — existing ROADMAP.md will be replaced by this milestone's roadmap.

Load project files:

- Read PROJECT.md (existing project, answered questions, decisions)
- Read MILESTONES.md (if exists — may not exist for first milestone)
- Read STATE.md (if `state_exists` — pending items, blockers)
- Check for MILESTONE-CONTEXT.md (from milestone discussion)
- If `reference_artifact_files` is non-empty, read the listed reference artifacts or use `reference_artifacts_content` as a compact fallback
- Keep `active_reference_context` available while gathering goals, defining objectives, and reviewing roadmap coverage

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

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/PROJECT.md .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: start milestone v[X.Y] [Name]" --files .gpd/PROJECT.md .gpd/STATE.md
```

## 7. Literature Survey Decision

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

ask_user: "Survey the research landscape for new investigations before defining objectives?"

- "Survey first (Recommended)" — Discover new results, methods, and open problems for NEW directions
- "Skip survey" — Go straight to objectives

**Persist choice to config** (so future `/gpd:plan-phase` honors it):

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
mkdir -p .gpd/research
```

Spawn 4 parallel gpd-project-researcher agents. Each uses this template with dimension-specific fields:
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

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
Write to: .gpd/research/{FILE}
Use template: {GPD_INSTALL_DIR}/templates/research-project/{FILE}
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", readonly=false, description="{DIMENSION} survey")
```

Add this contract inside each spawned scout prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - .gpd/research/{FILE}
expected_artifacts:
  - .gpd/research/{FILE}
shared_state_policy: return_only
</spawn_contract>
```

**Dimension-specific fields:**

| Field            | Prior Work                                                             | Methods                                                                     | Computational                                                                       | Pitfalls                                                                             |
| ---------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| EXISTING_CONTEXT | Existing validated results (DO NOT re-research): [from PROJECT.md]     | Existing methods (already used): [from PROJECT.md]                          | Existing computational framework: [from PROJECT.md or research map]                 | Focus on pitfalls specific to EXTENDING these results                                |
| QUESTION         | What new results have appeared for [new direction]? What is now known? | What methods are appropriate for [new calculations]?                        | What computational extensions are needed for [new regime]?                          | Common mistakes when extending [existing results] to [new regime]?                   |
| CONSUMER         | Specific results with references, conditions, assumptions              | Methods with computational cost, scaling, known limitations                 | Algorithms, software, integration with existing code, resource estimates            | Warning signs, prevention strategy, which phase should address it                    |
| GATES            | References specific, conditions stated, relevance explained            | Methods specific to this physics domain, cost noted, limitations identified | Algorithms defined with convergence criteria, versions current, dependencies mapped | Pitfalls specific to this extension, numerical issues covered, prevention actionable |
| FILE             | PRIOR-WORK.md                                                          | METHODS.md                                                                  | COMPUTATIONAL.md                                                                    | PITFALLS.md                                                                          |

Before trusting the scout handoff, re-read the expected output files from disk and count only artifacts that actually exist. Do not trust the runtime handoff status by itself.

**If any research agent fails to spawn or returns an error:** Check which output files were created. For each missing file, note the gap and continue with available outputs. If 3+ agents failed, offer: 1) Retry all agents, 2) Skip literature survey entirely (user selects "Skip survey"), 3) Stop. If 1-2 agents failed, proceed with the synthesizer using available files.

**Artifact gate:** If a scout reports success but its `expected_artifacts` entry (`.gpd/research/{FILE}`) is missing, treat that scout as incomplete. Offer: 1) Retry the missing scout in the same write scope, 2) Execute that scout's research in the main context, 3) Continue without that artifact only if the remaining survey still answers the milestone decision.

After all 4 complete (or partial completion handled), spawn synthesizer:

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-research-synthesizer.md for your role and instructions.

<task>
Synthesize literature survey outputs into SUMMARY.md.
</task>

<files_to_read>
Read these files using the file_read tool:
- .gpd/research/PRIOR-WORK.md
- .gpd/research/METHODS.md
- .gpd/research/COMPUTATIONAL.md
- .gpd/research/PITFALLS.md
</files_to_read>

<output>
Write to: .gpd/research/SUMMARY.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/SUMMARY.md
Do NOT commit — the orchestrator handles commits.
</output>
", subagent_type="gpd-research-synthesizer", model="{synthesizer_model}", readonly=false, description="Synthesize literature survey")
```

Add this contract inside the spawned synthesizer prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - .gpd/research/SUMMARY.md
expected_artifacts:
  - .gpd/research/SUMMARY.md
shared_state_policy: return_only
</spawn_contract>
```

**If the synthesizer agent fails to spawn or returns an error:** Check if individual research files exist. If they do, create a minimal SUMMARY.md in the main context by extracting key findings from each file. Proceed with available research.

**Artifact gate:** If the synthesizer reports success but `.gpd/research/SUMMARY.md` is missing, treat the handoff as incomplete. Offer: 1) Retry synthesizer, 2) Create SUMMARY.md in the main context from the scout artifacts, 3) Stop and review the missing inputs.

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
PRE_CHECK=$(gpd pre-commit-check --files .gpd/research/PRIOR-WORK.md .gpd/research/METHODS.md .gpd/research/COMPUTATIONAL.md .gpd/research/PITFALLS.md .gpd/research/SUMMARY.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: complete literature survey" --files .gpd/research/PRIOR-WORK.md .gpd/research/METHODS.md .gpd/research/COMPUTATIONAL.md .gpd/research/PITFALLS.md .gpd/research/SUMMARY.md
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
PRE_CHECK=$(gpd pre-commit-check --files .gpd/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: define milestone v[X.Y] objectives" --files .gpd/REQUIREMENTS.md
```

## 9. Create Roadmap

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> CREATING RESEARCH ROADMAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>>> Spawning roadmapper...
```

**Starting phase number:** Read MILESTONES.md for last phase number. Continue from there (v1.0 ended at phase 5 -> v1.1 starts at phase 6).

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-roadmapper.md for your role and instructions.

<files_to_read>
Read these files using the file_read tool before proceeding:
- .gpd/PROJECT.md
- .gpd/state.json
- .gpd/REQUIREMENTS.md
- .gpd/research/SUMMARY.md (if exists, skip if not found)
- .gpd/config.json
- .gpd/MILESTONES.md (if exists, skip if not found)
- Files named in `effective_reference_intake.must_include_prior_outputs` when they exist
- Files named in `reference_artifact_files` when they exist and are relevant to anchor coverage
</files_to_read>

<contract_context>
Project contract: {project_contract}
Contract intake: {contract_intake}
Active references: {active_reference_context}
Effective reference intake: {effective_reference_intake}
Reference artifacts: {reference_artifacts_content}
</contract_context>

<instructions>
Create research roadmap for milestone v[X.Y]:
1. Start phase numbering from [N]
2. Derive phases from THIS MILESTONE's objectives, the approved project contract, and the effective reference intake
3. Map every objective to exactly one phase
4. For each phase, include explicit contract coverage in ROADMAP.md showing decisive contract items, anchor coverage, required prior outputs, and forbidden proxies advanced by that phase
5. Treat `must_read_refs`, `must_include_prior_outputs`, `user_asserted_anchors`, `known_good_baselines`, and `crucial_inputs` as binding milestone context, and surface unresolved `context_gaps`
6. Derive 2-5 success criteria per phase (concrete, verifiable results)
7. Validate 100% objective coverage and surface all contract-critical items touched by this milestone
8. Write files immediately (ROADMAP.md, STATE.md, update REQUIREMENTS.md traceability) while preserving existing `.gpd/state.json` fields, especially `project_contract`
9. Return ROADMAP CREATED with summary

Write files first, then return.
</instructions>
", subagent_type="gpd-roadmapper", model="{roadmapper_model}", readonly=false, description="Create research roadmap")
```

Add this contract inside the spawned roadmapper prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - .gpd/ROADMAP.md
    - .gpd/STATE.md
    - .gpd/REQUIREMENTS.md
expected_artifacts:
  - .gpd/ROADMAP.md
  - .gpd/STATE.md
shared_state_policy: return_only
</spawn_contract>
```

**Handle return:**

**If the roadmapper agent fails to spawn or returns an error:** Check if ROADMAP.md was partially written. If it exists and has phases, offer to proceed with it. If no ROADMAP.md, offer: 1) Retry the roadmapper, 2) Create ROADMAP.md in the main context using PROJECT.md and REQUIREMENTS.md.

**Artifact gate:** If the roadmapper reports `## ROADMAP CREATED` but `.gpd/ROADMAP.md` or `.gpd/STATE.md` is missing, treat the handoff as incomplete. Do not trust the runtime handoff status by itself. Offer: 1) Retry the roadmapper, 2) Create the missing artifacts in the main context, 3) Abort and inspect the partial write.

**If `## ROADMAP BLOCKED`:** Present blocker, work with user, re-spawn.

**If `## ROADMAP CREATED`:** Read ROADMAP.md, present inline:

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

**If "Adjust":** Get notes, re-spawn roadmapper with revision context, loop until approved.
**If "Review":** Display raw ROADMAP.md, re-ask.

**Commit roadmap** (after approval):

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: create milestone v[X.Y] roadmap ([N] phases)" --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/REQUIREMENTS.md
```

## 10. Done

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> MILESTONE INITIALIZED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Milestone v[X.Y]: [Name]**

| Artifact       | Location                    |
|----------------|-----------------------------|
| Project        | `.gpd/PROJECT.md`      |
| Literature     | `.gpd/research/`       |
| Objectives     | `.gpd/REQUIREMENTS.md`   |
| Roadmap        | `.gpd/ROADMAP.md`      |

**[N] phases** | **[X] objectives** | Ready to investigate

## >> Next Up

**Phase [N]: [Phase Name]** — [Goal]

`/gpd:discuss-phase [N]` — gather context and clarify approach

<sub>`/clear` first -> fresh context window</sub>

Also: `/gpd:plan-phase [N]` — skip discussion, plan directly
```

</process>

<success_criteria>

- [ ] PROJECT.md updated with Current Milestone section
- [ ] STATE.md reset for new milestone
- [ ] MILESTONE-CONTEXT.md consumed and deleted (if existed)
- [ ] Literature survey completed (if selected) — 4 parallel agents, milestone-aware
- [ ] Objectives gathered and scoped per category
- [ ] REQUIREMENTS.md created with REQ-IDs
- [ ] gpd-roadmapper spawned with phase numbering context
- [ ] Roadmap files written immediately (not draft)
- [ ] User feedback incorporated (if any)
- [ ] ROADMAP.md phases continue from previous milestone
- [ ] All commits made (if planning docs committed)
- [ ] User knows next step: `/gpd:discuss-phase [N]`

**Atomic commits:** Each phase commits its artifacts immediately.
</success_criteria>

<purpose>
Initialize a new physics research project through unified flow: questioning, literature survey (optional), mathematical framework, computational setup, target venue identification. This is the most leveraged moment in any research project — deep questioning here means better formulations, better methods, better results. One workflow takes you from research idea to ready-for-investigation.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<auto_mode>

## Auto Mode Detection

Check if `--auto` flag is present in $ARGUMENTS.

**If auto mode:**

- Auto mode compresses intake; it does not override autonomy review gates after the scoping contract is approved
- Do not assume scope is already correct just because a document exists
- Existing-work routing may be compressed to one lightweight question, but cannot be skipped when prior artifacts are detected
- Skip full deep questioning, but still synthesize a scoping contract from the supplied document
- Ask at most one repair prompt if blocking scoping fields are missing
- Config questions still required (Step 5)
- Require one explicit scoping approval gate before requirements and roadmap generation
- After config and scope approval: run Steps 6-9 automatically with smart defaults:
  - Literature survey: Always yes
  - Research questions: Include all from provided document
  - Research questions approval: Use approved scoping contract as source of truth
  - Roadmap approval: Auto-approve only for `balanced` / `yolo`; if `autonomy=supervised`, present the draft roadmap before commit

**Document requirement:**
Auto mode requires a research document via @ reference (e.g., `/gpd:new-project --auto @proposal.md`). If no document provided, error:

```
Error: --auto requires a research document via @ reference.

Usage: /gpd:new-project --auto @your-proposal.md

The document should describe the physics problem you want to investigate.
```

</auto_mode>

<minimal_mode>

## Minimal Mode Detection

Check if `--minimal` flag is present in $ARGUMENTS.

**If minimal mode:** After Step 1 (Setup), skip the entire standard flow (Steps 2-9) and execute the **Minimal Initialization Path** below instead.

Minimal mode creates the SAME directory structure and file set as the full path -- just with less conversational overhead. It still must produce a scoping contract with decisive outputs, anchors, and explicit approval so downstream workflows (`/gpd:plan-phase`, `/gpd:execute-phase`, etc.) work identically.

**Two variants:**

1. `--minimal @file.md` — Input file provided. Parse it for research context.
2. `--minimal` (no file) — Ask ONE question, then generate everything from the response.

---

### Minimal Initialization Path

**After Step 1 completes (init checks, git, project_exists guard):**

#### M1. Gather Research Context

**If `--minimal` with file** (`/gpd:new-project --minimal @plan.md`):

Parse the input markdown for:

- **Research question** — Look for headings like "Research Question", "Objective", "Goal", or the first substantive paragraph
- **Decisive observables and deliverables** — Look for explicit plots, figures, datasets, calculations, derivations, or benchmark outputs the user says matter
- **Existing decomposition, if any** — Look for numbered lists, headings like "Phases", "Plan", "Steps", "Milestones", or any clear sequence of investigation chunks. Treat these as optional grounding, not as a setup prerequisite.
- **Key parameters** — Look for mentions of physical parameters, coupling constants, energy scales, system sizes
- **Theoretical framework** — Infer from terminology (QFT, condensed matter, GR, statistical mechanics, etc.)
- **Computational tools** — Any mentioned software, libraries, or numerical methods
- **Must-keep context** — Look for must-read references, benchmark values, prior outputs, figures, notebooks, and any stop/rethink conditions

If the file cannot be parsed (no discernible research question or objective), error:

```
Error: Could not extract research context from the provided file.

The file should contain at minimum:
- A research question or objective

It should ideally also name at least one decisive output, anchor, prior output, or explicit "anchor unknown / need grounding / target not yet chosen" note so any repair prompt can stay narrow. Missing-anchor notes preserve uncertainty, but they do not satisfy approval on their own.

Example structure:
  # Research Question
  What is the critical exponent of the 3D Ising model?

  # Success Signal
  Extract the critical exponent and compare it against a trusted benchmark.

  # Anchors
  Compare against the known 3D Ising result from the literature.

  # Optional First Investigation Chunk
  Set up the Monte Carlo simulation and finite-size scaling workflow.
```

**If `--minimal` without file** (`/gpd:new-project --minimal`):

Ask ONE question inline (freeform, NOT ask_user):

"Describe your research project in one pass: what's the core question, what output, claim, or deliverable would count as success, what references, prior outputs, or known results must stay visible, whether the anchor is still unknown, any first investigation chunk you already know, and what would make you rethink the approach?"

Wait for response. From the single response, extract:

- Research question
- Theoretical framework
- Any decisive outputs, anchors, prior outputs, or explicit context gaps
- Any mentioned parameters, tools, constraints, or initial investigation chunk

#### M1.5. Synthesize And Approve The Scoping Contract

Build a canonical scoping contract from the extracted input.

**Blocking fields that must be present before approval:**

- Core question
- At least one decisive output, claim, or deliverable
- At least one concrete anchor, reference, prior-output constraint, or baseline
- If the decisive anchor is still unknown, keep that blocker explicit in `scope.unresolved_questions`, `context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors` rather than inventing one

**Fields to capture even if still uncertain:**

- In-scope and out-of-scope boundaries
- Must-read references, benchmarks, or prior outputs
- User-stated observables, deliverables, decisive plots, or artifact expectations
- User-stated stop conditions, rethink triggers, or "come back to me before continuing" guidance
- Initial investigation chunk or decomposition sketch if the user already knows it
- Weakest anchor
- What would look like progress but should not count as success
- What result would make the current framing look wrong or incomplete
- Unresolved questions / context gaps

**Preservation rule:** If the user names a specific observable, figure, dataset, derivation, paper, benchmark, notebook, prior run, or stop condition, keep that wording recognizable in the contract. Do not generalize it away into a vague proxy.
If the user does not know the anchor yet, preserve that explicitly in `scope.unresolved_questions`, `context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors` rather than inventing a paper, benchmark, or baseline.
Prefer explicit missing-anchor wording such as `Which reference should serve as the decisive benchmark anchor?`, `Benchmark reference not yet selected`, `need grounding before the decisive anchor is chosen`, `decisive target not yet chosen`, or `baseline comparison is TBD`.
Do not force a phase list just to make the scoping contract look complete. If decomposition is still unclear, record that uncertainty and let `ROADMAP.md` start with a single coarse phase or first grounded investigation chunk.
If the init JSON already contains `project_contract`, `project_contract_load_info`, or `project_contract_validation`, preserve that state in the approval gate and continuation decision. Do not collapse a visible-but-blocked contract into a blank slate when deciding whether this is a fresh project or a continuation.

If a blocking field is missing, ask exactly one repair prompt that targets only the missing field. Do not silently continue with placeholders.

Before you show the approval gate, build the raw contract as a literal JSON object for the `project_contract` subsection of `templates/state-json-schema.md`:

- author only the JSON object that will be stored in `project_contract`, not the surrounding `state.json` envelope
- follow the `project_contract` object rules in `templates/state-json-schema.md` exactly

- `project_contract` is a JSON object, not prose
- `observables`, `claims`, `deliverables`, `acceptance_tests`, `references`, `forbidden_proxies`, and `links` are arrays of objects, not strings
- every object in those arrays must declare a stable `id`
- same-kind IDs must be unique within each section; do not repeat an `id` inside `observables[]`, `claims[]`, `deliverables[]`, `acceptance_tests[]`, `references[]`, `forbidden_proxies[]`, or `links[]`
- `context_intake`, `approach_policy`, and `uncertainty_markers` are objects, not strings or lists
- `schema_version` must be the integer `1`
- `references[].must_surface` must be a boolean `true` or `false`, not a quoted synonym
- `context_intake.must_read_refs` must contain only `references[].id` values
- `claims[].observables`, `claims[].deliverables`, `claims[].acceptance_tests`, and `claims[].references` must point only to declared IDs
- `acceptance_tests[].subject`, `references[].applies_to`, and `forbidden_proxies[].subject` must point to a claim ID or deliverable ID, never an observable label or free text
- `acceptance_tests[].evidence_required`, `links[].source`, and `links[].target` may only point to declared claim, deliverable, acceptance-test, or reference IDs
- for enum fields, use only the exact schema vocabulary:
  - `observables[].kind`: `scalar | curve | map | classification | proof_obligation | other`
  - `deliverables[].kind`: `figure | table | dataset | data | derivation | code | note | report | other`
  - `acceptance_tests[].kind`: `existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | proof_hypothesis_coverage | proof_parameter_coverage | proof_quantifier_domain | claim_to_proof_alignment | lemma_dependency_closure | counterexample_search | human_review | other`
  - `acceptance_tests[].automation`: `automated | hybrid | human`
  - `references[].kind`: `paper | dataset | prior_artifact | spec | user_anchor | other`
  - `references[].role`: `definition | benchmark | method | must_consider | background | other`
  - `links[].relation`: `supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`
- if `references[].must_surface` is `true`, both `references[].applies_to[]` and `references[].required_actions[]` must be non-empty; do not leave must-surface anchors implicit
- `references[].carry_forward_to[]` is free-text workflow scope such as `planning`, `execution`, `verification`, or `writing`; it is not an enum and must not match any declared contract ID from `observables[]`, `claims[]`, `deliverables[]`, `acceptance_tests[]`, `references[]`, `forbidden_proxies[]`, or `links[]`
- do **not** invent near-miss enum values such as `anchor`, `manual`, `content-check`, `benchmark-record`, or `anchors`; rewrite them to the exact schema term before approval
- the contract schema is closed: do not add invented top-level or nested keys, and do not use scalar shortcuts for list fields
- list fields must stay lists even for single-item values, and blank or duplicate list entries are invalid after trimming whitespace
- if the user chooses "Review raw contract", show the exact JSON object that will be validated and persisted

Then present a concise scoping summary and require explicit approval:

- header: "Scope"
- question: "Does this scoping contract look right before I generate the project artifacts?"
- options:
  - "Approve scope" -- proceed
  - "Adjust scope" -- revise before writing files
  - "Review raw contract" -- show the structured contract
  - "Stop here" -- do not create downstream artifacts

**CRITICAL:** Minimal mode is still allowed to be lean, but it is not allowed to be contract-free.

After approval, validate the contract before persisting it:

```bash
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract - --mode approved
```

If validation fails, show the errors, revise the scoping contract, and do NOT continue to downstream artifact generation.

After validation passes, persist the approved contract into `GPD/state.json` from the same stdin payload:

```bash
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -
```

Do not write `/tmp` intermediates for the approved contract. Prefer piping the exact approved JSON directly to `gpd ... -`. Only write a file if the user explicitly wants a durable saved copy, and if so place it under the project, not an OS temp directory.

#### M2. Create PROJECT.md

Populate `GPD/PROJECT.md` using the template from `templates/project.md`.

Fill in what was extracted. For sections without enough information, use sensible placeholder text that signals incompleteness:

```markdown
# [Extracted Research Title]

## What This Is

[Extracted research description — keep it concise, 2-3 sentences from the input]

## Core Research Question

[Extracted research question]

## Scoping Contract Summary

### Contract Coverage

- [Claim / deliverable]: [What counts as success]
- [Acceptance signal]: [Benchmark match, proof obligation, figure, dataset, or note]
- [False progress to reject]: [Proxy that must not count]

### User Guidance To Preserve

- **User-stated observables:** [Specific quantity, curve, figure, or smoking-gun signal]
- **User-stated deliverables:** [Specific table, plot, derivation, dataset, note, or code output]
- **Must-have references / prior outputs:** [Paper, notebook, run, figure, or benchmark that must remain visible]
- **Stop / rethink conditions:** [When to pause, ask again, or re-scope before continuing]

### Scope Boundaries

**In scope**

- [Approved in-scope item]

**Out of scope**

- [Approved out-of-scope item]

### Active Anchor Registry

- [Anchor ID or short label]: [Paper, dataset, spec, benchmark, or prior artifact]
  - Why it matters: [What it constrains]
  - Carry forward: [planning | execution | verification | writing]
  - Required action: [read | use | compare | cite | avoid]

### Carry-Forward Inputs

- [Prior output, notebook, figure, baseline, or "None confirmed yet"]

### Skeptical Review

- **Weakest anchor:** [Least-certain assumption, reference, or prior result]
- **Disconfirming observation:** [What would make the framing look wrong]
- **False progress to reject:** [What might look promising but should not count as success]

### Open Contract Questions

- [Unresolved question or context gap]

## Physics Subfield

[Inferred from input, e.g., "Condensed matter — phase transitions"]

## Mathematical Framework

[Inferred from input, or "To be determined during Phase 1"]

## Notation Conventions

To be established during initial phases.

## Unit System

[Inferred from input, or "Natural units (hbar = c = 1)"]

## Computational Tools

[Extracted from input, or "To be determined"]

If the project may rely on Wolfram capability, distinguish a local Mathematica / Wolfram Language install from the shared optional Wolfram integration config. Add `--live-executable-probes` to `gpd doctor` if you also want cheap local executable probes such as `pdflatex --version` or `wolframscript -version`, but that stays separate from the shared path enabled with `gpd integrations enable wolfram`, and it is still separate from `gpd validate plan-preflight <PLAN.md>` and from local install checks.

## Requirements

### Validated

(None yet — derive and validate to confirm)

### Active

- [ ] [One requirement per extracted phase goal]

### Out of Scope

(To be refined as project progresses)

## Key References

[Approved must-read references, benchmarks, or "None confirmed yet"]

## Target Publication

(To be determined)

## Constraints

(None specified)

## Key Decisions

| Decision                                    | Rationale              | Outcome   |
| ------------------------------------------- | ---------------------- | --------- |
| Minimal initialization — defer deep scoping | Fast project bootstrap | — Pending |

---

_Last updated: [today's date] after initialization (minimal)_
```

#### M3. Create REQUIREMENTS.md

Auto-generate REQ-IDs from the phase goals or major work chunks extracted in M1.

For each phase, create one or more requirements using the standard format:

```markdown
# Research Requirements

## Current Requirements

### Phase-Derived Requirements

[For each confirmed phase or work chunk, generate requirements with REQ-IDs:]

- [ ] **REQ-01**: [Goal of phase 1, made specific and testable]
- [ ] **REQ-02**: [Goal of phase 2, made specific and testable]
- [ ] **REQ-03**: [Goal of phase 3, made specific and testable]
      [... one per confirmed phase or work chunk minimum ...]

## Future Work

(To be identified as project progresses)

## Out of Scope

(To be refined — use /gpd:settings or edit REQUIREMENTS.md directly)

## Traceability

| REQ-ID | Phase | Status  |
| ------ | ----- | ------- |
| REQ-01 | 1     | Planned |
| REQ-02 | 2     | Planned |
| REQ-03 | 3     | Planned |
```

#### M4. Create ROADMAP.md

Create `GPD/ROADMAP.md` directly from the phase descriptions or inferred work chunks (no roadmapper agent).

Use the coarsest decomposition the approved contract actually supports. If the input only supports one grounded stage so far, create a one-phase roadmap and carry later decomposition as an open question instead of inventing filler phases.

Use the standard roadmap template structure:

```markdown
# Roadmap: [Research Project Title]

## Overview

[One paragraph synthesized from the research description]

## Phases

- [ ] **Phase 1: [Phase name]** - [One-line description]
- [ ] **Phase 2: [Phase name]** - [One-line description]
- [ ] **Phase 3: [Phase name]** - [One-line description]
      [... from extracted or inferred stages/work chunks ...]

## Phase Details

### Phase 1: [Phase name]

**Goal:** [Extracted from input]
**Depends on:** Nothing (first phase)
**Requirements:** [REQ-01]
**Success Criteria** (what must be TRUE):

1. [Derived from phase goal — one concrete observable outcome]
2. [Second criterion if obvious from context]

Plans:

- [ ] 01-01: [TBD — created during /gpd:plan-phase]

[... repeat for each phase ...]

## Progress

| Phase     | Plans Complete | Status      | Completed |
| --------- | -------------- | ----------- | --------- |
| 1. [Name] | 0/TBD          | Not started | -         |
| 2. [Name] | 0/TBD          | Not started | -         |
| 3. [Name] | 0/TBD          | Not started | -         |
```

#### M5. Create STATE.md and config.json

**STATE.md** — Initialize using the standard template:

```markdown
# Research State

## Project Reference

See: GPD/PROJECT.md (updated [today's date])

**Core research question:** [From PROJECT.md]
**Current focus:** Phase 1 — [Phase 1 name]

## Current Position

**Current Phase:** 1
**Current Phase Name:** [Phase 1 name]
**Total Phases:** [N]
**Current Plan:** 0
**Total Plans in Phase:** 0
**Status:** Ready to plan
**Last Activity:** [today's date]
**Last Activity Description:** Project initialized (minimal)

**Progress:** [░░░░░░░░░░] 0%

## Active Calculations

None yet.

## Intermediate Results

None yet.

## Open Questions

[Populate from approved scoping-contract unresolved questions. If none, say "None yet."]

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

- [Phase 1]: Minimal mode — scoping contract approved before phase planning

### Active Approximations

None yet.

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

**Last session:** [current ISO timestamp]
**Stopped at:** Project initialized (minimal)
**Resume file:** —
**Hostname:** [current hostname]
**Platform:** [current platform]
```

Initialize matching continuity fields in `GPD/state.json.session` (`last_session`, `stopped_at`, `resume_file`, `hostname`, `platform`) so `/gpd:resume-work` sees the same state when JSON is healthy.

**config.json** — Create with sensible defaults (no config questions asked):

```json
{
  "autonomy": "balanced",
  "research_mode": "balanced",
  "execution": {
    "review_cadence": "adaptive"
  },
  "parallelization": true,
  "planning": {
    "commit_docs": true
  },
  "model_profile": "review",
  "workflow": {
    "research": true,
    "plan_checker": true,
    "verifier": true
  }
}
```

#### M6. Commit All Artifacts

Create the directory structure and commit everything in a single commit:

```bash
mkdir -p GPD

PRE_CHECK=$(gpd pre-commit-check --files GPD/PROJECT.md GPD/REQUIREMENTS.md GPD/ROADMAP.md GPD/STATE.md GPD/state.json GPD/config.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: initialize research project (minimal)" --files GPD/PROJECT.md GPD/REQUIREMENTS.md GPD/ROADMAP.md GPD/STATE.md GPD/state.json GPD/config.json
```

#### M7. Done — Offer Next Step

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> RESEARCH PROJECT INITIALIZED (MINIMAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**[Research Project Name]**

| Artifact     | Location                    |
|--------------|-----------------------------|
| Project      | `GPD/PROJECT.md`      |
| Config       | `GPD/config.json`     |
| Requirements | `GPD/REQUIREMENTS.md` |
| Roadmap      | `GPD/ROADMAP.md`      |
| State        | `GPD/STATE.md`        |

**[N] phases** | **[N] requirements** | Ready to investigate

Note: Initialized with --minimal. Literature survey and deep scoping
were skipped. Use /gpd:settings to adjust workflow preferences.

---------------------------------------------------------------

## >> Next Up

**Phase 1: [Phase Name]** — [Goal from ROADMAP.md]
```

Use ask_user:

- header: "Next Step"
- question: "Discuss phase 1 now?"
- options:
  - "Discuss phase 1" — Run /gpd:discuss-phase 1
  - "Review artifacts first" — I want to check the generated files
  - "Done for now" — I'll continue later

**If "Discuss phase 1":** Tell the user to run `/gpd:discuss-phase 1` (and suggest `/clear` first for a fresh context window).

**If "Review artifacts first":** List the files and let the user inspect them. Suggest edits if needed, then re-offer planning.

**If "Done for now":** Exit. Remind them to use `/gpd:resume-work` or `/gpd:discuss-phase 1` when ready.

---

**End of Minimal Initialization Path.** The standard flow (Steps 2-9) is not executed when `--minimal` is active.

</minimal_mode>

<process>

## 1. Setup

**MANDATORY FIRST STEP — Execute these checks before ANY user interaction:**

```bash
INIT=$(gpd init new-project)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed with the workflow.
fi
```

Parse JSON for: `researcher_model`, `synthesizer_model`, `roadmapper_model`, `commit_docs`, `autonomy`, `research_mode`, `project_exists`, `has_research_map`, `planning_exists`, `has_research_files`, `has_project_manifest`, `has_existing_project`, `needs_research_map`, `has_git`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause for user confirmation after each major step (questioning, scoping contract, research, roadmap). Show summaries and wait for approval before proceeding.
- `autonomy=balanced` (default): Execute the full pipeline automatically. Pause only if research results are ambiguous, the roadmap has gaps, or scope-setting decisions need user judgment. The initial scoping contract is always a user-judgment checkpoint.
- `autonomy=yolo`: Execute full pipeline, skip optional literature survey, auto-approve roadmap. Do NOT skip the initial scoping-contract approval gate. Do NOT skip the requirement to show contract coverage in the roadmap.
- `--auto` changes how intake happens, not who owns later review gates. If `autonomy=supervised`, keep the roadmap approval checkpoint even in auto mode.
- `research_mode=explore`: Expand literature survey (spawn 5+ researchers), broader questioning, include speculative research directions in roadmap.
- `research_mode=exploit`: Focused literature survey (2-3 researchers), targeted questioning, lean roadmap with minimal exploratory phases.
- `research_mode=adaptive`: Start broad enough to compare viable approaches while scoping the project. Narrow the roadmap only after anchors or decisive evidence make one method family clearly preferable.
- Before `GPD/config.json` exists, the `autonomy` and `research_mode` values from `gpd init new-project` are temporary defaults, not a durable user choice. Let those defaults govern the initial questioning and scoping pass, then run Step 5 immediately after scope approval and before the first project-artifact commit so the durable config takes over before research and roadmap execution.
- Treat `project_contract` as approved scope only when `project_contract_gate.authoritative` is true. If the gate is false, keep the contract visible for scoping diagnostics and repair, not as authoritative downstream scope.

**If `project_exists` is true:** Error — project already initialized. Use `/gpd:progress`.

**If `has_git` is false:** Initialize git:

```bash
git init
```

**Check for previous initialization attempt:**

```bash
if [ -f GPD/init-progress.json ]; then
  # Guard against corrupted JSON (e.g., from interrupted write)
  PREV_STEP=""
  PREV_DESC=""
  INIT_PROGRESS_RAW=$(cat GPD/init-progress.json 2>/dev/null || echo "")
  if [ -n "$INIT_PROGRESS_RAW" ]; then
    PREV_STEP=$(echo "$INIT_PROGRESS_RAW" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('step',''))" 2>/dev/null)
    PREV_DESC=$(echo "$INIT_PROGRESS_RAW" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('description',''))" 2>/dev/null)
  fi

  # If JSON was corrupted (empty step), treat as fresh start
  if [ -z "$PREV_STEP" ]; then
    echo "WARNING: init-progress.json exists but is corrupted or empty. Starting fresh."
    rm -f GPD/init-progress.json
  fi
fi
```

If `init-progress.json` exists and is valid, offer to resume:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PREVIOUS INITIALIZATION DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Completed through step {PREV_STEP}: {PREV_DESC}

──────────────────────────────────────────────────────
Options:
  1. "Resume from step {PREV_STEP + 1}" -- continue where you left off
  2. "Start fresh" -- re-run from the beginning
──────────────────────────────────────────────────────
```

If resume: skip to the step after PREV_STEP (check which artifacts already exist on disk to confirm).
If start fresh: delete `init-progress.json` and proceed normally.

## 2. Existing Work Offer

**If auto mode:** Do not offer the full mapping flow by default, but do NOT assume a fresh project if prior artifacts exist. If `needs_research_map` is true or existing artifacts are detected, ask one lightweight routing question:

- header: "Existing Work"
- question: "Should I treat the supplied document as a fresh project, or as a continuation that must carry forward existing outputs?"
- options:
  - "Fresh project" -- synthesize scope from the document only
  - "Continuation" -- include existing outputs and baselines as contract inputs

If no prior artifacts are detected, continue directly to Step 3 / Step 4 as appropriate.

**If `needs_research_map` is true** (from init — existing research artifacts detected but no research map):

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

Use ask_user:

- header: "Existing Research"
- question: "I detected existing research artifacts in this directory. Would you like to map the existing work first?"
- options:
  - "Map existing work first" — Run /gpd:map-research to understand current research state (Recommended)
  - "Skip mapping" — Proceed with fresh project initialization

**If "Map existing work first":**

```
Run `/gpd:map-research` first, then return to `/gpd:new-project`
```

Exit command.

If `project_contract` is present in the init JSON, keep `project_contract`, `project_contract_load_info`, and `project_contract_validation` visible while deciding whether this is fresh work or a continuation. Preserve blockers, warnings, and approval state rather than flattening them into a blank-slate prompt.

**If "Skip mapping" OR `needs_research_map` is false:** Continue to Step 3.

## 3. Deep Questioning

**If auto mode:** Skip. Extract research context from provided document instead and proceed to Step 4.

**Display stage banner:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> RESEARCH QUESTION FORMULATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Open the conversation:**

Ask inline (freeform, NOT ask_user):

"What physics problem do you want to investigate?"

Wait for their response. This gives you the context needed to ask intelligent follow-up questions.

**Follow the thread:**

Based on what they said, ask follow-up questions that dig into their response. Use ask_user with options that probe what they mentioned — interpretations, clarifications, concrete examples.

Keep following threads. Each answer opens new threads to explore. Ask about:

- What physical system or phenomenon motivated this
- What they currently suspect about the answer, and what evidence would change their mind
- What theoretical framework they are working in
- What approximations or limits they are considering
- What observable or measurable quantities they care about
- What exact output, artifact, or benchmark would count as success
- What exact observable, figure, derivation, dataset, or note they would personally look for first
- What first smoking-gun observable, curve, benchmark reproduction, or scaling law they would trust before softer sanity checks
- What would look like progress but should not count as success
- Whether passing limiting cases, generic expectations, or qualitative agreement without that smoking gun should still count as failure
- What references, benchmark results, datasets, or prior internal outputs must stay visible
- What prior plots, notebooks, code outputs, or existing artifacts already matter and must not be ignored
- What should make the system stop, re-scope, or ask them again before a long execution branch
- Which anchor or assumption feels weakest right now
- What result would make the current framing look wrong or incomplete
- What computational resources they have access to
- Whether this connects to existing experimental data

If the user names a specific observable, deliverable, anchor paper, benchmark, figure, notebook, or prior result, reflect it back using recognizable wording and treat it as binding context unless the user later revises it.

Consult `{GPD_INSTALL_DIR}/references/research/questioning.md` for techniques:

- Challenge vagueness ("What do you mean by 'interesting regime'?")
- Make abstract concrete ("Can you write down the Hamiltonian?")
- Surface assumptions ("Are you assuming equilibrium? Why?")
- Find edges ("What happens at strong coupling?")
- Reveal motivation ("What would change if you solved this?")
- Surface anchors ("What do we trust as ground truth here?")
- Demand the smoking gun ("What exact check would make you trust this over softer sanity checks?")
- Force one disconfirming question ("What would make this framing look wrong?")
- Reject proxies ("What should not count as done?")

**Check context (background, not out loud):**

As you go, mentally check the context checklist from `{GPD_INSTALL_DIR}/references/research/questioning.md`. If gaps remain, weave questions naturally. Don't suddenly switch to checklist mode.

Context to gather:

- Research question (precise, falsifiable or answerable)
- Physical system and regime
- Theoretical framework (QFT, condensed matter, GR, statistical mechanics, etc.)
- Key parameters and scales
- User-stated observables, smoking-gun signals, or decisive plots
- Decisive outputs, deliverables, or benchmark targets
- Must-read references, baselines, and prior outputs to carry forward
- User-stated stop conditions, rethink triggers, or review requests before long execution
- Known results in the field (what has been done)
- What is new or open (what has NOT been done)
- Computational vs analytical approach preference
- Target audience and venue (journal, conference)
- Timeline and collaboration context
- Available computational resources
- Weakest anchor or assumption
- Disconfirming observation / change-course trigger
- False-progress signals to reject

**Decision gate:**

When you could write a clear scoping contract, use ask_user:

- header: "Ready?"
- question: "I think I understand the research direction, the decisive outputs, and the anchors we need to respect. Ready to create PROJECT.md?"
- options:
  - "Create PROJECT.md" — Let's move forward
  - "Keep exploring" — I want to share more / ask me more

If "Keep exploring" — ask what they want to add, or identify gaps and probe naturally.

Avoid rigid turn-counting. After several substantive exchanges, if you can state the core question, one decisive output or deliverable, and at least one concrete anchor/reference/prior-output/baseline while keeping any still-missing decisive anchor explicit as an open question, offer to proceed. If those blocking fields are still missing after roughly 6 follow-ups, summarize what is missing and keep exploring or pause until at least one concrete anchor/reference/prior-output/baseline is available; do not offer approval yet. A full phase breakdown is not required at this stage; if only the first grounded investigation chunk is clear, say so and carry later decomposition as an open question. Do not force closure just because a counter was hit, and do not imply certainty where there is still ambiguity.
If you only have limiting cases, sanity checks, or generic benchmark language with no decisive smoking-gun observable, curve, or benchmark reproduction, keep exploring unless the user explicitly says that is the decisive standard.

## 4. Synthesize The Approved Project Contract And Write PROJECT.md

**If auto mode:** Synthesize the scoping contract from the provided document, ask at most one repair prompt for blocking gaps, and require one explicit scope approval before continuing.

Before writing `PROJECT.md`, synthesize a canonical project contract with at least these elements:

- `scope.question`
- `scope.in_scope`
- `scope.out_of_scope`
- `scope.unresolved_questions`
- `context_intake.must_read_refs`
- `context_intake.must_include_prior_outputs`
- `context_intake.user_asserted_anchors`
- `context_intake.known_good_baselines`
- `context_intake.context_gaps`
- `context_intake.crucial_inputs` for user-stated observables, deliverables, stop conditions, or anything the user said must stay visible even when it is not itself approved-mode grounding
- `observables` for any user-named decisive quantity, signal, or behavior, especially the first smoking-gun check they would trust over softer proxies or limiting cases
- at least one decisive claim, observable, or deliverable
- any forbidden proxy or false-progress signal that the user called out
- `uncertainty_markers.weakest_anchors`
- `uncertainty_markers.unvalidated_assumptions`
- `uncertainty_markers.competing_explanations`
- `uncertainty_markers.disconfirming_observations`
`context_intake`, `approach_policy`, and `uncertainty_markers` must each stay as objects, not strings or lists.
`schema_version` must be the integer `1`, and `references[].must_surface` must be a boolean `true` or `false`, not a quoted synonym.

If no must-read references are confirmed yet, record that explicitly in the contract rather than inventing one.
If the user does not know the anchor yet, record that explicitly as an unresolved question or context gap rather than fabricating a paper, dataset, benchmark, or baseline.
Accepted shorthand like `need grounding` or `target not yet chosen` is fine when it clearly refers to the missing decisive anchor.
If the user supplied explicit observables, deliverables, prior outputs, or stop conditions, preserve them in the contract using wording the user would still recognize. Do not paraphrase them into generic "benchmark" or "artifact" language unless the user asked you to broaden them.
If the user named a prior output or review checkpoint that must ground approval or be carried forward, put it in `context_intake.must_include_prior_outputs`. Use `context_intake.crucial_inputs` for user-stated observables, stop conditions, review requests, or constraints that must stay visible but do not themselves replace approved-mode grounding.
Do not approve a scoping contract that strips decisive outputs, anchors, prior outputs, or review/stop triggers down to generic placeholders. The approved contract must preserve the user guidance that downstream planning needs.
If the only checks captured so far are limiting cases, sanity checks, or qualitative expectations, treat the contract as still underspecified unless the user explicitly states that these are the decisive standard.
Missing-anchor notes preserve uncertainty, but they do not satisfy approval on their own. Do not offer approval until at least one concrete anchor, reference, prior-output constraint, or baseline is present.

Before you ask for approval, build the raw contract as a literal JSON object for the `project_contract` subsection of `templates/state-json-schema.md`:

- author only the JSON object that will be stored in `project_contract`, not the surrounding `state.json` envelope
- follow the `project_contract` object rules in `templates/state-json-schema.md` exactly

- `project_contract` is a JSON object, not prose
- `observables`, `claims`, `deliverables`, `acceptance_tests`, `references`, `forbidden_proxies`, and `links` are arrays of objects, not strings
- every object in those arrays must declare a stable `id`
- same-kind IDs must be unique within each section; do not repeat an `id` inside `observables[]`, `claims[]`, `deliverables[]`, `acceptance_tests[]`, `references[]`, `forbidden_proxies[]`, or `links[]`
- `context_intake`, `approach_policy`, and `uncertainty_markers` are objects, not strings or lists
- `schema_version` must be the integer `1`
- `references[].must_surface` must be a boolean `true` or `false`, not a quoted synonym
- `context_intake.must_read_refs` must contain only `references[].id` values
- `references[].carry_forward_to[]` is free-text workflow scope such as `planning`, `execution`, `verification`, or `writing`; it is not an enum and must not match any declared contract ID from `observables[]`, `claims[]`, `deliverables[]`, `acceptance_tests[]`, `references[]`, `forbidden_proxies[]`, or `links[]`
- `claims[].observables`, `claims[].deliverables`, `claims[].acceptance_tests`, and `claims[].references` must point only to declared IDs
- `acceptance_tests[].subject`, `references[].applies_to`, and `forbidden_proxies[].subject` must point to a claim ID or deliverable ID, never an observable label or free text
- `acceptance_tests[].evidence_required`, `links[].source`, and `links[].target` may only point to declared claim, deliverable, acceptance-test, or reference IDs
- for enum fields, use only the exact schema vocabulary:
  - `observables[].kind`: `scalar | curve | map | classification | proof_obligation | other`
  - `deliverables[].kind`: `figure | table | dataset | data | derivation | code | note | report | other`
  - `acceptance_tests[].kind`: `existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | proof_hypothesis_coverage | proof_parameter_coverage | proof_quantifier_domain | claim_to_proof_alignment | lemma_dependency_closure | counterexample_search | human_review | other`
  - `acceptance_tests[].automation`: `automated | hybrid | human`
  - `references[].kind`: `paper | dataset | prior_artifact | spec | user_anchor | other`
  - `references[].role`: `definition | benchmark | method | must_consider | background | other`
  - `links[].relation`: `supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other`
- if `references[].must_surface` is `true`, both `references[].applies_to[]` and `references[].required_actions[]` must be non-empty; do not leave must-surface anchors implicit
- if the user chooses "Review raw contract", show the exact JSON object that will be validated and persisted

Present a concise scoping summary and require explicit approval before downstream artifact generation:

- header: "Scope"
- question: "Does this scoping contract look right before I generate project artifacts?"
- options:
  - "Approve scope" -- proceed
  - "Adjust scope" -- revise the contract before writing files
  - "Review raw contract" -- show the structured contract
  - "Stop here" -- exit without creating downstream artifacts

Validate the approved contract before persisting it:

```bash
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract - --mode approved
```

If validation fails, show the errors, revise the scoping contract, and do NOT continue.

Persist the approved contract into `GPD/state.json` from the same stdin payload:

```bash
printf '%s\n' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -
```

Do not write `/tmp` intermediates for the approved contract. Prefer piping the exact approved JSON directly to `gpd ... -`. Only write a file if the user explicitly wants a durable saved copy, and if so place it under the project, not an OS temp directory.

If `GPD/config.json` does not exist yet, run Step 5 now before generating or committing `PROJECT.md`. This keeps the opening focused on the physics question while still letting `planning.commit_docs` and other durable workflow settings apply before the first project-artifact commit. After Step 5 completes, return here and continue.

Then synthesize all context into `GPD/PROJECT.md` using the template from `templates/project.md`.

**For fresh research projects:**

Initialize research questions as hypotheses:

```markdown
## Research Questions

### Answered

(None yet — investigate to answer)

### Active

- [ ] [Research question 1]
- [ ] [Research question 2]
- [ ] [Research question 3]

### Out of Scope

- [Question 1] — [why: e.g., requires experiment, different subfield]
- [Question 2] — [why]
```

**For continuation projects (existing work map exists):**

Infer answered questions from existing work:

1. Read `GPD/research-map/ARCHITECTURE.md` and `FORMALISM.md`
2. Identify what has already been established
3. These become the initial Answered set

```markdown
## Research Questions

### Answered

- [checkmark] [Existing result 1] — established
- [checkmark] [Existing result 2] — established
- [checkmark] [Existing result 3] — established

### Active

- [ ] [New question 1]
- [ ] [New question 2]

### Out of Scope

- [Question 1] — [why]
```

**Scoping Contract Summary:**

Ensure PROJECT.md visibly summarizes the approved contract, including:

```markdown
## Scoping Contract Summary

### Contract Coverage

- [Claim / deliverable]: [What counts as success]
- [Acceptance signal]: [Benchmark match, proof obligation, figure, dataset, or note]
- [False progress to reject]: [Proxy that must not count]

### Scope Boundaries

**In scope**

- [Approved in-scope item]

**Out of scope**

- [Approved out-of-scope item]

### Active Anchor Registry

- [Anchor ID or short label]: [Paper, dataset, spec, benchmark, or prior artifact]
  - Why it matters: [What it constrains]
  - Carry forward: [planning | execution | verification | writing]
  - Required action: [read | use | compare | cite | avoid]

### Carry-Forward Inputs

- [Prior output, notebook, figure, baseline, or "None confirmed yet"]

### Skeptical Review

- **Weakest anchor:** [Least-certain assumption, reference, or prior result]
- **Unvalidated assumptions:** [What is currently assumed rather than checked]
- **Competing explanation:** [Alternative story that could also fit]
- **Disconfirming observation:** [What would make the framing look wrong]
- **False progress to reject:** [What might look promising but should not count as success]

### Open Contract Questions

- [Unresolved question or context gap]
```

**Key Decisions:**

Initialize with any decisions made during questioning:

```markdown
## Key Decisions

| Decision                  | Rationale | Outcome   |
| ------------------------- | --------- | --------- |
| [Choice from questioning] | [Why]     | — Pending |
```

**Research Context:**

```markdown
## Research Context

### Physical System

[Description of the system under study]

### Theoretical Framework

[QFT / condensed matter / GR / statistical mechanics / etc.]

### Key Parameters and Scales

| Parameter | Symbol | Regime  | Notes   |
| --------- | ------ | ------- | ------- |
| [param 1] | [sym]  | [range] | [notes] |

### Known Results

- [Prior work 1] — [reference]
- [Prior work 2] — [reference]

### What Is New

[What this project contributes beyond existing work]

### Target Venue

[Journal or conference, with rationale]

### Computational Environment

[Available resources: local workstation, cluster, cloud, specific codes]
```

**Last updated footer:**

```markdown
---

_Last updated: [date] after initialization_
```

Do not compress. Capture everything gathered.

**Commit PROJECT.md:**

```bash
mkdir -p GPD

PRE_CHECK=$(gpd pre-commit-check --files GPD/PROJECT.md GPD/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: initialize research project" --files GPD/PROJECT.md GPD/state.json
```

**Checkpoint step 4:**

```bash
cat > GPD/init-progress.json << CHECKPOINT
{"step": 4, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "Approved project contract and PROJECT.md created and committed"}
CHECKPOINT
```

## 5. Workflow Preferences

**Quick setup gate — offer a preset choice before individual questions:**

Run this step after scope approval and before the first project-artifact commit whenever `GPD/config.json` does not exist yet.

Treat the selected setup as a workflow preset bundle over the existing config knobs, not a new persisted preset block. The workflow should only write `autonomy`, `research_mode`, `parallelization`, `planning.commit_docs`, `execution.review_cadence`, `model_profile`, and the workflow toggles that already exist.

First surface a preset choice so the user can start from a bundle or jump straight to customization. If a preset is selected, preview the changed knobs before writing `GPD/config.json`, then ask for explicit apply or customize. Do not persist a separate preset key.

Use ask_user:

- header: "Workflow Setup"
- question: "Which starting workflow preset should GPD use for `GPD/config.json`?"
- options:
  - "Core research (Recommended)" — balanced planning/execution/verification default using the base runtime-readiness contract only
  - "Theory" — derivation-heavy workflow with `model_profile=deep-theory` and denser review cadence
  - "Numerics" — computation-heavy workflow with `model_profile=numerical` and the base runtime-readiness contract only
  - "Publication / manuscript" — paper-writing workflow with `model_profile=paper-writing`; `paper-build` is the manuscript build contract and `arxiv-submission` depends on that built output later
  - "Full research" — core research defaults plus publication readiness tracking for projects expected to end in a paper
  - "Customize settings" — choose `autonomy`, `research_mode`, `parallelization`, `planning.commit_docs`, `execution.review_cadence`, workflow agents, and `model_profile` individually

**If a preset is selected:** Resolve the selected catalog preset into the existing config keys, show the changed knobs before writing config.json, and if the user wants to adjust the bundle, fall back to "Customize settings". For the recommended `core-research` preset, that preview should surface `autonomy=balanced`, `research_mode=balanced`, `parallelization=true`, `planning.commit_docs=true`, `execution.review_cadence=adaptive`, and `model_profile=review`. Example for `core-research`:

```json
{
  "autonomy": "balanced",
  "research_mode": "balanced",
  "parallelization": true,
  "planning": {
    "commit_docs": true
  },
  "execution": {
    "review_cadence": "adaptive"
  },
  "model_profile": "review",
  "workflow": {
    "research": true,
    "plan_checker": true,
    "verifier": true
  }
}
```

Display confirmation:

```
Config: Balanced autonomy | Adaptive review cadence | Balanced research mode | Parallel | All agents | Review profile
(Change anytime with /gpd:settings)
```

Skip to "Commit config.json" below.

**If "Customize settings":** Proceed through Round 1 and Round 2 below.

---

**Round 1 — Core workflow settings (4 questions):**

```
questions: [
  {
    header: "Autonomy",
    question: "How much autonomy should GPD have?",
    multiSelect: false,
    options: [
      { label: "Balanced (Recommended)", description: "Routine work is automatic; pause on important physics decisions, ambiguities, blockers, or scope changes" },
      { label: "YOLO", description: "Fastest mode. Auto-approve checkpoints, sync the active runtime to its most autonomous permission mode when supported, and keep going unless a hard stop fires" },
      { label: "Supervised", description: "Confirm each major step before proceeding" }
    ]
  },
  {
    header: "Research Mode",
    question: "What research strategy should GPD use?",
    multiSelect: false,
    options: [
      { label: "Balanced (Recommended)", description: "Standard breadth and rigor for most projects" },
      { label: "Explore", description: "Broader literature search and more alternative approaches" },
      { label: "Exploit", description: "Focused execution with minimal branching" },
      { label: "Adaptive", description: "Start broad, then narrow once the best path is clear" }
    ]
  },
  {
    header: "Execution",
    question: "Run plans in parallel?",
    multiSelect: false,
    options: [
      { label: "Parallel (Recommended)", description: "Independent plans run simultaneously" },
      { label: "Sequential", description: "One plan at a time" }
    ]
  },
  {
    header: "Git Tracking",
    question: "Commit planning docs to git?",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Set planning.commit_docs=true so planning docs are tracked in version control" },
      { label: "No", description: "Set planning.commit_docs=false and keep GPD/ local-only (add to .gitignore)" }
    ]
  }
]
```

**Round 2 — Workflow agents (only if customizing):**

These spawn additional agents during planning/execution. They add tokens and time but improve quality.

| Agent                   | When it runs               | What it does                                                                        |
| ----------------------- | -------------------------- | ----------------------------------------------------------------------------------- |
| **Literature Scout**    | Before planning each phase | Surveys relevant literature, finds key references, surfaces known results           |
| **Derivation Checker**  | After plan is created      | Verifies mathematical consistency and completeness of proposed approach             |
| **Validation Verifier** | After phase execution      | Confirms results satisfy physical constraints, limiting cases, and known benchmarks |

All recommended for rigorous research. Skip for quick exploratory calculations.

```
questions: [
  {
    header: "Literature Survey",
    question: "Survey literature before planning each phase? (adds tokens/time)",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Find relevant references, known results, standard methods" },
      { label: "No", description: "Plan directly from research questions" }
    ]
  },
  {
    header: "Derivation Check",
    question: "Verify mathematical approach before execution? (adds tokens/time)",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Catch errors in formulation before computing" },
      { label: "No", description: "Execute approach without mathematical pre-check" }
    ]
  },
  {
    header: "Validation",
    question: "Validate results against known limits after each phase? (adds tokens/time)",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Check limiting cases, conservation laws, dimensional analysis" },
      { label: "No", description: "Trust results, skip systematic validation" }
    ]
  },
  {
    header: "Model Profile",
    question: "Which AI models for planning agents?",
    multiSelect: false,
    options: [
      { label: "Review (Recommended)", description: "Balanced cost/quality — tier-1 for critical agents, tier-2 for others" },
      { label: "Deep Theory", description: "Maximum capability — tier-1 for most agents — higher cost, deeper analysis" },
      { label: "Numerical", description: "Prioritize computation, convergence, and implementation-heavy work" },
      { label: "Exploratory", description: "Fast iteration — tier-2/tier-3 where possible — fastest, lowest cost" },
      { label: "Paper Writing", description: "Bias model selection toward manuscript drafting and polishing" }
    ]
  }
]
```

Create `GPD/config.json` with all settings:

```json
{
  "autonomy": "supervised|balanced|yolo",
  "research_mode": "explore|balanced|exploit|adaptive",
  "parallelization": true|false,
  "planning": {
    "commit_docs": true|false
  },
  "model_profile": "deep-theory|numerical|exploratory|review|paper-writing",
  "workflow": {
    "research": true|false,
    "plan_checker": true|false,
    "verifier": true|false
  }
}
```

**If planning.commit_docs = No:**

- Set `planning.commit_docs: false` in config.json
- Add `GPD/` to `.gitignore` (create if needed)

**If planning.commit_docs = Yes:**

- No additional gitignore entries needed

**Sync runtime permissions after writing config.json:**

Run this regardless of whether the user chose recommended defaults or custom settings. For `autonomy=yolo`, this should persist or prepare the runtime's most autonomous permission mode. For non-yolo autonomy, it should restore any earlier GPD-managed yolo override.

```bash
PERMISSIONS_SYNC=$(gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY" 2>/dev/null || true)
echo "$PERMISSIONS_SYNC"
```

Interpret the sync payload before continuing:

- If `message` is present, summarize it in plain language.
- If `requires_relaunch` is `true`, show `next_step` verbatim before moving on so the user knows whether the runtime must be restarted or relaunched through a generated command or wrapper.
- If sync fails because no runtime install could be resolved, explain that the project config was still created successfully and the user can run `gpd permissions sync --runtime <name>` later.
- This sync only updates runtime-owned permission settings; it does not create or validate the base install or workflow-tool readiness.

**Commit config.json:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/config.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "chore: add project config" --files GPD/config.json
```

**Checkpoint step 5:**

```bash
cat > GPD/init-progress.json << CHECKPOINT
{"step": 5, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "config.json created, runtime permissions synced, and config committed"}
CHECKPOINT
```

**Note:** Run `/gpd:settings` anytime to update these preferences and re-sync runtime permissions.

## 5.5. Resolve Model Profile

Use models from init: `researcher_model`, `synthesizer_model`, `roadmapper_model`.

## 6. Literature Survey Decision

**If auto mode:** Default to "Survey first" without asking.

Use ask_user:

- header: "Literature Survey"
- question: "Survey the research landscape before defining the investigation plan?"
- options:
  - "Survey first (Recommended)" — Discover known results, standard methods, open problems, available data
  - "Skip survey" — I know this field well, go straight to planning

**If "Survey first":**

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> SURVEYING RESEARCH LANDSCAPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Surveying [research domain] landscape...
```

Create research directory:

```bash
mkdir -p GPD/research
```

**Determine project context:**

Check if this is a fresh project or continuation:

- If no "Answered" research questions in PROJECT.md → Fresh project (starting from scratch)
- If "Answered" questions exist → Continuation (building on existing results)

Display spawning indicator:

```
>>> Spawning 4 literature scouts in parallel...
  -> Known results survey
  -> Methods and techniques survey
  -> Computational approaches survey
  -> Open problems and pitfalls survey
```

Spawn 4 parallel gpd-project-researcher agents with rich context:
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Known Results dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: Survey the landscape of known results in [research domain].
Continuation: Survey what's new since the existing results. Don't re-survey established ground.
</project_context_type>

<question>
What are the key known results, exact solutions, and established techniques in [research domain]?
</question>

<project_context>
[PROJECT.md summary - research question, physical system, theoretical framework, key parameters]
</project_context>

<downstream_consumer>
Your PRIOR-WORK.md feeds into research planning. Be precise:
- Specific results with references (author, year, journal)
- Conditions under which results hold
- Limitations and assumptions
- What remains open or contested
</downstream_consumer>

<quality_gate>
- [ ] References are specific (not vague citations)
- [ ] Conditions and assumptions stated for each result
- [ ] Relevance to our specific problem explained
</quality_gate>

<output>
Write to: GPD/research/PRIOR-WORK.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/PRIOR-WORK.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", readonly=false, description="Prior work research")

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Methods dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: What methods and computational tools are standard for [research domain]?
Continuation: What methods are appropriate for the new research questions?
</project_context_type>

<question>
What analytical techniques, numerical methods, and computational tools are standard for [research domain]?
</question>

<project_context>
[PROJECT.md summary]
</project_context>

<downstream_consumer>
Your METHODS.md feeds into approach selection. Categorize clearly:
- Analytical methods (exact solutions, perturbation theory, RG, etc.)
- Numerical methods (Monte Carlo, exact diagonalization, tensor networks, DFT, MD, etc.)
- Computational tools (specific codes, libraries, frameworks with versions)
- Validation techniques (benchmarks, limiting cases, sum rules)
</downstream_consumer>

<quality_gate>
- [ ] Methods are specific to this physics domain (not generic advice)
- [ ] Computational cost and scaling noted for numerical methods
- [ ] Known limitations and failure modes identified
</quality_gate>

<output>
Write to: GPD/research/METHODS.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/METHODS.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", readonly=false, description="Methods research")

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Computational Approaches dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: What computational tools and algorithms are available for [research domain]?
Continuation: What computational extensions are needed for the new questions?
</project_context_type>

<question>
What computational approaches, algorithms, and software tools are available for [research domain]? What are the convergence criteria and resource requirements?
</question>

<project_context>
[PROJECT.md summary]
</project_context>

<downstream_consumer>
Your COMPUTATIONAL.md informs the computational strategy. Include:
- Algorithms with convergence criteria and scaling behavior
- Software packages, libraries, and frameworks (with versions)
- Integration with existing code or workflows
- Resource estimates (memory, CPU/GPU, storage)
- Known numerical pitfalls and stability issues
</downstream_consumer>

<quality_gate>
- [ ] Algorithms defined with convergence criteria
- [ ] Software versions current and dependencies mapped
- [ ] Resource estimates provided for key calculations
</quality_gate>

<output>
Write to: GPD/research/COMPUTATIONAL.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/COMPUTATIONAL.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", readonly=false, description="Computational approaches research")

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-project-researcher.md for your role and instructions.

<research_type>
Literature Survey — Open Problems and Pitfalls dimension for [research domain].
</research_type>

<project_context_type>
[fresh project OR continuation]

Fresh project: What are the known open problems and common pitfalls in [research domain]?
Continuation: What pitfalls are specific to extending existing results in the new directions?
</project_context_type>

<question>
What are the open problems, common mistakes, and known pitfalls in [research domain]?
</question>

<project_context>
[PROJECT.md summary]
</project_context>

<downstream_consumer>
Your PITFALLS.md prevents wasted effort. For each pitfall:
- Warning signs (how to detect early)
- Prevention strategy (how to avoid)
- Which research phase should address it
- References to papers that fell into this trap
</downstream_consumer>

<quality_gate>
- [ ] Pitfalls are specific to this physics domain (not generic research advice)
- [ ] Known incorrect results or retracted papers noted
- [ ] Numerical stability and convergence issues identified
- [ ] Common sign errors, factor-of-2 mistakes, gauge issues flagged
</quality_gate>

<output>
Write to: GPD/research/PITFALLS.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/PITFALLS.md
</output>
", subagent_type="gpd-project-researcher", model="{researcher_model}", readonly=false, description="Pitfalls research")
```

**If any research agent fails to spawn or returns an error:** Check which output files were created (PRIOR-WORK.md, METHODS.md, COMPUTATIONAL.md, PITFALLS.md). For each missing file, note the gap and continue with available outputs. If 3+ agents failed, offer: 1) Retry all agents, 2) Skip literature survey and proceed with manual research context, 3) Stop initialization. If 1-2 agents failed, proceed with the synthesizer using available files — the synthesis will be partial but usable.

After all 4 agents complete (or partial completion handled), spawn synthesizer to create SUMMARY.md:

```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-research-synthesizer.md for your role and instructions.

<task>
Synthesize literature survey outputs into SUMMARY.md.
</task>

<research_files>
Read these files:
- GPD/research/PRIOR-WORK.md
- GPD/research/METHODS.md
- GPD/research/COMPUTATIONAL.md
- GPD/research/PITFALLS.md
</research_files>

<output>
Write to: GPD/research/SUMMARY.md
Use template: {GPD_INSTALL_DIR}/templates/research-project/SUMMARY.md
Do NOT commit — the orchestrator handles commits.
</output>
", subagent_type="gpd-research-synthesizer", model="{synthesizer_model}", readonly=false, description="Synthesize research")
```

**If the synthesizer agent fails to spawn or returns an error:** Check if individual research files exist. If they do, create a minimal SUMMARY.md in the main context by reading each file's key findings. The individual research files are more important than the synthesis — proceed with what exists.

Display research complete banner and key findings:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> LITERATURE SURVEY COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Key Findings

**Known Results:** [from SUMMARY.md]
**Standard Methods:** [from SUMMARY.md]
**Watch Out For:** [from SUMMARY.md]

Files: `GPD/research/`
```

**Commit research files:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/research/PRIOR-WORK.md GPD/research/METHODS.md GPD/research/COMPUTATIONAL.md GPD/research/PITFALLS.md GPD/research/SUMMARY.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: literature survey complete" \
  --files GPD/research/PRIOR-WORK.md GPD/research/METHODS.md \
  GPD/research/COMPUTATIONAL.md GPD/research/PITFALLS.md \
  GPD/research/SUMMARY.md
```

**Checkpoint step 6:**

```bash
cat > GPD/init-progress.json << CHECKPOINT
{"step": 6, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "Literature survey completed"}
CHECKPOINT
```

**If "Skip survey":** Continue to Step 7.

## 7. Define Research Questions and Requirements

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> DEFINING RESEARCH REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Load context:**

Read PROJECT.md and `GPD/state.json` and extract:

- Core research question (the ONE thing that must be answered)
- Stated constraints (computational resources, timeline, method limitations)
- Any explicit scope boundaries
- The approved `project_contract`
- Decisive outputs, deliverables, and forbidden proxies from the contract
- Must-read references, prior outputs, and known baselines from the contract

**If literature survey exists:** Read research/METHODS.md and PRIOR-WORK.md and extract available approaches.

**If auto mode:**

- Auto-include all essential research requirements (directly answer the core question and satisfy the approved contract)
- Include requirements explicitly mentioned in provided document
- Auto-defer tangential investigations not mentioned in document
- Skip per-category ask_user loops
- Skip "Any additions?" question
- Skip requirements approval gate
- Generate REQUIREMENTS.md and commit directly

**Present requirements by category (interactive mode only):**

```
Here are the research requirements for [domain]:

## Analytical Derivations
**Essential:**
- Derive the effective Hamiltonian in the [regime] limit
- Compute the [observable] to leading order in [parameter]

**Extended:**
- Include next-to-leading order corrections
- Explore connection to [related framework]

**Literature notes:** [any relevant notes]

---

## Numerical Validation
...
```

**If no literature survey:** Gather requirements through conversation instead.

Ask: "What are the key results you need to establish?"

For each objective mentioned:

- Ask clarifying questions to make it precise
- Probe for related calculations
- Group into categories (analytical, numerical, phenomenological)

**Scope each category:**

For each category, use ask_user:

- header: "[Category name]"
- question: "Which [category] requirements are in scope?"
- multiSelect: true
- options:
  - "[Objective 1]" — [brief description]
  - "[Objective 2]" — [brief description]
  - "[Objective 3]" — [brief description]
  - "None for now" — Defer entire category

Track responses:

- Selected requirements → current investigation
- Unselected essential → future work
- Unselected extended → out of scope

**Identify gaps:**

Use ask_user:

- header: "Additions"
- question: "Any requirements the literature survey missed? (Calculations specific to your approach)"
- options:
  - "No, survey covered it" — Proceed
  - "Yes, let me add some" — Capture additions

**Validate core question:**

Cross-check requirements against Core Research Question from PROJECT.md. If gaps detected, surface them.

**Generate REQUIREMENTS.md:**

Create `GPD/REQUIREMENTS.md` with:

- Current Requirements grouped by category (checkboxes, REQ-IDs)
- Future Requirements (deferred)
- Out of Scope (explicit exclusions with reasoning)
- Contract Coverage section mapping requirements to decisive outputs, anchors, baselines, and false-progress risks
- Traceability section (empty, filled by roadmap)

**REQ-ID format:** `[CATEGORY]-[NUMBER]` (ANAL-01, NUMR-02, PHENO-03)

**Objective quality criteria:**

Good research requirements are:

- **Specific and testable:** "Compute the spectral gap as a function of coupling g" (not "Study the spectrum")
- **Result-oriented:** "Derive expression for X" or "Determine whether Y holds" (not "Think about Z")
- **Atomic:** One calculation or result per requirement (not "Derive and numerically validate the phase diagram")
- **Independent:** Minimal dependencies on other requirements

Reject vague requirements. Push for specificity:

- "Study the phase transition" → "Determine the critical exponent nu for the [model] phase transition using [method]"
- "Compute correlators" → "Compute the two-point correlation function G(r) in the [regime] and extract the correlation length"

**Present full requirements list (interactive mode only):**

Show every requirement (not counts) for user confirmation:

```
## Current Research Requirements

### Analytical Derivations
- [ ] **ANAL-01**: Derive the effective low-energy Hamiltonian by integrating out high-energy modes
- [ ] **ANAL-02**: Compute the one-loop correction to the self-energy
- [ ] **ANAL-03**: Establish the Ward identity relating vertex and propagator

### Numerical Validation
- [ ] **NUMR-01**: Benchmark the derived spectral gap against exact diagonalization for N <= 16
- [ ] **NUMR-02**: Verify the predicted scaling exponent using finite-size scaling

[... full list ...]

---

Does this capture the research program? (yes / adjust)
```

If "adjust": Return to scoping.

**Commit requirements:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: define research requirements" --files GPD/REQUIREMENTS.md
```

**Checkpoint step 7:**

```bash
cat > GPD/init-progress.json << CHECKPOINT
{"step": 7, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "REQUIREMENTS.md created and committed"}
CHECKPOINT
```

## 8. Create Roadmap

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> CREATING RESEARCH ROADMAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>>> Spawning roadmapper...
```

Spawn gpd-roadmapper agent with context:

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(prompt="First, read {GPD_AGENTS_DIR}/gpd-roadmapper.md for your role and instructions.

<planning_context>

**Read these files before proceeding:**
- `GPD/PROJECT.md` — Project definition and research question
- `GPD/state.json` — Approved project contract in `project_contract`
- `GPD/REQUIREMENTS.md` — Derived requirements
- `GPD/research/SUMMARY.md` — Literature survey (if exists)
- `GPD/config.json` — Project configuration

</planning_context>

<instructions>
Create research roadmap:
1. Derive phases from requirements AND the approved project contract. Use the smallest decomposition that keeps decisive outputs, anchor handoffs, and verification legible. A tightly scoped project may have a single phase or a coarse early roadmap. Do NOT invent literature, numerics, or paper phases unless the requirements or contract demand them.
2. Map every requirement to exactly one phase
3. For each phase, include explicit contract coverage in ROADMAP.md showing the decisive contract items, deliverables, anchor coverage, and forbidden proxies advanced by that phase
4. Derive 2-5 success criteria per phase (concrete, verifiable results) that respect the decisive outputs, anchors, and forbidden proxies in the approved project contract
5. Validate 100% requirement coverage and surface all contract-critical items
6. Write files immediately (ROADMAP.md, STATE.md, update REQUIREMENTS.md traceability) while preserving any existing `GPD/state.json` fields, especially `project_contract` and previously recorded open questions
7. Return ROADMAP CREATED with summary

Write files first, then return. This ensures artifacts persist even if context is lost.
</instructions>
", subagent_type="gpd-roadmapper", model="{roadmapper_model}", readonly=false, description="Create research roadmap")
```

**Handle roadmapper return:**

**If the roadmapper agent fails to spawn or returns an error:** Check if ROADMAP.md was partially written (the agent writes files first). If ROADMAP.md exists, verify it has phases and offer to proceed with it. If no ROADMAP.md exists, offer: 1) Retry the roadmapper, 2) Create ROADMAP.md in the main context using PROJECT.md and REQUIREMENTS.md. Do not leave the project in a state with REQUIREMENTS.md but no ROADMAP.md. **Also check if STATE.md exists** — the roadmapper creates both. If STATE.md is missing, create a minimal STATE.md (using the template from Step M5 in the minimal mode section above) so that downstream commands (`convention set`, `state validate`, etc.) can function.

**If `## ROADMAP BLOCKED`:**

- Present blocker information
- Work with user to resolve
- Re-spawn when resolved

**If `## ROADMAP CREATED`:**

Read the created ROADMAP.md and present it nicely inline:

```
---

## Proposed Research Roadmap

**[N] phases** | **[X] requirements mapped** | Contract coverage surfaced

| # | Phase | Goal | Requirements | Contract Coverage | Success Criteria |
|---|-------|------|--------------|-------------------|------------------|
| 1 | [Name] | [Goal] | [REQ-IDs] | [claims / anchors] | [count] |
| 2 | [Name] | [Goal] | [REQ-IDs] | [claims / anchors] | [count] |
| 3 | [Name] | [Goal] | [REQ-IDs] | [claims / anchors] | [count] |
...

### Phase Details

**Phase 1: [Name]**
Goal: [goal]
Requirements: [REQ-IDs]
Contract coverage: [decisive outputs, anchors, forbidden proxies]
Success criteria:
1. [criterion]
2. [criterion]
3. [criterion]

**Phase 2: [Name]**
Goal: [goal]
Requirements: [REQ-IDs]
Contract coverage: [decisive outputs, anchors, forbidden proxies]
Success criteria:
1. [criterion]
2. [criterion]

[... continue for all phases ...]

---
```

**If auto mode and `autonomy` is not `supervised`:** Skip approval gate — auto-approve and commit directly.

**CRITICAL: Ask for approval before committing (interactive mode only):**

Use ask_user:

- header: "Roadmap"
- question: "Does this research roadmap structure work for you?"
- options:
  - "Approve" — Commit and continue
  - "Adjust phases" — Tell me what to change
  - "Review full file" — Show raw ROADMAP.md

**If "Approve":** Continue to commit.

**If "Adjust phases":**

- Get user's adjustment notes
- Re-spawn roadmapper with revision context:

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

  ```
  task(prompt="First, read {GPD_AGENTS_DIR}/gpd-roadmapper.md for your role and instructions.

  <revision>
  User feedback on roadmap:
  [user's notes]

  Read `GPD/ROADMAP.md` for the current roadmap.

  Update the roadmap based on feedback. Edit files in place.
  Return ROADMAP REVISED with changes made.
  </revision>
  ", subagent_type="gpd-roadmapper", model="{roadmapper_model}", readonly=false, description="Revise roadmap")
  ```

  **If the revision roadmapper agent fails to spawn or returns an error:** Check if ROADMAP.md was updated (compare with pre-revision content). If changes were made, proceed to present the revised roadmap. If no changes, offer: 1) Retry the revision agent, 2) Apply the user's adjustment notes manually in the main context by editing ROADMAP.md directly.

- Present revised roadmap
- Loop until user approves (**maximum 3 revision iterations** — after 3, commit the current version with user's notes recorded as open questions in ROADMAP.md, and note: "Roadmap committed after 3 revision rounds. Further adjustments via `/gpd:add-phase` or `/gpd:remove-phase`.")

**If "Review full file":** Display raw `cat GPD/ROADMAP.md`, then re-ask.

**Commit roadmap (after approval or auto mode):**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/ROADMAP.md GPD/STATE.md GPD/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: create research roadmap ([N] phases)" --files GPD/ROADMAP.md GPD/STATE.md GPD/REQUIREMENTS.md
```

**Checkpoint step 8:**

```bash
cat > GPD/init-progress.json << CHECKPOINT
{"step": 8, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "ROADMAP.md created and committed"}
CHECKPOINT
```

## 8.5. Establish Conventions

**After roadmap is committed, spawn gpd-notation-coordinator to establish notation conventions.**

This step is critical for multi-phase projects where convention mismatches cause silent errors (wrong signs, factors of 2*pi, metric signature confusion).

**If auto mode:** Auto-approve subfield defaults without user confirmation.

Display stage banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> ESTABLISHING CONVENTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

>>> Spawning notation coordinator...
```

```bash
NOTATION_MODEL=$(gpd resolve-model gpd-notation-coordinator)
```

If `NOTATION_MODEL` is empty or null, omit `model=` entirely in the spawn call. If it has a concrete value, include `model="$NOTATION_MODEL"`.

Spawn gpd-notation-coordinator:

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
  task(prompt="First, read {GPD_AGENTS_DIR}/gpd-notation-coordinator.md for your role and instructions.

<task>
Establish initial conventions for this research project.
</task>

<project_context>
Read these files:
- GPD/PROJECT.md — Project definition, physics subfield, theoretical framework
- GPD/ROADMAP.md — Phase structure (what conventions will be needed)
- GPD/REQUIREMENTS.md — Research requirements
- GPD/research/SUMMARY.md — Literature survey (if exists)
</project_context>

<mode>
{auto | interactive}
Auto mode: Use subfield defaults, lock all, skip user confirmation.
Interactive mode: Present suggested conventions, wait for user confirmation/override.
</mode>

<output>
1. Create: GPD/CONVENTIONS.md (full convention reference)
2. Lock conventions via: gpd convention set
3. Return CONVENTIONS ESTABLISHED with summary
</output>
", subagent_type="gpd-notation-coordinator", readonly=false, description="Establish project conventions")
```

**Handle notation-coordinator return:**

**If the notation-coordinator agent fails to spawn or returns an error:** Conventions are not critical for project initialization to succeed, BUT the convention_lock in state.json must be populated for downstream defense layers (L1-L4) to function. Fallback:

1. Create a minimal CONVENTIONS.md with the project's unit system and metric signature from PROJECT.md (if specified)
2. **Populate the convention_lock** with at minimum the unit system and metric signature:

   ```bash
   # Populate convention_lock so downstream L1-L4 defense layers are active
   gpd convention set natural_units "natural" 2>/dev/null || true
   gpd convention set metric_signature "mostly_minus" 2>/dev/null || true
   ```

   Adjust values based on what PROJECT.md specifies. If PROJECT.md doesn't specify conventions, use the subfield defaults from `{GPD_INSTALL_DIR}/references/conventions/subfield-convention-defaults.md`.

3. Note that full convention establishment was skipped. The user can run `gpd convention set ...` or `/gpd:validate-conventions` later to complete convention setup.

- **`CONVENTIONS ESTABLISHED`:** Display confirmation with convention summary. Commit CONVENTIONS.md:

  ```bash
  PRE_CHECK=$(gpd pre-commit-check --files GPD/CONVENTIONS.md 2>&1) || true
  echo "$PRE_CHECK"

  gpd commit "docs: establish notation conventions" --files GPD/CONVENTIONS.md
  ```

- **`CONVENTION CONFLICT`:** Display conflicts. Ask user to resolve before proceeding.

**Checkpoint step 8.5:**

```bash
cat > GPD/init-progress.json << CHECKPOINT
{"step": 8.5, "completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "description": "Conventions established and committed"}
CHECKPOINT
```

## 9. Done

**Delete init-progress.json — initialization is complete:**

```bash
rm -f GPD/init-progress.json
```

Present completion with next steps:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD >>> RESEARCH PROJECT INITIALIZED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**[Project Name]**

| Artifact       | Location                    |
|----------------|-----------------------------|
| Project        | `GPD/PROJECT.md`      |
| Config         | `GPD/config.json`     |
| Literature     | `GPD/research/`       |
| Requirements   | `GPD/REQUIREMENTS.md` |
| Roadmap        | `GPD/ROADMAP.md`      |
| Conventions    | `GPD/CONVENTIONS.md`  |

**[N] phases** | **[X] requirements** | Ready to investigate

---------------------------------------------------------------

## >> Next Up

**Phase 1: [Phase Name]** — [Goal from ROADMAP.md]

/gpd:discuss-phase 1 — gather context and clarify approach

<sub>/clear first -> fresh context window</sub>

---

**Also available:**
- /gpd:plan-phase 1 — skip discussion, plan directly

---------------------------------------------------------------
```

</process>

<output>

- `GPD/PROJECT.md`
- `GPD/config.json`
- `GPD/research/` (if literature survey selected)
  - `PRIOR-WORK.md`
  - `METHODS.md`
  - `COMPUTATIONAL.md`
  - `PITFALLS.md`
  - `SUMMARY.md`
- `GPD/REQUIREMENTS.md`
- `GPD/ROADMAP.md`
- `GPD/STATE.md`
- `GPD/state.json` with `project_contract`
- `GPD/CONVENTIONS.md` (established by gpd-notation-coordinator)

</output>

<success_criteria>

- [ ] GPD/ directory created
- [ ] Git repo initialized
- [ ] Existing work detection completed
- [ ] Deep questioning completed (threads followed, not rushed)
- [ ] Approved scoping contract persisted in `GPD/state.json`
- [ ] Scoping contract captures decisive outputs, anchors, weakest assumptions, and unresolved gaps
- [ ] PROJECT.md captures full research context — **committed**
- [ ] config.json has autonomy, research_mode, and parallelization settings — **committed**
- [ ] Literature survey completed (if selected) — 4 parallel agents spawned — **committed**
- [ ] Research requirements gathered (from survey or conversation)
- [ ] User scoped each category (current/future/out of scope)
- [ ] REQUIREMENTS.md created with REQ-IDs — **committed**
- [ ] gpd-roadmapper spawned with context
- [ ] Roadmap files written immediately (not draft)
- [ ] User feedback incorporated (if any)
- [ ] ROADMAP.md created with phases, requirement mappings, success criteria
- [ ] STATE.md initialized
- [ ] REQUIREMENTS.md traceability updated
- [ ] gpd-notation-coordinator spawned to establish conventions
- [ ] CONVENTIONS.md created with subfield-appropriate conventions — **committed**
- [ ] Convention lock populated via `gpd convention set`
- [ ] User knows next step is `/gpd:discuss-phase 1`

**Atomic commits:** Each phase commits its artifacts immediately. If context is lost, artifacts persist.

</success_criteria>

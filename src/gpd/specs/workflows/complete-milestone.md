<purpose>

Mark a completed research stage (v1.0, v1.1, v2.0) as done. Creates historical record in MILESTONES.md, performs full PROJECT.md evolution review, reorganizes ROADMAP.md with milestone groupings, archives completed research, and tags the release in git. Prepares handoff notes for the next research stage.

</purpose>

<required_reading>

1. templates/milestone.md
2. templates/milestone-archive.md
3. `.gpd/ROADMAP.md`
4. `.gpd/REQUIREMENTS.md`
5. `.gpd/PROJECT.md`

</required_reading>

<archival_behavior>

When a research milestone completes:

1. Extract full milestone details to `.gpd/milestones/v[X.Y]-ROADMAP.md`
2. Archive requirements to `.gpd/milestones/v[X.Y]-REQUIREMENTS.md`
3. Update ROADMAP.md -- replace milestone details with one-line summary
4. Delete REQUIREMENTS.md (fresh one for next research stage)
5. Perform full PROJECT.md evolution review
6. Offer to create next milestone inline

**Context Efficiency:** Archives keep ROADMAP.md constant-size and REQUIREMENTS.md milestone-scoped.

**ROADMAP archive** uses `templates/milestone-archive.md` -- includes milestone header (status, phases, date), full phase details, milestone summary (decisions, key findings, open questions).

**REQUIREMENTS archive** contains all requirements marked complete with outcomes, traceability table with final status, notes on changed requirements.

</archival_behavior>

<process>

<step name="verify_readiness">

**Use `roadmap analyze` for comprehensive readiness check:**

```bash
ROADMAP=$(gpd roadmap analyze)
```

This returns all phases with plan/summary counts and disk status. Use this to verify:

- Which phases belong to this milestone?
- All phases complete (all plans have summaries)? Check `disk_status == 'complete'` for each.
- `progress_percent` should be 100%.

Present:

```
Milestone: [Name, e.g., "v1.0 Model Derivation"]

Includes:
- Phase 1: Hamiltonian Setup (2/2 plans complete)
- Phase 2: Mean-Field Solution (2/2 plans complete)
- Phase 3: Numerical Validation (3/3 plans complete)
- Phase 4: Limiting Cases (1/1 plan complete)

Total: {phase_count} phases, {total_plans} plans, all complete
```

<config-check>

```bash
if [ -f .gpd/config.json ]; then cat .gpd/config.json; else echo "WARNING: config.json not found — using defaults"; fi
```

</config-check>

<if mode="yolo">

```
Auto-approved: Milestone scope verification
[Show breakdown summary without prompting]
Proceeding to stats gathering...
```

Proceed to gather_stats.

</if>

<if mode="interactive" OR="custom with gates.confirm_milestone_scope true">

```
Ready to mark this research milestone as complete?
(yes / wait / adjust scope)
```

Wait for confirmation.

- "adjust scope": Ask which phases to include.
- "wait": Stop, researcher returns when ready.

</if>

</step>

<step name="gather_stats">

Calculate milestone statistics:

```bash
git log --oneline --grep="feat(" | head -20
git diff --stat FIRST_COMMIT..LAST_COMMIT | tail -1
find . -name "*.py" -o -name "*.tex" -o -name "*.ipynb" | xargs wc -l 2>/dev/null
git log --format="%ai" FIRST_COMMIT | tail -1
git log --format="%ai" LAST_COMMIT | head -1
```

Present:

```
Milestone Stats:
- Phases: [X-Y]
- Plans: [Z] total
- Research tasks: [N] total (from phase summaries)
- Files modified: [M]
- Lines of code/text: [LOC] (Python/LaTeX/notebooks)
- Timeline: [Days] days ([Start] -> [End])
- Git range: feat(XX-XX) -> feat(YY-YY)
```

</step>

<step name="extract_accomplishments">

Extract one-liners from SUMMARY.md files using summary-extract:

```bash
# For each phase in milestone, extract one-liner
for summary in .gpd/phases/*-*/*-SUMMARY.md; do
  gpd summary-extract "$summary" --field one_liner | gpd json get .one_liner --default ""
done
```

Extract 4-6 key research accomplishments. Present:

```
Key accomplishments for this milestone:
1. [Research achievement from phase 1]
2. [Research achievement from phase 2]
3. [Research achievement from phase 3]
4. [Research achievement from phase 4]
5. [Research achievement from phase 5]
```

</step>

<step name="create_milestone_entry">

**Note:** MILESTONES.md entry is now created automatically by `gpd milestone complete` in the archive_milestone step. The entry includes version, date, phase/plan/task counts, and accomplishments extracted from SUMMARY.md files.

If additional details are needed (e.g., researcher-provided "Key Findings" summary, git range, LOC stats), add them manually after the CLI creates the base entry.

</step>

<step name="evolve_project_full_review">

Full PROJECT.md evolution review at milestone completion.

Read all phase summaries:

```bash
cat .gpd/phases/*-*/*-SUMMARY.md
```

**Full review checklist:**

1. **"What This Is" accuracy:**

   - Compare current description to what was actually researched
   - Update if the research scope has meaningfully changed

2. **Core Research Question check:**

   - Still the right question? Did investigation reveal a different core question?
   - Update if the primary research focus has shifted

3. **Requirements audit:**

   **Validated section:**

   - All Active requirements completed this milestone -> Move to Validated
   - Format: `- [x] [Requirement] -- v[X.Y]`

   **Active section:**

   - Remove requirements moved to Validated
   - Add new requirements for next research stage
   - Keep unaddressed requirements

   **Out of Scope audit:**

   - Review each item -- reasoning still valid?
   - Remove irrelevant items
   - Add research directions invalidated during milestone

4. **Context update:**

   - Current research state (key results, methods used)
   - Comparison with literature (agreements, disagreements)
   - Known limitations or open questions
   - Key parameter values and their justification

5. **Key Decisions audit:**

   - Extract all decisions from milestone phase summaries
   - Add to Key Decisions table with outcomes
   - Mark: Good (validated), Revisit (questionable), Pending (untested)

6. **Constraints check:**
   - Any constraints changed during research? Update as needed
   - New physical constraints discovered?

Update PROJECT.md inline. Update "Last updated" footer:

```markdown
---

_Last updated: [date] after v[X.Y] milestone_
```

**Example full evolution (v1.0 -> v1.1 prep):**

Before:

```markdown
## What This Is

A systematic study of phase transitions in the 2D Hubbard model using DMFT.

## Core Research Question

What is the nature of the Mott transition at half-filling?

## Requirements

### Validated

(None yet -- complete research to validate)

### Active

- [ ] Derive self-consistency equations for DMFT
- [ ] Implement impurity solver (ED or CTQMC)
- [ ] Map phase diagram (U/t vs T)
- [ ] Compare with exact diagonalization benchmarks

### Out of Scope

- Doped case -- focus on half-filling first
- Cluster extensions (CDMFT) -- single-site first
```

After v1.0:

```markdown
## What This Is

A systematic study of the Mott transition in the 2D Hubbard model at half-filling using single-site DMFT with an ED impurity solver.

## Core Research Question

What is the nature of the Mott transition at half-filling?

## Requirements

### Validated

- [x] Derive self-consistency equations for DMFT -- v1.0
- [x] Implement impurity solver (ED) -- v1.0 (6-bath-site solver, converges in <20 iterations)
- [x] Map phase diagram (U/t vs T) -- v1.0 (critical Uc/t = 9.35 +/- 0.15)

### Active

- [ ] Compare with exact diagonalization benchmarks
- [ ] Investigate hysteresis near transition
- [ ] Compute spectral functions at key points

### Out of Scope

- Doped case -- focus on half-filling first
- Cluster extensions (CDMFT) -- single-site captures essential physics at half-filling
- Superconducting order -- not relevant at half-filling

## Context

Completed v1.0 with DMFT self-consistency loop and ED solver.
Phase diagram shows first-order Mott transition with Uc/t = 9.35.
Good agreement with Bulla et al. (1999) NRG results (Uc/t = 9.35).
Minor discrepancy with Georges et al. (1996) at high T -- likely finite bath-size effect.
```

**Step complete when:**

- [ ] "What This Is" reviewed and updated if needed
- [ ] Core Research Question verified as still correct
- [ ] All completed requirements moved to Validated
- [ ] New requirements added to Active for next milestone
- [ ] Out of Scope reasoning audited
- [ ] Context updated with current research state
- [ ] All milestone decisions added to Key Decisions
- [ ] "Last updated" footer reflects milestone completion

</step>

<step name="generate_research_digest">

Generate a structured research digest that serves as the primary handoff artifact between milestone completion and paper writing. This digest lives at `.gpd/milestones/v[X.Y]/RESEARCH-DIGEST.md` and captures the full research story in a form optimized for downstream consumption by the paper-writing workflow.

**Step 0 -- Ensure digest directory exists:**

```bash
mkdir -p .gpd/milestones/v[X.Y]
```

**Step 1 -- Run history-digest for foundation data:**

```bash
DIGEST=$(gpd history-digest)
```

This returns per-phase summaries with one-liners, provides/requires, and dependency graph data.

**Step 2 -- Read source materials:**

```bash
# All SUMMARY.md files from this milestone's phases
cat .gpd/phases/*-*/*-SUMMARY.md

# Research state
cat .gpd/state.json

# Convention catalog (full reference)
cat .gpd/CONVENTIONS.md

# Convention lock (machine-readable, from state.json)
gpd --raw convention list

# Original objectives
cat .gpd/REQUIREMENTS.md
```

**Step 3 -- Compose RESEARCH-DIGEST.md:**

Create `.gpd/milestones/v[X.Y]/RESEARCH-DIGEST.md` with the following structure:

```markdown
# Research Digest: v[X.Y] [Milestone Name]

Generated: [date]
Milestone: v[X.Y]
Phases: [first]-[last]

## Narrative Arc

[One paragraph summarizing the research story from first phase to last. This is not a
list of what was done -- it is the logical thread that connects the initial question
through intermediate steps to the final result. Written in a way that maps naturally
to a paper's Introduction -> Methods -> Results flow.]

## Key Results

| Phase | Result        | Equation / Value                                        | Validity Range     | Confidence          |
| ----- | ------------- | ------------------------------------------------------- | ------------------ | ------------------- |
| [N]   | [Description] | [Equation or numerical value from intermediate_results] | [Parameter regime] | [From verification] |
| ...   | ...           | ...                                                     | ...                | ...                 |

Source: state.json intermediate_results, organized by phase ordering.

## Methods Employed

[Extracted from the `methods` field in SUMMARY.md frontmatter across all phases.
Listed in the order they were introduced, noting which phase introduced each method.]

- **Phase [N]:** [Method name] -- [Brief description]
- **Phase [M]:** [Method name] -- [Brief description]
- ...

## Convention Evolution

[Timeline of convention changes extracted from `gpd --raw convention list`, showing
when each convention was established or modified. This ensures the paper writer uses the
final, settled notation consistently.]

| Date / Phase | Convention        | Description     | Status              |
| ------------ | ----------------- | --------------- | ------------------- |
| Phase [N]    | [Symbol/notation] | [What it means] | Active / Superseded |
| ...          | ...               | ...             | ...                 |

## Figures and Data Registry

[All figures and data files created during this milestone, with paths and descriptions.
Extracted from phase directories and SUMMARY.md artifacts sections.]

| File   | Phase | Description     | Paper-ready? |
| ------ | ----- | --------------- | ------------ |
| [path] | [N]   | [What it shows] | Yes/No       |
| ...    | ...   | ...             | ...          |

## Open Questions

[From state.json open_questions field. These become the "Future Work" section of a
paper or motivate the next milestone.]

1. [Open question 1]
2. [Open question 2]
3. ...

## Dependency Graph

[The provides/requires graph from history-digest output, rendered as text. Shows how
results flow between phases -- useful for determining which derivation steps are
prerequisites for which results in the paper.]

    Phase [N] "[Name]"
      provides: [list]
      requires: [list]
    -> Phase [M] "[Name]"
      provides: [list]
      requires: [list]

## Mapping to Original Objectives

[Cross-reference results back to REQUIREMENTS.md objectives. Shows which requirements
were fulfilled by which phases/results.]

| Requirement | Status | Fulfilled by | Key Result |
|-------------|--------|-------------|------------|
| [Requirement text] | Complete/Partial | Phase [N] | [Result reference] |
| ... | ... | ... | ... |
```

**Step 4 -- Verify digest completeness:**

Before proceeding, confirm:

- [ ] Narrative arc covers the full research trajectory (not just the last phase)
- [ ] All intermediate_results from state.json appear in the Key Results table
- [ ] Methods list is complete (cross-check with SUMMARY frontmatter)
- [ ] Convention timeline includes all entries from `gpd convention list`
- [ ] Figures/data registry includes all artifacts from phase directories
- [ ] Open questions match state.json
- [ ] Dependency graph matches history-digest output
- [ ] Requirements mapping covers all REQUIREMENTS.md items

</step>

<step name="archive_milestone">

**Delegate archival to gpd CLI:**

```bash
ARCHIVE=$(gpd milestone complete "v[X.Y]" --name "[Milestone Name]")
```

The CLI handles:

- Creating `.gpd/milestones/` directory
- Archiving ROADMAP.md to `milestones/v[X.Y]-ROADMAP.md`
- Archiving REQUIREMENTS.md to `milestones/v[X.Y]-REQUIREMENTS.md` with archive header
- Moving audit file to milestones if it exists
- Creating/appending MILESTONES.md entry with accomplishments from SUMMARY.md files
- Updating STATE.md (status, last activity)

Extract from result: `version`, `date`, `phases`, `plans`, `tasks`, `accomplishments`, `archived`.

Verify: `Milestone archived to .gpd/milestones/`

**Note:** Phase directories (`.gpd/phases/`) are NOT deleted -- they accumulate across milestones as raw research history. Phase numbering continues (v1.0 phases 1-4, v1.1 phases 5-8, etc.).


</step>

<step name="promote_patterns">

Review project-local insights accumulated during this milestone and promote confirmed patterns to the global pattern library. This is the natural time to consolidate learnings — the research is complete, patterns have been validated across multiple phases, and confidence is highest.

**Step 1 — Check for project insights:**

```bash
ls .gpd/INSIGHTS.md 2>/dev/null
```

If no INSIGHTS.md exists, skip this step.

**Step 2 — Search for matching global patterns:**

```bash
# Check if pattern library is initialized
gpd --raw pattern list 2>/dev/null
```

**Step 3 — Review insights for promotion candidates:**

Read `.gpd/INSIGHTS.md` and identify entries that:
- Were confirmed across 2+ phases (high confidence)
- Describe repeatable error patterns, not one-off issues
- Have clear detection and prevention strategies

For each candidate, check if a matching pattern already exists:

```bash
gpd --raw pattern search "keyword from insight" 2>/dev/null
```

**Step 4 — Suggest promotions:**

If promotion candidates found, present them:

```
## Pattern Library: Promote Milestone Insights?

Found {N} confirmed insights that could become global patterns:

1. **{insight title}** — confirmed in phases {X}, {Y}
   Domain: {domain}  Category: {category}
   → `gpd pattern add --domain {domain} --category {category} --title "{title}"`

2. ...

Promote now? (yes / skip / select specific)
```

If user approves, run `pattern add` for each selected insight. If user skips, proceed silently.

**If no candidates found:** Proceed silently (no output needed).

</step>

<step name="reorganize_roadmap_and_delete_originals">

After `milestone complete` has archived, reorganize ROADMAP.md with milestone groupings, then delete originals:

**Reorganize ROADMAP.md** -- group completed milestone phases:

```markdown
# Roadmap: [Research Project Name]

## Milestones

- **v1.0 Model Derivation** -- Phases 1-4 (completed YYYY-MM-DD)
- **v1.1 Validation** -- Phases 5-6 (in progress)

## Phases

<details>
<summary>v1.0 Model Derivation (Phases 1-4) -- COMPLETED YYYY-MM-DD</summary>

- [x] Phase 1: Hamiltonian Setup (2/2 plans) -- completed YYYY-MM-DD
- [x] Phase 2: Mean-Field Solution (2/2 plans) -- completed YYYY-MM-DD

</details>
```

**Then delete original REQUIREMENTS.md after verifying archive exists:**

ROADMAP.md is kept and reorganized (above). REQUIREMENTS.md is deleted -- a fresh one is created for the next milestone.

```bash
# Verify archive exists before deleting original
if [ -f ".gpd/milestones/v${VERSION}-REQUIREMENTS.md" ]; then
  # Use git rm so the deletion is staged for commit (not just a filesystem rm)
  git rm .gpd/REQUIREMENTS.md 2>/dev/null || rm .gpd/REQUIREMENTS.md
else
  echo "ERROR: Archive not found at .gpd/milestones/v${VERSION}-REQUIREMENTS.md. Refusing to delete original."
  exit 1
fi
```

Commit the reorganized roadmap and milestone archive:

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/milestones/ .gpd/ROADMAP.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "chore(milestone-v${VERSION}): reorganize roadmap and retire requirements" \
  --files .gpd/milestones/ .gpd/ROADMAP.md
```

</step>

<step name="update_state">

Most STATE.md updates were handled by `milestone complete`, but verify and update remaining fields:

**Project Reference:**

```markdown
## Project Reference

See: .gpd/PROJECT.md (updated [today])

**Core research question:** [Current core question from PROJECT.md]
**Current focus:** [Next milestone or "Planning next research stage"]
```

**Accumulated Context:**

- Clear decisions summary (full log in DECISIONS.md)
- Clear resolved blockers
- Keep open blockers for next milestone

</step>

<step name="handle_branches">

Check branching strategy and offer merge options.

Use `init milestone-op` for context, or load config directly:

```bash
INIT=$(gpd init milestone-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract `branching_strategy`, `phase_branch_template`, `milestone_branch_template` from init JSON.

**If "none":** Skip to git_tag.

**For "per-phase" strategy:**

```bash
BRANCH_PREFIX=$(echo "$PHASE_BRANCH_TEMPLATE" | sed 's/{.*//')
PHASE_BRANCHES=$(git branch --list "${BRANCH_PREFIX}*" 2>/dev/null | sed 's/^\*//' | tr -d ' ')
```

**For "per-milestone" strategy:**

```bash
BRANCH_PREFIX=$(echo "$MILESTONE_BRANCH_TEMPLATE" | sed 's/{.*//')
MILESTONE_BRANCH=$(git branch --list "${BRANCH_PREFIX}*" 2>/dev/null | sed 's/^\*//' | tr -d ' ' | head -1)
```

**If no branches found:** Skip to git_tag.

**If branches exist:**

```
## Git Branches Detected

Branching strategy: {per-phase/per-milestone}
Branches: {list}

Options:
1. **Merge to main** -- Merge branch(es) to main
2. **Delete without merging** -- Already merged or not needed
3. **Keep branches** -- Leave for manual handling
```

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

ask_user with options: Squash merge (Recommended), Merge with history, Delete without merging, Keep branches.

**Squash merge:**

```bash
CURRENT_BRANCH=$(git branch --show-current)
git checkout main

if [ "$BRANCHING_STRATEGY" = "per-phase" ]; then
  for branch in $PHASE_BRANCHES; do
    git merge --squash "$branch"
    git commit -m "feat: $branch for v[X.Y]"
  done
fi

if [ "$BRANCHING_STRATEGY" = "per-milestone" ]; then
  git merge --squash "$MILESTONE_BRANCH"
  git commit -m "feat: $MILESTONE_BRANCH for v[X.Y]"
fi

git checkout "$CURRENT_BRANCH"
```

**Merge with history:**

```bash
CURRENT_BRANCH=$(git branch --show-current)
git checkout main

if [ "$BRANCHING_STRATEGY" = "per-phase" ]; then
  for branch in $PHASE_BRANCHES; do
    git merge --no-ff "$branch" -m "Merge branch '$branch' for v[X.Y]"
  done
fi

if [ "$BRANCHING_STRATEGY" = "per-milestone" ]; then
  git merge --no-ff "$MILESTONE_BRANCH" -m "Merge branch '$MILESTONE_BRANCH' for v[X.Y]"
fi

git checkout "$CURRENT_BRANCH"
```

**Delete without merging:**

```bash
if [ "$BRANCHING_STRATEGY" = "per-phase" ]; then
  for branch in $PHASE_BRANCHES; do
    git branch -d "$branch" 2>/dev/null || git branch -D "$branch"
  done
fi

if [ "$BRANCHING_STRATEGY" = "per-milestone" ]; then
  git branch -d "$MILESTONE_BRANCH" 2>/dev/null || git branch -D "$MILESTONE_BRANCH"
fi
```

**Keep branches:** Report "Branches preserved for manual handling"

</step>

<step name="git_tag">

Create git tag:

```bash
git tag -a v[X.Y] -m "v[X.Y] [Name]

Completed: [One sentence summary of research achieved]

Key findings:
- [Finding 1]
- [Finding 2]
- [Finding 3]

See .gpd/MILESTONES.md for full details."
```

Confirm: "Tagged: v[X.Y]"

Ask: "Push tag to remote? (y/n)"

If yes:

```bash
git push origin v[X.Y]
```

</step>

<step name="git_commit_milestone">

Commit milestone completion. Only include files that exist (MILESTONE-AUDIT.md is optional — only present if `/gpd:audit-milestone` was run beforehand).

Build the file list, conditionally including MILESTONE-AUDIT.md if it exists:

```bash
COMMIT_FILES=".gpd/milestones/v[X.Y]-ROADMAP.md .gpd/milestones/v[X.Y]-REQUIREMENTS.md .gpd/milestones/v[X.Y]/RESEARCH-DIGEST.md .gpd/MILESTONES.md .gpd/PROJECT.md .gpd/STATE.md"

if [ -f ".gpd/milestones/v[X.Y]-MILESTONE-AUDIT.md" ]; then
  COMMIT_FILES="$COMMIT_FILES .gpd/milestones/v[X.Y]-MILESTONE-AUDIT.md"
fi

PRE_CHECK=$(gpd pre-commit-check --files $COMMIT_FILES 2>&1) || true
echo "$PRE_CHECK"

gpd commit "chore: complete v[X.Y] research milestone" --files $COMMIT_FILES
```

Confirm: "Committed: chore: complete v[X.Y] research milestone"

</step>

<step name="offer_next">

```
Milestone v[X.Y] [Name] complete

Research completed:
- [N] phases ([M] plans, [P] tasks)
- [One sentence of key finding / research outcome]

Archived:
- milestones/v[X.Y]-ROADMAP.md
- milestones/v[X.Y]-REQUIREMENTS.md
- milestones/v[X.Y]/RESEARCH-DIGEST.md

Summary: .gpd/MILESTONES.md
Tag: v[X.Y]

---

## > Next Up

**Start Next Research Stage** -- new questions -> literature review -> requirements -> roadmap

`/gpd:new-milestone`

<sub>`/clear` first -> fresh context window</sub>

---
```

</step>

</process>

<milestone_naming>

**Version conventions:**

- **v1.0** -- Initial model/derivation complete
- **v1.1, v1.2** -- Refinements, additional analysis, new parameter regimes
- **v2.0, v3.0** -- Major extensions, new methods, fundamentally different approach

**Names:** Short 1-2 words (v1.0 Model Derivation, v1.1 Validation, v1.2 Parameter Sweep, v2.0 Beyond Mean-Field).

</milestone_naming>

<what_qualifies>

**Create milestones for:** Complete derivation of key result, validated numerical implementation, systematic parameter study complete, paper draft ready, comparison with literature complete.

**Do not create milestones for:** Every phase completion (too granular), work in progress, exploratory calculations (unless they produce a definitive result).

Heuristic: "Is this a complete, self-contained research result that could be presented or published?" If yes -> milestone. If no -> keep working.

</what_qualifies>

<success_criteria>

Milestone completion is successful when:

- [ ] MILESTONES.md entry created with stats and accomplishments
- [ ] RESEARCH-DIGEST.md generated with narrative arc, key results, methods, conventions, figures, open questions, and dependency graph
- [ ] PROJECT.md full evolution review completed
- [ ] All completed requirements moved to Validated in PROJECT.md
- [ ] Key Decisions updated with outcomes
- [ ] ROADMAP.md reorganized with milestone grouping
- [ ] Roadmap archive created (milestones/v[X.Y]-ROADMAP.md)
- [ ] Requirements archive created (milestones/v[X.Y]-REQUIREMENTS.md)
- [ ] REQUIREMENTS.md deleted (fresh for next research stage)
- [ ] STATE.md updated with fresh project reference
- [ ] Pattern promotion reviewed (INSIGHTS.md checked, candidates offered for `pattern add`)
- [ ] Git tag created (v[X.Y])
- [ ] Milestone commit made (includes archive files and deletion)
- [ ] Researcher knows next step (/gpd:new-milestone)

</success_criteria>

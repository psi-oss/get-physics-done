<purpose>
Create a git branch for parallel investigation of an alternative hypothesis or approach. Sets up isolated research state with hypothesis documentation, enabling side-by-side comparison later via /gpd:compare-branches. Common in physics when multiple approximation schemes, gauge choices, or derivation pathways need to be compared systematically.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="init" priority="first">
Load project context:

```bash
INIT=$(gpd init phase-op --include state,config "${PHASE_ARG:-}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `phase_dir`, `phase_number`, `state_exists`, `roadmap_exists`, `commit_docs`.
This command requires project context because it forks hypothesis state from the active roadmap and STATE.md.
</step>

<step name="parse_arguments">
Parse the hypothesis description from command arguments.

Example: `/gpd:branch-hypothesis Use dimensional regularization instead of hard cutoff`
-> description = "Use dimensional regularization instead of hard cutoff"

If no arguments provided:

```
ERROR: Hypothesis description required
Usage: /gpd:branch-hypothesis <description>
Example: /gpd:branch-hypothesis Use dimensional regularization instead of hard cutoff
```

Exit.
</step>

<step name="generate_slug">
Generate a branch slug from the description:

1. Take the description string
2. Convert to lowercase
3. Replace non-alphanumeric characters with hyphens
4. Collapse multiple hyphens to single
5. Trim leading/trailing hyphens
6. Truncate to 50 characters (at word boundary)

Example: "Use dimensional regularization instead of hard cutoff"
-> slug = "use-dimensional-regularization-instead-of-hard"
</step>

<step name="verify_git_state">
Verify the repository is in a clean state for branching:

```bash
# Check for uncommitted changes
git status --porcelain
```

**If uncommitted changes exist:**

Offer to stash instead of hard-failing:

```
Uncommitted changes detected:
{list of files from git status}

Options:
1. "Stash changes" — Auto-stash and continue
2. "Abort" — I'll handle this manually
```

**If "Stash changes":**

```bash
git stash push -m "gpd: auto-stash before hypothesis branch ${SLUG}"
```

Inform user: "Changes stashed. Recover later with `git stash pop`."
Continue to create_branch.

**If "Abort":** Exit.

Record the current branch name for the hypothesis metadata:

```bash
PARENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
```

</step>

<step name="create_branch">
Create the hypothesis branch:

```bash
git checkout -b "hypothesis/${SLUG}"
```

**If branch already exists:**

```
ERROR: Branch hypothesis/{slug} already exists.
Either:
1. Switch to it: git checkout hypothesis/{slug}
2. Choose a different description
3. Delete it first: git branch -D hypothesis/{slug}
```

Exit.
</step>

<step name="create_hypothesis_doc">
Create the hypothesis documentation directory and file:

```bash
mkdir -p .gpd/hypotheses/${SLUG}
```

Write `.gpd/hypotheses/${SLUG}/HYPOTHESIS.md`:

```markdown
# Hypothesis: {description}

## Description

{description}

## Motivation

<!-- Why is this alternative worth investigating? -->
<!-- What limitation of the current approach does it address? -->

[To be filled by researcher]

## Expected Outcome

<!-- What do you expect to find if this hypothesis is correct? -->
<!-- What observable difference should exist vs. the main approach? -->

[To be filled by researcher]

## Success Criteria

<!-- How will you know this approach is better/worse/equivalent? -->

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Metadata

- **Parent branch:** {parent_branch}
- **Created:** {YYYY-MM-DD}
- **Status:** Active
- **Current phase:** [same as parent STATE.md current phase]
```

</step>

<step name="populate_hypothesis_doc">
Help the researcher populate the HYPOTHESIS.md placeholders by inferring content from the research context.

**1. Read project context:**

```bash
# Get current phase and project state via gpd CLI
INIT=$(gpd init progress --include roadmap,state)
```

Parse from INIT JSON: `project_exists`, `state_exists`, `current_phase` (object with `number`, `name`, `directory`), `state_content`, `roadmap_content`.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context branch-hypothesis "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Then find the current phase directory:

```bash
CURRENT_PHASE_NUM="${current_phase.number}"
PHASE_DIR=$(gpd --raw phase find "$CURRENT_PHASE_NUM")
if [ $? -ne 0 ]; then
  echo "ERROR: Could not find phase directory for phase $CURRENT_PHASE_NUM"
  # STOP — display the error to the user and do not proceed.
fi
```

Use the file_read tool to read `.gpd/STATE.md`, `.gpd/ROADMAP.md`, and any SUMMARY.md files in the phase directory. If `state_content` and `roadmap_content` were included via `--include`, use those directly instead of re-reading.

**2. Generate draft content for each placeholder section:**

Using the hypothesis description, project state, and latest research results, draft:

- **Motivation:** Infer from the description what limitation of the current approach this addresses. Reference specific results or methods from STATE.md / SUMMARY that motivate the alternative.
- **Expected Outcome:** Based on the hypothesis, predict what observable differences should exist. Be specific: "If dimensional regularization preserves gauge invariance better, we expect the Ward identity violation to decrease from O(epsilon) to O(epsilon^2)."
- **Success Criteria:** Generate 3 concrete, testable criteria derived from the expected outcome. Each criterion should be a checkable statement, not vague: "Energy eigenvalues agree with exact solution to within 1%" not "Results are accurate."

**3. Update HYPOTHESIS.md with drafts:**

Replace the placeholder sections with the generated content, clearly marked as AI-drafted for researcher review:

```markdown
## Motivation

<!-- AI-drafted from project context — review and edit -->

{generated motivation referencing current approach limitations}

## Expected Outcome

<!-- AI-drafted — review and edit -->

{generated expected outcome with specific observables}

## Success Criteria

<!-- AI-drafted — review and edit -->

- [ ] {specific testable criterion 1}
- [ ] {specific testable criterion 2}
- [ ] {specific testable criterion 3}
```

**4. Present to researcher:**

```
Drafted motivation, expected outcome, and success criteria from project context.
Review and edit: .gpd/hypotheses/{slug}/HYPOTHESIS.md

The AI-drafted content is marked with <!-- AI-drafted --> comments.
Edit these sections before proceeding to planning.
```

</step>

<step name="fork_state">
Fork STATE.md to include hypothesis context:

1. Record the hypothesis branch decision via gpd CLI:

```bash
gpd state add-decision --phase "${CURRENT_PHASE_NUM}" --summary "Created hypothesis branch: ${description}" --rationale "Investigating alternative approach on branch hypothesis/${slug}"
```

2. Optionally add a short hypothesis note to `STATE.md` via file_edit tool. After the `## Current Position` section, add:

```markdown
## Active Hypothesis

**Branch:** hypothesis/{slug}
**Description:** {description}
**Parent:** {parent_branch}

This is a hypothesis branch investigating an alternative approach.
Compare results with parent branch via `/gpd:compare-branches`.
```

3. Treat that note as markdown-only context. It is not part of the structured state schema, so it will not be mirrored into `state.json`, and future JSON-driven state rewrites may replace it. The durable record for the hypothesis is the `gpd state add-decision` entry plus `.gpd/hypotheses/${SLUG}/HYPOTHESIS.md`.
   </step>

<step name="commit_setup">
Commit the hypothesis setup.

The `commit` CLI command respects `commit_docs` from `.gpd/config.json` internally — if `commit_docs` is false, the commit is automatically skipped.

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/hypotheses/${SLUG}/HYPOTHESIS.md .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: create hypothesis branch for {slug}" --files .gpd/hypotheses/${SLUG}/HYPOTHESIS.md .gpd/STATE.md
```
</step>

<step name="completion">
Present completion summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > HYPOTHESIS BRANCH CREATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Branch:** hypothesis/{slug}
**Description:** {description}
**Parent:** {parent_branch}
**Hypothesis doc:** .gpd/hypotheses/{slug}/HYPOTHESIS.md

---

## Next Steps

1. **Fill in HYPOTHESIS.md** — document motivation, expected outcome, and success criteria
2. **Plan the phase** using the alternative approach:

   /gpd:plan-phase {current_phase}

   <sub>/clear first -> fresh context window</sub>

3. **Execute and compare** when ready:

   /gpd:compare-branches

---

**Also available:**
- Switch back to parent: `git checkout {parent_branch}`
- List hypothesis branches: `git branch --list 'hypothesis/*'`

---
```

</step>

</process>

<anti_patterns>

- Don't create hypothesis branches for trivial variations (use a parameter sweep instead)
- Don't nest hypothesis branches (hypothesis off hypothesis) — branch from main or the primary research branch
- Don't modify the parent branch's STATE.md — only the copy on this branch
- Don't skip the HYPOTHESIS.md documentation — it's essential for later comparison
- Don't forget to fill in motivation and success criteria before starting work

</anti_patterns>

<success_criteria>
Hypothesis branch creation is complete when:

- [ ] Description parsed and slug generated
- [ ] Git state verified clean
- [ ] Branch `hypothesis/{slug}` created
- [ ] `.gpd/hypotheses/{slug}/HYPOTHESIS.md` created with metadata
- [ ] Motivation, Expected Outcome, and Success Criteria populated from project context (AI-drafted)
- [ ] Structured hypothesis record created (decision entry + HYPOTHESIS.md)
- [ ] Changes committed (if commit_docs enabled)
- [ ] User informed of next steps

</success_criteria>

<overview>
GitHub lifecycle management for GPD research projects -- push timing, branch strategy, PR workflows, deliverable handling, repository hygiene, and tagging conventions.
</overview>

<push_timing>

## Push Timing by Event Type

Push frequency balances backup safety against noise. Not every commit needs an immediate push.

| Event Type | Push? | Rationale |
|---|---|---|
| **init** (project + roadmap created) | YES -- push immediately | Establishes remote backup from first commit; collaborators see project exists |
| **phase complete** (all plans in a phase done) | YES -- push immediately | Natural review boundary; triggers phase-level CI if configured |
| **milestone complete** (all phases done) | YES -- push immediately | Major deliverable boundary; often triggers PR or release |
| **paper draft ready** | YES -- push immediately | Collaborators need access for review; CI can build PDF |
| **final deliverable** | YES -- push immediately | Archive-grade checkpoint; tag should be on remote |
| **task complete** (single task commit) | NO -- batch with plan completion | Per-task pushes create noise; local commits suffice for crash recovery |
| **plan complete** (summary + metadata commit) | OPTIONAL -- push if session ending | Good checkpoint if you are about to close the session |
| **handoff / WIP** | YES -- push immediately | Another session or collaborator may need to resume |

**Rule of thumb:** push at every natural review boundary (init, phase, milestone, paper, final) and whenever you are about to stop working.

</push_timing>

<branch_lifecycle>

## Branch Lifecycle

### Default Branch

All work happens on the repository's default branch (`<default-branch>`) unless one of the conditions below applies. Replace `<default-branch>` with the branch configured as the repository default before using the command examples below. Single-researcher projects rarely need branches.

### Per-Phase Branches

Create a phase branch when:

- Multiple contributors work on different phases concurrently.
- A phase involves risky or exploratory work that may be rolled back entirely.
- CI/CD pipelines are configured to run phase-specific checks.

Naming: `phase/{NN}-{short-name}` (e.g. `phase/03-screening`).

Merge back to the default branch when the phase is complete and verified.

### Per-Milestone Branches

Create a milestone branch when:

- The milestone represents a submission-ready deliverable (paper, dataset release).
- You need a stable snapshot while continuing development on the default branch.

Naming: `milestone/{short-name}` (e.g. `milestone/v1-submission`).

### Cleanup

Delete feature, phase, and milestone branches after merge. Stale branches (no commits for 30+ days, not tagged) should be pruned:

```bash
DEFAULT_BRANCH="<default-branch>"
git branch --merged "$DEFAULT_BRANCH" | grep -vE "^\*|^[[:space:]]*${DEFAULT_BRANCH}$" | xargs -r git branch -d
```

</branch_lifecycle>

<pr_workflow>

## PR Workflow

### When to Create a PR

| Trigger | PR Target | Notes |
|---|---|---|
| Phase complete on a phase branch | default branch | Standard review-and-merge flow |
| Milestone complete | default branch (or release branch) | Include full milestone summary |
| Paper ready for co-author review | default branch or paper branch | Attach rendered PDF as artifact |
| External contribution | default branch | Require full test suite green |

For single-researcher projects on the default branch, PRs are optional. Use them when you want a reviewable record of a phase or milestone.

### PR Description Template

```markdown
## Summary

[1-3 sentence description of what this phase/milestone accomplished]

## Key Results

- [Quantitative result 1 with uncertainty]
- [Quantitative result 2 with uncertainty]

## Phases/Plans Included

- Phase NN Plan MM: [name] -- [status]

## Validation

- [ ] All verification checks pass
- [ ] Dimensional consistency confirmed
- [ ] Limiting cases checked
- [ ] No uncommitted work in phase directories
- [ ] SUMMARY.md files present for all completed plans

## Files Changed

[Brief description of major file additions/changes]
```

### PR Checklist

Before opening or merging a PR, verify:

1. **All plans have SUMMARY.md files.** No orphaned PLANs without completion records.
2. **STATE.md is current.** Position, decisions, and session info reflect the latest work.
3. **ROADMAP.md is updated.** Completed phases marked with dates.
4. **No sensitive data.** API keys, credentials, and large data files excluded.
5. **No stale artifacts.** Temporary files, scratch notebooks, and debug logs removed.
6. **Commit history is clean.** Each commit message follows the `{type}({phase}-{plan}): {description}` format.
7. **CI passes.** If configured, all automated checks are green.

</pr_workflow>

<final_deliverable_handling>

## Final Deliverable Handling

### What Belongs in Git

| Artifact | In Git? | Notes |
|---|---|---|
| Source code (`.py`, `.jl`, `.m`) | YES | Always version-controlled |
| LaTeX source (`.tex`, `.bib`) | YES | Paper source is a first-class deliverable |
| Derivation notes (`.md`, `.tex`) | YES | Research record |
| Small data files (< 1 MB) | YES | Results, parameters, spectra |
| Configuration files | YES | Reproducibility requirement |
| SUMMARY.md, STATE.md, ROADMAP.md | YES | GPD metadata |
| Generated PDF | CONDITIONAL | See PDF handling below |
| Large data files (> 10 MB) | NO | Use git-lfs or external storage |
| Virtual environments | NO | Reproducible from requirements |
| Cache directories | NO | Transient |
| Credentials / API keys | NO | Security risk |

### .gitignore Recommendations

```gitignore
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# LaTeX build artifacts
*.aux
*.log
*.out
*.bbl
*.blg
*.fls
*.fdb_latexmk
*.synctex.gz
*.toc
*.lof
*.lot

# Large / generated data
*.hdf5
*.h5
*.npy
*.npz
data/raw/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Secrets
.env
*.key
credentials.*
```

### PDF Handling

PDFs are the primary deliverable for paper projects but create merge conflicts and inflate repository size.

**Recommended approach:**

1. **Do not commit intermediate PDF builds.** Add `*.pdf` to `.gitignore` during development.
2. **Commit the final PDF at submission/milestone.** Remove the `.pdf` entry from `.gitignore` (or use `git add -f`) for the archive-grade version only.
3. **Tag the final PDF commit** with `paper/v{N}` or `submission/{venue}-{date}`.
4. **CI-built PDFs:** If a CI pipeline builds the PDF, store it as a build artifact rather than committing it. Attach to the GitHub release.

</final_deliverable_handling>

<repository_cleanliness>

## Repository Cleanliness Checks

Run these checks before any push at a review boundary (phase complete, milestone complete, paper submission).

### Automated Checks

```bash
# 1. No uncommitted changes
git status --short
# Expected: empty output

# 2. No untracked files that should be committed
git ls-files --others --exclude-standard
# Expected: only intentionally untracked files (data, caches)

# 3. No large files accidentally staged
git diff --cached --stat | awk '{print $NF}' | sort -rn | head -5
# Expected: no files > 1 MB unless intentional

# 4. Commit message format check
git log --oneline -20 | grep -vE '^[0-9a-f]+ (calc|fix|verify|simplify|sim|data|docs|chore|wip)\('
# Expected: empty output (all commits follow format)

# 5. No secrets in tracked files
git ls-files | xargs grep -l 'PRIVATE_KEY\|SECRET\|PASSWORD\|API_KEY' 2>/dev/null
# Expected: empty output
```

### Manual Checks

- [ ] All PLAN.md files in completed phases have matching SUMMARY.md files
- [ ] STATE.md current position matches actual progress
- [ ] ROADMAP.md phase statuses are accurate
- [ ] No TODO/FIXME/HACK comments left in deliverable code
- [ ] No placeholder text in paper drafts

</repository_cleanliness>

<tagging_conventions>

## Tagging Conventions

Tags create permanent, named snapshots of important project states.

### Tag Format

| Event | Tag Format | Example |
|---|---|---|
| Phase completion | `phase/{NN}-complete` | `phase/03-complete` |
| Milestone completion | `milestone/{name}` | `milestone/v1` |
| Paper submission | `paper/{venue}-{version}` | `paper/prl-v1` |
| Paper revision | `paper/{venue}-{version}` | `paper/prl-v2` |
| Dataset release | `data/{name}-{version}` | `data/spectrum-v1` |
| GPD checkpoint (internal) | `gpd-checkpoint-{description}` | `gpd-checkpoint-phase-03-plan-02-1709312400` |

### Tagging Protocol

1. **Annotated tags for milestones and papers.** Include a message summarizing the state:

```bash
git tag -a milestone/v1 -m "Complete through Phase 05. Key result: critical temperature Tc = 2.27 J/kB."
git tag -a paper/prl-v1 -m "Initial PRL submission. 4 pages, 3 figures."
```

2. **Lightweight tags for phase completions and checkpoints.** These are navigational, not archival:

```bash
git tag phase/03-complete
git tag gpd-checkpoint-phase-03-plan-02-$(date +%s)
```

3. **Push tags explicitly.** Tags are not pushed by default:

```bash
REMOTE_NAME="<remote-name>"
git push "$REMOTE_NAME" <tag-name>
# Or push all tags:
git push "$REMOTE_NAME" --tags
```

4. **Never delete published tags.** If a tag points to incorrect work, create a new tag at the corrected commit rather than moving or deleting the old one.

5. **GPD checkpoint tags are ephemeral.** Clean up `gpd-checkpoint-*` tags after successful plan completion (see `execute-plan-checkpoints.md`).

</tagging_conventions>

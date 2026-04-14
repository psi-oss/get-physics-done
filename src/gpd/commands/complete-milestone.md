---
name: gpd:complete-milestone
description: Archive completed research milestone and prepare for next phase of investigation
argument-hint: <version>
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md"]
allowed-tools:
  - file_read
  - file_write
  - shell
---


<objective>
Mark research milestone {version} complete, archive to milestones/, and update ROADMAP.md and REQUIREMENTS.md.

Purpose: Create a historical record of completed research (e.g., "analytical derivation complete" or "numerical validation done"), archive milestone artifacts (roadmap + requirements), and prepare for the next stage of investigation.
Output: Milestone archived (roadmap + requirements), PROJECT.md evolved, git tagged.
</objective>

<execution_context>
**Load these files NOW (before proceeding):**

- @{GPD_INSTALL_DIR}/workflows/complete-milestone.md (main workflow)
- @{GPD_INSTALL_DIR}/templates/milestone.md (milestone template)
- @{GPD_INSTALL_DIR}/templates/milestone-archive.md (archive template)
  </execution_context>

<context>
**Project files:**
- `GPD/ROADMAP.md`
- `GPD/REQUIREMENTS.md`
- `GPD/STATE.md`
- `GPD/PROJECT.md`

**User input:**

- Version: {version} (e.g., "1.0", "1.1", "2.0")
  </context>

<process>

This wrapper runs the archive workflow directly. Any stopping points come from the workflow's own readiness and confirmation gates.

0. **Check for audit**
   - Confirm `GPD/v{version}-MILESTONE-AUDIT.md` exists and reports `passed`.
   - If missing, run `gpd:audit-milestone`; if it reports `gaps_found`, suggest `gpd:plan-milestone-gaps` before continuing.
   - Only proceed once the audit has no open gaps.

1. **Verify readiness**
   - Ensure every phase in the milestone has a `SUMMARY.md`.
   - Summarize the milestone scope (phase counts, research types) and get user confirmation.

2. **Gather stats**
   - Count phases, plans, and tasks; capture git range, file changes, and LOC; extract the timeline from `git log`.
   - Present that summary and confirm with the user.

3. **Extract accomplishments**
   - Read each phase `SUMMARY.md` in the milestone range.
   - Highlight 4–6 key outcomes (analytical, numerical, novel insights) and get approval before archiving.

4. **Archive milestone**
   - Create `GPD/milestones/v{version}-ROADMAP.md` with the extracted phase details.
   - Collapse `GPD/ROADMAP.md` to a single-line summary that links to the archive.

5. **Archive requirements**
   - Generate `GPD/milestones/v{version}-REQUIREMENTS.md`, mark the checkboxes complete, and record the disposition (validated, adjusted, deferred, ruled out).
   - Delete the old `GPD/REQUIREMENTS.md` only after the archive exists so the next milestone starts clean.
   - Scan `INSIGHTS.md` for confirmed patterns, run `gpd pattern search` for duplicates, and suggest `gpd pattern add` candidates when justified.

6. **Update PROJECT.md**
   - Add a "Current State" section describing the established results.
   - Add "Next Milestone Goals" for the immediate follow-up work.
   - Archive the prior content in `<details>` bubbles when the milestone is v1.1 or later.

7. **Commit and tag**
   - Stage `MILESTONES.md`, `PROJECT.md`, `ROADMAP.md`, `STATE.md`, and the archive files.
   - Commit `chore: archive v{version} research milestone` and tag `v{version}` with a summary message.
   - Ask the user whether to push the tag.

8. **Offer next steps**
   - Recommend `gpd:new-milestone` to start the next research cycle.

</process>

<success_criteria>

- Milestone archived to `GPD/milestones/v{version}-ROADMAP.md`
- Requirements archived to `GPD/milestones/v{version}-REQUIREMENTS.md`
- `GPD/REQUIREMENTS.md` deleted (fresh for next milestone)
- ROADMAP.md collapsed to one-line entry
- PROJECT.md updated with current state of research
- Pattern promotion reviewed (INSIGHTS.md checked for global library candidates)
- Git tag v{version} created
- Commit successful
- User knows next steps (including need for fresh requirements)
  </success_criteria>

<critical_rules>

- **Load workflow first:** Read complete-milestone.md before executing
- **Verify completion:** All phases must have SUMMARY.md files
- **User confirmation:** Wait for approval at verification gates
- **Archive before deleting:** Always create archive files before updating/deleting originals
- **One-line summary:** Collapsed milestone in ROADMAP.md should be single line with link
- **Context efficiency:** Archive keeps ROADMAP.md and REQUIREMENTS.md constant size per milestone
- **Fresh requirements:** Next milestone starts with `gpd:new-milestone` which includes requirements definition
- **Research continuity:** PROJECT.md must capture what was learned, not just what was done, so the next milestone builds on established results
  </critical_rules>

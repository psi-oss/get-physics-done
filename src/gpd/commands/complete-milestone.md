---
name: gpd:complete-milestone
description: Archive completed research milestone and prepare for next phase of investigation
argument-hint: <version>
context_mode: project-required
requires:
  files: [".gpd/ROADMAP.md"]
  recommended: ["audit-milestone"]
allowed-tools:
  - file_read
  - file_write
  - shell
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Mark research milestone {{version}} complete, archive to milestones/, and update ROADMAP.md and REQUIREMENTS.md.

Purpose: Create a historical record of completed research (e.g., "analytical derivation complete" or "numerical validation done"), archive milestone artifacts (roadmap + requirements), and prepare for the next stage of investigation.
Output: Milestone archived (roadmap + requirements), PROJECT.md evolved, git tagged.
</objective>

<execution_context>
**Load these files NOW (before proceeding):**

- @{GPD_INSTALL_DIR}/workflows/complete-milestone.md (main workflow)
- @{GPD_INSTALL_DIR}/templates/milestone-archive.md (archive template)
  </execution_context>

<context>
**Project files:**
- `.gpd/ROADMAP.md`
- `.gpd/REQUIREMENTS.md`
- `.gpd/STATE.md`
- `.gpd/PROJECT.md`

**User input:**

- Version: {{version}} (e.g., "1.0", "1.1", "2.0")
  </context>

<process>

If `--dry-run` flag is present, show what would be archived and deleted (milestone archive files, requirements deletion, roadmap collapse, git tag) without making any changes.

**Follow complete-milestone.md workflow:**

0. **Check for audit:**

   - Look for `.gpd/v{{version}}-MILESTONE-AUDIT.md`
   - If missing or stale: recommend `/gpd:audit-milestone` first
   - If audit status is `gaps_found`: recommend `/gpd:plan-milestone-gaps` first
   - If audit status is `passed`: proceed to step 1

   ```markdown
   ## Pre-flight Check

   {If no v{{version}}-MILESTONE-AUDIT.md:}
   No milestone audit found. Run `/gpd:audit-milestone` first to verify
   research question coverage, derivation completeness, and cross-phase consistency.

   {If audit has gaps:}
   Milestone audit found gaps (e.g., unchecked limits, missing error bars,
   unsupported claims). Run `/gpd:plan-milestone-gaps` to create phases that
   close the gaps, or proceed anyway to defer to the next milestone.

   {If audit passed:}
   Milestone audit passed. Proceeding with completion.
   ```

1. **Verify readiness:**

   - Check all phases in milestone have completed plans (SUMMARY.md exists)
   - Present milestone scope and stats (e.g., "3 analytical phases, 2 numerical phases, 1 literature review")
   - Wait for confirmation

2. **Gather stats:**

   - Count phases, plans, tasks
   - Calculate git range, file changes, LOC
   - Extract timeline from git log
   - Present summary, confirm

3. **Extract accomplishments:**

   - Read all phase SUMMARY.md files in milestone range
   - Extract 4-6 key research accomplishments (e.g., "Derived closed-form expression for spectral gap", "Validated N-scaling numerically up to N=256", "Identified novel crossover regime at intermediate coupling")
   - Present for approval

4. **Archive milestone:**

   - Create `.gpd/milestones/v{{version}}-ROADMAP.md`
   - Extract full phase details from ROADMAP.md
   - Fill milestone-archive.md template
   - Update ROADMAP.md to one-line summary with link

5. **Archive requirements:**

   - Create `.gpd/milestones/v{{version}}-REQUIREMENTS.md`
   - Mark all requirements for this milestone as complete (checkboxes checked)
   - Note requirement outcomes (validated, adjusted, deferred, ruled out by physics)
   - Delete `.gpd/REQUIREMENTS.md` (fresh one created for next milestone)

5b. **Promote patterns:**

   - Check INSIGHTS.md for confirmed patterns (2+ phases, clear detection/prevention)
   - Run `gpd pattern search` to check for duplicates
   - Suggest `gpd pattern add` for promotion candidates
   - Skip silently if no INSIGHTS.md or no candidates

6. **Update PROJECT.md:**

   - Add "Current State" section describing what has been established so far
   - Add "Next Milestone Goals" section (e.g., "extend to finite temperature", "incorporate disorder", "draft manuscript")
   - Archive previous content in `<details>` (if v1.1+)

7. **Commit and tag:**

   Note: MILESTONES.md is CREATED by `gpd milestone complete` during this workflow. It does not need to exist beforehand.

   - Stage: MILESTONES.md, PROJECT.md, ROADMAP.md, STATE.md, archive files
   - Commit: `chore: archive v{{version}} research milestone`
   - Tag: `git tag -a v{{version}} -m "[milestone summary]"`
   - Ask about pushing tag

8. **Offer next steps:**
   - `/gpd:new-milestone` — start next research milestone (questioning -> literature review -> requirements -> roadmap)

</process>

<success_criteria>

- Milestone archived to `.gpd/milestones/v{{version}}-ROADMAP.md`
- Requirements archived to `.gpd/milestones/v{{version}}-REQUIREMENTS.md`
- `.gpd/REQUIREMENTS.md` deleted (fresh for next milestone)
- ROADMAP.md collapsed to one-line entry
- PROJECT.md updated with current state of research
- Pattern promotion reviewed (INSIGHTS.md checked for global library candidates)
- Git tag v{{version}} created
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
- **Fresh requirements:** Next milestone starts with `/gpd:new-milestone` which includes requirements definition
- **Research continuity:** PROJECT.md must capture what was learned, not just what was done, so the next milestone builds on established results
  </critical_rules>

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

This wrapper owns the public command surface and required version argument. The workflow owns audit/readiness checks, milestone statistics, archive generation, PROJECT.md evolution, MILESTONES.md updates, commit/tag behavior, and next-step routing.
</objective>

<execution_context>
**Load these files NOW (before proceeding):**

- @{GPD_INSTALL_DIR}/workflows/complete-milestone.md (main workflow)
- @{GPD_INSTALL_DIR}/templates/milestone.md (milestone template)
- @{GPD_INSTALL_DIR}/templates/milestone-archive.md (archive template)
  </execution_context>

<context>
**User input:**

- Version: {version} (e.g., "1.0", "1.1", "2.0")

Primary outputs remain workflow-owned:

- `GPD/milestones/v{version}-ROADMAP.md`
- `GPD/milestones/v{version}-REQUIREMENTS.md`
  </context>

<process>
Follow the included complete-milestone workflow end-to-end after loading the execution-context files above.

Use the workflow's readiness, audit, confirmation, archive, commit, and tag gates as the authority. The wrapper must not restate or fork those mechanics.

</process>

<success_criteria>

- Milestone archived to `GPD/milestones/v{version}-ROADMAP.md`
- Requirements archived to `GPD/milestones/v{version}-REQUIREMENTS.md`
- Complete-milestone workflow executed as the authority for readiness, archive, commit, tag, and next-step mechanics
  </success_criteria>

<critical_rules>

- **Load workflow first:** Read complete-milestone.md before executing
- **Do not fork workflow gates:** Audit, readiness, archive-before-delete, commit, tag, and next-milestone routing come from the workflow
  </critical_rules>

---
name: gpd:new-milestone
description: Start a new research milestone cycle — update PROJECT.md and route to requirements
argument-hint: "[milestone name, e.g., 'v1.1 Finite-Temperature Extension']"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - task
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Start a new research milestone: questioning → literature research (optional) → requirements → roadmap.

Continuation equivalent of new-project. Research project exists, PROJECT.md has history. Gathers "what's next", updates PROJECT.md, then runs requirements → roadmap cycle.

**Creates/Updates:**

- `.gpd/PROJECT.md` — updated with new milestone goals
- `.gpd/research/` — domain and literature research (optional, NEW research objectives only)
- `.gpd/REQUIREMENTS.md` — scoped requirements for this milestone
- `.gpd/ROADMAP.md` — phase structure (continues numbering)
- `.gpd/STATE.md` — reset for new milestone

**After:** `/gpd:plan-phase [N]` to start execution.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/new-milestone.md
@{GPD_INSTALL_DIR}/references/research/questioning.md
@{GPD_INSTALL_DIR}/references/ui/ui-brand.md
@{GPD_INSTALL_DIR}/templates/project.md
@{GPD_INSTALL_DIR}/templates/requirements.md
</execution_context>

<context>
Milestone name: $ARGUMENTS (optional - will prompt if not provided)

**Load project context:**
@.gpd/PROJECT.md
@.gpd/STATE.md
@.gpd/MILESTONES.md
@.gpd/config.json

**Load milestone context (if exists, from /gpd:discuss-phase):**
@.gpd/MILESTONE-CONTEXT.md
</context>

<process>
**Follow the new-milestone workflow** from `@{GPD_INSTALL_DIR}/workflows/new-milestone.md`.

**Argument parsing:**

- `$ARGUMENTS` → milestone name (optional, will prompt if not provided)
- Parse milestone name from arguments if present

**Flags:** None currently defined.

The workflow handles the full milestone initialization flow:

1. Load existing project context (PROJECT.md, MILESTONES.md, STATE.md)
2. Gather milestone goals (from MILESTONE-CONTEXT.md or user questioning)
3. Determine milestone version (auto-increment from MILESTONES.md)
4. Update PROJECT.md and STATE.md
5. Optional literature survey (4 parallel researcher agents)
6. Define research requirements (category scoping, REQ-IDs)
7. Create research roadmap (gpd-roadmapper agent)
8. Commit all artifacts
9. Present next steps (`/gpd:discuss-phase [N]` or `/gpd:plan-phase [N]`)

All gates (validation, questioning, research, requirements, roadmap approval, commits) are preserved in the workflow.
</process>

<success_criteria>

- [ ] PROJECT.md updated with Current Milestone section
- [ ] STATE.md reset for new milestone
- [ ] MILESTONE-CONTEXT.md consumed and deleted (if existed)
- [ ] Literature survey completed (if selected) — 4 parallel agents, milestone-aware
- [ ] Research requirements gathered and scoped per category
- [ ] REQUIREMENTS.md created with REQ-IDs
- [ ] gpd-roadmapper spawned with phase numbering context
- [ ] Roadmap files written immediately (not draft)
- [ ] User feedback incorporated (if any)
- [ ] ROADMAP.md phases continue from previous milestone
- [ ] All commits made (if planning docs committed)
- [ ] User knows next step: `/gpd:discuss-phase [N]`

**Atomic commits:** Each phase commits its artifacts immediately.
</success_criteria>

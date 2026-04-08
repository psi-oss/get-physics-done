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


<objective>
Start a new research milestone: questioning → literature research (optional) → requirements → roadmap.

Continuation equivalent of new-project. Research project exists, PROJECT.md has history. Gathers "what's next", updates PROJECT.md, then runs requirements → roadmap cycle while honoring `planning.commit_docs` for milestone artifact commits.

**Creates/Updates:**

- `GPD/PROJECT.md` — updated with new milestone goals
- `GPD/literature/` — domain and literature survey (optional, NEW research objectives only)
- `GPD/REQUIREMENTS.md` — scoped requirements for this milestone
- `GPD/ROADMAP.md` — phase structure (continues numbering)
- `GPD/STATE.md` — reset for new milestone

**After:** `gpd:plan-phase [N]` to start execution.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/new-milestone.md
</execution_context>

<context>
Milestone name: $ARGUMENTS (optional - will prompt if not provided)

**Load project context:**
@GPD/PROJECT.md
@GPD/STATE.md
@GPD/MILESTONES.md
@GPD/config.json

**Load milestone context (if exists, from gpd:discuss-phase):**
@GPD/MILESTONE-CONTEXT.md
</context>

<process>
**Follow the new-milestone workflow** from `@{GPD_INSTALL_DIR}/workflows/new-milestone.md`.

Load late-stage authorities only when the workflow reaches the matching stage:
- Read {GPD_INSTALL_DIR}/references/research/questioning.md only when you need guided milestone questioning.
- Read {GPD_INSTALL_DIR}/templates/project.md only when updating `GPD/PROJECT.md`.
- Read {GPD_INSTALL_DIR}/templates/requirements.md only when writing `GPD/REQUIREMENTS.md`.
- Read {GPD_INSTALL_DIR}/references/ui/ui-brand.md only when rendering branded completion or status blocks.

**Argument parsing:**

- `$ARGUMENTS` → milestone name (optional, will prompt if not provided)
- Parse milestone name from arguments if present

**Flags:** None currently defined.
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
- [ ] All commits made when `planning.commit_docs` is true
- [ ] User knows next step: `gpd:discuss-phase [N]`

**Atomic commits:** Each phase commits its artifacts immediately.
</success_criteria>

---
template_version: 1
---

# Roadmap Template

Template for `GPD/ROADMAP.md`.

## Initial Roadmap (First Paper / New Project)

```markdown
# Roadmap: [Research Project Title]

## Overview

[One paragraph describing the project goals, the objective-driven phase structure, and the expected outcome]

## Contract Overview

| Contract Item | Advanced By Phase(s) | Status |
| ------------- | -------------------- | ------ |
| [claim / deliverable / anchor label] | [Phase 1, Phase 3] | [Planned] |

## Phases

Choose only the phases this project actually needs. Phase names should come from the research objectives and dependencies, not from a fixed literature/formalism/calculation/paper sequence.

- [ ] **Phase 1: [Objective-driven phase title]** - [One-line outcome]
- [ ] **Phase 2: [Objective-driven phase title]** - [One-line outcome]
- [ ] **Phase N: [Add only if needed]** - [One-line outcome]

## Phase Details

### Phase [N]: [Phase Title]

**Goal:** [State the physics outcome this phase must achieve]
**Depends on:** [Nothing or the upstream phase]
**Requirements:** [REQ-01, REQ-02]
**Contract Coverage:**
- Advances: [claim / deliverable labels]
- Deliverables: [artifact, note, figure, derivation]
- Anchor coverage: [must-read refs, prior outputs, decisive baselines]
- Forbidden proxies: [what should NOT count as success here]
**Success Criteria** (what must be TRUE):

1. [Outcome that can be checked from the resulting artifact]
2. [Independent check, comparison, or constraint]
3. [Any regime or coverage requirement the phase must satisfy]
   **Plans:** [Number of plans, or "TBD" if the count is not yet known]

Plans:

- [ ] [N]-01: [Short task description]
- [ ] [N]-02: [Short task description]
- [ ] [N]-03: [Short task description]
- [ ] [Add only if needed]

### Alternative: stub phase block (when `shallow_mode=true` for Phases 2+)

Use this shape for Phases 2+ when the initial roadmap is authored in shallow mode. The researcher fleshes each stub out later via `gpd:plan-phase N`.

### Phase [N]: [Phase Title]

**Goal:** [one-line outcome]
**Plans:** 0 plans

- [ ] TBD (run plan-phase [N] to break down)

## Progress

**Execution Order:**
Phases execute in numeric order: 2 -> 2.1 -> 2.2 -> 3 -> 3.1 -> 4

| Phase                        | Plans Complete | Status      | Completed |
| ---------------------------- | -------------- | ----------- | --------- |
| 1. [Phase title]             | 0/2            | Not started | -         |
| 2. [Phase title]             | 0/3            | Not started | -         |
| 3. [Phase title]             | 0/3            | Not started | -         |
| 4. [Phase title]             | 0/2            | Not started | -         |
| 5. [Phase title]             | 0/2            | Not started | -         |
```

<guidelines>
**Initial planning (first paper):**
- Phase count depends on depth setting (quick: 3-5, standard: 5-8, comprehensive: 8-12)
- Shallow mode (`shallow_mode=true`, used by `gpd:new-project` standard mode by default): Phase 1 carries the full detail block; Phases 2+ carry only the stub block above. The researcher runs `gpd:plan-phase N` to flesh each subsequent phase out when its turn comes.
- Each phase delivers a coherent body of results
- Phase titles should be objective-driven, not template-driven
- Phases can have 1+ plans (split if >3 tasks or multiple independent calculations)
- Plans use naming: {phase}-{plan}-PLAN.md (e.g., 01-02-PLAN.md)
- No time estimates (research timelines are inherently unpredictable)
- Progress table updated by execute workflow
- Plan count can be "TBD" initially, refined during planning

**Success criteria:**

- 2-5 observable outcomes per phase (from the researcher's perspective)
- Cross-checked against requirements during roadmap creation
- Flow downstream to plan `contract` directly in plan-phase
- Verified by verify-phase after execution
- Format: "[Result] obtained/derived/verified" or "[Comparison] shows agreement"

**After milestones complete:**

- Collapse completed milestones in `<details>` tags
- Add new milestone sections for upcoming work
- Keep continuous phase numbering (never restart at 01)
  </guidelines>

<status_values>

- `Not started` - Haven't begun
- `Planning` - Creating execution plans
- `Researching` - Literature review or domain research in progress
- `Ready to execute` - Plans exist, ready for execution
- `Executing` - Actively running plans
- `Paused` - Temporarily halted (with reason)
- `Phase complete — ready for verification` - Awaiting verification checks
- `Verifying` - Running verification checks
- `Verified` - Verification passed
- `Complete` - Done and verified (add completion date)
- `Blocked` - Waiting on prerequisite result or external input
- `Ready to plan` - Context gathered, ready for planning
- `Milestone complete` - All phases in milestone finished
  </status_values>

## Milestone-Grouped Roadmap (After First Paper Submitted)

After completing first milestone, reorganize with milestone groupings:

```markdown
# Roadmap: [Research Project Title]

## Milestones

- Done: **Paper I** - Phases 1-5 (submitted YYYY-MM-DD)
- Active: **Paper I Revisions** - Phases 6-7 (in progress)
- Planned: **Paper II: [Extension]** - Phases 8-12 (planned)

## Phases

<details>
<summary>Done: Paper I (Phases 1-5) - SUBMITTED YYYY-MM-DD</summary>

### Phase 1: [Project-specific phase title]

**Goal:** [State the outcome achieved by this phase]
**Plans:** 2 plans

Plans:

- [x] 01-01: [Brief description]
- [x] 01-02: [Brief description]

[... remaining Paper I phases ...]

</details>

### Active: Paper I Revisions (In Progress)

**Milestone Goal:** [Address referee comments and strengthen results]

#### Phase 6: Referee Response

**Goal:** [Address all referee comments with the needed follow-up work]
**Depends on:** Phase 5
**Plans:** 2 plans

Plans:

- [ ] 06-01: [e.g., Additional calculation requested by Referee 1]
- [ ] 06-02: [e.g., Extended comparison requested by Referee 2]

[... remaining revision phases ...]

### Planned: Paper II: [Extension] (Planned)

**Milestone Goal:** [Extend results to new regime / higher order / different system]

[... Paper II phases ...]

## Progress

| Phase                | Milestone | Plans Complete | Status      | Completed  |
| -------------------- | --------- | -------------- | ----------- | ---------- |
| 1. [Phase title]     | Paper I   | 2/2            | Complete    | YYYY-MM-DD |
| 2. [Phase title]     | Paper I   | 3/3            | Complete    | YYYY-MM-DD |
| 6. Referee Response  | Revisions | 0/2            | Not started | -          |
```

**Notes:**

- Milestone labels: Done (submitted/published), Active (in progress), Planned (future)
- Completed milestones collapsed in `<details>` for readability
- Current/future milestones expanded
- Continuous phase numbering (01-99)
- Progress table includes milestone column

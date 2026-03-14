---
template_version: 1
---

# Roadmap Template

Template for `.gpd/ROADMAP.md`.

## Initial Roadmap (First Paper / New Project)

```markdown
# Roadmap: [Research Project Title]

## Overview

[One paragraph describing the research journey from literature review to submitted paper]

## Contract Overview

| Contract Item | Advanced By Phase(s) | Status |
| ------------- | -------------------- | ------ |
| [claim / deliverable / anchor label] | [Phase 1, Phase 3] | [Planned] |

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned research work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Literature Review** - [One-line description of review scope]
- [ ] **Phase 2: Formalism Development** - [One-line description of theoretical framework]
- [ ] **Phase 3: Calculation / Simulation** - [One-line description of core computation]
- [ ] **Phase 4: Validation & Cross-checks** - [One-line description of verification approach]
- [ ] **Phase 5: Paper Writing** - [One-line description of manuscript scope]

## Phase Details

### Phase 1: Literature Review

**Goal:** Establish the state of the art and identify the gap this work fills
**Depends on:** Nothing (first phase)
**Requirements:** [REQ-01, REQ-02]
**Contract Coverage:**
- Advances: [claim / deliverable labels]
- Deliverables: [survey note, comparison table, baseline artifact]
- Anchor coverage: [must-read refs, prior outputs, decisive baselines]
- Forbidden proxies: [what should NOT count as success here]
**Success Criteria** (what must be TRUE):

1. [Key prior results catalogued with their limitations identified]
2. [Research gap clearly articulated and distinct from existing work]
3. [Relevant methods and formalisms identified for adaptation]
   **Plans:** [Number of plans, e.g., "2 plans" or "TBD"]

Plans:

- [ ] 01-01: [e.g., Survey recent papers on topic X]
- [ ] 01-02: [e.g., Catalogue known results and identify discrepancies]

### Phase 2: Formalism Development

**Goal:** Develop the mathematical framework for the calculation
**Depends on:** Phase 1
**Requirements:** [DERV-01, DERV-02, DERV-03]
**Contract Coverage:**
- Advances: [claim / deliverable labels]
- Deliverables: [derivation, conventions note, benchmark equation]
- Anchor coverage: [benchmark refs, prior summaries, required baselines]
- Forbidden proxies: [e.g. algebra completed without decisive comparison]
**Success Criteria** (what must be TRUE):

1. [Starting Lagrangian/Hamiltonian written down with all terms justified]
2. [Approximation scheme defined with controlled expansion parameter identified]
3. [Key equations derived and verified in known limits]
   **Plans:** [Number of plans]

Plans:

- [ ] 02-01: [e.g., Construct effective Hamiltonian]
- [ ] 02-02: [e.g., Derive perturbative expansion to required order]
- [ ] 02-03: [e.g., Verify symmetry constraints and Ward identities]

### Phase 2.1: Formalism Correction (INSERTED)

**Goal:** [Address issue discovered during formalism development]
**Depends on:** Phase 2
**Contract Coverage:**
- Advances: [claim / deliverable labels]
- Deliverables: [correction note, replacement derivation, revised benchmark]
- Anchor coverage: [refreshed anchor set or prior outputs that stay decisive]
- Forbidden proxies: [what false progress this inserted phase prevents]
**Success Criteria** (what must be TRUE):

1. [What the correction achieves]
   **Plans:** 1 plan

Plans:

- [ ] 02.1-01: [Description]

### Phase 3: Calculation / Simulation

**Goal:** Obtain the main quantitative results of the project
**Depends on:** Phase 2
**Requirements:** [CALC-01, CALC-02, SIMU-01, SIMU-02]
**Contract Coverage:**
- Advances: [claim / deliverable labels]
- Deliverables: [figure, dataset, report, derivation]
- Anchor coverage: [benchmarks, baselines, prior outputs, must-read refs]
- Forbidden proxies: [e.g. qualitative agreement without decisive measurement]
**Success Criteria** (what must be TRUE):

1. [Core calculation complete with results in tabular/graphical form]
2. [Numerical results converged to required accuracy]
3. [Parameter dependence mapped out over specified range]
   **Plans:** [Number of plans]

Plans:

- [ ] 03-01: [e.g., Implement numerical solver for RG equations]
- [ ] 03-02: [e.g., Run Monte Carlo simulations at target parameters]
- [ ] 03-03: [e.g., Perform finite-size scaling analysis]

### Phase 4: Validation & Cross-checks

**Goal:** Confirm results are correct via independent checks
**Depends on:** Phase 3
**Requirements:** [VALD-01, VALD-02, VALD-03]
**Contract Coverage:**
- Advances: [claim / deliverable labels]
- Deliverables: [comparison figure, benchmark table, verification note]
- Anchor coverage: [literature anchors, prior artifacts, baseline checks]
- Forbidden proxies: [e.g. passing internal consistency only]
**Success Criteria** (what must be TRUE):

1. [Known limiting cases reproduced to required accuracy]
2. [Independent calculation methods agree within error bars]
3. [Results consistent with experimental/literature data where available]
   **Plans:** [Number of plans]

Plans:

- [ ] 04-01: [e.g., Verify limiting cases against known results]
- [ ] 04-02: [e.g., Compare analytic and numerical approaches]

### Phase 5: Paper Writing

**Goal:** Produce a publication-ready manuscript
**Depends on:** Phase 4
**Requirements:** [PAPR-01, PAPR-02]
**Contract Coverage:**
- Advances: [claim / deliverable labels]
- Deliverables: [paper draft, figure set, response note]
- Anchor coverage: [citations, benchmark references, prior outputs to cite]
- Forbidden proxies: [e.g. polished prose without decisive result traceability]
**Success Criteria** (what must be TRUE):

1. [Manuscript complete with all figures and tables]
2. [All results clearly presented with error estimates]
3. [Introduction motivates the work and conclusion summarizes findings]
   **Plans:** [Number of plans]

Plans:

- [ ] 05-01: [e.g., Draft results and methods sections]
- [ ] 05-02: [e.g., Write introduction, conclusion, and abstract]

## Progress

**Execution Order:**
Phases execute in numeric order: 2 -> 2.1 -> 2.2 -> 3 -> 3.1 -> 4

| Phase                        | Plans Complete | Status      | Completed |
| ---------------------------- | -------------- | ----------- | --------- |
| 1. Literature Review         | 0/2            | Not started | -         |
| 2. Formalism Development     | 0/3            | Not started | -         |
| 3. Calculation / Simulation  | 0/3            | Not started | -         |
| 4. Validation & Cross-checks | 0/2            | Not started | -         |
| 5. Paper Writing             | 0/2            | Not started | -         |
```

<guidelines>
**Initial planning (first paper):**
- Phase count depends on depth setting (quick: 3-5, standard: 5-8, comprehensive: 8-12)
- Each phase delivers a coherent body of results
- Standard physics research flow: Literature -> Formalism -> Calculation -> Validation -> Paper
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
- `Ready to plan` - Context gathered, ready for planning
- `Planning` - Creating execution plans
- `Researching` - Literature review or domain research in progress
- `Ready to execute` - Plans exist, ready for execution
- `Executing` - Actively running plans
- `Paused` - Temporarily halted (with reason)
- `Phase complete` - All plans executed
- `Phase complete — ready for verification` - Awaiting verification checks
- `Verifying` - Running verification checks
- `Complete` - Done and verified (add completion date)
- `Blocked` - Waiting on prerequisite result or external input
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

### Phase 1: Literature Review

**Goal:** Establish the state of the art
**Plans:** 2 plans

Plans:

- [x] 01-01: [Brief description]
- [x] 01-02: [Brief description]

[... remaining Paper I phases ...]

</details>

### Active: Paper I Revisions (In Progress)

**Milestone Goal:** [Address referee comments and strengthen results]

#### Phase 6: Referee Response

**Goal:** [Address all referee comments with additional calculations]
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
| 1. Literature Review | Paper I   | 2/2            | Complete    | YYYY-MM-DD |
| 2. Formalism         | Paper I   | 3/3            | Complete    | YYYY-MM-DD |
| 6. Referee Response  | Revisions | 0/2            | Not started | -          |
```

**Notes:**

- Milestone labels: Done (submitted/published), Active (in progress), Planned (future)
- Completed milestones collapsed in `<details>` for readability
- Current/future milestones expanded
- Continuous phase numbering (01-99)
- Progress table includes milestone column

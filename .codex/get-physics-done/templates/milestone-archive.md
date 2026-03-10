---
template_version: 1
---

<!-- For the concise milestone log entry format, see milestone.md -->

# Milestone Archive Template

This template is used by the complete-milestone workflow to create archive files in `.gpd/milestones/`.

---

## File Template

# Milestone: {milestone_name}

**Status:** Completed {date}
**Phases:** {phase_start}-{phase_end}
**Total Plans:** {total_plans}

## Overview

{milestone_description}

## Phases

{phases_section}

[For each phase in this milestone, include:]

### Phase {phase_num}: {phase_name}

**Goal:** {phase_goal}
**Depends on:** {depends_on}
**Plans:** {plan_count} plans

Plans:

- [x] {phase}-01: {plan_description}
- [x] {phase}-02: {plan_description}
      [... all plans ...]

**Details:**
{phase_details_from_roadmap}

**For decimal phases, include (INSERTED) marker:**

### Phase 2.1: Regularization Fix (INSERTED)

**Goal:** Fix divergence in loop integral discovered during calculation
**Depends on:** Phase 2
**Plans:** 1 plan

Plans:

- [x] 02.1-01: Implement dimensional regularization for problematic integral

**Details:**
{phase_details_from_roadmap}

---

## Milestone Summary

**Key Results:**
{key_results_from_milestone}
[Example:]

- Derived RG flow equations for long-range XY model (Eqs. 15-17 in notebook 02-03)
- Identified critical alpha_c = 2.32(5) from finite-size scaling
- T_c(alpha) curve mapped for alpha in [1.5, 4.0]

**Key Equations:**
{central_equations_and_values}
[Example:]

- T_c(alpha)/T_BKT = 1 - 0.47(3) \* (alpha - 2.32)^{0.51(4)} near alpha_c
- Universal helicity modulus jump confirmed: Delta_rho = 2T_c/pi

**Decimal Phases:**

- Phase 2.1: Regularization Fix (inserted after Phase 2 for UV divergence in self-energy)
- Phase 3.1: Extended Parameter Scan (inserted after Phase 3 for referee-requested data)

**Key Decisions:**
{decisions_from_project_state}
[Example:]

- Decision: Use dimensional regularization (Rationale: Preserves gauge invariance)
- Decision: Wolff cluster algorithm for MC (Rationale: Reduces critical slowing down)

**Issues Resolved:**
{issues_resolved_during_milestone}
[Example:]

- Resolved UV divergence in 2-loop self-energy via dimensional regularization
- Fixed finite-size scaling collapse by including logarithmic corrections

**Issues Deferred:**
{issues_deferred_to_later}
[Example:]

- Extension to quantum regime (deferred to Paper II)
- Effect of disorder on transition (deferred to future work)

**Lessons Learned:**
{lessons_from_research_process}
[Example:]

- Logarithmic corrections essential for BKT finite-size scaling — cannot be neglected even at L=128
- RG truncation at leading order in fugacity sufficient for alpha > 2; higher orders needed near alpha_c

**Open Questions and Shortcuts:**
{shortcuts_needing_future_work}
[Example:]

- Monte Carlo code not optimized for GPU (acceptable for current system sizes)
- Error analysis uses simple bootstrap; should upgrade to jackknife for correlated data

---

_For current project status, see .gpd/ROADMAP.md_

---

## Usage Guidelines

<guidelines>
**When to create milestone archives:**
- After completing all phases in a milestone (Paper I, Revisions, Paper II, etc.)
- Triggered by complete-milestone workflow
- Before planning next milestone work

**How to fill template:**

- Replace `{placeholders}` with actual values
- Extract phase details from ROADMAP.md
- Document decimal phases with (INSERTED) marker
- Include key results with equations and numerical values
- Include key decisions from PROJECT.md or SUMMARY files
- List issues resolved vs deferred
- Capture lessons learned for future research
- Note open questions for future reference

**Archive location:**

- Save to `.gpd/milestones/{milestone-name}.md`
- Example: `.gpd/milestones/paper-i-submitted.md`

**After archiving:**

- Update ROADMAP.md to collapse completed milestone in `<details>` tag
- Update PROJECT.md with current state of validated results
- Continue phase numbering in next milestone (never restart at 01)
  </guidelines>

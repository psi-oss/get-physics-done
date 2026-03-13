---
template_version: 1
---

# State Template

Template for `.gpd/STATE.md` — the research project's living memory.

---

## File Template

```markdown
# Research State

## Project Reference

See: .gpd/PROJECT.md (updated [date])

**Machine-readable scoping contract:** `.gpd/state.json` field `project_contract`

**Core research question:** [One-liner from PROJECT.md Core Research Question section]
**Current focus:** [Current phase name]

## Current Position

**Current Phase:** 01
**Current Phase Name:** [Phase name]
**Total Phases:** [N]
**Current Plan:** 1
**Total Plans in Phase:** [M]
**Status:** Ready to plan
**Last Activity:** [YYYY-MM-DD]
**Last Activity Description:** [What happened]
**Paused At:** [Description if paused, omit line if not paused]

**Progress:** [░░░░░░░░░░] 0%

## Active Calculations

[What is currently being computed/derived/simulated — the work in progress:]

- [Calculation 1: e.g., Evaluating 2-loop self-energy diagrams, 3 of 7 complete]
- [Calculation 2: e.g., Monte Carlo equilibration at T = 0.85, 60% of sweeps done]

## Intermediate Results

[Partial results obtained so far that inform ongoing work. Each result is a structured record in state.json:]

- [R-01-01-lxk7a2b] Dispersion relation: `\omega(k) = \sqrt{k^2 + m^2}` (units: energy, valid: k << \Lambda, phase 01) [deps: none]
- [R-02-01-m1k3f9c] Leading-order correction: `\Delta E = -0.237 g^2` (units: energy, valid: g << 1, phase 02, verified) [deps: R-01-01-lxk7a2b]
- [R-03-01-q9d4h2a] Phase boundary: `T_c(\alpha=2.0) \in [0.71, 0.73]` (units: temperature, valid: L >= 32, phase 03) [deps: R-02-01-m1k3f9c]

JSON sidecar schema per result:

```json
{
  "id": "R-01-01-lxk7a2b",
  "equation": "\\omega(k) = \\sqrt{k^2 + m^2}",
  "description": "Dispersion relation",
  "units": "energy",
  "validity": "k << \\Lambda",
  "phase": "01",
  "depends_on": [],
  "verified": false
}
```

## Open Questions

[Physics questions that have emerged during the work:]

- [Question 1: e.g., Is the sign of the 2-loop correction scheme-dependent?]
- [Question 2: e.g., Why does finite-size scaling collapse degrade below L = 32?]

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
| -     | -        | -     | -     |

## Accumulated Context

### Decisions

Full log: `.gpd/DECISIONS.md`

**Recent high-impact:**
- [Phase X]: [Decision summary: e.g., Chose dim-reg over cutoff to preserve gauge invariance]
- [Phase Y]: [Decision summary: e.g., Using Wolff algorithm instead of Metropolis for MC]

### Active Approximations

| Approximation                  | Validity Range | Controlling Parameter | Current Value | Status                   |
| ------------------------------ | -------------- | --------------------- | ------------- | ------------------------ |
| {e.g., Perturbative expansion} | {g << 1}       | {coupling g}          | {0.1}         | {Valid/Marginal/Invalid} |

**Convention Lock:**

- Metric signature: {e.g., (-,+,+,+) or "not set"}
- Fourier convention: {e.g., ∫dk/(2π) e^{ikx} or "not set"}
- Natural units: {e.g., ħ=c=1 or "not set"}
- Gauge choice: {e.g., Lorenz gauge or "not set"}
- Regularization scheme: {e.g., Dimensional regularization, d=4-2ε or "not set"}
- Renormalization scheme: {e.g., MS-bar at μ = m_Z or "not set"}
- Coordinate system: {e.g., Mostly-plus metric with x⁰=t or "not set"}
- Spin basis: {e.g., Pauli matrices σ_x, σ_y, σ_z in standard basis or "not set"}
- State normalization: {e.g., ⟨p|p'⟩ = (2π)³2E_p δ³(p-p') or "not set"}
- Coupling convention: {e.g., g² includes 1/(4π) factor or "not set"}
- Index positioning: {e.g., covariant derivatives ∂_μ with lower index or "not set"}
- Time ordering: {e.g., T-product with Feynman iε prescription or "not set"}
- Commutation convention: {e.g., [x_i, p_j] = iħδ_{ij} or "not set"}
- Levi-Civita sign: {e.g., ε^{0123} = +1 or "not set"}
- Generator normalization: {e.g., Tr(T^a T^b) = 1/2 δ^{ab} or "not set"}
- Covariant derivative sign: {e.g., D_μ = ∂_μ + i g A_μ or "not set"}
- Gamma matrix convention: {e.g., Dirac basis, γ^5 = iγ^0γ^1γ^2γ^3 or "not set"}
- Creation/annihilation order: {e.g., normal ordering puts a† left of a or "not set"}

### Propagated Uncertainties

| Quantity    | Current Value | Uncertainty | Last Updated (Phase) | Method                |
| ----------- | ------------- | ----------- | -------------------- | --------------------- |
| {e.g., T_c} | {0.893}       | {+/- 0.005} | {Phase 2}            | {finite-size scaling} |

[Update when a phase produces a refined value. If a downstream phase uses a quantity, it must propagate the uncertainty. If two phases produce independent estimates, combine using standard error propagation.]

### Pending Todos

[From .gpd/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work:]

- [Blocker 1: e.g., Integral in Eq. (23) diverges for d < 3; need regularization scheme]
- [Concern 1: e.g., MC autocorrelation time growing faster than expected near T_c]

None yet.

## Session Continuity

**Last session:** —
**Stopped at:** —
**Resume file:** —
```

<purpose>

STATE.md is the research project's short-term memory spanning all phases and sessions.

**Problem it solves:** Information is captured in derivation notebooks, simulation logs, and decision records but not systematically consumed. Sessions start without context of what has been tried, what intermediate results exist, and what questions are open.

**Solution:** A single, small file that's:

- Read first in every workflow
- Updated after every significant action
- Contains digest of accumulated research context
- Enables instant session restoration with full awareness of current research state

</purpose>

<lifecycle>

**Creation:** After ROADMAP.md is created (during init)

- Reference PROJECT.md (read it for current context)
- Initialize empty accumulated context sections
- Set position to "Phase 1 ready to plan"

**Reading:** First step of every workflow

- progress: Present status to researcher
- plan: Inform planning decisions with current intermediate results
- execute: Know current position and what's been tried
- transition: Know what's complete and what validations passed

**Writing:** After every significant action

- execute: After SUMMARY.md created
  - Update position (phase, plan, status)
  - Update active calculations and intermediate results
  - Note new decisions (detail in DECISIONS.md)
  - Add open questions and blockers/concerns
- transition: After phase marked complete
  - Update progress bar
  - Move completed calculations to intermediate results
  - Clear resolved blockers and answered questions
  - Refresh Project Reference date

</lifecycle>

<sections>

### Project Reference

Points to PROJECT.md for full context. Includes:

- Core research question (the ONE thing to answer)
- Current focus (which phase)
- Last update date (triggers re-read if stale)

The agent reads PROJECT.md directly for requirements, constraints, notation, and references.
The authoritative structured scoping contract lives in `state.json.project_contract`; PROJECT.md is the human-readable projection.

### Current Position

Where we are right now:

- Phase X of Y — which phase
- Plan A of B — which plan within phase
- Status — current state
- Last activity — what happened most recently
- Progress bar — visual indicator of overall completion

Progress calculation: (completed plans) / (total plans across all phases) x 100%

### Active Calculations

Work currently in progress:

- What is being derived, computed, or simulated right now
- Progress within each active calculation
- Expected output when complete

### Intermediate Results

Partial results obtained so far:

- Numerical values, analytic expressions, or qualitative findings
- Include enough detail to resume work without re-deriving
- Reference notebook/file locations where full details live

### Open Questions

Physics questions that emerged during work:

- Questions about the formalism, numerics, or interpretation
- Questions that may require literature consultation or new calculations
- Prefix with originating phase for traceability

### Performance Metrics

Track throughput to understand execution patterns:

- Total plans completed
- Average duration per plan
- Per-phase breakdown
- Recent trend (improving/stable/degrading)

Updated after each plan completion.

### Accumulated Context

**Decisions:** Full log: `.gpd/DECISIONS.md` (single source of truth). Recent high-impact decisions shown in Accumulated Context for quick access.

**Active Approximations:** Tracks all approximations currently in use, their validity ranges, and the controlling parameters. Convention lock is an 18-field snapshot of active conventions — full convention catalog lives in `.gpd/CONVENTIONS.md`.

**Pending Todos:** Ideas captured via /gpd:add-todo

- Count of pending todos
- Reference to .gpd/todos/pending/
- Brief list if few, count if many (e.g., "5 pending todos — see /gpd:check-todos")

**Blockers/Concerns:** From "Next Phase Readiness" sections

- Issues that affect future work (divergences, convergence problems, missing data)
- Prefix with originating phase
- Cleared when addressed

### Session Continuity

Enables instant resumption:

- When was last session
- What was last completed
- Is there a .continue-here file to resume from

</sections>

<size_constraint>

STATE.md is a human-readable digest. The JSON sidecar (state.json) is the authoritative source with no size limit.

STATE.md should be concise but not artificially truncated. If accumulated context grows very large:

- Keep only 3-5 recent decisions in summary (full log in DECISIONS.md)
- Keep only active blockers, remove resolved ones
- Summarize intermediate results compactly, but preserve equations and validity ranges
- Keep only currently open questions, archive answered ones
- Convention lock renders only non-null entries, so it stays compact automatically

The goal is "read once, know where we are" while preserving all physics-critical information (equations, conventions, validity ranges).

</size_constraint>

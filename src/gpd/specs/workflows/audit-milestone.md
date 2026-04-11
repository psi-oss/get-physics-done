<purpose>
Verify research milestone achieved its definition of done by aggregating phase verifications, checking cross-phase consistency, and assessing research completeness. Reads existing `*-VERIFICATION.md` files (phases already verified during execute-phase), aggregates open questions and deferred analysis, then spawns consistency checker for cross-phase physics validation.

Key questions: Are all claims supported? All calculations verified? All comparisons made? Ready for publication or next research stage?
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

## 0. Initialize Milestone Context

```bash
INIT=$(gpd --raw init milestone-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `milestone_version`, `milestone_name`, `phase_count`, `completed_phases`, `commit_docs`, `project_exists`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `active_reference_context`.

Keep `project_contract`, `project_contract_load_info`, `project_contract_validation`, and `active_reference_context` visible while auditing:

- Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true.
- If that contract gate is blocked, keep the contract visible as context but record contract repair as a blocker in the audit instead of silently substituting prose-only scope.
- If contract repair is still pending, do not mark the milestone `passed` and do not trust mock peer-review publishability judgments as approval to submit.

**Read mode settings:**

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after each audit criterion for user discussion of gaps.
- `autonomy=balanced` (default): Complete the full audit and generate a gap-closure plan when needed. Pause only if critical gaps or milestone-scope questions need user judgment.
- `autonomy=yolo`: Complete audit, auto-approve milestone if > 80% criteria met.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context audit-milestone "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

**If `milestone_version` is null/empty:**

```
ERROR: No active milestone found.

A milestone audit requires a project with phases.
Run gpd:new-project first, then complete phases before auditing.
```

Exit.

Resolve consistency checker model:

```bash
CHECKER_MODEL=$(gpd resolve-model gpd-consistency-checker)
```

## 1. Determine Milestone Scope

```bash
# Get phases in milestone (sorted numerically, handles decimals)
gpd phase list
```

- Parse version from arguments or detect current from ROADMAP.md
- Identify all phase directories in scope
- Extract milestone definition of done from ROADMAP.md
- Extract requirements mapped to this milestone from REQUIREMENTS.md

## 2. Read All Phase Verifications

Use the canonical phase helpers instead of raw phase-path globbing:

```bash
gpd phase list
gpd --raw init phase-op <phase-number>
```

For each phase in the milestone, use `gpd --raw init phase-op <phase-number>` to surface the canonical `*-VERIFICATION.md` artifact and its verification status, then read the artifact itself only when you need blocker-level detail. Do not `find_files` `GPD/phases/*/*-VERIFICATION.md` by hand.

From each `*-VERIFICATION.md`, extract:

- **Status:** passed | gaps_found
- **Critical gaps:** (if any -- these are blockers)
- **Non-critical gaps:** open questions, deferred analysis, warnings
- **Anti-patterns found:** placeholders, unjustified approximations, missing checks
- **Requirements coverage:** which requirements satisfied/blocked

If a phase is missing `*-VERIFICATION.md`, flag it as "unverified phase" -- this is a blocker.

## 3. Spawn Consistency Checker

With phase context collected:
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

Apply this delegation note to every subagent spawn in this workflow; do not repeat it before individual spawn examples.

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-consistency-checker.md for your role and instructions.

Check cross-phase physics consistency and end-to-end research coherence.

Phases: {phase_dirs}
Phase results: {from SUMMARYs}
Key equations: {equations derived/used}
Parameters: {shared parameters and their values}

Verify:
- Notation consistency across phases (same symbols mean same things)
- Parameter values used consistently (no contradictory assumptions)
- Results from early phases correctly used in later phases
- Approximations compatible across phases (not contradictory limits)
- Physical units consistent throughout
- Overall narrative coherence (do the phases tell a complete story?)",
  subagent_type="gpd-consistency-checker",
  model="{checker_model}",
  readonly=false
)
```

**If the consistency checker agent fails to spawn or returns an error:** Proceed without cross-phase consistency checks. Note in the audit report that consistency verification was skipped. The phase-level checks (step 2) still provide individual phase validation. The user should run `gpd:validate-conventions` separately after the audit.

## 4. Collect Results

Combine:

- Phase-level gaps and open questions (from step 2)
- Consistency checker's report (notation conflicts, parameter mismatches, broken reasoning chains) — or note "skipped" if agent failed
- Contract-gate blockers from step 0 (if `project_contract_load_info` is blocked or `project_contract_validation` fails)

## 5. Check Requirements Coverage

For each requirement in REQUIREMENTS.md mapped to this milestone:

- Find owning phase
- Check phase verification status
- Determine: satisfied | partial | unsatisfied

## 6. Aggregate into v{version}-MILESTONE-AUDIT.md

Create `GPD/v{version}-MILESTONE-AUDIT.md` with:

```yaml
---
milestone: { version }
audited: { timestamp }
status: passed | gaps_found | open_questions
scores:
  requirements: N/M
  phases: N/M
  consistency: N/M
  completeness: N/M
gaps: # Critical blockers
  requirements: [...]
  consistency: [...]
  completeness: [...]
open_questions: # Non-critical, deferred
  - phase: 01-model-setup
    items:
      - "Open: higher-order corrections not yet computed"
      - "Warning: approximation validity not tested near phase boundary"
  - phase: 03-numerics
    items:
      - "Deferred: finite-size scaling analysis"
      - "Open: alternative discretization schemes not compared"
---
```

Plus full markdown report with tables for requirements, phases, consistency, open questions.

**Status values:**

- `passed` -- all requirements met, no critical gaps, research is coherent and complete
- `gaps_found` -- critical blockers exist (missing derivations, contradictory results, unverified claims)
- `open_questions` -- no blockers but accumulated deferred analysis needs review before publication

## 7. Optional: Mock Peer Review

If enabled in config (`referee_review: true` in `GPD/config.json`) or if the user requests it, spawn the referee agent for a simulated peer review of the milestone's research outputs. This provides an independent critical assessment before the researcher decides on next steps, with a milestone-scoped Markdown report plus a polished LaTeX companion artifact.

If `project_contract_load_info.status` starts with `blocked` or `project_contract_validation.valid` is false, skip mock peer review and note that the contract gate must be repaired before milestone publishability review.

**Check config or ask user:**

```bash
REFEREE_ENABLED=$(gpd --raw config get referee_review 2>/dev/null | gpd json get .value --default unset 2>/dev/null || echo "unset")
```

- If `true`: proceed with referee review
- If `false`: skip to step 8
- If `unset`: ask the user — "Run a mock peer review of this milestone? This spawns a referee agent that evaluates the research across 10 dimensions (correctness, novelty, significance, etc.) and produces a structured report. Recommended before paper writing."

**If proceeding:**

Resolve referee model:

```bash
REFEREE_MODEL=$(gpd resolve-model gpd-referee)
```

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-referee",
  model="{referee_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-referee.md for your role and instructions.

Conduct a mock peer review of milestone {milestone_version} research outputs.

Scope: Full milestone review
Milestone: {milestone_version} -- {milestone_name}
Project contract load info: {project_contract_load_info}
Project contract validation: {project_contract_validation}
Project contract: {project_contract}
Active references: {active_reference_context}

Files to read:
- ROADMAP.md (research goals and phase structure)
- All SUMMARY.md files from completed phases in GPD/phases/
- STATE.md (conventions, notation, parameters)
- All VERIFICATION.md files from completed phases
- Any manuscript .tex files (if they exist)
- GPD/v{milestone_version}-MILESTONE-AUDIT.md (audit results)

Evaluate across all 10 dimensions:
1. Correctness -- dimensional analysis, limiting cases, sign conventions
2. Completeness -- all promised results delivered, error analysis present
3. Technical soundness -- methodology appropriate, approximations justified
4. Novelty -- comparison with prior work
5. Significance -- importance to the field
6. Literature context -- key references, comparisons
7. Reproducibility -- parameters stated, methods described
8. Clarity -- logical flow, notation consistency
9. Presentation quality -- organization, figures
10. Publishability -- overall assessment

Treat `project_contract` as approved milestone scope only when `project_contract_gate.authoritative` is true. If the contract gate is blocked, keep it visible as context but call out the blocker explicitly instead of relying on it as approved scope.

Write `GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md` and the matching `GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.tex` companion.

Return REVIEW COMPLETE with recommendation and issue counts."
)
```

**If the referee agent fails to spawn or returns an error:** Proceed without mock peer review — note in the audit report that peer review was skipped. The audit is still valid based on consistency checks and phase-level verification. The user should run `gpd:verify-work` separately after the audit.

**After referee report:**

Verify the promised referee artifacts before trusting the handoff text:
- Confirm `GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md` exists and contains a recommendation plus issue counts.
- Confirm `GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.tex` exists as the matching companion artifact.
- If the agent reported success but either artifact is missing, treat peer review as failed, note the failure in the audit report, and do not summarize imaginary review findings.

Read the report and include a summary in the presented results:

```markdown
### Mock Peer Review

**Recommendation:** {accept | minor_revision | major_revision | reject}
**Major issues:** {N}
**Minor issues:** {N}
**Report:** GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md
**LaTeX report:** GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.tex

{2-3 sentence summary of key findings}
```

If the referee found major issues, append them to the gaps in the milestone audit report.

## 8. Present Results

Route by status (see `<offer_next>`).

</process>

<offer_next>
Output this markdown directly (not as a code block). Route based on status:

---

**If passed:**

## Milestone {version} -- Audit Passed

**Score:** {N}/{M} requirements satisfied
**Report:** GPD/v{version}-MILESTONE-AUDIT.md

All requirements covered. Cross-phase consistency verified. Research is complete and coherent.

---

## > Next Up

**Complete milestone** -- archive and tag

gpd:complete-milestone {version}

<sub>/clear first -> fresh context window</sub>

---

---

**If gaps_found:**

## Milestone {version} -- Gaps Found

**Score:** {N}/{M} requirements satisfied
**Report:** GPD/v{version}-MILESTONE-AUDIT.md

### Unsatisfied Requirements

{For each unsatisfied requirement:}

- **{REQ-ID}: {description}** (Phase {X})
  - {reason}

### Consistency Issues

{For each consistency gap:}

- **{phase_A} vs {phase_B}:** {issue} (e.g., contradictory parameter values, incompatible approximations)

### Incomplete Analysis

{For each completeness gap:}

- **{analysis name}:** missing {what} (e.g., limiting case not checked, comparison with literature not performed)

---

## > Next Up

**Plan gap closure** -- create phases to complete research

gpd:plan-milestone-gaps

<sub>/clear first -> fresh context window</sub>

---

**Also available:**

- cat GPD/v{version}-MILESTONE-AUDIT.md -- see full report
- gpd:complete-milestone {version} -- proceed anyway (accept open questions)

---

---

**If open_questions (no blockers but accumulated deferred analysis):**

## Milestone {version} -- Open Questions Review

**Score:** {N}/{M} requirements satisfied
**Report:** GPD/v{version}-MILESTONE-AUDIT.md

All requirements met. No critical blockers. Accumulated open questions need review.

### Open Questions by Phase

{For each phase with open items:}
**Phase {X}: {name}**

- {item 1}
- {item 2}

### Total: {N} items across {M} phases

---

## > Options

**A. Complete milestone** -- accept open questions, track in research log

gpd:complete-milestone {version}

**B. Plan additional analysis** -- address open questions before completing

gpd:plan-milestone-gaps

<sub>/clear first -> fresh context window</sub>

---

</offer_next>

<success_criteria>

- [ ] Milestone scope identified
- [ ] All phase VERIFICATION.md files read
- [ ] Open questions and deferred analysis aggregated
- [ ] Consistency checker spawned for cross-phase physics validation
- [ ] v{version}-MILESTONE-AUDIT.md created
- [ ] Optional referee review spawned (if enabled or requested)
- [ ] Results presented with actionable next steps

</success_criteria>

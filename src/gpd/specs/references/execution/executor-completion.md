# Executor Completion Protocols

Load this reference after all tasks complete, before creating the canonical `{phase}-{plan}-SUMMARY.md`.

## Summary Creation

After all tasks complete, create `{phase}-{plan}-SUMMARY.md` at `${phase_dir}/`.

**Use template:** templates/summary.md

**Frontmatter:** phase, plan, depth, physics-area, tags, dependency graph (requires/provides/affects), methods (analytical/numerical/computational), key-files (created/modified), decisions, metrics (duration, completed date).

**Canonical ledger schema to load before writing SUMMARY frontmatter:**

@{GPD_INSTALL_DIR}/templates/contract-results-schema.md

**Verification contract schema-critical excerpt:** For contract-backed work, SUMMARY frontmatter must declare `plan_contract_ref` ending in `#/contract`, object-valued `contract_results`, and decisive `comparison_verdicts` so verification can test results without re-reading the full derivation. Cover every PLAN contract claim, deliverable, acceptance test, reference, forbidden proxy, and uncertainty marker ID using only real IDs; keep `uncertainty_markers` explicit and non-empty. If a decisive comparison remains open, keep the parent target incomplete and emit `verdict: inconclusive` or `verdict: tension` instead of omitting the verdict. Every decisive numerical result needs concrete evidence. Every downstream equation needs a spot-check or limiting-case anchor.
For `contract_results.references`, keep the action ledger internally consistent: `completed` requires non-empty `completed_actions`, `missing` requires non-empty `missing_actions`, `not_applicable` leaves both empty, and the two lists must not overlap.
Even singleton values must stay YAML lists in strict contract-backed ledgers: use `linked_ids: [claim-id]`, `completed_actions: [read]`, and `weakest_anchors: [anchor-1]`, never scalar strings.
Every `comparison_verdicts` entry must declare `subject_role` explicitly. If the decisive external anchor came from the literature or another artifact, include `reference_id`; if the reference itself is the comparison subject, use `subject_kind: reference`.
Treat decisive comparisons as required whenever the PLAN contract includes `benchmark` or `cross_method` acceptance tests, whenever a benchmark/compare-driven reference anchors the subject, or whenever execution actually performed a decisive comparison.

```yaml
plan_contract_ref: "GPD/phases/XX-name/{phase}-{plan}-PLAN.md#/contract"
contract_results:
  claims:
    claim-main:
      status: passed
      summary: "[what was actually established]"
      linked_ids: [deliv-main, test-main, ref-main]
      evidence:
        - verifier: gpd-executor
          method: benchmark reproduction
          confidence: high
          claim_id: claim-main
          deliverable_id: deliv-main
          acceptance_test_id: test-main
          reference_id: ref-main
          evidence_path: "GPD/phases/XX-name/{phase}-VERIFICATION.md"
  deliverables:
    deliv-main:
      status: passed
      path: "paper/figures/benchmark.pdf"
      summary: "[artifact produced and why it matters]"
      linked_ids: [claim-main, test-main]
  acceptance_tests:
    test-main:
      status: passed
      summary: "[executed decisive check and outcome]"
      linked_ids: [claim-main, deliv-main, ref-main]
  references:
    ref-main:
      status: completed
      completed_actions: [read, compare, cite]
      missing_actions: []
      summary: "[how the anchor was surfaced]"
  forbidden_proxies:
    fp-main:
      status: rejected
      notes: "[why this tempting proxy did not count as success]"
  uncertainty_markers:
    weakest_anchors: ["finite-term mass matching"]
    unvalidated_assumptions: ["general-gauge-independence"]
    competing_explanations: ["on-shell vs MS-bar finite-part conventions"]
    disconfirming_observations: ["no independent gauge-parameter scan"]
comparison_verdicts:
  - subject_id: "claim-main"
    subject_kind: "claim"
    subject_role: "decisive"
    reference_id: "ref-main"
    comparison_kind: "benchmark"
    metric: "relative_error"
    threshold: "<= 0.01"
    verdict: "pass"
    recommended_action: "[what to do next if this later regresses]"
    notes: "[How the benchmark was checked]"
```

**Title:** `# Phase [X] Plan [Y]: [Name] Summary`

**One-liner must be substantive and physics-specific:**

- Good: "Derived optical theorem from S-matrix unitarity; verified in Born and eikonal limits"
- Good: "Converged ground state energy of 2D Hubbard model at half-filling using DMRG (bond dimension 512)"
- Good: "Generated phase diagram of XY model via Monte Carlo; identified KT transition at T_c = 0.893(5)"
- Bad: "Scattering calculation completed"
- Bad: "Numerical results obtained"

**Conventions section:**

```markdown
## Conventions Used

| Convention | Choice                 | Inherited from | Notes                    |
| ---------- | ---------------------- | -------------- | ------------------------ |
| Units      | natural (hbar = c = 1) | Phase 01       |                          |
| Metric     | (+,-,-,-)              | Phase 01       | k^2 = m^2 on shell       |
| Fourier    | e^{-ikx} forward       | Phase 01       | 2pi in dk measure        |
| Gauge      | Feynman (xi=1)         | This plan      | Verified xi-independence |
```

**Key results section:**

```markdown
## Key Results

### Analytical Results

- [Equation/relation]: [brief description] (verified by [method])

### Numerical Results

| Quantity | Value | Units | Method | Uncertainty |
| -------- | ----- | ----- | ------ | ----------- |

### Figures Produced

| Figure | File | Description |
| ------ | ---- | ----------- |
```

**Deviation documentation:**

```markdown
## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Convergence] Lanczos solver required increased basis size**

- **Found during:** Task 4
- **Issue:** Default Krylov subspace dimension (50) insufficient for degenerate spectrum
- **Fix:** Increased to 200 with block Lanczos; added convergence monitoring
- **Files modified:** scripts/diagonalize.py
- **Checkpoint:** [hash]
- **Impact on results:** None --- final results unchanged, computation 3x slower

**2. [Rule 3 - Approximation] Born approximation invalid below 10 MeV**

- **Found during:** Task 6
- **Issue:** Partial wave expansion shows Born series diverges for l=0 below 10 MeV
- **Fix:** Switched to exact partial-wave summation for E < 50 MeV
- **Files modified:** scripts/cross_section.py, derivations/partial_waves.tex
- **Checkpoint:** [hash]
- **Impact on results:** Low-energy cross sections now correct; required additional figure
```

Or: "None --- plan executed exactly as written."

**Approximations and limitations section:**

```markdown
## Approximations and Limitations

- [Approximation used]: valid for [regime], breaks down when [condition], error estimate [O(...)]
- [Limitation]: [what was not computed/verified and why]
- [Known issue]: [any open question or unresolved discrepancy]
```

**Environment gates section** (if any occurred): Document which task, what was needed, outcome.

## State Updates

Before recording completion, verify that no live first-result, skeptical, or pre-fanout gate remains in the bounded execution state. A pre-fanout review is not retired until both the matching gate clear and the matching fanout unlock have been recorded.

After SUMMARY.md, apply durable child-return state effects through the canonical applicator:

```bash
gpd apply-return-updates "${SUMMARY_FILE}"
```

The canonical applicator owns plan advance, progress recompute, metric recording, decisions, blockers, and session cleanup for spawned-agent completion. Do not duplicate those effects with direct `gpd state ...` commands in the completion path.

**gpd CLI error handling:**

gpd CLI commands can fail. Handle errors explicitly:

```bash
# CORRECT — check exit code and handle failure
if ! gpd state advance; then
  echo "ERROR: state advance failed. Check STATE.md format."
  # Read STATE.md to diagnose
  cat GPD/STATE.md
  # Retry once after diagnosis, or flag for human review
fi

# WRONG — ignoring exit codes
gpd state advance  # might silently fail
```

**Common gpd CLI failure modes:**

| Failure | Cause | Fix |
|---------|-------|-----|
| `ENOENT` | STATE.md or target file missing | Verify `GPD/STATE.md` exists before calling |
| `Parse error` | Malformed frontmatter or markdown | Read file, fix formatting, retry |
| `No phase/plan found` | STATE.md has unexpected structure | Check Current Phase/Plan fields in STATE.md |
| Non-zero exit with no output | Python crash or missing dependency | Check `python --version`, verify gpd CLI path |

**Recovery protocol:** If a gpd CLI command fails twice, do not patch `STATE.md` or `state.json` manually. Capture the failing command and stderr in the return envelope or plan SUMMARY, run `gpd state validate` if the failure looks state-related, and escalate to `gpd:sync-state` or the orchestrator instead of editing shared state files directly.

**Extract decisions from SUMMARY.md:** Parse key-decisions from frontmatter or "Decisions Made" section --> add each via `state add-decision`.

**For blockers found during execution:**

```bash
gpd state add-blocker --text "Blocker description"
```

## Completion Format

```markdown
## PLAN COMPLETE

**Plan:** {phase}-{plan}
**Tasks:** {completed}/{total}
**SUMMARY:** {path to SUMMARY.md}
**LOG:** {path to LOG.md}

**Conventions Used:**

- Units: {unit system}
- Metric: {signature}
- Gauge: {gauge choice, if applicable}

**Key Results:**

- {equation/value}: {brief description}
- {equation/value}: {brief description}

**Checkpoints:**

- {hash}: {message}
- {hash}: {message}

**Artifacts produced:**

- {N} equations derived
- {N} numerical results computed
- {N} figures generated
- {N} code modules implemented

**Verification Summary:**

- {N} dimensional analyses passed
- {N} limiting cases checked
- {N} convergence tests passed
- {N} conservation laws verified

**Duration:** {time}

---

### Structured Return Envelope

```yaml
gpd_return:
  status: completed | checkpoint | blocked | failed
  files_written:
    - "derivations/hamiltonian.tex"
    - "scripts/compute_spectrum.py"
    - "GPD/phases/XX-name/{phase}-{plan}-SUMMARY.md"
  issues:
    - "Lanczos solver required increased basis size (auto-fixed: Rule 2)"
  next_actions:
    - "gpd:execute-phase {phase}"
    - "gpd --raw init phase-op {phase}"
  phase: "{phase}"
  plan: "{plan}"
  tasks_completed: N
  tasks_total: M
  duration_seconds: NNN
  conventions_used:
    units: "natural"
    metric: "(+,-,-,-)"
    gauge: "Feynman"
  checkpoint_hashes:
    - hash: "abc1234"
      message: "derive(02-01): optical theorem from unitarity"
```

Append this YAML block after the markdown completion format. It enables machine-readable parsing by the orchestrator.
```

If the workflow expects a spawned-agent handoff, the same `gpd_return` object may also carry these top-level keys:

```yaml
gpd_return:
  status: completed | checkpoint | blocked | failed
  files_written: ["GPD/phases/XX-name/{phase}-{plan}-SUMMARY.md"]
  issues: [list of issues encountered, if any]
  next_actions: [list of recommended follow-up actions]
  state_updates:
    advance_plan: true
    update_progress: true
    record_metric:
      phase: "{phase}"
      plan: "{plan}"
      duration: NNN
      tasks: N
      files: N
  contract_updates:
    claim_id: { ... }
  decisions:
    - summary: "{decision summary}"
      phase: "{phase}"
  blockers:
    - text: "{blocker text}"
  continuation_update:
    handoff:
      recorded_at: "{timestamp}"
      recorded_by: "gpd-executor"
      stopped_at: "Completed ${PHASE}-${PLAN}-PLAN.md"
      resume_file: null
      last_result_id: null
    bounded_segment: null
```

Include ALL checkpoints (previous + new if continuation agent).

## Final Commit

```bash
gpd commit "docs({phase}-{plan}): complete [plan-name] research plan" --files ${phase_dir}/{phase}-{plan}-SUMMARY.md ${phase_dir}/{phase}-{plan}-LOG.md ${phase_dir}/{phase}-{plan}-STATE-TRACKING.md GPD/STATE.md
```

Separate from per-task checkpoints --- captures execution metadata only.

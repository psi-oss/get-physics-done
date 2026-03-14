# Executor Completion Protocols

Load this reference after all tasks complete, before creating SUMMARY.md.

## Summary Creation

After all tasks complete, create `{phase}-{plan}-SUMMARY.md` at `${phase_dir}/`.

**Use template:** templates/summary.md

**Frontmatter:** phase, plan, physics-area, tags, dependency graph (requires/provides/affects), methods (analytical/numerical/computational), key-files (created/modified), decisions, metrics (duration, completed date).

**Verification contract:** For contract-backed work, the SUMMARY.md frontmatter MUST declare `plan_contract_ref`, `contract_results`, and any decisive `comparison_verdicts` so the verifier can test results without re-reading the full derivation. Every decisive numerical result needs concrete evidence. Every equation that matters downstream needs a spot-check or limiting-case anchor.

```yaml
plan_contract_ref: ".gpd/phases/XX-name/{phase}-{plan}-PLAN.md#/contract"
contract_results:
  claims:
    claim-main:
      status: passed
      evidence:
        - verifier: gpd-executor
          method: benchmark reproduction
          confidence: high
          evidence_path: "paper/benchmark.dat"
          notes: "[How the decisive claim was checked]"
  deliverables:
    deliv-main:
      status: passed
      evidence:
        - verifier: gpd-executor
          method: artifact creation
          confidence: high
          evidence_path: "paper/figures/main.pdf"
          notes: "[Artifact produced]"
  acceptance_tests:
    test-main:
      status: passed
      evidence:
        - verifier: gpd-executor
          method: acceptance test execution
          confidence: high
          evidence_path: "analysis/benchmark_check.py"
          notes: "[Executed check and outcome]"
comparison_verdicts:
  - subject_id: "claim-main"
    subject_kind: "claim"
    subject_role: "decisive"
    reference_id: "ref-main"
    comparison_kind: "benchmark"
    metric: "relative_error"
    threshold: "<= 0.01"
    verdict: "pass"
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

After SUMMARY.md, update STATE.md using gpd CLI:

```bash
# Advance plan counter (handles edge cases automatically)
gpd state advance-plan

# Recalculate progress bar from disk state
gpd state update-progress

# Record execution metrics
gpd state record-metric \
  --phase "${PHASE}" --plan "${PLAN}" --duration "${DURATION}" \
  --tasks "${TASK_COUNT}" --files "${ARTIFACT_COUNT}"

# Add decisions (extract from SUMMARY.md key-decisions)
for decision in "${DECISIONS[@]}"; do
  gpd state add-decision \
    --phase "${PHASE}" --summary "${decision}"
done

# Add key results to global results registry
for result in "${KEY_RESULTS[@]}"; do
  gpd result add \
    --phase "${PHASE}" --description "${result}"
done

# Update session info
gpd state record-session \
  --stopped-at "Completed ${PHASE}-${PLAN}-PLAN.md"
```

**State command behaviors:**

- `state advance-plan`: Increments Current Plan, detects last-plan edge case, sets status
- `state update-progress`: Recalculates progress bar from SUMMARY.md counts on disk
- `state record-metric`: Appends to Performance Metrics table
- `state add-decision`: Adds to Decisions section, removes placeholders
- `result add`: Adds to intermediate results registry for cross-referencing
- `state record-session`: Updates Last session timestamp and Stopped At fields

**gpd CLI error handling:**

gpd CLI commands can fail. Handle errors explicitly:

```bash
# CORRECT — check exit code and handle failure
if ! gpd state advance-plan; then
  echo "ERROR: state advance-plan failed. Check STATE.md format."
  # Read STATE.md to diagnose
  cat .gpd/STATE.md
  # Retry once after diagnosis, or flag for human review
fi

# WRONG — ignoring exit codes
gpd state advance-plan  # might silently fail
```

**Common gpd CLI failure modes:**

| Failure | Cause | Fix |
|---------|-------|-----|
| `ENOENT` | STATE.md or target file missing | Verify `.gpd/STATE.md` exists before calling |
| `Parse error` | Malformed frontmatter or markdown | Read file, fix formatting, retry |
| `No phase/plan found` | STATE.md has unexpected structure | Check Current Phase/Plan fields in STATE.md |
| Non-zero exit with no output | Python crash or missing dependency | Check `python --version`, verify gpd CLI path |

**Recovery protocol:** If a gpd CLI command fails twice, read the target file manually, make the state update via file_edit tool, and document the manual fix in the plan SUMMARY.md.

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
    - ".gpd/phases/XX-name/{phase}-{plan}-SUMMARY.md"
  issues:
    - "Lanczos solver required increased basis size (auto-fixed: Rule 2)"
  next_actions:
    - "/gpd:execute-phase {phase}"
    - "/gpd:show-phase {phase}"
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

Include ALL checkpoints (previous + new if continuation agent).

## Final Commit

```bash
gpd commit "docs({phase}-{plan}): complete [plan-name] research plan" --files ${phase_dir}/{phase}-{plan}-SUMMARY.md ${phase_dir}/{phase}-{plan}-LOG.md ${phase_dir}/{phase}-{plan}-STATE-TRACKING.md .gpd/STATE.md
```

Separate from per-task checkpoints --- captures execution metadata only.

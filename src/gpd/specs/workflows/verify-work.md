<purpose>
Validate research results through conversational verification with persistent state. This workflow creates the canonical `XX-VERIFICATION.md` artifact, survives /clear, and feeds gaps into `gpd:plan-phase --gaps`.

Researcher validates, the AI records. One check at a time. Plain text responses.

**Key upgrade:** the workflow now runs computational spot-checks before presenting each check, so the researcher confirms concrete numerical evidence instead of only qualitative summaries.
</purpose>

<philosophy>
**Show expected physics and computational evidence, then ask if reality matches.**

The AI computes the expected result at specific test points before asking the researcher to confirm it.

- "yes" / "y" / "next" / empty -> pass
- Anything else -> logged as issue, severity inferred

Walk through derivation logic, perform numerical spot-checks, re-derive limiting cases, and probe edge cases with actual computations. No formal review forms. Just: "Here is what I independently computed. Does your result match?"

**Verification independence:** Derive validation checks from the phase goal, the PLAN `contract`, and the actual research artifacts — not from phase-summary claims about what was accomplished. Summary artifacts (`SUMMARY.md` and `*-SUMMARY.md`) `contract_results` and `comparison_verdicts` tell you where evidence lives; the expected physics comes from the phase goal, contract IDs, and domain knowledge. See @{GPD_INSTALL_DIR}/references/verification/meta/verification-independence.md.
</philosophy>

<template>
@{GPD_INSTALL_DIR}/templates/research-verification.md
</template>

Use the researcher-session body scaffold from `research-verification.md`, but keep the frontmatter contract compatible with `@{GPD_INSTALL_DIR}/templates/verification-report.md` and `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md`.

<required_reading>
@{GPD_INSTALL_DIR}/references/verification/meta/verification-independence.md
@{GPD_INSTALL_DIR}/templates/verification-report.md
@{GPD_INSTALL_DIR}/templates/contract-results-schema.md
@{GPD_INSTALL_DIR}/references/protocols/error-propagation-protocol.md
</required_reading>

<process>

<step name="check_type_selection">
## Check Type Selection

Parse `$ARGUMENTS` for specific check flags:
- `--dimensional` — Run only dimensional analysis checks
- `--limits` — Run only limiting case checks
- `--convergence` — Run only numerical convergence checks
- `--regression` — Run regression scan (check summary artifacts (`SUMMARY.md` and `*-SUMMARY.md`) / `*-VERIFICATION.md` frontmatter for convention conflicts and verification-state issues)
- `--all` or no flags — Run full verification suite

This allows targeted verification without running the full suite.

Targeted flags narrow the optional check mix only. They do NOT waive mandatory proof red-teaming for proof-bearing or `proof_obligation` work.
</step>

<step name="initialize" priority="first">
If $ARGUMENTS contains a phase number, load context:

```bash
INIT=$(gpd --raw init verify-work "${PHASE_ARG}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `planner_model`, `checker_model`, `verifier_model`, `commit_docs`, `autonomy`, `research_mode`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `has_verification`, `has_validation`, `phase_proof_review_status`, `project_contract`, `project_contract_validation`, `project_contract_load_info`, `project_contract_gate`, `contract_intake`, `effective_reference_intake`, `derived_active_references`, `derived_active_reference_count`, `citation_source_files`, `citation_source_count`, `citation_source_warnings`, `derived_citation_sources`, `derived_citation_source_count`, `active_references`, `active_reference_count`, `convention_lock`, `convention_lock_count`, `derived_convention_lock`, `derived_convention_lock_count`, `selected_protocol_bundle_ids`, `protocol_bundle_count`, `protocol_bundle_context`, `protocol_bundle_verifier_extensions`, `active_reference_context`, `literature_review_files`, `literature_review_count`, `research_map_reference_files`, `research_map_reference_count`, `reference_artifact_files`, `reference_artifacts_content`.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after each verification round for user review. Present findings and wait for confirmation before writing the canonical `XX-VERIFICATION.md` artifact.
- `autonomy=balanced` (default): Run the full verification pipeline. Pause only if verification reveals critical issues that require user judgment or claim-level decisions.
- `research_mode=balanced` (default): Keep the full contract-critical floor and the balanced review cadence. Run the standard verification pipeline unless another `research_mode` is explicitly selected.
- `autonomy=yolo`: Run verification but skip optional cross-checks and literature comparison. Do NOT skip contract-critical anchors, decisive benchmarks, or user-mandated references.
- `research_mode=explore`: Thorough verification — run all check types, compare against literature, verify intermediate steps. More spawned verifier agents.
- `research_mode=exploit`: Keep the full contract-critical floor, but narrow optional breadth around the already-validated method family. Favor decisive comparisons over extra exploratory audits.
- `research_mode=adaptive`: Keep the same contract-critical floor at all times. Start with explore-style skepticism until prior decisive evidence or an explicit approach lock exists, then narrow only the optional breadth that no longer serves the locked method.

**If `phase_found` is false:**

```
ERROR: Phase not found: ${PHASE_ARG}

Available phases:
$(gpd phase list)

Usage: gpd:verify-work <phase-number>
```

Exit.

Run the centralized review preflight before continuing:

```bash
if [ -n "${PHASE_ARG}" ]; then
  REVIEW_PREFLIGHT=$(gpd validate review-preflight verify-work "${PHASE_ARG}" --strict)
else
  REVIEW_PREFLIGHT=$(gpd validate review-preflight verify-work --strict)
fi
if [ $? -ne 0 ]; then
  echo "$REVIEW_PREFLIGHT"
  exit 1
fi
```

If review preflight exits nonzero because the project state is missing or not yet ready for verification, the roadmap is missing, review integrity is degraded, or the selected phase lacks the required artifacts, STOP and show the blocking issues before starting the session.

If `project_contract_load_info.status` starts with `blocked`, STOP and show the surfaced `project_contract_load_info.errors` / `warnings` before verification. Do not infer contract intent from prose-only artifacts when the stored contract payload could not be loaded cleanly.

If `project_contract_validation.valid` is false, STOP and show `project_contract_validation.errors` before verification. A visible-but-blocked contract must be repaired before it is used as authoritative verification scope.
</step>

<step name="proof_obligation_gate">
Detect whether the selected phase contains proof-bearing work before finalizing the check inventory.

Treat the phase as proof-bearing when any of the following are true:

- the approved contract or plan contract includes an observable or claim with kind `proof_obligation`
- the phase goal, plan contract, or artifacts mention `theorem`, `lemma`, `corollary`, `proposition`, `claim`, `proof`, `prove`, `show that`, `existence`, or `uniqueness`
- a derivation artifact is being used as a formal proof whose correctness depends on explicit coverage of named hypotheses, parameters, or quantifiers

If ambiguous, default to proof-bearing.

For proof-bearing work:

- require a canonical `*-PROOF-REDTEAM.md` artifact for each proof-bearing plan or derivation
- read that artifact before presenting any researcher-facing "passed" outcome
- confirm it inventories theorem text, named parameters, hypotheses, quantifier/domain obligations, conclusion clauses, and at least one adversarial special-case or counterexample probe
- treat missing artifact, missing coverage inventory, or `status != passed` as a blocking gap
- do not let `--dimensional`, `--limits`, `--convergence`, exploratory mode, or manual urgency waive this gate
- if `phase_proof_review_status` is present, use it as the structured freshness summary for the phase proof-review manifest instead of re-deriving freshness from file greps.

When runtime delegation is available and a required proof-redteam artifact is missing, malformed, or stale, spawn `gpd-check-proof` once before finalizing the gap ledger:

```bash
CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)
```

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

```
task(
  subagent_type="gpd-check-proof",
  model="{check_proof_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-check-proof.md for your role and instructions.

Operate in proof-redteam remediation mode with a fresh context.

Write to the missing or stale sibling `*-PROOF-REDTEAM.md` artifact for the proof-bearing target under review.

Files to read:
- The proof-bearing plan or derivation artifact
- The current verification artifact
- Supporting summary / verification / contract artifacts for this phase

Reconstruct the exact theorem inventory before judging the proof. Do not self-repair missing assumptions or narrowed scope silently.",
  description="Proof redteam remediation for phase {phase_number}"
)
```

If `gpd-check-proof` still cannot produce a passed audit, keep the verification status fail-closed.
</step>

<step name="load_anchor_context">
Use `active_reference_context` from init JSON as a mandatory input to verification.

- If it names a benchmark, prior artifact, or must-read reference, verification must explicitly check it or report why it could not.
- Treat `effective_reference_intake` as the structured source of must-read refs, prior outputs, baselines, user anchors, and context gaps. `active_reference_context` is the readable rendering of that ledger, not its substitute.
- Treat `reference_artifacts_content` as supporting evidence for what comparisons remain decisive.
- Background literature may be reduced by mode; anchor checks may not.
</step>

<step name="load_protocol_bundle_context">
Use `protocol_bundle_context` from init JSON as additive specialized guidance.

- If `selected_protocol_bundle_ids` is non-empty, use `protocol_bundle_verifier_extensions` from init JSON as the primary source for bundle checklist extensions and treat them as extra prompts for evidence gathering.
- Call `get_bundle_checklist(selected_protocol_bundle_ids)` through the verification server only when the init payload lacks those extensions or when you need a fallback consistency check.
- Bundle guidance may add estimator checks, decisive artifact expectations, or domain-specific audits, but it does NOT replace the plan contract or reduce anchor obligations.
- Use `protocol_bundle_verifier_extensions` as the machine-readable quick map when deciding which contract-aware checks deserve deeper scrutiny first.
- If the phase has a PLAN `contract` and project-local anchors or prior-output paths matter, use this contract-check loop before finalizing the inventory:
  1. Call `suggest_contract_checks(contract, project_dir=...)`.
  2. Treat the returned items as the default contract-aware seed unless they are clearly inapplicable.
  3. For each returned check, start from `request_template`, satisfy `required_request_fields` and `schema_required_request_fields`, satisfy one full alternative from `schema_required_request_anyof_fields`, stay within `supported_binding_fields` for `request.binding`, and keep `project_dir` as the top-level absolute project root argument.
  4. Call `run_contract_check(request=..., project_dir=...)` so contract-aware checks are executed rather than only discovered.
</step>

<step name="check_active_session">
**First: Check for active verification sessions**

```bash
rg -l '^session_status: (validating|diagnosed)$' GPD/phases/*/*-VERIFICATION.md 2>/dev/null | sort | head -5
```

**If active sessions exist AND no $ARGUMENTS provided:**

Only treat files with `session_status: validating` or `session_status: diagnosed` as active researcher sessions.
Read each active file's frontmatter to extract canonical verification `status`, `session_status`, `phase`, and the Current Check section. Do not let `session_status` replace or overwrite the canonical verification `status`.

Display inline:

```
## Active Verification Sessions

| # | Phase | Session | Verification Status | Current Check | Progress |
|---|-------|---------|---------------------|---------------|----------|
| 1 | 04-dispersion | validating | gaps_found | 3. Limiting Cases | 2/6 |
| 2 | 05-numerics | diagnosed | expert_needed | 1. Convergence Test | 0/4 |

Reply with a number to resume, or provide a phase number to start new.
```

Wait for user response.

- If user replies with number (1, 2) -> Load that file, go to `resume_from_file`
- If user replies with phase number -> Treat as new session, go to `create_verification_file`

**If active sessions exist AND $ARGUMENTS provided:**

Check if session exists for that phase. If yes, offer to resume or restart.
If no, continue to `create_verification_file`.

**If no active sessions AND no $ARGUMENTS:**

```
No active verification sessions.

Provide a phase number to start validation (e.g., gpd:verify-work 4)
```

**If no active sessions AND $ARGUMENTS provided:**

Continue to `create_verification_file`.
</step>

<step name="find_summaries">
**Find what to validate:**

Use `phase_dir` from init (or run init if not already done).

```bash
ls "$phase_dir"/*SUMMARY.md 2>/dev/null
```

Read each phase-summary artifact to extract **deliverable names, file paths, and evidence locations only**. Do NOT trust phase-summary claims about correctness, convergence, or agreement with literature — those are exactly what you are validating. Use the phase summary as a map to find artifacts and comparison evidence, not as evidence that they are correct.

If a SUMMARY has `contract_results` or `comparison_verdicts`, use them only as evidence maps keyed to contract IDs. The PLAN `contract` remains the source of truth for what must be verified.

Also load the phase goal from ROADMAP.md to derive expected physics outcomes independently:

```bash
gpd --raw roadmap get-phase "${phase_number}"
```

</step>

<step name="extract_checks">
**Extract validatable contract-backed checks from PLAN `contract` first, then use phase-summary artifacts as an evidence map:**

Parse for:

1. **Claims** - Contract-backed statements the phase is supposed to establish
2. **Deliverables** - Analytical results, numerical outputs, plots, tables, code artifacts
3. **Acceptance tests** - Explicit tests that must pass for the phase to count as complete
4. **Reference actions** - Must-read anchors that require read / compare / cite / reproduce actions
5. **Forbidden proxies** - Outputs that would look like progress but do not establish success
6. **Suggested contract checks** - Decisive checks the verifier thinks should exist if the contract is incomplete
7. **Proof-redteam evidence** - Required `*-PROOF-REDTEAM.md` artifacts for theorem-style or `proof_obligation` work

Focus on VERIFIABLE RESEARCH OUTCOMES the researcher can recognize in the phase promise, not implementation details. Use contract IDs (`claim_id`, `deliverable_id`, `acceptance_test_id`, `reference_id`, `forbidden_proxy_id`) as canonical names throughout the verification file.
If a contract item is only meaningful as an internal process milestone, do not make it a researcher-facing check; map it to the user-visible claim or deliverable it was supposed to establish, or drop it from validation.

For each contract-backed check, create a validation record that includes **both qualitative expectations and a concrete computational test:**

- name: Brief check name
- expected: What the physics should show (specific, verifiable)
- computation: A specific numerical test the AI will perform before presenting to the researcher
- check_subject_kind: `claim|deliverable|acceptance_test|reference`
- subject_id: Contract ID when available

Keep `check_subject_kind` and `gap_subject_kind` aligned with the canonical frontmatter-safe subject vocabulary. Use `forbidden_proxy_id` for explicit proxy-rejection checks, and keep missing decisive checks in the `suggested_contract_checks` ledger instead of inventing extra body subject kinds.

Rules:

- If the contract already says a comparison against a benchmark / prior work / experiment / cross-method result is decisive, attach a comparison target so the final verification can emit a `comparison_verdict`. Do not mark the parent claim or acceptance test as passed until that decisive comparison is resolved. If the comparison was attempted but is still open, record `inconclusive` or `tension` instead of silently dropping it.
- If a forbidden proxy exists, create an explicit rejection check rather than assuming silence means success.
- If the contract lacks an obvious decisive check, create a structured `suggested_contract_checks` entry with a short rationale instead of silently dropping the concern.
- Only create `suggested_contract_checks` entries for obvious decisive gaps on user-visible targets, not for paperwork preferences or generic workflow niceties.
- Each `suggested_contract_checks` entry must stay structured: `check`, `reason`, optional paired `suggested_subject_kind` + `suggested_subject_id` when the gap can be bound to a known contract target, and `evidence_path`. If no target is known yet, omit both keys instead of leaving one blank. When the gap comes from `suggest_contract_checks(contract)`, copy the returned `check_key` into the frontmatter `check` field.
- For proof-bearing checks, create explicit validation records for theorem statement coverage, parameter coverage, hypothesis coverage, quantifier/domain coverage, conclusion-clause coverage, and special-case / counterexample probes. A theorem parameter that never appears in the proof is a failure, not a style issue.

**Examples with computational verification:**

- Derivation: "Derived Boltzmann equation from BBGKY hierarchy"
  -> Check: "Derivation of Boltzmann Equation"
  -> Expected: "Starting from the BBGKY hierarchy, the two-particle correlation is factored in the dilute gas limit. The collision integral should have the form of gain minus loss terms with cross-section weighting."
  -> Computation: "I will evaluate the collision integral at a test point (v1=[1,0,0], v2=[0,1,0]) and verify it has the correct structure: gain - loss with appropriate cross-section weighting."

- Calculation: "Computed critical temperature for 3D Ising model"
  -> Check: "Critical Temperature Value"
  -> Expected: "Tc/J should be approximately 4.51 for simple cubic lattice."
  -> Computation: "I will extract the computed Tc from the artifact, compute the exact value Tc/J = 4.5115..., and report the relative error."

- Plot: "Phase diagram as function of temperature and coupling"
  -> Check: "Phase Diagram Features"
  -> Expected: "Phase boundary should show expected topology: ordered phase at low T, disordered at high T."
  -> Computation: "I will evaluate the order parameter at 3 test points: (T=0.5*Tc, g=1) should be non-zero, (T=2*Tc, g=1) should be zero, and the boundary should cross at T=Tc."

- Limiting case: "Free-particle limit of interacting Green's function"
  -> Check: "Free-particle Limit"
  -> Expected: "G(k, omega) should reduce to 1/(omega - epsilon_k + i\*eta) when interaction V -> 0."
  -> Computation: "I will take V=0 in the expression from the artifact, simplify, and verify it equals the free-particle propagator. Then I will evaluate both at k=pi/2, omega=1.0 and compare numerically."

Skip internal/non-observable items (code refactors, file reorganization, checklist completion, etc.).
</step>

<step name="minimum_verification_floor">
**Regardless of profile (including exploratory), the pre-computation phase must satisfy these minimums:**

1. **Dimensional analysis**: At least one equation checked symbol-by-symbol for dimensional consistency
2. **Limiting case**: At least one limiting case independently re-derived (not just discussed qualitatively)
3. **Numerical spot-check with code execution**: At least one Python/SymPy script actually executed via shell, with the output captured and presented to the researcher

**Code output requirement:** The final verification artifact must contain at least one fenced code block showing actual execution output. A verification report with only text analysis and zero computational evidence is INCOMPLETE. If the pre-computation step produces no code outputs, flag the verification as incomplete before presenting to the researcher.

These 3 minimum checks must be among the checks presented to the researcher, even when the exploratory profile reduces the total check count.

For proof-bearing or `proof_obligation` work, an additional mandatory floor applies: every required `*-PROOF-REDTEAM.md` artifact must exist, must include theorem-coverage tables plus an adversarial probe, and must report `status: passed` before the verification session may end at `status: passed`.
</step>

<step name="precompute_checks">
**Before presenting checks to the researcher, perform computational verification on each deliverable.**

For each check:

1. **Read the artifact** to extract the actual expression/result/code
2. **Perform the computational test** specified in the check definition
3. **Record the result** (pass/fail/inconclusive) as pre-computed evidence

This gives the researcher concrete numbers to compare against, not just qualitative expectations.

```bash
# Example: pre-compute a spot-check before presenting to researcher
python3 -c "
import numpy as np
# Extract key expression from artifact
# Evaluate at test point
# Compare with expected
# print('Pre-check result: ...')
"
```

**If the pre-computation reveals an obvious error:** Still present the check to the researcher, but include your finding:
"I computed X at test point Y and got Z, but expected W. This suggests a possible error. Can you confirm?"

**If the pre-computation confirms the result:** Present with confidence:
"I independently computed X at test point Y and got Z, which matches the artifact. Does this agree with your understanding?"
</step>

<step name="create_verification_file">
**Create or extend verification file with all checks:**

```bash
mkdir -p "$phase_dir"
```

**Check for existing verification artifact** (e.g., from a prior `gpd:execute-phase` → `verify-phase` run):

```bash
EXISTING_VERIFICATION=$(ls "$phase_dir"/*-VERIFICATION.md 2>/dev/null | head -1)
```

If an existing verification artifact is found (e.g., from a prior `gpd:execute-phase` → `verify-phase` automated run):
1. Read it to preserve any prior automated verification results
2. Do NOT overwrite — instead, append a `## Researcher Validation` section after the existing content
3. The new researcher checks go under this section, keeping the automated checks intact
4. **Status merge rule:** The combined verification `status` uses the MORE RESTRICTIVE verification-report vocabulary (`passed|gaps_found|expert_needed|human_needed`). If automated verification passed but the researcher finds issues, the combined status becomes `gaps_found`. If automated found gaps but the researcher confirms they are acceptable, the combined status stays `gaps_found` unless the researcher explicitly upgrades each gap to `pass`. Keep `session_status` for conversational progress only.
5. If you report an aggregate independently confirmed tally, keep it in body prose or tables rather than adding a non-canonical verification frontmatter key

If no existing verification artifact exists, create a new one from scratch.

Build check list from extracted contract-backed checks, including computational test specifications.
Checks with non-empty `comparison_kind` are decisive and must end with either a recorded `comparison_verdict` or a recorded gap before the file can finish. Exploratory or partial verification is allowed to end at `inconclusive` or `tension`; it is not allowed to imply a pass from suggestive but non-decisive evidence.
If a decisive benchmark / cross-method check remains `partial`, `not_attempted`, or still lacks a decisive verdict, add a structured `suggested_contract_checks` entry before final validation. Do not replace that ledger with prose.
If proof-bearing work is present, mirror missing or open proof-redteam audits into the verification gaps. Never let the frontmatter `status` be `passed` while any required `*-PROOF-REDTEAM.md` artifact is missing, malformed, or reports `gaps_found` / `human_needed`.

If the PLAN has a `contract`, every body check in this file must carry the relevant `check_subject_kind`, `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`, `reference_ids`, and `forbidden_proxy_id` when applicable.
Mirror decisive verdicts into frontmatter `comparison_verdicts`. The body `## Comparison Verdicts` section is a readable summary, not a substitute for the frontmatter ledger consumed by validation and downstream publication tooling.

Create file (or extend existing):

```markdown
---
phase: 01-benchmark
verified: 2026-04-06T00:00:00Z
status: gaps_found
# Allowed status values: passed|gaps_found|expert_needed|human_needed
score: 0/4 contract targets verified
plan_contract_ref: GPD/phases/01-benchmark/01-plan-PLAN.md#/contract
contract_results:
  claims:
    claim-main:
      status: not_attempted
      summary: "verification not started yet"
  deliverables:
    deliverable-main:
      status: not_attempted
      summary: "verification not started yet"
  acceptance_tests:
    acceptance-test-main:
      status: not_attempted
      summary: "verification not started yet"
  references:
    reference-main:
      status: missing
      completed_actions: []
      missing_actions: [read]
      summary: "verification not started yet"
  forbidden_proxies:
    forbidden-proxy-main:
      status: unresolved
      notes: "verification not started yet"
  uncertainty_markers:
    weakest_anchors: [anchor-1]
    unvalidated_assumptions: [assumption-1]
    competing_explanations: [alternative-1]
    disconfirming_observations: [observation-1]
comparison_verdicts:
  - subject_id: claim-main
    subject_kind: claim
    subject_role: decisive
    reference_id: reference-main
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: inconclusive
    recommended_action: "close the decisive benchmark once the evidence is written"
    notes: "The benchmark evidence is close but not yet decisive."
suggested_contract_checks:
  - check: "missing decisive benchmark comparison"
    reason: "The contract still needs a named benchmark check for the main claim."
    suggested_subject_kind: acceptance_test
    suggested_subject_id: acceptance-test-main
    evidence_path: "artifact path or expected evidence path"
  - check: "missing decisive reference comparison"
    reason: "The reference-backed comparison is still missing."
    suggested_subject_kind: reference
    suggested_subject_id: reference-main
    evidence_path: "artifact path or expected evidence path"
source: ["list of phase-summary files"]
started: "ISO timestamp"
updated: "ISO timestamp"
session_status: validating
# Allowed session_status values: validating|completed|diagnosed
---

## Current Check

<!-- OVERWRITE each check - shows where we are -->
<!-- Omit unused `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`, and `forbidden_proxy_id` fields instead of leaving blank placeholders. -->
<!-- Copy-safe scalar examples: `expected: "verifiable physics outcome"` and `computation: "specific numerical test performed"`. -->
<!-- Allowed body enum values:
`check_subject_kind`: claim|deliverable|acceptance_test|reference
`comparison_kind`: benchmark|prior_work|experiment|cross_method|baseline|other
`suggested_subject_kind`: claim|deliverable|acceptance_test|reference
-->

number: 1
name: "benchmark comparison"
check_subject_kind: claim
subject_id: "claim-main"
claim_id: "claim-main"
reference_ids: ["reference-main"]
comparison_kind: benchmark
comparison_reference_id: "reference-main"
# If this check is not comparison-backed yet, omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders.
expected: |
  The derived benchmark should match the reference within 1%.
computation: |
  Evaluated the benchmark at k = 0.5 and k = 1.0.
precomputed_result: |
  Independent arithmetic gives a relative error of 0.006.
# Benchmark acceptance tests require `comparison_kind: benchmark`.
# cross-method acceptance tests require `comparison_kind: cross_method`.
suggested_contract_checks:
  # If you cannot bind the gap to a known contract target yet, omit both
  # `suggested_subject_kind` and `suggested_subject_id` instead of leaving one blank.
  - check: "missing decisive check"
    reason: "The decisive benchmark comparison still needs an explicit contract target."
    suggested_subject_kind: acceptance_test
    suggested_subject_id: "acceptance-test-main"
    evidence_path: "GPD/phases/01-benchmark/benchmark-comparison.csv"
  # Add a reference-backed decisive gap here whenever a benchmark reference or
  # a reference with required_actions including `compare` is still incomplete.
awaiting: researcher response

## Checks

### 1. Benchmark Comparison

<!-- Include only the ID keys that actually bind this check.
Follow the omission rule from current check instead of leaving blank placeholder strings. -->

check_subject_kind: claim
subject_id: "claim-main"
claim_id: "claim-main"
reference_ids: ["reference-main"]
comparison_kind: benchmark
comparison_reference_id: "reference-main"
expected: "The benchmark comparison should land within the 1% tolerance."
computation: "Evaluated the benchmark at the configured test points."
precomputed_result: "Independent arithmetic gives a relative error of 0.006."
suggested_contract_checks:
  # If you cannot bind the gap to a known contract target yet, omit both
  # `suggested_subject_kind` and `suggested_subject_id` instead of leaving one blank.
  - check: "missing decisive check"
    reason: "The decisive benchmark comparison still needs an explicit contract target."
    suggested_subject_kind: acceptance_test
    suggested_subject_id: "acceptance-test-main"
    evidence_path: "GPD/phases/01-benchmark/benchmark-comparison.csv"
result: "pending"

### 2. Benchmark Pass

expected: "The benchmark comparison should land within the 1% tolerance."
computation: "Evaluated the benchmark at the configured test points."
precomputed_result: "Independent arithmetic gives a relative error of 0.006."
result: "pending"

...

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
comparison_verdicts_recorded: 0
forbidden_proxies_rejected: 0

## Comparison Verdicts

[]

## Suggested Contract Checks

[]

## Gaps

[]
```

Write to `${phase_dir}/${phase_number}-VERIFICATION.md`

If the project has an active convention lock, include the machine-readable `ASSERT_CONVENTION` comment immediately after the YAML frontmatter using the canonical lock keys and exact lock values from init / `gpd convention list`. The canonical shape is documented in `@{GPD_INSTALL_DIR}/templates/verification-report.md`, and changed verification files fail `gpd pre-commit-check` when this header is missing or mismatched against the active lock.

Proceed to `present_check`.
</step>

<step name="present_check">
**Present current check to researcher with computational evidence:**

Read Current Check section from verification file.

Display using checkpoint box format:

```
+================================================+
|  CHECKPOINT: Research Validation Required      |
+================================================+

**Check {number}: {name}**

{expected}

**Independent computation:**
{computation description and result}

--------------------------------------------------------------
-> Confirm this matches your result, or describe what differs
--------------------------------------------------------------
```

The key upgrade: instead of just asking "does it look right?", present concrete numbers from your independent computation so the researcher has something specific to compare against.

**Guide the researcher through numerical spot-checks when appropriate:**

For derivation checks:

```
I independently evaluated your expression at [test point]:
  Your expression gives: [value]
  Expected (from [source]): [value]
  Relative error: [value]

Does this match what you see when you evaluate at this point?
```

For limiting case checks:

```
I took the [limit name] limit of your final expression:
  Your expression in the limit: [simplified form]
  Known result in this limit: [known form]
  Agreement: [yes/no, with details]

Can you confirm this is the correct limiting behavior?
```

For numerical checks:

```
I ran your code at resolutions N=[50, 100, 200]:
  N=50:  result = [value]
  N=100: result = [value]
  N=200: result = [value]
  Convergence rate: O(1/N^[p])

Does this convergence rate match the expected order of your method?
```

Wait for researcher response (plain text).
</step>

<step name="process_response">
**Process researcher response and update file:**

**If response indicates pass:**

- Empty response, "yes", "y", "ok", "pass", "next", "confirmed", "correct"

Update Checks section:

```
### 1. Benchmark Comparison
expected: The benchmark comparison should land within the 1% tolerance.
computation: Evaluated the benchmark at the configured test points.
precomputed_result: Independent arithmetic gives a relative error of 0.006.
result: pass
confidence: independently confirmed
```

**If response indicates skip:**

- "skip", "cannot check", "n/a", "not applicable"

Update Checks section:

```
### 2. Benchmark Comparison
expected: The benchmark comparison is not needed for this check.
computation: The check was not run because it is outside the current scope.
precomputed_result: No computation performed.
result: skipped
reason: The researcher confirmed this check was outside the current scope.
```

**If response is anything else:**

- Treat as issue description

Infer severity from description:

- Contains: wrong, error, diverges, blows up, unphysical, violates -> blocker
- Contains: disagrees, inconsistent, does not match, off by, missing -> major
- Contains: approximate, close but, small discrepancy, minor -> minor
- Contains: label, formatting, axis, legend, cosmetic -> cosmetic
- Default if unclear: major

Update Checks section:

```
### 3. Benchmark Comparison
expected: The benchmark comparison should land within the 1% tolerance.
computation: Evaluated the benchmark at the configured test points.
precomputed_result: Independent arithmetic gives a relative error of 0.006.
result: issue
reported: "The benchmark comparison still needs one more reference point."
severity: major
```

Append to Gaps section (structured YAML for plan-phase --gaps).
Use the same omission rule here: emit only the ID keys that actually bind the gap.

```yaml
- gap_subject_kind: "claim"
  subject_id: "claim-main"
  expectation: "The benchmark comparison should land within the 1% tolerance."
  expected_check: "The independent calculation should reproduce the same sign and scale."
  claim_id: "claim-main"
  reference_ids: ["reference-main"]
  comparison_kind: "benchmark"
  comparison_reference_id: "reference-main"
  status: failed
  reason: "Researcher reported: the benchmark comparison still needs one more reference point."
  computation_evidence: "Independent arithmetic gave a relative error of 0.012."
  suggested_contract_checks: []
  severity: major
  check: 1
  artifacts: [] # Filled by diagnosis
  missing: [] # Filled by diagnosis
```

**After any response:**

Update Summary counts.
Update frontmatter.updated timestamp.

**REQUIREMENTS.md traceability update (on pass only):**

If the check passed AND the check name or expected outcome corresponds to a requirement ID (REQ-*) from `GPD/REQUIREMENTS.md`, update the requirement's status:

1. Read `GPD/REQUIREMENTS.md` (skip if file doesn't exist)
2. Search for the matching REQ-ID in the requirements table
3. Update the requirement row's validation status:
   - Change status cell to `Validated`
   - Append ` (Phase {phase_number}, Check {N})` to the evidence/notes cell
4. Write back the updated REQUIREMENTS.md

**Matching logic:**

- Check name contains `REQ-NNN` literally -> direct match
- Check expected outcome references a requirement by ID -> direct match
- Check validates a deliverable that maps to a known requirement -> fuzzy match (note the match in the verification artifact but don't auto-update REQUIREMENTS.md for fuzzy matches)

Skip this sub-step silently if no REQUIREMENTS.md exists or no REQ-IDs match.

If more checks remain -> Update Current Check, go to `present_check`
If no more checks -> Go to `complete_session`
</step>

<step name="resume_from_file">
**Resume validation from file:**

Read the full verification file.

Find first check with `result: pending`.

Announce:

```
Resuming: Phase {phase_number} Research Validation
Progress: {passed + issues + skipped}/{total}
Issues found so far: {issues count}

Continuing from Check {N}...
```

Update Current Check section with the pending check.
Proceed to `present_check`.
</step>

<step name="researcher_custom_checks">
**After presenting all automated checks, invite researcher to add their own:**

```
All {N} automated checks complete ({passed} passed, {issues} issues, {skipped} skipped).

Are there any additional physics checks you'd like to verify?
Examples: "check Ward identity", "verify sum rule", "test at strong coupling"
(Type "done" to skip)
```

**If researcher provides custom checks:**

For each custom check:
1. Parse the description into a check name and expected behavior
2. Attempt to pre-compute the check (read relevant artifacts, run test if possible)
3. Present the result using the same checkpoint box format as automated checks
4. Process the response identically to automated checks (pass/issue/skip)
5. Append to the Checks section in the verification artifact with `source: researcher`

Custom checks are numbered continuing from the last automated check (e.g., if 6 automated checks, first custom check is 7).

**If researcher says "done", "no", "skip", or empty:** Proceed to `cross_phase_uncertainty_audit`.
</step>

<step name="cross_phase_uncertainty_audit">
**Audit uncertainty propagation across phases with researcher.**

This step checks that uncertainties from prior phases propagate correctly into the current phase's results — the #1 gap found by physics verification audits.

**1. Identify inherited quantities:**

Read phase summary files (current and prior phases). Find quantities consumed by the current phase that were produced by earlier phases.

```bash
# Check if prior phases declared uncertainty budgets
for PRIOR_SUMMARY in $(ls GPD/phases/*/*SUMMARY.md 2>/dev/null | sort); do
  grep -l "Uncertainty Budget\|uncertainty\|±\|\\\\pm" "$PRIOR_SUMMARY" 2>/dev/null
done
```

**2. If inherited quantities exist, present uncertainty audit to researcher:**

For each inherited quantity used in the current phase:

```
+================================================+
|  UNCERTAINTY CHECK: {quantity_name}            |
+================================================+

Source: Phase {N} summary artifact
Value: {central_value} ± {uncertainty}
Used in: {current phase equation/computation}

Propagated uncertainty in final result:
{independently computed propagated uncertainty}

Does this uncertainty budget look correct? (yes/no/skip)
```

**3. Check for catastrophic cancellation (Error #102):**

If two quantities with comparable magnitudes are subtracted, compute the relative uncertainty of the difference:

```bash
python3 -c "
a, da = ${VALUE_A}, ${UNCERT_A}
b, db = ${VALUE_B}, ${UNCERT_B}
diff = abs(a - b)
d_diff = (da**2 + db**2)**0.5
if diff > 0:
    rel = d_diff / diff
    print(f'Relative uncertainty of difference: {rel:.2%}')
    if rel > 1.0:
        print('WARNING: Catastrophic cancellation — uncertainty exceeds the difference')
else:
    print('WARNING: Exact cancellation — difference is zero')
"
```

**4. Record findings in the verification artifact:**

Add an "Uncertainty Propagation Audit" section with:
- List of inherited quantities and their declared uncertainties
- Propagation check results (pass/fail per quantity)
- Any catastrophic cancellation warnings
- Researcher responses

If no inherited quantities exist (Phase 1 or self-contained): note "N/A — no cross-phase uncertainty dependencies" and proceed.

Proceed to `complete_session`.
</step>

<step name="complete_session">
**Complete validation and commit:**

Update frontmatter:

- verified: [now]
- status: preserve the final verification outcome vocabulary used by `verification-report.md` (`passed | gaps_found | expert_needed | human_needed`)
- updated: [now]
- score: [final contract-backed verification progress summary]
- session_status: completed

Clear Current Check section:

```
## Current Check

[validation complete]
```

Commit the verification file:

```bash
gpd validate verification-contract "${phase_dir}/${phase_number}-VERIFICATION.md"

PRE_CHECK=$(gpd pre-commit-check --files "${phase_dir}/${phase_number}-VERIFICATION.md" 2>&1) || true
echo "$PRE_CHECK"

gpd commit "verify(${phase_number}): complete research validation - {passed} passed, {issues} issues" --files "${phase_dir}/${phase_number}-VERIFICATION.md"
```

Present summary:

```
## Research Validation Complete: Phase {phase_number}

| Result | Count |
|--------|-------|
| Passed | {N}   |
| Issues | {N}   |
| Skipped| {N}   |

### Verification Confidence

| Confidence Level | Count |
|------------------|-------|
| Independently Confirmed | {N} |
| Structurally Present    | {N} |
| Unable to Verify        | {N} |

[If issues > 0:]
### Issues Found

[List from Issues section, including computation evidence for each]
```

**If issues > 0:** Proceed to `diagnose_issues`

**If issues == 0:**

```
All checks passed. Research validated. Ready to continue.

- `gpd:plan-phase {next}` -- Plan next research phase
- `gpd:execute-phase {next}` -- Execute next research phase
```

</step>

<step name="diagnose_issues">
**Diagnose root causes before planning fixes:**

**Severity gate:** Only spawn parallel diagnosis agents for major+ issues. Minor and cosmetic issues are reported directly without investigation overhead.

**1. Partition issues by severity:**

- **Major+ issues** (blocker, major): Collect into `investigate_issues` list
- **Minor/cosmetic issues** (minor, cosmetic): Collect into `report_directly` list

**2. Present minor/cosmetic issues directly:**

If `report_directly` is non-empty:

```
### Minor/Cosmetic Issues (no investigation needed)

| # | Check | Severity | Reported |
|---|-------|----------|----------|
| {N} | {name} | {severity} | {verbatim response} |
```

These are noted in the verification artifact but do not trigger investigation agents.

**3. Investigate major+ issues:**

If `investigate_issues` is non-empty:

```
---

{N} major+ issues found. Diagnosing root causes...

Spawning parallel investigation agents for each major+ issue.
({M} minor/cosmetic issues reported directly — no investigation needed.)
```

- Load debug workflow
- Follow @{GPD_INSTALL_DIR}/workflows/debug.md
- Spawn parallel investigation agents for each issue in `investigate_issues`
- **Include computation evidence from pre-checks and researcher reports in the diagnosis context** — the investigator should know what specific test failed and what values were obtained
- Collect root causes
- Update the verification artifact with root causes
- Proceed to `diagnosis_review`

**4. If only minor/cosmetic issues exist (no major+ issues):**

Skip investigation entirely. Present summary and offer options:

```
All {N} issues are minor or cosmetic — no root cause investigation needed.

Options:
1. Plan fixes for minor issues
2. Accept as-is — issues are low-impact
3. Investigate anyway — I want deeper analysis
```

Diagnosis runs automatically for major+ issues — no researcher prompt. Parallel agents investigate simultaneously, so overhead is minimal and fixes are more accurate.
</step>

<step name="diagnosis_review">
## Diagnosis Review

Present the diagnosis results to the user:

| Issue | Root Cause | Confidence |
|-------|-----------|------------|
{diagnosis results from investigation agents}

Use ask_user:

- header: "Fix Approach"
- question: "How would you like to handle the identified issues?"
- options:
  - "Auto-plan fixes (Recommended)" — Spawn planner for systematic gap closure
  - "Investigate manually" — I want to explore the issues myself first
  - "Accept as-is" — The issues are minor, results are acceptable

**If "Auto-plan fixes":** Continue to plan_gap_closure step.
**If "Investigate manually":** Present the detailed diagnosis and pause. Offer `gpd:debug` for structured investigation.
**If "Accept as-is":** Skip gap closure, mark phase verified with noted caveats.
</step>

<step name="plan_gap_closure">
**Auto-plan fixes from diagnosed gaps:**

Display:

```
====================================================
 GPD > PLANNING FIXES
====================================================

* Spawning planner for gap closure...
```

Spawn gpd-planner in --gaps mode:
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="""First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.

<planning_context>

**Phase:** {phase_number}
**Mode:** gap_closure
**Project Contract:** {project_contract}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

Use the shared planner template, phase template, and `templates/plan-contract-schema.md` before drafting the fix plan. If the downstream fix plan needs specialized tooling or any other machine-checkable hard validation requirement, surface it in PLAN frontmatter `tool_requirements`.

<files_to_read>
Read these files using the file_read tool:
- Validation with diagnoses: ${phase_dir}/${phase_number}-VERIFICATION.md
- Structured init payload: `project_contract_gate`, `effective_reference_intake`, `active_reference_context`, `derived_active_references`, `citation_source_files`, `derived_citation_sources`, `reference_artifacts_content`
- Roadmap: GPD/ROADMAP.md
</files_to_read>

</planning_context>

<downstream_consumer>
Output consumed by gpd:execute-phase
Plans must be executable prompts.
</downstream_consumer>
""",
  subagent_type="gpd-planner",
  model="{planner_model}",
  readonly=false,
  description="Plan gap fixes for Phase {phase_number}"
)
```

On return:

**If the planner agent fails to spawn or returns an error:** Check if any PLAN.md files were written to the phase directory. If plans exist, proceed to `verify_gap_plans`. If no plans, offer: 1) Retry planner, 2) Create fix plans manually in the main context, 3) Skip gap closure and mark gaps as deferred.

- **PLANNING COMPLETE:** Proceed to `verify_gap_plans`
- **PLANNING INCONCLUSIVE:** Report and offer manual intervention
  </step>

<step name="verify_gap_plans">
**Verify fix plans with checker:**

Display:

```
====================================================
 GPD > VERIFYING FIX PLANS
====================================================

* Spawning plan checker...
```

Initialize: `iteration_count = 1`

Spawn gpd-plan-checker:

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="""First, read {GPD_AGENTS_DIR}/gpd-plan-checker.md for your role and instructions.

<verification_context>

**Phase:** {phase_number}
**Phase Goal:** Close diagnosed gaps from research validation

<files_to_read>
Read all PLAN.md files in ${phase_dir}/ using the file_read tool.
</files_to_read>

</verification_context>

<expected_output>
Return one of:
- ## VERIFICATION PASSED -- all checks pass
- ## ISSUES FOUND -- structured issue list
</expected_output>
""",
  subagent_type="gpd-plan-checker",
  model="{checker_model}",
  readonly=false,
  description="Verify Phase {phase_number} fix plans"
)
```

On return:

**If the plan-checker agent fails to spawn or returns an error:** Proceed without plan verification — the plans will still be executable. Note that plans were not verified and recommend running `gpd:plan-phase --gaps` to re-verify if needed.

- **VERIFICATION PASSED:** Proceed to `present_ready`
- **ISSUES FOUND:** Proceed to `revision_loop`
  </step>

<step name="revision_loop">
**Iterate planner <-> checker until plans pass (max 3):**

**If iteration_count < 3:**

Display: `Sending back to planner for revision... (iteration {N}/3)`

Spawn gpd-planner with revision context:

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="""First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.

<revision_context>

**Phase:** {phase_number}
**Mode:** revision
**Project Contract:** {project_contract}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

Use the shared planner template, phase template, and `templates/plan-contract-schema.md` before rewriting the fix plan. If the revised fix plan still needs specialized tooling or any other machine-checkable hard validation requirement, keep it in PLAN frontmatter `tool_requirements`.

<files_to_read>
Read all PLAN.md files in ${phase_dir}/ using the file_read tool.
</files_to_read>

**Checker issues:**
{structured_issues_from_checker}

</revision_context>

<instructions>
Read existing PLAN.md files. Make targeted updates to address checker issues.
Do NOT replan from scratch unless issues are fundamental.
</instructions>
""",
  subagent_type="gpd-planner",
  model="{planner_model}",
  readonly=false,
  description="Revise Phase {phase_number} plans"
)
```

**If the revision planner agent fails to spawn or returns an error:** Check if any revised PLAN.md files were written to the phase directory. If revisions exist, proceed to re-check via `verify_gap_plans`. If no revisions, offer: 1) Retry revision planner, 2) Apply revisions manually in the main context, 3) Force proceed with current gap-fix plans despite checker issues.

After planner returns -> spawn checker again (verify_gap_plans logic)
Increment iteration_count

**If iteration_count >= 3:**

Display: `Max iterations reached. {N} issues remain.`

Offer options:

1. Force proceed (execute despite issues)
2. Provide guidance (researcher gives direction, retry)
3. Abandon (exit, researcher runs gpd:plan-phase manually)

Wait for researcher response.
</step>

<step name="present_ready">
**Present completion and next steps:**

```
====================================================
 GPD > FIXES READY
====================================================

**Phase {X}: {Name}** -- {N} gap(s) diagnosed, {M} fix plan(s) created

| Contract Target | Root Cause | Computation Evidence | Fix Plan |
|-----------------|------------|---------------------|----------|
| {subject-id or expected check 1} | {root_cause} | {what test showed} | {phase_number}-04 |
| {subject-id or expected check 2} | {root_cause} | {what test showed} | {phase_number}-04 |

Plans verified and ready for execution.

---------------------------------------------------------------

## > Next Up

**Execute fixes** -- run fix plans

`/clear` then `gpd:execute-phase {phase_number} --gaps-only`

---------------------------------------------------------------
```

</step>

</process>

<update_rules>
**Batched writes for efficiency:**

Keep results in memory. Write to file only when:

1. **Issue found** -- Preserve the problem immediately
2. **Session complete** -- Final write before commit
3. **Checkpoint** -- Every 5 passed checks (safety net)

| Section             | Rule      | When Written      |
| ------------------- | --------- | ----------------- |
| Frontmatter.status  | OVERWRITE | Start, complete   |
| Frontmatter.updated | OVERWRITE | On any file write |
| Current Check       | OVERWRITE | On any file write |
| Checks.{N}.result   | OVERWRITE | On any file write |
| Summary             | OVERWRITE | On any file write |
| Gaps                | APPEND    | When issue found  |

On context reset: File shows last checkpoint. Resume from there.
</update_rules>

<severity_inference>
**Infer severity from researcher's natural language:**

| Researcher says                                                 | Infer    |
| --------------------------------------------------------------- | -------- |
| "wrong sign", "diverges", "unphysical", "violates conservation" | blocker  |
| "disagrees with literature", "off by factor", "missing term"    | major    |
| "close but not exact", "small discrepancy", "approximate"       | minor    |
| "axis label", "legend", "formatting", "color"                   | cosmetic |

Default to **major** if unclear. Researcher can correct if needed.

**Never ask "how severe is this?"** - just infer and move on.
</severity_inference>

<success_criteria>

- [ ] Verification file created with checks sourced from the PLAN `contract` first, then phase-summary evidence maps, including computational test specifications
- [ ] Checks stay grounded in user-visible contract targets rather than internal process markers
- [ ] **Minimum verification floor met**: dimensional analysis + limiting case + numerical spot-check with code execution
- [ ] **Verification artifact contains at least one code output block** (actual execution result, not just text analysis)
- [ ] **Pre-computation performed** on each check before presenting to researcher
- [ ] Checks presented one at a time with expected physics outcome AND computation evidence
- [ ] **Numerical spot-checks** presented with concrete values for researcher to compare
- [ ] **Limiting cases independently re-derived** and presented to researcher for confirmation
- [ ] **Convergence data** computed and presented for numerical results
- [ ] Researcher responses processed as pass/issue/skip
- [ ] Confidence rating assigned to each passed check (independently confirmed / structurally present)
- [ ] Severity inferred from description (never asked)
- [ ] Batched writes: on issue, every 5 passes, or completion
- [ ] Committed on completion
- [ ] Forbidden proxies explicitly checked and rejected or escalated
- [ ] Decisive comparison outcomes recorded as `comparison_verdicts` when applicable, including `inconclusive` / `tension` when that is the honest state
- [ ] Parent claims / acceptance tests do not pass while decisive comparisons remain unresolved
- [ ] Missing decisive checks recorded as structured `suggested_contract_checks`
- [ ] Cross-phase uncertainty audit performed (or N/A noted for Phase 1)
- [ ] Catastrophic cancellation check for subtracted inherited quantities
- [ ] If issues: parallel investigation agents diagnose root causes (with computation evidence)
- [ ] If issues: gpd-planner creates fix plans (gap_closure mode)
- [ ] If issues: gpd-plan-checker verifies fix plans
- [ ] If issues: revision loop until plans pass (max 3 iterations)
- [ ] Ready for `gpd:execute-phase --gaps-only` when complete
- [ ] REQUIREMENTS.md updated for any passed checks matching REQ-IDs (if REQUIREMENTS.md exists)

</success_criteria>

<purpose>
Verify research phase goal achievement through decisive evidence. Check that the
phase delivered the promised research outcome by testing the physics: substitute
values, re-derive limits, trace dimensions, run independent computations, and
for proof obligations audit theorem-to-proof coverage adversarially.

Executed by a verification subagent spawned from `execute-phase.md`.

`verify-phase` is the compact root authority for phase verification handoff,
target selection, fail-closed proof gates, report helper usage, and artifact
return routing. Shared mechanics live in
`references/verification/core/verification-child-return-contract.md`; status
vocabulary lives in `references/verification/verification-status-authority.md`;
computational procedures live in the verification references listed below.

The standalone `gpd:verify-work` workflow reuses the same verification criteria
through `verify-work.md`; this file itself is executed by the execute-phase
orchestrator.
</purpose>

<core_principle>
**Task completion != Goal achievement**

Goal-backward verification asks:

1. What contract-backed outcomes must be true for the research goal to be achieved?
2. What artifacts must exist for those outcomes to hold?
3. What checks must validate those artifacts as scientifically trustworthy?
4. What forbidden proxies must be rejected because they look like progress but
   do not establish the claim?

Then verify each level against the actual research artifacts by doing physics,
not by pattern-matching.

**Fundamental rule: every verification check must involve decisive evidence,
not just text search.** For most targets this means executed computation. For
proof-bearing or `proof_obligation` targets it means theorem-to-proof audit plus
an adversarial special-case or counterexample probe. Plain text search never
suffices.

| Verification theater | Real verification |
| --- | --- |
| Search for "limit" | Take the limit and compare with a known result |
| Search for "dimensions" | Assign dimensions and check every term |
| Count imports or files | Run the code and inspect output |
| Trust polished algebra | Inventory hypotheses, quantifiers, parameters, and conclusions |
</core_principle>

<required_reading>
Do not raw-include the verification library at workflow load. Load references only at the consuming step:
quick checklist (`verification-quick-reference.md`), universal checks (`verification-core.md`), numerical checks (`verification-numerical.md`), executable oracle templates (`computational-verification-templates.md`), child-return/artifact gate (`verification-child-return-contract.md`), status vocabulary (`verification-status-authority.md`), independence rules (`verification-independence.md`), and uncertainty protocol (`error-propagation-protocol.md`). Use `verification_report_skeleton_bridge` for gap-only reports and `verification_report_finalizer_bridge` for typed outcomes; open templates only when helper/validator errors require them.
</required_reading>

<process>

<step name="load_context" priority="first">
Load phase operation context:

```bash
INIT=$(gpd --raw init phase-op "${PHASE_ARG}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP; surface the error.
fi
```

Extract from init JSON: phase identity/inventory (`phase_found`, `phase_dir`, `phase_number`, `phase_name`, `has_plans`, `plan_count`), contract fields (`project_contract`, validation/load/gate info, `contract_intake`), reference/bundle carry-forward (`effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`, selected bundle IDs, load manifest, context, verifier extensions), proof-review status, and the verification report skeleton/finalizer bridges.

If `phase_found` is false:

```text
ERROR: Phase not found: ${PHASE_ARG}

Available phases:
$(gpd phase list)
```

Then load phase details:

```bash
gpd --raw roadmap get-phase "${phase_number}"
grep -E "^| ${phase_number}" GPD/REQUIREMENTS.md 2>/dev/null
```

Use the ROADMAP phase goal as the outcome to verify, not the task list. Extract
PLAN frontmatter contract only:

```bash
for plan in "$phase_dir"/PLAN.md "$phase_dir"/*-PLAN.md; do
  gpd frontmatter get "$plan" --field contract
done
```

Verification context includes the phase goal, PLAN frontmatter contract,
artifact paths, `GPD/STATE.md`, `GPD/config.json`, and visible
contract/reference carry-forward context when `project_contract_gate.visible` is
true. Exclude full PLAN bodies, summaries, execution logs, and agent
conversation history except for scoped boundary checks called out below.

If `derived_manuscript_proof_review_status` is present, use it as the
structured freshness summary for any manuscript-local proof-bearing artifact and
keep the corresponding `*-PROOF-REDTEAM.md` artifact authoritative for pass/fail
decisions.

If `project_contract_gate.visible` is true, keep `project_contract`,
`contract_intake`, `effective_reference_intake`, `active_reference_context`,
`reference_artifacts_content`, `selected_protocol_bundle_ids`,
`protocol_bundle_load_manifest`, `protocol_bundle_context`, and
`protocol_bundle_verifier_extensions` visible to the verifier even when
`project_contract_gate.authoritative` is false. They are carry-forward context,
not authoritative scope, until the gate clears. Use
`protocol_bundle_verifier_extensions` as the primary bundle-extension surface
when selected bundle IDs are present; `protocol_bundle_context` remains the
readable projection. Stable knowledge docs are reviewed background synthesis for
check selection and interpretation; they do not override the contract, the gate,
or decisive evidence.
</step>

<step name="establish_contract_targets">
Use the PLAN `contract` block as the canonical target definition. Verification
must be keyed to user-visible contract IDs (`claim`, `deliverable`,
`acceptance_test`, `reference`, `forbidden_proxy`) rather than task prose.
Verification targets must stay user-visible: a researcher should be able to
point to the promised claim, artifact, comparison, or forbidden proxy in both
the contract and the report.

Treat these as separate obligations:

- `claims`: whether the physics claim is actually established.
- `deliverables`: whether the artifact exists and is substantively correct.
- `acceptance_tests`: whether decisive checks actually passed.
- `references`: whether required actions (`read`, `compare`, `cite`, etc.) were completed.
- `forbidden_proxies`: whether tempting non-decisive substitutes were explicitly rejected.
- decisive comparisons: emit `comparison_verdicts` for benchmark, prior-work,
  experiment, cross-method, or baseline checks; use `inconclusive` or `tension`
  honestly when evidence does not justify `pass`.

When project-local anchors or prior-output paths matter, run `gpd --raw verify suggest-checks --contract <file|-> --project-dir DIR [--active-checks <id>,... ]`, fold applicable returned checks into the plan, build each request from its template with the required/any-of fields and supported bindings, pass the absolute project root through the `--project-dir` option and never as a `project_dir` payload key, and execute `gpd --raw verify contract-check --payload <file|-> [--project-dir DIR]`.

Schema/helper field names that must remain visible when helper errors are repaired: `request_template`, `required_request_fields`, `supported_binding_fields`, `schema_required_request_fields`, and `schema_required_request_anyof_fields`.
Reference paths stay staged, not raw-included: `{GPD_INSTALL_DIR}/references/verification/meta/verification-independence.md` and `{GPD_INSTALL_DIR}/templates/contract-results-schema.md`.

If no frontmatter contract exists, derive a contract-like target set from the
phase goal: claims, deliverables, acceptance tests, required comparisons, and
forbidden proxies. Every derived claim must be checkable by computation,
substitution, limiting behavior, or a proof audit; outcomes that can only be
grepped are not verification targets.

If the plan contract omits an obvious decisive check, record a structured
`suggested_contract_checks` entry rather than silently ignoring it. Record only
decisive, user-visible gaps. Every entry must include `check`, `reason`,
`suggested_subject_kind`, `suggested_subject_id` when known, and
`evidence_path`. When the gap comes from `gpd --raw verify suggest-checks`,
copy the returned `check_key` into the frontmatter `check` field.

If a theorem-style claim or `proof_obligation` lacks a structured theorem
inventory, derive one before continuing: theorem statement, named parameters,
hypotheses, quantifier/domain obligations, and conclusion clauses.
</step>

<step name="proof_obligation_gate">
Detect proof-bearing verification targets.

Use the shared verification child-return contract for generic handoff mechanics;
the proof-redteam requirements here are authoritative. Load
`{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-workflow-gate.md`
only when a target is proof-bearing.

For each proof-bearing plan or claim, require the sibling
`*-PROOF-REDTEAM.md` artifact. Missing artifact, missing theorem inventory, or
`status != passed` is a blocking gap. Do not allow `status: passed` in the phase
verification report while any required proof-redteam artifact is missing,
stale, malformed, or open.

When runtime delegation is available and the audit is missing, malformed, stale,
or non-passing, spawn `gpd-check-proof` once to repair the gap before finalizing
the verdict. If the proof critic cannot produce a passed audit, keep the target
blocked rather than inferring theorem-proof alignment from the verifier context.
</step>

<step name="proof_redteam_repair">
Resolve the proof critic and run one repair handoff:

```bash
CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)
```

Runtime delegation is a single-turn handoff: the spawned agent checkpoints and returns if user input is needed; this run does not wait inside the same task. Load `proof-redteam-workflow-gate.md` for the scoped spawn contract, helper commands (`gpd proof-redteam skeleton`, `gpd validate proof-redteam`), allowed path `${phase_dir}/${phase_number}-PROOF-REDTEAM.md`, and repair prompt. Never trust return text alone; after return, re-open the artifact and require `status: passed`.

```
task(
  subagent_type="gpd-check-proof",
  model="{check_proof_model}",
  readonly=false,
  prompt="Proof-redteam repair handoff. Load {GPD_INSTALL_DIR}/references/verification/core/proof-redteam-workflow-gate.md for the `request_template`, helper commands, and validation gate.

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - \"${phase_dir}/${phase_number}-PROOF-REDTEAM.md\"
expected_artifacts:
  - \"${phase_dir}/${phase_number}-PROOF-REDTEAM.md\"
shared_state_policy: return_only
</spawn_contract>

Read the phase PLAN, SUMMARY, verification draft, theorem inventory, and proof artifacts. Write only the proof-redteam artifact, return once, and do not mutate shared state.",
  description="Proof redteam repair for phase ${phase_number}"
)
```

Do not raw-include the verification reference library at workflow load. Stage proof-redteam and verification references only when their gate is active.
</step>

<step name="verify_contract_targets">
Load `{GPD_INSTALL_DIR}/references/verification/verification-status-authority.md`
and apply its target-status vocabulary and fail-closed promotion rules.

For each contract-backed target, identify supporting artifacts, run structural
artifact checks, perform decisive scientific checks, and state the verdict in
terms of the promised outcome. Structural presence is never decisive by itself.

Use `gpd verify artifacts` and `gpd verify plan` only as initial structural
signals:

```bash
for plan in "$phase_dir"/PLAN.md "$phase_dir"/*-PLAN.md; do
  gpd verify artifacts "$plan"
  gpd verify plan "$plan"
done
```

Promote a target only after artifact Level 3 content validation and Level 4
contract/integration checks close:

- Level 1: artifact exists.
- Level 2: artifact is substantive and structurally complete.
- Level 3: content is validated by executed physics checks.
- Level 4: the artifact supports the contract target, required anchors, and
  downstream integration.

For proof-bearing claims, also verify that the proof and the passed
`*-PROOF-REDTEAM.md` artifact cover every named parameter, hypothesis,
quantifier/domain obligation, and conclusion clause. A proof that silently
collapses to a special case remains `PARTIAL` or `FAILED`.
</step>

<step name="run_decisive_scientific_checks">
Load `verification-quick-reference.md` to select checks and target-type evidence minimums, `verification-core.md` for universal physics checks, `verification-numerical.md` for numerical/simulation/statistical/benchmark-heavy targets, and `computational-verification-templates.md` only when an executable oracle template is needed.

Every decisive target needs evidence that breaks the LLM self-consistency loop:
executed code, CAS output, numeric output, algebraic simplification output, or a
proof-redteam adversarial probe. Include the code/output/verdict transcript in
the report body. If execution is unavailable, route to `expert_needed` or
`human_needed` and explain what prevented execution; do not mark the target
verified.

Record each check with inputs, expected result, actual output, verdict, contract
IDs, and any uncertainty or benchmark threshold.
</step>

<step name="verify_requirements_and_boundaries">
If `GPD/REQUIREMENTS.md` exists, match rows where the phase column references
the current phase and mark each requirement `SATISFIED`, `BLOCKED`, or
`NEEDS EXPERT` based on verified contract targets.

```bash
grep -E "\|.*Phase\s*${PHASE_NUM}(\s*[,|]|\s*$)" GPD/REQUIREMENTS.md 2>/dev/null
grep -E "^\|.*\b${PHASE_NUM}\b" GPD/REQUIREMENTS.md 2>/dev/null
```

Extract modified files from `SUMMARY.md` and `*-SUMMARY.md` only for boundary
checks such as placeholders, unexplained approximations, or claimed downstream
usage. These scans can find blockers but cannot prove success.

If this is not the first phase, do a lightweight cross-phase consistency check.
Keep the legacy summary discovery commands visible because they define the
standalone summary fallback:

```bash
PREV_PHASE_DIR=$(ls -d GPD/phases/*/ | sort | grep -B1 "$phase_dir" | head -1)
PREV_SUMMARY=$(ls "$PREV_PHASE_DIR"/SUMMARY.md "$PREV_PHASE_DIR"/*-SUMMARY.md 2>/dev/null | tail -1)
CURR_SUMMARY=$(ls "$phase_dir"/SUMMARY.md "$phase_dir"/*-SUMMARY.md 2>/dev/null | tail -1)
```

Read current summary dependencies, previous summary approximations/results, and
`GPD/STATE.md`. Notation drift, convention drift, approximation-regime mismatch,
or unit-system mismatch blocks `passed` when it affects a decisive target.
</step>

<step name="determine_status">
Apply `{GPD_INSTALL_DIR}/references/verification/verification-status-authority.md`.
Do not recompute, soften, or upgrade a scientific verdict after the evidence is
recorded.

Top-level routing:

- `passed`: every decisive target is `VERIFIED`, required references are
  complete, decisive comparisons are acceptable, forbidden proxies are rejected,
  proof-bearing work has passed proof-redteam artifacts, and no decisive
  `suggested_contract_checks` remain open.
- `gaps_found`: any decisive target is `FAILED` or `PARTIAL`.
- `expert_needed`: automated/computational checks pass, but domain expert
  judgment remains necessary.
- `human_needed`: automated/computational checks pass, but non-expert human
  input or a user decision remains.

If an aggregate independently confirmed tally helps the narrative, keep it in
body prose or tables. Keep any independent-confirmed tally in the report body or markdown return narrative only; do not add it to verification frontmatter or `gpd_return`.
</step>

<step name="create_report">
Set the report path:

```bash
REPORT_PATH="$phase_dir/${phase_number}-VERIFICATION.md"
```

Write body-only evidence first: goal narrative, contract evidence, artifact table, computation transcripts, proof gate evidence, requirements/boundaries, expert/human needs, gaps, and fix plans.

Use `verification_report_skeleton_bridge` only for conservative gap reports:
`gpd verification-report skeleton PLAN.md --write --output "$REPORT_PATH" --force --body-file BODY.md --validate contract`.

Use `verification_report_finalizer_bridge` for typed final outcomes:
`gpd verification-report finalize PLAN.md --patch PATCH.json --body-file BODY.md --output "$REPORT_PATH" --validate contract --force`.

The skeleton bridge is gap-only. The finalizer bridge handles `passed`, `gaps_found`, `expert_needed`, and `human_needed`. The helper owns frontmatter shape, `plan_contract_ref`, `contract_results`, `comparison_verdicts`, `suggested_contract_checks`, and validation. Do not hand-author or reflow full YAML/frontmatter.

If the verifier identifies a decisive check omitted by the contract, keep body evidence explicit and let the helper/validator-owned `suggested_contract_checks` ledger carry it. Do not mark the parent target `VERIFIED` until the check is resolved or explicitly re-scoped.
</step>

<step name="oracle_gate_check">
Before returning, verify that the canonical report exists, is named in `gpd_return.files_written`, passes the verification-contract validator, and contains an executed oracle transcript.

```bash
VERIFICATION_FILE="${phase_dir}/${phase_number}-VERIFICATION.md"
gpd validate verification-contract "${VERIFICATION_FILE}"
```

If the file is missing, absent from `gpd_return.files_written`, or fails validation, the verification is incomplete. The validator enforces the computational oracle evidence gate, so a report with no executed code/output/verdict block cannot pass. Run a decisive check or route to `expert_needed` / `human_needed` instead of claiming success.
</step>

<step name="return_to_orchestrator">
Route on `gpd_return.status`, not on headings. Accept `completed` only after `VERIFICATION.md` exists, is named in `gpd_return.files_written`, and passes `gpd validate verification-contract "${phase_dir}/${phase_number}-VERIFICATION.md"`. For proof-bearing phases, the sibling `*-PROOF-REDTEAM.md` must also exist and report `status: passed`.

`checkpoint` presents the checkpoint and starts a fresh continuation after user input. `blocked` or `failed` keeps the session fail-closed and surfaces validator errors and missing artifacts.

Return status (`passed` | `gaps_found` | `expert_needed` | `human_needed`),
score (N/M contract targets), and report path.

If `gaps_found`, list gaps with contract IDs, computation evidence, comparison verdict failures or forbidden-proxy violations, and recommended fix plan names. If `expert_needed` or `human_needed`, list open items and why computation was insufficient.

Orchestrator routes: `passed` -> update_roadmap; `gaps_found` -> create/execute
fixes then re-verify; `expert_needed` -> present to researcher/expert review;
`human_needed` -> present to researcher. When this workflow returns directly to
the user or a blocking status stops orchestration, include concrete
`next_actions`: `gpd:plan-phase {phase} --gaps`, `gpd:verify-work {phase}`,
`gpd:show-phase {phase}`, and `gpd:suggest-next`.
</step>

</process>

<success_criteria>

- [ ] Contract-backed targets established from PLAN frontmatter or a documented derived target set.
- [ ] Verification scoped to user-visible outcomes, not internal task milestones.
- [ ] Proof-bearing targets fail closed unless sibling proof-redteam artifacts pass.
- [ ] Structural artifact checks treated as non-decisive signals.
- [ ] Decisive scientific checks executed with visible code/output/verdict evidence.
- [ ] Numerical/statistical targets load `verification-numerical.md`; oracle templates load from `computational-verification-templates.md` only when needed.
- [ ] Required references, decisive comparisons, forbidden proxies, requirements, and cross-phase blockers assessed.
- [ ] Overall status determined through the verification-status authority.
- [ ] VERIFICATION.md created through the skeleton bridge for gap-only reports or the finalizer bridge for typed outcomes.
- [ ] `gpd validate verification-contract` and the child-return artifact gate pass before success is accepted.
- [ ] Results returned to the orchestrator with canonical status, score, report path, and next actions when blocked.

</success_criteria>

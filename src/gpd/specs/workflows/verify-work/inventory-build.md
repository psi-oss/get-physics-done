<purpose>
Delegate phase verification to one fresh `gpd-verifier` and gate the produced report.
</purpose>
<first_route>
First fail closed if project, roadmap, contract, proof, or anchor readiness is
unusable; only then delegate one fresh verifier and gate its report.
</first_route>
<philosophy>
Do not duplicate verifier policy. Fail closed before delegation if project, roadmap, contract, or proof readiness is unusable. The wrapper gates artifacts and routes; the verifier owns scientific status. Every child handoff is one-shot and file-producing success requires fresh expected artifacts.
</philosophy>
<shared_contract_floor>
**Project Contract Gate:** {project_contract_gate}
**Project Contract Load Info:** {project_contract_load_info}
**Project Contract Validation:** {project_contract_validation}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. A visible-but-blocked contract must be repaired before it is used as authoritative verification scope.
Treat `effective_reference_intake` as the structured source of carry-forward anchors; `active_references`, `citation_source_files`, and `citation_source_warnings` are compact routing handles, not rendered evidence bodies.
Do NOT skip contract-critical anchors.
</shared_contract_floor>

<process>

<step name="load_anchor_context">
Load inventory-building before using anchor, protocol-bundle, state, or verifier-handoff fields:

```bash
INVENTORY_BUILD_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage inventory_build)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd inventory-build initialization failed: $INVENTORY_BUILD_INIT"
  # STOP; surface the error.
fi
```

<field_access>
Apply `INVENTORY_BUILD_INIT.staged_loading.field_access_instruction` before
reading `INVENTORY_BUILD_INIT`. Use reference/citation handles without inlining
rendered prose or bodies.
</field_access>

- If it names a benchmark, prior artifact, or must-read reference, verification must explicitly check it or report why it could not.
- Stable knowledge docs that appear through handle/status fields are reviewed background synthesis: use them to clarify definitions, assumptions, and caveats only when they agree with stronger sources, and never as decisive evidence on their own.
- Background literature may be reduced by mode; anchor checks may not.
</step>

<step name="load_protocol_bundle_handles">
Use `protocol_bundle_load_manifest` as specialized-loading guidance. If bundles are selected, use `protocol_bundle_verifier_extensions` as the primary checklist surface; run `gpd --raw verify bundle-checklist <bundle-id> [<bundle-id> ...]` (passing `selected_protocol_bundle_ids`) only when extensions are missing or inconsistent. Bundle guidance may add checks, but it never replaces the plan contract or reduces anchor obligations.

For PLAN contracts with project-local anchors or prior-output paths, run `gpd --raw verify suggest-checks --contract <file|-> --project-dir DIR [--active-checks <id>,... ]`, fill the returned `request_template` completely, and run each applicable check with `gpd --raw verify contract-check --payload <file|-> [--project-dir DIR]`.
</step>

<step name="delegate_verification">
## Delegate Verification

Spawn `gpd-verifier` once with scoped write. It owns target extraction, evidence mapping, proof policy, checks, decisive comparisons, canonical status, suggested contract checks, and the gap ledger.

Pass the project contract, proof freshness summary, reference handles, and protocol bundle handoff fields into the handoff so the verifier can build its own authoritative ledger.
Point it at `{GPD_INSTALL_DIR}/references/verification/verification-status-authority.md`. Presentation headings are non-authority; route through the verifier tuple plus canonical report status.

> Verifier checkpoints use `references/orchestration/continuation-boundary.md`; the wrapper starts a fresh continuation after the user responds.

Use `verification_report_finalizer_bridge` as the canonical report finalizer bridge for passed, `human_needed`, `expert_needed`, and typed non-gap outcomes. Gap-only conservative reports may use `verification_report_skeleton_bridge`; stronger statuses must run `gpd verification-report finalize` with a typed patch JSON plus body-only evidence and pass `gpd validate verification-contract` before the wrapper routes on the report.

Set `VERIFIER_HANDOFF_STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` immediately before spawning.

Prompt: "First, read {GPD_AGENTS_DIR}/gpd-verifier.md for your role and instructions." Then verify Phase {phase_number}; use `Verification flags from the normalized parser: $VERIFY_FLAG_TEXT`; treat `--dimensional`, `--limits`, `--convergence`, and `--regression` as optional-breadth narrowing only.

Read with `file_read`: `${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md`, all PLAN/SUMMARY/`*-PROOF-REDTEAM.md` files in `${PHASE_DIR_ABS}/`, `${PROJECT_ROOT}/GPD/STATE.md`, and `${PROJECT_ROOT}/GPD/ROADMAP.md`.

Pass the staged contract/gate values, `contract_intake`, `effective_reference_intake`, compact reference handles, and `{phase_proof_review_status}`. Do not pass `active_reference_context`, `protocol_bundle_context`, or `reference_artifacts_content` from this stage.

<selected_protocol_bundle_ids>
{selected_protocol_bundle_ids}
</selected_protocol_bundle_ids>

<protocol_bundle_load_manifest>
{protocol_bundle_load_manifest}
</protocol_bundle_load_manifest>

<protocol_bundle_verifier_extensions>
{protocol_bundle_verifier_extensions}
</protocol_bundle_verifier_extensions>

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. Use `protocol_bundle_verifier_extensions` as primary bundle-extension surface. Keep decisive comparison gaps legible at the claim / acceptance-test / reference level. If user input is required, return checkpoint state and stop.
Schema finalization is bounded: validator pass returns; after the second validator failure total, including the initial failure and one repair rerun, return `gpd_return.status: blocked` with latest errors. Stop after two schema-only repair failures.

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - ${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md
expected_artifacts:
  - ${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md
shared_state_policy: return_only
</spawn_contract>

Run this `child_gate`; shared gate/continuation rules live in `references/orchestration/child-artifact-gate.md` and `references/orchestration/continuation-boundary.md`; scientific routing lives in `references/verification/verification-status-authority.md`.

```yaml
child_gate:
  id: "verify_work_verifier_report"
  role: "gpd-verifier"
  return_profile: "verifier"
  required_status: "completed"
  expected_artifacts:
    - "${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md"
  allowed_roots:
    - "${PHASE_DIR_ABS}"
  freshness_marker: "after $VERIFIER_HANDOFF_STARTED_AT"
  validators:
    - "gpd validate handoff-artifacts - --expected '${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md' --allowed-root '${PHASE_DIR_ABS}' --required-suffix=-VERIFICATION.md --require-status completed --require-files-written --fresh-after \"$VERIFIER_HANDOFF_STARTED_AT\""
    - "gpd validate verification-contract ${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md"
    - "verification-status-authority.md status rules"
    - "required proof-redteam artifacts report status: passed"
  applicator:
    command: "sync_verifier_output only after tuple passes"
    require_passed_true: false
  failure_route: "fail_closed -> gpd:verify-work ${phase_number} | repair_prompt_once | fresh_verifier_continuation_or_non_green_stop | non_green_stop_with_validator_errors"
  status_route:
    checkpoint: "fresh verifier continuation after user response"
    blocked: "non-green stop with validator errors"
    failed: "non-green stop with validator errors"
```

If runtime delegation is unavailable, fallback execution is still `gpd-verifier` work: read both report bridges, create bridge-valid body-only evidence, use the skeleton bridge only for conservative gap reports, and use `gpd verification-report finalize` for passed, `human_needed`, `expert_needed`, or typed non-gap outcomes. Do not hand-author frontmatter. Verification-report YAML must come from the skeleton/finalizer helpers; keep transcripts, hashes, oracle details, prose-only evidence, and `gpd_return` runtime return envelopes out of YAML, not in YAML. Then run `sync_verifier_output`; on validation failure, stop non-green and do not wrapper-repair the canonical report.
</step>

<step name="sync_verifier_output">
Read the verifier-produced verification file or report path.

Apply the `verify_work_verifier_report` child_gate before downstream routing.
Route only on canonical verification frontmatter plus `gpd_return.status`;
headings, marker strings, runtime success, and preexisting reports are not
authority. Every verifier-written canonical `VERIFICATION.md`, including gap or
non-green handoffs, must pass `gpd validate verification-contract` before this
wrapper accepts it. Missing, unreadable, unnamed, invalid, or failed-validation
reports stop through the tuple failure route; do not list them as authoritative,
route to gaps, enter `gap_repair`, patch frontmatter, or recompute canonical
status. Existing canonical frontmatter stays authoritative; append only the
session-local overlay here.

Load the staged researcher-session scaffold and canonical schema pack at this stage.

```bash
INTERACTIVE_VALIDATION_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage interactive_validation)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd interactive-validation initialization failed: $INTERACTIVE_VALIDATION_INIT"
  # STOP; surface the error.
fi
```

<field_access>
Apply `INTERACTIVE_VALIDATION_INIT.staged_loading.field_access_instruction`
before reading `INTERACTIVE_VALIDATION_INIT`. Session-overlay writes stay
report-schema bounded.
</field_access>

Keep the session overlay frontmatter compatible with the authoritative verification report.
Write to `${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md`.
Changed verification files fail `gpd pre-commit-check` when this header is missing or mismatched against the active lock.
</step>

</process>

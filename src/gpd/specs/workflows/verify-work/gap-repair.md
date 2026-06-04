<purpose>
Plan, check, and close verifier-diagnosed gaps without changing verifier-owned canonical status.
</purpose>
<philosophy>
Verifier owns scientific status. This stage turns diagnosed gaps into plans, checks, and records closeout after canonical validation.

An INCONCLUSIVE numeric-oracle verdict (`contract.numeric_oracle_agreement` -> `insufficient_evidence`, including `no_oracle_yet`) is **not** a gap: the physics may be correct, the oracle just could not certify it. Route it to `expert_needed` or suggested checks, never to gap-closure. Only a RED verdict (genuine numeric disagreement) is a `gaps_found` issue for the loop below.
</philosophy>
<shared_contract_floor>
**Project Contract Gate:** {project_contract_gate}
**Project Contract Load Info:** {project_contract_load_info}
**Project Contract Validation:** {project_contract_validation}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true; blocked contracts stop verification scope and keep the same contract-critical floor. `effective_reference_intake` carries anchors. This stage receives reference artifact handles, not embedded bodies; read or quote a listed artifact file only when a diagnosed gap cites that exact artifact or needs decisive comparison evidence.
Do not skip contract-critical anchors.
</shared_contract_floor>

<field_access>
Apply `GAP_REPAIR_INIT.staged_loading.field_access_instruction` before reading
`GAP_REPAIR_INIT`; the staged payload is the source of truth for
planner/checker routing.
</field_access>

<process>

<step name="plan_gap_closure">
**Auto-plan fixes from diagnosed gaps**

Display a compact "Planning fixes" status before spawning.

Spawn `gpd-planner` in `--gaps` mode as a fresh one-shot delegation from the staged gap-repair payload. First read {GPD_AGENTS_DIR}/gpd-planner.md. Use `templates/planner-subagent-prompt.md` for the gap_closure handoff, keeping `tool_requirements`, checker feedback, and hard requirements explicit.
Bind the template's protocol fields from the gap-repair payload: `{selected_protocol_bundle_ids}`, `{protocol_bundle_load_manifest}`, and `{protocol_bundle_verifier_extensions}`. Do not require rendered `protocol_bundle_context`; use the load manifest and verifier extensions as the targeted repair handles.
If a diagnosed gap is specifically an uncertainty or error-propagation gap, load the `error_propagation_gap` conditional authority pack before using error-propagation protocol requirements in the planner handoff.

Set `GAP_PLANNER_HANDOFF_STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` immediately before spawning.

Run this `child_gate`; shared gate and continuation rules live in `references/orchestration/child-artifact-gate.md` and `references/orchestration/continuation-boundary.md`.

```yaml
child_gate:
  id: "verify_work_gap_planner"
  role: "gpd-planner"
  return_profile: "planner"
  required_status: "completed"
  expected_artifacts:
    - path: "${PHASE_DIR_ABS}/*-PLAN.md"
      kind: "glob"
  allowed_roots:
    - "${PHASE_DIR_ABS}"
  freshness_marker: "after $GAP_PLANNER_HANDOFF_STARTED_AT"
  validators:
    - "gpd validate handoff-artifacts - --expected-glob '${PHASE_DIR_ABS}/*-PLAN.md' --allowed-root '${PHASE_DIR_ABS}' --required-suffix=-PLAN.md --require-files-written --require-status completed --fresh-after \"$GAP_PLANNER_HANDOFF_STARTED_AT\""
    - "gpd validate plan-contract <each fresh gap plan>"
    - "gpd validate plan-preflight <each fresh gap plan>"
  applicator: none
  failure_route: "fail_closed -> gpd:plan-phase ${phase_number} --gaps | repair_prompt_once | fresh_gap_planner_continuation"
  status_route:
    checkpoint: "fresh gap-planner continuation after user response"
    blocked: "gpd:plan-phase ${phase_number} --gaps"
    failed: "retry gap planner or gpd:plan-phase ${phase_number} --gaps"
```

If the planner fails or returns an error, stay fail-closed; do not use preexisting PLAN files as success. Primary route: `gpd:plan-phase ${phase_number} --gaps`.
</step>

<step name="verify_gap_plans">
**Verify fix plans with checker**

Display a compact "Verifying fix plans" status, then spawn `gpd-plan-checker` as a fresh one-shot delegation.

Set `GAP_CHECKER_HANDOFF_STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` immediately before spawning.

Run this `child_gate`; shared gate and continuation rules live in `references/orchestration/child-artifact-gate.md` and `references/orchestration/continuation-boundary.md`.

```yaml
child_gate:
  id: "verify_work_gap_plan_checker"
  role: "gpd-plan-checker"
  return_profile: "checker"
  required_status: "completed"
  expected_artifacts: []
  allowed_roots: []
  validators:
    - "fresh planner PLAN.md artifacts remain readable and named in planner files_written"
    - "approved_plans and blocked_plans reconcile to fresh gap plans"
    - "files_written: []"
  applicator: none
  failure_route: "manual_review_or_fail_closed | repair_prompt_once | fail_closed | revision_loop_or_fail_closed"
  status_route:
    checkpoint: "record approved/blocked plans for gap revision"
    blocked: "gpd:plan-phase ${phase_number} --gaps"
    failed: "retry or manual revision"
```

Gap-checker stops render through `references/orchestration/stage-stop-envelope.md`: checkpoint stops use primary `gpd:resume-work`; blocked or failed stops use primary `gpd:plan-phase ${phase_number} --gaps`; keep `gpd:suggest-next` secondary.

If the checker fails to spawn or returns an error, proceed without plan verification but note that the plans were not verified.

If the checker returns a structured `gpd_return`, route on `gpd_return.status` and the structured plan lists, not on presentation text:

- `completed`: accept only after fresh on-disk plans still match planner `files_written`.
- `checkpoint`: some plans are approved and others need revision; record `approved_plans` and `blocked_plans`, then send only the blocked plans back through the revision loop. If stopping for user input, use the gap-checker checkpoint stop route.
- `blocked`: nothing is approved; feed the checker issues and blocked plan IDs back into the revision loop without rewriting approved plans. If stopping, use the gap-checker blocked stop route.
- `failed`: present the issues and offer retry or manual revision. If stopping, use the gap-checker failed stop route.
</step>

<step name="revision_loop">
**Iterate planner <-> checker until plans pass, up to 3 rounds**

If the checker reports issues, send a fresh planner handoff with checker feedback, then rerun the checker. Each agent turn is one-shot. For `checkpoint` or `blocked`, route from structured `approved_plans`, `blocked_plans`, and `issues`; do not rewrite approved plans.
First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.
Use `templates/planner-subagent-prompt.md` again for checker-driven gap_closure revisions.
Again bind `{selected_protocol_bundle_ids}`, `{protocol_bundle_load_manifest}`, and `{protocol_bundle_verifier_extensions}` from the staged gap-repair payload so revision planners keep verifier-extension obligations visible without loading rendered bundle prose.

If iteration count reaches 3, stop and offer the user:

1. Force proceed
2. Provide guidance and retry
3. Abandon and exit

Render that stop through `references/orchestration/stage-stop-envelope.md`: primary `gpd:plan-phase ${phase_number} --gaps`, secondary `gpd:execute-phase ${phase_number} --gaps-only`, `gpd:verify-work ${phase_number}`, and `gpd:suggest-next`.
</step>

<step name="complete_session">
**Complete validation and commit**

Before updating `XX-VERIFICATION.md`, repairing schema, or serializing the gap ledger, load `gap_report_write_or_schema_repair`.

Update the verification file overlay:

- `verified`: now
- `updated`: now
- `session_status`: `completed`

Clear the current check display to indicate completion.

Run `gpd validate verification-contract "${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md"` before committing it; invalid reports stop non-green and do not advance state.
If the schema/report pack cannot be loaded or validation fails, stop before commit and before `record-verification`.

```bash
gpd commit "verify(${phase_number}): complete research validation - {passed} passed, {issues} issues" --files "${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md"
```

**Atomically advance shared state** so `gpd:progress` / `gpd:show-phase` reflect the verifier outcome without a manual `gpd:sync-state`:

```bash
gpd --raw state record-verification --phase "${phase_number}"
```

`record-verification` uses the canonical status reader (`passed` -> `Verified`; canonical non-passed -> `Blocked`; missing/unparseable/unknown fails closed). Do not pass `--status`; never parallelize state mutation with validation.

Present the summary of passed, issue, and skipped checks. Do not relax verifier fail-closed results.

End with `## > Next Up`:

- If verification passed: run read-only closeout readiness first with `gpd --raw phase closeout-readiness "${phase_number}" --require-verification`.
  - If readiness is blocked, render the readiness payload's runtime primary.
  - If readiness is ready, render the local transition below and leave next-phase routing to `gpd:suggest-next` after it completes.
- If gaps remain: primary `gpd:plan-phase ${phase_number} --gaps`; after gap plans exist, `gpd:execute-phase ${phase_number} --gaps-only`; confirm with `gpd:verify-work ${phase_number}`
- Always include `gpd:suggest-next` as the recovery/confirmation command
- Include `<sub>Start a fresh context window, then run the primary command above.</sub>`

Local preflight before rendering the ready local transition:
`gpd --raw phase closeout-readiness {PHASE_NUMBER} --require-verification`

## > Next Up

Primary local transition: `gpd phase complete {PHASE_NUMBER}`

**After this completes:** `gpd:suggest-next`

<sub>Start a fresh context window, then run the primary command above.</sub>
</step>

</process>

<update_rules>
Write only when needed:

1. issue found
2. session complete
3. every 5 passed checks as a safety net

Keep the current check display, summary, and session overlay in sync with the verifier output. The canonical verifier report content remains owned by `gpd-verifier`.
</update_rules>

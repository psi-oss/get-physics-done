<purpose>
Orchestrate conversational verification through a thin session wrapper around `gpd-verifier`.

The verifier agent owns contract-backed target construction, proof policy, computational checks, comparison verdicts, and canonical verification status. This workflow owns preflight, session routing, researcher interaction, report synchronization, diagnosis, and gap-repair routing.
</purpose>

<philosophy>
**Do not duplicate verifier policy here.**

- Fail closed before delegation if the project, roadmap, contract, or proof readiness are not usable.
- Present verifier-produced evidence one check at a time and record only the session overlay in this workflow.
- Every spawned agent is a one-shot delegation: if it needs user input, it must checkpoint and return, and the wrapper must start a fresh continuation after the user responds.
- File-producing handoffs must prove the expected artifact exists before success is accepted.
</philosophy>

<shared_contract_floor>
**Project Contract Gate:** {project_contract_gate}
**Project Contract Load Info:** {project_contract_load_info}
**Project Contract Validation:** {project_contract_validation}
**Contract Intake:** {contract_intake}
**Effective Reference Intake:** {effective_reference_intake}

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. A visible-but-blocked contract must be repaired before it is used as authoritative verification scope; keep the same contract-critical floor at all times.
Treat `effective_reference_intake` as the structured source of carry-forward anchors; `active_reference_context` is the readable projection, not the source of truth.
Do NOT skip contract-critical anchors.
</shared_contract_floor>

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

<process>

<step name="check_type_selection">
## Check Type Selection

Parse `$ARGUMENTS` for targeted verification flags:

- `--dimensional` - narrow the verifier's optional breadth to dimensional checks
- `--limits` - narrow the verifier's optional breadth to limiting cases
- `--convergence` - narrow the verifier's optional breadth to numerical convergence
- `--regression` - narrow the verifier's optional breadth to regression scans
- `--all` or no flags - delegate the full verifier package

Targeted flags narrow the optional check mix only. They do not change canonical verifier ownership or relax fail-closed routing.
</step>

<step name="initialize" priority="first">
Load the workflow context:

```bash
INIT=$(gpd --raw init verify-work "${PHASE_ARG}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP - display the error to the user and do not proceed.
fi
```

Parse the init JSON for the wrapper-facing fields only: `planner_model`, `checker_model`, `verifier_model`, `commit_docs`, `autonomy`, `research_mode`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `has_verification`, `has_validation`, `phase_proof_review_status`, `project_contract`, `project_contract_validation`, `project_contract_load_info`, `project_contract_gate`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `protocol_bundle_verifier_extensions`.

Treat `effective_reference_intake` as the structured source of carry-forward anchors; `active_reference_context` is the readable projection, not the source of truth.

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

If review preflight exits nonzero because the project state is missing or not yet ready for verification, the roadmap is missing, review integrity is degraded, or the selected phase lacks the required artifacts, stop and show the blocking issues before any delegation.

If `project_contract_load_info.status` starts with `blocked`, stop and show the surfaced `project_contract_load_info.errors` / `warnings` before delegation.

If `project_contract_validation.valid` is false, stop and show `project_contract_validation.errors` before delegation.

Use canonical artifact discovery helpers during bootstrap:

```bash
PHASE_INFO=$(gpd --raw roadmap get-phase "${phase_number}")
ls "$phase_dir"/*SUMMARY.md 2>/dev/null
ls "$phase_dir"/*-VERIFICATION.md 2>/dev/null | head -1
ls GPD/phases/*/*SUMMARY.md 2>/dev/null | sort
```

Read all PLAN.md files in ${phase_dir}/ using the file_read tool.
</step>

<step name="proof_readiness_gate">
Detect whether the phase is proof-bearing before any verifier handoff.

Use `phase_proof_review_status` as the structured freshness summary for the phase proof-review manifest if present. If a required proof-redteam audit is missing, stale, malformed, or not `passed`, spawn `gpd-check-proof` once before finalizing the gap ledger.
Proof-bearing phases require a canonical `*-PROOF-REDTEAM.md` artifact.
For proof-bearing work, an additional mandatory floor applies before the wrapper can accept a passed verification result.

```bash
CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)
```

> Runtime delegation rule: this is a single-turn handoff. If the spawned agent needs user input, it checkpoints and returns; do not keep the original run waiting inside the same task. If the proof critic cannot produce a passed audit, keep the verification session fail-closed.

```
task(
  subagent_type="gpd-check-proof",
  model="{check_proof_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-check-proof.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/templates/proof-redteam-schema.md and {GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md before writing any proof audit artifact.

Write to:
- `${phase_dir}/${phase_number}-PROOF-REDTEAM.md`

Read the phase proof artifacts, the relevant PLAN contract slice, and any current verification artifact before auditing.
Return `status: checkpoint` instead of waiting for user input inside this run.",
  description="Repair proof audit for phase {phase_number}"
)
```

After the proof critic returns, re-open `${phase_dir}/${phase_number}-PROOF-REDTEAM.md` from disk and confirm the artifact exists and is `passed` before finalizing the gap ledger. Never trust the return text alone; if the file is missing, stale, malformed, or not passed, keep the verification session fail-closed and start a fresh proof continuation.
If `gpd-check-proof` still cannot produce a passed audit, keep the verification status fail-closed.
</step>

<step name="load_anchor_context">
Use `active_reference_context` from init JSON as a mandatory input to verification.

- If it names a benchmark, prior artifact, or must-read reference, verification must explicitly check it or report why it could not.
- Treat `effective_reference_intake` as the structured source of must-read refs, prior outputs, baselines, user anchors, and context gaps. `active_reference_context` is the readable rendering of that ledger, not its substitute.
- Treat `reference_artifacts_content` as supporting evidence for what comparisons remain decisive. Stable knowledge docs that appear there are reviewed background synthesis: use them to clarify definitions, assumptions, and caveats only when they agree with stronger sources, and never as decisive evidence on their own.
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
for file in GPD/phases/*/*-VERIFICATION.md; do
  [ -f "$file" ] || continue
  session_status=$(gpd frontmatter get "$file" --field session_status 2>/dev/null)
  if [ "$session_status" = "validating" ] || [ "$session_status" = "diagnosed" ]; then
    printf '%s\n' "$file"
  fi
done | sort | head -5
```

**If active sessions exist and no `$ARGUMENTS` are provided:**

Only treat files whose frontmatter `session_status` is `validating` or `diagnosed` as active researcher sessions. Read each active file's frontmatter to extract canonical verification `status`, `session_status`, `phase`, and the Current Check section. Do not let `session_status` replace or overwrite the canonical verification `status`.

Display:

```
## Active Verification Sessions

| # | Phase | Session | Verification Status | Current Check | Progress |
|---|-------|---------|---------------------|---------------|----------|
| 1 | 04-dispersion | validating | gaps_found | 3. Limiting Cases | 2/6 |
| 2 | 05-numerics | diagnosed | expert_needed | 1. Convergence Test | 0/4 |

Reply with a number to resume, or provide a phase number to start new.
```

Wait for user response.

**If active sessions exist and `$ARGUMENTS` are provided:**

Check whether a session already exists for that phase. If yes, offer to resume or restart. If no, continue to verifier delegation.

**If no active sessions exist and no `$ARGUMENTS` are provided:**

```
No active verification sessions.

Provide a phase number to start validation (e.g., gpd:verify-work 4)
```

**If no active sessions exist and `$ARGUMENTS` are provided:**

Continue to verifier delegation.
</step>

<step name="delegate_verification">
## Delegate Verification

Spawn `gpd-verifier` once and let it own the physics policy.

The delegation prompt must tell the verifier to own:

- contract-backed target extraction
- evidence mapping from roadmap, contract, artifacts, anchors, and protocol bundles
- proof-bearing policy
- computational checks and decisive comparisons
- canonical verification report and status semantics
- suggested contract checks and gap ledger contents

Pass the project contract, proof freshness summary, active reference context, and protocol bundle context into the handoff so the verifier can build its own authoritative ledger.
Use `protocol_bundle_verifier_extensions` as the primary source for bundle checklist extensions; `protocol_bundle_context` is the readable projection. Use `suggest_contract_checks(contract)` whenever decisive anchor actions or prior-output paths remain ambiguous. Required decisive comparisons should stay legible enough that the researcher can recognize in the phase promise which `claim`, acceptance test, or reference is still unresolved. Do not mark the parent claim or acceptance test as passed until that decisive comparison is resolved.
Human-readable headings in the verifier output are presentation only; route on the canonical verification frontmatter and `gpd_return.status`, not on headings or marker strings.

> Runtime delegation rule: this is a one-shot handoff. If the spawned verifier needs user input, it must checkpoint and return. The wrapper must start a fresh continuation after the user responds instead of trying to keep the original verifier alive.

```
task(
  subagent_type="gpd-verifier",
  model="{verifier_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-verifier.md for your role and instructions.

Verify Phase {phase_number}. Keep verifier ownership of contract-backed target extraction, evidence mapping, proof-bearing policy, computational checks, decisive comparisons, and canonical verification status semantics.

Verification flags from the invoking wrapper: $ARGUMENTS
Treat `--dimensional`, `--limits`, `--convergence`, and `--regression` as optional-breadth narrowing only. Otherwise run the full verifier package.

<files_to_read>
Read these files using the file_read tool:
- Verification artifact if present: {phase_dir}/{phase_number}-VERIFICATION.md
- All PLAN.md files in {phase_dir}/
- All SUMMARY.md files in {phase_dir}/
- All `*-PROOF-REDTEAM.md` files in {phase_dir}/
- GPD/STATE.md
- GPD/ROADMAP.md
</files_to_read>

<verification_context>
Project contract: {project_contract}
Project contract gate: {project_contract_gate}
Project contract load info: {project_contract_load_info}
Project contract validation: {project_contract_validation}
Contract intake: {contract_intake}
Effective reference intake: {effective_reference_intake}
Active reference context: {active_reference_context}
Selected protocol bundle ids: {selected_protocol_bundle_ids}
Protocol bundle context: {protocol_bundle_context}
Protocol bundle verifier extensions: {protocol_bundle_verifier_extensions}
Proof freshness summary: {phase_proof_review_status}
</verification_context>

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. Use `protocol_bundle_verifier_extensions` as the primary bundle-extension surface. Keep decisive comparison gaps legible at the claim / acceptance-test / reference level. If user input is required, return `gpd_return.status: checkpoint` and stop; do not wait inside the same run.

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - {phase_dir}/{phase_number}-VERIFICATION.md
expected_artifacts:
  - {phase_dir}/{phase_number}-VERIFICATION.md
shared_state_policy: return_only
</spawn_contract>
",
  description="Verify Phase {phase_number}"
)
```

If runtime delegation is unavailable, execute the handoff in the main context, but do not re-implement verifier policy here.
</step>

<step name="sync_verifier_output">
Read the verifier-produced verification file or report path.

- Route only on the canonical verification frontmatter and `gpd_return.status`; do not route on headings or marker strings.
- `gpd_return.status: completed` means success only after verifying that:
  1. `${phase_dir}/${phase_number}-VERIFICATION.md` exists on disk and is readable
  2. the same path appears in `gpd_return.files_written`
  3. `gpd validate verification-contract "${phase_dir}/${phase_number}-VERIFICATION.md"` passes before any downstream routing
- If a canonical verification file already existed before this run, do not treat it as fresh verifier output unless the child reported that same path in `gpd_return.files_written`.
- `gpd_return.status: checkpoint` means present the verifier checkpoint, collect user input, spawn a fresh verifier continuation, and end the stop with `## > Next Up`: primary `gpd:resume-work`, plus `gpd:verify-work ${phase_number}` and `gpd:suggest-next`. Do not overwrite canonical verification status in this workflow.
- `gpd_return.status: blocked` or `failed` means keep the session fail-closed, present the issues, and end with `## > Next Up`: primary `gpd:verify-work ${phase_number}`, plus `gpd:resume-work` and `gpd:suggest-next`. Do not treat any preexisting verification file as a new verifier result on this path.
- If the verifier agent fails to spawn or returns an error, keep the session fail-closed. End with the same `gpd:verify-work ${phase_number}` Next Up route. Do not let a stale existing verification file satisfy the success path.
- If the canonical verification artifact is missing, unreadable, absent from `gpd_return.files_written`, or fails contract validation, treat the handoff as incomplete and request a fresh verifier continuation. Never trust the return text alone.
- If a canonical verification file already exists, preserve its authoritative frontmatter and append only the session-local overlay here.
- Do not recompute canonical verification status in this workflow.

Load the staged researcher-session scaffold and canonical schema pack at this stage.
Keep the session overlay frontmatter compatible with the authoritative verification report.
Write to `${phase_dir}/${phase_number}-VERIFICATION.md`.
Changed verification files fail `gpd pre-commit-check` when this header is missing or mismatched against the active lock.
</step>

<step name="present_check">
**Present current check to the researcher with verifier evidence:**

Read the verifier-supplied current check from the verification file or report state.

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

The wrapper should present verifier-produced evidence exactly once per check. It should not derive a new physics criterion here.

Keep body-only session-overlay fields aligned with the staged researcher-session scaffold. Use `forbidden_proxy_id` for explicit proxy-rejection checks instead of inventing extra body subject kinds.

Wait for researcher response (plain text).
</step>

<step name="process_response">
**Process researcher response and update the session overlay**

- Empty response, `yes`, `y`, `ok`, `pass`, `next`, `confirmed`, `correct` -> pass
- `skip`, `cannot check`, `n/a`, `not applicable` -> skipped
- Anything else -> issue

Infer severity from the response text:

- `wrong`, `error`, `diverges`, `unphysical`, `violates` -> blocker
- `disagrees`, `inconsistent`, `does not match`, `off by`, `missing` -> major
- `approximate`, `close but`, `small discrepancy`, `minor` -> minor
- `label`, `formatting`, `axis`, `legend`, `cosmetic` -> cosmetic
- default -> major

Update the session overlay only. The canonical verifier verdict remains verifier-owned.
</step>

<step name="resume_from_file">
**Resume validation from file:**

Read the active verification file. Find the first verifier-supplied check with `result: pending`.

Announce:

```
Resuming: Phase {phase_number} Research Validation
Progress: {passed + issues + skipped}/{total}
Issues found so far: {issues count}

Continuing from Check {N}...
```

Update the current check display and continue to `present_check`.
</step>

<step name="researcher_custom_checks">
**After the verifier-supplied checks are complete, invite researcher-supplied checks:**

```
All {N} verifier checks complete ({passed} passed, {issues} issues, {skipped} skipped).

Are there any additional physics checks you'd like to verify?
Examples: "check Ward identity", "verify sum rule", "test at strong coupling"
(Type "done" to skip)
```

If the researcher provides custom checks, spawn a fresh verifier continuation rather than extending the old run. Keep the one-shot delegation rule in force.

If the researcher says `done`, `no`, `skip`, or leaves it empty, proceed to issue routing.
</step>

<step name="diagnose_issues">
**Diagnose root causes before planning fixes**

**Severity gate:** only spawn parallel diagnosis agents for major+ issues. Minor and cosmetic issues are reported directly without investigation overhead.

**Major+ issues**

- Collect the major+ issues into an investigation list.
- Spawn parallel diagnosis agents once per issue.
- Pass the pre-check evidence and researcher response into each agent.
- Each spawned agent is a one-shot handoff and must checkpoint instead of waiting for user interaction.
- Collect root causes and update the verification overlay with the diagnosis result.

**Minor/cosmetic issues**

- Present them directly.
- Do not trigger investigation agents.
</step>

<step name="diagnosis_review">
## Diagnosis Review

Present the diagnosis results to the user and ask how to proceed:

- Auto-plan fixes
- Investigate manually
- Accept as-is
</step>

<step name="load_gap_repair_stage">
## Load Gap Repair Stage

When the user chooses auto-plan fixes, reload `verify-work` through the explicit gap-repair stage:

```bash
GAP_REPAIR_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage gap_repair)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd gap-repair initialization failed: $GAP_REPAIR_INIT"
  # STOP - display the error to the user and do not proceed.
fi
```

Parse the same wrapper-facing fields from the staged payload as in the main init, then treat the staged payload as the source of truth for planner and checker routing. Use the staged `planner_model`, `checker_model`, `phase_dir`, `phase_number`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `protocol_bundle_verifier_extensions`, and `phase_proof_review_status` values for the gap-repair route.

If the staged init is blocked, stale, or missing required fields, stop and surface the blocking issues instead of falling back to unstaged plan repair.
</step>

<step name="plan_gap_closure">
**Auto-plan fixes from diagnosed gaps**

Display:

```
====================================================
 GPD > PLANNING FIXES
====================================================

* Spawning planner for gap closure...
```

Spawn `gpd-planner` in `--gaps` mode as a fresh one-shot delegation from the staged gap-repair payload.
First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.
Use `templates/planner-subagent-prompt.md` to build the gap_closure planner handoff from the staged payload. Keep `tool_requirements`, the checker feedback, and other machine-checkable hard requirements explicit.

> Runtime delegation rule: the planner is single-shot. If it needs user input, it checkpoints and returns. Do not keep the same planner run open across user interaction.

Before treating the handoff as complete, verify that the expected `PLAN.md` files exist in the phase directory and are listed in `gpd_return.files_written` from the fresh planner run.
After the planner returns, route on `gpd_return.status`, not on headings. If `gpd_return.status` is `completed`, verify that each expected path is present on disk, readable, and present in `gpd_return.files_written` before treating the handoff as complete.
If `gpd_return.status` is `checkpoint`, present the checkpoint, collect user input, spawn a fresh planner continuation from the staged gap-repair payload instead of waiting inside the same run, and end with `## > Next Up`: primary `gpd:resume-work`, plus `gpd:plan-phase ${phase_number} --gaps` and `gpd:suggest-next`.
If the planner reports `blocked` or `failed`, or if the expected `PLAN.md` files are missing, unreadable, stale, or absent from `gpd_return.files_written`, keep the session fail-closed and end with `## > Next Up`: primary `gpd:plan-phase ${phase_number} --gaps`, plus `gpd:resume-work` and `gpd:suggest-next`.

If the planner fails to spawn or returns an error, keep the session fail-closed and offer retry or manual plan creation. Do not fall through to gap verification on the basis of preexisting `PLAN.md` files alone. End with the same `gpd:plan-phase ${phase_number} --gaps` Next Up route.
</step>

<step name="verify_gap_plans">
**Verify fix plans with checker**

Display:

```
====================================================
 GPD > VERIFYING FIX PLANS
====================================================

* Spawning plan checker...
```

Spawn `gpd-plan-checker` as a fresh one-shot delegation.

> Runtime delegation rule: this checker is single-shot. If it needs user input, it checkpoints and returns. Do not keep the same checker run open across user interaction.

Before accepting the handoff as complete, confirm the expected `PLAN.md` files are present, readable, and listed in `gpd_return.files_written` from the planner turn.

If the checker fails to spawn or returns an error, proceed without plan verification but note that the plans were not verified.

If the checker returns a structured `gpd_return`, route on `gpd_return.status` and the structured plan lists, not on presentation text:

- `completed`: treat the fresh fix plans as verified only after the on-disk files still match the planner's `files_written` set.
- `checkpoint`: some plans are approved and others need revision; record `approved_plans` and `blocked_plans`, then send only the blocked plans back through the revision loop. If stopping for user input, end with `## > Next Up`: primary `gpd:resume-work`, plus `gpd:plan-phase ${phase_number} --gaps` and `gpd:suggest-next`.
- `blocked`: nothing is approved; feed the checker issues and blocked plan IDs back into the revision loop without rewriting approved plans. If stopping, use the same Next Up route.
- `failed`: present the issues and offer retry or manual revision. End with `## > Next Up`: primary `gpd:plan-phase ${phase_number} --gaps`, plus `gpd:resume-work` and `gpd:suggest-next`.
</step>

<step name="revision_loop">
**Iterate planner <-> checker until plans pass, up to 3 rounds**

If the checker reports issues, send a fresh planner continuation from the staged gap-repair payload with the checker feedback. After the planner returns, run the checker again. Each agent turn is one-shot; do not keep either agent alive across user interaction.
When the checker returns `checkpoint` or `blocked`, use the structured `approved_plans`, `blocked_plans`, and `issues` fields to decide which plans to revise. Use the structured fields, not the human-readable approval table, as the source of truth. Do not rewrite approved plans during the revision round.
First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.
Use `templates/planner-subagent-prompt.md` again for checker-driven gap_closure revisions.

If iteration count reaches 3, stop and offer the user:

1. Force proceed
2. Provide guidance and retry
3. Abandon and exit

End that stop with `## > Next Up`: primary `gpd:plan-phase ${phase_number} --gaps`, plus `gpd:execute-phase ${phase_number} --gaps-only`, `gpd:verify-work ${phase_number}`, and `gpd:suggest-next`.
</step>

<step name="complete_session">
**Complete validation and commit**

Update the verification file overlay:

- `verified`: now
- `updated`: now
- `session_status`: `completed`

Clear the current check display to indicate completion.

Validate the final verification file, then commit it.

```bash
gpd commit "verify(${phase_number}): complete research validation - {passed} passed, {issues} issues" --files "${phase_dir}/${phase_number}-VERIFICATION.md"
```

**Atomically advance shared state** so `gpd:progress` / `gpd:show-phase` reflect the verifier outcome without a manual `gpd:sync-state`:

```bash
gpd --raw state record-verification --phase "${phase_number}"
```

The command reads the canonical verification frontmatter `status:` field and
transitions STATE.md / state.json to `Verified` on pass or `Blocked` on fail.
Pass `--status passed|failed` explicitly only when bypassing the frontmatter.

Present the summary of passed, issue, and skipped checks. Do not relax verifier fail-closed results.

End with `## > Next Up`:

- If verification passed and more phases remain: primary `gpd:discuss-phase ${next_phase}` when context is missing, otherwise `gpd:plan-phase ${next_phase}`
- If verification passed and the milestone is complete: primary `gpd:complete-milestone`
- If gaps remain: primary `gpd:plan-phase ${phase_number} --gaps`; after gap plans exist, `gpd:execute-phase ${phase_number} --gaps-only`; confirm with `gpd:verify-work ${phase_number}`
- Always include `gpd:suggest-next` as the recovery/confirmation command
- Include `<sub>Start a fresh context window, then run the primary command above.</sub>`
</step>

</process>

<update_rules>
Write only when needed:

1. issue found
2. session complete
3. every 5 passed checks as a safety net

Keep the current check display, summary, and session overlay in sync with the verifier output. The canonical verifier report content remains owned by `gpd-verifier`.
</update_rules>

<success_criteria>

- [ ] `verify-work` stays thin and does not duplicate verifier policy
- [ ] Preflight, review gating, session routing, diagnosis, and gap repair remain in the workflow
- [ ] `gpd-verifier` owns canonical target extraction, evidence mapping, proof policy, checks, and status
- [ ] Spawned agents use one-shot delegation with checkpoint-and-restart semantics after user input
- [ ] File-producing handoffs verify expected artifacts on disk before success is accepted
- [ ] The verification overlay is written only after authoritative verifier output is available
- [ ] Researcher responses are processed as pass / issue / skip
- [ ] Final session closeout validates and commits the verification file without recomputing verifier policy

</success_criteria>

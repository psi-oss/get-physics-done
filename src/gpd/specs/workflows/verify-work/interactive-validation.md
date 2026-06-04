<purpose>
Present verifier evidence, collect researcher responses, and route diagnosed issues.
</purpose>
<philosophy>
Present verifier-produced evidence one check at a time, write only the session overlay, and checkpoint user input.
</philosophy>
<stage_scope>
Stage id: `interactive_validation`. Owns check presentation, response capture, diagnosis, and the explicit transition into gap repair.
</stage_scope>

Apply `INTERACTIVE_VALIDATION_INIT.staged_loading.field_access_instruction`
before reading `INTERACTIVE_VALIDATION_INIT`.

<process>

<step name="present_check">
Read the verifier-supplied current check from the verification file or report state.

Display compactly:

```
### Research Validation Check {number}: {name}

{expected}

**Independent computation:** {computation description and result}

**Oracle verdict:** {oracle_status: PASS | INCONCLUSIVE | (none)} — {sample_points_compared} points, fidelity {matched|mismatch}

Confirm this matches your result, or describe what differs.
```

The **Oracle verdict** line is shown only when the verifier recorded a blind oracle check (`contract.numeric_oracle_agreement`) for this check; omit it otherwise. Surface the verifier's recorded verdict verbatim — do not recompute it here.

Present verifier-produced evidence exactly once per check. Do not derive a new physics criterion here.

Keep body-only session-overlay fields aligned with the staged researcher-session scaffold. Use `forbidden_proxy_id` for explicit proxy-rejection checks instead of inventing extra body subject kinds.

Wait for researcher response (plain text).
</step>

<step name="process_response">
- Empty response, `yes`, `y`, `ok`, `pass`, `next`, `confirmed`, `correct` -> pass
- `skip`, `cannot check`, `n/a`, `not applicable` -> skipped
- Anything else -> issue

Infer severity from the response text:

- `wrong`, `error`, `diverges`, `unphysical`, `violates` -> blocker
- `disagrees`, `inconsistent`, `does not match`, `off by`, `missing` -> major
- `approximate`, `close but`, `small discrepancy`, `minor` -> minor
- `label`, `formatting`, `axis`, `legend`, `cosmetic` -> cosmetic
- default -> major

Before creating, editing, or repairing the session overlay, load `session_overlay_write_or_repair`.

Update the session overlay only. The canonical verifier verdict remains verifier-owned.
After any overlay write, validate the verification report/contract through the existing helper path before presenting the next check or routing to gap repair. If the schema/report pack cannot be loaded, stop instead of writing from memory.
</step>

<step name="resume_from_file">
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
```
All {N} verifier checks complete ({passed} passed, {issues} issues, {skipped} skipped).

Are there any additional physics checks you'd like to verify?
Examples: "check Ward identity", "verify sum rule", "test at strong coupling"
(Type "done" to skip)
```

If the researcher provides custom checks, spawn a fresh verifier continuation. Before that handoff, load `custom_verifier_continuation`.

If the researcher says `done`, `no`, `skip`, or leaves it empty, proceed to issue routing.
</step>

<step name="diagnose_issues">
**Diagnose root causes before planning fixes**

Only spawn diagnosis agents for major+ issues; report minor/cosmetic issues directly.

- Collect the major+ issues into an investigation list.
- Spawn parallel diagnosis agents once per issue.
- Pass the pre-check evidence and researcher response into each agent.
- Each spawned agent is a one-shot handoff and must checkpoint instead of waiting for user interaction.
- Collect root causes and update the verification overlay with the diagnosis result.

</step>

<step name="diagnosis_review">
## Diagnosis Review

Present diagnosis results and ask how to proceed:

- Auto-plan fixes
- Investigate manually
- Acknowledge limitation; verification status remains non-passed

Acknowledgement is routing only, not verification evidence. It cannot upgrade non-passed verifier/frontmatter/proof/check status to `passed`; preserve verifier-owned status and route to gap planning or follow-up.
</step>

<step name="load_gap_repair_stage">
## Load Gap Repair Stage

When the user chooses auto-plan fixes, reload `verify-work` through the explicit gap-repair stage:

```bash
GAP_REPAIR_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage gap_repair)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd gap-repair initialization failed: $GAP_REPAIR_INIT"
  # STOP; surface the error.
fi
```

Apply `GAP_REPAIR_INIT.staged_loading.field_access_instruction` before planning repairs.

If the staged init is blocked, stale, or missing required fields, stop and surface the blocking issues instead of falling back to unstaged plan repair.
</step>

</process>

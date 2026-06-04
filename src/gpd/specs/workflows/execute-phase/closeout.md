<purpose>
Close the phase only after execution, verification, gap re-verification if needed, consistency checking, and read-only closeout readiness have all passed.
</purpose>

<stage_boundary>
This stage owns readiness-gated completion, helper checkpoint cleanup, and renderer-ready next-command selection. Code owns the `NextCommand` taxonomy and public next-up shape. This stage does not spawn verifiers, close gaps, run consistency checks, or decide scientific status.
</stage_boundary>

<process>

<step name="closeout_readiness_gate">
Refresh only this stage before reading closeout fields:

```bash
CLOSEOUT_INIT=$(gpd --raw init execute-phase "${PHASE_ARG}" --stage closeout)
if [ $? -ne 0 ] || [ -z "$CLOSEOUT_INIT" ]; then
  echo "ERROR: closeout init failed: $CLOSEOUT_INIT"
  exit 1
fi
```

Apply `CLOSEOUT_INIT.staged_loading.field_access_instruction` before reading `CLOSEOUT_INIT`.

Before any roadmap/state transition, run the read-only helper below and route from its JSON. It is the authority for verification, proof-redteam, consistency, bounded-segment, and closeout readiness.

```bash
CLOSEOUT_READINESS=$(gpd --raw phase closeout-readiness "${phase_number}" --require-verification)
READINESS_STATUS=$?
if [ -z "$CLOSEOUT_READINESS" ]; then
  echo "ERROR: closeout-readiness produced no JSON (exit ${READINESS_STATUS})"
  exit 1
fi
```

The readiness helper is read-only. A nonzero exit can mean "blocked but rendered as JSON"; route from the JSON before deciding whether to stop. On any blocker, stop and surface its next action. Do not repair blockers, update roadmap/state, or clean checkpoints from this stage.

`ready-to-execute` and `ready-for-verification` are not `ready-for-closeout`; the helper JSON is the transition authority. Branch before showing any mutation:

```bash
CLOSEOUT_READY=$(echo "$CLOSEOUT_READINESS" | gpd json get .ready --default false)
if [ "$CLOSEOUT_READY" != "true" ]; then
  echo "$CLOSEOUT_READINESS" | gpd json get .next_up.rendered_markdown --default "$CLOSEOUT_READINESS"
  exit 0
fi
```

Readiness next-action ownership:

- Blocked closeout keeps a public runtime primary, such as `gpd:verify-work ${phase_number}`, `gpd:resume-work`, or `gpd:execute-phase ${phase_number}`.
- Ready closeout labels `gpd phase complete "${phase_number}"` as `Primary local transition`, not a runtime workflow.
- Read-only readiness and checkpoint cleanup are local helper context, not `stage_stop` runtime commands.
- If `next_up.rendered_markdown` or matching `next_up.stage_stop_*` fields are absent, surface the helper JSON instead of hand-rendering.
</step>

<step name="ready_success_complete_phase">
Only after `CLOSEOUT_READINESS.ready == true`, show and run the safe local transition:

```bash
gpd phase complete "${phase_number}"
```

The completion helper owns the roadmap/state transition and rechecks lifecycle readiness before mutating. Treat it as a local transition command, not a public runtime workflow. Load broader transition policy references only after readiness is green and only if the helper reports a transition ambiguity that needs policy interpretation.
Do not read `workflows/transition.md`, `templates/state-machine.md`, or `references/orchestration/state-portability.md` during normal closeout. If readiness is green and `gpd phase complete` reports an ambiguous transition/state-machine result, load the `transition_helper_ambiguity` conditional authority pack before interpreting or repairing that result.
</step>

<step name="ready_success_cleanup_phase_checkpoints">
After successful phase completion, remove only helper-owned checkpoint tags:

```bash
gpd --raw phase checkpoint cleanup --phase "${phase_number}" --namespace phase --policy successful-closeout
```

If cleanup exits nonzero, print the helper JSON and stop. Preserve tags for blockers, recovery artifacts, failed/skipped/rolled-back plans, verification gaps, or preservation policy. Cleanup is secondary local helper work after the transition; do not render it as the primary next action.
</step>

<step name="offer_next">
Never end with only "ready to plan/continue" prose. After successful closeout,
refresh the lifecycle route and emit the code-owned next-up projection. Do not
print raw staged-init, field-access, readiness, or cleanup commands as public
next actions.

```bash
POST_CLOSEOUT_ROUTE=$(gpd --raw phase closeout-readiness "${phase_number}" --require-verification || true)
```

The post-closeout helper may exit nonzero because the phase is already closed;
that is acceptable only when it prints a parseable route payload. Prefer
`lifecycle_next_up.rendered_markdown`, then `next_up.rendered_markdown`; pair it
with the matching `lifecycle_next_up.stage_stop_*` or `next_up.stage_stop_*`
projection. Emit the rendered `## > Next Up` block exactly as supplied by the
payload's shared renderer shape (`Primary:`, `Primary local transition:`,
`**After this completes:**`, and `Secondary ...` lines).

The prompt must not decide whether the next runtime command is
`gpd:discuss-phase`, `gpd:plan-phase`, milestone audit, milestone archive, or
new milestone. Those route variants belong to the lifecycle route payload. Load
`next_up_rendering_recovery` only if a parseable payload contains route fields
but no rendered projection. If the route payload, rendered markdown, or matching
stage-stop projection is absent, surface the helper JSON instead of
hand-rendering a route.
</step>

<step name="mayfly_notebook_maintenance">
After the phase is closed, update the Mayfly research notebook so the next
session starts informed (project_dir=$CWD). Skip silently if the gpd-mayfly
tools are unavailable.

1. `gpd_mayfly:read_session_log` — check for unprocessed sessions.
2. For each significant finding: `gpd_mayfly:upsert_knowledge(topic, content)`.
   Read the existing entry first; preserve prior bullets; add `→ session NNN` links.
3. `gpd_mayfly:update_frontier` — overwrite FRONTIER.md with updated current best,
   directions, hypotheses, dead ends. Every direction links to a knowledge entry.
4. `gpd_mayfly:append_journal_row` — outcome + summary + knowledge_updated slugs.
5. `gpd_mayfly:write_session_notes` — raw notes (approach, result, what worked/failed).
6. If new topics or status changes: `gpd_mayfly:update_map`.
</step>

</process>

<purpose>
Thin wrapper around `gpd-consistency-checker` for convention validation.

This workflow resolves the requested scope, delegates the physics policy to the checker, and accepts success only when the typed `gpd_return.status` and the expected consistency report artifact both check out. The checker owns the convention logic; this workflow only gates scope, artifact presence, and post-return routing.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

<process>

<step name="initialize" priority="first">
Load project context and scope:

```bash
PHASE_ARG="${ARGUMENTS:-}"
if [ -n "${PHASE_ARG}" ]; then
  INIT=$(gpd --raw init phase-op --include state,roadmap,config "${PHASE_ARG}")
else
  INIT=$(gpd --raw init progress --include state,roadmap,config)
fi
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `state_exists`, `roadmap_exists`, `phases`, `current_phase`, `derived_convention_lock`, and when phase-scoped `phase_found`, `phase_dir`, `phase_number`.

Read mode settings:

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context validate-conventions "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

If `state_exists` is false:

```
No project state found. Run gpd:new-project first.
```

Exit.

Resolve scope immediately after preflight:

- If `$PHASE_ARG` is set, require `phase_found: true` from `init phase-op` and derive a single-phase scope from `phase_dir`.
- If `$PHASE_ARG` is empty, scan all completed phases from `gpd --raw roadmap analyze`.
- If the requested phase cannot be resolved, fail closed with `ERROR: Phase not found: ${PHASE_ARG}`.

Capture the selected phase directory and roadmap view for the downstream scan:

```bash
ROADMAP=$(gpd --raw roadmap analyze)
```

Load the convention ledger:

```bash
CONVENTIONS=$(gpd convention list)
```

Read `GPD/CONVENTIONS.md` when present so the checker can compare the human-readable convention record against the structured lock. If the file is missing, continue with the structured lock and report the missing artifact as a limitation rather than inventing a fallback policy.
</step>

<step name="delegate_checker">
Spawn `gpd-consistency-checker` once and let it own convention policy.

Use the requested scope to choose checker mode:

- `PHASE_ARG` present -> `rapid`
- no phase argument -> `full`

For the checker prompt, provide only the scope, expected artifact path, and the required project files. Do not restate the checker's severity taxonomy or convention policy here.

Derive the routed scope explicitly:

```bash
if [ -n "${PHASE_ARG}" ]; then
  CHECKER_MODE="rapid"
  CHECK_SCOPE="phase ${PHASE_ARG}"
  EXPECTED_ARTIFACT="GPD/phases/${PHASE_DIR}/CONSISTENCY-CHECK.md"
else
  CHECKER_MODE="full"
  CHECK_SCOPE="all completed phases"
  EXPECTED_ARTIFACT="GPD/CONSISTENCY-CHECK.md"
fi
```

Expected artifact:

- phase-scoped run: `GPD/phases/${PHASE_DIR}/CONSISTENCY-CHECK.md`
- project-wide run: `GPD/CONSISTENCY-CHECK.md`

If `PHASE_ARG` is set, capture `PHASE_DIR` from the scoped init payload:

```bash
PHASE_DIR=$(echo "$INIT" | gpd json get .phase_dir --default "")
```

Use the selected scope to gather summary artifacts:

```bash
if [ -n "${PHASE_ARG}" ]; then
  for SUMMARY in "${PHASE_DIR}"/*SUMMARY.md; do
    gpd --raw summary-extract "$SUMMARY" --field conventions --field affects
  done
else
  for SUMMARY in GPD/phases/*/*SUMMARY.md; do
    gpd --raw summary-extract "$SUMMARY" --field conventions --field affects
  done
fi
```

Runtime delegation rule: this is a one-shot handoff. If the checker needs user input, it checkpoints and returns; the wrapper must start a fresh continuation after the user responds.

```bash
CHECKER_MODEL=$(gpd resolve-model gpd-consistency-checker)
```

```
task(
  subagent_type="gpd-consistency-checker",
  model="{CHECKER_MODEL}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-consistency-checker.md for your role and instructions.

<mode>{CHECKER_MODE}</mode>
<scope>{CHECK_SCOPE}</scope>
<expected_artifacts>
- {EXPECTED_ARTIFACT}
</expected_artifacts>

Validate convention consistency for the requested scope.
Read the structured init payload, the current convention lock, GPD/STATE.md, GPD/state.json, GPD/CONVENTIONS.md, and the relevant SUMMARY artifacts.
Write the report to the expected artifact path and return the canonical gpd_return envelope.",
  description="Validate conventions for {CHECK_SCOPE}"
)
```

If the checker returns `gpd_return.status: completed`, accept success only after verifying that:

1. The expected artifact exists on disk.
2. The same path appears in `gpd_return.files_written`.

If either check fails, treat the handoff as incomplete and do not accept success.
</step>

<step name="route_return">
Route only on the canonical `gpd_return.status`:

- `gpd_return.status: completed` means the checker finished for the selected scope. Surface any advisory items from `gpd_return.issues`, but do not reinterpret the status text.
- `gpd_return.status: checkpoint` means the checker needs user input. Present options, checkpoint, and return. End with `## > Next Up`: primary `gpd:resume-work`, plus `gpd:validate-conventions` and `gpd:suggest-next`.
- `gpd_return.status: blocked` or `gpd_return.status: failed` means the checker could not complete. Surface `gpd_return.issues`, keep the run fail-closed, and end with `## > Next Up`: primary `gpd:validate-conventions`, plus `gpd:resume-work`, `gpd convention set <key> <value>` when a lock repair is known, and `gpd:suggest-next`.

Do not route on checker-local text markers or headings. Those are presentation only; route only on the canonical `gpd_return.status`.

If the checker's `next_actions` call for notation repair, spawn `gpd-notation-coordinator` with the checker report and the same scope. Keep that handoff thin: the coordinator owns the repair policy, not this workflow.

Verify that `GPD/CONVENTIONS.md` exists and that `gpd convention list` reflects the resolved fields before accepting the update. Convention artifact and lock re-verified after notation resolution before success is accepted.
</step>

<step name="report">
Present a concise convention report:

- scope scanned
- expected artifact path
- canonical `gpd_return.status`
- any advisory issues or blocker issues
- whether the artifact gate passed

Before accepting any repaired result from the notation coordinator, re-check that `GPD/CONVENTIONS.md` exists and that `gpd convention list` reflects the resolved fields.

If the checker completed and the artifact gate passed, return the updated report to the user.
</step>

</process>

<success_criteria>

- [ ] Project context loaded and command-context validation run
- [ ] Optional phase scope is resolved or fails closed
- [ ] Convention ledger loaded from `gpd convention list`
- [ ] Checker prompt stays thin and delegates policy to `gpd-consistency-checker`
- [ ] Expected `CONSISTENCY-CHECK.md` artifact is verified before success is accepted
- [ ] Routing uses canonical `gpd_return.status`
- [ ] Legacy checker-text routing is not used
- [ ] Notation repair remains delegated to `gpd-notation-coordinator` when requested by the checker
- [ ] Report presented with the selected scope and artifact gate result

</success_criteria>

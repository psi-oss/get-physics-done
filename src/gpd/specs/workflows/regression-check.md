<purpose>
Run the lightweight regression audit implemented by `gpd regression-check`.

This workflow does **not** re-run physics, numerical, dimensional, or contract verification. It scans already-recorded phase artifacts for frontmatter-level regressions:

- conflicting `conventions` definitions across completed `*-SUMMARY.md` artifacts
- missing, invalid, or non-canonical `*-VERIFICATION.md` statuses
- completed phases whose `*-VERIFICATION.md` still reports unresolved gaps

Use `/gpd:verify-work <phase>` when a flagged phase needs actual re-verification.
</purpose>

<process>

<step name="initialize" priority="first">
Run centralized context preflight before scanning:

```bash
CONTEXT=$(gpd --raw validate command-context regression-check "${PHASE_ARG:-}")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Determine scope:

- **Single phase:** Scan only that completed phase
- **All phases:** Scan all completed phases
- **Quick mode:** If invoked through the local CLI with `--quick`, keep only the two most recent completed phases after scope filtering
</step>

<step name="discover_completed_phases">
Identify completed phase directories under `GPD/phases`.

A phase counts as completed when it contains at least one plan artifact (`PLAN.md` or `*-PLAN.md`) and at least one summary artifact (`*-SUMMARY.md`).

```bash
find GPD/phases -type f -name "*-SUMMARY.md" 2>/dev/null | sort
```

Filter the discovered directories by the optional phase argument. If quick mode is active, keep only the two most recent completed phases after filtering.

If no completed phases remain after filtering, return a passing result with `phases_checked: 0`.
</step>

<step name="scan_summary_frontmatter">
Scan the selected summary artifacts for convention conflicts.

Each selected completed phase should expose a `*-SUMMARY.md` file. Read the frontmatter and inspect the `conventions` field.

Accepted frontmatter shapes:

- list of `symbol=value` or `symbol: value` strings
- mapping of `symbol: value`

Normalize each entry into `(symbol, value)` and accumulate definitions across phases.

If the same symbol appears with more than one distinct value across the selected completed phases, emit a `convention_conflict` issue with:

- `symbol`
- `definitions[]` containing `phase`, `file`, and `value`

This is a frontmatter consistency audit only. Do not re-run derivations, dimensional checks, limiting cases, or numerical verification here.
</step>

<step name="scan_verification_frontmatter">
Scan the selected verification artifacts for status regressions.

```bash
find GPD/phases -type f -name "*-VERIFICATION.md" 2>/dev/null | sort
```

For each selected completed phase:

1. If a verification file cannot be parsed as frontmatter, emit `unparseable_verification`.
2. If `status` is missing or blank, emit `invalid_verification_status`.
3. If `status` is not one of the canonical values `passed`, `gaps_found`, `expert_needed`, or `human_needed`, emit `invalid_verification_status`.
4. If `status` is `gaps_found`, `expert_needed`, or `human_needed`, emit `unresolved_verification_issues`.

When `score` is available in `X/Y` form, derive `gap_count = Y - X`. Otherwise keep the issue and fall back to a conservative gap count.

Do not inspect the body for VERIFIED targets and do not claim physics was re-verified.
</step>

<step name="emit_result">
Return the same structured shape as the implemented command:

```json
{
  "passed": true,
  "issues": [],
  "phases_checked": 3
}
```

Issue types emitted by this workflow are limited to:

- `convention_conflict`
- `unparseable_verification`
- `invalid_verification_status`
- `unresolved_verification_issues`

If issues are present, recommend the narrow next action:

1. Fix the frontmatter or convention drift directly if the issue is clerical
2. Run `/gpd:verify-work <phase>` if an affected phase now needs real re-verification
3. Re-run `/gpd:regression-check [phase]` to confirm the artifact-level audit is clean
</step>

</process>

<success_criteria>

- [ ] Completed phases discovered correctly
- [ ] Optional phase scope respected
- [ ] Quick mode respected when requested
- [ ] Summary frontmatter scanned for convention conflicts
- [ ] Verification frontmatter scanned for parse/status issues
- [ ] Structured result returned with `passed`, `issues`, and `phases_checked`
- [ ] No workflow step claims that physics or numerical checks were re-run

</success_criteria>

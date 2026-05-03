<purpose>
Create the canonical `.continue-here.md` continuation handoff artifact for `gpd:resume-work`, `gpd resume`, and `gpd resume --recent`. It is a handoff surface, not the durable authority.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="detect">
Find current phase directory from most recently modified files:

```bash
# Find most recent phase directory with work
ls -lt GPD/phases/*/*PLAN.md 2>/dev/null | head -1 | sed 's|.*phases/||' | sed 's|/.*||'
```

If no active phase detected, ask user which phase they're pausing work on.
</step>

<step name="gather">
**Collect complete research state for the continuation handoff artifact:**

- Current phase, plan, task, and what remains.
- Derivation state: established equations, parameter values, intermediate results, active approximations, and what still must be shown.
- Session delta: completed work, modified files, decisions made, open questions, blockers, and the next theoretical approach.
- Result continuity: if a canonical derived result was just persisted, capture its `result_id` as the active `last_result_id` rerun anchor. Treat an explicit `--last-result-id` override as a manual repair path when the inherited continuity anchor needs correction.

Ask user for clarifications if needed via conversational questions.
</step>

<step name="extract_persistent_state">
**Extract and append persistent derivation state to `GPD/DERIVATION-STATE.md`:**

Before writing the canonical continue-here handoff, append this session's equations, conventions, and results to the append-only cumulative derivation state file.

1. **Collect from the current session:**

   - Every equation derived (LaTeX form, units, validity range, derivation method)
   - Every convention choice made or confirmed (metric, Fourier, normalization, regularization)
   - Every intermediate result added to state.json (with result IDs), plus the canonical `last_result_id` rerun anchor when this session produced a persisted derivation result
   - Every approximation invoked (name, validity regime, how checked)

2. **Ensure `GPD/DERIVATION-STATE.md` exists**, then draft the session block separately.

```bash
# Get timestamp and phase context
timestamp=$(gpd --raw timestamp full)
phase_dir=$(ls -dt GPD/phases/*/ 2>/dev/null | head -1 | sed 's|/$||' | xargs basename)

# Create file with header if it doesn't exist
if [ ! -f GPD/DERIVATION-STATE.md ]; then
  cat > GPD/DERIVATION-STATE.md << 'HEADER'
# Derivation State (Cumulative)

This file is append-only. Each session appends its equations, conventions,
and results here before the CONTINUE-HERE file is deleted. This prevents
lossy compression across context resets.

HEADER
fi
```

Draft this session block as text first. Replace every placeholder with actual session content before appending it to `GPD/DERIVATION-STATE.md`; do not run or persist this template as-is:

```text
---

## Session: ${timestamp} | Phase: ${phase_dir}

### Equations Established
[Fill: every equation derived this session -- LaTeX, units, validity range]

### Conventions Applied
[Fill: any convention choices made or confirmed this session]

### Intermediate Results
[Fill: result IDs added to state.json this session with brief descriptions]

### Approximations Used
[Fill: approximations invoked, validity conditions, how checked]
```

3. **Append only the filled section** with actual content from the current session before proceeding.
   Do NOT leave the placeholders -- replace `[Fill: ...]` with real content.

4. **Tag each entry** with the current phase and plan context so the history is traceable.

5. **Prune stale entries after appending (cap enforcement):**

   After appending the new session block, check total size and prune if over limit so the file stays bounded without a resume-work read cycle.

   **IMPORTANT: Atomic read-modify-write through .tmp to prevent race conditions.**
   Read, transform, write a .tmp file, validate it, then atomically replace the original. If any step fails, preserve the original.

   ```bash
   # Count session blocks
   SESSION_COUNT=$(grep -c "^## Session:" GPD/DERIVATION-STATE.md 2>/dev/null || echo 0)

   if [ "$SESSION_COUNT" -gt 5 ]; then
     echo "DERIVATION-STATE.md has ${SESSION_COUNT} session blocks (cap: 5). Pruning oldest..."

     # Atomic read-modify-write: write to same-directory temp, validate, then rename
     TMP_FILE=$(mktemp GPD/DERIVATION-STATE.md.tmp.XXXXXX) || {
       echo "WARNING: Failed to create DERIVATION-STATE.md temp file. Keeping original."
       exit 1
     }
     trap "rm -f '$TMP_FILE'" EXIT

     # Keep only the 5 most recent session blocks
     KEEP_FROM=$(grep -n "^## Session:" GPD/DERIVATION-STATE.md | tail -5 | head -1 | cut -d: -f1)
     HEADER_END=$(grep -n "^## Session:" GPD/DERIVATION-STATE.md | head -1 | cut -d: -f1)
     HEADER_END=$((HEADER_END - 1))
     {
       head -n "$HEADER_END" GPD/DERIVATION-STATE.md
       echo ""
       echo "> Older session entries archived in git history."
       echo "> Use \`git log -p -- GPD/DERIVATION-STATE.md\` to recover."
       echo ""
       tail -n +"$KEEP_FROM" GPD/DERIVATION-STATE.md
     } > "$TMP_FILE"

     # Validate the tmp file before replacing
     TMP_LINES=$(wc -l < "$TMP_FILE")
     if [ "$TMP_LINES" -lt 5 ]; then
       echo "WARNING: Pruned file suspiciously small (${TMP_LINES} lines). Keeping original."
       rm -f "$TMP_FILE"
     elif ! grep -q "^# Derivation State" "$TMP_FILE"; then
       echo "WARNING: Pruned file missing required header. Keeping original."
       rm -f "$TMP_FILE"
     else
       # Same-directory rename is atomic on the project filesystem.
       if ! mv -f "$TMP_FILE" GPD/DERIVATION-STATE.md; then
         echo "WARNING: Failed to replace DERIVATION-STATE.md. Original preserved."
         rm -f "$TMP_FILE"
       fi
     fi
     trap - EXIT
   fi
   ```

   **Size cap per session block:** Each session block should target ~50-100 lines. If a session produced many equations, summarize older entries within the block rather than listing every intermediate step. The DERIVATION-STATE.md file is a reference index, not a full derivation log.

6. **Commit the updated file:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/DERIVATION-STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "wip: append derivation state from session" --files GPD/DERIVATION-STATE.md
```

</step>

<step name="write">
**Write the canonical continuation handoff artifact to `GPD/phases/{phase_slug}/.continue-here.md`** (where `{phase_slug}` is the detected phase directory name from the `detect` step, e.g., `03-dispersion`).

Use the shared template at `{GPD_INSTALL_DIR}/templates/continue-here.md` as the authoritative structure. Do not invent alternate tag names when writing the handoff. The canonical file should keep:

- YAML frontmatter: `phase`, `task`, `total_tasks`, `status`, `last_updated`
- `<current_state>` for the immediate physics situation
- `<completed_work>` for completed and partially completed tasks
- `<remaining_work>` for what is still left
- `<decisions_made>` for physics or method choices that must not be silently re-debated
- `<intermediate_results>` for equations, values, outputs, and convention snapshots needed on return
- If a canonical derived result was persisted this session, call out its `result_id` as `last_result_id` so reruns can target the same registry entry directly.
- `<blockers>` for active blockers and physics impact
- `<context>` for the reasoning chain and overall approach
- `<next_action>` for the exact first thing to do on return
- `<persistent_state>` for the subset that must be appended to `GPD/DERIVATION-STATE.md`

The `.continue-here.md` file and canonical continuation payload are handoff surfaces only. `state.json.continuation.handoff` is the durable handoff authority. If the pause produces a resumable bounded stop, persist the matching `execution_segment` into `continuation.bounded_segment`; that persisted field is the bounded authority for later resume logic. Do not treat the markdown handoff file or derived execution head as the durable authority.

Fold older ad hoc notions such as separate `parameter_values`, `approximations_active`, or `open_questions` into the canonical sections above instead of creating extra top-level tags. For example:

- parameter values and approximation regimes belong inside `<intermediate_results>` and `<context>`
- unresolved questions belong inside `<context>` or `<blockers>`, whichever better reflects whether they block execution

Be specific enough that a fresh AI session can resume from the canonical handoff without reconstructing the derivation from scratch.

Use `current-timestamp` for last_updated field. You can use init todos (which provides timestamps) or call directly:

```bash
timestamp=$(gpd --raw timestamp full)
```

</step>

<step name="update_state">
**Update STATE.md with pause context:**

```bash
: "${phase_slug:?set detected phase directory before recording session}"
: "${task_index:?set current task number before recording session}"
: "${task_total:?set total task count before recording session}"
resume_file="GPD/phases/${phase_slug}/.continue-here.md"
last_result_id=""               # set only when manually overriding or repairing the carried anchor

# Record one continuation pointer for runtime resume-work, gpd resume, and gpd resume --recent.
record_session_args=(
  --stopped-at "Paused at task ${task_index}/${task_total} in phase ${phase_slug}"
  --resume-file "$resume_file"
)
if [ -n "$last_result_id" ]; then
  record_session_args+=(--last-result-id "$last_result_id")
fi
gpd state record-session "${record_session_args[@]}"
if [ $? -ne 0 ]; then echo "WARNING: state record-session failed — resume info may be lost"; fi

# If the active bounded-segment continuity already carries a canonical
# last_result_id, omit --last-result-id and let the automatic continuity path
# supply it. Pass --last-result-id only when manually overriding or repairing
# the carried anchor.

# Mark Paused for resume-work; bounded continuation is managed separately.
gpd state patch --Status "Paused"
if [ $? -ne 0 ]; then echo "WARNING: state patch failed — status not marked as Paused"; fi
```

</step>

<step name="commit">
```bash
: "${phase_slug:?set detected phase directory before commit}"
: "${task_index:?set current task number before commit}"
: "${task_total:?set total task count before commit}"

PRE_CHECK=$(gpd pre-commit-check --files GPD/phases/*/.continue-here.md GPD/STATE.md GPD/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "wip: ${phase_slug} paused at task ${task_index}/${task_total}" --files GPD/phases/*/.continue-here.md GPD/STATE.md GPD/state.json
```

</step>

<step name="confirm">
```
Handoff created: GPD/phases/[{phase_slug}]/.continue-here.md

This is the canonical recorded handoff artifact for the current phase. `gpd:resume-work`
and the local `gpd resume` recovery surface should now point to the same continuation file.
If the user is not sure which repo to reopen, `gpd resume --recent` should be
the first discovery step before the per-project resume flow.

Current state:

- Phase: [{phase_slug}]
- Task: [X] of [Y]
- Status: [in_progress/blocked]
- Derivation state: [brief summary of where the calculation stands]
- Committed as WIP

To return in the runtime: gpd:resume-work
To inspect local recovery summary: gpd resume
To rediscover the project first: gpd resume --recent

```
</step>

</process>

<success_criteria>
- [ ] Persistent derivation state appended to `GPD/DERIVATION-STATE.md`
- [ ] DERIVATION-STATE.md committed separately before writing CONTINUE-HERE
- [ ] Canonical `.continue-here.md` created in correct phase directory
- [ ] Canonical section names from the shared template are preserved
- [ ] All canonical sections are filled with specific content, especially `<current_state>`, `<completed_work>`, `<remaining_work>`, `<intermediate_results>`, `<context>`, and `<next_action>`
- [ ] The `<persistent_state>` and `<intermediate_results>` sections in `.continue-here.md` are filled (documenting what was appended to DERIVATION-STATE.md)
- [ ] Enough physics context preserved that a fresh session can resume without re-deriving
- [ ] STATE.md session continuity updated as a handoff pointer to the pause point and resume file path
- [ ] STATE.md status set to "Paused"
- [ ] Committed as WIP (including STATE.md and state.json)
- [ ] User knows the handoff location and the return path via `gpd:resume-work` / `gpd resume` / `gpd resume --recent`
</success_criteria>

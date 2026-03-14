<purpose>
Create `.continue-here.md` handoff file to preserve complete research state across sessions. Enables seamless resumption with full context restoration, including derivation progress, parameter values, intermediate results, and theoretical assumptions.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="detect">
Find current phase directory from most recently modified files:

```bash
# Find most recent phase directory with work
ls -lt .gpd/phases/*/*PLAN.md 2>/dev/null | head -1 | sed 's|.*phases/||' | sed 's|/.*||'
```

If no active phase detected, ask user which phase they're pausing work on.
</step>

<step name="gather">
**Collect complete research state for handoff:**

1. **Current position**: Which phase, which plan, which task
2. **Derivation state**: Where in the calculation or derivation are we? What equations have been established, what remains to be shown?
3. **Parameter values**: All parameter values, coupling constants, cutoffs, or numerical settings currently in use
4. **Intermediate results**: Partial results, expressions derived so far, numerical outputs obtained
5. **Approximations active**: Which approximations or truncations are in effect, with their justifications
6. **Work completed**: What got done this session (derivations finished, code written, plots generated, checks passed)
7. **Work remaining**: What's left in current plan/phase
8. **Decisions made**: Key decisions and rationale (sign conventions chosen, gauge fixed, method selected)
9. **Open questions**: Physics questions that arose during the session and remain unresolved
10. **Blockers/issues**: Anything stuck (divergence encountered, numerical instability, missing input data)
11. **Mental context**: The theoretical approach, next steps, "vibe" of where this is going
12. **Files modified**: What's changed but not committed (scripts, notebooks, LaTeX, data files)

Ask user for clarifications if needed via conversational questions.
</step>

<step name="extract_persistent_state">
**Extract and append persistent derivation state to `.gpd/DERIVATION-STATE.md`:**

Before writing the ephemeral CONTINUE-HERE file, extract all equations, conventions,
and results from the current session and append them to the cumulative derivation
state file. This file is append-only and never deleted -- it is the permanent record
that prevents lossy compression across context resets.

1. **Collect from the current session:**

   - Every equation derived (LaTeX form, units, validity range, derivation method)
   - Every convention choice made or confirmed (metric, Fourier, normalization, regularization)
   - Every intermediate result added to state.json (with result IDs)
   - Every approximation invoked (name, validity regime, how checked)

2. **Append to `.gpd/DERIVATION-STATE.md`** (create if it doesn't exist):

```bash
# Get timestamp and phase context
timestamp=$(gpd --raw timestamp full)
phase_dir=$(ls -dt .gpd/phases/*/ 2>/dev/null | head -1 | sed 's|/$||' | xargs basename)

# Create file with header if it doesn't exist
if [ ! -f .gpd/DERIVATION-STATE.md ]; then
  cat > .gpd/DERIVATION-STATE.md << 'HEADER'
# Derivation State (Cumulative)

This file is append-only. Each session appends its equations, conventions,
and results here before the CONTINUE-HERE file is deleted. This prevents
lossy compression across context resets.

HEADER
fi

# Append this session's persistent state
cat >> .gpd/DERIVATION-STATE.md << EOF

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

EOF
```

3. **Fill in the appended section** with actual content from the current session before proceeding.
   Do NOT leave the placeholders -- replace `[Fill: ...]` with real content.

4. **Tag each entry** with the current phase and plan context so the history is traceable.

5. **Prune stale entries after appending (cap enforcement):**

   After appending the new session block, check total size and prune if over limit.
   This ensures the file stays bounded even without a resume-work read cycle.

   **IMPORTANT: Atomic read-modify-write through .tmp to prevent race conditions.**
   The pruning operation reads the file, transforms it, writes to a .tmp file, validates
   the .tmp file, then atomically replaces the original. If ANY step fails, the original
   is preserved.

   ```bash
   # Count session blocks
   SESSION_COUNT=$(grep -c "^## Session:" .gpd/DERIVATION-STATE.md 2>/dev/null || echo 0)

   if [ "$SESSION_COUNT" -gt 5 ]; then
     echo "DERIVATION-STATE.md has ${SESSION_COUNT} session blocks (cap: 5). Pruning oldest..."

     # Atomic read-modify-write: write to .tmp, validate, then replace
     TMP_FILE=".gpd/DERIVATION-STATE.md.tmp.$$"
     trap "rm -f '$TMP_FILE'" EXIT

     # Keep only the 5 most recent session blocks
     KEEP_FROM=$(grep -n "^## Session:" .gpd/DERIVATION-STATE.md | tail -5 | head -1 | cut -d: -f1)
     HEADER_END=$(grep -n "^## Session:" .gpd/DERIVATION-STATE.md | head -1 | cut -d: -f1)
     HEADER_END=$((HEADER_END - 1))
     {
       head -n "$HEADER_END" .gpd/DERIVATION-STATE.md
       echo ""
       echo "> Older session entries archived in git history."
       echo "> Use \`git log -p -- .gpd/DERIVATION-STATE.md\` to recover."
       echo ""
       tail -n +"$KEEP_FROM" .gpd/DERIVATION-STATE.md
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
       # Atomic replace: cp to preserve original on failure, then rm tmp
       cp "$TMP_FILE" .gpd/DERIVATION-STATE.md && \
         rm -f "$TMP_FILE" || \
         echo "WARNING: Failed to replace DERIVATION-STATE.md. Original preserved."
     fi
     trap - EXIT
   fi
   ```

   **Size cap per session block:** Each session block should target ~50-100 lines. If a session produced many equations, summarize older entries within the block rather than listing every intermediate step. The DERIVATION-STATE.md file is a reference index, not a full derivation log.

6. **Commit the updated file:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/DERIVATION-STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "wip: append derivation state from session" --files .gpd/DERIVATION-STATE.md
```

</step>

<step name="write">
**Write handoff to `.gpd/phases/{phase_slug}/.continue-here.md`** (where `{phase_slug}` is the detected phase directory name from the `detect` step, e.g., `03-dispersion`):

```markdown
---
phase: {phase_slug}
task: 3
total_tasks: 7
status: in_progress
last_updated: [timestamp from current-timestamp]
---

<current_state>
[Where exactly are we? Immediate context -- which equation, which step of the derivation, which numerical experiment]
</current_state>

<derivation_state>
[Current position in the theoretical calculation. What has been established (key equations, identities proven, limits checked). What remains to be derived or verified.]
</derivation_state>

<parameter_values>
[All parameter values, coupling constants, cutoffs, grid sizes, convergence thresholds currently in use. Include units.]

- [parameter]: [value] ([units]) -- [why this value]
  </parameter_values>

<intermediate_results>
[Partial results obtained so far. Key expressions, numerical outputs, plots generated. Include enough detail to resume without re-deriving.]

- [result]: [value or expression] -- [how obtained, which script/notebook]
  </intermediate_results>

<approximations_active>
[Which approximations or truncations are in effect and their justifications]

- [approximation]: [justification] -- [validity regime]
  </approximations_active>

<completed_work>

- Task 1: [name] - Done
- Task 2: [name] - Done
- Task 3: [name] - In progress, [what's done]
  </completed_work>

<remaining_work>

- Task 3: [what's left]
- Task 4: Not started
- Task 5: Not started
  </remaining_work>

<decisions_made>

- Decided to use [method/convention] because [physics reason]
- Chose [approach] over [alternative] because [reason]
  </decisions_made>

<open_questions>

- [Physics question that arose and remains unresolved]
- [Discrepancy noticed but not yet investigated]
  </open_questions>

<blockers>
- [Blocker 1]: [status/workaround]
</blockers>

<context>
[Mental state, theoretical intuition, the plan -- what were you thinking about the physics, where is this heading]
</context>

<next_action>
Start with: [specific first action when resuming -- e.g., "continue expanding Eq. (12) to second order in the coupling", "run convergence test with N=128", "check Ward identity for the vertex function"]
</next_action>
```

Be specific enough for a fresh AI session to understand immediately and pick up the physics without re-reading everything from scratch.

Use `current-timestamp` for last_updated field. You can use init todos (which provides timestamps) or call directly:

```bash
timestamp=$(gpd --raw timestamp full)
```

</step>

<step name="update_state">
**Update STATE.md with pause context:**

```bash
# Record session continuity so resume-work knows where we stopped
gpd state record-session \
  --stopped-at "Paused at task [X]/[Y] in phase [{phase_slug}]" \
  --resume-file ".gpd/phases/[{phase_slug}]/.continue-here.md"
if [ $? -ne 0 ]; then echo "WARNING: state record-session failed — resume info may be lost"; fi

# Set status to Paused so resume-work detects it
gpd state patch --Status "Paused"
if [ $? -ne 0 ]; then echo "WARNING: state patch failed — status not marked as Paused"; fi
```

</step>

<step name="commit">
```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/phases/*/.continue-here.md .gpd/STATE.md .gpd/state.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "wip: [phase-name] paused at task [X]/[Y]" --files .gpd/phases/*/.continue-here.md .gpd/STATE.md .gpd/state.json
```

</step>

<step name="confirm">
```
Handoff created: .gpd/phases/[{phase_slug}]/.continue-here.md

Current state:

- Phase: [{phase_slug}]
- Task: [X] of [Y]
- Status: [in_progress/blocked]
- Derivation state: [brief summary of where the calculation stands]
- Committed as WIP

To resume: /gpd:resume-work

```
</step>

</process>

<success_criteria>
- [ ] Persistent derivation state appended to `.gpd/DERIVATION-STATE.md` (equations, conventions, results, approximations from this session)
- [ ] DERIVATION-STATE.md committed separately before writing CONTINUE-HERE
- [ ] .continue-here.md created in correct phase directory
- [ ] All sections filled with specific content, especially derivation_state, parameter_values, intermediate_results, and approximations_active
- [ ] The `<derivation_state>` and `<intermediate_results>` sections in .continue-here.md are filled (documenting what was appended to DERIVATION-STATE.md)
- [ ] Enough physics context preserved that a fresh session can resume without re-deriving
- [ ] STATE.md session continuity updated with pause point and resume file path
- [ ] STATE.md status set to "Paused"
- [ ] Committed as WIP (including STATE.md and state.json)
- [ ] User knows location and how to resume
</success_criteria>

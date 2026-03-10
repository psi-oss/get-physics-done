<purpose>
Combine two research phases that turned out to be more tightly coupled than expected. Absorbs a source phase into a target phase, merging plans, summaries, verification results, and convention records. Updates ROADMAP.md, STATE.md, and the dependency graph.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="init" priority="first">
**Parse arguments and load context:**

```bash
INIT=$(gpd init phase-op --include state,roadmap)
```

Extract from $ARGUMENTS: `source_phase` (to be absorbed) and `target_phase` (to absorb into).

**If arguments incomplete:**

```
Usage: /gpd:merge-phases <source> <target>

  <source>  Phase number to absorb (will be removed)
  <target>  Phase number to merge into (will be expanded)

Example: /gpd:merge-phases 5 4
  Absorbs Phase 5 into Phase 4.
```

Exit.

**Validate both phases exist and resolve directories:**

```bash
SOURCE_INFO=$(gpd phase find "${SOURCE_PHASE}")
TARGET_INFO=$(gpd phase find "${TARGET_PHASE}")
```

**If either phase not found:** Error with available phases from roadmap.

Extract from find-phase: `source_dir` (`directory`), `source_name` (`phase_name`), `target_dir` (`directory`), `target_name` (`phase_name`).

**Get goals from roadmap:**

```bash
SOURCE_GOAL=$(gpd roadmap get-phase "${SOURCE_PHASE}" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('goal',''))")
TARGET_GOAL=$(gpd roadmap get-phase "${TARGET_PHASE}" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('goal',''))")
```
</step>

<step name="validate_merge">
**Idempotency guard — check if merge was already partially applied:**

```bash
# Check if source directory still exists (merge may have been partially applied)
if [ ! -d "${SOURCE_DIR}" ]; then
  echo "WARNING: Source phase directory ${SOURCE_DIR} does not exist."
  echo "This merge may have already been applied (source was absorbed)."
  echo ""
  echo "Check target phase for merged plans:"
  ls "${TARGET_DIR}"/*-PLAN.md 2>/dev/null
  echo ""
  echo "If the merge is already complete, no further action needed."
  echo "If the merge was interrupted, check git log for partial commits."
  exit 0
fi

# Check if target already contains plans from source (partial merge)
MERGED_MARKER=$(ls "${TARGET_DIR}"/merged-from-phase-${SOURCE_PHASE}-* 2>/dev/null | head -1)
if [ -n "$MERGED_MARKER" ]; then
  echo "WARNING: Target already contains merged artifacts from Phase ${SOURCE_PHASE}."
  echo "This merge may have been partially applied."
  echo ""
  echo "Options:"
  echo "  1. Continue merge (skip already-copied files)"
  echo "  2. Abort (inspect manually)"
  echo ""
  # Wait for user decision before proceeding
fi
```

**Verify merge is safe:**

1. **Adjacency check:** Phases should be adjacent or closely related. Warn if `|source - target| > 2`:

   ```
   WARNING: Phases {source} and {target} are not adjacent.
   Merging distant phases may create dependency issues.
   Continue anyway? (y/n)
   ```

2. **Completion status check:**

   ```bash
   ls "${SOURCE_DIR}"/*-SUMMARY.md 2>/dev/null | wc -l
   ls "${SOURCE_DIR}"/*-PLAN.md 2>/dev/null | wc -l
   ls "${TARGET_DIR}"/*-SUMMARY.md 2>/dev/null | wc -l
   ls "${TARGET_DIR}"/*-PLAN.md 2>/dev/null | wc -l
   ```

   Report status of both phases (complete, partial, unstarted).

3. **Dependency check:** Verify no other phases depend solely on the source phase.

   Inspect SUMMARY frontmatter and ROADMAP dependencies directly. Check whether any other phase has `requires` entries pointing to artifacts that only the source phase provides. Those dependencies must be redirected to the target after the merge. If the dependency picture is nontrivial, reuse the manual graph-building procedure from `workflows/graph.md`.

**Present merge plan to user:**

```
## Merge Plan

**Source:** Phase {S}: {source_name} ({plan_count} plans, {summary_count} summaries)
**Target:** Phase {T}: {target_name} ({plan_count} plans, {summary_count} summaries)

### What will happen:
1. Source plans appended to target (renumbered)
2. Source summaries copied to target
3. Source verification results preserved as-is
4. ROADMAP.md updated (source removed, target expanded)
5. STATE.md updated
6. Dependencies redirected: {list or "none"}

Proceed? (y/n)
```

Wait for user confirmation.
</step>

<step name="analyze_overlap">
**Check for content overlap between source and target:**

Read PLAN.md files from both phases. Compare:

- Overlapping objectives (plans that derive/compute the same thing)
- Shared convention declarations
- Duplicate file paths in `files_modified` frontmatter

If overlap found:

```
## Content Overlap Detected

| Source Plan | Target Plan | Overlap |
|------------|------------|---------|
| {S}-01 | {T}-02 | Both compute {quantity} |

These overlapping plans will need manual reconciliation after merge.
```
</step>

<step name="merge_plans">
**Copy and renumber source plans into target directory:**

1. Determine the next plan number in target: count existing `*-PLAN.md` files
2. For each source plan:

   ```bash
   # Renumber: source plan 01 becomes target plan (N+1), etc.
   NEW_NUM=$(printf "%02d" $((TARGET_PLAN_COUNT + SOURCE_INDEX)))
   NEW_PREFIX="${TARGET_PHASE_PADDED}-${NEW_NUM}"
   ```

3. Copy plan file with new name
4. Update frontmatter in copied plan:
   - Update plan number
   - Update `depends_on` references (source phase refs -> target phase refs)
   - Preserve wave assignments (may need adjustment)
5. Copy matching SUMMARY.md files with same renumbering

**Source plans are APPENDED to target, never overwrite existing target plans.**
</step>

<step name="merge_verification">
**Handle verification and research artifacts:**

```bash
# Copy verification results (preserve as-is with source phase prefix)
for FILE in "${SOURCE_DIR}"/*-VERIFICATION.md "${SOURCE_DIR}"/*-VALIDATION.md; do
  if [ -f "$FILE" ]; then
    cp "$FILE" "${TARGET_DIR}/merged-from-phase-${SOURCE_PHASE}-$(basename "$FILE")"
  fi
done

# Copy research and context if target lacks them
for FILE in "${SOURCE_DIR}"/*-RESEARCH.md "${SOURCE_DIR}"/*-CONTEXT.md; do
  if [ -f "$FILE" ] && ! ls "${TARGET_DIR}"/*-RESEARCH.md 2>/dev/null; then
    cp "$FILE" "${TARGET_DIR}/"
  fi
done
```

Copy any scripts, data files, or other artifacts from source to target.
</step>

<step name="reconcile_conventions">
**Reconcile conventions between phases:**

Read convention declarations from SUMMARY.md frontmatter in both phases:

```bash
gpd summary-extract "${SOURCE_DIR}"/*-SUMMARY.md --field conventions
gpd summary-extract "${TARGET_DIR}"/*-SUMMARY.md --field conventions
```

**If conventions conflict** (same field, different value):

```
## Convention Conflict

| Field | Source (Phase {S}) | Target (Phase {T}) |
|-------|-------------------|-------------------|
| metric_signature | (-,+,+,+) | (+,-,-,-) |

CRITICAL: This must be resolved before merge completes.
Which convention should the merged phase use?
```

Wait for user decision. Record decision via gpd CLI:

```bash
gpd state add-decision --phase "${TARGET_PHASE}" --summary "Convention resolution for merge: chose {chosen}" --rationale "{user rationale}"
```

**If conventions compatible:** No action needed.
</step>

<step name="update_roadmap">
**Update ROADMAP.md:**

1. Remove the source phase entry
2. Expand the target phase description to include source objectives:

   ```markdown
   ## Phase {T}: {target_name} (merged with Phase {S}: {source_name})

   **Goal:** {target_goal}. Additionally: {source_goal}
   ```

3. Renumber all phases after source (if source < target, phases between shift down)
4. Update dependency references throughout: any `requires: Phase {S}` becomes `requires: Phase {T}`

Write updated ROADMAP.md.
</step>

<step name="update_state">
**Update STATE.md:**

```bash
gpd state patch \
  "--Current Phase" "${TARGET_PHASE}" \
  "--Last Activity Description" "Merged phase ${SOURCE_PHASE} into ${TARGET_PHASE}"
if [ $? -ne 0 ]; then echo "WARNING: state patch failed — phase position may be wrong"; fi
```

Record merge decision:

```bash
gpd state add-decision \
  --phase "${TARGET_PHASE}" \
  --summary "Merged Phase ${SOURCE_PHASE} (${SOURCE_NAME}) into Phase ${TARGET_PHASE} (${TARGET_NAME})" \
  --rationale "${USER_RATIONALE}"
if [ $? -ne 0 ]; then echo "WARNING: state add-decision failed — merge decision not recorded"; fi
```
</step>

<step name="cleanup_source">
**Remove source phase directory:**

```bash
# Safety: verify all files were copied before removing
SOURCE_FILE_COUNT=$(find "${SOURCE_DIR}" -type f | wc -l)
# Compare against expected copied count

if [ "${ALL_COPIED}" = "true" ]; then
  rm -rf "${SOURCE_DIR}"
else
  echo "WARNING: Not all source files were copied. Source directory preserved."
  echo "Manual cleanup needed: ${SOURCE_DIR}"
fi
```
</step>

<step name="commit">
**Commit all merge changes atomically:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/state.json "${TARGET_DIR}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "refactor(phases): merge phase ${SOURCE_PHASE} into phase ${TARGET_PHASE}" \
  --files .gpd/ROADMAP.md .gpd/STATE.md .gpd/state.json "${TARGET_DIR}"
```
</step>

<step name="report">
**Present merge summary:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PHASES MERGED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase {S}: {source_name} absorbed into Phase {T}: {target_name}

**Plans:** {target_original} + {source_count} = {total} plans
**Summaries:** {summary_count} completed
**Convention conflicts:** {count resolved or "none"}
**Dependencies redirected:** {count or "none"}

---

**Also available:**
- /gpd:show-phase {T} -- inspect merged phase
- /gpd:execute-phase {T} -- execute pending plans
- /gpd:validate-conventions -- verify convention consistency

---
```
</step>

</process>

<failure_handling>

- **Phase not found:** List available phases from roadmap. Exit.
- **Convention conflict unresolved:** Do not proceed with merge. User must decide.
- **File copy failure:** Preserve source directory. Report which files failed. User can retry or merge manually.
- **Circular dependency after merge:** Detect during dependency graph update. Warn user and suggest resolution.

</failure_handling>

<success_criteria>

- [ ] Both phases validated as existing
- [ ] User confirmed merge plan
- [ ] Content overlap analyzed and reported
- [ ] Source plans appended to target (renumbered, dependencies updated)
- [ ] Verification artifacts preserved
- [ ] Convention conflicts resolved (if any)
- [ ] ROADMAP.md updated (source removed, target expanded, phases renumbered)
- [ ] STATE.md updated with merge decision
- [ ] Source directory removed (or preserved if incomplete copy)
- [ ] All changes committed atomically
- [ ] Merge summary presented
</success_criteria>

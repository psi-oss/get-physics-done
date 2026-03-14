<purpose>
Supersede a completed research phase and create a replacement phase for iterative revision. The original phase is marked as superseded (not deleted) to preserve the historical record of the research path. The replacement phase inherits valid decisions and context from the original while addressing what needs to change. This supports non-linear research where earlier results must be revisited after gaining new understanding.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="parse_arguments">
Parse the command arguments:
- First argument: phase number to revise (integer or decimal)
- Remaining arguments (in quotes): reason for revision

Example: `/gpd:revise-phase 3 "Sign error in vertex correction propagated to all subsequent phases"`
-> phase = 3
-> reason = "Sign error in vertex correction propagated to all subsequent phases"

Example: `/gpd:revise-phase 5.1 "Regularization scheme breaks gauge invariance"`
-> phase = 5.1
-> reason = "Regularization scheme breaks gauge invariance"

If arguments missing or malformed:

```
ERROR: Phase number and reason required
Usage: /gpd:revise-phase <phase-number> "<reason for revision>"
Example: /gpd:revise-phase 3 "Sign error in vertex correction"
```

Exit.
</step>

<step name="load_context">
Load project context and verify the target phase:

```bash
INIT=$(gpd init phase-op "${target_phase}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract: `phase_found`, `phase_dir`, `phase_number`, `commit_docs`, `roadmap_exists`.

**If `phase_found` is false:**

```
ERROR: Phase not found: ${target_phase}

Available phases:
$(gpd phase list)

Usage: /gpd:revise-phase <phase-number> "<reason>"
```

Exit.

Also read:

- `.gpd/ROADMAP.md` -- full roadmap structure
- `.gpd/STATE.md` -- current position and accumulated context
- All artifacts in the target phase directory:

```bash
ls ${phase_dir}/ 2>/dev/null
```

Read the target phase's PLAN.md, SUMMARY.md, VERIFICATION.md, and CONTEXT.md files if they exist.

**Validation: Phase must be completed (not future)**

Compare target phase to current phase from STATE.md:

- Target must be < current phase number (completed phase)
- OR target must be == current phase AND have SUMMARY.md files (completed plans)

If the target phase is a future unstarted phase:

```
ERROR: Cannot revise Phase {target} -- it has not been completed yet.

Phase {target} is a future phase. Options:
- /gpd:remove-phase {target} -- remove it entirely
- /gpd:plan-phase {target} -- plan it differently from scratch

Revision applies to completed phases where results need reworking.
```

Exit.

**Display current phase state:**

```
## Phase {target}: {Name}

**Goal:** {goal from ROADMAP.md}
**Status:** Completed
**Results:** {brief summary from SUMMARY.md files}
**Verification:** {status from VERIFICATION.md if exists}
**Plans executed:** {count}

**Reason for revision:** {reason}
```

</step>

<step name="analyze_revision_scope">
Analyze what needs to change and what can be preserved.

**Ask the user (interactive mode) or infer (yolo mode):**

```
## Revision Scope Analysis

What specifically needs to change in Phase {target}?

1. **Method** -- The approach was wrong; need a different technique
2. **Assumptions** -- Key assumptions were invalid; need to relax or change them
3. **Entire approach** -- Everything needs redoing from scratch
4. **Partial results** -- Some results are valid, others need correction

Which applies? (1/2/3/4, or describe)
```

**Identify downstream impact:**

Read ROADMAP.md to find all phases that come after the target phase. For each subsequent phase that has been completed, check if its PLAN.md or CONTEXT.md references results from the target phase.

```bash
# Search for references to the target phase in downstream phases
```

Use search_files to search `.gpd/phases/` for references to the target phase number, its results, or its key outputs.

Build an impact assessment:

```
## Downstream Impact

**Directly affected phases:**
- Phase {X}: {name} -- references {specific result} from Phase {target}
- Phase {Y}: {name} -- depends on {assumption} established in Phase {target}

**Potentially affected phases:**
- Phase {Z}: {name} -- uses notation from Phase {target} (likely still valid)

**Unaffected phases:**
- Phase {W}: {name} -- independent of Phase {target}
```

**Identify what is still valid from the original phase:**

Review SUMMARY.md and DECISIONS.md entries for the target phase. Categorize each decision and result as:

- **Still valid:** Can be carried forward to replacement phase
- **Invalidated:** Must be redone in replacement phase
- **Uncertain:** Needs re-evaluation in replacement phase

</step>

<step name="mark_phase_superseded">
Mark the original phase as superseded in ROADMAP.md.

**In ROADMAP.md**, find the target phase entry and update its status:

1. Change the checkbox from `[x]` to `[s]` (superseded marker)
2. Add a superseded note after the phase entry:

```markdown
- [s] **Phase {target}: {Name}** -- SUPERSEDED by Phase {replacement_number}
  - Reason: {reason}
  - Original completion: {original_date}
```

**Do NOT delete the original phase directory or its artifacts.** They are historical record of the research path. The original SUMMARY.md files document what was tried and why it was superseded.

**Add a SUPERSEDED.md file to the original phase directory:**

Write `.gpd/phases/{target_dir}/SUPERSEDED.md`:

```markdown
# Phase {target}: SUPERSEDED

**Superseded by:** Phase {replacement_number}
**Date:** {today}
**Reason:** {reason}

## What was learned

{Brief summary of what the original phase established, even if the results are being revised}

## What is being changed

{What specifically needs to change and why}

## What remains valid

{Decisions and results from this phase that carry forward}
```

</step>

<step name="create_replacement_phase">
Create the replacement phase using decimal numbering.

**Calculate replacement phase number:**

The replacement phase number is `{target}.1` (or `{target}.2`, `{target}.3`, etc. if earlier revisions exist).

```bash
# Check for existing decimal phases under this integer
ls -d .gpd/phases/${target_integer}.* 2>/dev/null
```

Use the next available decimal.

**Create phase directory:**

```bash
RESULT=$(gpd phase insert "${target_phase}" "${phase_name_with_revised_prefix}")
if [ $? -ne 0 ]; then
  echo "ERROR: phase insert failed: $RESULT"
  # STOP — do not proceed.
fi
```

Use description: "Revise: {original phase name} -- {brief reason}"

The CLI handles directory creation and ROADMAP.md insertion.

**Pre-populate CONTEXT.md in the replacement phase:**

Write `.gpd/phases/{replacement_dir}/CONTEXT.md`:

```markdown
# Phase {replacement_number}: Context

## Revision of Phase {target}

This phase supersedes Phase {target} ({original_name}).

### Revision trigger

{reason}

### What worked in the original phase

{List of valid results, methods, and decisions from the original}

### What did not work

{What failed or was invalidated, with explanation}

### What to do differently

{Specific changes to approach, method, or assumptions}

### Inherited decisions

{Decisions from Phase {target} that remain valid, with DEC-IDs if available}

### Requirements mapping

{REQ-IDs inherited from the original phase}

### Reference

- Original phase: `.gpd/phases/{target_dir}/`
- Original summary: `.gpd/phases/{target_dir}/{target}-01-SUMMARY.md` (etc.)
- Supersession record: `.gpd/phases/{target_dir}/SUPERSEDED.md`
```

</step>

<step name="update_dependencies">
Find all downstream phases that depend on the superseded phase and update their references.

**Search for dependency references:**

```bash
# Find phases that reference the superseded phase
```

Use search_files to search `.gpd/phases/` and `.gpd/ROADMAP.md` for:

- "Phase {target}" references
- "Depends on.\*{target}" patterns
- Results or artifacts from Phase {target} cited in other phases

**For each downstream phase with a dependency:**

1. Update "Depends on" references in ROADMAP.md to point to the replacement phase number
2. If the downstream phase has a CONTEXT.md or PLAN.md that references Phase {target} results, add a note:

```markdown
> **Note:** Phase {target} has been superseded by Phase {replacement_number}.
> Results referenced from Phase {target} may change after the revision is complete.
```

**Flag downstream phases that may also need revision:**

If a completed downstream phase heavily depends on invalidated results from the target phase, flag it:

```
WARNING: Phase {X} ({name}) may also need revision.
It depends on {specific_result} from Phase {target}, which is being invalidated.
Consider: /gpd:revise-phase {X} "{cascading_reason}"
```

</step>

<step name="update_state">
Update project state with the revision event using gpd commands (ensures STATE.md + state.json stay in sync):

1. Record the supersession decision:

```bash
gpd state add-decision --phase "${target}" --summary "Superseded Phase ${target} (${name}) with Phase ${replacement_number}" --rationale "${reason}"
```

2. Add a blocker noting the results are under revision:

```bash
gpd state add-blocker --text "Phase ${target} results under revision -- superseded by Phase ${replacement_number}: ${reason}"
```

3. Update last activity:

```bash
gpd state update "Last Activity" "$(date +%Y-%m-%d)"
```

4. Update ROADMAP.md progress table if one exists -- the superseded phase should show status "Superseded" rather than "Complete". Use the file_edit tool for this ROADMAP.md change (not STATE.md).

Do NOT edit STATE.md directly — always use gpd state commands to maintain state.json sync.
</step>

<step name="commit">
Stage and commit all changes:

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/ROADMAP.md .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs(phase-${target_padded}): supersede and replace — ${reason}" --files .gpd/
```
</step>

<step name="offer_next_steps">
Present completion summary and next steps:

```
## Phase {target} Superseded

**Original:** Phase {target}: {original_name} -- marked as superseded
**Replacement:** Phase {replacement_number}: {replacement_name} -- created with inherited context

### Changes made:
- Marked Phase {target} as superseded in ROADMAP.md
- Created SUPERSEDED.md in original phase directory
- Created Phase {replacement_number} directory with pre-populated CONTEXT.md
- Updated {N} downstream dependency references
- Updated STATE.md and DECISIONS.md
- Committed: docs(phase-{target_padded}): supersede and replace — {reason}

### Downstream impact:
{List of affected phases, or "No downstream phases affected"}

{If flagged phases exist:}
### Phases that may also need revision:
- Phase {X}: {name} -- depends on invalidated results
{End if}

---

## Next Steps

**Plan the replacement phase now?**
`/gpd:plan-phase {replacement_number}`

<sub>`/clear` first -> fresh context window</sub>

**Review affected downstream phases first?**
{List /gpd:show-phase commands for affected phases}

---
```

</step>

</process>

<anti_patterns>

- Don't delete the original phase directory or any of its artifacts -- they are historical record
- Don't mark future/unstarted phases as superseded -- use /gpd:remove-phase instead
- Don't silently skip downstream dependency updates -- always check and update references
- Don't create the replacement without pre-populating CONTEXT.md -- the whole point is to carry forward learnings
- Don't use `python` for gpd invocations -- always use `gpd`
- Don't renumber existing phases -- use decimal numbering for the replacement
- Don't modify the original phase's PLAN.md or SUMMARY.md files -- only add SUPERSEDED.md

</anti_patterns>

<success_criteria>
Phase revision is complete when:

- [ ] Target phase verified as completed (not future)
- [ ] Revision scope analyzed (what changes, what is preserved, downstream impact)
- [ ] Original phase marked as superseded in ROADMAP.md (not deleted)
- [ ] SUPERSEDED.md created in original phase directory
- [ ] Replacement phase created with decimal numbering
- [ ] CONTEXT.md pre-populated with revision context (what worked, what didn't, what to change)
- [ ] Downstream dependency references updated to replacement phase
- [ ] Downstream phases flagged if they may also need revision
- [ ] Decision recorded via `gpd state add-decision` (STATE.md + state.json synced)
- [ ] Blocker recorded via `gpd state add-blocker` for results under revision
- [ ] Changes committed with descriptive message
- [ ] User informed of next steps (plan replacement or review downstream)

</success_criteria>

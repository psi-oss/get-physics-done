---
name: gpd:deslop-paper
description: Deslopify a finalized manuscript; strip public-facing AI/agent writing tells under frozen scientific invariants, with a by-line audit and substantive issues flagged, not fixed
argument-hint: "[manuscript root or .tex entrypoint] [--mode audit|apply|ci]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - task
help:
  group: Writing and publication
  order: 485
  compact_description: Deslopify a manuscript; strip AI/agent tells, freeze the science, emit a by-line audit and author flags
  display_signature: gpd:deslop-paper [manuscript] [--mode audit|apply|ci]
---

<purpose>
Deslopify a finalized manuscript: remove public-facing AI/agent writing tells while
freezing all scientific content, emitting a by-line audit and an author-flag list.
Standalone entry point for the deslopification gate (also runs inside
`gpd:write-paper` publication-review finalization and as an `gpd:arxiv-submission`
pre-flight). Authority: `references/publication/deslopification-gate.md`.
Worker: `gpd-discipline-editor` (it may only propose style edits or flags; never repair claims).
</purpose>

<usage>
```bash
gpd:deslop-paper                                   # resolve current manuscript, audit mode
gpd:deslop-paper manuscript/main.tex --mode audit  # propose edits + flags; do not modify
gpd:deslop-paper manuscript/main.tex --mode apply  # apply only invariant-passing edits; write audit
gpd:deslop-paper GPD/publication/<slug>/manuscript --mode apply --strict
gpd:deslop-paper <manuscript> --mode ci            # fail if release-blocking slop remains
```

| Mode | Behavior |
|------|----------|
| `audit` (default) | Produce proposed edits and flags; the manuscript is not modified. |
| `apply` | Apply only edits that pass every invariant check; write the full by-line audit and the edited `.tex`. |
| `ci` | Fail-closed: `gate_status: blocked` if scaffolding leakage, placeholder/submission-time-check citations, missing/incomplete audit coverage, or unresolved notation/concept-order flags remain. |

`--strict` additionally treats any unresolved FLAG (not just release blockers) as a non-zero exit.
</usage>

<init>
```bash
if [ -n "${ARGUMENTS:-}" ]; then DESLOP_INIT=$(gpd --raw init deslop-paper -- "$ARGUMENTS"); else DESLOP_INIT=$(gpd --raw init deslop-paper); fi
if [ $? -ne 0 ]; then echo "ERROR: deslop-paper init failed: $DESLOP_INIT"; fi
INIT="$DESLOP_INIT"
PAPER_DIR=$(echo "$INIT" | gpd json get .manuscript_root --default "")
MANUSCRIPT=$(echo "$INIT" | gpd json get .manuscript_entrypoint --default "")
MODE=$(echo "$INIT" | gpd json get .mode --default audit)
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
```
If the manuscript root or entrypoint cannot be resolved, stop and report; do not guess a target.
</init>

<run>
Spawn the editor using the canonical runtime delegation convention. `readonly=true` for `audit`/`ci`,
`readonly=false` for `apply`:

```python
task(
  subagent_type="gpd-discipline-editor",
  model="{writer_model}",
  readonly=(MODE != "apply"),
  prompt="Read {GPD_AGENTS_DIR}/gpd-discipline-editor.md and {GPD_INSTALL_DIR}/references/publication/deslopification-gate.md. Run the four-pass deslopification gate on ${MANUSCRIPT} in --mode ${MODE}. Freeze every protected span and the claim/notation/citation ledgers first; route each paragraph KEEP/EDIT/FLAG; apply only invariant-passing style edits; flag (never fix) everything substantive. Write ${PAPER_DIR}/DESLOP-AUDIT.jsonl, ${PAPER_DIR}/DESLOP-AUDIT.md, ${PAPER_DIR}/DESLOP-FLAGS.md, ${PAPER_DIR}/DESLOP-SUMMARY.json; in apply mode also write the edited ${MANUSCRIPT}.\n\n<autonomy_mode>${AUTONOMY}</autonomy_mode>",
  description="Deslopification gate (${MODE})"
)
```

Then read `${PAPER_DIR}/DESLOP-SUMMARY.json`:
- `audit`: present `edit_count`/`flag_count`/`release_blocker_count`; recommend `--mode apply` if edits are safe.
- `apply`: compile when possible; report `gate_status`, the edited file, and the flag list. Edits are auditable in `DESLOP-AUDIT.md`.
- `ci`: exit non-zero if `gate_status: blocked` (or, with `--strict`, if any FLAG is unresolved).
</run>

<success_criteria>
- [ ] Manuscript root + entrypoint resolved; not guessed.
- [ ] `gpd-discipline-editor` ran the four passes; protected spans frozen before any edit.
- [ ] `DESLOP-AUDIT.{jsonl,md}`, `DESLOP-FLAGS.md`, `DESLOP-SUMMARY.json` written; `apply` mode also wrote the edited `.tex`.
- [ ] Every applied edit has a by-line audit record; every substantive concern is a flag, not a silent edit.
- [ ] `ci` mode failed closed on release-blocking slop.
</success_criteria>

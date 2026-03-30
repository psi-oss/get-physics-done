---
template_version: 1
purpose: Formal specification of all valid state transitions in GPD
---

# GPD State Machine Specification

Reference document specifying all valid entity lifecycles, state ownership, and transition triggers across the GPD system.

---

## Continuation Surfaces

Phase 5 separates three layers that were previously blurred together:

1. An append-only execution lineage records what happened.
2. A derived execution head projects the latest resumable execution state for compatibility surfaces.
3. `state.json.continuation.bounded_segment` remains the durable bounded-resume authority.

Current public behavior keeps the canonical continuation decision in `gpd init resume`, which reads `state.json.continuation` first and only consults compatibility surfaces when canonical continuation is missing or incomplete. `session` is a compatibility mirror of the canonical continuation view, and `.continue-here.md` plus `current-execution.json` are projections or advisory compatibility surfaces, not peer authorities.

| Surface | Role | Authority Level | Notes |
|---------|------|-----------------|-------|
| `GPD/state.json` | Storage authority | Authoritative | Machine-readable project state, including canonical `continuation`; `session` is the compatibility mirror of its handoff/machine view |
| `GPD/state.json.bak` | Recovery backup | Fallback only | Used when the primary JSON state is unreadable or unavailable |
| `GPD/STATE.md` | Editable mirror | Reconstruction/edit surface | Human-readable mirror of state; also the final reconstruction source if both JSON files are unavailable |
| Execution lineage | Append-only execution history | Authoritative for provenance only | Records execution/workflow transitions and can rebuild the execution head |
| Derived execution head / `GPD/observability/current-execution.json` | Compatibility mirror | Non-authoritative | Latest execution snapshot rebuilt from lineage; used by legacy consumers and live status surfaces |
| `GPD/phases/.../.continue-here.md` | Temporary handoff artifact | Non-authoritative | Written by `/gpd:pause-work`; may be referenced by canonical continuation, session compatibility, or a live execution snapshot |

The canonical continuation decision comes from `gpd init resume`, not from reading any one of these files in isolation. Canonical `state.json.continuation.bounded_segment` wins first; the derived execution head only fills compatibility gaps when the canonical continuation is incomplete. The temporary handoff artifact and derived execution head remain projections of that decision, not independent sources of truth.

---

## Entity Lifecycles

### Project

```
Created → Active → Paused → Active → Complete → Archived
```

- **Owner surfaces**: `GPD/state.json` (authoritative state, including canonical `continuation`), `GPD/STATE.md` (editable mirror), append-only execution lineage, derived execution head / `GPD/observability/current-execution.json` compatibility mirror, optional `.continue-here.md` temporary handoff projection
- **Created → Active**: `/gpd:new-project` completes (ROADMAP.md exists, STATE.md initialized)
- **Active → Paused**: `/gpd:pause-work` (explicit user action, records canonical continuation and may write `.continue-here.md`)
- **Paused → Active**: `/gpd:resume-work` (restores context from authoritative state plus any handoff projection or derived execution head compatibility mirror)
- **Active → Complete**: All phases reach `complete` status
- **Complete → Archived**: `/gpd:complete-milestone` (archives ROADMAP.md, REQUIREMENTS.md to `milestones/`, updates MILESTONES.md)

### Phase

```
Not started → Discussed → Researched → Planned → Executing → Phase complete → Verified → Complete
                                                      ↓
                                                   Blocked → (resolve) → Executing
```

Disk status values (from `roadmap_analyze`): `no_directory`, `empty`, `discussed`, `researched`, `planned`, `partial`, `complete`

- **Owner files**: ROADMAP.md (phase section, checkbox), STATE.md (Current Phase, Status)
- **Not started → Discussed**: `/gpd:discuss-phase` completes (`{NN}-CONTEXT.md` created in phase directory)
- **Discussed → Researched**: `/gpd:research-phase` completes (`{NN}-RESEARCH.md` created)
- **Not started → Researched**: `/gpd:plan-phase` with research enabled (skips discuss, creates RESEARCH.md directly)
- **Researched → Planned**: `/gpd:plan-phase` completes (`{NN}-{plan}-PLAN.md` files created with wave frontmatter)
- **Planned → Executing**: `/gpd:execute-phase` starts (STATE.md Status set to "Ready to execute", Current Plan set to 1)
- **Executing → Phase complete**: `gpd state advance` when `currentPlan >= totalPlans` (Status set to "Phase complete — ready for verification")
- **Phase complete → Verified**: `/gpd:verify-work` completes (`{NN}-VERIFICATION.md` and/or `{NN}-VALIDATION.md` created)
- **Verified → Complete**: `gpd phase complete {N}` (ROADMAP checkbox marked `[x]`, STATE.md advances to next phase)
- **Executing → Blocked**: Dependency not met or failure encountered (blocker added via `gpd state add-blocker`)
- **Blocked → Executing**: Blocker resolved via `gpd state resolve-blocker`

### Phase Failure States

| State | Triggered By | Recovery |
|-------|-------------|----------|
| Planning failed | /gpd:plan-phase unable to produce valid plan after 3 attempts | Re-run /gpd:research-phase, then retry planning |
| Execution failed | Executor returns unrecoverable failure | See RECOVERY-{plan}.md, option to rollback or resume |
| Verification failed | Verifier finds gaps, user chooses not to override | Run /gpd:plan-phase --gaps to create fix plans |

### Verification Synthesis

Two verification tracks exist:
1. **Automated (verify-phase.md):** Computational checks via gpd-verifier subagent → VERIFICATION.md
2. **Interactive (verify-work.md):** Conversational walkthrough with researcher → detailed check results

**When both are required:** Novel results, publication-bound phases, milestone-final phases
**When automated suffices:** Standard computations with clear benchmarks, intermediate phases
**When interactive suffices:** Qualitative analysis, literature review phases

**Combined pass criteria:** A phase is VERIFIED when:
- Automated verification score ≥ 80% AND no BLOCKER-level gaps, OR
- Interactive verification explicitly approves with documented reasoning

### Plan

```
Pending → In progress → Complete
               ↓
            Failed → (replan) → Pending
```

- **Owner file**: Plan frontmatter (`status` field), SUMMARY.md existence
- **Pending → In progress**: `gpd state advance` sets Current Plan to this plan's number; executor begins work
- **In progress → Complete**: Executor creates matching `{NN}-{plan}-SUMMARY.md` with frontmatter (one-liner, key-files, methods, patterns, decisions, dependency-graph)
- **In progress → Failed**: Executor encounters unrecoverable error; plan marked failed
- **Failed → Pending**: `/gpd:revise-phase` creates replacement plan

### task (within plan)

```
Pending → Active → [Checkpoint] → Active → Complete
                        ↓
                     Blocked
```

- **Owner**: Plan body (## Task N sections), executor agent state
- **Pending → Active**: Executor starts working on the task
- **Active → Checkpoint**: Plan has `interactive: true` in frontmatter; executor pauses for user review
- **Checkpoint → Active**: User approves checkpoint; executor resumes
- **Active → Complete**: Task deliverables produced
- **Active → Blocked**: External dependency or user input needed

### Milestone

```
Active → Audited → Complete → Archived
```

- **Owner files**: ROADMAP.md, MILESTONES.md, `milestones/` archive directory
- **Active → Audited**: `/gpd:audit-milestone` produces `{version}-MILESTONE-AUDIT.md`
- **Audited → Complete**: `/gpd:complete-milestone {version}` (all phases verified)
- **Complete → Archived**: Same command archives ROADMAP.md and REQUIREMENTS.md to `milestones/{version}-*`, creates/appends MILESTONES.md entry

---

## State Ownership Table

| State Field | Owner File | Updated By |
|-------------|-----------|------------|
| Current Phase | STATE.md (`**Current Phase:**`) | `gpd state update`, `gpd phase complete` |
| Current Phase Name | STATE.md (`**Current Phase Name:**`) | `gpd state update`, `gpd phase complete` |
| Total Phases | STATE.md (`**Total Phases:**`) | `gpd phase add/remove` |
| Current Plan | STATE.md (`**Current Plan:**`) | `gpd state advance` |
| Total Plans in Phase | STATE.md (`**Total Plans in Phase:**`) | Workflow orchestrator |
| Status | STATE.md (`**Status:**`) | `gpd state update`, `gpd state advance`, `gpd phase complete` |
| Progress | STATE.md (`**Progress:**`) | `gpd state update-progress` (counts SUMMARY.md files across all phases) |
| Last Activity | STATE.md (`**Last Activity:**`) | Most state-modifying commands |
| Paused At | STATE.md (`**Paused At:**`) | `/gpd:pause-work` (set), `/gpd:resume-work` (clear) |
| Convention Lock | state.json (`convention_lock`) | `gpd convention set/list/check` |
| Intermediate Results | state.json (`intermediate_results`) + STATE.md | `gpd result add` |
| Decisions | STATE.md (Decisions section) + DECISIONS.md | `gpd state add-decision` |
| Blockers | STATE.md (Blockers section) | `gpd state add-blocker/resolve-blocker` |
| Approximations | state.json (`approximations`) | `gpd approximation add/list/check` |
| Propagated Uncertainties | state.json (`propagated_uncertainties`) | `gpd uncertainty add/list` |
| Session Continuity | state.json (`continuation` authority + `session` compatibility mirror) + STATE.md | `gpd state record-session` |
| Performance Metrics | STATE.md (Performance Metrics table) | `gpd state record-metric` |
| Phase Completion | ROADMAP.md (checkbox `[x]`) | `gpd phase complete` |
| Milestone Completion | MILESTONES.md | `gpd milestone complete` |

---

## Transition Triggers

| Transition | Command / Workflow | Files Modified |
|-----------|---------|---------------|
| Project: Created → Active | `/gpd:new-project` | PROJECT.md, ROADMAP.md, STATE.md, state.json, config.json created |
| Project: Active → Paused | `/gpd:pause-work` | state.json + STATE.md (canonical continuation / paused marker), `.continue-here.md` temporary handoff projection may be created |
| Project: Paused → Active | `/gpd:resume-work` | Guided by `gpd init resume` over canonical state, editable mirror, temporary handoff projection, and any derived execution head compatibility mirror; STATE.md paused marker may be cleared and the handoff projection may be consumed |
| Phase: Not started → Discussed | `/gpd:discuss-phase` | `{NN}-CONTEXT.md` created |
| Phase: → Researched | `/gpd:research-phase` or `/gpd:plan-phase` | `{NN}-RESEARCH.md` created |
| Phase: Researched → Planned | `/gpd:plan-phase` | `{NN}-{plan}-PLAN.md` files created, STATE.md updated |
| Phase: Planned → Executing | `/gpd:execute-phase` | STATE.md (Status, Current Plan updated) |
| Plan: advance within phase | `gpd state advance` | STATE.md (Current Plan incremented, Status updated) |
| Plan: complete | Executor creates SUMMARY.md | `{NN}-{plan}-SUMMARY.md` created |
| Phase: → Phase complete | `gpd state advance` (last plan) | STATE.md (Status = "Phase complete — ready for verification") |
| Phase: → Verified | `/gpd:verify-work` | `{NN}-VERIFICATION.md` and/or `{NN}-VALIDATION.md` created |
| Phase: Verified → Complete | `gpd phase complete {N}` | ROADMAP.md (checkbox), STATE.md (next phase), progress updated |
| Milestone: → Audited | `/gpd:audit-milestone` | `{version}-MILESTONE-AUDIT.md` created |
| Milestone: → Archived | `/gpd:complete-milestone` | MILESTONES.md updated, files archived to `milestones/` |
| Decision recorded | `gpd state add-decision` | STATE.md (Decisions section), state.json synced |
| Blocker added | `gpd state add-blocker` | STATE.md (Blockers section), state.json synced |
| Blocker resolved | `gpd state resolve-blocker` | STATE.md (Blockers section), state.json synced |
| Metric recorded | `gpd state record-metric` | STATE.md (Performance Metrics table), state.json synced |
| Progress recalculated | `gpd state update-progress` | STATE.md (Progress bar), state.json synced |
| Session recorded | `gpd state record-session` | STATE.md (Session section), state.json synced through canonical continuation |
| State compacted | `gpd state compact` | STATE.md (trimmed), STATE-ARCHIVE.md (appended) |

---

## Status Vocabulary Mapping

Three status systems coexist. The **disk status** (from `roadmap_analyze`) is the canonical internal representation. ROADMAP.md and STATE.md use display labels.

| Disk Status (canonical) | ROADMAP.md Display | STATE.md Status | Description |
|------------------------|--------------------|-----------------|-------------|
| `no_directory` | Not started | — | Phase directory does not exist |
| `empty` | Not started | — | Phase directory exists but is empty |
| `discussed` | Not started | Ready to plan | Context file exists (`{NN}-CONTEXT.md`) |
| `researched` | Not started | Ready to plan | Research file exists (`{NN}-RESEARCH.md`) |
| `planned` | Not started | Ready to execute | Plan files exist (`{NN}-{plan}-PLAN.md`) |
| `partial` | In progress | Executing | Some summaries exist (execution in progress) |
| `complete` | Complete | Phase complete — ready for verification | All plan summaries exist |
| — | Blocked | Blocked | Blocker added (not a disk status) |
| — | Deferred | — | Phase pushed to later (not a disk status) |

**Notes:**
- Disk statuses are detected by scanning phase directory contents (see `roadmap_analyze`)
- ROADMAP.md statuses are display labels in the Progress table
- STATE.md Status reflects the current phase's workflow position
- "Blocked" and "Deferred" are workflow states, not detected from disk

---

## Dual-Write Consistency

STATE.md and state.json are kept in sync via `sync_state_json()`:

- **state.json** is the authoritative machine-readable storage surface
- **state.json.bak** is the crash-recovery backup if the primary JSON state becomes unreadable or unavailable
- **STATE.md** is the editable human-readable mirror, rendered by `generate_state_markdown()` and still usable as the final reconstruction source when both JSON files are unavailable
- Every write to STATE.md triggers `sync_state_json()` which parses markdown edits and merges them into existing JSON
- Every write to state.json via `save_state_json()` also regenerates STATE.md
- `state_validate` cross-checks position fields between both files
- `state.json.bak` provides crash recovery if state.json becomes corrupt

For continuation specifically:

- `.continue-here.md` is the canonical temporary handoff projection, not the storage authority
- append-only execution lineage is the provenance record, not the bounded-resume authority
- the derived execution head and `GPD/observability/current-execution.json` are compatibility mirrors, not the storage authority
- `gpd init resume` resolves the canonical continuation view with `state.json.continuation` first and compatibility fallback only for legacy or incomplete bounded-segment recovery

---

## Invariants

1. **Phase numbering is sequential** for integer phases (gaps detected by `validate_consistency`)
2. **Decimal phases** (e.g., 06.1, 06.2) are inserted between integer phases and renumbered on removal
3. **Every SUMMARY.md must have a matching PLAN.md** (orphan summaries flagged by consistency check)
4. **Plan wave ordering**: a plan cannot depend on a plan in the same or later wave
5. **No circular dependencies** between plans (validated by topological sort in `validate_waves`)
6. **Convention lock is append-only** in spirit: conventions should not be silently changed
7. **Decisions are append-only** in STATE.md; full log lives in DECISIONS.md
8. **Progress percentage** = (total SUMMARY.md files) / (total PLAN.md files) across all phases

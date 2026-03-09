---
tier: 3
---

# Resolved Known Bugs — GPD Workflows

Last updated: 2026-02-24

## GPD-Specific Issues

### 1. Phase Number Parsing Bugs (parseFloat / .sort())

**Bug:** `parseFloat("2.1.1")` returns `2.1`, silently truncating multi-level decimal phases. This conflates distinct phases (e.g., "2.1" and "2.1.1" both map to 2.1). Similarly, `parseFloat("01.10")` returns `1.1`, conflating phase "01.10" with "01.1". Lexicographic `.sort()` on phase directories also misordered phases when sub-phases reach 10+ (e.g., "02.10" sorts before "02.2").

**Status:** Fixed. All files now use `comparePhaseNumbers` (segment-by-segment comparison) and segment-by-segment `parseInt` normalization. `commands.js` six `.sort()` calls now use `comparePhaseNumbers`. `state.js` `cmdStateCompact` now uses segment-by-segment threshold computation and `comparePhaseNumbers` instead of `parseFloat`.

**Note:** Decimal phase numbers (e.g., 2.1) and multi-level decimals (e.g., 2.1.1) are correctly supported across all phase ordering, directory matching, insert, result, compact, and validation operations.

### 6. Dollar Sign Backreference in State Replace Calls

**Bug:** Several `String.replace()` calls in `state.js` pass user-provided text in the replacement string without escaping `$` characters. In JavaScript, `$1`, `$&`, `$'`, `$$` in replacement strings are interpreted as regex backreferences, not literal text.

**Affected locations (state.js):**
- Line 1350: `cmdStateRecordMetric` — metrics table body includes user-provided phase/duration values
- Line 1470: `cmdStateAddDecision` — decision text from user
- Line 1515: `cmdStateAddBlocker` — blocker text from user
- Line 1604: `cmdStateResolveBlocker` — resolved section body

**Note:** The `stateReplaceField` helper (line 1016) already correctly escapes `$` via `String(newValue).replace(/\$/g, "$$$$")`. The above locations do NOT use this helper.

**Fix:** Use function replacement — `content.replace(pattern, () => replacement)` — which prevents `$` interpretation.

**Status:** Fixed. All 4 locations now use arrow function replacement.

### 7. Phase Remove Cascading Renumber in ROADMAP.md

**Bug:** `cmdPhaseRemove` in `phases.js` renumbered subsequent phase references in ROADMAP.md using a reverse loop (from maxPhase down to removedInt+1). This caused cascading renames: "Phase 8" -> "Phase 7", then the new "Phase 7" was caught again by the "Phase 7" -> "Phase 6" rename, producing incorrect numbering.

**Example:** Removing phase 5 from [1,2,3,4,5,6,7,8] would produce [1,2,3,4,5,5,5] instead of [1,2,3,4,5,6,7].

**Fix:** Changed the loop to forward iteration (removedInt+1 upward), so each phase is renamed exactly once.

**Status:** Fixed.

**Note:** The filesystem directory renaming in the same function uses descending order, which is correct because directories have unique slugs (e.g., "08-numerics" -> "07-numerics" won't conflict with "07-formalism").

### 8. install.js Error Recovery Could Delete Original Data

**Bug:** In `copyWithPathReplacement`, if both the swap rename (tmpDir->destDir) and the restore rename (oldDir->destDir) failed, the outer catch block unconditionally deleted oldDir — which held the only copy of the original installation.

**Fix:** Added a guard: only delete oldDir in the error handler if destDir exists (meaning the original was successfully restored).

**Status:** Fixed.

### 9. Progress Data Loss from Unconditional Delete in syncStateJson

**Bug:** In `syncStateJson` (state.js), the line `delete merged.position.progress` executed unconditionally after attempting a `%` regex match on the progress string. If the regex didn't match (e.g., progress was "Drafting introduction" instead of "50%"), the progress field was silently destroyed.

**Fix:** Moved the `delete merged.position.progress` inside the `if (m)` block so it only fires when the percentage was successfully extracted.

**Status:** Fixed.

### 10. NaN Propagation from Non-Numeric Total Phases/Plans

**Bug:** `parseStateMd` in state.js used `parseInt(value, 10)` on `Total Phases` and `Total Plans in Phase` fields without a NaN guard. If these fields contained non-numeric values like "TBD" or "N/A", `parseInt` returned `NaN`, which propagated into state.json and serialized as `null`, silently losing the original value.

**Fix:** Replaced with `safeParseInt(value, null)` from utils.js, which never returns NaN. Non-numeric values produce `null`.

**Status:** Fixed.

### 11. progress_percent Null-to-Zero Roundtrip Corruption

**Bug:** `renderStateMd` in state.js used `const pct = s.position.progress_percent ?? 0` to render the progress bar. When progress was genuinely unknown (`null`), this defaulted to `0`, rendering `[░░░░░░░░░░] 0%` in STATE.md. On the next parse, this re-read as `progress_percent: 0`, permanently replacing "unknown" with "zero progress".

**Fix:** Only render the progress bar when `pct != null`. Unknown progress now correctly omits the progress bar entirely.

**Status:** Fixed.

### 12. depends-on Hyphenated YAML Key Ignored in Wave Validation

**Bug:** `validateWaves` and `cmdPhasePlanIndex` in phases.js only checked `fm.depends_on` (underscore) from YAML frontmatter, ignoring `fm["depends-on"]` (hyphen). YAML allows both `depends_on:` and `depends-on:` as keys, and the hyphenated form is common. This caused silent dependency loss — plans with `depends-on:` appeared to have no dependencies, potentially executing out of order.

**Note:** The existing code already had this hyphen fallback pattern for `files-modified` vs `files_modified`, but it was missing for `depends-on`.

**Fix:** Added `fm.depends_on || fm["depends-on"]` at both locations (validateWaves and cmdPhasePlanIndex).

**Status:** Fixed.

### 13. gpd CLI Requires Node.js 18+ (Caveat)

**Bug:** The original Node.js CLI used `SharedArrayBuffer` for `Atomics.wait` (used in file locking). This required Node.js 18 or later. Previously had no version check at startup — running with an older Node.js produced a cryptic error.

**Status:** Obsolete. The CLI has been rewritten in Python. The `gpd health` command checks Python version and environment. The Node.js dependency no longer exists.

### 15. State Auto-Compact Implementation Lost During Concurrent Edits

**Bug:** The `cmdStateAutoCompact` function and its `state auto-compact` CLI routing were implemented in state.js/index.js but lost during concurrent edits by multiple agents. The function body and routing were present in one session but absent in the next.

**Status:** Fixed. Auto-compact is wired into transition.md (step `auto_compact_state`, lines 469-491) — calls `state compact` after each phase transition and commits if compaction occurred. Progress.md (line 153) runs a compaction health check and warns when STATE.md exceeds the 150-line target. The `state compact` command uses a 1500-line hard threshold for automatic compaction and a 150-line soft warning threshold.

### 16. validate-return Command Integration

**Bug:** The `gpd validate-return` command was implemented (index.js, frontmatter.js) and initially reported as having no callers.

**Status:** Fixed. `execute-phase.md` (line 264) calls `validate-return` as part of post-execution validation for each agent SUMMARY. The command validates gpd_return YAML envelopes and marks plans as NEEDS_REVIEW if validation fails (non-fatal warning). Additionally, `health.js` checks for gpd_return presence in the system health dashboard.

### 17. verify-conventions Not Integrated Into Inter-Wave Gates (Integration Gap)

**Bug:** The execute-phase workflow uses `convention set` to lock conventions before parallel waves, but does NOT call `verify-conventions` between waves. The verify-conventions command exists and is available via `$gpd-validate-conventions`, but it is not part of the automatic execute-phase flow.

**Status:** Fixed. Inter-wave verification gates (execute-phase.md step 8, lines 302-370) now include convention consistency checks via `gpd convention check --raw` between waves. Gates are controlled by `workflow.verify_between_waves` config ("auto" by default — enabled for deep-theory/review profiles, disabled for others). Also includes dimensional spot-checks on wave SUMMARY.md outputs.

### 19. Workflow Init Error Handling Inconsistency

**Bug:** Many standalone physics workflows used `2>/dev/null` on `gpd init` calls, silently swallowing initialization errors.

**Status:** Fixed. All 42 workflows with init calls now have `if [ $? -ne 0 ]` error checks. Wiring test suite 20 (Init Error Check Coverage) prevents regression.

History:
- Wave 5 (commit 3f16965cb): `2>/dev/null` removed from 6 files, error checks added to 13 files, init step added to literature-review.md, agent failure handling added to write-paper.md
- Wave 7 (commit aa11a2f4e): Error checks added to 6 remaining workflows (audit-milestone, discuss-phase, map-theory, quick, verify-phase, verify-work). Wiring test added.

### 20. Agent Init Error Handling Gap

**Bug:** 4 agent prompt files had `INIT=$(gpd init ...)` commands without error checks. If init fails, the agent would proceed with empty/garbage JSON, causing silent downstream failures.

**Affected agents:** gpd-executor.md, gpd-experiment-designer.md, gpd-plan-checker.md, gpd-planner.md.

**Status:** Fixed. All 4 agents now have `if [ $? -ne 0 ]` error checks after init.

### 21. NaN Guard Gaps in gpd CLI parseInt Calls

**Bug:** Several `parseInt()` calls in gpd CLI can produce NaN that propagates silently:
- CLI argument parsing: `--check-count`, `--limit`, `--last` without value after flag
- `parseStateMd`: `parseInt(...) ?? null` does NOT catch NaN (only catches null/undefined)
- `cmdStateCompact`: non-numeric phase segment produces `"NaN"` string
- `normalizePhaseName`: non-numeric segments produce `"01.NaN"`

**Status:** Fixed. Two new utility functions added to utils.js:
- `safeParseInt(value, defaultVal)` — never returns NaN; returns `defaultVal` for non-numeric input
- `phaseToTopLevel(phase)` — correctly extracts top-level phase number from multi-level strings like "2.1.1" (replaces broken `parseFloat` pattern)

All affected locations updated:
- `parseStateMd` (state.js): `total_phases` and `total_plans_in_phase` use `safeParseInt(value, null)`
- `cmdValidateState` (state.js): phase range check uses `phaseToTopLevel()` instead of `parseFloat()`
- `cmdTemplateFill` (frontmatter.js): wave number uses `safeParseInt(options.wave, 1)`
- CLI args (index.js): `--check-count` and `--limit` use `safeParseInt()` with appropriate defaults

### 22. cost-track Command Not Implemented

**Bug:** `execute-plan.md` referenced `gpd cost-track` which was commented out. Listed in help text but the call was dead code.

**Status:** Fixed. Both `cost-track` and `cost-report` are fully implemented in commands.js with CLI routing in index.js. `cost-track` appends JSONL entries to `.planning/cost-tracking.jsonl`, `cost-report` aggregates by agent/phase with variance analysis. The `execute-plan.md` step `track_cost` has been uncommented to call `cost-track` after each plan execution.

### 23. pre-commit-check Only Used in 2 Workflows

**Bug:** `pre-commit-check` command validates commit artifacts before committing, but originally only `execute-plan.md` and `transition.md` used it.

**Status:** Fixed. Now used in 37 out of 59 workflow files. The remaining 22 workflows are read-only (help, show-phase, settings, progress, etc.) or delegate commits to sub-workflows. Every workflow that performs `git commit` now calls `pre-commit-check` before committing.

### 26. derive-equation.md Bypasses All Convention Defense Layers

**Bug:** The standalone `$gpd-derive-equation` workflow had no convention lock verification, no ASSERT_CONVENTION requirement, and no cross-phase consistency check. Derivations performed via this workflow bypassed L1, L2, L3, L4, and L6 entirely.

**Status:** Fixed. derive-equation.md now has full convention defense coverage:
- **Pre-step:** `gpd init phase-op --include state,config` loads convention lock + `convention check --raw` verifies consistency
- **Step 1b:** 5-point checklist (metric, Fourier, normalization, coupling, renormalization scheme) with hard STOP on mismatch. ASSERT_CONVENTION template included in conventions block.
- **Step 3e:** Cross-phase consistency check — verifies ASSERT_CONVENTION lines match across phases, shared symbols have same definitions, and approximation regimes are compatible before combining results.
- **Step 5 template:** ASSERT_CONVENTION comment included in the derivation document template so all output files carry machine-readable convention assertions.
- **Success criteria:** Convention lock verification, ASSERT_CONVENTION inclusion, and cross-phase consistency are now required checkboxes.

### 27. executor-completion.md Used Wrong Return Envelope Key

**Bug:** `executor-completion.md` used `return:` as the YAML key for the structured return envelope (line 240), while `agent-infrastructure.md` and the executor agent prompt itself use `gpd_return:`. The `validate-return` command regex searches for `gpd_return:\s*\n`, so envelopes keyed as `return:` would silently pass validation failure (reported as "no gpd_return block found").

**Impact:** Executors loading executor-completion.md as their SUMMARY template reference could produce return envelopes that `validate-return` fails to parse, triggering spurious NEEDS_REVIEW warnings in execute-phase.md.

**Status:** Fixed. Changed `return:` to `gpd_return:` in executor-completion.md. Also reordered fields to put the 4 base fields (status, files_written, issues, next_actions) first, matching agent-infrastructure.md. Wiring test added to prevent regression (suite 27: "executor-completion.md: uses gpd_return key").

### 28. gpd-debugger Used Raw Git Commands Instead of gpd CLI commit

**Bug:** The gpd-debugger agent prompt had raw `git add` + `git commit -m` commands for committing correction files and resolved debugging session docs (lines 1563-1577). This bypassed the pre-commit validation that `gpd CLI commit` provides (state.json NaN checks, frontmatter validation, ASSERT_CONVENTION consistency).

**Impact:** Debugger corrections could be committed without pre-commit validation, potentially introducing malformed state or inconsistent conventions. Per agent-infrastructure.md, the debugger is one of only 3 agents authorized to commit directly, and all 3 must use `gpd CLI commit`.

**Status:** Fixed. Both commit points in the debugger (correction commit and session docs commit) now use `gpd CLI commit --files`. Wiring test added (suite 26: "no raw git commit bypassing pre-commit validation").

### 29. gpd-verifier Missing "Spawned By" Documentation

**Bug:** The gpd-verifier agent prompt had no documentation about which orchestrators spawn it, unlike all other 16 agents which document their spawning context.

**Status:** Fixed. Added spawning documentation: `$gpd-execute-phase` (automatic post-phase verification), `$gpd-execute-phase --gaps-only` (re-verification after gap closure), `$gpd-verify-work` (standalone), `$gpd-regression-check` (re-verify truths). Wiring test added (suite 25: "documents spawning context").

### GPD Bug 28 (originally under Platform-Specific). ASSERT_CONVENTION Metric Signature Equivalence Not Normalized

**Bug:** The pre-commit-check L3 convention verification compared ASSERT_CONVENTION values against the convention_lock using exact string comparison. Physicists naturally write metric signatures in multiple equivalent forms: `(+,-,-,-)`, `mostly_minus`, `+---` all mean the same thing. If a user set `convention set metric_signature "(+,-,-,-)"` but wrote `ASSERT_CONVENTION: metric_signature=mostly_minus`, the pre-commit check would falsely report a convention mismatch, even though both values refer to the same physical convention.

**Impact:** False-positive convention mismatch errors that could block commits or trigger unnecessary NEEDS_REVIEW warnings. Physicists who mix formats (common when copying from different textbooks) would face spurious errors.

**Status:** Fixed. Added `normalizeConventionValue()` in commands.js that maps equivalent metric signature representations to canonical forms before comparison:
- `(+,-,-,-)`, `+---` -> `mostly_minus`
- `(-,+,+,+)`, `-+++` -> `mostly_plus`
- `(+,+,+,+)`, `++++` -> `euclidean`

Both the lock value and the asserted value are normalized before comparison, so any equivalent representation matches correctly. 4 new tests verify the normalization (L3 convention mismatch detection suite).

---

## Recent Structural Improvements (2026-02-22/23 Session)

The following improvements were made during a comprehensive audit and hardening session:

**New CLI Commands:**
- `gpd state validate` — 11-check validation between STATE.md and state.json
- `gpd convention check` — convention lock vs CONVENTIONS.md consistency
- `gpd trace start/stop/log/show` — execution trace logging for debugging
- `gpd cost-estimate` — token budget estimation
- `gpd cost-track` — post-execution token tracking (JSONL-based)
- `gpd cost-report` — cost aggregation by agent/phase with variance analysis
- `gpd dependency-graph` — phase dependency visualization (mermaid/JSON)
- `gpd validate-return` — validates gpd_return YAML envelope from agent output
- `gpd health` — comprehensive environment and project health checks

**Agent Prompt Improvements:**
- All 17 agents include context pressure monitoring (GREEN/YELLOW/ORANGE/RED thresholds with per-agent RED calibration)
- Convention Loading Protocol standardized in agent-infrastructure.md (canonical source: state.json convention_lock)
- ASSERT_CONVENTION enforcement added to shared-protocols.md
- gpd_return envelope required in all agents with standardized 4 base fields (status, files_written, issues, next_actions)
- Cross-project pattern library wired into 4 key agents (planner, executor, verifier, debugger) via gpd CLI pattern commands

**Workflow Hardening:**
- execute-phase.md: classifyHandoffIfNeeded failure handling, inter-wave verification gates
- transition.md: state update-progress, convention consistency checks
- progress.md: health check integration, auto-compact dry-run
- pause-work/resume-work: enhanced session continuity

**Wiring Test Expansion:**
- 707 wiring tests covering gpd_return envelope, workflow spawning, config cross-references, pattern library integration

---

## Resolved Platform-Specific Bugs

### Platform-Specific Runtime Bugs

These bugs affect specific AI agents. The installer handles most translation automatically, but edge cases may exist.

#### P1. No Subagent Spawning (Some Runtimes)

**Bug:** Some runtimes do not provide a subagent spawning mechanism (equivalent to Task()). All GPD workflows that spawn subagents (execute-phase, plan-phase, new-project, literature-review, write-paper) fall back to sequential in-context execution on these platforms.

**Impact:** No parallel agent execution. All work runs sequentially in the main context window. Context pressure builds faster. Long research projects may hit context limits before completion.

**Workaround:** Use `$gpd-quick` for individual tasks. Break large projects into smaller milestones. Use `$gpd-pause-work` proactively when context exceeds 50%.

#### P2. Command Syntax Differences

**Bug:** Different runtimes use different command invocation syntax (slash commands vs dollar-sign skills vs other formats). The `$ARGUMENTS` variable behavior is platform-dependent.

**Status:** Monitoring. The installer rewrites command files for each runtime's format. Report issues if argument parsing fails.

#### P3. Skill Invocation Syntax Mapping

**Bug:** Some runtimes use different skill invocation syntax than the source format. The installer generates runtime-specific skill files, but the mapping may have edge cases.

**Status:** Monitoring. The installer handles the format conversion. Report issues if specific commands fail.

#### P4. No @ File References (Some Runtimes)

**Bug:** Some runtimes do not support `@file.md` references in prompts. All file content must be loaded via explicit Read tool calls.

**Impact:** Similar to bug #2 (@ references in Task prompts), but applies to ALL file references, not just subagent prompts.

**Workaround:** GPD workflows use explicit Read instructions. No user action needed.

#### P5. Tool Name Mapping

**Bug:** Different runtimes use different tool names for the same operations (e.g., file reading, shell execution). The installer rewrites tool references, but edge cases may exist where a workflow references a tool name that does not have an equivalent on the target runtime.

**Status:** Monitoring. Report unmapped tool names if workflows fail with "unknown tool" errors.

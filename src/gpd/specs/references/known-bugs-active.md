---
tier: 2
---

# Active Known Bugs Affecting GPD Workflows

Last updated: 2026-02-24

## GPD-Specific Issues

### 2. State Dual-Write Consistency

**Caveat:** STATE.md and state.json can drift out of sync when one is updated without the other. The state module writes both, but manual edits to STATE.md (common during debugging) leave state.json stale.

**Status:** Improved. The `gpd state validate` command now performs 11 cross-checks between STATE.md and state.json including: field sync (phase, plan, total counts), NaN detection, schema completeness, status vocabulary validation, phase ID format, phase range bounds, result ID uniqueness, and dependency validity. A state-json-schema template documents the full schema. The `$gpd-sync-state` command provides reconciliation when drift is detected. However, the dual-write architecture itself remains — full resolution would require making STATE.md a generated read-only view of state.json.

**Workaround:** Run `gpd state validate` to detect drift. After manually editing STATE.md, delete `state.json` so it regenerates on the next `gpd state` command (the fallback parser in `load_state_json` reconstructs it from STATE.md). When reading state, prefer `gpd state load` which reads from the canonical source.

### 3. Convention Source-of-Truth Multiplicity

**Caveat:** Conventions can be declared in multiple places: STATE.md `convention_lock`, PLAN.md frontmatter `conventions`, per-derivation file headers, and CONVENTIONS.md.

**Status:** Substantially resolved. Multiple layers of enforcement now exist:
- **Single source of truth:** `state.json convention_lock` is canonical (documented in agent-infrastructure.md Convention Loading Protocol)
- **Convention Loading Protocol:** All equation-handling agents reference agent-infrastructure.md Convention Loading Protocol (canonical source: `state.json convention_lock` via `gpd convention list`)
- **ASSERT_CONVENTION enforcement:** Derivation files include machine-readable convention assertions checked by executors and verifiers (documented in shared-protocols.md)
- **Convention check command:** `gpd convention check` reports which convention lock fields are set vs missing (completeness check, not lock-vs-CONVENTIONS.md consistency)
- **Convention diff command:** `gpd convention diff` compares conventions across phases
- **Agent convention loading:** All 16 equation-handling agents reference "agent-infrastructure.md Convention Loading Protocol" (7 core agents `@`-include it, 9 others reference it on demand)
- **Context pressure monitoring:** All 17 agents have context pressure thresholds (per-agent RED calibration: 60-75%)

**Remaining:** No automated pre-commit hook that validates convention consistency. The gpd-consistency-checker agent verifies cross-phase consistency but only runs on demand (via `$gpd-validate-conventions` or end-of-phase verification).

### 4. Context Window Compression Artifacts

**Bug:** When the runtime compresses prior messages approaching context limits, formatting and structure may be lost. This can affect derivation continuity when long equation chains or structured convention tables span multiple messages.

**Symptoms:**
- LaTeX equations truncated or reformatted after compression
- Convention tables lose alignment or columns
- Multi-step derivation chains lose intermediate steps
- Structured frontmatter (YAML) may be garbled

**Status:** Mitigated (platform issue — cannot fully fix). All 17 agents now include context pressure self-measurement with recall-based tests (convention recall, equation recall). The 4-level context pressure protocol (GREEN/YELLOW/ORANGE/RED) is enforced in agent-infrastructure.md with specific thresholds and actions. Context budget guidelines in context-budget.md provide per-workflow token budgets and segmentation strategies.

**Workaround:** Persist critical derivation state to files (DERIVATION-STATE.md, state.json) rather than relying on in-context message history. The pause-work workflow handles session continuity. Use `$gpd-pause-work` proactively when context exceeds 60%. The `context_pressure` field in `gpd_return` envelopes signals the orchestrator to spawn continuation agents.

### 5. Git Tag Accumulation from Failed Plans

**Bug:** Checkpoint tags created during failed or abandoned plan executions are never cleaned up. Over multiple sessions, this creates tag pollution in the git repository.

**Symptoms:**
- `git tag -l` shows many `gpd-checkpoint/*` tags from old sessions
- Tags reference commits on abandoned branches or deleted work
- Tag list grows unbounded across sessions

**Workaround:** Periodically clean up stale checkpoint tags manually:

```bash
# List GPD checkpoint tags older than 7 days
git tag -l 'gpd-checkpoint/*' | while read tag; do
  date=$(git log -1 --format=%ai "$tag" 2>/dev/null)
  echo "$tag  $date"
done

# Remove specific stale tags
git tag -d gpd-checkpoint/old-tag-name
```

### 14. Concurrent Agent File Edit Conflicts

**Bug:** When multiple agents (spawned via Task tool in parallel) edit the same files, later writes silently overwrite earlier changes. There is no file locking across subagents.

**Symptoms:**
- Agent A edits section X of a shared file, agent B edits section Y
- If agent B uses full-file Write (not targeted Edit), agent A's changes are lost
- No error is raised — the last writer wins silently
- Past sessions experienced multiple instances of lost edits on shared files (agent-infrastructure.md and core module files)

**Workaround:** Use targeted `Edit` (string replacement) instead of full-file `Write` whenever possible. Read the file immediately before writing to capture recent teammate changes. Orchestrators should avoid assigning overlapping file edits to parallel agents.

### 18. Reference Files — Content Duplicated Inline and as Extracted Files

**Bug:** Four reference files were created to extract content from agent prompts. The content exists both inline in agent prompts AND as separate reference files. All four files ARE correctly cross-referenced by agents (not orphaned):

- `references/executor-deviation-rules.md` — Referenced by gpd-executor.md (lines 458, 831) as load-on-demand
- `references/executor-task-checkpoints.md` — Referenced by gpd-executor.md (lines 616, 832) as load-on-demand
- `references/verification-hierarchy-mapping.md` — Referenced by gpd-verifier.md (line 360), gpd-plan-checker.md (line 64), gpd-consistency-checker.md (line 106)
- `references/figure-generation-templates.md` — Referenced by gpd-paper-writer.md (lines 60, 651)

**Status:** Partially resolved. The files are correctly cross-referenced. The inline summaries in agent prompts are intentional (agents load the full files on demand). The duplication is by design: inline summaries for quick reference, extracted files for full detail.

### 24. Verification Gap Analysis Coverage Matrix Was Overstated

**Bug:** The original `verification-gap-analysis.md` coverage matrix overstated multi-layer coverage for 16+ error classes by crediting L4 (inter-wave gates) with partial detection of error types that L4 does not actually check. L4 only performs convention consistency + dimensional spot-check, but was credited for catching asymptotic expansion errors (#5), intensive/extensive confusion (#8), tensor decomposition errors (#10), anomaly errors (#42), and others.

**Impact:** The original analysis reported 25/51 (49%) single-layer coverage. Corrected analysis: **40/51 (78%) single-layer coverage**. The system is significantly more vulnerable than previously documented.

**Status:** Fixed (documentation). The coverage matrix in `verification-gap-analysis.md` has been corrected with accurate implementation-verified coverage claims. New columns added for L0 (plan-checker) and L2b (executor self-critique) which were missing from the original model.

### 25. Exploratory Profile Verification Void

**Bug:** In exploratory profile, the verifier originally ran only checks 5.1, 5.2, 5.3, 5.10 (4 of 15 checks). This meant 36 of 51 error classes lost their ONLY defense layer.

**Status:** Fixed. The exploratory profile now runs a 7-check floor: 5.1 (dimensional), 5.2 (spot-check), 5.3 (limiting cases), 5.6 (symmetry), 5.7 (conservation), 5.8 (math consistency), 5.10 (literature). Confirmed in `verifier-profile-checks.md` line 225 and `verification-hierarchy-mapping.md` line 133. The gap is reduced from 36 to ~16 unprotected error classes (those requiring 5.9, 5.11-5.15).

---

## Platform-Specific Bugs

### Runtime-Specific

### 1. classifyHandoffIfNeeded False Failure

**Bug:** When a subagent spawned via `Task()` completes all its work, the runtime sometimes reports it as "failed" with the error `classifyHandoffIfNeeded is not defined`. This is a runtime bug in the completion handler that fires AFTER all tool calls have already finished successfully.

**Symptoms:**
- Agent appears to have failed
- Error message contains `classifyHandoffIfNeeded is not defined`
- But the agent actually completed its work (files written, commits made)

**Workaround — spot-check before treating as failure:**

Before treating a subagent result as a failure, run these spot-checks:

1. Check if the expected output file exists (e.g., SUMMARY.md, PLAN.md, RESEARCH.md)
2. Check `git log --oneline --grep="{phase}-{plan}"` returns >= 1 commit (if commits expected)
3. Check for `## Self-Check: FAILED` or `## Validation: FAILED` markers (if applicable)

**Decision logic:**

| Spot-checks | Action |
|-------------|--------|
| All pass | Treat as **successful** — the error is cosmetic |
| Any fail | Treat as **real failure** — route to failure handling |

### 2. @-Reference Behavior in Task() Prompts

**Bug:** `@` references (e.g., `@{GPD_INSTALL_DIR}/workflows/execute-plan.md`) inside `Task()` prompt strings do NOT load files for subagents. The `@` syntax only works in the main conversation context, not across Task() boundaries.

**Symptoms:**
- Subagent does not have access to referenced file contents
- Agent may hallucinate or skip instructions from the referenced file
- No error is raised — the reference is silently ignored

**Workaround — use explicit Read instructions:**

Instead of `@` references, instruct the subagent to read files explicitly:

```
# WRONG — subagent won't see the file contents
Task(prompt="
  @{GPD_INSTALL_DIR}/workflows/execute-plan.md
  Execute the plan...
")

# CORRECT — subagent reads the file itself
Task(prompt="
  First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

  <files_to_read>
  Read these files at execution start using the Read tool:
  - Plan: {phase_dir}/{plan_file}
  - State: .planning/STATE.md
  </files_to_read>

  Execute the plan...
")
```

**Alternative — pass file contents inline:**

For small files, load the content before spawning and embed it in the prompt:

```bash
CONTENT=$(cat {GPD_INSTALL_DIR}/references/checkpoints.md)
```

Then include `${CONTENT}` directly in the Task() prompt string. This is used by plan-phase.md (step 7) which loads all file contents via `--include` and passes them inline.

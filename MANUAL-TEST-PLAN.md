# GPD Manual Test Plan — Complete Step-by-Step

## Prerequisites

```bash
uv pip install -e .
```

Verify:
```bash
gpd version
gpd --help
```

---

## PHASE 1: Standalone Commands (no project needed)

These commands work without any `.planning/` directory.

### 1.1 Version & Help

```bash
gpd version
gpd --help
gpd state --help
gpd phase --help
gpd convention --help
gpd json --help
```

**Check:** Version prints. Help lists all subgroups. Each subgroup help lists its subcommands.

### 1.2 Pure Utilities

```bash
gpd timestamp
gpd timestamp date
gpd timestamp filename
gpd timestamp full
gpd slug "Hello World Test"
gpd slug "Señor García's résumé"
gpd verify-path /tmp
gpd verify-path /nonexistent/path
```

**Check:** Three timestamp formats. Slug is URL-safe lowercase. Existing path returns ok. Missing path exits non-zero.

### 1.3 JSON Utilities (stdin-based)

```bash
echo '{"a":{"b":42}}' | gpd json get a.b
echo '{"a":{"b":42}}' | gpd json get a.b --raw
echo '{"x":1,"y":2}' | gpd json keys .
echo '[{"n":"a"},{"n":"b"}]' | gpd json list .
echo '[{"n":"a","v":1},{"n":"b","v":2}]' | gpd json pluck . n
echo '{"a":[1,2],"b":[3]}' | gpd json sum-lengths a b

# File-based
echo '{"x":1}' > /tmp/j1.json && echo '{"y":2}' > /tmp/j2.json
gpd json merge-files /tmp/j1.json /tmp/j2.json --out /tmp/merged.json
cat /tmp/merged.json

gpd json set --file /tmp/j1.json --path "z" --value "99"
cat /tmp/j1.json

# Edge cases
echo '{}' | gpd json get missing --default "fallback"
echo 'not json' | gpd json get x         # should error gracefully
```

**Check:** All return correct values. `--raw` returns JSON. `merge-files` combines. `set` modifies file. Bad JSON errors cleanly.

### 1.4 Doctor (installation health)

```bash
gpd doctor
gpd doctor --raw
```

**Check:** 8 checks all pass (Specs Structure, Agent Files, Key References, Workflows, Templates, Python Version, Package Imports, Skill Files). `--raw` returns JSON with `overall: "ok"`.

### 1.5 Model Resolution

```bash
gpd resolve-model gpd-executor
gpd resolve-model gpd-planner
gpd resolve-model gpd-verifier
gpd resolve-model gpd-project-researcher
gpd resolve-model nonexistent-agent
```

**Check:** Each returns a tier (tier-1/2/3). Nonexistent agent errors.

---

## PHASE 2: Installation on All Platforms

### 2.1 Claude Code (local)

```bash
mkdir -p /tmp/gpd-test-cc && cd /tmp/gpd-test-cc && git init
gpd install claude-code --local
```

**Check:**
- `.claude/commands/gpd/` has 58 `.md` files
- `.claude/agents/` has 17 `gpd-*.md` files
- `.claude/get-physics-done/{references,templates,workflows}` exist
- `.claude/get-physics-done/VERSION` matches `gpd version`
- `.claude/hooks/` has 4 `.py` files
- `.claude/gpd-file-manifest.json` exists
- `.claude/settings.json` has `statusLine` and `SessionStart` hook
- No `{GPD_INSTALL_DIR}` or `{GPD_AGENTS_DIR}` placeholders remain in any file:
  ```bash
  grep -r '{GPD_INSTALL_DIR}' .claude/ || echo "PASS: no placeholders"
  grep -r '{GPD_AGENTS_DIR}' .claude/ || echo "PASS: no placeholders"
  ```

### 2.2 Claude Code (global)

```bash
gpd install claude-code --global --target-dir /tmp/gpd-test-cc-global
ls /tmp/gpd-test-cc-global/commands/gpd/ | wc -l   # 58
ls /tmp/gpd-test-cc-global/agents/gpd-*.md | wc -l  # 17
```

### 2.3 Codex

```bash
mkdir -p /tmp/gpd-test-codex && cd /tmp/gpd-test-codex && git init
gpd install codex --local
```

**Check:**
- `.codex/` directory created
- SKILL.md format (directories, not flat files)
- `$gpd-` prefix in skill names
- `@` includes expanded (no raw `@{GPD_INSTALL_DIR}` left)

### 2.4 Gemini

```bash
mkdir -p /tmp/gpd-test-gemini && cd /tmp/gpd-test-gemini && git init
gpd install gemini --local
```

**Check:**
- `.gemini/` directory created
- `.toml` command files (not `.md`)
- No `<sub>` tags remain
- `settings.json` has `experimental.enableAgents`

### 2.5 OpenCode

```bash
mkdir -p /tmp/gpd-test-oc && cd /tmp/gpd-test-oc && git init
gpd install opencode --local --target-dir /tmp/gpd-test-oc/.opencode
```

**Check:**
- Flat `gpd-*.md` files (not in subdirectories)
- Colors converted to hex (no raw color names like "blue")
- No `name:` field in frontmatter

### 2.6 Idempotent Reinstall

```bash
cd /tmp/gpd-test-cc
gpd install claude-code --local   # Second install over existing
```

**Check:** No errors. File counts unchanged. Stale agents removed if any existed.

### 2.7 Uninstall

```bash
cd /tmp/gpd-test-cc
gpd uninstall claude-code --local
```

**Check:** GPD files removed. `.claude/` may remain (if user has other config), but GPD content gone.

### 2.8 Cross-Platform Parity

```bash
# From repo root, run existing parity test
uv run pytest tests/test_parity.py -v
```

**Check:** All parity assertions pass — every command available on every platform.

---

## PHASE 3: Project Scaffolding & State Management

### 3.1 Create Test Project

```bash
mkdir -p /tmp/gpd-project && cd /tmp/gpd-project && git init
mkdir -p .planning/phases/01-test-phase

# Create minimal PROJECT.md
cat > .planning/PROJECT.md << 'EOF'
# Test Research Project
## Core Research Question
What is the ground state energy of the 1D Hubbard model at half-filling?
EOF

# Create minimal ROADMAP.md
cat > .planning/ROADMAP.md << 'EOF'
# Research Roadmap
## Milestone: v1.0 — Initial Investigation
### Phase 01: Literature Review
- Survey existing results for 1D Hubbard model
### Phase 02: Analytical Framework
- Set up Bethe ansatz equations
EOF

# Create minimal STATE.md
cat > .planning/STATE.md << 'EOF'
# Research State
## Project Reference
See: .planning/PROJECT.md
**Core research question:** Ground state of 1D Hubbard model
**Current focus:** Phase 01
## Current Position
**Current Phase:** 1
**Current Phase Name:** Literature Review
**Total Phases:** 2
**Current Plan:** 1
**Total Plans in Phase:** 1
**Status:** Ready to plan
**Last Activity:** 2025-01-01
**Last Activity Description:** Project initialized
**Progress:** [░░░░░░░░░░] 0%
## Active Calculations
None yet.
## Intermediate Results
None yet.
## Open Questions
None yet.
## Performance Metrics
| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |
## Accumulated Context
### Decisions
None yet.
### Active Approximations
None yet.
### Blockers/Concerns
None yet.
## Session Continuity
**Last session:** —
**Stopped at:** —
**Resume file:** None
EOF

# Initialize state.json
cat > .planning/state.json << 'EOF'
{
  "current_phase": "01",
  "current_plan": 1,
  "total_phases": 2,
  "status": "Ready to plan",
  "convention_lock": {},
  "intermediate_results": [],
  "approximations": [],
  "propagated_uncertainties": [],
  "open_questions": [],
  "active_calculations": [],
  "decisions": [],
  "blockers": [],
  "metrics": [],
  "sessions": []
}
EOF
```

### 3.2 State Load & Get

```bash
cd /tmp/gpd-project
gpd state load
gpd state load --raw
gpd state get
gpd state get "current_phase"
gpd state get "status"
gpd state get "nonexistent_section"   # should handle gracefully
```

**Check:** Load shows full state. Get returns specific fields. `--raw` returns JSON.

### 3.3 State Update & Patch

```bash
gpd state update status "Planning in progress"
gpd state get "status"                # should show "Planning in progress"

gpd state patch status "Executing" current_plan 2
gpd state get "status"                # "Executing"
gpd state get "current_plan"          # 2
```

**Check:** Fields update in both STATE.md and state.json.

### 3.4 State Validate

```bash
gpd state validate
gpd state validate --raw
```

**Check:** Should pass (or show specific validation issues). Exit code 0 if valid, 1 if not.

### 3.5 Decisions & Blockers

```bash
gpd state add-decision --phase 01 --summary "Use Bethe ansatz" --rationale "Exact solution available in 1D"
gpd state add-decision --phase 01 --summary "Focus on half-filling"

gpd state add-blocker --text "Need to verify integral convergence"
gpd state add-blocker --text "Missing reference for finite-size scaling"

gpd state resolve-blocker --text "Need to verify integral convergence"
```

**Check:** Decisions appear in state. Blocker added then resolved. `state load` reflects changes.

### 3.6 Metrics & Progress

```bash
gpd state record-metric --phase 01 --plan 01 --duration "5m" --tasks 3 --files 2
gpd state update-progress
gpd progress json
gpd progress bar
gpd progress table
```

**Check:** Metric recorded. Progress calculates. All three formats render.

### 3.7 Session Recording

```bash
gpd state record-session --stopped-at "Finished literature review"
gpd state snapshot
gpd state snapshot --raw
```

**Check:** Session recorded with timestamp. Snapshot returns read-only summary.

### 3.8 State Compaction

```bash
# Add many decisions to trigger compaction threshold
for i in $(seq 1 25); do
  gpd state add-decision --phase 01 --summary "Decision $i" --rationale "Reason $i"
done

gpd state compact
gpd state load   # should be shorter now
```

**Check:** Old entries archived. STATE.md trimmed.

---

## PHASE 4: Convention System

```bash
cd /tmp/gpd-project
```

### 4.1 Set Conventions

```bash
gpd convention set metric_signature "(-,+,+,+)"
gpd convention set natural_units "hbar=c=1"
gpd convention set fourier_convention "integral dk/(2pi) e^{ikx}"
gpd convention set coordinate_system "Cartesian"
gpd convention set regularization_scheme "Dimensional regularization"

# Test aliases
gpd convention set metric "mostly plus"     # alias for metric_signature

# Test bogus value rejection
gpd convention set metric_signature "not set"  # should warn or reject
```

**Check:** Each convention persists. Aliases resolve. Bogus values handled.

### 4.2 List & Check

```bash
gpd convention list
gpd convention list --raw
gpd convention check
gpd convention check --raw
```

**Check:** List shows all set conventions. Check reports unset core conventions.

### 4.3 Diff

```bash
gpd convention diff
```

**Check:** Shows current state (may show empty diff if no cross-phase differences).

---

## PHASE 5: Results, Approximations, Uncertainties, Questions, Calculations

```bash
cd /tmp/gpd-project
```

### 5.1 Intermediate Results

```bash
gpd result add --id res-0 --equation "E_0 = -4t" --description "Ground state energy" \
  --units energy --validity "U/t << 1" --phase 01

gpd result add --id res-1 --equation "delta_E = 0.1 U^2/t" --description "First correction" \
  --units energy --validity "U/t < 0.5" --phase 01 --depends-on res-0

gpd result list
gpd result list --raw
gpd result list --verified
gpd result list --unverified

gpd result deps res-1          # BFS graph

gpd result verify res-0
gpd result list --verified     # res-0 should appear

gpd result update res-0 --equation "E_0 = -4t + O(U^2)"
```

**Check:** Add works. Dependencies tracked. Verify toggles flag. Update modifies.

### 5.2 Approximations

```bash
gpd approximation add "Weak coupling" --validity-range "U/t << 1" \
  --controlling-param "U/t" --current-value "0.1" --status valid

gpd approximation add "Large system" --validity-range "L >> 1" \
  --controlling-param "L" --current-value "64" --status valid

gpd approximation list
gpd approximation check        # validates all approximations
```

**Check:** Both listed. Check reports validity status.

### 5.3 Uncertainties

```bash
gpd uncertainty add "T_c" --value "0.893" --uncertainty "0.005" --phase 01 --method "finite-size scaling"
gpd uncertainty list
```

### 5.4 Questions

```bash
gpd question add "Is the sign of the 2-loop correction scheme-dependent?"
gpd question add "Why does scaling collapse degrade below L=32?"
gpd question list
gpd question resolve "Is the sign of the 2-loop correction scheme-dependent?"
gpd question list   # should show only 1 remaining
```

### 5.5 Calculations

```bash
gpd calculation add "Evaluate 2-loop self-energy diagrams"
gpd calculation add "Monte Carlo at T=0.85"
gpd calculation list
gpd calculation complete "Monte Carlo at T=0.85"
gpd calculation list   # MC should be gone or marked complete
```

---

## PHASE 6: Phase Lifecycle

```bash
cd /tmp/gpd-project
```

### 6.1 List & Find

```bash
gpd phase list
gpd phase find 01
gpd phase find 99   # should error or report not found
```

### 6.2 Add & Insert

```bash
gpd phase add "Numerical Verification"
gpd phase list     # should show 3 phases now

gpd phase insert 01 "Extended Literature Review"
gpd phase list     # should show 4 phases, new one after 01

gpd phase next-decimal 01    # should return 01.1 or similar
```

### 6.3 Create Plan Files & Wave Validation

```bash
# Create a plan file in phase 01
cat > .planning/phases/01-test-phase/PLAN-01-survey.md << 'EOF'
---
wave: 1
status: incomplete
---
# Plan: Literature Survey
Survey existing Bethe ansatz results.
EOF

cat > .planning/phases/01-test-phase/PLAN-02-gaps.md << 'EOF'
---
wave: 2
depends_on: [PLAN-01]
status: incomplete
---
# Plan: Identify Gaps
Identify open questions from the survey.
EOF

gpd phase index 01
gpd phase validate-waves 01
```

**Check:** Index shows 2 plans in 2 waves. Wave validation passes (wave 2 depends on wave 1).

### 6.4 Complete & Remove

```bash
# Create a SUMMARY for the plan
cat > .planning/phases/01-test-phase/SUMMARY-01-survey.md << 'EOF'
---
status: complete
phase: "01"
plan: "01"
provides: [bethe-ansatz-overview]
---
# Summary: Literature Survey
Found 15 relevant papers.

```gpd_return
status: done
phase: "01"
plan: "01"
tasks_completed: 3
tasks_total: 3
```
EOF

gpd phase complete 01         # may fail if not all plans complete — that's OK to test
gpd phase remove 03 --force   # remove the "Numerical Verification" phase added earlier
gpd phase list
```

### 6.5 Roadmap Analysis

```bash
gpd roadmap analyze
gpd roadmap analyze --raw
gpd roadmap get-phase 01
gpd roadmap get-phase 02
```

---

## PHASE 7: Frontmatter & Verification

```bash
cd /tmp/gpd-project
```

### 7.1 Frontmatter CRUD

```bash
gpd frontmatter get .planning/phases/01-test-phase/PLAN-01-survey.md
gpd frontmatter get .planning/phases/01-test-phase/PLAN-01-survey.md --field wave

gpd frontmatter set .planning/phases/01-test-phase/PLAN-01-survey.md --field status --value complete
gpd frontmatter get .planning/phases/01-test-phase/PLAN-01-survey.md --field status  # "complete"

gpd frontmatter merge .planning/phases/01-test-phase/PLAN-01-survey.md --data '{"tags":["survey","literature"]}'
gpd frontmatter get .planning/phases/01-test-phase/PLAN-01-survey.md   # should show tags

gpd frontmatter validate .planning/phases/01-test-phase/PLAN-01-survey.md --schema plan
```

### 7.2 Verification Suite

```bash
gpd verify summary .planning/phases/01-test-phase/SUMMARY-01-survey.md
gpd verify plan .planning/phases/01-test-phase/PLAN-01-survey.md
gpd verify phase 01
gpd verify artifacts .planning/phases/01-test-phase/PLAN-01-survey.md
```

### 7.3 Validate Return Block

```bash
gpd validate-return .planning/phases/01-test-phase/SUMMARY-01-survey.md
```

**Check:** Should pass — the gpd_return block has all required fields.

---

## PHASE 8: Query System

```bash
cd /tmp/gpd-project
```

### 8.1 Cross-Phase Search

```bash
gpd query search --provides bethe-ansatz-overview
gpd query search --text "Bethe ansatz"
gpd query search --equation "E_0"
gpd query search --phase-range "01-02"
```

### 8.2 Dependencies & Assumptions

```bash
gpd query deps bethe-ansatz-overview
gpd query assumptions "weak coupling"
```

---

## PHASE 9: Patterns, Trace, Config

### 9.1 Pattern Library

```bash
cd /tmp/gpd-project
export GPD_PATTERNS_ROOT=/tmp/gpd-patterns

gpd pattern init
gpd pattern seed               # 8 bootstrap patterns
gpd pattern list
gpd pattern list --domain qft
gpd pattern list --severity high
gpd pattern search "sign error"
gpd pattern search "Fourier"

gpd pattern add --domain qft --title "Test pattern" --description "A test" \
  --detection "Check signs" --prevention "Double-check" --severity medium
gpd pattern list               # should show 9 patterns
```

### 9.2 Execution Trace

```bash
cd /tmp/gpd-project

gpd trace start 01 01
gpd trace log convention_load --data '{"key":"metric_signature","value":"(-,+,+,+)"}'
gpd trace log checkpoint --data '{"step":"halfway"}'
gpd trace log error --data '{"msg":"test error"}'
gpd trace stop

gpd trace show
gpd trace show --phase 01
gpd trace show --type error
gpd trace show --last 2
```

### 9.3 Configuration

```bash
cd /tmp/gpd-project

gpd config ensure-section      # creates config.json if missing
gpd config get model_profile
gpd config set model_profile deep-theory
gpd config get model_profile   # should be "deep-theory"
gpd config set commit_docs true
gpd config get commit_docs     # should be true
```

---

## PHASE 10: Health, Suggest, Scaffold, History

### 10.1 Health (11 checks)

```bash
cd /tmp/gpd-project

gpd health
gpd health --raw
gpd health --fix              # should auto-fix any fixable issues
```

**Check:** All 11 checks run. Review each: environment, project_structure, state_validity, compaction, roadmap, orphans, convention_lock, plan_frontmatter, latest_return, config, git_status.

### 10.2 Suggest

```bash
gpd suggest
gpd suggest --raw
gpd suggest --limit 3
```

**Check:** Returns prioritized recommendations based on current project state.

### 10.3 Scaffolding

```bash
gpd scaffold context --phase 01
gpd scaffold validation --phase 01
gpd scaffold verification --phase 01
gpd scaffold phase-dir --phase 03 --name "Numerical Verification"
```

**Check:** Files created in correct locations.

### 10.4 History & Summary Extract

```bash
gpd history-digest
gpd summary-extract .planning/phases/01-test-phase/SUMMARY-01-survey.md --field status --field provides
```

### 10.5 Regression Check

```bash
gpd regression-check
gpd regression-check --quick
```

### 10.6 Validate Consistency

```bash
gpd validate consistency
```

---

## PHASE 11: Template System

```bash
cd /tmp/gpd-project

gpd template select .planning/phases/01-test-phase/PLAN-01-survey.md
gpd template fill execute --phase 01 --plan 01 --name "survey" --type execute --wave 1
gpd template fill execute --phase 01 --plan 01 --name "survey" --fields '{"custom":"value"}'
```

---

## PHASE 12: Git Operations

```bash
cd /tmp/gpd-project

# Pre-commit check
gpd pre-commit-check
gpd pre-commit-check --files .planning/phases/01-test-phase/PLAN-01-survey.md

# Commit
git add .planning/
gpd commit "Initial project setup"

# Verify commits
HASH=$(git rev-parse HEAD)
gpd verify commits $HASH
gpd verify commits deadbeef123   # should fail — nonexistent hash
```

---

## PHASE 13: Init Context Commands

These return JSON context for agent workflows. Test that they assemble correctly.

```bash
cd /tmp/gpd-project

gpd init new-project --raw
gpd init new-milestone --raw
gpd init execute-phase 01 --raw
gpd init execute-phase 01 --include state,config,roadmap --raw
gpd init plan-phase 01 --raw
gpd init plan-phase 01 --include state,roadmap --raw
gpd init quick "Calculate ground state energy" --raw
gpd init resume --raw
gpd init verify-work 01 --raw
gpd init progress --raw
gpd init progress --include state,roadmap --raw
gpd init map-theory --raw
gpd init todos --raw
gpd init phase-op 01 --raw
gpd init milestone-op --raw
```

**Check:** Each returns valid JSON with documented keys. No crashes.

---

## PHASE 14: Milestone Lifecycle

```bash
cd /tmp/gpd-project

# Complete the milestone
gpd milestone complete v1.0 --name "Initial Investigation"
```

**Check:** Archives milestone data. May fail if phases aren't complete — that's the correct behavior to verify.

---

## PHASE 15: MCP Servers

Test each of the 7 MCP servers. Use `mcp dev` (from `mcp[cli]`) for interactive testing, or pipe JSON-RPC over stdio.

### 15.1 Conventions Server

```bash
# Start in background
python -m gpd.mcp.servers.conventions_server &
MCP_PID=$!

# Or use mcp dev for interactive testing
mcp dev python -m gpd.mcp.servers.conventions_server
```

**Test tools:**
- `subfield_defaults` with `{"domain": "qft"}` → expect `metric_signature`
- `convention_set` with `{"project_dir": "/tmp/gpd-project", "key": "metric_signature", "value": "(-,+,+,+)"}`
- `convention_lock_status` with `{"project_dir": "/tmp/gpd-project"}`
- `convention_check` with the returned lock
- `convention_diff` with two different locks

```bash
kill $MCP_PID 2>/dev/null
```

### 15.2 Verification Server

```bash
mcp dev python -m gpd.mcp.servers.verification_server
```

**Test tools:**
- `get_checklist` with `{"domain": "qft"}` → expect verification items
- `get_checklist` with `{"domain": "condmat"}`, `{"domain": "statmech"}`
- `dimensional_check` with `{"expressions": ["[M][L]^2[T]^-2 = [M][L]^2[T]^-2"]}`
- `run_check` with `{"check_id": "5.1", "domain": "qft", "artifact_content": "test"}`
- `get_verification_coverage` with `{"error_class_ids": [1,2,3], "active_checks": ["5.1"]}`

### 15.3 Errors Server

```bash
mcp dev python -m gpd.mcp.servers.errors_mcp
```

**Test tools:**
- `list_error_classes` with `{}` → expect count >= 100
- `list_error_classes` with `{"domain": "core"}`
- `get_error_class` with `{"error_id": 1}` through a few IDs
- `check_error_classes` with `{"computation_desc": "perturbative QFT calculation"}`
- `get_detection_strategy` with `{"error_id": 1}`
- `get_traceability` with `{"error_id": 1}`

### 15.4 Protocols Server

```bash
mcp dev python -m gpd.mcp.servers.protocols_server
```

**Test tools:**
- `list_protocols` with `{}` → expect count >= 40
- `get_protocol` with `{"name": "perturbation-theory"}`
- `get_protocol` with `{"name": "renormalization-group"}`
- `route_protocol` with `{"computation_type": "one-loop Feynman diagram evaluation"}`
- `get_protocol_checkpoints` with `{"name": "perturbation-theory"}`

### 15.5 Patterns Server

```bash
mcp dev python -m gpd.mcp.servers.patterns_server
```

**Test tools:**
- `list_domains` → expect 13 domains
- `seed_patterns` → 8 bootstrap patterns
- `lookup_pattern` with `{"domain": "qft"}`
- `lookup_pattern` with `{"keywords": "sign error"}`
- `add_pattern` with full fields
- `promote_pattern` with a pattern ID

### 15.6 State Server

```bash
mcp dev python -m gpd.mcp.servers.state_server
```

**Test tools:**
- `get_state` with `{"project_dir": "/tmp/gpd-project"}`
- `get_phase_info` with `{"project_dir": "/tmp/gpd-project", "phase": "01"}`
- `get_progress` with `{"project_dir": "/tmp/gpd-project"}`
- `validate_state` with `{"project_dir": "/tmp/gpd-project"}`
- `run_health_check` with `{"project_dir": "/tmp/gpd-project"}`
- `get_config` with `{"project_dir": "/tmp/gpd-project"}`
- `advance_plan` with `{"project_dir": "/tmp/gpd-project"}`

### 15.7 Skills Server

```bash
mcp dev python -m gpd.mcp.servers.skills_server
```

**Test tools:**
- `list_skills` with `{}` → expect ~75 skills
- `get_skill` with `{"name": "gpd-execute-phase"}`
- `get_skill` with `{"name": "gpd-new-project"}`
- `route_skill` with `{"task_description": "I need to plan my next research phase"}`
- `get_skill_index` → compact index

---

## PHASE 16: Hooks

### 16.1 Statusline

```bash
cd /tmp/gpd-project
python src/gpd/hooks/statusline.py
```

**Check:** Prints ANSI-formatted status line with model, phase, progress.

### 16.2 Update Check

```bash
python src/gpd/hooks/check_update.py
```

**Check:** Runs silently (background check), writes cache file.

### 16.3 Runtime Detection

```bash
python -c "from gpd.hooks.runtime_detect import detect_active_runtime; print(detect_active_runtime())"
```

### 16.4 Codex Notify

```bash
python src/gpd/hooks/codex_notify.py
```

**Check:** Runs without crash (may do nothing outside Codex).

---

## PHASE 17: Ablation & Feature Flags

```bash
cd /tmp/gpd-project

# Test ablation env vars
GPD_DISABLE_CONVENTIONS=1 gpd convention list   # should be disabled/no-op
GPD_DISABLE_VERIFICATION=1 gpd health           # verification checks skipped

# Test from Python
python -c "
from gpd.core.observability import load_feature_flags, is_enabled
flags = load_feature_flags()
print('conventions:', is_enabled('conventions'))
print('verification:', is_enabled('verification'))
print('patterns:', is_enabled('patterns'))
"

# Ablation presets
python -c "
from gpd.ablations import ABLATION_POINTS, report_ablations
for name, point in ABLATION_POINTS.items():
    print(f'{name}: {point.description}')
print(f'\nTotal ablation points: {len(ABLATION_POINTS)}')
"
```

**Check:** 22 ablation points listed. Env var disables work.

---

## PHASE 18: GPD+ and Pipeline

### 18.1 GPD+ CLI

```bash
gpd+ --version
gpd+ --history              # may be empty on first run
gpd+ --search "test"        # FTS5 search, may return nothing
gpd+ reindex                # rebuild search index
```

### 18.2 Pipeline Discover

```bash
gpd+ pipeline discover "lattice QCD phase transition"
```

**Check:** Returns tool selection with domains, confidence, reasoning.

### 18.3 Pipeline Plan

```bash
# Requires tools file from discover step
gpd+ pipeline plan --query "lattice QCD phase transition" \
  --tools-file /path/to/tools.json --work-dir /tmp/gpd-pipeline
```

### 18.4 Pipeline Execute, Paper, Compile

```bash
# These require prior steps and may need Modal credentials
gpd+ pipeline execute --plan-file /tmp/gpd-pipeline/plan.json \
  --milestone M1 --work-dir /tmp/gpd-pipeline

gpd+ pipeline paper --work-dir /tmp/gpd-pipeline \
  --title "Test Paper" --abstract "Test abstract" --journal prl

gpd+ pipeline compile --paper-dir /tmp/gpd-pipeline/paper
```

### 18.5 Fix MCPs

```bash
gpd+ pipeline fix-mcps    # tests Modal connectivity + MCP health
```

---

## PHASE 19: End-to-End Workflow in Claude Code

This tests the actual agent workflows. Requires Claude Code installed with GPD.

### 19.1 Setup

```bash
mkdir -p /tmp/gpd-e2e && cd /tmp/gpd-e2e && git init
gpd install claude-code --local
```

### 19.2 Test each slash command in Claude Code

Open Claude Code in `/tmp/gpd-e2e` and run each command:

```
/gpd:help                          # should list all commands
/gpd:new-project                   # interactive project creation
/gpd:progress                      # show current state
/gpd:suggest-next                  # what to do next
/gpd:discuss-phase 1               # discuss before planning
/gpd:plan-phase 1                  # create execution plans
/gpd:execute-phase 1               # run the plans
/gpd:verify-work 1                 # verify results
/gpd:show-phase 1                  # inspect phase artifacts
/gpd:health                        # project health
/gpd:validate-conventions          # convention consistency
/gpd:check-todos                   # pending todos
/gpd:add-todo Fix the sign error   # capture an idea
/gpd:decisions                     # decision log
/gpd:error-patterns                # known LLM errors
/gpd:settings                      # view/modify settings
/gpd:set-profile deep-theory       # switch model profile
/gpd:pause-work                    # save context and pause
/gpd:resume-work                   # restore context
/gpd:estimate-cost                 # token/cost estimate
/gpd:compact-state                 # trim state
/gpd:record-insight                # save a learning
/gpd:graph                         # dependency visualization
```

**Advanced workflows (need a more complete project):**
```
/gpd:add-phase Numerical verification
/gpd:insert-phase 1 Extended review
/gpd:remove-phase 3
/gpd:merge-phases
/gpd:revise-phase 1
/gpd:branch-hypothesis
/gpd:compare-branches
/gpd:audit-milestone
/gpd:complete-milestone
/gpd:new-milestone
/gpd:plan-milestone-gaps

/gpd:derive-equation
/gpd:dimensional-analysis
/gpd:limiting-cases
/gpd:sensitivity-analysis
/gpd:error-propagation
/gpd:numerical-convergence
/gpd:parameter-sweep
/gpd:compare-experiment

/gpd:literature-review
/gpd:map-theory
/gpd:discover
/gpd:debug
/gpd:regression-check
/gpd:quick Calculate ground state energy at U/t=4

/gpd:write-paper
/gpd:respond-to-referees
/gpd:arxiv-submission
/gpd:export
```

---

## PHASE 20: Run All Existing Unit Tests

```bash
# Full suite
uv run pytest tests/ -v --tb=short 2>&1 | tee /tmp/gpd-test-results.txt

# By area (for tracking)
uv run pytest tests/core/ -v                    # Core modules
uv run pytest tests/adapters/ -v                # Platform adapters
uv run pytest tests/hooks/ -v                   # Hooks
uv run pytest tests/mcp/ -v                     # MCP servers
uv run pytest tests/test_parity.py -v           # Cross-platform parity
uv run pytest tests/test_cli.py tests/test_cli_commands.py -v  # CLI
uv run pytest tests/test_paper_e2e.py -v        # Paper generation
uv run pytest tests/test_subagents_*.py -v      # Subagent system
uv run pytest tests/test_discovery_*.py -v      # MCP discovery
uv run pytest tests/test_research_*.py -v       # Research planner
```

**Check:** All 1903 tests pass.

---

## PHASE 21: Edge Cases & Error Handling

### 21.1 Empty/Missing Project

```bash
mkdir /tmp/gpd-empty && cd /tmp/gpd-empty
gpd health          # should report missing .planning/
gpd suggest         # should suggest new-project
gpd state load      # should error cleanly
gpd phase list      # should error cleanly
```

### 21.2 Corrupted State

```bash
cd /tmp/gpd-project
cp .planning/state.json .planning/state.json.backup
echo "not json" > .planning/state.json
gpd state load      # should handle gracefully
gpd health --fix    # should regenerate from STATE.md
cp .planning/state.json.backup .planning/state.json
```

### 21.3 Unicode & Special Characters

```bash
gpd slug "Schrödinger's équation — λ → ∞"
gpd question add "Does ⟨ψ|H|ψ⟩ converge for d→4?"
gpd state add-decision --phase 01 --summary "Use ℏ=c=kB=1" --rationale "Simplifies all expressions"
```

### 21.4 Concurrent Access

```bash
cd /tmp/gpd-project
# Two simultaneous state updates
gpd state update status "Writing" &
gpd state update status "Executing" &
wait
gpd state get status    # one should win, no corruption
```

### 21.5 Large State

```bash
cd /tmp/gpd-project
for i in $(seq 1 50); do
  gpd result add --id "res-$i" --equation "E_$i = $i" --description "Result $i" \
    --units energy --validity "always" --phase 01
done
gpd result list
gpd state load   # should still work at scale
```

---

## PHASE 22: Cleanup

```bash
rm -rf /tmp/gpd-test-cc /tmp/gpd-test-cc-global /tmp/gpd-test-codex
rm -rf /tmp/gpd-test-gemini /tmp/gpd-test-oc /tmp/gpd-project
rm -rf /tmp/gpd-empty /tmp/gpd-patterns /tmp/gpd-pipeline /tmp/gpd-e2e
rm -f /tmp/j1.json /tmp/j2.json /tmp/merged.json /tmp/gpd-test-results.txt
```

---

## Summary Checklist

| Phase | Area | Commands Tested |
|-------|------|----------------|
| 1 | Standalone utilities | 15 |
| 2 | Installation (4 platforms) | 10 |
| 3 | State management | 18 |
| 4 | Conventions | 8 |
| 5 | Results/approx/uncert/questions/calcs | 20 |
| 6 | Phase lifecycle | 12 |
| 7 | Frontmatter & verification | 8 |
| 8 | Query system | 5 |
| 9 | Patterns, trace, config | 16 |
| 10 | Health, suggest, scaffold, history | 10 |
| 11 | Templates | 3 |
| 12 | Git operations | 5 |
| 13 | Init context commands | 15 |
| 14 | Milestone lifecycle | 1 |
| 15 | MCP servers (7 × ~5 tools) | 37 |
| 16 | Hooks | 4 |
| 17 | Ablation & feature flags | 5 |
| 18 | GPD+ & pipeline | 7 |
| 19 | E2E agent workflows (Claude Code) | 45+ |
| 20 | Unit test suite | 1903 tests |
| 21 | Edge cases & error handling | 10 |
| **Total** | | **~250+ manual test points + 1903 automated** |

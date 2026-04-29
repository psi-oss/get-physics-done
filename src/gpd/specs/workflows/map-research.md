<purpose>
Orchestrate parallel research-mapper agents to analyze a physics research project and produce structured documents in GPD/research-map/

Each agent has fresh context, explores a specific focus area, and **writes documents directly**. The orchestrator receives typed returns plus confirmation and line counts, verifies the expected files on disk, then writes a summary.

Output: `GPD/research-map/` under the resolved project root, with 7 structured documents covering theoretical content, computational methods, data artifacts, conventions, and open questions.
</purpose>

<philosophy>
**Why dedicated mapper agents:**
- Fresh context per domain (no token contamination)
- Agents write documents directly (no context transfer back to orchestrator)
- Orchestrator only summarizes what was created (minimal context usage)
- Faster execution (agents run simultaneously)

**Document quality over length:**
Include enough detail to be useful as reference. Prioritize practical examples (key equations, code patterns, data formats) over arbitrary brevity.

**Document templates:** Mapper agents load templates from `{GPD_INSTALL_DIR}/references/templates/research-mapper/` (FORMALISM.md, CONVENTIONS.md, CONCERNS.md, etc.). These paths are deterministic across runtimes after install; if they are missing, treat that as a broken install and fall back to the agent's built-in structural guidance rather than searching alternate runtime-specific locations.

**Always include file paths:**
Documents are reference material for the AI when planning/executing. Always include actual file paths formatted with backticks: `src/hamiltonian.py`, `notebooks/convergence_test.ipynb`, `latex/topic_stem.tex`.

**Map all project artifacts:**
A physics research project typically contains:

- Theoretical derivations (LaTeX, markdown, handwritten-note scans)
- Computational code (Python, Julia, C++, Fortran scripts and libraries)
- Data files (HDF5, CSV, NumPy arrays, simulation outputs)
- Notebooks (Jupyter/Mathematica/Maple for exploratory calculations)
- Figures and plots (generated or hand-drawn)
- Configuration files (input decks, parameter files, job scripts)
- References (BibTeX, downloaded papers, annotated PDFs)
  </philosophy>

<process>

<step name="init_context" priority="first">
Load research mapping context:

```bash
load_map_research_stage() {
  local stage_name="$1"
  local init_payload=""
  local target_cwd="${PROJECT_ROOT:-$PWD}"

  if [ -n "${ARGUMENTS:-}" ]; then
    init_payload=$(gpd --raw --cwd "$target_cwd" init map-research --stage "${stage_name}" -- "${ARGUMENTS:-}" 2>/dev/null)
  else
    init_payload=$(gpd --raw --cwd "$target_cwd" init map-research --stage "${stage_name}" 2>/dev/null)
  fi
  if [ $? -ne 0 ] || [ -z "$init_payload" ]; then
    echo "ERROR: staged gpd initialization failed for stage '${stage_name}': ${init_payload}"
    return 1
  fi

  printf '%s' "$init_payload"
  return 0
}

BOOTSTRAP_INIT=$(load_map_research_stage map_bootstrap)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $BOOTSTRAP_INIT"
  # STOP — display the error to the user and do not proceed.
fi

PROJECT_ROOT=$(echo "$BOOTSTRAP_INIT" | gpd json get .project_root --default "")
WORKSPACE_ROOT=$(echo "$BOOTSTRAP_INIT" | gpd json get .workspace_root --default "")
RESEARCH_MAP_DIR=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_map_dir --default "GPD/research-map")
RESEARCH_MAP_DIR_ABS=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_map_dir_absolute --default "")
if [ -z "$PROJECT_ROOT" ] || [ -z "$RESEARCH_MAP_DIR_ABS" ]; then
  echo "ERROR: map-research init did not return project_root and research_map_dir_absolute"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `mapper_model`, `workspace_root`, `project_root`, `commit_docs`, `research_mode`, `map_focus`, `map_focus_provided`, `research_map_dir`, `research_map_dir_absolute`, `existing_maps`, `has_maps`, `research_map_dir_exists`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`.

All filesystem actions in this workflow must use `PROJECT_ROOT` / `RESEARCH_MAP_DIR_ABS` from the staged payload. Do not create, delete, archive, verify, or commit `GPD/research-map` relative to the shell launch directory; a nested launch cwd inside a project is valid and must still target the resolved project root.

**Read mode settings:**

```bash
RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)
```

**Mode-aware behavior:**
- `research_mode=explore`: Map broadly — include alternative theoretical frameworks, speculative connections, open questions across related domains.
- `research_mode=exploit`: Map narrowly — focus on primary formalism, established results, direct computational needs.
- `research_mode=balanced` (default): Use the standard mapping depth for this workflow and preserve the default anchor and contract coverage unless the research question needs broader or narrower mapping.
- `research_mode=adaptive`: Start with primary framework, expand mapping if connections to other domains appear.
- Regardless of mode, do not drop contract-critical anchors, prior baselines, or user-mandated references.
- `RESEARCH_MODE` is sourced from the init payload. Do not re-query config later in this workflow.
- Preserve stable anchor identity when you rewrite or merge references: every durable anchor in `REFERENCES.md` should carry a reusable `Anchor ID` and a concrete `Source / Locator`.
- Keep workflow carry-forward scope separate from canonical contract subject linkage. `Carry Forward To` names workflow stages; if exact claim/deliverable IDs are known, record them in a dedicated `Contract Subject IDs` field instead of overloading the stage field.
- Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. If the gate is blocked, keep the contract visible as context but do not treat it as approved mapping truth.
- If `map_focus_provided` is true, keep `map_focus` visible and bias each slice without losing contract-critical coverage. Map focus: {map_focus}
Each mapper agent is a one-shot file-producing handoff. Route on `gpd_return.status`, then verify `gpd_return.files_written` against the expected artifacts before accepting the run.
</step>

<step name="check_existing">
Check if the project-rooted research-map directory already exists using `has_maps` and `research_map_dir_exists` from init context.

If `research_map_dir_exists` is true:

```bash
ls -la "$RESEARCH_MAP_DIR_ABS/"
```

**If exists:**

```
GPD/research-map/ already exists at:
{research_map_dir_absolute}

Existing documents:
[List files found]

What's next?
- option_id: refresh_archive - archive existing map beside it, create a new empty map, remap.
- option_id: update_selected - keep existing files and update selected documents.
- option_id: skip_existing - use existing research map as-is.
```

Wait for user response and route by exact `option_id`, not option number or label.

If `refresh_archive`: archive first, then continue to create_structure:

```bash
RESEARCH_MAP_ARCHIVE_DIR="${RESEARCH_MAP_DIR_ABS}.archive-$(date +%Y%m%d-%H%M%S)"
if [ -e "$RESEARCH_MAP_ARCHIVE_DIR" ]; then
  RESEARCH_MAP_ARCHIVE_DIR="${RESEARCH_MAP_ARCHIVE_DIR}-$$"
fi
mv "$RESEARCH_MAP_DIR_ABS" "$RESEARCH_MAP_ARCHIVE_DIR"
mkdir -p "$RESEARCH_MAP_DIR_ABS"
echo "Archived previous research map at: $RESEARCH_MAP_ARCHIVE_DIR"
```

If `update_selected`: Ask which documents to update, continue to spawn_agents (filtered)
If `skip_existing`: Exit workflow

**If doesn't exist:**
Continue to create_structure.
</step>

<step name="create_structure">
Create the project-rooted research-map directory:

```bash
mkdir -p "$RESEARCH_MAP_DIR_ABS"
```

**Expected output files:**

- FORMALISM.md (from theory mapper)
- REFERENCES.md (from theory mapper)
- ARCHITECTURE.md (from computation mapper)
- STRUCTURE.md (from computation mapper)
- CONVENTIONS.md (from methodology mapper)
- VALIDATION.md (from methodology mapper)
- CONCERNS.md (from status mapper)

Continue to spawn_agents.
</step>

<step name="spawn_agents">
Spawn 4 parallel gpd-research-mapper agents.

Load the authoring slice only after existing-map routing and directory setup are complete:

```bash
MAPPER_AUTHORING_INIT=$(load_map_research_stage mapper_authoring)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $MAPPER_AUTHORING_INIT"
  exit 1
fi
```

Extract from the staged refresh: `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifact_files`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_references`, `citation_source_files`, and the manuscript-reference status fields. Use that refresh for mapper prompts; do not reuse bootstrap state for authoring.

Use task tool with `subagent_type="gpd-research-mapper"`, `model="{mapper_model}"`, `readonly=false`, and `run_in_background=true` for parallel execution.
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> Apply the canonical runtime delegation convention already loaded above.

**CRITICAL:** Use the dedicated `gpd-research-mapper` agent, NOT `Explore`. The mapper agent writes documents directly.

Each mapper prompt must carry the staged intake fields, active reference context, reference excerpts, contract load/validation status, and the project contract. Contract IDs are preferred only when `project_contract_gate.authoritative` is true; otherwise the contract stays context-only.

Mapper write paths are project-rooted. Resolve every relative `GPD/research-map/...` path against `{project_root}` and write to the corresponding absolute target under `{research_map_dir_absolute}`. Never write under the runtime shell cwd unless it is the same directory as `{project_root}`.

**Agent 1: Theory Focus**

task(
  subagent_type="gpd-research-mapper",
  model="{mapper_model}",
  readonly=false,
  run_in_background=true,
  description="Map research project theoretical content",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: theory. Bias toward {map_focus} when provided without dropping contract-critical anchors.
Analyze theoretical content and literature foundations.

Staged context: {effective_reference_intake}
Active references: {active_reference_context}
Reference excerpts: {reference_artifacts_content}
Contract load/validation: {project_contract_load_info} / {project_contract_validation}
Project contract for gated IDs/context: {project_contract}
Use contract IDs only when the gate is authoritative; otherwise treat the contract as context.

- FORMALISM.md - equations, symmetries, approximations, boundary conditions, conservation laws
- REFERENCES.md - anchor registry for papers, benchmarks, prior artifacts, required carry-forward actions, and open questions. Every row needs `Anchor ID` and `Source / Locator`; record exact contract IDs separately when known.

Write to: GPD/research-map/FORMALISM.md
Write to: GPD/research-map/REFERENCES.md
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/research-map/FORMALISM.md
    - GPD/research-map/REFERENCES.md
expected_artifacts:
  - GPD/research-map/FORMALISM.md
  - GPD/research-map/REFERENCES.md
shared_state_policy: return_only
</spawn_contract>

Return typed `gpd_return`; `completed` is provisional until both files exist and appear in `files_written`.

Read LaTeX, markdown notes, comments/docstrings, README files, BibTeX, and docs. Write documents directly from templates; return confirmation only.
"
)

**Agent 2: Computation Focus**

task(
  subagent_type="gpd-research-mapper",
  model="{mapper_model}",
  readonly=false,
  run_in_background=true,
  description="Map research project computational methods",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: computation. Bias toward {map_focus} when provided without dropping contract-critical anchors.
Analyze computational methods, solvers, and project structure.

Staged context: {effective_reference_intake}
Active references: {active_reference_context}
Reference excerpts: {reference_artifacts_content}
Contract load/validation: {project_contract_load_info} / {project_contract_validation}
Project contract for gated IDs/context: {project_contract}
Use contract IDs only when the gate is authoritative; otherwise treat the contract as context.

- ARCHITECTURE.md - computational pipeline, solver choices, libraries, data flow, performance bottlenecks
- STRUCTURE.md - directory layout, file roles, naming conventions, formats, dependencies, build/job scripts

Write to: GPD/research-map/ARCHITECTURE.md
Write to: GPD/research-map/STRUCTURE.md
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/research-map/ARCHITECTURE.md
    - GPD/research-map/STRUCTURE.md
expected_artifacts:
  - GPD/research-map/ARCHITECTURE.md
  - GPD/research-map/STRUCTURE.md
shared_state_policy: return_only
</spawn_contract>

Return typed `gpd_return`; `completed` is provisional until both files exist and appear in `files_written`.

Read Python/Julia/C++/Fortran, notebooks, Makefiles, configs, requirements/pyproject files. Write documents directly from templates; return confirmation only.
"
)

**Agent 3: Methodology Focus**

task(
  subagent_type="gpd-research-mapper",
  model="{mapper_model}",
  readonly=false,
  run_in_background=true,
  description="Map research project conventions and validation",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: methodology. Bias toward {map_focus} when provided without dropping contract-critical anchors.
Analyze notation conventions, unit systems, and validation practices.

Staged context: {effective_reference_intake}
Active references: {active_reference_context}
Reference excerpts: {reference_artifacts_content}
Contract load/validation: {project_contract_load_info} / {project_contract_validation}
Project contract for gated IDs/context: {project_contract}
Use contract IDs only when the gate is authoritative; otherwise treat the contract as context.

- CONVENTIONS.md - notation, signs, units, indices, coordinates, variable naming, coupling definitions
- VALIDATION.md - known limits, convergence, consistency checks, comparisons, tests, error analysis

Write to: GPD/research-map/CONVENTIONS.md
Write to: GPD/research-map/VALIDATION.md
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/research-map/CONVENTIONS.md
    - GPD/research-map/VALIDATION.md
expected_artifacts:
  - GPD/research-map/CONVENTIONS.md
  - GPD/research-map/VALIDATION.md
shared_state_policy: return_only
</spawn_contract>

Return typed `gpd_return`; `completed` is provisional until both files exist and appear in `files_written`.

Read LaTeX preambles, code variable naming, tests, validation scripts, comparison notebooks. Write documents directly from templates; return confirmation only.
"
)

**Agent 4: Status Focus**

task(
  subagent_type="gpd-research-mapper",
  model="{mapper_model}",
  readonly=false,
  run_in_background=true,
  description="Map research project concerns and open questions",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: status. Bias toward {map_focus} when provided without dropping contract-critical anchors.
Analyze open questions, known issues, and concerns.

Staged context: {effective_reference_intake}
Active references: {active_reference_context}
Reference excerpts: {reference_artifacts_content}
Contract load/validation: {project_contract_load_info} / {project_contract_validation}
Project contract for gated IDs/context: {project_contract}
Use contract IDs only when the gate is authoritative; otherwise treat the contract as context.

- CONCERNS.md - known issues, theoretical gaps, TODOs, fragile code/calculations, missing validation, bottlenecks, stale branches

Write to: GPD/research-map/CONCERNS.md
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - GPD/research-map/CONCERNS.md
expected_artifacts:
  - GPD/research-map/CONCERNS.md
shared_state_policy: return_only
</spawn_contract>

Return typed `gpd_return`; `completed` is provisional until the file exists and appears in `files_written`.

Search TODO/FIXME/HACK/XXX, issue trackers, commented-out code, notebooks with errors. Write document directly from template; return confirmation only.
"
)

**If any mapper agent fails to spawn or returns an error:** Continue with remaining agents. After all agents complete, report which focus areas failed. For each failed agent, offer: 1) Retry that focus area, 2) Skip it (the research map will be incomplete but usable for the covered areas). A partial research map is still valuable — do not abort the entire mapping operation for individual agent failures.

Continue to collect_confirmations.
</step>

<step name="collect_confirmations">
Wait for all 4 agents to complete.

Read each agent's output file to collect confirmations, then reconcile the typed return envelope with the on-disk artifacts.

**Expected confirmation format from each agent:**

```yaml
gpd_return:
  status: completed | checkpoint | blocked | failed
  files_written: [GPD/research-map/{DOC1}.md, ...]
  issues: [list of issues encountered, if any]
  next_actions: [concrete commands or exact artifact review actions]
  focus: "theory | computation | methodology | status"
```

**What you receive:** Typed return + file paths and line counts. NOT document contents.

If an agent reports `gpd_return.status: completed`, treat the handoff as provisional until every expected artifact exists on disk and the same paths appear in `gpd_return.files_written`.

If any agent failed, note the failure and continue with successful documents.

Continue to verify_output.
</step>

<step name="verify_output">
Verify all documents created successfully:

```bash
ls -la "$RESEARCH_MAP_DIR_ABS/"
wc -l "$RESEARCH_MAP_DIR_ABS"/*.md
```

**Verification checklist:**

- All 7 documents exist
- No empty documents (each should have >20 lines)

If any documents missing or empty, note which agents may have failed.

Continue to scan_for_secrets.
</step>

<step name="scan_for_secrets">
**CRITICAL SECURITY CHECK:** Scan output files for accidentally leaked secrets before committing.

Run secret pattern detection:

```bash
# Check for common API key patterns in generated docs
grep -E '(sk-[a-zA-Z0-9]{20,}|sk_live_[a-zA-Z0-9]+|sk_test_[a-zA-Z0-9]+|ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|glpat-[a-zA-Z0-9_-]+|AKIA[A-Z0-9]{16}|xox[baprs]-[a-zA-Z0-9-]+|-----BEGIN.*PRIVATE KEY|eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.)' "$RESEARCH_MAP_DIR_ABS"/*.md 2>/dev/null && SECRETS_FOUND=true || SECRETS_FOUND=false
```

**If SECRETS_FOUND=true:**

```
>> SECURITY ALERT: Potential secrets detected in research map documents!

Found patterns that look like API keys or tokens in:
[show grep output]

This would expose credentials if committed.

**Action required:**
1. Review the flagged content above
2. If these are real secrets, they must be removed before committing
3. Consider adding sensitive files to your runtime's restricted-access list

Pausing before commit. Reply "safe to proceed" if the flagged content is not actually sensitive, or edit the files first.
```

Wait for user confirmation before continuing to commit_research_map.

**If SECRETS_FOUND=false:**

Continue to commit_research_map.
</step>

<step name="commit_research_map">
Commit the research map:

```bash
PRE_CHECK=$(gpd --cwd "$PROJECT_ROOT" pre-commit-check --files "$RESEARCH_MAP_DIR" 2>&1) || true
echo "$PRE_CHECK"

gpd --cwd "$PROJECT_ROOT" commit "docs: map existing research project" --files "$RESEARCH_MAP_DIR"
```

Continue to offer_next.
</step>

<step name="offer_next">
Present completion summary and next steps.

**Get line counts:**

```bash
wc -l "$RESEARCH_MAP_DIR_ABS"/*.md
```

**Output format:**

```
Research project mapping complete.

Created GPD/research-map/:
- FORMALISM.md ([N] lines) - Theoretical framework, key equations, symmetries
- REFERENCES.md ([N] lines) - Literature foundations, cited papers, experimental data
- ARCHITECTURE.md ([N] lines) - Computational pipeline, solvers, algorithms
- STRUCTURE.md ([N] lines) - Directory layout, file organization, data formats
- CONVENTIONS.md ([N] lines) - Notation, units, sign conventions
- VALIDATION.md ([N] lines) - Benchmarks, consistency checks, test coverage
- CONCERNS.md ([N] lines) - Known issues, theoretical gaps, open questions


---

## > Next Up

**Initialize project** -- use research map context for planning

`gpd:new-project`

<sub>Start a fresh context window</sub>

---

**Also available:**
- Re-run mapping: `gpd:map-research`
- Review specific file: `cat GPD/research-map/FORMALISM.md`
- Edit any document before proceeding

---
```

End workflow.
</step>

</process>

<success_criteria>

- GPD/research-map/ directory created
- 4 parallel gpd-research-mapper agents spawned with run_in_background=true
- Agents write documents directly (orchestrator doesn't receive document contents)
- Read agent output files to collect confirmations
- All 7 research map documents exist covering theory, computation, methodology, and status
- Clear completion summary with line counts
- User offered clear next steps in GPD style
  </success_criteria>

<purpose>
Orchestrate parallel research-mapper agents to analyze a physics research project and produce structured documents in .gpd/research-map/

Each agent has fresh context, explores a specific focus area, and **writes documents directly**. The orchestrator only receives confirmation + line counts, then writes a summary.

Output: .gpd/research-map/ folder with 7 structured documents covering theoretical content, computational methods, data artifacts, conventions, and open questions.
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
Documents are reference material for the AI when planning/executing. Always include actual file paths formatted with backticks: `src/hamiltonian.py`, `notebooks/convergence_test.ipynb`, `latex/main.tex`.

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
# Research-mapping initialization.
INIT=$(gpd init map-research)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `mapper_model`, `commit_docs`, `research_map_dir`, `existing_maps`, `has_maps`, `research_map_dir_exists`, `project_contract`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`.

**Read mode settings:**

```bash
RESEARCH_MODE=$(gpd --raw config get research_mode 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

**Mode-aware behavior:**
- `research_mode=explore`: Map broadly — include alternative theoretical frameworks, speculative connections, open questions across related domains.
- `research_mode=exploit`: Map narrowly — focus on primary formalism, established results, direct computational needs.
- `research_mode=adaptive`: Start with primary framework, expand mapping if connections to other domains appear.
- Regardless of mode, do not drop contract-critical anchors, prior baselines, or user-mandated references.
- Treat `effective_reference_intake` as the machine-readable carry-forward registry for anchors, prior outputs, baselines, and unresolved gaps. Use `active_reference_context` to render and explain it, not to replace it.
- Use `reference_artifacts_content` when the existing literature/research-map artifacts already contain stable citations, prior-output paths, or benchmark wording that should be preserved verbatim.
- Preserve stable anchor identity when you rewrite or merge references: every durable anchor in `REFERENCES.md` should carry a reusable `Anchor ID` and a concrete `Source / Locator`.
- Keep workflow carry-forward scope separate from canonical contract subject linkage. `Carry Forward To` names workflow stages; if exact claim/deliverable IDs are known, record them in a dedicated `Contract Subject IDs` field instead of overloading the stage field.
</step>

<step name="check_existing">
Check if .gpd/research-map/ already exists using `has_maps` from init context.

If `research_map_dir_exists` is true:

```bash
ls -la .gpd/research-map/
```

**If exists:**

```
.gpd/research-map/ already exists with these documents:
[List files found]

What's next?
1. Refresh - Delete existing and remap research project
2. Update - Keep existing, only update specific documents
3. Skip - Use existing research map as-is
```

Wait for user response.

If "Refresh": Delete .gpd/research-map/, continue to create_structure
If "Update": Ask which documents to update, continue to spawn_agents (filtered)
If "Skip": Exit workflow

**If doesn't exist:**
Continue to create_structure.
</step>

<step name="create_structure">
Create .gpd/research-map/ directory:

```bash
mkdir -p .gpd/research-map
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

Use task tool with `subagent_type="gpd-research-mapper"`, `model="{mapper_model}"`, `readonly=false`, and `run_in_background=true` for parallel execution.
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

**CRITICAL:** Use the dedicated `gpd-research-mapper` agent, NOT `Explore`. The mapper agent writes documents directly.

**Agent 1: Theory Focus**

task tool parameters:

```
subagent_type="gpd-research-mapper"
model: "{mapper_model}"
run_in_background: true
description: "Map research project theoretical content"
```

Prompt:

```
First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: theory

Analyze this research project for theoretical content and literature foundations.
Treat the machine-readable intake below as binding carry-forward context:
{effective_reference_intake}

Keep this active reference context visible while mapping:
{active_reference_context}

Existing reference artifact excerpts:
{reference_artifacts_content}

If `project_contract` is present, use its existing IDs as the preferred canonical names for anchors and contract subject references:
{project_contract}

Write these documents to .gpd/research-map/:
- FORMALISM.md - Lagrangians/Hamiltonians, symmetries, gauge groups, field content, key equations, approximation schemes, effective theories, governing PDEs/ODEs, boundary conditions, conservation laws
- REFERENCES.md - Active anchor registry: papers cited, benchmarks, prior artifacts, required carry-forward actions, open questions from literature, experimental data sources, collaboration context. Every row must have a stable `Anchor ID` and concrete `Source / Locator`. Use `Carry Forward To` for workflow stages only; if exact contract claim/deliverable IDs are known, record them separately as `Contract Subject IDs`.

Explore thoroughly: read LaTeX files, markdown notes, code comments, docstrings, README files, BibTeX databases, and any documentation. Write documents directly using templates. Return confirmation only.
```

**Agent 2: Computation Focus**

task tool parameters:

```
subagent_type="gpd-research-mapper"
model: "{mapper_model}"
run_in_background: true
description: "Map research project computational methods"
```

Prompt:

```
First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: computation

Analyze this research project for computational methods, solvers, and project structure.

Write these documents to .gpd/research-map/:
- ARCHITECTURE.md - Computational pipeline, solver choices (ODE/PDE/linear algebra), algorithm design, parallelization strategy, key libraries used (NumPy, SciPy, PETSc, etc.), MCP simulation servers, data flow from input to output, performance bottlenecks
- STRUCTURE.md - Directory layout, file organization (code vs data vs docs vs notebooks), naming conventions, input/output formats (HDF5, CSV, JSON), dependency graph between scripts, build system, job submission scripts

Explore thoroughly: read Python/Julia/C++/Fortran files, Jupyter notebooks, Makefiles, configuration files, requirements/pyproject files. Write documents directly using templates. Return confirmation only.
```

**Agent 3: Methodology Focus**

task tool parameters:

```
subagent_type="gpd-research-mapper"
model: "{mapper_model}"
run_in_background: true
description: "Map research project conventions and validation"
```

Prompt:

```
First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: methodology

Analyze this research project for notation conventions, unit systems, and validation practices.

Write these documents to .gpd/research-map/:
- CONVENTIONS.md - Notation system, sign conventions (metric signature, Fourier transforms), unit system (natural/SI/CGS), index placement conventions (Einstein summation), coordinate labeling, variable naming in code vs equations, coupling constant definitions, Wick rotation conventions
- VALIDATION.md - Known limits checked (analytic benchmarks, exact solutions), convergence tests performed, consistency checks (conservation laws, sum rules, Ward identities), comparison with published results, test suite structure, regression tests, error analysis methodology

Explore thoroughly: read LaTeX preambles for notation macros, code variable naming, test files, validation scripts, comparison notebooks. Write documents directly using templates. Return confirmation only.
```

**Agent 4: Status Focus**

task tool parameters:

```
subagent_type="gpd-research-mapper"
model: "{mapper_model}"
run_in_background: true
description: "Map research project concerns and open questions"
```

Prompt:

```
First, read {GPD_AGENTS_DIR}/gpd-research-mapper.md for your role and instructions.

Focus: status

Analyze this research project for open questions, known issues, and areas of concern.

Write this document to .gpd/research-map/:
- CONCERNS.md - Known issues (unresolved divergences, numerical instabilities, sign ambiguities), theoretical gaps (missing diagrams, uncontrolled approximations, gauge artifacts), TODO items found in code and notes, fragile areas (code that breaks easily, calculations sensitive to parameter choices), missing validation (untested regimes, unchecked limits), computational bottlenecks, stale or abandoned branches of investigation

Explore thoroughly: search for TODO/FIXME/HACK/XXX comments, read issue trackers, check for commented-out code, look for notebooks with error outputs. Write document directly using template. Return confirmation only.
```

**If any mapper agent fails to spawn or returns an error:** Continue with remaining agents. After all agents complete, report which focus areas failed. For each failed agent, offer: 1) Retry that focus area, 2) Skip it (the research map will be incomplete but usable for the covered areas). A partial research map is still valuable — do not abort the entire mapping operation for individual agent failures.

Continue to collect_confirmations.
</step>

<step name="collect_confirmations">
Wait for all 4 agents to complete.

Read each agent's output file to collect confirmations.

**Expected confirmation format from each agent:**

```
## Mapping Complete

**Focus:** {focus}
**Documents written:**
- `.gpd/research-map/{DOC1}.md` ({N} lines)
- `.gpd/research-map/{DOC2}.md` ({N} lines)

Ready for orchestrator summary.
```

**What you receive:** Just file paths and line counts. NOT document contents.

If any agent failed, note the failure and continue with successful documents.

Continue to verify_output.
</step>

<step name="verify_output">
Verify all documents created successfully:

```bash
ls -la .gpd/research-map/
wc -l .gpd/research-map/*.md
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
grep -E '(sk-[a-zA-Z0-9]{20,}|sk_live_[a-zA-Z0-9]+|sk_test_[a-zA-Z0-9]+|ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|glpat-[a-zA-Z0-9_-]+|AKIA[A-Z0-9]{16}|xox[baprs]-[a-zA-Z0-9-]+|-----BEGIN.*PRIVATE KEY|eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.)' .gpd/research-map/*.md 2>/dev/null && SECRETS_FOUND=true || SECRETS_FOUND=false
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
PRE_CHECK=$(gpd pre-commit-check --files .gpd/research-map/*.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: map existing research project" --files .gpd/research-map/*.md
```

Continue to offer_next.
</step>

<step name="offer_next">
Present completion summary and next steps.

**Get line counts:**

```bash
wc -l .gpd/research-map/*.md
```

**Output format:**

```
Research project mapping complete.

Created .gpd/research-map/:
- FORMALISM.md ([N] lines) - Theoretical framework, key equations, symmetries
- REFERENCES.md ([N] lines) - Literature foundations, cited papers, experimental data
- ARCHITECTURE.md ([N] lines) - Computational pipeline, solvers, algorithms
- STRUCTURE.md ([N] lines) - Directory layout, file organization, data formats
- CONVENTIONS.md ([N] lines) - Notation, units, sign conventions
- VALIDATION.md ([N] lines) - Benchmarks, consistency checks, test coverage
- CONCERNS.md ([N] lines) - Known issues, theoretical gaps, open questions


---

## Next Up

**Initialize project** -- use research map context for planning

`/gpd:new-project`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- Re-run mapping: `/gpd:map-research`
- Review specific file: `cat .gpd/research-map/FORMALISM.md`
- Edit any document before proceeding

---
```

End workflow.
</step>

</process>

<success_criteria>

- .gpd/research-map/ directory created
- 4 parallel gpd-research-mapper agents spawned with run_in_background=true
- Agents write documents directly (orchestrator doesn't receive document contents)
- Read agent output files to collect confirmations
- All 7 research map documents exist covering theory, computation, methodology, and status
- Clear completion summary with line counts
- User offered clear next steps in GPD style
  </success_criteria>

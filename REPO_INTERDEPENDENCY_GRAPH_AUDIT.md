# Repository Interdependency Graph Completeness Audit

Generated on `2026-03-10`.

## Bottom Line

No: the repository interdependency graph is **not** completely capturing everything.

It is strong as a mixed-confidence architectural map, but it is not an exhaustive directed graph of all file and object dependencies in this repo. The current approach captures a large fraction of the static, canonical, in-repo relationships, but it still misses important behavioral, semantic, and runtime-resolved dependencies, and it overstates some weaker relationships.

## What This Audit Checked

This audit combined:

- direct inspection of runtime, docs, CI, adapter, hook, and test files in the current worktree
- four waves of focused audit subagent deployments covering runtime, tests, docs/CI, adapters/mirrors, prompt/specs, release/build, and methodology
- usable returned findings from the docs/CI, methodology, and adapter/materialization slices
- local verification of representative files where the graph is most likely to overclaim completeness

This audit is now the companion skepticism document for [REPO_INTERDEPENDENCY_GRAPH.md](/Users/sergio/GitHub/get-physics-done/REPO_INTERDEPENDENCY_GRAPH.md). The graph file is the rebuilt dependency atlas; this file records where static analysis still cannot honestly prove absolute completeness.

## Confidence Summary

### High confidence coverage

- packaging and bootstrap authority chain:
  `package.json -> bin/install.js -> src/gpd/cli.py`
- Python packaging/version chain:
  `pyproject.toml -> src/gpd/cli.py`, `src/gpd/version.py -> pyproject.toml`
- committed MCP descriptor authority:
  `src/gpd/mcp/builtin_servers.py -> infra/gpd-*.json`
- many direct Python import relationships under `src/gpd/**`
- broad source-to-installed-layout correspondence between `src/gpd/**` and `.claude/**`

### Medium confidence coverage

- prompt/workflow/agent/reference relationships under `src/gpd/commands`, `src/gpd/agents`, and `src/gpd/specs/**`
- release-contract relationships among `README.md`, `CONTRIBUTING.md`, `CITATION.cff`, `package.json`, `pyproject.toml`, and `tests/test_release_consistency.py`
- test-to-source consumption patterns

### Low confidence / incomplete coverage

- object-level dependencies such as call graphs, mutation graphs, inheritance graphs, and dataflow
- runtime-resolved file I/O dependencies under `.gpd/**`, runtime config files, caches, todos, candidate path sets, and external install locations
- semantic GitHub governance dependencies under `.github/**`
- external tool and system binary dependencies in the paper pipeline
- transformed install artifacts versus exact file mirrors

## What Is Missing

### 1. Semantic docs, CI, and GitHub governance edges

The graph undercaptures files whose dependencies are real but not expressed as Python imports or explicit path literals.

Important missing or under-modeled edges:

- `README.md -> CONTRIBUTING.md`
- `.github/workflows/test.yml -> tests/**`
- `.github/workflows/test.yml -> pyproject.toml`
- `.github/workflows/test.yml -> uv.lock`
- `.github/pull_request_template.md -> src/**`
- `.github/pull_request_template.md -> tests/**`
- `.github/pull_request_template.md -> README.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml -> src/gpd/cli.py`
- `.github/ISSUE_TEMPLATE/bug_report.yml -> pyproject.toml`
- `.github/ISSUE_TEMPLATE/bug_report.yml -> package.json`
- `.github/ISSUE_TEMPLATE/feature_request.yml -> src/gpd/cli.py`
- `.github/ISSUE_TEMPLATE/feature_request.yml -> src/gpd/commands/**`
- `CONTRIBUTING.md -> src/gpd/mcp/builtin_servers.py`
- `CONTRIBUTING.md -> infra/gpd-conventions.json`
- `CONTRIBUTING.md -> infra/gpd-errors.json`
- `CONTRIBUTING.md -> infra/gpd-patterns.json`
- `CONTRIBUTING.md -> infra/gpd-protocols.json`
- `CONTRIBUTING.md -> infra/gpd-skills.json`
- `CONTRIBUTING.md -> infra/gpd-state.json`
- `CONTRIBUTING.md -> infra/gpd-verification.json`
- `CONTRIBUTING.md -> infra/gpd-arxiv.json`

Why this matters:

- `.github/workflows/test.yml` runs `uv run pytest tests/ -v`, which is a directory-wide policy dependency, not a dependency on one representative test file.
- `.github/pull_request_template.md` requires testing and docs updates across `src/`, `tests/`, and public docs even though it does not import them.
- `CONTRIBUTING.md` explicitly states that `infra/gpd-*.json` must stay synced with the canonical descriptor builder in `src/gpd/mcp/builtin_servers.py`.
- `.github/workflows/test.yml` also depends on external CI action nodes `actions/checkout@v4`, `actions/setup-python@v5`, and `astral-sh/setup-uv@v4`, which are outside the repo but still part of the operational graph.

### 2. Runtime file-I/O and environment-resolved dependencies

The graph is materially incomplete anywhere code depends on files discovered through runtime layout, environment variables, caches, or install-time path resolution instead of through imports.

Important missing dependency classes:

- `src/gpd/hooks/runtime_detect.py -> environment-signal family {CLAUDE_CODE_SESSION, CLAUDE_CODE, CODEX_SESSION, CODEX_CLI, GEMINI_CLI, OPENCODE_SESSION, CLAUDE_CONFIG_DIR, CODEX_CONFIG_DIR, GEMINI_CONFIG_DIR, OPENCODE_CONFIG_DIR, OPENCODE_CONFIG, XDG_CONFIG_HOME}`
- `src/gpd/hooks/runtime_detect.py -> candidate directory families {cwd}/{.claude,.codex,.gemini,.opencode} and {home}/{.claude,.codex,.gemini,.config/opencode}`
- `src/gpd/hooks/statusline.py -> <workspace>/.gpd/state.json`
- `src/gpd/hooks/statusline.py -> todos/*.json`
- `src/gpd/hooks/statusline.py -> gpd-update-check.json`
- `src/gpd/hooks/statusline.py -> stdin payload schema {model, workspace, session_id, context_window}`
- `src/gpd/hooks/statusline.py -> candidate todo family {local,global runtime dirs}/todos/<session>-agent-*.json`
- `src/gpd/hooks/runtime_detect.py -> CLAUDE_CONFIG_DIR`
- `src/gpd/hooks/runtime_detect.py -> CODEX_CONFIG_DIR`
- `src/gpd/hooks/runtime_detect.py -> GEMINI_CONFIG_DIR`
- `src/gpd/hooks/runtime_detect.py -> OPENCODE_CONFIG_DIR`
- `src/gpd/hooks/runtime_detect.py -> XDG_CONFIG_HOME`
- `src/gpd/hooks/runtime_detect.py -> ~/.gpd/cache/gpd-update-check.json`
- `src/gpd/hooks/check_update.py -> */get-physics-done/VERSION`
- `src/gpd/hooks/check_update.py -> gpd-update-check.json`
- `src/gpd/hooks/check_update.py -> src/gpd/version.py`
- `src/gpd/hooks/check_update.py -> ordered candidate cache family including ~/.gpd/cache/gpd-update-check.json`
- `src/gpd/hooks/codex_notify.py -> src/gpd/hooks/check_update.py`
- `src/gpd/hooks/codex_notify.py -> stdin payload schema {type, workspace}`
- `src/gpd/hooks/runtime_detect.py -> runtime config / install directory resolution`
- `src/gpd/version.py -> pyproject.toml` as a fallback source when installed metadata is unavailable
- `src/gpd/cli.py -> many lazily imported core/adapters/paper modules` as command-activated dependencies rather than eager imports
- `src/gpd/cli.py -> external project-layout family <cwd>/.gpd/{state.json,STATE.md,config.json,phases/**,milestones/**,traces/**}`
- `src/gpd/cli.py -> external paper artifact family {paper,manuscript,draft,.gpd/paper}/PAPER-CONFIG.json, ARTIFACT-MANIFEST.json, BIBLIOGRAPHY-AUDIT.json, reproducibility-manifest.json`
- `src/gpd/cli.py -> src/gpd/core/patterns.py -> env/storage family {GPD_PATTERNS_ROOT, GPD_DATA_DIR, ~/.gpd/learned-patterns}`

These are real operational edges, but they are difficult to represent honestly without distinguishing:

- in-repo nodes
- user-home/runtime nodes
- generated/cache nodes
- command-activated edges
- ordered candidate-set edges
- runtime-input-schema edges

### 3. Adapter materialization and transformed-artifact lineage

The graph understates installer behavior and overstates simple mirror behavior.

Important missing or under-modeled edges:

- `src/gpd/adapters/install_utils.py -> .claude/gpd-file-manifest.json`
- `src/gpd/adapters/install_utils.py -> .claude/get-physics-done/VERSION`
- `src/gpd/adapters/install_utils.py -> .claude/commands/gpd/**`
- `src/gpd/adapters/install_utils.py -> .claude/get-physics-done/**`
- `src/gpd/adapters/install_utils.py -> .claude/hooks/**`
- `src/gpd/adapters/claude_code.py -> .claude/settings.json`
- `src/gpd/adapters/claude_code.py -> .claude/hooks/check_update.py`
- `src/gpd/adapters/claude_code.py -> .claude/hooks/statusline.py`
- `src/gpd/adapters/claude_code.py -> ~/.claude.json`
- `src/gpd/adapters/codex.py -> external Codex config.toml / skills dirs`
- `src/gpd/adapters/codex.py -> ~/.agents/skills`
- `src/gpd/adapters/gemini.py -> external Gemini settings.json`
- `src/gpd/adapters/opencode.py -> external opencode.json`
- `src/gpd/adapters/opencode.py -> ~/.config/opencode`
- `src/gpd/adapters/opencode.py -> .opencode`
- `src/gpd/adapters/install_utils.py -> gpd-local-patches/**`
- `src/gpd/adapters/install_utils.py -> gpd-local-patches/backup-meta.json`
- `src/gpd/adapters/codex.py -> gpd-file-manifest.json::codex_skills_dir`
- `.claude/settings.local.json -> src/gpd/mcp/builtin_servers.py` as an in-repo runtime-config node that enables specific MCP server names
- `tests/test_install_edge_cases.py -> cross-runtime collision / overwrite relationships among adapters`

The checked-in `.claude/**` tree is better described as a **transformed installed snapshot** than as an exact mirror:

- command markdown is rewritten for runtime-specific tool names and placeholders
- workflow/reference assets may be expanded or rewritten during installation
- hook files differ from their canonical source versions

The second-wave audit also surfaced a lifecycle constraint the graph still tends to miss: adapters do not own an entire runtime tree. They own only GPD-managed subtrees and specific config keys, while tests explicitly require non-GPD commands, agents, and unrelated config content to survive install/uninstall.

### 4. Test breadth and release-contract edges

The graph captures that tests consume runtime code, but it still underrepresents the breadth and intent of test dependencies.

Important missing or under-modeled edges:

- `tests/test_release_consistency.py -> CITATION.cff`
- `tests/test_release_consistency.py -> LICENSE`
- `tests/test_release_consistency.py -> README.md`
- `tests/test_release_consistency.py -> CONTRIBUTING.md`
- `tests/test_release_consistency.py -> package.json`
- `tests/test_release_consistency.py -> pyproject.toml`
- `tests/test_release_consistency.py -> bin/install.js`
- `tests/test_release_consistency.py -> src/gpd/specs/workflows/export.md`
- `tests/test_metadata_consistency.py -> README.md`
- `tests/test_metadata_consistency.py -> .github/workflows/test.yml`
- `tests/test_metadata_consistency.py -> src/gpd/cli.py`
- `tests/test_metadata_consistency.py -> pyproject.toml`
- `tests/test_metadata_consistency.py -> src/gpd/registry.py`
- `tests/test_metadata_consistency.py -> src/gpd/core/__init__.py`
- `tests/test_metadata_consistency.py -> src/gpd/commands/health.md`
- `tests/test_metadata_consistency.py -> src/gpd/commands/**`
- `tests/test_metadata_consistency.py -> src/gpd/agents/**`
- `tests/test_metadata_consistency.py -> src/gpd/mcp/servers/**`
- `tests/test_metadata_consistency.py -> gpd.contracts.ConventionLock`
- `tests/test_metadata_consistency.py -> gpd.core.health._ALL_CHECKS`
- `tests/test_metadata_consistency.py -> gpd.core.patterns.PatternDomain`
- `tests/test_install_lifecycle.py -> .claude/**` as installed-layout expectations
- `tests/adapters/test_install_roundtrip.py -> source prompt/spec trees and installed prompt/spec trees`
- `tests/test_release_consistency.py -> dist/*.whl`
- `tests/test_release_consistency.py -> dist/*.tar.gz`
- `tests/test_release_consistency.py -> gpd.mcp.builtin_servers.build_public_descriptors()`
- `tests/test_release_consistency.py -> infra/gpd-*.json`
- `tests/test_release_consistency.py -> src/gpd/mcp/viewer/cli.py` as a negative packaging assertion
- `tests/test_release_consistency.py -> docs/USER-GUIDE.md` as a negative packaging assertion
- `tests/test_release_consistency.py -> MANUAL-TEST-PLAN.md` as a negative packaging assertion
- `tests/test_install_edge_cases.py -> gpd.adapters.install_utils.expand_at_includes`
- `tests/test_install_edge_cases.py -> gpd.adapters.install_utils.validate_package_integrity`
- `tests/test_install_edge_cases.py -> gpd.registry._parse_agent_file`
- `tests/test_install_edge_cases.py -> gpd.registry._parse_frontmatter`
- `tests/test_install_edge_cases.py -> CLAUDE_CONFIG_DIR / CODEX_CONFIG_DIR / HOME fallback`
- `tests/core/test_cli_install.py -> gpd.cli._install_single_runtime`
- `tests/core/test_cli_install.py -> gpd.adapters.install_utils.compute_path_prefix`
- `.github/workflows/test.yml -> tests/**` as the CI execution surface

This matters because some tests are not checking implementation internals; they are checking release-facing contracts, packaging, and install-time generated layouts.

The current audit was also too coarse about what these tests validate:

- `tests/test_metadata_consistency.py` is not just a metadata smoke test. It enforces count-based contracts across `pyproject.toml`, `src/gpd/registry.py`, `src/gpd/core/__init__.py`, `src/gpd/cli.py`, `src/gpd/commands/health.md`, and `README.md`.
- `tests/test_release_consistency.py` is not just a static-file check. It depends on `uv build`, generated wheel/sdist artifacts under `dist/`, exact wheel entry points, exact sdist contents, and exact equality between `infra/gpd-*.json` and `build_public_descriptors()`.
- `tests/test_install_edge_cases.py` adds real dependency pressure on environment-variable resolution, manifest corruption handling, circular include expansion, and registry parser fallback behavior.
- `tests/core/test_cli_install.py` binds the CLI install surface to adapter delegation, path-prefix computation, explicit-target semantics, and raw JSON output contracts.

### 4a. Over-narrow test edges to avoid

The graph should avoid collapsing these contracts into one representative source file.

Examples:

- `.github/workflows/test.yml -> tests/core/test_cli.py` is too narrow by itself
- `tests/test_metadata_consistency.py -> README.md` is too narrow if it omits the coupled count/entrypoint sources
- `tests/test_release_consistency.py -> package.json` is too narrow if it omits generated wheel/sdist outputs and descriptor regeneration
- `tests/test_install_lifecycle.py -> .claude/**` is too narrow if it omits runtime-specific settings/config surfaces like `settings.json`, `config.toml`, and `opencode.json`
- any edge that implies adapters own all of `commands/**`, `agents/**`, or an entire runtime config file is too strong

### 4b. Prompt orchestration edges beyond same-stem pairing

The graph is also incomplete if it reduces prompt structure to `command -> same-stem workflow` plus generic reference mentions.

Important missing or under-modeled edges:

- `src/gpd/commands/literature-review.md -> src/gpd/agents/gpd-literature-reviewer.md`
- `src/gpd/specs/workflows/plan-phase.md -> src/gpd/agents/gpd-phase-researcher.md`
- `src/gpd/specs/workflows/plan-phase.md -> src/gpd/agents/gpd-planner.md`
- `src/gpd/specs/workflows/plan-phase.md -> src/gpd/agents/gpd-plan-checker.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/specs/workflows/execute-plan.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/specs/workflows/verify-phase.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/specs/workflows/transition.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/agents/gpd-executor.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/agents/gpd-debugger.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/agents/gpd-verifier.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/agents/gpd-consistency-checker.md`
- `src/gpd/specs/workflows/execute-phase.md -> src/gpd/agents/gpd-notation-coordinator.md`
- `src/gpd/specs/workflows/write-paper.md -> src/gpd/agents/gpd-paper-writer.md`
- `src/gpd/specs/workflows/write-paper.md -> src/gpd/agents/gpd-bibliographer.md`
- `src/gpd/specs/workflows/write-paper.md -> src/gpd/agents/gpd-referee.md`
- `src/gpd/specs/workflows/validate-conventions.md -> src/gpd/agents/gpd-consistency-checker.md`
- `src/gpd/specs/workflows/validate-conventions.md -> src/gpd/agents/gpd-notation-coordinator.md`
- `src/gpd/specs/workflows/quick.md -> src/gpd/agents/gpd-planner.md`
- `src/gpd/specs/workflows/quick.md -> src/gpd/agents/gpd-executor.md`
- `src/gpd/specs/workflows/literature-review.md -> src/gpd/agents/gpd-bibliographer.md`
- `src/gpd/specs/workflows/respond-to-referees.md -> src/gpd/agents/gpd-paper-writer.md`
- `src/gpd/specs/workflows/verify-work.md -> src/gpd/agents/gpd-planner.md`
- `src/gpd/commands/new-project.md -> src/gpd/specs/templates/requirements.md`
- `src/gpd/commands/discuss-phase.md -> src/gpd/specs/templates/context.md`
- `src/gpd/specs/workflows/verify-work.md -> src/gpd/specs/templates/research-verification.md`
- `src/gpd/specs/workflows/verify-work.md -> src/gpd/specs/references/error-propagation-protocol.md`
- `src/gpd/specs/workflows/new-project.md -> src/gpd/specs/templates/project.md`
- `src/gpd/specs/workflows/new-project.md -> src/gpd/specs/templates/research-project/**`
- `src/gpd/agents/gpd-roadmapper.md -> src/gpd/specs/templates/project-types/**`
- `src/gpd/agents/gpd-research-synthesizer.md -> src/gpd/specs/templates/research-project/SUMMARY.md`
- `src/gpd/agents/gpd-theory-mapper.md -> src/gpd/specs/references/theory-mapper-templates/**`
- `src/gpd/agents/gpd-planner.md -> src/gpd/specs/templates/planner-subagent-prompt.md`

These edges are stronger than mere naming convention because the workflows and commands explicitly reference or spawn those assets.

The second-wave audit also tightened the warning on family edges here: `project-types/**` and `research-project/**` are often conditional selection sets, not unconditional dependencies on the entire family.

### 5. External tool dependencies

The graph is incomplete if it claims full operational coverage without modeling subprocess and system-binary dependencies.

Concrete examples:

- `src/gpd/mcp/paper/compiler.py -> kpsewhich`
- `src/gpd/mcp/paper/compiler.py -> latexmk`
- `src/gpd/mcp/paper/compiler.py -> pdflatex`
- `src/gpd/mcp/paper/compiler.py -> xelatex`
- `src/gpd/mcp/paper/compiler.py -> bibtex`
- `src/gpd/mcp/paper/template_registry.py -> src/gpd/mcp/paper/templates/**`
- `pyproject.toml -> external Python packages {hatchling, pybtex, jinja2, Pillow, arxiv-mcp-server}`
- `src/gpd/mcp/paper/bibliography.py -> external Python packages {arxiv, pybtex}`
- `src/gpd/mcp/paper/template_registry.py -> external Python package {jinja2}`
- `src/gpd/mcp/paper/figures.py -> external Python packages {Pillow, cairosvg}`
- `src/gpd/mcp/builtin_servers.py -> external Python package {arxiv_mcp_server}`
- `tests/test_paper_e2e.py -> generated output family {main.tex, references.bib, ARTIFACT-MANIFEST.json, BIBLIOGRAPHY-AUDIT.json, paper.pdf, figures/**}`

Those are not repo files, but they are real runtime dependencies for the paper pipeline.

### 6. Object-level incompleteness

The graph is not a true “all files and objects” graph.

What is still missing at object granularity:

- function-to-function call graph
- method override / inheritance graph
- mutation and ownership graph over shared state structures
- command-to-subcommand execution graph inside `src/gpd/cli.py`
- object-level dataflow among `contracts`, `state`, `results`, `conventions`, and tests

An inventory of classes/functions is not the same thing as an object dependency graph.

### 6b. Schema, serialization, and duplicate logical-node gaps

The current audit also understates a second object-level problem: many logical entities appear in multiple physical forms, and the graph does not currently model that identity.

Important missing or under-modeled relationships:

- `src/gpd/contracts.py -> src/gpd/core/state.py` through `ConventionLock`
- `src/gpd/contracts.py -> src/gpd/core/results.py` through `VerificationEvidence`
- `src/gpd/core/state.py -> state.json`
- `src/gpd/core/state.py -> STATE.md`
- `src/gpd/core/state.py -> state.json.bak`
- `src/gpd/mcp/paper/models.py -> src/gpd/mcp/paper/artifact_manifest.py`
- `src/gpd/mcp/paper/bibliography.py -> src/gpd/mcp/paper/models.py` through `BibliographyAudit`
- `tests/test_parity.py -> tests/fixtures/parity/**`
- `tests/test_metadata_consistency.py -> src/gpd/core/__init__.py`
- `tests/test_metadata_consistency.py -> src/gpd/core/patterns.py`
- `tests/test_metadata_consistency.py -> src/gpd/registry.py`
- `tests/test_release_consistency.py -> dist/*.whl`
- `tests/test_release_consistency.py -> dist/*.tar.gz`

What this exposes:

- `ConventionLock`, `ResearchState`, `VerificationEvidence`, `ArtifactManifest`, and related models are schema nodes, not just ordinary file contents.
- those schema nodes are serialized into `state.json`, rendered into `STATE.md`, copied into backups, emitted into `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json`, and mirrored again inside tests and fixtures
- release and integration tests create synthetic install trees, temporary `.gpd` projects, generated distributions, and fixture corpora that act like additional graph node families even though they are not committed canonical source files

### 6c. Edge Taxonomy Gaps

The second-wave audit identified two additional edge classes that still are not modeled cleanly:

- `decorator-runtime`: where files such as `src/gpd/core/observability.py` modify execution behavior in other modules without changing the import graph shape
- `count-contract`: where tests such as `tests/test_metadata_consistency.py` depend on counts, field cardinalities, or registry totals rather than direct execution flow

Without explicit modeling of:

- canonical schema objects
- serialized instances
- generated outputs
- fixture corpora
- temporary installed-layout trees

the graph still overstates its own completeness even if every committed file path were listed.

## What Is Overstated or Noisy

### 1. Path-string and mention-derived edges

Any graph that treats path mentions, include mentions, badges, or documentation references on the same footing as imports or build authority edges will overclaim precision.

Examples of weaker-than-they-look edges:

- `README.md -> .github/workflows/test.yml` via badge link
- documentation path mentions that only indicate discoverability, not execution
- prompt/spec references that are convention-based rather than mechanically loaded
- single fixed-file edges where the real dependency is an ordered candidate family selected at runtime
- edges that imply whole-tree or whole-file ownership when the tested contract is actually selective mutation or selective cleanup

### 2. `.claude/gpd-file-manifest.json` as a “hub”

This file can look like a giant high-degree node, but most of that degree is inventory membership rather than causal dependency. It should not be interpreted as a semantic hub on the same level as `src/gpd/cli.py` or `src/gpd/mcp/builtin_servers.py`.

### 3. Exact mirror semantics for `.claude/**`

“Mirror” is directionally useful, but too strong as a literal statement. The more accurate relationship is:

- canonical source asset
- transformed/materialized installed artifact
- sometimes host-shaped installed artifact with machine-specific interpreter paths or runtime state

### 4. Same-stem pairing heuristics

Command/workflow same-stem matches are helpful structure, but they are not sufficient proof of execution dependency. They should be treated as convention-backed edges unless also supported by explicit include/materialization evidence.

### 5. Count-contract edges collapsed into hard edges

If inventory-count and schema-count tests are folded into ordinary hard dependency edges, centrality will be overstated for files like `src/gpd/contracts.py`, `src/gpd/core/health.py`, and `src/gpd/registry.py`.

## Honest Calibration

The graph should be described as:

- an observed-and-inferred file dependency atlas
- strong on canonical in-repo import and authority chains
- medium on prompt/spec/reference structure
- weaker on policy, semantics, runtime I/O, candidate-set path resolution, external tools, generated outputs, and object-level behavior

It should **not** be described as:

- a complete graph of all repo file dependencies
- a complete graph of all object dependencies
- a purely “clean” directed graph without confidence tiers

## Recommended Corrections To The Graph Method

### Required

- separate edge types by confidence:
  `hard`, `materialized`, `contract`, `semantic`, `mention`
- distinguish canonical source nodes from installed/generated mirror nodes
- model directory-wide policy edges explicitly:
  `.github/workflows/test.yml -> tests/**`
- model transformed artifact lineage separately from exact mirrors
- represent runtime-home and cache artifacts as external nodes instead of silently omitting them
- model ordered candidate-set edges and precedence rules explicitly
- model runtime input schemas separately from file edges where hooks depend on stdin event payloads
- distinguish schema nodes from serialized-file nodes and generated-output nodes
- model partial-ownership relationships for shared runtime trees and shared config files

### Strongly recommended

- add file-I/O extraction for `read_text`, `write_text`, `glob`, `rglob`, manifest writes, and config writes
- add subprocess/external-tool edges for the paper pipeline and installers
- add command-activated lazy edges from `src/gpd/cli.py`
- add release-contract edges from tests to public metadata files
- downweight badge links and other weak documentation references
- add schema/serialization edges for Pydantic and dataclass models that are persisted, rendered, or round-tripped in tests
- add generated-node families for `dist/**`, paper manifests, bibliography audit outputs, state backups, and synthetic install trees created by tests
- add package-data edges for template directories loaded via `importlib.resources`
- add external Python package nodes separately from external system-binary nodes
- add `decorator-runtime` and `count-contract` edge types

### Needed for any true “all objects” claim

- build a Python object graph:
  functions, methods, classes, inheritance, calls, and shared dataclasses/models
- distinguish static references from dynamic execution paths
- include mutation ownership for `.gpd/state.json`, `STATE.md`, conventions, results, and manifest files
- model logical identity across canonical schema object, serialized form, generated output, mirrored install artifact, and fixture copy

## Final Assessment

The current graphing effort is valuable, but it is not complete.

My best current calibration is:

- high confidence for core packaging/install/descriptor authority chains
- medium confidence for prompt/spec/reference topology
- medium confidence for broad test-to-source relationships
- low confidence for full runtime, candidate-set resolution, external-tool, policy, and object-level completeness

If the goal is an honest repo-wide dependency atlas, the work is already useful.

If the goal is a literally complete directed graph of **all** file and object interdependencies, the answer is no: more extraction work is still required.

Static ceiling conclusion:

- After the fourth wave, the graph appears close to the practical static-analysis ceiling for this worktree.
- The remaining uncertainty is now concentrated in dynamic runtime state, environment-specific external nodes, precedence-dependent candidate sets, and branch-conditional execution that static inspection cannot fully resolve.
- That means the graph is now substantially stronger than before, but "absolutely complete" is still not a defensible claim unless those dynamic/runtime branches are exercised, not just read.

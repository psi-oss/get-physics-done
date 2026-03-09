# GPD Package Architecture

GPD (Get Physics Done) is a unified physics research orchestration package. It provides state management, convention enforcement, verification checks, multi-runtime install adapters, MCP tool servers, and a CLI.

---

## Package Layout

```
├── pyproject.toml              # Package metadata, entry points, dependencies
├── ARCHITECTURE.md             # This file
├── src/gpd/
│   ├── __init__.py             # Package root — re-exports __version__
│   ├── version.py              # importlib.metadata version reader
│   ├── contracts.py            # Inlined contract types (ConventionLock, GPDConfig, etc.)
│   ├── registry.py             # Content registry — parses commands/, agents/, specs/
│   ├── ablations.py            # Feature flag ablation system (env var overrides, guards)
│   ├── cli.py                  # `gpd` CLI (typer) — state, phase, health commands
│   │
│   ├── core/                   # Layer 1 — pure state management (~14k LOC)
│   │   ├── state.py            # STATE.md parser/renderer, JSON sync, atomic writes
│   │   ├── phases.py           # Phase/roadmap/milestone management, wave validation
│   │   ├── conventions.py      # Convention lock (18 physics fields + custom)
│   │   ├── results.py          # Intermediate results with BFS dependency graphs
│   │   ├── health.py           # 11-check diagnostic dashboard
│   │   ├── query.py            # Cross-phase dependency tracing
│   │   ├── frontmatter.py      # YAML frontmatter CRUD + verification suite
│   │   ├── patterns.py         # Error pattern library (8 categories, 13 domains)
│   │   ├── extras.py           # Approximations, uncertainties, questions
│   │   ├── context.py          # Context assembly for AI agents
│   │   ├── suggest.py          # Next-action intelligence
│   │   ├── config.py           # Multi-runtime config, model tiers
│   │   ├── model_defaults.py   # GPD_MODEL / GPD_FAST_MODEL env var defaults
│   │   ├── verification_checks.py # Standalone verification check endpoints
│   │   ├── trace.py            # JSONL execution tracing
│   │   ├── constants.py        # Named constants for domain values
│   │   ├── utils.py            # Pure utility functions
│   │   ├── errors.py           # Exception hierarchy (GPDError base)
│   │   ├── observability.py    # Feature flags, Logfire spans, metrics
│   │   └── commands.py         # CLI command implementations
│   │
│   ├── adapters/               # Layer 2 — multi-runtime install system (~3.7k LOC)
│   │   ├── base.py             # RuntimeAdapter ABC + template method install()
│   │   ├── claude_code.py      # Claude Code adapter
│   │   ├── codex.py            # OpenAI Codex adapter
│   │   ├── gemini.py           # Google Gemini CLI adapter
│   │   ├── opencode.py         # OpenCode adapter
│   │   ├── install_utils.py    # Pure-stdlib install helpers (~1.1k LOC)
│   │   └── tool_names.py       # Canonical → runtime tool name translation tables
│   │
│   ├── mcp/                    # Layer 2 — MCP servers + orchestration (~11k LOC)
│   │   ├── servers/            # 7 MCP tool servers (conventions, verification, etc.)
│   │   ├── discovery/          # Tool discovery: catalog, router, selector, reconciler, fallback, sources
│   │   ├── research/           # Research planner, cost estimator, error recovery
│   │   ├── paper/              # Paper generation: bibliography, compiler, figures, templates
│   │   ├── session/            # Session manager, models, search
│   │   ├── subagents/          # Subagent orchestration: SDK, specialist, MCP builder, cost estimator
│   │   ├── gpd_bridge/         # Bridge for external GPD version discovery
│   │   ├── viewer/             # Web viewer (FastAPI, optional)
│   │   ├── cli.py              # `gpd+` CLI entry point
│   │   ├── config.py           # MCP configuration
│   │   ├── pipeline.py         # Pipeline integration
│   │   ├── launch.py           # Launch prompt generation
│   │   ├── history.py          # Session history
│   │   └── signal_handler.py   # Graceful shutdown
│   │
│   ├── utils/                  # Shared utilities (effort mapping, LaTeX, MCP registry, paths)
│   ├── hooks/                  # Runtime hooks (statusline, update check, Codex notify)
│   ├── commands/               # ~56 command .md files with YAML frontmatter
│   ├── agents/                 # 17 agent .md files with YAML frontmatter
│   └── specs/                  # Bundled spec content (agents, skills, references, etc.)
│
└── tests/
    ├── core/                   # Core module tests
    ├── adapters/               # Adapter + install roundtrip tests
    ├── hooks/                  # Hook tests
    ├── mcp/                    # MCP server tests
    └── test_*.py               # Discovery, paper, session, subagents tests
```

---

## Layers and Dependency Rules

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Adapters + MCP                                    │
│  gpd.adapters.*  →  gpd.registry, gpd.core.observability   │
│  gpd.mcp.*       →  gpd.contracts, pydantic-ai, gpd.core  │
│                  →  gpd.adapters (launch.py only)           │
└─────────────────────────────────────────────────────────────┘
        │  uses
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Core (pure domain)                                │
│  gpd.core.*      →  gpd.contracts (GPDConfig, ConventionLock)│
│                  →  logfire (spans/metrics only)            │
│                  →  pydantic (models), PyYAML               │
└─────────────────────────────────────────────────────────────┘
        │  uses
┌─────────────────────────────────────────────────────────────┐
│  Layer 0: Content (no Python imports)                       │
│  gpd.commands/*.md, gpd.agents/*.md, gpd.specs/**           │
└─────────────────────────────────────────────────────────────┘
```

**Dependency rules:**

1. `core/` modules import only: stdlib, `logfire`, `pydantic`, `PyYAML`, `gpd.contracts`. No PydanticAI, no MCP.
2. `adapters/install_utils.py` is **pure stdlib** — no external deps at all.
3. `adapters/` import `gpd.registry` and `gpd.core.observability` but never `gpd.mcp`.
4. `mcp/` may import `gpd.core.*` and `gpd.adapters.*`.
5. No circular imports between layers. Layer N may only import from Layer N-1 or lower.

---

## Content Registry (`registry.py`)

Single source of truth for all GPD content discovery. Parses markdown files with YAML frontmatter once, caches results for the process lifetime.

**Content locations** (priority order — later overrides earlier):

| Content Type | Legacy Location    | Primary Location | Parsed Into  |
|-------------|--------------------|------------------|-------------|
| Agents      | `specs/agents/*.md`| `agents/*.md`    | `AgentDef`  |
| Commands    | `specs/skills/*/SKILL.md` | `commands/*.md` | `CommandDef` |

**Public API:**
- `list_agents()` / `get_agent(name)` — agent discovery
- `list_commands()` / `get_command(name)` — command discovery
- `invalidate_cache()` — clear after install/uninstall

All consumers (adapters, CLI, MCP) use the registry — no direct file parsing.

---

## Install System

### Template Method Pattern

`RuntimeAdapter.install()` implements a template method with 10 hooks:

```
install(gpd_root, target_dir, is_global)
  → _validate(gpd_root)              # package integrity check
  → _compute_path_prefix(...)         # global vs local path prefix
  → _pre_cleanup(target_dir)          # remove stale patches, save local mods
  → _install_commands(...)             # runtime-specific command generation
  → _install_content(...)              # copy specs/ → get-physics-done/
  → _install_agents(...)               # runtime-specific agent generation
  → _install_version(...)              # write VERSION file
  → _install_hooks(...)                # copy hook scripts
  → _configure_runtime(...)            # runtime-specific settings (statusline, etc.)
  → _write_manifest(...)               # SHA-256 file manifest for modification detection
  → _verify(target_dir)               # post-install verification
```

Subclasses override individual hooks as needed.

### Supported Runtimes

| Runtime           | Adapter Class              | Config Dir  | Commands Format       | Agents Format       |
|-------------------|---------------------------|-------------|----------------------|---------------------|
| Claude Code       | `ClaudeCodeAdapter`       | `.claude`   | `commands/gpd/*.md`  | `agents/gpd-*.md`   |
| OpenAI Codex      | `CodexAdapter`            | `.codex`    | Skills in `~/.agents/skills/gpd-*/` | `agents/gpd-*.md` |
| Google Gemini CLI | `GeminiAdapter`           | `.gemini`   | `commands/gpd/*.md`  | `agents/gpd-*.md`   |
| OpenCode          | `OpenCodeAdapter`         | `.opencode` | `commands/gpd/*.md`  | `agents/gpd-*.md`   |

### Tool Name Translation

`tool_names.py` defines canonical GPD tool names (e.g., `file_read`, `shell`, `search_files`) and maps them to each runtime's equivalents. The `canonical()` function normalizes legacy Claude Code names (`Read` → `file_read`).

### Install Utilities (`install_utils.py`)

Pure-stdlib helpers shared across all adapters:
- Path prefix computation (global vs local)
- JSONC parsing (settings files with comments)
- Settings I/O (atomic write with temp+rename)
- `@include` expansion (for runtimes that do not resolve them natively)
- File manifest generation (SHA-256 hashes for modification detection)
- Local patch backup/restore
- Orphaned file cleanup
- Hook command building

---

## Feature Flags and Ablation System

### Flag Hierarchy

Every GPD component has a feature flag in `core/observability.py`:

```
gpd.enabled                          # master kill switch
├── gpd.conventions.enabled
│   ├── gpd.conventions.commit_gate
│   ├── gpd.conventions.assert_check
│   └── gpd.conventions.drift_detection
├── gpd.verification.enabled
│   ├── gpd.verification.checks.dimensional
│   ├── gpd.verification.checks.limiting_cases
│   ├── gpd.verification.checks.symmetry
│   ├── gpd.verification.checks.conservation
│   ├── gpd.verification.checks.numerical
│   ├── gpd.verification.checks.sign_convention
│   └── gpd.verification.checks.index_consistency
├── gpd.protocols.enabled
│   └── gpd.protocols.checkpoint_enforcement
├── gpd.errors.enabled
│   └── gpd.errors.classification
├── gpd.patterns.enabled
│   └── gpd.patterns.cross_project
└── gpd.diagnostics.*
```

Parent flags short-circuit children: if `gpd.enabled` is False, everything is off.

### Flag Resolution Priority

```
env vars (GPD_FLAG_*) > YAML overrides > GPDConfig (contracts) > local config > preset > defaults
```

### Ablation Points (`ablations.py`)

Simplified env var interface on top of feature flags:

```bash
GPD_DISABLE_CONVENTIONS=1    # disables all convention enforcement
GPD_DISABLE_VERIFICATION=1   # disables all verification checks
GPD_DISABLE_GPD=1            # master kill switch
```

Guards for use in code:

```python
@guarded("gpd.verification.checks.dimensional", default=[])
def check_dimensions(equations): ...

with ablation_guard("gpd.conventions.commit_gate") as active:
    if not active:
        return []
```

### Ablation Presets

| Preset                | Description                                         |
|-----------------------|-----------------------------------------------------|
| `gpd_full`            | All components enabled                              |
| `gpd_off`             | All components disabled                             |
| `gpd_verification_only` | Only verification, no conventions/patterns        |
| `gpd_conventions_only`  | Only conventions, no verification/patterns         |
| `gpd_exploratory`      | Lighter verification for exploratory research      |

---

## Model Selection

GPD uses a two-tier, provider-agnostic model system. All LLM calls go through PydanticAI `Agent()` with model IDs in `provider:model-name` format.

### Default Model Constants (`core/model_defaults.py`)

Two module-level constants serve as the single source of truth:

| Constant                | Env Var Override  | Default                                   | Usage                                    |
|-------------------------|-------------------|-------------------------------------------|------------------------------------------|
| `GPD_DEFAULT_MODEL`     | `GPD_MODEL`       | `anthropic:claude-sonnet-4-5-20250929`    | Primary model — agents, planning, paper  |
| `GPD_DEFAULT_FAST_MODEL`| `GPD_FAST_MODEL`  | `anthropic:claude-haiku-4-5-20251001`     | Cheap/fast — curation, triage, classify  |

Layer 1 code: stdlib `os.environ.get()` only, no external imports.

### Multi-Provider Usage

Model IDs follow PydanticAI's `provider:model-name` format. Switch providers by setting the env var:

```bash
# Anthropic (default)
GPD_MODEL=anthropic:claude-sonnet-4-5-20250929

# OpenAI
GPD_MODEL=openai:gpt-4o

# Google
GPD_MODEL=google-gla:gemini-2.5-pro
```

All GPD agents accept these IDs through PydanticAI, which handles provider-specific API differences.

### Consumers

**`GPD_DEFAULT_MODEL`** (sonnet-tier):
- `mcp/discovery/` — router, selector
- `mcp/paper/` — paper generator
- `mcp/research/` — error recovery, planner
- `mcp/subagents/` — tool spec builder

### Config-Based Model Resolution (`core/config.py`)

For project-level customization, `GPDProjectConfig` (loaded from `.planning/config.json`) provides a profile-based tier system:

```
resolve_model(project_dir, agent_name)
  → load_config()               # reads .planning/config.json
  → resolve_agent_tier()        # profile × agent → ModelTier (tier-1/2/3)
  → config.model_map lookup     # optional: tier → concrete model ID
```

**Resolution priority**: `config.model_map[tier]` > tier string (e.g., `"tier-1"`)

**Model profiles** control tier assignments per agent. 16 agents × 5 profiles:

| Profile          | High-tier agents                          | Low-tier agents                    |
|------------------|-------------------------------------------|------------------------------------|
| `deep-theory`    | planner, debugger, verifier, consistency  | theory-mapper, notation-coordinator|
| `numerical`      | planner, phase-researcher, debugger       | theory-mapper, bibliographer       |
| `exploratory`    | planner, phase-researcher, lit-reviewer   | theory-mapper, notation-coordinator|
| `review`         | planner, debugger, verifier, referee      | project-researcher, phase-researcher|
| `paper-writing`  | planner, paper-writer, referee, bibliographer | project-researcher, experiment-designer |

**Example `.planning/config.json`:**

```json
{
  "model_profile": "deep-theory",
  "model_map": {
    "tier-1": "anthropic:claude-sonnet-4-5-20250929",
    "tier-2": "openai:gpt-4o-mini",
    "tier-3": "google-gla:gemini-2.0-flash"
  }
}
```

### Reasoning Effort

Model specs encode effort as a suffix: `"openai:gpt-5.2-low"`, `"anthropic:claude-sonnet-4-5-high"`. The `gpd.utils.effort` module (inlined standalone, no external dependency) handles provider-specific translation:

```python
from gpd.utils.effort import parse_model_spec, effort_to_model_settings

provider, base, effort = parse_model_spec("openai:gpt-5.2-low")
if effort:
    settings = effort_to_model_settings(provider, base, effort)
    result = await agent.run(prompt, model_settings=settings)
```

Provider-specific output:
- **OpenAI**: `{"openai_reasoning_effort": "low"}`
- **Anthropic**: `{"anthropic_thinking": {"type": "enabled", "budget_tokens": N}}`
- **Google**: `{"google_thinking_config": {"thinking_level": "low"}}`

**Never** set `reasoning_effort` directly — it only works for OpenAI and silently fails for other providers.

### Bundle Overlay Configuration

Bundle overlays layer domain-specific specs (actors, actions, skills) on top of a base bundle. The overlay name determines which subdirectory under `specs/` to load. The default overlay is `["physics"]`, configured via `GPDConfig.bundle_overlays`.

| Source                       | Format                          | Example                          |
|------------------------------|---------------------------------|----------------------------------|
| `GPDConfig.bundle_overlays`  | `list[str]` field in contracts  | `["physics"]`                    |
| `GPD_BUNDLE_OVERLAYS` env    | Comma-separated string          | `"physics,astro"`                |
| Default                      | —                               | `["physics"]`                    |

Overlays are merged sequentially: base → overlay₁ → overlay₂. Merge rules:
- Actor prompts: base system prompt + overlay extensions (appended)
- Action specs: deep merge (overlay fields override base, lists concatenated)
- Skills: union (overlay additions merged in)
- Config: overlay values override base

---

## MCP Servers

7 MCP tool servers, each a standalone process registered in `pyproject.toml` scripts:

| Server                  | Entry Point                | Provides                              |
|------------------------|---------------------------|---------------------------------------|
| `gpd-mcp-conventions`  | `conventions_server:main`  | Convention lock CRUD, drift detection |
| `gpd-mcp-verification` | `verification_server:main` | Physics verification checks           |
| `gpd-mcp-protocols`    | `protocols_server:main`    | Protocol enforcement, checkpoints     |
| `gpd-mcp-errors`       | `errors_mcp:main`          | Error classification, pattern matching|
| `gpd-mcp-patterns`     | `patterns_server:main`     | Error pattern library                 |
| `gpd-mcp-state`        | `state_server:main`        | STATE.md read/write                   |
| `gpd-mcp-skills`       | `skills_server:main`       | Skill/command discovery               |

---

## Error Hierarchy

All GPD exceptions inherit from `GPDError`:

```
GPDError
├── ValidationError(ValueError)
├── StateError(ValueError)
├── ConventionError(ValueError)
├── LoaderError
├── ResultError(ValueError)
│   ├── ResultNotFoundError(KeyError)
│   └── DuplicateResultError(ValueError)
├── QueryError(ValueError)
├── ExtrasError(ValueError)
│   └── DuplicateApproximationError(ValueError)
├── PatternError
├── TraceError
├── ConfigError(ValueError)
├── BundleError
├── PhaseError (in phases.py)
│   ├── PhaseNotFoundError
│   ├── PhaseValidationError
│   ├── PhaseIncompleteError
│   ├── RoadmapNotFoundError
│   └── MilestoneIncompleteError
├── FrontmatterParseError(ValueError)
├── FrontmatterValidationError(ValueError)
└── FeatureFlagError (in observability.py)
    ├── UnknownPresetError
    └── FlagNotInitializedError
```

Domain errors also inherit from their stdlib counterpart (`ValueError`, `KeyError`) for backwards compatibility.

---

## Observability

`core/observability.py` provides:
- **Logfire spans**: `gpd_span(name, **attrs)` creates spans with `gpd.` prefix
- **Metrics**: 6 pre-built counters (`gpd_checks_run`, `gpd_checks_passed`, `gpd_checks_failed`, `gpd_convention_violations`, `gpd_overhead_tokens`, `gpd_overhead_cost_usd`)
- **Instrumentation decorator**: `@instrument_gpd_function("name")` wraps sync/async functions
- All adapter install/uninstall flows emit Logfire spans

---

## CLI Entry Points

| Command    | Module         | Description                                      |
|-----------|----------------|--------------------------------------------------|
| `gpd`     | `gpd.cli`      | Core CLI: state, phase, health, conventions      |
| `gpd+`    | `gpd.mcp.cli`  | MCP orchestration CLI                            |

---

## How to Add a New Adapter

1. Create `src/gpd/adapters/my_runtime.py`
2. Subclass `RuntimeAdapter`
3. Implement required abstract properties: `runtime_name`, `display_name`, `config_dir_name`, `help_command`
4. Implement required abstract methods: `translate_tool_name()`, `generate_command()`, `generate_agent()`, `generate_hook()`
5. Override template method hooks as needed (e.g., `_install_commands`, `_install_agents`, `_configure_runtime`)
6. Add tool name mappings in `tool_names.py`
7. Register in `adapters/__init__.py` `_ensure_loaded()` function
8. Add install roundtrip tests in `tests/adapters/`


---

## Testing

```bash
uv run pytest -v          # all GPD tests
uv run pytest tests/core/  # core only
uv run pytest tests/adapters/ # adapters only
```

Test organization mirrors source:
- `tests/core/` — state, phases, conventions, config, health, etc.
- `tests/adapters/` — per-adapter tests + install roundtrip suite
- `tests/hooks/` — hook tests (statusline, update check, runtime detect)
- `tests/mcp/` — MCP server tests
- `tests/test_*.py` — discovery, paper, session, subagents tests

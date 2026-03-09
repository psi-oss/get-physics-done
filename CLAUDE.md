# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest -v

# Run specific test file or directory
uv run pytest tests/core/test_state.py -v
uv run pytest tests/adapters/ -v

# Run tests matching a keyword
uv run pytest -k "test_phase" -v

# Run only integration tests (requires external services)
uv run pytest -m integration -v

# Lint
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/

# Format
uv run ruff format src/ tests/

# Type check (if needed)
uv run pyright src/

# CLI entry points
uv run gpd --help        # Core CLI
uv run gpd+ --help       # MCP orchestration CLI
```

## Architecture

GPD (Get Physics Done) is an autonomous physics research orchestration system. It enables AI agents to formalize, plan, execute, and verify physics research. Python 3.11+, built with Hatchling, managed with uv.

### Three-Layer Architecture

```
Layer 2: adapters/ + mcp/     — Multi-runtime install, MCP servers, agent orchestration
Layer 1: core/                — Pure domain logic (state, phases, conventions, verification)
Layer 0: commands/ + agents/  — YAML-frontmatter Markdown content (no Python)
```

**Strict dependency rules:**
- `core/` imports only: stdlib, logfire, pydantic, PyYAML, `gpd.contracts`
- `adapters/install_utils.py` is pure stdlib — zero external deps
- `adapters/` imports `gpd.registry` and `gpd.core.observability`, never `gpd.mcp`
- `mcp/` may import `core/` and `adapters/`
- No circular imports; Layer N only imports Layer N-1 or lower

### Key Modules

- **`contracts.py`** — Pydantic models: `ConventionLock` (18 physics fields), `GPDConfig`
- **`registry.py`** — Content registry; discovers agents/commands from frontmatter `.md` files, caches for process lifetime. All consumers use the registry, never parse files directly.
- **`core/state.py`** — Dual-write STATE.md ↔ state.json with atomic writes and file locking
- **`core/phases.py`** — Phase/roadmap/milestone lifecycle and wave validation
- **`core/conventions.py`** — 18-field convention lock system
- **`core/errors.py`** — `GPDError` exception hierarchy (all inherit from stdlib counterparts)
- **`core/observability.py`** — Hierarchical feature flags, Logfire spans, metrics
- **`ablations.py`** — Simplified env-var ablation interface (`GPD_DISABLE_*`)
- **`adapters/base.py`** — `RuntimeAdapter` ABC with template method `install()` (10 hooks)
- **`adapters/tool_names.py`** — Canonical → runtime tool name translation

### Adapters (Multi-Runtime Support)

Template method pattern in `RuntimeAdapter.install()`. Four runtimes: Claude Code (`.claude`), OpenAI Codex (`.codex`), Google Gemini CLI (`.gemini`), OpenCode (`.opencode`). Each adapter overrides hooks for runtime-specific behavior.

### MCP Servers (7 standalone)

Located in `mcp/servers/`: conventions, verification, protocols, errors, patterns, state, skills. Each runs as a separate FastMCP process with its own CLI entry point (`gpd-mcp-*`).

### Content System

- **`commands/*.md`** (~58 files) — YAML frontmatter commands parsed into `CommandDef`
- **`agents/*.md`** (17 files) — YAML frontmatter agent specs parsed into `AgentDef`
- **`specs/`** — Bundled content: base bundle, physics overlay, templates, schemas, workflows

## Code Conventions

- **Line length:** 120 chars
- **Ruff rules:** E, W, F, I, B, C4, UP, TID251 (E501 ignored)
- **Async:** pytest-asyncio with `asyncio_mode = "auto"`
- **CLI:** typer with custom `_GPDTyper` subclass that catches `GPDError` for user-friendly output
- **Models:** Use `GPD_MODEL` / `GPD_FAST_MODEL` env vars to override defaults; model IDs follow PydanticAI format (`provider:model-name`)

# Contributing to GPD

Thanks for helping improve Get Physics Done.

GPD is published by Physical Superintelligence PBC (PSI) as an open-source community contribution for physics research workflows. We welcome fixes, tests, documentation improvements, and carefully scoped feature work.

## Before You Start

- Search existing issues and pull requests before opening a new one.
- For non-trivial changes, open an issue or discussion first so the implementation direction is clear.
- Keep changes tightly scoped. Small, reviewable pull requests are strongly preferred.

## Development Setup

```bash
uv sync --dev
source .venv/bin/activate
```

Useful checks:

```bash
uv build
npm_config_cache="$(mktemp -d)" npm pack --dry-run --json
uv run pytest tests/test_metadata_consistency.py -v
uv run pytest tests/test_release_consistency.py -v
uv run pytest tests/adapters/test_registry.py tests/adapters/test_install_roundtrip.py -v
uv run pytest tests/core/test_cli.py -v
uv run pytest tests/ -v
```

Cross-runtime release checks:

- `tests/adapters/test_registry.py` and `tests/adapters/test_install_roundtrip.py` cover install-time translation across Claude Code, Gemini CLI, Codex, and OpenCode.
- `tests/core/test_cli.py` covers the public `gpd` CLI surface.
- `tests/test_metadata_consistency.py` covers public docs, inventory counts, and CLI/registry metadata alignment.
- `tests/test_release_consistency.py` covers the public install flow, release artifacts, and release-facing messaging.
- `uv build` validates the published Python wheel and sdist.
- `npm pack --dry-run --json` validates the published `npx` bootstrap package surface before release. Use a temporary cache outside the repo so the worktree does not gain a local `.npm-cache/`.
- Gemini installs are expected to be complete on disk after `GeminiAdapter.install()`: `.gemini/settings.json` should already exist with `experimental.enableAgents`, GPD hooks, and GPD MCP servers configured.

## Release-Facing Guardrails

- Public install docs should use `npx -y get-physics-done`.
- Do not reintroduce stale internal paths such as `packages/gpd` into docs or descriptors.
- Keep public artifacts present and up to date: `README.md`, `LICENSE`, `CITATION.cff`, `CONTRIBUTING.md`, `package.json`, and `pyproject.toml`.
- Keep the `tests` workflow pinned to the minimum supported Python version (`3.11`) unless we intentionally broaden CI coverage.
- Keep `infra/gpd-*.json` synced with the canonical descriptor builder in `src/gpd/mcp/builtin_servers.py`.
- Keep user-facing validation docs aligned with the CLI surface in `gpd validate`, especially `consistency`, `review-preflight`, `paper-quality`, `referee-decision`, and `reproducibility-manifest`.
- Do not commit secrets, private infrastructure details, internal strategy notes, or cached research outputs.

## Pull Request Checklist

- `main` is protected: direct pushes are blocked, and pull requests must pass the required `tests` workflow before merge.
- Add or update tests when behavior changes.
- Update public docs when install flow, commands, or release messaging changes.
- Keep commit messages concise and descriptive.

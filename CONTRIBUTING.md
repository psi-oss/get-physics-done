# Contributing to GPD

Thanks for helping improve Get Physics Done.

GPD is published by Physical Superintelligence PBC (PSI) as an open-source community contribution for physics research workflows. We welcome fixes, tests, documentation improvements, and carefully scoped feature work.

## Contributor License Agreement (CLA)

All contributors must sign a CLA before their pull requests can be merged.

**Individual contributors:** Sign the CLA at https://cla-assistant.io/psi-oss/get-physics-done — the CLA Assistant bot will prompt you automatically when you open a pull request.

**Corporate contributors** (if your employer owns your IP): Download [GPD_CLA_Corporate.pdf](CLA/GPD_CLA_Corporate.pdf), sign it, and email it to legal@psi.inc.

## Before You Start

- Search existing issues and pull requests before opening a new one.
- For non-trivial changes, open an issue or discussion first so the implementation direction is clear.
- Keep changes tightly scoped. Small, reviewable pull requests are strongly preferred.

## Development Setup

```bash
uv sync --dev
source .venv/bin/activate
uv tool install pre-commit
pre-commit install
```

## Local CLI From This Checkout

Prefer `uv run` from the repo root when you want the local CLI without relying
on a separately installed `gpd` executable.

```bash
uv run gpd --help
uv run gpd install <runtime> --local
```

Use `codex`, `claude`, `gemini`, or `opencode` for `<runtime>`. After
`uv sync --dev`, an activated `.venv` can also run `gpd ...` directly.

The tracked pre-commit hook runs `uv run ruff check --fix --unsafe-fixes` on staged Python files.

## Contributor License Agreements

Before we can accept a contribution, you must complete the applicable CLA:

- Individual contributors should review `CLA/GPD_CLA_Individual.pdf`; signing is handled automatically via the CLA Assistant GitHub flow at https://cla-assistant.io/psi-oss/get-physics-done
- Corporate contributors, or contributors whose employer owns their IP, should review `CLA/GPD_CLA_Corporate.pdf` and email the signed PDF to legal@psi.inc
- Corporate CLA submissions are collected manually and should be logged by the owner of contributor agreement tracking, Ted Grace
- If your employer owns the intellectual property for your work, use the corporate CLA flow instead of the individual one

Useful checks:

```bash
uv build
npm_config_cache="$(mktemp -d)" npm pack --dry-run --json
pre-commit run --all-files
python scripts/sync_repo_graph_contract.py
uv run pytest tests/test_metadata_consistency.py -v
uv run pytest tests/test_release_consistency.py -v
uv run pytest tests/adapters/test_registry.py tests/adapters/test_install_roundtrip.py -v
uv run pytest tests/core/test_cli.py -v
uv run pytest tests/ -v
HEAVY_SUITE_IGNORE_ARGS="$(uv run python - <<'PY'
from tests.conftest import complementary_heavy_suite_ignore_args
print(' '.join(complementary_heavy_suite_ignore_args()))
PY
)" uv run pytest tests/ -v --full-suite $HEAVY_SUITE_IGNORE_ARGS
```

Cross-runtime release checks:

- `tests/adapters/test_registry.py` and `tests/adapters/test_install_roundtrip.py` cover install-time translation across Claude Code, Gemini CLI, Codex, and OpenCode.
- `tests/core/test_cli.py` covers the public `gpd` CLI surface.
- `tests/test_metadata_consistency.py` covers public docs, inventory counts, and CLI/registry metadata alignment.
- `tests/test_release_consistency.py` covers the public install flow, release artifacts, and release-facing messaging.
- `uv build` validates the published Python wheel and sdist.
- `npm pack --dry-run --json` validates the published `npx` bootstrap package surface before release. Use a temporary cache outside the repo so the worktree does not gain a local `.npm-cache/`.
- Gemini installs are expected to be complete on disk after `GeminiAdapter.install()`: `.gemini/settings.json` should already exist with `experimental.enableAgents`, GPD hooks, GPD MCP servers, and `policyPaths` configured, and `policies/gpd-auto-edit.toml` should already be present.
- OpenCode installs are expected to leave `opencode.json` complete on disk with GPD-managed `permission.read` / `permission.external_directory` entries and built-in MCP servers under the `mcp` key.

## Release-Facing Guardrails

- Public install docs should use `npx -y get-physics-done`.
- Do not reintroduce stale internal paths such as `packages/gpd` into docs or descriptors.
- Keep public artifacts present and up to date: `README.md`, `LICENSE`, `CITATION.cff`, `CONTRIBUTING.md`, `package.json`, and `pyproject.toml`.
- Keep the `tests` workflow pinned to the minimum supported Python version (`3.11`) unless we intentionally broaden CI coverage.
- Keep `infra/gpd-*.json` synced with the canonical descriptor builder in `src/gpd/mcp/builtin_servers.py`.
- Keep user-facing validation docs aligned with the CLI surface in `gpd validate`, especially `consistency`, `project-contract`, `review-preflight`, `paper-quality`, `referee-decision`, and `reproducibility-manifest`.
- Do not commit secrets, private infrastructure details, internal strategy notes, or cached research outputs.

## Pull Request Checklist

- `main` is protected: direct pushes are blocked, and pull requests must pass the required `tests` workflow before merge.
- Feature and fix PRs must not bump package versions or publish releases.
- Add public release notes under `## vNEXT` in `CHANGELOG.md` so the release workflows can prepare the next tagged release from reviewed notes.
- Add or update tests when behavior changes.
- Update public docs when install flow, commands, or release messaging changes.
- Keep commit messages concise and descriptive.

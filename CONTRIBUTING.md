# Contributing to GPD

Thanks for helping improve Get Physics Done.

GPD is published by Physical Superintelligence (PSI) as an open-source community contribution for physics research workflows. We welcome fixes, tests, documentation improvements, and carefully scoped feature work.

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
uv run pytest tests/test_release_consistency.py -v
uv run pytest tests/core/test_cli.py tests/test_cli.py -v
uv run pytest tests/ -v
```

## Release-Facing Guardrails

- Public install docs should use `npx github:physicalsuperintelligence/get-physics-done`.
- Do not reintroduce stale internal paths such as `packages/gpd` into docs or descriptors.
- Keep public artifacts present and up to date: `README.md`, `LICENSE`, `CITATION.cff`, `CONTRIBUTING.md`, `package.json`, and `pyproject.toml`.
- Do not commit secrets, private infrastructure details, internal strategy notes, or cached research outputs.

## Pull Request Checklist

- Add or update tests when behavior changes.
- Update public docs when install flow, commands, or release messaging changes.
- Keep commit messages concise and descriptive.

## Security

If you find a security issue, do not open a public issue. Email [security@getphysicsdone.com](mailto:security@getphysicsdone.com).

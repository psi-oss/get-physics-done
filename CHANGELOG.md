# Changelog

All notable changes to Get Physics Done are documented here.

## vNEXT

- Add result-consistency health check that cross-validates `state.json` intermediate results against SUMMARY.md `provides` frontmatter and warns on mismatches, with guards against empty-string false matches, short-string over-matching, and malformed state records.
- Fix Windows test compatibility: cross-platform absolute paths in MCP tests, `shlex.quote`-aware assertions, `encoding="utf-8"` on `read_text()`, POSIX display paths in CLI/git_ops, permission/LaTeX/tilde/bash test portability, and schema pattern alignment.
- Split releases into a manual release-PR preparation workflow and a separate publish workflow for PyPI, npm, tags, and GitHub Releases.
- fix: use `Path.replace()` instead of `Path.rename()` for atomic settings overwrite on Windows.
<<<<<<< fix/agent-docs-positional-arg-syntax
- Fix agent docs: `approximation add` and `uncertainty add` use positional arguments, not `--name`/`--quantity` flags (agent-infrastructure.md, sensitivity-analysis.md, error-propagation.md).
=======
- Fix catastrophic state reset: `_normalize_state_schema({})` now emits the integrity sentinel that triggers backup recovery, preventing silent data loss when `state.json` contains an empty object.
>>>>>>> main

## v1.1.0

- Public open-source release.
- Multi-runtime support for Claude Code, Gemini CLI, Codex, and OpenCode.
- Structured physics research workflows for planning, execution, verification, and publication support.

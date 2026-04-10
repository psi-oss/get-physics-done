# Changelog

All notable changes to Get Physics Done are documented here.

## vNEXT

- Fix Windows test compatibility: cross-platform absolute paths in MCP tests, `shlex.quote`-aware assertions, `encoding="utf-8"` on `read_text()`, POSIX display paths in CLI/git_ops, permission/LaTeX/tilde/bash test portability, and schema pattern alignment.
- Split releases into a manual release-PR preparation workflow and a separate publish workflow for PyPI, npm, tags, and GitHub Releases.
- fix: use `Path.replace()` instead of `Path.rename()` for atomic settings overwrite on Windows.

## v1.1.0

- Public open-source release.
- Multi-runtime support for Claude Code, Gemini CLI, Codex, and OpenCode.
- Structured physics research workflows for planning, execution, verification, and publication support.

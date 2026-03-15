# Changelog

All notable changes to Get Physics Done are documented here.

Format: each release gets a `## vX.Y.Z` heading with a brief summary of changes.
The release workflow validates that the latest heading here matches the version
in `pyproject.toml` and `package.json` before publishing.

## v1.0.1

- Initial public release on npm and PyPI
- Multi-runtime support: Claude Code, Gemini CLI, Codex, OpenCode
- 22 physics research agents, 58 commands, 8 MCP servers
- Bootstrap installer with SSH-first fallback chain
- Codex notify config fix (placed at TOML root level, not inside sections)

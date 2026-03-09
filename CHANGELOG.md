# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-09

### Added

- Initial release as a standalone package.
- 56 commands covering the full physics research workflow (project setup, phase planning, execution, verification, paper generation).
- 17 specialist agents (derivation, numerical verification, literature review, dimensional analysis, and more).
- 7 MCP tool servers: conventions, verification, protocols, errors, patterns, state, skills.
- 75 skills for physics research tasks.
- Multi-runtime install adapters for Claude Code, OpenCode, Gemini CLI, and Codex.
- Experiment design system with power analysis, budget estimation, feasibility checks, and ethics review.
- Convention lock system enforcing 17 physics notation fields with drift detection.
- 11-check diagnostic health dashboard.
- Feature flag and ablation system with hierarchical flag resolution.
- MCTS strategy bridge for pipeline integration.
- Content registry with YAML frontmatter parsing and caching.
- Session management, research planner, and cost estimator.
- Paper generation pipeline with bibliography, figures, and LaTeX compilation.
- Web viewer (optional FastAPI server) for session inspection.

[0.1.0]: https://github.com/get-physics-done/get-physics-done/releases/tag/v0.1.0

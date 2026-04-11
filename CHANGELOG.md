# Changelog

All notable changes to Get Physics Done are documented here.

## vNEXT

- Fix LaTeX special character escaping in user-provided metadata fields: `~`, `#`, `%`, and `&` in title, abstract, author fields, and acknowledgments are now escaped before rendering, preventing compilation errors and silent data loss. Agent-generated LaTeX content (section bodies, figure captions, appendix content) is deliberately unaffected.
- **Breaking (raw output only):** `gpd question resolve` and `gpd calculation complete` now return structured results (resolved/completed text, search text, remaining count) instead of a bare `1`. Raw JSON output changes from `{"result": "1"}` to a model with `resolved`/`completed`, `search_text`, and `remaining` fields. The prior `{"result": "1"}` output was a bug (unhelpful) and is not considered a stable contract.
- Broaden citation regexes to detect natbib (`\citep`, `\citet`, `\citealt`, `\citealp`, `\citeauthor`, `\citeyear`, `\citetext`), capitalized (`\Cite*`), starred (`\cite*`), and biblatex (`\parencite`, `\textcite`, `\autocite`) variants across the paper-quality scorer and artifact builder. Add `check_citation_bib_coherence()` to `build_paper()` to warn when `.tex` citations and `.bib` entries are inconsistent, with `\nocite{*}` support.
- Add `check_result_consistency` health check: cross-validates `state.json` intermediate results against SUMMARY `provides` frontmatter with guards against empty-string false matches, short-string over-matching, and malformed state records.
- Fix Windows test compatibility: cross-platform absolute paths in MCP tests, `shlex.quote`-aware assertions, `encoding="utf-8"` on `read_text()`, POSIX display paths in CLI/git_ops, permission/LaTeX/tilde/bash test portability, and schema pattern alignment.
- Split releases into a manual release-PR preparation workflow and a separate publish workflow for PyPI, npm, tags, and GitHub Releases.
- fix: use `Path.replace()` instead of `Path.rename()` for atomic settings overwrite on Windows.
- Fix silent data loss in state normalization: malformed list entries (e.g., approximations with missing `name` field) now remove only the invalid entry instead of stripping the entire section.
- Add result-consistency health check that cross-validates `state.json` intermediate results against SUMMARY.md `provides` frontmatter and warns on mismatches, with guards against empty-string false matches, short-string over-matching, and malformed state records.
- Fix Windows test compatibility: cross-platform absolute paths in MCP tests, `shlex.quote`-aware assertions, `encoding="utf-8"` on `read_text()`, POSIX display paths in CLI/git_ops, permission/LaTeX/tilde/bash test portability, and schema pattern alignment.
- Split releases into a manual release-PR preparation workflow and a separate publish workflow for PyPI, npm, tags, and GitHub Releases.
- fix: use `Path.replace()` instead of `Path.rename()` for atomic settings overwrite on Windows.
- Fix agent docs: `approximation add` and `uncertainty add` use positional arguments, not `--name`/`--quantity` flags (agent-infrastructure.md, sensitivity-analysis.md, error-propagation.md).
- Fix catastrophic state reset: `_normalize_state_schema({})` now emits the integrity sentinel that triggers backup recovery, preventing silent data loss when `state.json` contains an empty object.
- Auto-migrate `ROADMAP.md` and `PROJECT.md` from workspace root into `GPD/` on first command, so files placed at the root are found by all GPD operations.
- Accept integer and float values in `depends_on` and `files_modified` frontmatter lists by coercing them to strings during validation.
- Add `--answer` flag to `gpd question resolve` so resolved questions and their answers are preserved in `state.json` and `STATE.md` instead of being silently discarded.

## v1.1.0

- Public open-source release.
- Multi-runtime support for Claude Code, Gemini CLI, Codex, and OpenCode.
- Structured physics research workflows for planning, execution, verification, and publication support.

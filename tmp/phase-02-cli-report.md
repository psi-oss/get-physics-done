# Phase 2 Report: Research Persona CLI

## Executor Scope

This executor was scoped to:

- `tmp/phase-02-cli-report.md`
- `tests/core/test_research_persona_cli_help.py`, only if a separate broad help smoke test was necessary

No source files were edited by this executor.

While this report was being prepared, separate source-writing executors added the Research Persona CLI surface and tests. This report describes the integrated tree, the safety contract, test coverage, and the Phase 2 verification result.

## Observed Files

Current Phase 2 source/test files visible in the working tree:

- `src/gpd/cli.py`
- `src/gpd/core/research_persona_cli.py`
- `tests/core/test_research_persona_cli_show_validate.py`
- `tests/core/test_research_persona_cli_privacy.py`
- `tests/core/test_research_persona_cli_mutation.py`
- `tests/core/test_research_persona_cli_support.py`
- `tests/core/test_research_persona_privacy_contract.py`

This executor changed only:

- `tmp/phase-02-cli-report.md`

No separate `tests/core/test_research_persona_cli_help.py` was added because help coverage already exists in `tests/core/test_research_persona_cli_privacy.py`.

## Implemented CLI Surface

`src/gpd/cli.py` now registers:

```text
gpd research-persona
```

Implemented wrapper commands:

- `show`
- `validate`
- `diff`
- `apply-patch`
- `forget`
- `export-capsule`

The wrapper delegates business logic to `gpd.core.research_persona_cli` and keeps Typer concerns in `src/gpd/cli.py`.

This split is the right shape for the repo: CLI parsing, stdin/file loading, `--raw` output, and `_error()` handling stay in the monolithic CLI, while persona-specific payload logic stays Typer-free and unit-testable.

## Support Adapter Resolution

The CLI wrapper calls these support handlers from `gpd.core.research_persona_cli`:

- `build_show_payload`
- `build_validate_payload`
- `build_diff_payload`
- `build_apply_patch_payload`
- `build_forget_payload`
- `build_export_capsule_payload`

The support module also keeps lower-level Typer-free helpers:

- `research_persona_show_payload`
- `research_persona_validate_payload`
- `research_persona_diff_payload`
- `research_persona_apply_patch_payload`
- `research_persona_forget_fact_payload`
- `research_persona_export_capsule_payload`

The `build_*_payload` adapters translate CLI-shaped kwargs such as `cwd`, `projection`, `document`, `input_path`, `patch_document`, `patch_path`, `fact_id`, `reason`, and `dry_run` into the lower-level support API. This keeps `src/gpd/cli.py` thin and keeps persona-specific behavior unit-testable outside Typer.

## Command Semantics

### `show`

Purpose: read and display the local persona without creating files.

Expected behavior:

- missing persona is read-only
- output includes store path, existence flag, counts, projection counts, and projection payload
- `--projection local` may show local user-visible private data
- `--projection project-private`, `--projection prompt`, and `--projection public` must use core projection rules

### `validate`

Purpose: validate a persona JSON document from file, stdin, or the stored profile.

Expected behavior:

- file input and stdin are read-only
- valid input returns `{ "valid": true, "errors": [] }`
- schema-invalid input returns structured validation failure
- invalid JSON follows existing raw CLI error behavior
- default stored-profile validation should not create a missing profile

### `diff`

Purpose: preview an explicit patch.

Expected behavior:

- reads patch JSON from file or stdin
- strict-loads any existing persona
- returns value-redacted before/after diff
- writes nothing

### `apply-patch`

Purpose: apply an explicit user-provided persona patch.

Expected behavior:

- `--dry-run` validates and previews without writing
- non-dry-run writes `profile.json`
- non-dry-run appends a history event
- tombstones embedded in the patch are appended to the tombstone ledger
- corrupt existing persona data fails closed

### `forget`

Purpose: remove a fact by id and record an erasure tombstone.

Expected behavior:

- strict-loads the existing persona
- removes the fact through a tombstone patch
- appends history and tombstone records
- does not preserve the removed fact value in the tombstone
- `--dry-run` writes nothing

### `export-capsule`

Purpose: emit a prompt-safe capsule for future workflow roles.

Supported roles:

- `planner`
- `executor`
- `verifier`
- `paper_writer`
- `literature`
- `recovery`
- `explainer`
- `doppelganger`
- `taste`

Expected behavior:

- delegates to `build_research_persona_capsule()`
- exposes only prompt-safe material
- excludes `private_local`, `project_private`, `session_only`, and `never_prompt` facts

## Safety And Approval Guarantees

Phase 2 is a manual local control plane. It must not infer persona facts from chat context, repository content, Git history, papers, shell history, or external services.

The only intended mutations are explicit:

- `apply-patch PATCH_JSON|-`
- `forget FACT_ID`

All persona writes must remain under:

```text
${GPD_DATA_DIR:-~/.gpd}/research-persona/
```

Phase 2 must not write persona content into:

- project `GPD/`
- `state.json`
- `STATE.md`
- command markdown
- agent markdown
- runtime projection catalogues
- public surface contracts

Mutation commands must use strict loading. A malformed existing local persona is not an empty persona; it is a failure that should prevent writes.

## Privacy Rules

The Phase 1 privacy labels remain authoritative:

- `session_only`
- `private_local`
- `project_private`
- `safe_to_share`
- `never_prompt`

Projection policy:

- `local`: local user view; still excludes session-only and never-prompt material according to the current core projection tests
- `project-private`: project-safe view; excludes local-only, session-only, and never-prompt material
- `prompt`: prompt-safe view; only prompt-safe material
- `public`: explicitly shareable material only

The CLI should never hand-roll these filters. It should use:

- `project_research_persona()`
- `build_research_persona_capsule()`

## Test Coverage

Existing new tests cover:

- support helper payload behavior independent of Typer
- help surface and command listing
- missing-profile `show` read-only behavior
- projection privacy boundaries
- file and stdin validation
- invalid JSON behavior
- invalid schema behavior
- prompt-safe capsules for `planner`, `explainer`, `doppelganger`, and `taste`
- `diff` write isolation
- `apply-patch --dry-run` write isolation
- `apply-patch` profile/history/tombstone writes
- `forget` profile/history/tombstone writes
- corrupt existing persona fail-closed behavior
- privacy contract narrowed to allow local CLI integration while still forbidding runtime markdown/registry/frontmatter integration

No extra help test was added because `tests/core/test_research_persona_cli_privacy.py` already asserts:

- root help includes `research-persona`
- group help includes `show`, `validate`, `apply-patch`, `diff`, `forget`, and `export-capsule`
- `export-capsule --help` includes `--role` and prompt-safe language

## Test Results

Command:

```text
uv run pytest -q -p no:cacheprovider tests/core/test_research_persona_cli_support.py tests/core/test_research_persona_cli_show_validate.py tests/core/test_research_persona_cli_mutation.py tests/core/test_research_persona_cli_privacy.py tests/core/test_research_persona_privacy_contract.py
```

Result:

```text
33 passed
```

Command:

```text
uv run pytest -q -p no:cacheprovider tests/core/test_research_persona_*.py tests/core/test_cli.py::test_help_surfaces_core_and_auxiliary_commands tests/core/test_cli.py::test_help_surfaces_public_fragments
```

Result:

```text
101 passed
```

Command:

```text
uv run pytest -q -p no:cacheprovider tests/core/test_research_persona_cli_support.py
```

Result:

```text
All checks passed
```

Command:

```text
git diff --check
```

Result:

```text
passed
```

## Risks

- Silent reset risk: mutation adapters must not call tolerant loading.
- Prompt leak risk: capsule export must only use the core capsule builder.
- Real home write risk: every CLI test must set `GPD_DATA_DIR`.
- Ledger consistency risk: a profile write without a history event weakens auditability.
- Forget semantics risk: tombstones must not preserve the sensitive deleted value.

## Next Phase Hooks

Phase 3 should build the Persona Builder as a patch-producing workflow, not as a direct profile mutator.

The Phase 2 CLI should become the backend for:

- manual candidate patches
- builder interview approval
- imported paper metadata
- collaborator/reference enrichment
- expertise updates
- taste calibration

The ambitious features should consume role capsules first:

- Researcher Doppelganger: `role="doppelganger"`
- Expertise-Aware Explanations: `role="explainer"`
- Scientific Taste Model: `role="taste"`

No future feature should receive unfiltered local persona access by default.

## Commands Run

```text
git status --short
rg -n "research-persona|research_persona|ResearchPersona|research persona" src/gpd tests tmp pyproject.toml
rg --files tests/core tmp src/gpd/core | rg "research_persona|phase-0"
git log --oneline -5
rg -n "add_typer\\(|Typer\\(|research_persona_app|research-persona|persona" src/gpd/cli.py tests/core/test_cli.py tests/helpers/cli.py
rg --files tmp tests/core | rg "phase-02|research_persona_cli"
sed -n '5330,5510p' src/gpd/cli.py
sed -n '1,620p' src/gpd/core/research_persona_cli.py
sed -n '1,260p' tests/core/test_research_persona_cli_show_validate.py
sed -n '1,260p' tests/core/test_research_persona_cli_privacy.py
sed -n '1,260p' tests/core/test_research_persona_cli_mutation.py
sed -n '1,320p' tests/core/test_research_persona_cli_support.py
uv run pytest -q -p no:cacheprovider tests/core/test_research_persona_cli_show_validate.py tests/core/test_research_persona_cli_privacy.py tests/core/test_research_persona_cli_mutation.py tests/core/test_research_persona_privacy_contract.py
uv run pytest -q -p no:cacheprovider tests/core/test_research_persona_cli_support.py
uv run pytest -q -p no:cacheprovider tests/core/test_research_persona_cli_support.py tests/core/test_research_persona_cli_show_validate.py tests/core/test_research_persona_cli_mutation.py tests/core/test_research_persona_cli_privacy.py tests/core/test_research_persona_privacy_contract.py
uv run pytest -q -p no:cacheprovider tests/core/test_research_persona_*.py tests/core/test_cli.py::test_help_surfaces_core_and_auxiliary_commands tests/core/test_cli.py::test_help_surfaces_public_fragments
uv run ruff check src/gpd/core/research_persona_cli.py src/gpd/core/research_persona.py src/gpd/cli.py tests/core/test_research_persona_*.py
git diff --check
```

# Phase 1 Foundation Report: Research Persona Core

## Scope

Phase 1 builds the core, private, strict Research Persona foundation only. It should not add runtime commands, staged workflows, new agents, prompt injection, model-profile integration, workflow presets, or generated public docs. Those belong to later phases.

The goal is to create a stable substrate for:

- strict persona/profile data models
- private machine-local storage
- patch/evidence/tombstone/history primitives
- privacy projection and prompt-safe capsules
- focused core tests

## Naming Decision

Use `research_persona` as the product and code term.

Do not use:

- `Profile` or `profile.json`, already used by `src/gpd/core/profile.py` for author/byline preferences
- `model_profile`, already a closed project config field with values such as `review`, `deep-theory`, and `paper-writing`
- `return_profile`, already used in child-return skeletons
- `workflow_preset` or `preset`
- plain `researcher` as a profile selector

Recommended names for Phase 1:

- module: `src/gpd/core/research_persona.py`
- test file: `tests/core/test_research_persona.py`
- root directory: `${GPD_DATA_DIR:-~/.gpd}/research-persona/`
- snapshot: `profile.json`
- history ledger: `history/events.jsonl`
- tombstone ledger: `tombstones/events.jsonl`

## Storage Policy

The Research Persona store is private machine-local data, not project-portable state.

Use the same data-root precedence as existing machine-local stores:

1. explicit `data_root`
2. `GPD_DATA_DIR`
3. `Path.home() / ".gpd"`

Do not write persona data to:

- `GPD/state.json`
- `GPD/STATE.md`
- `GPD/config.json`
- project artifacts/data/paper directories
- repo-root `tmp/` except for this phase report

Storage layout:

```text
${GPD_DATA_DIR:-~/.gpd}/research-persona/
  profile.json
  history/events.jsonl
  tombstones/events.jsonl
```

Mutation rules:

- reads of a missing profile return an empty default persona
- malformed existing private profile should fail closed for strict load and mutation
- writes use `file_lock` plus `atomic_write`
- POSIX files should be chmod `0o600`
- POSIX store directories should be chmod `0o700` when possible
- history/tombstone appends happen under the store lock

## Model Patterns

Follow the stricter contract style from `src/gpd/contracts.py`, not the permissive author `profile.py` style.

Use:

- `ConfigDict(validate_assignment=True, extra="forbid")` for canonical data models
- `ConfigDict(frozen=True, extra="forbid")` for parse/result/projection objects
- explicit normalizers for required strings, optional strings, string lists, literal vocabularies, and strict booleans
- schema version exactly integer `1`; reject `true`, `1.0`, strings, and future versions

Do not silently coerce:

- bool-like strings
- ints as bools
- scalar strings into lists in strict mode
- unknown top-level or nested keys

## Privacy Model

Every persona fact needs structured governance. Phase 1 should define the vocabulary even if later phases populate it.

Recommended closed vocabularies:

- confidence: `confirmed`, `inferred`, `stale`, `disputed`
- privacy: `session_only`, `private_local`, `project_private`, `safe_to_share`, `never_prompt`
- source kind: `user_statement`, `interview`, `project_scan`, `paper_import`, `bibtex_import`, `repo_scan`, `manual_patch`, `system_default`
- capsule role: `planner`, `executor`, `verifier`, `paper_writer`, `literature`, `recovery`, `explainer`, `doppelganger`, `taste`

Projection rules:

- `never_prompt` facts never appear in prompt/project/public projections
- `session_only` facts can only appear in explicit session projections, not persisted capsules
- `private_local` facts can influence local behavior only through redacted or safe fields
- `project_private` facts can appear only in explicitly project-private projections
- `safe_to_share` facts are eligible for prompt capsules
- contact/identity/collaborator/private-paper facts need explicit safety before prompt projection

The repo already enforces leakage prevention through allowlisted staged fields, `must_not_eager_load`, prompt diagnostics, typed `gpd_return`, child gates, generated-surface checks, and class-only persona summary policies. Phase 1 should follow that pattern: selected-field projection instead of broad serialization.

## Proposed Phase 1 API

Public API in `gpd.core.research_persona`:

```python
class ResearchPersonaError(ValueError): ...
class ResearchPersonaFact(BaseModel): ...
class ResearchPersonaAxis(BaseModel): ...
class ResearchPersona(BaseModel): ...
class ResearchPersonaEvidence(BaseModel): ...
class ResearchPersonaPatchOperation(BaseModel): ...
class ResearchPersonaPatch(BaseModel): ...
class ResearchPersonaTombstone(BaseModel): ...
class ResearchPersonaHistoryEvent(BaseModel): ...
class ResearchPersonaCapsule(BaseModel): ...
class ResearchPersonaValidationResult(BaseModel): ...

def research_persona_root(data_root: Path | None = None) -> Path: ...
def research_persona_path(data_root: Path | None = None) -> Path: ...
def load_research_persona(data_root: Path | None = None, *, strict: bool = False) -> ResearchPersona: ...
def save_research_persona(persona: ResearchPersona, data_root: Path | None = None) -> Path: ...
def parse_research_persona_data_strict(data: object) -> ResearchPersona: ...
def validate_research_persona(data: object) -> ResearchPersonaValidationResult: ...
def apply_research_persona_patch(persona: ResearchPersona, patch: ResearchPersonaPatch) -> ResearchPersona: ...
def append_research_persona_history(event: ResearchPersonaHistoryEvent, data_root: Path | None = None) -> Path: ...
def append_research_persona_tombstone(tombstone: ResearchPersonaTombstone, data_root: Path | None = None) -> Path: ...
def project_research_persona(persona: ResearchPersona, *, purpose: str) -> dict[str, object]: ...
def build_research_persona_capsule(persona: ResearchPersona, *, role: str) -> ResearchPersonaCapsule: ...
```

Keep the API modest enough to land in Phase 1, but include the data structures needed by later phases.

## Data Shape

The top-level persona should include:

- `schema_version`
- `facts`
- `axes`
- `standing_preferences`
- `negative_preferences`
- `tools`
- `research_areas`
- `papers`
- `collaborators`
- `references`
- `expertise`
- `workstyle`
- `scientific_taste`

All list fields should default to empty lists. A fact should carry:

- `id`
- `category`
- `value`
- `confidence`
- `privacy`
- `sources`
- `evidence_refs`
- `last_confirmed_at`
- `expires_at`

Phase 1 does not need semantic ingestion. It only needs the schema, validation, projection, and patch primitives.

## Test Plan

Add focused tests in `tests/core/test_research_persona.py`.

Required coverage:

- explicit data root, `GPD_DATA_DIR`, and home fallback path resolution
- namespaced store separate from author `profile.json`
- default empty persona
- strict schema version validation
- unknown fields forbidden
- strict bool behavior
- string trimming and blank rejection
- list trimming, dedupe, and blank rejection
- strict parse rejects scalar list fields
- missing profile read returns default
- malformed profile strict load raises
- save/load round trip
- save creates parent directories
- save rejects non-persona input
- POSIX private file permissions when applicable
- privacy projection excludes `never_prompt`
- prompt capsule includes only eligible facts
- tombstoned facts are removed or suppressed by patch application
- validation returns structured errors/warnings
- no read-only load creates files
- persona data is not written under a project `GPD/` directory

Optional but useful:

- history/tombstone JSONL append creates private directories
- project-private projection hides private-local fields
- role-specific capsules keep a stable role value and influence summary

## Implementation Guardrails

Do not add:

- command wrappers
- staged workflow manifests
- `gpd-persona-builder` agent
- CLI commands
- config keys
- runtime projection changes
- generated docs

Those are Phase 2+ work. If Phase 1 touches registry/frontmatter/projection, it is probably overreaching.

## Acceptance Criteria

Phase 1 is complete when:

- `gpd.core.research_persona` imports cleanly
- focused tests pass
- full repo test suite passes
- no private persona data is created in the repo
- the phase report remains under `tmp/phase-01-foundation-report.md`
- the commit contains only Phase 1 foundation files/tests/report

"""Cross-phase acceptance inventory for Research Persona Phases 4 and 5."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from tests.markdown_test_support import has_line_with_terms, normalize_text

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "gpd"

PHASE4_MODULE_CANDIDATES = (
    SRC_ROOT / "core" / "research_persona_source_ingestion.py",
    SRC_ROOT / "core" / "research_persona_ingestion.py",
    SRC_ROOT / "core" / "research_persona_sources.py",
)

PHASE4_CLI_SURFACE_CANDIDATES = (
    SRC_ROOT / "commands" / "ingest-persona-sources.md",
    SRC_ROOT / "commands" / "ingest-research-persona-sources.md",
    SRC_ROOT / "commands" / "persona-source-ingest.md",
    SRC_ROOT / "commands" / "build-persona.md",
    SRC_ROOT / "cli.py",
)

PHASE5_MODULE_CANDIDATES = (
    SRC_ROOT / "core" / "research_persona_application.py",
    SRC_ROOT / "core" / "research_persona_applications.py",
    SRC_ROOT / "core" / "research_persona_application_previews.py",
)

PHASE5_AGENT_SURFACE_CANDIDATES = (
    SRC_ROOT / "agents" / "gpd-research-persona-applications.md",
    SRC_ROOT / "agents" / "gpd-persona-application-preview.md",
    SRC_ROOT / "agents" / "gpd-persona-applications.md",
    SRC_ROOT / "agents" / "gpd-researcher-doppelganger.md",
    SRC_ROOT / "agents" / "gpd-persona-doppelganger.md",
    SRC_ROOT / "agents" / "gpd-expertise-aware-explainer.md",
    SRC_ROOT / "agents" / "gpd-expertise-explainer.md",
    SRC_ROOT / "agents" / "gpd-scientific-taste-model.md",
    SRC_ROOT / "agents" / "gpd-scientific-taste.md",
    SRC_ROOT / "agents" / "gpd-persona-taste.md",
)

FEATURE_CONCEPTS = {
    "Researcher Doppelganger": ("doppelganger",),
    "Expertise-Aware Explanations": ("expertise", "explain"),
    "Scientific Taste Model": ("taste",),
}

PRIVATE_STORE_MARKERS = (
    "research-persona/profile.json",
    "research_persona/profile.json",
    "~/.gpd/research-persona",
    "$GPD_DATA_DIR/research-persona",
    "${GPD_DATA_DIR:-~/.gpd}/research-persona",
    "load_research_persona(",
    "save_research_persona(",
    "research_persona_path(",
)
DIRECT_PROFILE_MUTATION_TERMS = (
    "append",
    "create",
    "edit",
    "modify",
    "mutate",
    "overwrite",
    "persist",
    "save",
    "update",
    "write",
)
RAW_PROFILE_INJECTION_TERMS = (
    "copy",
    "embed",
    "expose",
    "include",
    "inject",
    "load",
    "paste",
    "read",
    "summarize",
)
NEGATION_TERMS = (
    "do not",
    "don't",
    "forbid",
    "forbidden",
    "must not",
    "never",
    "no direct",
    "not directly",
    "not raw",
    "without",
)
APPROVAL_ROUTE_TERMS = ("apply-patch", "gpd research-persona")


@dataclass(frozen=True)
class TextSurface:
    path: Path
    text: str

    @property
    def relpath(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _existing(paths: Iterable[Path]) -> tuple[Path, ...]:
    return tuple(path for path in paths if path.is_file())


def _surfaces(paths: Iterable[Path]) -> tuple[TextSurface, ...]:
    return tuple(TextSurface(path=path, text=_read(path)) for path in _existing(paths))


def _missing_message(paths: Iterable[Path], *, context: str) -> str:
    expected = "\n".join(path.relative_to(REPO_ROOT).as_posix() for path in paths)
    return f"missing {context}; expected one of:\n{expected}"


def _require_existing(paths: Iterable[Path], *, context: str) -> tuple[Path, ...]:
    path_tuple = tuple(paths)
    existing = _existing(path_tuple)
    assert existing, _missing_message(path_tuple, context=context)
    return existing


def _parse_python(path: Path) -> ast.Module:
    return ast.parse(_read(path), filename=str(path))


def _public_api_names(tree: ast.Module) -> tuple[str, ...]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            names.append(node.name)
    return tuple(sorted(names))


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    lowered = value.casefold()
    return any(term.casefold() in lowered for term in terms)


def _name_matches(names: Iterable[str], required_terms: Iterable[str], *, optional_terms: Iterable[str] = ()) -> bool:
    required = tuple(required_terms)
    optional = tuple(optional_terms)
    for name in names:
        lowered = name.casefold()
        if not all(term.casefold() in lowered for term in required):
            continue
        if optional and not any(term.casefold() in lowered for term in optional):
            continue
        return True
    return False


def _semantic_text(text: str, terms: Iterable[str]) -> bool:
    normalized = normalize_text(text).casefold()
    return all(term.casefold() in normalized for term in terms)


def _has_prompt_safe_capsule_contract(text: str) -> bool:
    lowered = text.casefold()
    return (
        has_line_with_terms(text, "prompt-safe", "capsule", casefold=True)
        or has_line_with_terms(text, "capsule", "privacy", casefold=True)
        or ("researchpersonacapsule" in lowered and "raw profile" not in lowered)
    )


def _non_negated_lines(text: str, *, markers: tuple[str, ...], verbs: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines():
        lowered = line.casefold()
        if not any(marker.casefold() in lowered for marker in markers):
            continue
        if any(term in lowered for term in NEGATION_TERMS):
            continue
        if any(term in lowered for term in APPROVAL_ROUTE_TERMS):
            continue
        if any(verb in lowered for verb in verbs):
            hits.append(line.strip())
    return hits


def _direct_profile_mutation_lines(text: str) -> list[str]:
    return _non_negated_lines(
        text,
        markers=PRIVATE_STORE_MARKERS,
        verbs=DIRECT_PROFILE_MUTATION_TERMS,
    )


def _raw_profile_injection_lines(text: str) -> list[str]:
    markers = (*PRIVATE_STORE_MARKERS, "raw profile", "raw private profile", "raw research persona")
    return _non_negated_lines(
        text,
        markers=markers,
        verbs=RAW_PROFILE_INJECTION_TERMS,
    )


def _assert_no_raw_profile_surface(surface: TextSurface) -> None:
    direct_lines = _direct_profile_mutation_lines(surface.text)
    injection_lines = _raw_profile_injection_lines(surface.text)
    assert not direct_lines, f"{surface.relpath} has direct private-profile mutation lines:\n" + "\n".join(direct_lines)
    assert not injection_lines, f"{surface.relpath} has raw private-profile injection lines:\n" + "\n".join(
        injection_lines
    )


def _feature_surfaces(surfaces: Iterable[TextSurface], terms: Iterable[str]) -> tuple[TextSurface, ...]:
    return tuple(
        surface for surface in surfaces if _contains_any(surface.path.stem, terms) or _contains_any(surface.text, terms)
    )


def test_phase4_source_ingestion_module_exposes_patch_only_api() -> None:
    module_paths = _require_existing(PHASE4_MODULE_CANDIDATES, context="Phase 4 source-ingestion module")
    module_path = module_paths[0]
    tree = _parse_python(module_path)
    public_names = _public_api_names(tree)
    module_text = _read(module_path)

    assert _name_matches(public_names, ("patch",), optional_terms=("candidate", "draft", "build", "source"))
    assert _name_matches(public_names, ("source",), optional_terms=("evidence", "ingest", "scan", "packet"))
    assert _semantic_text(module_text, ("ResearchPersonaPatch",))
    assert not _name_matches(public_names, ("profile",), optional_terms=("apply", "persist", "save", "write"))

    _assert_no_raw_profile_surface(TextSurface(path=module_path, text=module_text))


def test_phase4_cli_surface_is_read_only_until_approval() -> None:
    surfaces = _surfaces(PHASE4_CLI_SURFACE_CANDIDATES)
    assert surfaces, _missing_message(PHASE4_CLI_SURFACE_CANDIDATES, context="Phase 4 CLI surface")

    matching = tuple(
        surface
        for surface in surfaces
        if has_line_with_terms(surface.text, "read-only", casefold=True)
        and has_line_with_terms(surface.text, "candidate", "patch", casefold=True)
        and has_line_with_terms(surface.text, "apply-patch", casefold=True)
    )
    assert matching, "Phase 4 CLI surface must describe read-only candidate patch generation and approval routing"

    for surface in matching:
        _assert_no_raw_profile_surface(surface)


def test_phase5_application_module_exposes_ambitious_feature_helpers() -> None:
    module_paths = _require_existing(PHASE5_MODULE_CANDIDATES, context="Phase 5 application-preview module")
    module_path = module_paths[0]
    tree = _parse_python(module_path)
    public_names = _public_api_names(tree)
    module_text = _read(module_path)

    for feature_name, terms in FEATURE_CONCEPTS.items():
        helpers = tuple(name for name in public_names if _contains_any(name, terms))
        assert helpers, f"Phase 5 module is missing public helper coverage for {feature_name}"
        assert any(_contains_any(name, ("preview", "capsule", "render", "rank", "simulate")) for name in helpers)

    assert _has_prompt_safe_capsule_contract(module_text)
    _assert_no_raw_profile_surface(TextSurface(path=module_path, text=module_text))


def test_phase5_agent_surfaces_require_capsules_not_raw_profiles() -> None:
    surfaces = _surfaces(PHASE5_AGENT_SURFACE_CANDIDATES)
    assert surfaces, _missing_message(PHASE5_AGENT_SURFACE_CANDIDATES, context="Phase 5 agent surface")

    for feature_name, terms in FEATURE_CONCEPTS.items():
        feature_surfaces = _feature_surfaces(surfaces, terms)
        assert feature_surfaces, f"Phase 5 agent surfaces are missing coverage for {feature_name}"
        assert any(_has_prompt_safe_capsule_contract(surface.text) for surface in feature_surfaces)

    for surface in surfaces:
        _assert_no_raw_profile_surface(surface)


def test_phase4_phase5_tracked_surfaces_have_cross_phase_traceability() -> None:
    phase4_text = "\n\n".join(surface.text for surface in _surfaces((*PHASE4_MODULE_CANDIDATES, *PHASE4_CLI_SURFACE_CANDIDATES)))
    phase5_text = "\n\n".join(surface.text for surface in _surfaces((*PHASE5_MODULE_CANDIDATES, *PHASE5_AGENT_SURFACE_CANDIDATES)))
    combined = normalize_text("\n\n".join((phase4_text, phase5_text)))

    assert _semantic_text(phase4_text, ("source ingestion", "candidate patch", "approval"))
    assert _semantic_text(phase5_text, ("doppelganger", "explainer", "taste", "capsule"))
    assert _semantic_text(combined, ("Phase 4", "Phase 5", "acceptance"))


def test_phase4_and_phase5_surfaces_do_not_bypass_private_profile_controls() -> None:
    surfaces = (
        *_surfaces(PHASE4_MODULE_CANDIDATES),
        *_surfaces(PHASE4_CLI_SURFACE_CANDIDATES),
        *_surfaces(PHASE5_MODULE_CANDIDATES),
        *_surfaces(PHASE5_AGENT_SURFACE_CANDIDATES),
    )
    assert surfaces, "Phase 4/5 persona surfaces are missing"

    for surface in surfaces:
        _assert_no_raw_profile_surface(surface)

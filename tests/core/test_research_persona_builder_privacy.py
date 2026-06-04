"""Privacy and safety contracts for the research persona builder workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.markdown_test_support import assert_required_fragments, has_line_with_terms, markdown_fence_bodies

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_PATH = REPO_ROOT / "src" / "gpd" / "commands" / "build-persona.md"
WORKFLOW_PATH = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona.md"
AGENT_PATH = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-persona-builder.md"

EXPECTED_SURFACES = {
    "command": COMMAND_PATH,
    "workflow": WORKFLOW_PATH,
    "agent": AGENT_PATH,
}

PRIVACY_LABELS = (
    "session_only",
    "private_local",
    "project_private",
    "safe_to_share",
    "never_prompt",
)
CONFIDENCE_LABELS = ("confirmed", "inferred", "stale", "disputed")
SOURCE_KIND_LABELS = (
    "user_statement",
    "interview",
    "project_scan",
    "paper_import",
    "bibtex_import",
    "repo_scan",
    "manual_patch",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _combined_builder_text() -> str:
    parts = [
        f"\n\n<!-- {name}: {path.relative_to(REPO_ROOT).as_posix()} -->\n{_read(path)}"
        for name, path in EXPECTED_SURFACES.items()
    ]
    return "".join(parts)


def _surface_presence_message() -> str:
    return "\n".join(
        f"{name}: {path.relative_to(REPO_ROOT).as_posix()} exists={path.exists()}"
        for name, path in EXPECTED_SURFACES.items()
    )


def _non_negated_storage_lines(text: str, *, verbs: tuple[str, ...]) -> list[str]:
    storage_needles = (
        "research-persona/profile.json",
        "research_persona/profile.json",
        "~/.gpd/research-persona/profile.json",
        "$GPD_DATA_DIR/research-persona/profile.json",
        "${GPD_DATA_DIR:-~/.gpd}/research-persona/profile.json",
    )
    negations = (
        "do not",
        "don't",
        "never",
        "must not",
        "forbid",
        "forbidden",
        "without writing",
        "not directly",
    )
    allowed_indirect_markers = ("gpd research-persona apply-patch", "apply-patch")
    hits: list[str] = []
    for line in text.splitlines():
        lowered = line.casefold()
        if not any(needle in lowered for needle in storage_needles):
            continue
        if any(negation in lowered for negation in negations):
            continue
        if any(marker in lowered for marker in allowed_indirect_markers):
            continue
        if any(verb in lowered for verb in verbs):
            hits.append(line.strip())
    return hits


def test_research_persona_builder_surfaces_are_declared() -> None:
    missing = [
        f"{name}: {path.relative_to(REPO_ROOT).as_posix()}"
        for name, path in EXPECTED_SURFACES.items()
        if not path.exists()
    ]

    assert not missing, "Phase 3 persona builder surfaces are missing:\n" + "\n".join(missing)


def test_persona_builder_prompts_forbid_silent_memory_and_raw_profile_injection() -> None:
    text = _combined_builder_text()
    lowered = text.casefold()

    assert (
        "no silent memory" in lowered
        or has_line_with_terms(text, "do not", "silently", "memory", casefold=True)
        or has_line_with_terms(text, "silently", "persona", "storage", casefold=True)
    ), _surface_presence_message()
    assert_required_fragments(lowered, ("prompt-safe", "capsule"), context="persona builder privacy surface")
    assert any(fragment in lowered for fragment in ("export-capsule", "project_research_persona"))

    raw_injection_lines = _non_negated_storage_lines(
        text,
        verbs=("inject", "include", "paste", "load", "read", "embed", "summarize", "copy"),
    )
    assert not raw_injection_lines, (
        "Persona builder prompts must not inject the raw private profile into prompts:\n"
        + "\n".join(raw_injection_lines)
    )


def test_persona_builder_requires_explicit_approval_before_mutation() -> None:
    text = _combined_builder_text()

    assert has_line_with_terms(text, "explicit", "user", "approval", casefold=True), _surface_presence_message()
    assert (
        has_line_with_terms(text, "approval", "before", "apply-patch", casefold=True)
        or has_line_with_terms(text, "do not", "apply-patch", "until", "approval", casefold=True)
        or has_line_with_terms(text, "never", "apply-patch", "unless", "explicitly", casefold=True)
    )


def test_persona_builder_returns_candidate_patch_json_not_direct_writes() -> None:
    text = _combined_builder_text()
    lowered = text.casefold()

    assert_required_fragments(
        lowered,
        (
            "candidate patch",
            "researchpersonapatch",
            "schema_version",
            "operations",
            "gpd research-persona diff",
            "gpd research-persona apply-patch",
        ),
        context="persona builder patch review route",
    )

    json_fences = markdown_fence_bodies(text, info="json")
    assert any("schema_version" in fence and "operations" in fence for fence in json_fences), (
        "Builder prompt must show a JSON candidate patch shape."
    )

    direct_write_lines = _non_negated_storage_lines(
        text,
        verbs=("write", "save", "edit", "create", "mutate", "append", "overwrite", "persist"),
    )
    assert not direct_write_lines, (
        "Persona builder prompts must not tell the model to write the private profile directly:\n"
        + "\n".join(direct_write_lines)
    )


def test_persona_builder_privacy_labels_include_never_prompt() -> None:
    text = _combined_builder_text()

    for label in PRIVACY_LABELS:
        assert label in text, f"missing privacy label {label!r}; surfaces:\n{_surface_presence_message()}"
    assert has_line_with_terms(text, "never_prompt", "never", "prompt", casefold=True)
    assert has_line_with_terms(text, "privacy", "label", casefold=True) or has_line_with_terms(
        text, "privacy", "classification", casefold=True
    )


def test_persona_builder_requires_evidence_and_confidence_for_candidate_facts() -> None:
    text = _combined_builder_text()

    assert has_line_with_terms(text, "candidate patch", "evidence", casefold=True) or has_line_with_terms(
        text, "patch", "evidence", casefold=True
    )
    assert has_line_with_terms(text, "fact", "confidence", casefold=True)
    assert "evidence_refs" in text
    assert "source_kind" in text
    assert "sources" in text

    for label in CONFIDENCE_LABELS:
        assert label in text, f"missing confidence label {label!r}"
    for label in SOURCE_KIND_LABELS:
        assert label in text, f"missing source kind {label!r}"


@pytest.mark.parametrize("path", EXPECTED_SURFACES.values(), ids=EXPECTED_SURFACES.keys())
def test_persona_builder_surface_text_does_not_autoload_private_profile(path: Path) -> None:
    text = _read(path)
    if not text:
        pytest.fail(f"missing surface: {path.relative_to(REPO_ROOT).as_posix()}")

    forbidden_lines = _non_negated_storage_lines(
        text,
        verbs=("read", "load", "inject", "include", "paste", "copy", "summarize", "write", "save", "edit"),
    )
    assert not forbidden_lines, (
        f"{path.relative_to(REPO_ROOT).as_posix()} contains raw private-profile handling instructions:\n"
        + "\n".join(forbidden_lines)
    )

"""Static contracts for Research Persona application prompt surfaces."""

from __future__ import annotations

from pathlib import Path

import gpd.registry as registry
from tests.markdown_test_support import has_line_with_terms, tag_blocks

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
REFERENCE_PATH = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "research" / "research-persona-applications.md"

APPLICATION_AGENTS = {
    "gpd-researcher-doppelganger": {
        "path": AGENTS_DIR / "gpd-researcher-doppelganger.md",
        "role": "doppelganger",
        "terms": (
            ("likely", "objections", "questions", "standards"),
            ("do not", "impersonate", "user"),
            ("evidence", "needed"),
        ),
    },
    "gpd-expertise-explainer": {
        "path": AGENTS_DIR / "gpd-expertise-explainer.md",
        "role": "explainer",
        "terms": (
            ("math", "code", "experiment", "theory", "applied"),
            ("assume", "skip", "expand"),
            ("depth", "profile"),
        ),
    },
    "gpd-scientific-taste": {
        "path": AGENTS_DIR / "gpd-scientific-taste.md",
        "role": "taste",
        "terms": (
            ("rank", "novelty", "tractability"),
            ("evidence", "standard", "risk", "appetite"),
            ("field", "project", "persona", "fit"),
        ),
    },
}

RETURN_ONLY = "return_only"
SCOPED_WRITE = "scoped_write"
CAPSULE_SOURCE_TERMS = ("export-capsule", "Phase 5 application helpers")
PRIVATE_INPUT_TERMS = ("raw persona storage", "durable profile", "profile history", "tombstones")
REFERENCE_ROLE_TERMS = ("doppelganger", "explainer", "taste")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _has_any_line_with_terms(text: str, groups: tuple[tuple[str, ...], ...]) -> bool:
    return any(has_line_with_terms(text, *terms, casefold=True) for terms in groups)


def _non_negated_private_profile_lines(text: str) -> list[str]:
    verbs = ("read", "load", "open", "inspect", "mutate", "write", "save", "update", "create", "patch")
    negations = ("do not", "don't", "must not", "never", "forbidden", "without")
    hits: list[str] = []
    for line in text.splitlines():
        lowered = line.casefold()
        if not any(term in lowered for term in PRIVATE_INPUT_TERMS):
            continue
        if any(negation in lowered for negation in negations):
            continue
        if any(verb in lowered for verb in verbs):
            hits.append(line.strip())
    return hits


def test_research_persona_application_agents_are_registered() -> None:
    registry.invalidate_cache()
    missing = [_relative(spec["path"]) for spec in APPLICATION_AGENTS.values() if not Path(spec["path"]).is_file()]

    assert not missing, "missing Research Persona application agent surfaces:\n" + "\n".join(missing)

    for name, spec in APPLICATION_AGENTS.items():
        agent = registry.get_agent(name)

        assert agent.name == name
        assert Path(agent.path) == spec["path"]
        assert agent.shared_state_authority == RETURN_ONLY
        assert agent.artifact_write_authority == SCOPED_WRITE


def test_application_agents_accept_prompt_safe_capsules_only() -> None:
    for spec in APPLICATION_AGENTS.values():
        text = _read(spec["path"])
        role = str(spec["role"])

        assert has_line_with_terms(text, "prompt-safe", "capsule", role, casefold=True)
        assert _has_any_line_with_terms(text, ((CAPSULE_SOURCE_TERMS[0], role), (CAPSULE_SOURCE_TERMS[1], role)))
        assert has_line_with_terms(text, "do not", "read", "raw persona storage", casefold=True)
        assert has_line_with_terms(text, "do not", "mutate", "persona storage", casefold=True)
        assert not _non_negated_private_profile_lines(text)


def test_application_agents_have_role_specific_useful_behavior() -> None:
    for spec in APPLICATION_AGENTS.values():
        text = _read(spec["path"])
        term_groups = spec["terms"]

        assert _has_any_line_with_terms(text, term_groups)
        for terms in term_groups:
            assert has_line_with_terms(text, *terms, casefold=True)


def test_application_agents_define_structured_returns_and_privacy_notes() -> None:
    for spec in APPLICATION_AGENTS.values():
        text = _read(spec["path"])
        returns = "\n".join(tag_blocks(text, "return_contract"))

        assert returns
        assert has_line_with_terms(returns, "gpd_return", "status", casefold=True)
        assert has_line_with_terms(returns, "privacy_notes", casefold=True)
        assert has_line_with_terms(returns, "files_written", casefold=True)
        assert has_line_with_terms(text, "capsule", "confidence", casefold=True) or has_line_with_terms(
            text, "persona", "confidence", casefold=True
        )


def test_research_persona_application_reference_defines_shared_contract() -> None:
    text = _read(REFERENCE_PATH)

    assert text
    for role in REFERENCE_ROLE_TERMS:
        assert has_line_with_terms(text, role, "capsule", casefold=True)

    assert has_line_with_terms(text, "do not", "read", "raw persona storage", casefold=True)
    assert has_line_with_terms(text, "do not", "mutate", "persona storage", casefold=True)
    assert has_line_with_terms(text, "novelty", "tractability", "evidence", "risk", casefold=True)
    assert has_line_with_terms(text, "math", "code", "experiment", "theory", "applied", casefold=True)
    assert has_line_with_terms(text, "objections", "questions", "standards", casefold=True)

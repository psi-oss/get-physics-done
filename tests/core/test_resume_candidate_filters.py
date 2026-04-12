from gpd.core.resume_candidates import candidate_text, find_resume_candidate, has_resume_candidate
from gpd.core.resume_surface import RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF, resume_origin_for_handoff


def _samples() -> list[dict[str, object]]:
    return [
        {
            "source": "current_execution",
            "kind": "bounded_segment",
            "status": "available",
            "resume_file": "  workspace/resume-segment.md  ",
        },
        {
            "source": "session_resume_file",
            "status": "handoff",
            "origin": resume_origin_for_handoff(),
            "resume_pointer": "shared/hand-off.md",
        },
        {
            "source": "interrupted_agent",
            "status": "interrupted",
            "agent_id": "agent-01",
        },
    ]


def test_candidate_text_normalizes_edges() -> None:
    assert candidate_text({"foo": "  bar  "}, "foo") == "bar"
    assert candidate_text({"foo": None}, "foo") is None
    assert candidate_text({}, "missing") is None


def test_has_resume_candidate_matches_filters() -> None:
    candidates = _samples()
    assert has_resume_candidate(candidates, kind="bounded_segment", resume_file="workspace/resume-segment.md")
    assert has_resume_candidate(
        candidates,
        origin=resume_origin_for_handoff(),
        resume_pointer="shared/hand-off.md",
    )
    assert has_resume_candidate(candidates, source="interrupted_agent", agent_id="agent-01")
    assert not has_resume_candidate(candidates, kind=RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF, status="missing")


def test_find_resume_candidate_returns_first_match() -> None:
    candidates = _samples()
    handoff = find_resume_candidate(candidates, kind=RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF)
    assert handoff is not None
    assert handoff.get("origin") == resume_origin_for_handoff()
    assert find_resume_candidate(None, kind="bounded_segment") is None


def test_has_resume_candidate_handles_missing_sequence() -> None:
    assert not has_resume_candidate(None, kind="bounded_segment")

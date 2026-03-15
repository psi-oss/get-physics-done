"""Stress tests for state management edge cases.

Covers:
1.  Empty STATE.md (just "# State\\n")
2.  STATE.md with only frontmatter (no sections)
3.  state.json with all fields set to null
4.  state.json with unknown extra fields
5.  Concurrent file access simulation (write during read)
6.  Very large state (100 decisions, 50 blockers, 200 metrics)
7.  Unicode in all fields (Greek letters, CJK, emoji)
8.  Phase numbers: "0", "999", "1.1.1.1", negative "-1"
9.  Convention values with YAML special chars (: { } [ ] > |)
10. state.json with missing "position" or "session" sections
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from gpd.core.state import (
    ResearchState,
    _normalize_state_schema,
    default_state_dict,
    ensure_state_schema,
    generate_state_markdown,
    load_state_json,
    parse_state_md,
    parse_state_to_json,
    save_state_json,
    state_snapshot,
    state_validate,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap_project(tmp_path: Path, state_dict: dict | None = None) -> Path:
    """Create a minimal .gpd/ project with STATE.md + state.json."""
    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n")
    (planning / "ROADMAP.md").write_text("# Roadmap\n")

    state = state_dict or default_state_dict()
    pos = state.setdefault("position", {})
    if pos.get("current_phase") is None:
        pos["current_phase"] = "01"
    if pos.get("status") is None:
        pos["status"] = "Executing"
    if pos.get("current_plan") is None:
        pos["current_plan"] = "1"
    if pos.get("total_plans_in_phase") is None:
        pos["total_plans_in_phase"] = 3
    if pos.get("progress_percent") is None:
        pos["progress_percent"] = 33

    md = generate_state_markdown(state)
    (planning / "STATE.md").write_text(md, encoding="utf-8")
    (planning / "state.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# 1. Empty STATE.md
# ---------------------------------------------------------------------------


class TestEmptyStateMd:
    def test_parse_empty_state_md(self) -> None:
        """Parsing '# State\\n' returns dict with no crashes and empty lists."""
        parsed = parse_state_md("# State\n")
        assert isinstance(parsed, dict)
        assert parsed["decisions"] == []
        assert parsed["blockers"] == []
        assert parsed["position"]["current_phase"] is None
        assert parsed["position"]["status"] is None

    def test_snapshot_with_empty_state_md(self, tmp_path: Path) -> None:
        """state_snapshot falls back gracefully when STATE.md is minimal."""
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()
        (planning / "STATE.md").write_text("# State\n")
        # No state.json, so snapshot falls back to STATE.md
        snap = state_snapshot(tmp_path)
        assert snap.current_phase is None
        assert snap.status is None


# ---------------------------------------------------------------------------
# 2. STATE.md with only frontmatter (no sections)
# ---------------------------------------------------------------------------


class TestFrontmatterOnly:
    def test_parse_frontmatter_only(self) -> None:
        """STATE.md with only a YAML frontmatter block and no sections."""
        content = "---\ntitle: Research\ndate: 2026-01-01\n---\n"
        parsed = parse_state_md(content)
        assert isinstance(parsed, dict)
        assert parsed["decisions"] == []
        assert parsed["blockers"] == []
        assert parsed["position"]["current_phase"] is None

    def test_parse_state_to_json_frontmatter_only(self) -> None:
        """parse_state_to_json handles frontmatter-only without crashing."""
        content = "---\ntitle: Research\n---\n"
        result = parse_state_to_json(content)
        assert result["_version"] == 1
        assert result["position"]["current_phase"] is None


# ---------------------------------------------------------------------------
# 3. state.json with all fields set to null
# ---------------------------------------------------------------------------


class TestAllNullFields:
    def test_ensure_schema_all_null(self) -> None:
        """ensure_state_schema fills defaults when every field is null."""
        raw = {
            "position": None,
            "decisions": None,
            "blockers": None,
            "session": None,
            "convention_lock": None,
            "approximations": None,
            "propagated_uncertainties": None,
            "active_calculations": None,
            "intermediate_results": None,
            "open_questions": None,
            "pending_todos": None,
            "performance_metrics": None,
            "project_reference": None,
        }
        result = ensure_state_schema(raw)
        assert isinstance(result, dict)
        assert isinstance(result["position"], dict)
        assert isinstance(result["decisions"], list)
        assert isinstance(result["blockers"], list)
        assert isinstance(result["session"], dict)

    def test_load_all_null_state_json(self, tmp_path: Path) -> None:
        """load_state_json recovers from state.json where all values are null."""
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()
        null_state = dict.fromkeys(default_state_dict())
        (planning / "state.json").write_text(json.dumps(null_state))
        # Also write a minimal STATE.md for fallback
        (planning / "STATE.md").write_text("# State\n")
        loaded = load_state_json(tmp_path)
        assert loaded is not None
        assert "position" in loaded

    def test_ensure_schema_salvages_contract_when_approach_policy_is_malformed(self) -> None:
        raw = default_state_dict()
        raw["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        raw["project_contract"]["approach_policy"] = {"formulations": "not-a-list"}

        result = ensure_state_schema(raw)

        assert result["project_contract"] is not None
        assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert result["project_contract"]["approach_policy"] == {
            "formulations": [],
            "allowed_estimator_families": [],
            "forbidden_estimator_families": [],
            "allowed_fit_families": [],
            "forbidden_fit_families": [],
            "stop_and_rethink_conditions": [],
        }


# ---------------------------------------------------------------------------
# 4. state.json with unknown extra fields
# ---------------------------------------------------------------------------


class TestUnknownExtraFields:
    def test_extra_fields_preserved_by_ensure_schema(self) -> None:
        """Unknown top-level keys survive ensure_state_schema via extra='allow'."""
        raw = {
            "_custom_experiment": {"hypothesis": "H1"},
            "zz_metadata": [1, 2, 3],
            "position": {"current_phase": "03", "status": "Executing"},
        }
        result = ensure_state_schema(raw)
        assert result["_custom_experiment"] == {"hypothesis": "H1"}
        assert result["zz_metadata"] == [1, 2, 3]
        assert result["position"]["current_phase"] == "03"

    def test_roundtrip_extra_fields_in_state_json(self, tmp_path: Path) -> None:
        """Extra fields in state.json survive save + load round-trip."""
        cwd = _bootstrap_project(tmp_path)
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Executing"
        state["_experiment_id"] = "EXP-42"
        state["custom_notes"] = "Important note"
        save_state_json(cwd, state)

        loaded = load_state_json(cwd)
        assert loaded is not None
        assert loaded.get("_experiment_id") == "EXP-42"
        assert loaded.get("custom_notes") == "Important note"

    def test_project_contract_self_heals_malformed_context_intake(self) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = {
            "must_read_refs": "not-a-list",
            "must_include_prior_outputs": [".gpd/phases/00-baseline/00-01-SUMMARY.md"],
        }

        result = ensure_state_schema({"project_contract": contract})

        assert result["project_contract"] is not None
        assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert result["project_contract"]["context_intake"] == {
            "must_read_refs": [],
            "must_include_prior_outputs": [".gpd/phases/00-baseline/00-01-SUMMARY.md"],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": [],
            "crucial_inputs": [],
        }

    def test_project_contract_self_heals_malformed_uncertainty_markers(self) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["uncertainty_markers"] = {
            "weakest_anchors": "not-a-list",
            "disconfirming_observations": ["Benchmark mismatch survives normalization fix"],
        }

        result = ensure_state_schema({"project_contract": contract})

        assert result["project_contract"] is not None
        assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert result["project_contract"]["uncertainty_markers"] == {
            "weakest_anchors": [],
            "unvalidated_assumptions": [],
            "competing_explanations": [],
            "disconfirming_observations": ["Benchmark mismatch survives normalization fix"],
        }

    def test_project_contract_self_heals_malformed_approach_policy_without_dropping_valid_siblings(self) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["approach_policy"] = {
            "formulations": "hamiltonian",
            "stop_and_rethink_conditions": ["Sign flip after normalization change"],
        }

        result = ensure_state_schema({"project_contract": contract})

        assert result["project_contract"] is not None
        assert result["project_contract"]["scope"]["question"] == "What benchmark must the project recover?"
        assert result["project_contract"]["approach_policy"] == {
            "formulations": [],
            "allowed_estimator_families": [],
            "forbidden_estimator_families": [],
            "allowed_fit_families": [],
            "forbidden_fit_families": [],
            "stop_and_rethink_conditions": ["Sign flip after normalization change"],
        }

    def test_project_contract_scope_integrity_issue_mentions_nested_field(self) -> None:
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["scope"]["unresolved_questions"] = "not-a-list"

        normalized, integrity_issues = _normalize_state_schema({"project_contract": contract})

        assert normalized["project_contract"] is not None
        assert any("project_contract.scope.unresolved_questions" in issue for issue in integrity_issues)


# ---------------------------------------------------------------------------
# 5. Concurrent file access simulation
# ---------------------------------------------------------------------------


class TestConcurrentAccess:
    def test_concurrent_save_does_not_corrupt(self, tmp_path: Path) -> None:
        """Multiple threads writing state.json should not produce corrupt files."""
        cwd = _bootstrap_project(tmp_path)
        errors: list[str] = []

        def _writer(thread_id: int) -> None:
            try:
                state = default_state_dict()
                state["position"]["current_phase"] = f"{thread_id:02d}"
                state["position"]["status"] = "Executing"
                state["position"]["current_plan"] = "1"
                state["position"]["total_plans_in_phase"] = 3
                save_state_json(cwd, state)
            except Exception as exc:
                errors.append(f"Thread {thread_id}: {exc}")

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent writes produced errors: {errors}"

        # Verify the file is still valid JSON after all writes
        json_path = cwd / ".gpd" / "state.json"
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert "position" in loaded


# ---------------------------------------------------------------------------
# 6. Very large state
# ---------------------------------------------------------------------------


class TestVeryLargeState:
    def test_large_state_roundtrip(self) -> None:
        """State with 100 decisions, 50 blockers, 200 metric rows round-trips."""
        state = default_state_dict()
        state["position"]["current_phase"] = "42"
        state["position"]["status"] = "Executing"
        state["position"]["progress_percent"] = 50

        state["decisions"] = [
            {"phase": str(i % 10), "summary": f"Decision #{i}", "rationale": f"Reason {i}"}
            for i in range(100)
        ]
        state["blockers"] = [f"Blocker #{i}: need verification" for i in range(50)]
        state["performance_metrics"] = {
            "rows": [
                {"label": f"Phase {i} P1", "duration": f"{i}m", "tasks": str(i), "files": str(i * 2)}
                for i in range(200)
            ]
        }

        md = generate_state_markdown(state)
        assert len(md) > 1000  # should be substantial
        parsed = parse_state_md(md)
        assert len(parsed["decisions"]) == 100
        assert len(parsed["blockers"]) == 50

    def test_large_state_save_load(self, tmp_path: Path) -> None:
        """Save and load a large state dict from disk."""
        state = default_state_dict()
        state["position"]["current_phase"] = "05"
        state["position"]["status"] = "Executing"
        state["decisions"] = [
            {"phase": str(i), "summary": f"Dec-{i}", "rationale": None}
            for i in range(100)
        ]
        state["blockers"] = [f"Blocker-{i}" for i in range(50)]
        cwd = _bootstrap_project(tmp_path, state_dict=state)

        loaded = load_state_json(cwd)
        assert loaded is not None
        assert len(loaded["decisions"]) == 100
        assert len(loaded["blockers"]) == 50


# ---------------------------------------------------------------------------
# 7. Unicode in all fields
# ---------------------------------------------------------------------------


class TestUnicodeFields:
    def test_unicode_greek_letters(self) -> None:
        """Greek letters in phase names and decisions survive round-trip."""
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["current_phase_name"] = "\u039b\u03a6\u039c (Lambda-Phi-Mu)"
        state["position"]["status"] = "Executing"
        state["decisions"] = [
            {"phase": "1", "summary": "\u03b1 + \u03b2 = \u03b3 decay channel", "rationale": "\u03b4-expansion"}
        ]
        state["blockers"] = ["\u03b5-\u03b4 regularization diverges"]

        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert "\u039b\u03a6\u039c" in (parsed["position"]["current_phase_name"] or "")
        assert any("\u03b1" in d["summary"] for d in parsed["decisions"])

    def test_unicode_cjk(self) -> None:
        """CJK characters in state fields survive round-trip."""
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["current_phase_name"] = "\u91cf\u5b50\u529b\u5b66 (Quantum Mechanics)"
        state["position"]["status"] = "Executing"
        state["active_calculations"] = ["\u8ba1\u7b97\u54c8\u5bc6\u987f\u7b97\u7b26"]
        state["open_questions"] = ["\u6ce2\u51fd\u6570\u5d29\u5854\u95ee\u9898\u662f\u5426\u53ef\u89e3?"]

        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert "\u91cf\u5b50\u529b\u5b66" in (parsed["position"]["current_phase_name"] or "")
        assert any("\u54c8\u5bc6\u987f" in c for c in parsed["active_calculations"])

    def test_unicode_emoji(self) -> None:
        """Emoji characters in state fields do not crash the parser."""
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Executing"
        state["blockers"] = ["\u26a0\ufe0f Critical: need \u2705 verification"]
        state["open_questions"] = ["\ud83e\udd14 Is the model consistent?"]

        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert len(parsed["blockers"]) == 1
        assert "\u26a0\ufe0f" in parsed["blockers"][0]


# ---------------------------------------------------------------------------
# 8. Phase numbers edge cases
# ---------------------------------------------------------------------------


class TestPhaseNumbers:
    def test_phase_zero(self) -> None:
        """Phase '0' is handled gracefully."""
        state = default_state_dict()
        state["position"]["current_phase"] = "0"
        state["position"]["status"] = "Executing"
        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert parsed["position"]["current_phase"] == "0"

    def test_phase_very_large(self) -> None:
        """Phase '999' does not crash."""
        state = default_state_dict()
        state["position"]["current_phase"] = "999"
        state["position"]["status"] = "Executing"
        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert parsed["position"]["current_phase"] == "999"

    def test_phase_dotted_multilevel(self) -> None:
        """Phase '1.1.1.1' (multi-level dotted) survives round-trip."""
        state = default_state_dict()
        state["position"]["current_phase"] = "1.1.1.1"
        state["position"]["status"] = "Executing"
        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert parsed["position"]["current_phase"] == "1.1.1.1"

    def test_phase_negative(self) -> None:
        """Phase '-1' is tolerated (no crash) though semantically invalid."""
        state = default_state_dict()
        state["position"]["current_phase"] = "-1"
        state["position"]["status"] = "Executing"
        md = generate_state_markdown(state)
        parsed = parse_state_md(md)
        assert parsed["position"]["current_phase"] == "-1"

    def test_validate_negative_phase_flags_issue(self, tmp_path: Path) -> None:
        """state_validate should flag a negative phase number."""
        state = default_state_dict()
        state["position"]["current_phase"] = "-1"
        state["position"]["total_phases"] = 5
        state["position"]["status"] = "Executing"
        cwd = _bootstrap_project(tmp_path, state_dict=state)
        result = state_validate(cwd)
        # Should find issues (negative phase or missing phase dir)
        assert len(result.issues) > 0


# ---------------------------------------------------------------------------
# 9. Convention values with YAML special chars
# ---------------------------------------------------------------------------


class TestYamlSpecialCharsInConventions:
    def test_convention_with_colons(self) -> None:
        """Convention values with ':' do not break markdown generation."""
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Executing"
        state["convention_lock"]["metric_signature"] = "(-,+,+,+): mostly-minus"
        md = generate_state_markdown(state)
        assert "(-,+,+,+): mostly-minus" in md

    def test_convention_with_braces_and_brackets(self) -> None:
        """Convention values with { } [ ] do not crash."""
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Executing"
        state["convention_lock"]["natural_units"] = "{c = 1} [hbar = 1]"
        md = generate_state_markdown(state)
        assert "{c = 1}" in md

    def test_convention_with_pipe_and_gt(self) -> None:
        """Convention values with > and | characters survive markdown."""
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Executing"
        state["convention_lock"]["gauge_choice"] = "A_0 = 0 | temporal gauge > Coulomb"
        md = generate_state_markdown(state)
        # The pipe may be escaped in markdown table contexts, but in bullet lists
        # it should appear or be safely escaped
        assert "temporal gauge" in md


# ---------------------------------------------------------------------------
# 10. state.json with missing position or session sections
# ---------------------------------------------------------------------------


class TestMissingSections:
    def test_missing_position_section(self) -> None:
        """state.json without 'position' key gets defaults via ensure_state_schema."""
        raw = {"decisions": [{"phase": "1", "summary": "Use dim-reg"}], "blockers": []}
        result = ensure_state_schema(raw)
        assert "position" in result
        assert result["position"]["current_phase"] is None
        assert result["position"]["progress_percent"] == 0

    def test_missing_session_section(self) -> None:
        """state.json without 'session' key gets a default session dict."""
        raw = {"position": {"current_phase": "05", "status": "Executing"}}
        result = ensure_state_schema(raw)
        assert "session" in result
        assert isinstance(result["session"], dict)

    def test_load_state_json_missing_both_sections(self, tmp_path: Path) -> None:
        """load_state_json handles state.json with no position and no session."""
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()
        raw = {"decisions": [], "blockers": ["Something"]}
        (planning / "state.json").write_text(json.dumps(raw))
        (planning / "STATE.md").write_text(
            generate_state_markdown(default_state_dict())
        )
        loaded = load_state_json(tmp_path)
        assert loaded is not None
        assert "position" in loaded
        assert "session" in loaded

    def test_snapshot_missing_position_in_json(self, tmp_path: Path) -> None:
        """state_snapshot tolerates state.json that has no 'position' key."""
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()
        raw = {"decisions": [], "blockers": []}
        (planning / "state.json").write_text(json.dumps(raw))
        # state_snapshot reads json directly; 'position' missing -> empty pos dict
        snap = state_snapshot(tmp_path)
        # Should not crash; phase/status are None
        assert snap.current_phase is None
        assert snap.status is None


# ---------------------------------------------------------------------------
# Additional stress: Pydantic model edge cases
# ---------------------------------------------------------------------------


class TestPydanticModelEdgeCases:
    def test_research_state_from_empty_dict(self) -> None:
        """ResearchState.model_validate({}) produces valid defaults."""
        state = ResearchState.model_validate({})
        dumped = state.model_dump()
        assert "position" in dumped
        assert isinstance(dumped["decisions"], list)
        assert isinstance(dumped["blockers"], list)

    def test_ensure_schema_with_deeply_nested_garbage(self) -> None:
        """Deeply nested incorrect types do not crash ensure_state_schema."""
        raw = {
            "position": {
                "current_phase": {"nested": {"deep": True}},
                "status": ["not", "a", "string"],
                "progress_percent": {"bad": "type"},
            },
            "decisions": "not a list",
            "session": 42,
        }
        result = ensure_state_schema(raw)
        assert isinstance(result, dict)
        assert "position" in result
        assert isinstance(result["decisions"], list)

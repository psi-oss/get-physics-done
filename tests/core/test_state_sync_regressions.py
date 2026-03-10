from __future__ import annotations

import json
from pathlib import Path

from gpd.core.state import default_state_dict, generate_state_markdown, sync_state_json_core


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def test_sync_state_json_core_uses_markdown_bullet_sections_as_authority(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / ".gpd"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "03"
    existing["position"]["status"] = "Executing"
    existing["active_calculations"] = ["stale calculation"]
    existing["intermediate_results"] = ["stale result"]
    existing["open_questions"] = ["stale question"]
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")

    markdown_state = default_state_dict()
    markdown_state["position"]["current_phase"] = "03"
    markdown_state["position"]["status"] = "Executing"
    markdown_state["active_calculations"] = ["fresh calculation"]
    markdown_state["intermediate_results"] = ["fresh result"]
    markdown_state["open_questions"] = []
    md_content = generate_state_markdown(markdown_state)

    result = sync_state_json_core(cwd, md_content)
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert result["active_calculations"] == ["fresh calculation"]
    assert result["intermediate_results"] == ["fresh result"]
    assert result["open_questions"] == []
    assert stored["active_calculations"] == ["fresh calculation"]
    assert stored["intermediate_results"] == ["fresh result"]
    assert stored["open_questions"] == []

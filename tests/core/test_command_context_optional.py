from pathlib import Path

COMMANDS_DIR = Path("src/gpd/commands")


def test_health_command_context_marks_project_files_optional() -> None:
    health_text = (COMMANDS_DIR / "health.md").read_text(encoding="utf-8")
    assert "@GPD/STATE.md (if present)" in health_text
    assert "@GPD/state.json (if present)" in health_text
    assert "@GPD/config.json (if present)" in health_text


def test_suggest_next_context_marks_project_files_optional() -> None:
    suggest_text = (COMMANDS_DIR / "suggest-next.md").read_text(encoding="utf-8")
    assert "@GPD/STATE.md (if present)" in suggest_text
    assert "@GPD/ROADMAP.md (if present)" in suggest_text

"""Regression tests for the debugger prompt/session template contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "templates"
DEBUG_PROMPT_PATH = TEMPLATES_DIR / "debug-subagent-prompt.md"
DEBUG_TEMPLATE_PATH = TEMPLATES_DIR / "DEBUG.md"

SESSION_PATH = "GPD/debug/{slug}.md"
STATUS_VOCAB = "gathering | investigating | fixing | verifying | resolved"
GOAL_VOCAB = "find_root_cause_only | find_and_fix"
CONTINUATION_PHRASE = "continue from next_action"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_debug_subagent_prompt_surfaces_the_canonical_session_contract_before_template_output() -> None:
    prompt = _read(DEBUG_PROMPT_PATH)
    contract_block = prompt.split("## Debug Template", 1)[0]

    assert "## Canonical Debug Session Contract" in contract_block
    assert SESSION_PATH in contract_block
    assert STATUS_VOCAB in contract_block
    assert GOAL_VOCAB in contract_block
    assert CONTINUATION_PHRASE in contract_block
    assert prompt.index(SESSION_PATH) < prompt.index("## Debug Template")
    assert prompt.index(STATUS_VOCAB) < prompt.index("## Debug Template")
    assert prompt.index(GOAL_VOCAB) < prompt.index("## Debug Template")
    assert prompt.count("## Debug Template") == 1
    assert "<debug_session_contract>" in prompt
    assert "<debug_file>" not in prompt


def test_debug_session_template_and_prompt_share_the_same_goal_status_and_resume_vocabulary() -> None:
    prompt = _read(DEBUG_PROMPT_PATH)
    debug_template = _read(DEBUG_TEMPLATE_PATH)

    for marker in (SESSION_PATH, STATUS_VOCAB, GOAL_VOCAB, CONTINUATION_PHRASE):
        assert marker in prompt
        assert marker in debug_template

    assert "goal: find_root_cause_only | find_and_fix" in debug_template
    assert "goal: {find_root_cause_only | find_and_fix}" in prompt
    assert "Read the file at GPD/debug/{slug}.md first, then continue from next_action." in debug_template
    assert "Read the file at GPD/debug/{slug}.md first, then continue from next_action." in prompt

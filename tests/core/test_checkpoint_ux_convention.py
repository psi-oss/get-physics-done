"""Phase 8.A assertions for the `[Y/n/e]` checkpoint UX convention."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
REFERENCES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "references"
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"

_CHECKPOINTS_PATH = REFERENCES_DIR / "orchestration" / "checkpoints.md"
_PLANNER_PATH = AGENTS_DIR / "gpd-planner.md"
_CONVENTION_PATH = REFERENCES_DIR / "orchestration" / "checkpoint-ux-convention.md"


def test_checkpoint_human_verify_uses_y_n_e_idiom_in_canonical_templates() -> None:
    checkpoints = _CHECKPOINTS_PATH.read_text(encoding="utf-8")
    planner = _PLANNER_PATH.read_text(encoding="utf-8")

    # Canonical checkpoint spec should use [Y/n/e] in template + render template
    # + 4+ worked examples (>= 6 total occurrences).
    assert checkpoints.count("[Y/n/e]") >= 6, (
        f"expected >=6 occurrences of '[Y/n/e]' in checkpoints.md, "
        f"found {checkpoints.count('[Y/n/e]')}"
    )

    # Planner's replaced L758 template should use [Y/n/e] at least once.
    assert "[Y/n/e]" in planner, "expected '[Y/n/e]' in gpd-planner.md"

    # No old literal Type "confirmed" resume-signal text should remain inside
    # <resume-signal>...</resume-signal> tags in checkpoints.md.
    resume_signals = re.findall(
        r"<resume-signal>(.*?)</resume-signal>", checkpoints, re.DOTALL
    )
    assert resume_signals, "expected at least one <resume-signal> block in checkpoints.md"

    for signal in resume_signals:
        assert "confirmed" not in signal, (
            f"found legacy 'confirmed' resume-signal text inside a "
            f"<resume-signal> tag: {signal!r}"
        )

    # Every <resume-signal> in checkpoints.md should either use the [Y/n/e]
    # idiom (human-verify) or be a decision-style signal (contains 'Select:'
    # or a labeled-options colon pattern).
    for signal in resume_signals:
        has_y_n_e = "[Y/n/e]" in signal
        has_decision_shape = (
            "Select:" in signal
            or "Paste" in signal
            or signal.strip().startswith("[")
        )
        assert has_y_n_e or has_decision_shape, (
            f"<resume-signal> neither uses [Y/n/e] nor a decision/action pattern: {signal!r}"
        )


def test_checkpoint_ux_convention_doc_exists_and_enumerates_carve_outs() -> None:
    assert _CONVENTION_PATH.exists(), (
        f"expected canonical checkpoint-ux-convention.md at {_CONVENTION_PATH}"
    )
    convention = _CONVENTION_PATH.read_text(encoding="utf-8")

    assert "[Y/n/e]" in convention, "convention doc must contain '[Y/n/e]'"

    lowered = convention.lower()
    required_token_groups = [
        ("convention lock", "convention-lock"),
        ("destructive",),
        ("blocker triage",),
        ("claim",),
        ("first-result gate",),
    ]
    missing = [
        group[0]
        for group in required_token_groups
        if not any(tok in lowered for tok in group)
    ]
    assert not missing, f"convention doc missing carve-out tokens: {missing}"

    line_count = len(convention.splitlines())
    assert line_count < 200, (
        f"convention doc should be concise (<200 lines), found {line_count}"
    )

    # Cross-reference to the checkpoint taxonomy doc.
    assert "checkpoints.md" in convention or "orchestration/checkpoints" in convention, (
        "convention doc should cross-reference checkpoints.md"
    )


def test_checkpoint_ux_prompt_references_are_install_relative() -> None:
    paths = [
        AGENTS_DIR / "gpd-executor.md",
        AGENTS_DIR / "gpd-planner.md",
        WORKFLOWS_DIR / "settings.md",
        WORKFLOWS_DIR / "execute-plan.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        if path.name == "gpd-executor.md":
            assert "{GPD_INSTALL_DIR}/references/orchestration/checkpoint-ux-convention.md" in text, path
        else:
            assert "@{GPD_INSTALL_DIR}/references/orchestration/checkpoint-ux-convention.md" in text, path
        assert "specs/references/orchestration/checkpoint-ux-convention.md" not in text, path


def test_y_n_prompts_unified_and_carve_outs_preserved() -> None:
    unified_paths = [
        WORKFLOWS_DIR / "complete-milestone.md",
        WORKFLOWS_DIR / "parameter-sweep.md",
        WORKFLOWS_DIR / "graph.md",
        WORKFLOWS_DIR / "respond-to-referees.md",
        WORKFLOWS_DIR / "undo.md",
        COMMANDS_DIR / "undo.md",
    ]
    carve_out_paths = [
        WORKFLOWS_DIR / "remove-phase.md",
        WORKFLOWS_DIR / "merge-phases.md",
        WORKFLOWS_DIR / "transition.md",
    ]

    for path in unified_paths:
        text = path.read_text(encoding="utf-8")
        assert "[Y/n/e]" in text, f"expected '[Y/n/e]' prompt in {path}"

    for path in carve_out_paths:
        text = path.read_text(encoding="utf-8")
        # Carve-outs keep their original explicit confirmation shape — either
        # a lowercase (y/n) prompt, a multi-char confirmation like 'yes'/'no',
        # or a numeric multi-option decision menu (e.g., transition.md's
        # 3-option skip-incomplete rail).
        has_y_n_prompt = "(y/n)" in text.lower()
        has_multichar = (
            '"yes"' in text
            or '"no"' in text
            or "'yes'" in text
            or "'no'" in text
        )
        has_numeric_options = bool(
            re.search(r"(?m)^\s*1\.\s+\S", text) and re.search(r"(?m)^\s*2\.\s+\S", text)
        )
        assert has_y_n_prompt or has_multichar or has_numeric_options, (
            f"carve-out {path} lost its destructive-rail prompt shape "
            "(expected '(y/n)', a '\"yes\"'/'\"no\"' confirmation, or a "
            "numeric-options decision menu)"
        )


def test_workflow_y_n_e_prompts_define_edit_branch_semantics() -> None:
    paths = [
        WORKFLOWS_DIR / "complete-milestone.md",
        WORKFLOWS_DIR / "parameter-sweep.md",
        WORKFLOWS_DIR / "graph.md",
        WORKFLOWS_DIR / "respond-to-referees.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "[Y/n/e]" in text, path
        assert "**Edit branch:**" in text, path
        assert "re-present the updated `[Y/n/e]` prompt once" in text, path
        assert "Do not treat the edit text itself as approval." in text, path

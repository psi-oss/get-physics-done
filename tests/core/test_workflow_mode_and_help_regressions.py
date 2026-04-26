import re
from pathlib import Path

WORKFLOWS_DIR = Path("src/gpd/specs/workflows")

MODE_AWARE_WORKFLOWS = (
    "plan-phase.md",
    "research-phase.md",
    "map-research.md",
    "literature-review.md",
    "new-project.md",
    "new-milestone.md",
    "execute-phase.md",
)


def _read_workflow(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def _mode_aware_section(text: str) -> str:
    match = re.search(r"\*\*Mode-aware behavior:\*\*\n(?P<section>(?:- .+\n)+)", text)
    assert match is not None
    return match.group("section")


def _discover_help_section(text: str) -> str:
    match = re.search(
        r"\*\*`gpd:discover \[phase or topic\] \[--depth quick\|medium\|deep\]`\*\*\n(?P<section>.*?)(?=\n\*\*`gpd:show-phase)",
        text,
        re.S,
    )
    assert match is not None
    return match.group("section")


def test_owned_workflows_make_balanced_research_mode_explicit() -> None:
    for name in MODE_AWARE_WORKFLOWS:
        section = _mode_aware_section(_read_workflow(name))
        assert "research_mode=balanced" in section, name


def test_research_phase_splits_balanced_and_yolo_autonomy_rules() -> None:
    section = _mode_aware_section(_read_workflow("research-phase.md"))

    assert "autonomy=balanced/yolo" not in section
    assert "autonomy=balanced" in section
    assert "autonomy=yolo" in section


def test_autonomy_prompt_defaults_preserve_supervised_default() -> None:
    fallback_workflows = (
        "audit-milestone.md",
        "debug.md",
        "digest-knowledge.md",
        "validate-conventions.md",
        "literature-review.md",
    )

    for name in fallback_workflows:
        autonomy_lines = [
            line
            for line in _read_workflow(name).splitlines()
            if line.startswith("AUTONOMY=")
        ]
        assert autonomy_lines, name
        assert all("--default supervised" in line for line in autonomy_lines), name
        assert all('|| echo "balanced"' not in line for line in autonomy_lines), name
        assert all('|| echo "supervised"' in line for line in autonomy_lines), name

    for name in (
        "audit-milestone.md",
        "debug.md",
        "literature-review.md",
        "respond-to-referees.md",
        "plan-phase.md",
        "parameter-sweep.md",
        "quick.md",
        "new-milestone.md",
    ):
        section = _mode_aware_section(_read_workflow(name))
        assert "`autonomy=supervised` (default)" in section, name
        assert "`autonomy=balanced` (default)" not in section, name


def test_help_dedupes_runtime_permission_readiness_trio() -> None:
    help_workflow = _read_workflow("help.md")

    assert help_workflow.count("gpd permissions status --runtime <runtime> --autonomy <mode>") == 1
    assert help_workflow.count("gpd validate unattended-readiness --runtime <runtime> --autonomy <mode>") == 1
    assert help_workflow.count("gpd permissions sync --runtime <runtime> --autonomy <mode>") == 1


def test_help_describes_discover_quick_depth_as_verification_only_without_files() -> None:
    discover_help = _discover_help_section(_read_workflow("help.md"))

    assert "quick (summary)" not in discover_help
    assert re.search(r"verification[- ]only|no files? (?:created|written)|without writing a file", discover_help, re.I)


def test_publication_workflows_read_mode_state_from_init_context() -> None:
    write_paper = _read_workflow("write-paper.md")
    respond = _read_workflow("respond-to-referees.md")

    assert "INIT=$(gpd --raw init phase-op --include config)" in write_paper
    assert 'AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default supervised)' in write_paper
    assert 'RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)' in write_paper
    assert "gpd --raw config get autonomy" not in write_paper
    assert "gpd --raw config get research_mode" not in write_paper

    assert "INIT=$(gpd --raw init phase-op --include config)" in respond
    assert 'AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default supervised)' in respond
    assert "gpd --raw config get autonomy" not in respond

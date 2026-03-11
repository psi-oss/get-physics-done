"""Regression tests for the decision-count regex in check_compaction_needed.

Bug: The original regex required a literal '[' before 'Phase' in each
decision bullet (``- [Phase 3] ...``).  Decisions formatted as
``- Phase 3: ...`` (without brackets) were silently ignored, causing
the compaction trigger to undercount decisions.

Fix: Make the '[' optional — ``\\[?Phase``.
"""

from __future__ import annotations

from pathlib import Path

from gpd.core.health import CheckStatus, check_compaction_needed

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_state_md(tmp_path: Path, decisions_body: str, *, extra_lines: int = 0) -> Path:
    """Create a minimal .gpd/STATE.md with a Decisions section.

    The STATE.md is kept short enough that only the *decision count*
    can fire the compaction trigger (not the line count).
    """
    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)

    padding = "\n".join(f"<!-- pad {i} -->" for i in range(extra_lines))

    content = (
        "# State\n\n"
        "## Position\n\n"
        "Current Phase: 05\n\n"
        "### Decisions\n"
        f"{decisions_body}\n\n"
        "### Blockers\n\n"
        "None.\n"
        f"{padding}\n"
    )
    (planning / "STATE.md").write_text(content, encoding="utf-8")
    return tmp_path


def _make_bracketed_decisions(n: int) -> str:
    """Generate *n* decisions in ``- [Phase X] desc`` format."""
    return "\n".join(f"- [Phase {i % 5 + 1}] Decision {i + 1}" for i in range(n))


def _make_unbracketed_decisions(n: int) -> str:
    """Generate *n* decisions in ``- Phase X: desc`` format (no brackets)."""
    return "\n".join(f"- Phase {i % 5 + 1}: Decision {i + 1}" for i in range(n))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDecisionCountRegex:
    """Verify both bracketed and unbracketed decision formats are counted."""

    def test_bracketed_decisions_counted(self, tmp_path: Path) -> None:
        """Standard ``- [Phase N] desc`` bullets must be counted."""
        decisions = _make_bracketed_decisions(5)
        cwd = _write_state_md(tmp_path, decisions)
        result = check_compaction_needed(cwd)
        assert result.details["decisions"] == 5

    def test_unbracketed_decisions_counted(self, tmp_path: Path) -> None:
        """``- Phase N: desc`` bullets (no brackets) must also be counted.

        This is the regression test for the bug.
        """
        decisions = _make_unbracketed_decisions(5)
        cwd = _write_state_md(tmp_path, decisions)
        result = check_compaction_needed(cwd)
        assert result.details["decisions"] == 5

    def test_mixed_formats_total_correct(self, tmp_path: Path) -> None:
        """A mix of bracketed and unbracketed formats yields the correct total."""
        bracketed = _make_bracketed_decisions(3)
        unbracketed = _make_unbracketed_decisions(4)
        decisions = f"{bracketed}\n{unbracketed}"
        cwd = _write_state_md(tmp_path, decisions)
        result = check_compaction_needed(cwd)
        assert result.details["decisions"] == 7

    def test_no_decisions_returns_zero(self, tmp_path: Path) -> None:
        """An empty decisions section should yield count 0."""
        cwd = _write_state_md(tmp_path, "")
        result = check_compaction_needed(cwd)
        assert result.details["decisions"] == 0
        assert result.status == CheckStatus.OK

    def test_unbracketed_exceeds_threshold_triggers_warn(self, tmp_path: Path) -> None:
        """Enough unbracketed decisions should trigger WARN status.

        DECISION_THRESHOLD is 20, so 25 decisions should exceed it.
        """
        decisions = _make_unbracketed_decisions(25)
        cwd = _write_state_md(tmp_path, decisions)
        result = check_compaction_needed(cwd)
        assert result.details["decisions"] == 25
        assert result.status == CheckStatus.WARN
        assert any("decisions:" in w for w in result.warnings)

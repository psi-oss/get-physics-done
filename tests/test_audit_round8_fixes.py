"""Tests for round 8 codebase audit fixes."""
from __future__ import annotations

from pathlib import Path
import pytest


def test_get_verification_check_valid_id():
    """get_verification_check returns a check for valid ID."""
    from gpd.core.verification_checks import get_verification_check
    check = get_verification_check("5.1")
    assert check is not None
    assert check.name  # should have a name


def test_get_verification_check_invalid_id():
    """get_verification_check returns None for invalid ID."""
    from gpd.core.verification_checks import get_verification_check
    assert get_verification_check("99.99") is None


def test_list_verification_checks_returns_all():
    """list_verification_checks returns non-empty list of check dicts."""
    from gpd.core.verification_checks import list_verification_checks
    checks = list_verification_checks()
    assert len(checks) >= 10  # should have at least 10 checks
    for check in checks:
        assert "check_id" in check
        assert "name" in check


def test_build_artifact_manifest_minimal(tmp_path):
    """build_artifact_manifest with minimal inputs produces valid manifest."""
    from gpd.mcp.paper.artifact_manifest import build_artifact_manifest
    from gpd.mcp.paper.models import PaperConfig, Author, Section

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")

    config = PaperConfig(
        title="Test Paper",
        authors=[Author(name="Test Author", affiliation="Test Univ")],
        abstract="",
        sections=[Section(title="Intro", content="Some content")],
        journal="prl",
    )

    manifest = build_artifact_manifest(config, tmp_path, tex_path=tex_path)
    assert manifest.paper_title == "Test Paper"
    assert manifest.journal == "prl"
    assert len(manifest.artifacts) >= 1  # at least the tex file
    # Check the tex artifact has a sha256
    tex_artifacts = [a for a in manifest.artifacts if a.artifact_id == "tex-paper"]
    assert len(tex_artifacts) == 1
    assert len(tex_artifacts[0].sha256) == 64


def test_build_artifact_manifest_with_bib(tmp_path):
    """build_artifact_manifest includes bib file when provided."""
    from gpd.mcp.paper.artifact_manifest import build_artifact_manifest
    from gpd.mcp.paper.models import PaperConfig, Author, Section

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}\\bibliography{refs}\\end{document}", encoding="utf-8")
    bib_path = tmp_path / "refs.bib"
    bib_path.write_text("@article{test2024, author={Test}, title={Title}, year={2024}}", encoding="utf-8")

    config = PaperConfig(
        title="Test Paper",
        authors=[Author(name="Test Author", affiliation="Test Univ")],
        abstract="",
        sections=[Section(title="Intro", content="Content")],
        journal="mnras",
    )

    manifest = build_artifact_manifest(config, tmp_path, tex_path=tex_path, bib_path=bib_path)
    bib_artifacts = [a for a in manifest.artifacts if a.category == "bib"]
    assert len(bib_artifacts) == 1


def test_strip_placeholder_returns_stripped():
    """_strip_placeholder should return stripped value, not original with whitespace."""
    from gpd.core.state import _strip_placeholder
    result = _strip_placeholder("  some_value  ")
    assert result == "some_value", f"Expected stripped value, got {result!r}"
    # Placeholder values should still return None
    assert _strip_placeholder("\u2014") is None
    assert _strip_placeholder("None") is None
    assert _strip_placeholder("[Not set]") is None
    assert _strip_placeholder(None) is None


def test_progress_percent_default_is_zero():
    """Position model should default progress_percent to 0 (semantic: 0% complete)."""
    from gpd.core.state import Position
    pos = Position()
    assert pos.progress_percent == 0, f"Expected 0 default, got {pos.progress_percent}"


def test_resume_file_none_roundtrip():
    """resume_file=None should round-trip through markdown without becoming string 'None'."""
    from gpd.core.state import generate_state_markdown, parse_state_to_json
    state = {
        "project": {},
        "position": {"current_phase": "01", "status": "Executing"},
        "decisions": [],
        "blockers": [],
        "session": {"resume_file": None, "agent_model": "test"},
        "metrics": [],
        "active_calculations": [],
        "intermediate_results": [],
        "open_questions": [],
    }
    md = generate_state_markdown(state)
    parsed = parse_state_to_json(md)
    session = parsed.get("session", {})
    assert session.get("resume_file") is None, (
        f"resume_file should be None after round-trip, got {session.get('resume_file')!r}"
    )


def test_latex_brace_fix_not_before_documentclass():
    """_fix_unbalanced_braces should not prepend { before \\documentclass."""
    from gpd.utils.latex import _fix_unbalanced_braces
    doc = "\\documentclass{article}\n\\begin{document}\nHello}\n\\end{document}"
    result = _fix_unbalanced_braces(doc)
    assert not result.startswith("{\\documentclass"), (
        "Should not prepend { before \\documentclass"
    )


def test_latex_autofix_structure_before_escaping():
    """Structural fixes should run before character escaping in try_autofix."""
    import inspect
    from gpd.utils.latex import _AUTO_FIX_RULES
    # Find indices of structural vs character fixes
    structural_names = {"_fix_missing_document_begin", "_fix_missing_document_end", "_fix_unbalanced_braces"}
    char_names = {"_fix_unescaped_underscores_and_carets"}

    structural_indices = []
    char_indices = []
    for i, rule in enumerate(_AUTO_FIX_RULES):
        func_name = rule[1].__name__
        if func_name in structural_names:
            structural_indices.append(i)
        if func_name in char_names:
            char_indices.append(i)

    if structural_indices and char_indices:
        assert max(structural_indices) < min(char_indices), (
            f"Structural fixes (indices {structural_indices}) should come before "
            f"character fixes (indices {char_indices})"
        )


def test_latex_texttt_underscore_protected():
    """_fix_unescaped_underscores should not escape underscores inside \\texttt."""
    from gpd.utils.latex import _fix_unescaped_underscores
    tex = "The variable \\texttt{my_var} is important."
    result = _fix_unescaped_underscores(tex)
    assert "\\texttt{my_var}" in result, (
        f"Underscore inside \\texttt should be preserved, got: {result}"
    )


def test_json_set_resolves_cwd(tmp_path, monkeypatch):
    """json set CLI command should resolve file path against --cwd."""
    import gpd.cli as cli_mod
    from typer.testing import CliRunner

    # Create a JSON file in the project dir
    json_file = tmp_path / "test.json"
    json_file.write_text('{"a": 1}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli_mod.app, [
        "--raw", "--cwd", str(tmp_path),
        "json", "set", "--file", "test.json", "--path", "b", "--value", "2"
    ])
    assert result.exit_code == 0, f"Exit code {result.exit_code}: {result.output}"
    # Verify the file was modified
    import json
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data.get("b") in ("2", 2)  # json_set may store as int or string

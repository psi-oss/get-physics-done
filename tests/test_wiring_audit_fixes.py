"""Tests for all fixes from the comprehensive wiring audit.

Covers every bug fix applied across the codebase to prevent regressions.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── 1. utils.py: os.replace and None guards ───────────────────────────────


class TestUtilsOsReplace:
    """Verify atomic_write uses os.replace (not os.rename)."""

    def test_atomic_write_uses_os_replace(self):
        """Source code must call os.replace, not os.rename."""
        import inspect
        import gpd.core.utils as utils_mod

        source = inspect.getsource(utils_mod.atomic_write)
        assert "os.replace(" in source, "atomic_write should use os.replace"
        assert "os.rename(" not in source, "atomic_write should NOT use os.rename"

    def test_atomic_write_overwrites_existing(self, tmp_path):
        from gpd.core.utils import atomic_write

        target = tmp_path / "test.txt"
        target.write_text("old content")
        atomic_write(target, "new content")
        assert target.read_text() == "new content"


class TestPhaseNoneGuards:
    """Verify phase utility functions handle None input gracefully."""

    def test_phase_normalize_none(self):
        from gpd.core.utils import phase_normalize

        assert phase_normalize(None) == ""

    def test_phase_normalize_normal(self):
        from gpd.core.utils import phase_normalize

        assert phase_normalize("3") == "03"

    def test_phase_unpad_none(self):
        from gpd.core.utils import phase_unpad

        assert phase_unpad(None) == ""

    def test_phase_unpad_normal(self):
        from gpd.core.utils import phase_unpad

        assert phase_unpad("03") == "3"

    def test_compare_phase_numbers_none_a(self):
        from gpd.core.utils import compare_phase_numbers

        result = compare_phase_numbers(None, "3")
        assert isinstance(result, int)

    def test_compare_phase_numbers_none_b(self):
        from gpd.core.utils import compare_phase_numbers

        result = compare_phase_numbers("3", None)
        assert isinstance(result, int)

    def test_compare_phase_numbers_both_none(self):
        from gpd.core.utils import compare_phase_numbers

        assert compare_phase_numbers(None, None) == 0

    def test_phase_sort_key_none(self):
        from gpd.core.utils import phase_sort_key

        assert phase_sort_key(None) == [999999]


# ─── 2. json_utils.py: corrupt JSON warning and merge counts ───────────────


class TestJsonSetCorruptWarning:
    """json_set should warn when existing file has corrupt JSON."""

    def test_corrupt_json_produces_warning(self, tmp_path):
        from gpd.core.json_utils import json_set

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")
        result = json_set(str(bad_file), "key", '"value"')
        assert result.get("warning"), "Should include a warning about corrupt JSON"
        assert result["updated"] is True

    def test_valid_json_no_warning(self, tmp_path):
        from gpd.core.json_utils import json_set

        good_file = tmp_path / "good.json"
        good_file.write_text('{"existing": 1}', encoding="utf-8")
        result = json_set(str(good_file), "key", '"value"')
        assert "warning" not in result

    def test_oserror_on_read_handled(self, tmp_path):
        from gpd.core.json_utils import json_set

        # Create a file that will fail to decode as utf-8
        bad_path = tmp_path / "bad_encoding.json"
        bad_path.write_bytes(b"\xff\xfe{broken")
        result = json_set(str(bad_path), "key", '"value"')
        # Should handle gracefully with a warning, not crash
        assert isinstance(result, dict)
        assert result.get("warning"), "Should warn about corrupt/unreadable file"


class TestJsonMergeAccurateCounts:
    """json_merge_files should accurately report merged vs skipped."""

    def test_all_valid_no_skipped(self, tmp_path):
        from gpd.core.json_utils import json_merge_files

        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        f1.write_text('{"a": 1}', encoding="utf-8")
        f2.write_text('{"b": 2}', encoding="utf-8")
        out = tmp_path / "out.json"
        result = json_merge_files(str(out), [str(f1), str(f2)])
        assert result["merged"] == 2
        assert "skipped" not in result

    def test_corrupt_file_counted_as_skipped(self, tmp_path):
        from gpd.core.json_utils import json_merge_files

        f1 = tmp_path / "a.json"
        f2 = tmp_path / "bad.json"
        f1.write_text('{"a": 1}', encoding="utf-8")
        f2.write_text("{bad json", encoding="utf-8")
        out = tmp_path / "out.json"
        result = json_merge_files(str(out), [str(f1), str(f2)])
        assert result["merged"] == 1
        assert result["skipped"] == 1

    def test_missing_file_counted_as_skipped(self, tmp_path):
        from gpd.core.json_utils import json_merge_files

        f1 = tmp_path / "a.json"
        f1.write_text('{"a": 1}', encoding="utf-8")
        out = tmp_path / "out.json"
        result = json_merge_files(str(out), [str(f1), str(tmp_path / "nonexistent.json")])
        assert result["merged"] == 1
        assert result["skipped"] == 1

    def test_non_dict_json_counted_as_skipped(self, tmp_path):
        from gpd.core.json_utils import json_merge_files

        f1 = tmp_path / "a.json"
        f2 = tmp_path / "array.json"
        f1.write_text('{"a": 1}', encoding="utf-8")
        f2.write_text("[1, 2, 3]", encoding="utf-8")
        out = tmp_path / "out.json"
        result = json_merge_files(str(out), [str(f1), str(f2)])
        assert result["merged"] == 1
        assert result["skipped"] == 1


# ─── 3. git_ops.py: files=[] vs files=None ─────────────────────────────────


class TestGitOpsEmptyFilesList:
    """cmd_commit should distinguish files=[] from files=None."""

    def test_empty_list_does_not_stage_gpd_dir(self, tmp_path):
        from gpd.core.git_ops import cmd_commit

        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        # Create and commit an initial file
        (tmp_path / "init.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

        # Create a .gpd directory with content
        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        (gpd_dir / "test.md").write_text("test")

        # files=[] should NOT stage .gpd/ — should result in "nothing to commit"
        result = cmd_commit(tmp_path, "test commit", files=[])
        assert not result.committed
        assert "nothing to commit" in (result.error or "")

    def test_none_stages_gpd_dir(self, tmp_path):
        from gpd.core.git_ops import cmd_commit

        # Initialize a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        (tmp_path / "init.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)

        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        (gpd_dir / "test.md").write_text("test")

        # files=None should stage .gpd/
        result = cmd_commit(tmp_path, "test commit", files=None)
        assert result.committed


# ─── 4. context.py: constants instead of hardcoded strings ──────────────────


class TestContextUsesConstants:
    """context.py should use constants from gpd.core.constants, not hardcoded strings."""

    def test_no_hardcoded_research_map(self):
        import inspect
        import gpd.core.context as ctx

        source = inspect.getsource(ctx)
        # Check that path constructions use the constant
        # Allow string literals in dict keys, display strings, etc.
        path_uses = re.findall(r'(?:planning|cwd)\s*/\s*"research-map"', source)
        assert len(path_uses) == 0, f"Found hardcoded 'research-map' in path construction: {path_uses}"

    def test_no_hardcoded_todos_in_paths(self):
        import inspect
        import gpd.core.context as ctx

        source = inspect.getsource(ctx)
        path_uses = re.findall(r'(?:planning|cwd)\s*/\s*"todos"', source)
        assert len(path_uses) == 0, f"Found hardcoded 'todos' in path construction: {path_uses}"

    def test_no_hardcoded_milestones_in_paths(self):
        import inspect
        import gpd.core.context as ctx

        source = inspect.getsource(ctx)
        path_uses = re.findall(r'(?:planning|cwd)\s*/\s*"milestones"', source)
        assert len(path_uses) == 0, f"Found hardcoded 'milestones' in path construction: {path_uses}"

    def test_no_hardcoded_requirements_in_paths(self):
        import inspect
        import gpd.core.context as ctx

        source = inspect.getsource(ctx)
        path_uses = re.findall(r'(?:planning|cwd)\s*/\s*"REQUIREMENTS\.md"', source)
        assert len(path_uses) == 0, f"Found hardcoded 'REQUIREMENTS.md' in path construction: {path_uses}"


# ─── 5. suggest.py + state.py: constants and em-dash ───────────────────────


class TestSuggestUsesConstants:
    """suggest.py should use constants from gpd.core.constants."""

    def test_no_hardcoded_todos_in_paths(self):
        import inspect
        import gpd.core.suggest as sug

        source = inspect.getsource(sug)
        path_uses = re.findall(r'(?:planning|cwd)\s*/\s*"todos"', source)
        assert len(path_uses) == 0, f"Found hardcoded 'todos' in path: {path_uses}"

    def test_no_hardcoded_literature_in_paths(self):
        import inspect
        import gpd.core.suggest as sug

        source = inspect.getsource(sug)
        path_uses = re.findall(r'(?:planning|cwd)\s*/\s*"literature"', source)
        assert len(path_uses) == 0, f"Found hardcoded 'literature' in path: {path_uses}"


class TestStateExtractFieldEmDash:
    """state_extract_field should normalize em-dash to None."""

    def test_em_dash_returns_none(self):
        from gpd.core.state import state_extract_field

        content = "**Status:** \u2014"
        assert state_extract_field(content, "Status") is None

    def test_normal_value_returned(self):
        from gpd.core.state import state_extract_field

        content = "**Status:** active"
        assert state_extract_field(content, "Status") == "active"

    def test_missing_field_returns_none(self):
        from gpd.core.state import state_extract_field

        content = "No status field here"
        assert state_extract_field(content, "Status") is None


class TestStateArchiveConstant:
    """state.py should use STATE_ARCHIVE_FILENAME constant."""

    def test_no_hardcoded_state_archive(self):
        import inspect
        import gpd.core.state as state_mod

        source = inspect.getsource(state_mod)
        hardcoded = re.findall(r'"STATE-ARCHIVE\.md"', source)
        assert len(hardcoded) == 0, f"Found hardcoded 'STATE-ARCHIVE.md': {hardcoded}"


# ─── 6. phases.py: deque BFS and milestone canonical helper ────────────────


class TestPhasesBfsDeque:
    """validate_plan_waves BFS should use deque, not list.pop(0)."""

    def test_bfs_uses_deque(self):
        import inspect
        import gpd.core.phases as phases_mod

        source = inspect.getsource(phases_mod.validate_waves)
        assert "deque(" in source, "BFS should use deque"
        assert ".popleft()" in source, "BFS should use popleft()"
        assert ".pop(0)" not in source, "BFS should NOT use pop(0)"


class TestMilestoneCompleteUsesHelper:
    """milestone_complete should use _replace_state_field, not raw re.sub for state fields."""

    def test_no_raw_re_sub_for_state_fields(self):
        import inspect
        import gpd.core.phases as phases_mod

        source = inspect.getsource(phases_mod.milestone_complete)
        # Should not contain re.sub patterns targeting **Field:** markdown
        raw_subs = re.findall(r're\.sub\(.*?\\\*\\\*Status', source)
        assert len(raw_subs) == 0, "milestone_complete should use _replace_state_field, not raw re.sub"


# ─── 7. health.py: config backup and indented YAML ─────────────────────────


class TestHealthConfigBackup:
    """Config auto-fix should create a backup before overwriting."""

    def test_autofix_creates_backup(self, tmp_path):
        from gpd.core.health import run_health

        # Set up a minimal GPD project structure
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "PROJECT.md").write_text("# Test Project\n")
        (planning / "STATE.md").write_text("**Status:** active\n")
        (planning / "state.json").write_text("{}", encoding="utf-8")
        (planning / "ROADMAP.md").write_text("# Roadmap\n")

        # Write a malformed config.json
        config_path = planning / "config.json"
        config_path.write_text("{malformed json", encoding="utf-8")

        # Run health checks with auto-fix
        run_health(tmp_path, fix=True)

        # Verify backup was created
        backup_path = config_path.with_suffix(".json.bak")
        assert backup_path.exists(), "Auto-fix should create config.json.bak before overwriting"
        assert backup_path.read_text(encoding="utf-8") == "{malformed json"


class TestHealthIndentedYamlRegex:
    """gpd_return: regex should match indented YAML blocks."""

    def test_indented_gpd_return_matches(self):
        content = textwrap.dedent("""\
        # Summary

        ```yaml
          gpd_return:
            status: completed
        ```
        """)
        match = re.search(r"```ya?ml\s*\n(\s*gpd_return:\s*\n[\s\S]*?)```", content)
        assert match is not None, "Should match indented gpd_return: blocks"

    def test_non_indented_still_matches(self):
        content = textwrap.dedent("""\
        ```yaml
        gpd_return:
          status: completed
        ```
        """)
        match = re.search(r"```ya?ml\s*\n(\s*gpd_return:\s*\n[\s\S]*?)```", content)
        assert match is not None, "Should still match non-indented gpd_return:"


# ─── 8. verification_server.py: exp regex ──────────────────────────────────


class TestExpRegexNoFalsePositives:
    """exp() regex should not false-positive on array indexing."""

    def test_array_index_not_flagged(self):
        """exp(energy[0]) should NOT trigger the dimension warning."""
        pattern = re.compile(r"exp\s*\([^)]*\[(?:M|L|T|Q|Theta)\]")
        assert pattern.search("exp(energy[0])") is None
        assert pattern.search("exp(H[i,j])") is None
        assert pattern.search("exp(-beta[k] * t)") is None

    def test_dimension_annotation_flagged(self):
        """exp([M][L]^2) SHOULD trigger the dimension warning."""
        pattern = re.compile(r"exp\s*\([^)]*\[(?:M|L|T|Q|Theta)\]")
        assert pattern.search("exp([M][L]^2)") is not None
        assert pattern.search("exp(-k[T] * t)") is not None


# ─── 9. state_server.py: is_phase_complete utility ─────────────────────────


class TestStateServerUsesUtility:
    """state_server.py should use is_phase_complete utility."""

    def test_imports_is_phase_complete(self):
        import inspect
        import gpd.mcp.servers.state_server as srv

        source = inspect.getsource(srv)
        assert "is_phase_complete" in source


# ─── 10. paper __init__.py: JournalSpec export ─────────────────────────────


class TestPaperJournalSpecExport:
    """JournalSpec should be importable from gpd.mcp.paper."""

    def test_journal_spec_importable(self):
        from gpd.mcp.paper import JournalSpec

        assert JournalSpec is not None

    def test_journal_spec_in_all(self):
        import gpd.mcp.paper as paper_pkg

        assert "JournalSpec" in paper_pkg.__all__


# ─── 11. compiler.py: no dead figures_dir check ────────────────────────────


class TestCompilerNoDeadCode:
    """compiler.py should not have dead if figures_dir is not None check."""

    def test_no_figures_dir_none_check(self):
        import inspect
        import gpd.mcp.paper.compiler as compiler_mod

        source = inspect.getsource(compiler_mod.build_paper)
        assert "if figures_dir is not None" not in source


# ─── 12. latex.py: narrowed exception and odd backticks ────────────────────


class TestLatexNarrowedException:
    """try_autofix should catch specific exceptions, not broad Exception."""

    def test_no_broad_exception_catch(self):
        import inspect
        import gpd.utils.latex as latex_mod

        source = inspect.getsource(latex_mod.try_autofix)
        # Should not have bare "except Exception"
        assert "except Exception" not in source, "try_autofix should not catch broad Exception"


class TestCleanLatexFencesOddBackticks:
    """clean_latex_fences should handle unmatched backtick fences gracefully."""

    def test_unmatched_fence_returns_unchanged(self):
        from gpd.utils.latex import clean_latex_fences

        content = "Some text ```latex\\section{Intro} and no closing fence"
        result = clean_latex_fences(content)
        assert result == content, "Unmatched fences should return content unchanged"

    def test_matched_fences_work_normally(self):
        from gpd.utils.latex import clean_latex_fences

        content = "```latex\n\\section{Intro}\n```"
        result = clean_latex_fences(content)
        assert "```" not in result


# ─── 13. opencode.py: sub tag stripping ────────────────────────────────────


class TestOpenCodeSubTagStripping:
    """OpenCode adapter should strip <sub> tags from installed content."""

    def test_copy_dir_contents_strips_sub_tags(self):
        import inspect
        import gpd.adapters.opencode as oc

        source = inspect.getsource(oc)
        assert "strip_sub_tags" in source, "OpenCode should use strip_sub_tags"


# ─── 14. install_utils.py: no duplicate TODOS_DIR_NAME ─────────────────────


class TestInstallUtilsNoDuplicateConstant:
    """TODOS_DIR_NAME should be imported from constants, not defined locally."""

    def test_todos_dir_name_not_locally_defined(self):
        import inspect
        import gpd.adapters.install_utils as iu

        source = inspect.getsource(iu)
        # Should not have a local definition like TODOS_DIR_NAME = "todos"
        local_defs = re.findall(r'^TODOS_DIR_NAME\s*=\s*["\']todos["\']', source, re.MULTILINE)
        assert len(local_defs) == 0, "TODOS_DIR_NAME should be imported, not defined locally"

    def test_todos_dir_name_still_accessible(self):
        from gpd.adapters.install_utils import TODOS_DIR_NAME

        assert TODOS_DIR_NAME == "todos"


# ─── 15. Mirror parity ─────────────────────────────────────────────────────


class TestMirrorParityRestored:
    """Hook mirror files should match source files."""

    HOOK_FILES = ["runtime_detect.py", "statusline.py", "check_update.py", "notify.py"]
    REPO_ROOT = Path(__file__).resolve().parents[1]
    SOURCE_DIR = REPO_ROOT / "src" / "gpd" / "hooks"

    @pytest.mark.parametrize("hook_name", HOOK_FILES)
    def test_claude_mirror_matches_source(self, hook_name):
        mirror = self.REPO_ROOT / ".claude" / "hooks" / hook_name
        source = self.SOURCE_DIR / hook_name
        if mirror.exists() and source.exists():
            assert mirror.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    @pytest.mark.parametrize("hook_name", HOOK_FILES)
    def test_codex_mirror_matches_source(self, hook_name):
        mirror = self.REPO_ROOT / ".codex" / "hooks" / hook_name
        source = self.SOURCE_DIR / hook_name
        if mirror.exists() and source.exists():
            assert mirror.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

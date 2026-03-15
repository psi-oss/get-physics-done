"""Edge-case tests for install_utils.py — covers 5 categories:
1. expand_at_includes: nested includes, cycles, code fences
2. parse_jsonc: comments, BOM, trailing commas
3. write_settings: atomic write
4. generate_manifest: SHA256 correctness
5. copy_with_path_replacement: rollback on failure
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.adapters.install_utils import (
    build_hook_command,
    convert_tool_references_in_body,
    copy_with_path_replacement,
    ensure_update_hook,
    expand_at_includes,
    generate_manifest,
    get_global_dir,
    hook_python_interpreter,
    parse_jsonc,
    pre_install_cleanup,
    protect_runtime_agent_prompt,
    read_settings,
    replace_placeholders,
    translate_frontmatter_tool_names,
    write_manifest,
    write_settings,
)


def _bundled_hook_text(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / "src" / "gpd" / "hooks" / name).read_text(encoding="utf-8")

# =========================================================================
# 1. expand_at_includes
# =========================================================================


def test_get_global_dir_unknown_runtime_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="Unknown runtime"):
        get_global_dir("bogus-runtime")


def test_replace_placeholders_unknown_runtime_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="Unknown runtime"):
        replace_placeholders("{GPD_RUNTIME_FLAG}", "/custom/", "bogus-runtime")


class TestExpandAtIncludes:
    """Tests for expand_at_includes: nested includes, cycles, code fences."""

    def _make_src(self, tmp_path: Path, files: dict[str, str]) -> Path:
        """Create a source tree under tmp_path/get-physics-done/ and return the gpd dir."""
        gpd_dir = tmp_path / "get-physics-done"
        gpd_dir.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            p = gpd_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return gpd_dir

    def test_simple_include(self, tmp_path: Path) -> None:
        gpd_dir = self._make_src(tmp_path, {"sub.md": "included body"})
        content = f"@{tmp_path}/get-physics-done/sub.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "included body" in result
        assert "<!-- [included: sub.md] -->" in result

    def test_nested_includes(self, tmp_path: Path) -> None:
        """Two levels of nesting: A includes B which includes C."""
        gpd_dir = self._make_src(
            tmp_path,
            {
                "c.md": "leaf content",
                "b.md": f"before\n@{tmp_path}/get-physics-done/c.md\nafter",
                "a.md": f"top\n@{tmp_path}/get-physics-done/b.md\nbottom",
            },
        )
        content = f"@{tmp_path}/get-physics-done/b.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "leaf content" in result
        assert "before" in result

    def test_cycle_detection(self, tmp_path: Path) -> None:
        """A includes B, B includes A — should detect cycle."""
        gpd_dir = self._make_src(
            tmp_path,
            {
                "a.md": f"@{tmp_path}/get-physics-done/b.md",
                "b.md": f"@{tmp_path}/get-physics-done/a.md",
            },
        )
        content = f"@{tmp_path}/get-physics-done/a.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "cycle detected" in result

    def test_self_cycle_detection(self, tmp_path: Path) -> None:
        """File that includes itself."""
        gpd_dir = self._make_src(
            tmp_path,
            {"self.md": f"@{tmp_path}/get-physics-done/self.md"},
        )
        content = f"@{tmp_path}/get-physics-done/self.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "cycle detected" in result

    def test_code_fence_protection(self, tmp_path: Path) -> None:
        """@include inside code fences should NOT be expanded."""
        gpd_dir = self._make_src(tmp_path, {"sub.md": "should not appear"})
        content = f"before\n```\n@{tmp_path}/get-physics-done/sub.md\n```\nafter"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        # Original @include line should remain unchanged
        assert f"@{tmp_path}/get-physics-done/sub.md" in result
        assert "<!-- [included:" not in result

    def test_code_fence_triple_backtick_with_language(self, tmp_path: Path) -> None:
        """Code fence with language tag (```python) should still protect."""
        gpd_dir = self._make_src(tmp_path, {"sub.md": "should not appear"})
        content = f"```python\n@{tmp_path}/get-physics-done/sub.md\n```\n"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "<!-- [included:" not in result

    def test_depth_limit(self, tmp_path: Path) -> None:
        """Beyond MAX_INCLUDE_EXPANSION_DEPTH, includes are not expanded."""
        gpd_dir = self._make_src(tmp_path, {"deep.md": "deep content"})
        content = f"@{tmp_path}/get-physics-done/deep.md"
        # Start at depth = MAX (10)
        result = expand_at_includes(content, str(gpd_dir), "~/.test/", depth=10)
        # At depth=10, function returns content immediately
        assert "deep content" not in result

    def test_bibtex_not_expanded(self, tmp_path: Path) -> None:
        """@article{...} should not be treated as an include."""
        gpd_dir = self._make_src(tmp_path, {})
        content = '@article{doe2024, title="Test"}'
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert result == content

    def test_missing_file_comment(self, tmp_path: Path) -> None:
        """Include of a missing file produces a 'not resolved' comment."""
        gpd_dir = self._make_src(tmp_path, {})
        content = f"@{tmp_path}/get-physics-done/missing.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "not resolved" in result

    def test_frontmatter_stripped(self, tmp_path: Path) -> None:
        """Included file with YAML frontmatter should strip it."""
        gpd_dir = self._make_src(
            tmp_path,
            {"fm.md": "---\ntitle: Test\n---\nactual body"},
        )
        content = f"@{tmp_path}/get-physics-done/fm.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "actual body" in result
        assert "title: Test" not in result

    def test_frontmatter_with_triple_dash_value_is_stripped_without_corrupting_body(self, tmp_path: Path) -> None:
        gpd_dir = self._make_src(
            tmp_path,
            {"fm.md": "---\ndescription: before --- after\n---\nactual body"},
        )
        content = f"@{tmp_path}/get-physics-done/fm.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "actual body" in result
        assert "description: before --- after" not in result

    def test_path_replacement_in_included(self, tmp_path: Path) -> None:
        """Included files should have canonical GPD placeholders replaced."""
        gpd_dir = self._make_src(
            tmp_path,
            {"paths.md": "dir={GPD_INSTALL_DIR} config={GPD_CONFIG_DIR}/foo"},
        )
        content = f"@{tmp_path}/get-physics-done/paths.md"
        result = expand_at_includes(content, str(gpd_dir), "/custom/", runtime="claude-code")
        assert "dir=/custom/get-physics-done" in result
        assert "config=/custom/foo" in result

    def test_planning_paths_skipped(self, tmp_path: Path) -> None:
        """.gpd/ paths are project-specific, should not be expanded."""
        gpd_dir = self._make_src(tmp_path, {})
        content = "@.gpd/research/notes.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert result == content

    def test_example_paths_skipped(self, tmp_path: Path) -> None:
        """path/ prefixed paths are examples, should not be expanded."""
        gpd_dir = self._make_src(tmp_path, {})
        content = "@path/to/example.md"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert result == content

    def test_no_slash_not_treated_as_include(self, tmp_path: Path) -> None:
        """@decorator or @mention without / should not be treated as include."""
        gpd_dir = self._make_src(tmp_path, {})
        content = "@decorator_name"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert result == content

    def test_bullet_list_include_is_expanded(self, tmp_path: Path) -> None:
        gpd_dir = self._make_src(tmp_path, {"workflow.md": "workflow body"})
        content = f"- @{tmp_path}/get-physics-done/workflow.md (main workflow)"
        result = expand_at_includes(content, str(gpd_dir), "~/.test/")
        assert "workflow body" in result
        assert "<!-- [included: workflow.md] -->" in result

    def test_gpd_agents_dir_include_resolves_from_specs_root(self, tmp_path: Path) -> None:
        gpd_dir = self._make_src(
            tmp_path,
            {
                "agents/gpd-shared.md": "---\ndescription: shared\n---\nShared agent body\n",
                "specs/references/ref.md": "ref body\n",
            },
        )
        result = expand_at_includes(
            "@{GPD_AGENTS_DIR}/gpd-shared.md",
            gpd_dir / "specs",
            "/custom/",
            runtime="gemini",
        )

        assert "Shared agent body" in result
        assert "<!-- [included: gpd-shared.md] -->" in result


# =========================================================================
# 1b. protect_runtime_agent_prompt
# =========================================================================


class TestProtectRuntimeAgentPrompt:
    """Tests for runtime-specific agent prompt sanitization."""

    def test_rewrites_braced_and_shell_fence_vars_for_dollar_template_runtimes(self) -> None:
        content = (
            "---\n"
            "name: gpd:test\n"
            "description: test\n"
            "---\n"
            "Use ${PHASE_ARG} for planning.\n"
            "Fallback to ${PHASE_ARG:-plan} when unset.\n"
            "Strip suffixes with ${FILE%.*} before writing outputs.\n"
            "Also inspect $ARGUMENTS and store cache metadata in $CACHE.\n"
            'Use `file_read("$artifact_path")` to inspect the artifact.\n'
            "\n"
            "```bash\n"
            'echo "$phase_dir" "${PHASE_ARG}" "$file"\n'
            "$gpd-help\n"
            "echo $phase_number\n"
            "```\n"
            "\n"
            "Physics prose keeps $T$ and $T_N = 0.17(1)$ untouched outside shell examples.\n"
            'Inline math examples like `$sin(x)$` stay intact.\n'
        )

        for runtime in ("gemini", "opencode"):
            result = protect_runtime_agent_prompt(content, runtime)
            assert "${PHASE_ARG}" not in result
            assert "${PHASE_ARG:-plan}" not in result
            assert "${FILE%.*}" not in result
            assert "$ARGUMENTS" not in result
            assert "$CACHE" not in result
            assert "$phase_dir" not in result
            assert "$file" not in result
            assert "$phase_number" not in result
            assert "$artifact_path" not in result
            assert "<PHASE_ARG>" in result
            assert "Fallback to <PHASE_ARG> when unset." in result
            assert "Strip suffixes with <FILE> before writing outputs." in result
            assert "<ARGUMENTS>" in result
            assert "<CACHE>" in result
            assert "<phase_dir>" in result
            assert "<file>" in result
            assert "<phase_number>" in result
            assert "<artifact_path>" in result
            assert "$gpd-help" in result
            assert "Physics prose keeps $T$ and $T_N = 0.17(1)$ untouched" in result
            assert "$T_N = 0.17(1)$" in result
            assert "`$sin(x)$`" in result

    def test_noop_for_runtimes_without_dollar_template_collision(self) -> None:
        content = (
            "---\n"
            "name: gpd:test\n"
            "description: test\n"
            "---\n"
            "Use ${PHASE_ARG}, ${PHASE_ARG:-plan}, ${FILE%.*}, and $ARGUMENTS.\n"
            "```bash\n"
            'echo "$phase_dir"\n'
            "```\n"
        )

        for runtime in ("claude-code", "codex"):
            assert protect_runtime_agent_prompt(content, runtime) == content


class TestTranslateFrontmatterToolNames:
    def test_inline_yaml_array_tools_are_translated(self) -> None:
        content = "---\nallowed-tools: [Read, Edit]\n---\nBody\n"

        translated = translate_frontmatter_tool_names(
            content,
            lambda name: {"Read": "file_read", "Edit": "file_edit"}.get(name),
        )

        assert "allowed-tools: file_read, file_edit" in translated

    def test_quoted_list_items_are_translated(self) -> None:
        content = "---\ntools:\n  - \"Read\"\n  - 'Edit'\n---\nBody\n"

        translated = translate_frontmatter_tool_names(
            content,
            lambda name: {"Read": "file_read", "Edit": "file_edit"}.get(name),
        )

        assert "tools:\n  - file_read\n  - file_edit" in translated

    def test_frontmatter_with_literal_delimiter_text_keeps_frontmatter_vars_intact(self) -> None:
        content = (
            "---\n"
            "name: gpd:test\n"
            "description: keep --- and $HOME literal\n"
            "---\n"
            "Body uses $USER.\n"
        )

        for runtime in ("gemini", "opencode"):
            result = protect_runtime_agent_prompt(content, runtime)
            assert "description: keep --- and $HOME literal" in result
            assert "Body uses <USER>." in result


# =========================================================================
# 2. parse_jsonc
# =========================================================================


class TestParseJsonc:
    """Tests for parse_jsonc: comments, BOM, trailing commas."""

    def test_plain_json(self) -> None:
        result = parse_jsonc('{"key": "value"}')
        assert result == {"key": "value"}

    def test_single_line_comments(self) -> None:
        content = '{\n  // This is a comment\n  "key": "value"\n}'
        result = parse_jsonc(content)
        assert result == {"key": "value"}

    def test_block_comments(self) -> None:
        content = '{\n  /* block comment */\n  "key": "value"\n}'
        result = parse_jsonc(content)
        assert result == {"key": "value"}

    def test_multiline_block_comment(self) -> None:
        content = '{\n  /* multi\n     line\n     comment */\n  "key": "value"\n}'
        result = parse_jsonc(content)
        assert result == {"key": "value"}

    def test_inline_comment(self) -> None:
        content = '{\n  "key": "value" // inline comment\n}'
        result = parse_jsonc(content)
        assert result == {"key": "value"}

    def test_trailing_comma_object(self) -> None:
        content = '{\n  "a": 1,\n  "b": 2,\n}'
        result = parse_jsonc(content)
        assert result == {"a": 1, "b": 2}

    def test_trailing_comma_array(self) -> None:
        content = '{"arr": [1, 2, 3,]}'
        result = parse_jsonc(content)
        assert result == {"arr": [1, 2, 3]}

    def test_bom_stripped(self) -> None:
        content = '\ufeff{"key": "value"}'
        result = parse_jsonc(content)
        assert result == {"key": "value"}

    def test_comment_inside_string_preserved(self) -> None:
        """// inside a string is not a comment."""
        content = '{"url": "https://example.com"}'
        result = parse_jsonc(content)
        assert result == {"url": "https://example.com"}

    def test_block_comment_inside_string_preserved(self) -> None:
        """/* */ inside a string is not a comment."""
        content = '{"pattern": "/* not a comment */"}'
        result = parse_jsonc(content)
        assert result == {"pattern": "/* not a comment */"}

    def test_escaped_quote_in_string(self) -> None:
        r"""Escaped \" inside a string should not break parsing."""
        content = r'{"msg": "she said \"hi\""}'
        result = parse_jsonc(content)
        assert result == {"msg": 'she said "hi"'}

    def test_all_features_combined(self) -> None:
        """BOM + comments + trailing commas all at once."""
        content = '\ufeff{\n  // comment\n  "a": 1,\n  /* block */\n  "b": [1, 2,],\n  "c": "// not a comment",\n}\n'
        result = parse_jsonc(content)
        assert result == {"a": 1, "b": [1, 2], "c": "// not a comment"}

    def test_empty_object(self) -> None:
        assert parse_jsonc("{}") == {}

    def test_nested_objects_with_comments(self) -> None:
        content = '{\n  "outer": {\n    // inner comment\n    "inner": true,\n  },\n}'
        result = parse_jsonc(content)
        assert result == {"outer": {"inner": True}}

    def test_comment_only_lines(self) -> None:
        content = '// comment\n{"key": 1}\n// trailing'
        result = parse_jsonc(content)
        assert result == {"key": 1}

    def test_invalid_json_raises(self) -> None:
        """parse_jsonc should raise on truly invalid JSON after stripping comments."""
        with pytest.raises(json.JSONDecodeError):
            parse_jsonc("{not valid json}")


class TestReadSettings:
    """Tests for read_settings: JSONC support and safe fallback behavior."""

    def test_preserves_valid_jsonc_settings(self, tmp_path: Path) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            '{\n  // preserve this file\n  "theme": "solarized",\n  "nested": {"enabled": true,},\n}\n',
            encoding="utf-8",
        )

        assert read_settings(settings_path) == {
            "theme": "solarized",
            "nested": {"enabled": True},
        }


class TestBuildHookCommand:
    """Tests for build_hook_command: shared interpreter selection."""

    def test_defaults_to_current_python_interpreter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/custom/venv/bin/python")

        command = build_hook_command(
            tmp_path,
            "statusline.py",
            is_global=False,
            config_dir_name=".claude",
        )

        assert command == "/custom/venv/bin/python .claude/hooks/statusline.py"

    def test_explicit_target_uses_absolute_hook_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/custom/venv/bin/python")

        command = build_hook_command(
            tmp_path,
            "statusline.py",
            is_global=False,
            config_dir_name=".claude",
            explicit_target=True,
        )

        assert command == f"/custom/venv/bin/python {tmp_path / 'hooks' / 'statusline.py'}"

    def test_gpd_python_override_beats_other_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GPD_PYTHON", "/env/override/python")
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/ambient/python")

        assert hook_python_interpreter() == "/env/override/python"

    def test_prefers_managed_gpd_python_outside_checkout(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        managed_home = tmp_path / "managed-home"
        managed_python = managed_home / "venv" / "bin" / "python"
        managed_python.parent.mkdir(parents=True)
        managed_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

        monkeypatch.delenv("GPD_PYTHON", raising=False)
        monkeypatch.setenv("GPD_HOME", str(managed_home))
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/ambient/python")
        monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)

        assert hook_python_interpreter() == str(managed_python)

    def test_checkout_prefers_active_python_even_when_managed_env_exists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        managed_home = tmp_path / "managed-home"
        managed_python = managed_home / "venv" / "bin" / "python"
        managed_python.parent.mkdir(parents=True)
        managed_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

        monkeypatch.delenv("GPD_PYTHON", raising=False)
        monkeypatch.setenv("GPD_HOME", str(managed_home))
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/repo/.venv/bin/python")
        monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: Path("/repo"))

        assert hook_python_interpreter() == "/repo/.venv/bin/python"


class TestEnsureUpdateHook:
    """Tests for managed update-hook repair and deduplication."""

    def test_rewrites_stale_managed_command_and_preserves_other_hooks(self) -> None:
        settings = {
            "hooks": {
                "SessionStart": [
                    {
                        "matcher": "startup",
                        "hooks": [
                            {"type": "command", "command": "python3 .claude/hooks/check_update.py"},
                            {"type": "command", "command": "echo keep-me"},
                        ],
                    },
                    {
                        "hooks": [
                            {"type": "command", "command": "python3 .claude/hooks/check_update.py"},
                        ]
                    },
                ]
            }
        }

        ensure_update_hook(settings, "/custom/venv/bin/python .claude/hooks/check_update.py")

        session_start = settings["hooks"]["SessionStart"]
        assert len(session_start) == 1
        assert session_start[0]["matcher"] == "startup"
        commands = [hook["command"] for hook in session_start[0]["hooks"] if isinstance(hook, dict)]
        assert commands == [
            "/custom/venv/bin/python .claude/hooks/check_update.py",
            "echo keep-me",
        ]


# =========================================================================
# 3. write_settings
# =========================================================================


class TestWriteSettings:
    """Tests for write_settings: atomic write behavior."""

    def test_creates_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        write_settings(target, {"key": "value"})
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == {"key": "value"}

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "settings.json"
        target.write_text('{"old": true}', encoding="utf-8")
        write_settings(target, {"new": True})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == {"new": True}
        assert "old" not in data

    def test_tmp_file_cleaned_up(self, tmp_path: Path) -> None:
        """After write, the .tmp file should not remain."""
        target = tmp_path / "settings.json"
        write_settings(target, {"key": "value"})
        tmp_file = target.with_suffix(".tmp")
        assert not tmp_file.exists()

    def test_output_is_formatted(self, tmp_path: Path) -> None:
        """Output should be indented JSON with trailing newline."""
        target = tmp_path / "settings.json"
        write_settings(target, {"a": 1, "b": 2})
        content = target.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert "  " in content  # indented

    def test_atomic_semantics_no_partial_write(self, tmp_path: Path) -> None:
        """If the rename step failed, original file should be untouched."""
        target = tmp_path / "settings.json"
        target.write_text('{"original": true}', encoding="utf-8")

        # Patch rename to fail
        with patch.object(Path, "rename", side_effect=OSError("rename failed")):
            with pytest.raises(OSError, match="rename failed"):
                write_settings(target, {"new": True})

        # Original should be intact (write_text succeeded on .tmp, rename failed)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == {"original": True}


# =========================================================================
# 4. generate_manifest
# =========================================================================


class TestGenerateManifest:
    """Tests for generate_manifest: SHA256 correctness."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        manifest = generate_manifest(d)
        assert manifest == {}

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        manifest = generate_manifest(tmp_path / "nonexistent")
        assert manifest == {}

    def test_single_file_hash_correct(self, tmp_path: Path) -> None:
        d = tmp_path / "files"
        d.mkdir()
        f = d / "test.txt"
        f.write_text("hello world", encoding="utf-8")

        expected_hash = hashlib.sha256(b"hello world").hexdigest()
        manifest = generate_manifest(d)
        assert manifest == {"test.txt": expected_hash}

    def test_nested_directory_posix_paths(self, tmp_path: Path) -> None:
        """Paths in manifest should be POSIX-style (forward slashes)."""
        d = tmp_path / "root"
        sub = d / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "file.txt").write_text("nested", encoding="utf-8")

        manifest = generate_manifest(d)
        assert "sub/deep/file.txt" in manifest
        assert "\\" not in list(manifest.keys())[0]

    def test_multiple_files_all_hashed(self, tmp_path: Path) -> None:
        d = tmp_path / "multi"
        d.mkdir()
        for name in ["a.txt", "b.txt", "c.txt"]:
            (d / name).write_text(f"content of {name}", encoding="utf-8")

        manifest = generate_manifest(d)
        assert len(manifest) == 3
        for name in ["a.txt", "b.txt", "c.txt"]:
            expected = hashlib.sha256(f"content of {name}".encode()).hexdigest()
            assert manifest[name] == expected

    def test_custom_base_dir(self, tmp_path: Path) -> None:
        """base_dir parameter changes relative path calculation."""
        base = tmp_path / "base"
        d = base / "sub"
        d.mkdir(parents=True)
        (d / "file.txt").write_text("test", encoding="utf-8")

        manifest = generate_manifest(d, base_dir=base)
        assert "sub/file.txt" in manifest

    def test_binary_file_hashed_correctly(self, tmp_path: Path) -> None:
        """Binary files should be hashed correctly."""
        d = tmp_path / "bin"
        d.mkdir()
        data = bytes(range(256))
        (d / "binary.bin").write_bytes(data)

        expected = hashlib.sha256(data).hexdigest()
        manifest = generate_manifest(d)
        assert manifest["binary.bin"] == expected

    def test_sorted_output(self, tmp_path: Path) -> None:
        """Files should be sorted (since iterdir uses sorted())."""
        d = tmp_path / "sorted"
        d.mkdir()
        for name in ["z.txt", "a.txt", "m.txt"]:
            (d / name).write_text(name, encoding="utf-8")

        manifest = generate_manifest(d)
        keys = list(manifest.keys())
        assert keys == sorted(keys)


# =========================================================================
# 5. copy_with_path_replacement
# =========================================================================


class TestCopyWithPathReplacement:
    """Tests for copy_with_path_replacement: rollback on failure."""

    def _make_src(self, tmp_path: Path) -> Path:
        src = tmp_path / "src"
        src.mkdir()
        (src / "readme.md").write_text(
            "Config: {GPD_CONFIG_DIR}/foo\nDir: {GPD_INSTALL_DIR}/bar\nAgents: {GPD_AGENTS_DIR}/baz",
            encoding="utf-8",
        )
        (src / "script.sh").write_text("#!/bin/bash\necho ok", encoding="utf-8")
        return src

    def test_basic_copy(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dest = tmp_path / "dest"
        copy_with_path_replacement(src, dest, "/custom/", "claude-code")

        assert dest.exists()
        md_content = (dest / "readme.md").read_text(encoding="utf-8")
        assert "Config: /custom/foo" in md_content
        assert "/custom/get-physics-done/bar" in md_content
        assert "/custom/agents/baz" in md_content

        sh_content = (dest / "script.sh").read_text(encoding="utf-8")
        assert "echo ok" in sh_content

    def test_codex_slash_command_conversion(self, tmp_path: Path) -> None:
        """Codex runtime should convert /gpd: to $gpd-."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "commands.md").write_text("Use /gpd:execute-phase to run.", encoding="utf-8")

        dest = tmp_path / "dest"
        copy_with_path_replacement(src, dest, "/custom/", "codex")

        content = (dest / "commands.md").read_text(encoding="utf-8")
        assert "$gpd-execute-phase" in content
        assert "/gpd:" not in content

    def test_function_style_tool_invocations_are_rewritten(self) -> None:
        """Contextual tool references like task(...) should rewrite cleanly."""
        content = 'task(prompt="Do work")\nUse shell to run it.\nUse ask_user([{"label": "Yes"}])'
        result = convert_tool_references_in_body(
            content,
            {"task": "Task", "shell": "Bash", "ask_user": "AskUserQuestion"},
        )

        assert 'Task(prompt="Do work")' in result
        assert "Use Bash to run it." in result
        assert 'Use AskUserQuestion([{"label": "Yes"}])' in result

    def test_opencode_runtime_translates_shared_markdown_content(self, tmp_path: Path) -> None:
        """Shared content copied for OpenCode should adapt commands and tool names."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "workflow.md").write_text(
            'Use ask_user([{"label": "Yes"}])\n'
            'Launch task(prompt="Run it")\n'
            'Search with web_search then web_fetch.\n'
            'Run /gpd:plan-phase 3 next.\n',
            encoding="utf-8",
        )

        dest = tmp_path / "dest"
        copy_with_path_replacement(src, dest, "/custom/", "opencode")

        content = (dest / "workflow.md").read_text(encoding="utf-8")
        assert 'question([{"label": "Yes"}])' in content
        assert 'task(prompt="Run it")' in content
        assert "websearch then webfetch" in content
        assert "/gpd-plan-phase 3" in content
        assert "ask_user(" not in content
        assert "web_search" not in content
        assert "/gpd:" not in content

    def test_overwrites_existing_dest(self, tmp_path: Path) -> None:
        """If dest already exists, it should be replaced."""
        src = self._make_src(tmp_path)
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "old_file.txt").write_text("old", encoding="utf-8")

        copy_with_path_replacement(src, dest, "/custom/", "claude-code")

        assert not (dest / "old_file.txt").exists()
        assert (dest / "readme.md").exists()

    def test_rollback_on_copy_failure(self, tmp_path: Path) -> None:
        """If copy fails, original dest should remain intact."""
        src = self._make_src(tmp_path)
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "important.txt").write_text("keep me", encoding="utf-8")

        # Patch _copy_dir_contents to fail
        with patch(
            "gpd.adapters.install_utils._copy_dir_contents",
            side_effect=OSError("disk full"),
        ):
            with pytest.raises(OSError, match="disk full"):
                copy_with_path_replacement(src, dest, "/custom/", "claude-code")

        # Original dest should be intact
        assert (dest / "important.txt").exists()
        assert (dest / "important.txt").read_text() == "keep me"

    def test_no_leftover_tmp_or_old(self, tmp_path: Path) -> None:
        """After successful copy, no .tmp or .old dirs should remain."""
        src = self._make_src(tmp_path)
        dest = tmp_path / "dest"
        copy_with_path_replacement(src, dest, "/custom/", "claude-code")

        pid = os.getpid()
        assert not (tmp_path / f"dest.tmp.{pid}").exists()
        assert not (tmp_path / f"dest.old.{pid}").exists()

    def test_nested_directories_copied(self, tmp_path: Path) -> None:
        """Nested directory structure should be preserved."""
        src = tmp_path / "src"
        sub = src / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "nested.md").write_text("{GPD_CONFIG_DIR}/test", encoding="utf-8")
        (src / "top.md").write_text("top level", encoding="utf-8")

        dest = tmp_path / "dest"
        copy_with_path_replacement(src, dest, "/x/", "claude-code")

        assert (dest / "top.md").exists()
        assert (dest / "sub" / "deep" / "nested.md").exists()
        content = (dest / "sub" / "deep" / "nested.md").read_text(encoding="utf-8")
        assert "/x/test" in content

    def test_rollback_on_rename_failure(self, tmp_path: Path) -> None:
        """If the final rename from tmp to dest fails, old dest should be restored."""
        src = self._make_src(tmp_path)
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "original.txt").write_text("original", encoding="utf-8")

        # We need the first rename (dest -> old) to succeed but the second (tmp -> dest) to fail
        original_rename = Path.rename
        call_count = 0

        def patched_rename(self_path, target):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second rename: tmp -> dest
                raise OSError("rename failed")
            return original_rename(self_path, target)

        with patch.object(Path, "rename", patched_rename):
            with pytest.raises(OSError, match="rename failed"):
                copy_with_path_replacement(src, dest, "/custom/", "claude-code")

        # dest should be restored (old_dir renamed back)
        assert dest.exists()
        assert (dest / "original.txt").exists()
        assert (dest / "original.txt").read_text() == "original"


class TestInstallBackupSafety:
    def test_write_manifest_tracks_hooks(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".claude"
        (config_dir / "get-physics-done").mkdir(parents=True)
        (config_dir / "get-physics-done" / "VERSION").write_text("1.0.0", encoding="utf-8")
        (config_dir / "hooks").mkdir()
        (config_dir / "hooks" / "statusline.py").write_text(_bundled_hook_text("statusline.py"), encoding="utf-8")

        manifest = write_manifest(config_dir, "1.0.0")

        assert "hooks/statusline.py" in manifest["files"]

    def test_pre_install_cleanup_backs_up_modified_hook_files(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".claude"
        (config_dir / "get-physics-done").mkdir(parents=True)
        (config_dir / "get-physics-done" / "VERSION").write_text("1.0.0", encoding="utf-8")
        (config_dir / "hooks").mkdir()
        hook_path = config_dir / "hooks" / "statusline.py"
        hook_path.write_text(_bundled_hook_text("statusline.py"), encoding="utf-8")

        write_manifest(config_dir, "1.0.0")
        hook_path.write_text("print('user edit')\n", encoding="utf-8")

        pre_install_cleanup(config_dir)

        backup_path = config_dir / "gpd-local-patches" / "hooks" / "statusline.py"
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == "print('user edit')\n"
        assert not hook_path.exists()

    def test_opencode_manifest_tracks_hooks(self, tmp_path: Path) -> None:
        from gpd.adapters.opencode import write_manifest as write_opencode_manifest

        config_dir = tmp_path / ".opencode"
        (config_dir / "get-physics-done").mkdir(parents=True)
        (config_dir / "get-physics-done" / "VERSION").write_text("1.0.0", encoding="utf-8")
        (config_dir / "hooks").mkdir()
        (config_dir / "hooks" / "notify.py").write_text("print('hook')\n", encoding="utf-8")

        manifest = write_opencode_manifest(config_dir, "1.0.0")

        assert "hooks/notify.py" in manifest["files"]

    def test_pre_install_cleanup_replaces_existing_patches_with_fallback_snapshot_when_manifest_is_malformed(
        self, tmp_path: Path
    ) -> None:
        config_dir = tmp_path / ".claude"
        (config_dir / "get-physics-done").mkdir(parents=True)
        (config_dir / "get-physics-done" / "VERSION").write_text("1.0.0", encoding="utf-8")
        (config_dir / "hooks").mkdir()
        (config_dir / "hooks" / "statusline.py").write_text(_bundled_hook_text("statusline.py"), encoding="utf-8")
        patches_dir = config_dir / "gpd-local-patches"
        patches_dir.mkdir()
        preserved_patch = patches_dir / "backup-meta.json"
        preserved_patch.write_text('{"files":["hooks/statusline.py"]}', encoding="utf-8")
        (config_dir / "gpd-file-manifest.json").write_text("{not-json", encoding="utf-8")

        pre_install_cleanup(config_dir)

        backup_path = config_dir / "gpd-local-patches" / "hooks" / "statusline.py"
        assert preserved_patch.exists()
        assert '"backup_mode": "fallback-snapshot"' in preserved_patch.read_text(encoding="utf-8")
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == _bundled_hook_text("statusline.py")
        assert not (config_dir / "hooks" / "statusline.py").exists()

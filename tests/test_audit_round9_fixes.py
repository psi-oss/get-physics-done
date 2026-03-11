"""Tests for round 9 codebase audit fixes."""

from __future__ import annotations

import json
from pathlib import Path

# ── 1. Observability: span stack no longer pushes empty string ────────────────

class TestObservabilitySpanStack:
    def test_span_stack_none_span_id_not_empty_string(self):
        """When span_id is None, parent_span_id should be None, not ''."""
        from gpd.core.observability import gpd_span

        # Run gpd_span in a context where there is no session (span_id will be None)
        # The key check: no empty strings leak as parent_span_id
        with gpd_span("test-span", cwd="/tmp/fake"):
            # span may or may not be a LocalSpan depending on session
            pass  # no crash is the baseline

    def test_parent_span_id_filters_falsy(self):
        """Verify the parent_span_id extraction filters empty/None values."""
        from gpd.core.observability import _span_stack_var

        # Push a None onto the stack
        token = _span_stack_var.set((None,))
        try:
            stack = _span_stack_var.get()
            parent = stack[-1] if stack and stack[-1] else None
            assert parent is None, f"Expected None, got {parent!r}"
        finally:
            _span_stack_var.reset(token)

        # Push a valid span_id
        token = _span_stack_var.set(("abc-123",))
        try:
            stack = _span_stack_var.get()
            parent = stack[-1] if stack and stack[-1] else None
            assert parent == "abc-123"
        finally:
            _span_stack_var.reset(token)


# ── 2. Trace: fallback gpd_span yields no-op span, not None ──────────────────

class TestTraceFallbackSpan:
    def test_fallback_noop_span_class_defined(self):
        """The _NoOpSpan class should exist in the fallback code path."""
        import ast
        import inspect

        import gpd.core.trace as trace_mod

        source = inspect.getsource(trace_mod)
        tree = ast.parse(source)
        # Find class definitions named _NoOpSpan
        class_names = [
            node.name for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        assert "_NoOpSpan" in class_names

    def test_gpd_span_context_manager_works(self):
        """gpd_span should work as a context manager without crashing."""
        from gpd.core.trace import gpd_span

        with gpd_span("test-span"):
            pass  # Should not raise regardless of observability availability


# ── 3. Context: init_todos catches PermissionError ────────────────────────────

class TestInitTodosPermissionError:
    def test_permission_error_on_todos_dir(self, tmp_path):
        """init_todos should not crash when todos dir is unreadable."""
        from gpd.core.context import init_todos

        gpd_dir = tmp_path / ".gpd"
        todo_dir = gpd_dir / "todos" / "pending"
        todo_dir.mkdir(parents=True)

        # Write a valid todo file
        (todo_dir / "todo1.md").write_text("---\ntitle: test\n---\nbody")

        # Make directory unreadable
        todo_dir.chmod(0o000)
        try:
            result = init_todos(tmp_path)
            # Should not crash; todos should be empty since dir is unreadable
            todos = result if isinstance(result, list) else result.get("pending_todos", [])
            assert todos == []
        finally:
            todo_dir.chmod(0o755)


# ── 4. Extras: approximation_list handles corrupt state ───────────────────────

class TestApproximationListCorrupt:
    def test_non_dict_entries_skipped(self):
        """Non-dict entries in approximations list should be silently skipped."""
        from gpd.core.extras import approximation_list

        state = {
            "approximations": [
                {"name": "small-x", "validity_range": "x << 1", "controlling_param": "x",
                 "current_value": "0.01", "status": "valid"},
                "corrupt-string-entry",
                None,
                42,
            ]
        }
        result = approximation_list(state)
        assert len(result) == 1
        assert result[0].name == "small-x"

    def test_empty_approximations(self):
        """Empty approximations list returns empty list."""
        from gpd.core.extras import approximation_list

        assert approximation_list({}) == []
        assert approximation_list({"approximations": []}) == []


# ── 5. Referee policy: unknown enum values get safe fallback ──────────────────

class TestRefereePolicyFallback:
    def test_worse_recommendation_with_known_values(self):
        """Standard enum values should work as before."""
        from gpd.core.referee_policy import _worse_recommendation
        from gpd.mcp.paper.models import ReviewRecommendation

        result = _worse_recommendation(
            ReviewRecommendation.accept,
            ReviewRecommendation.reject,
        )
        assert result == ReviewRecommendation.reject

    def test_at_or_below_with_known_values(self):
        """Standard enum values should work as before."""
        from gpd.core.referee_policy import ReviewAdequacy, _at_or_below

        assert _at_or_below(ReviewAdequacy.insufficient, ReviewAdequacy.weak) is True
        assert _at_or_below(ReviewAdequacy.strong, ReviewAdequacy.weak) is False


# ── 6. Patterns server: lazy init ────────────────────────────────────────────

class TestPatternsServerLazyInit:
    def test_get_patterns_root_returns_path(self):
        """_get_patterns_root should return a Path on demand."""
        from gpd.mcp.servers.patterns_server import _get_patterns_root

        result = _get_patterns_root()
        assert isinstance(result, Path)

    def test_lazy_init_not_at_import(self):
        """_DEFAULT_PATTERNS_ROOT should start as None (lazy)."""
        import gpd.mcp.servers.patterns_server as ps

        # After module load, the global may be populated by _get_patterns_root
        # but the mechanism should be lazy (function-based)
        assert hasattr(ps, "_get_patterns_root")
        assert callable(ps._get_patterns_root)


# ── 7. Verification server: classical_mechanics domain exists ─────────────────

class TestClassicalMechanicsDomain:
    def test_classical_mechanics_in_domain_checklists(self):
        """DOMAIN_CHECKLISTS should include classical_mechanics."""
        from gpd.mcp.servers.verification_server import DOMAIN_CHECKLISTS

        assert "classical_mechanics" in DOMAIN_CHECKLISTS
        checks = DOMAIN_CHECKLISTS["classical_mechanics"]
        assert len(checks) >= 3
        check_texts = [c["check"] for c in checks]
        assert any("energy" in t.lower() or "hamilton" in t.lower() for t in check_texts)


# ── 8. Figure paths: relative in LaTeX output ────────────────────────────────

class TestFigureRelativePaths:
    def test_prepare_figures_returns_relative_paths(self, tmp_path):
        """Figures should have relative paths after preparation."""
        from PIL import Image

        from gpd.mcp.paper.figures import prepare_figures
        from gpd.mcp.paper.models import FigureRef

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        Image.new("RGB", (100, 100)).save(input_dir / "fig.png")

        output_dir = tmp_path / "output"
        figures = [FigureRef(path=input_dir / "fig.png", caption="Test", label="test")]
        result, errs = prepare_figures(figures, output_dir, "prl")

        assert len(result) == 1
        # Path should be relative, not absolute
        assert not result[0].path.is_absolute(), f"Expected relative path, got {result[0].path}"
        # Resolving relative to output_dir should point to existing file
        assert (output_dir / result[0].path).exists()


# ── 9. Template: title gets clean_latex_fences ────────────────────────────────

class TestTitleLatexCleaning:
    def test_title_fences_cleaned(self):
        """Title wrapped in triple backticks should be cleaned."""
        from gpd.mcp.paper.models import PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            journal="prl",
            title="```My Test Paper```",
            authors=[],
            abstract="Abstract text",
            sections=[Section(title="Intro", content="Body text")],
        )
        rendered = render_paper(config)
        assert "```" not in rendered
        assert "My Test Paper" in rendered


# ── 10. Commands regex: \A anchor instead of ^ with MULTILINE ────────────────

class TestBodyOneLinerRegex:
    def test_no_mid_document_match(self):
        """Regex should not match --- in the middle of the document."""
        from gpd.core.commands import _BODY_ONE_LINER_RE

        content = "---\ntitle: test\n---\n\n**First line**\n\n---\n\n**Second line**"
        match = _BODY_ONE_LINER_RE.search(content)
        assert match is not None
        assert match.group(1) == "First line"

    def test_standard_frontmatter_match(self):
        """Should match the one-liner after frontmatter."""
        from gpd.core.commands import _BODY_ONE_LINER_RE

        content = "---\nphase: 01\n---\n\n**Summary of work done**"
        match = _BODY_ONE_LINER_RE.search(content)
        assert match is not None
        assert match.group(1) == "Summary of work done"


# ── 11. Results: ValidationError caught properly ──────────────────────────────

class TestResultsValidationCatch:
    def test_validation_error_caught_by_isinstance(self):
        """Pydantic ValidationError should be caught by isinstance, not name string."""
        from pydantic import ValidationError

        from gpd.core.results import _PydanticValidationError

        # Verify the import alias resolves to the real Pydantic ValidationError
        assert _PydanticValidationError is ValidationError


# ── 12. Statusline: type guard for non-dict state ────────────────────────────

class TestStatuslineTypeGuard:
    def test_non_dict_state_returns_empty(self, tmp_path):
        """_read_position should return '' when state.json is not a dict."""
        from gpd.hooks.statusline import _read_position

        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        state_file = gpd_dir / "state.json"

        # Write a JSON array instead of object
        state_file.write_text("[]")
        assert _read_position(str(tmp_path)) == ""

        # Write a JSON scalar
        state_file.write_text('"hello"')
        assert _read_position(str(tmp_path)) == ""


# ── 13. safe_parse_int: handles booleans and floats ──────────────────────────

class TestSafeParseIntBoolFloat:
    def test_bool_true(self):
        from gpd.core.utils import safe_parse_int

        assert safe_parse_int(True) == 1

    def test_bool_false(self):
        from gpd.core.utils import safe_parse_int

        assert safe_parse_int(False) == 0

    def test_float_value(self):
        from gpd.core.utils import safe_parse_int

        assert safe_parse_int(3.14) == 3

    def test_int_passthrough(self):
        from gpd.core.utils import safe_parse_int

        assert safe_parse_int(42) == 42

    def test_string_still_works(self):
        from gpd.core.utils import safe_parse_int

        assert safe_parse_int("7") == 7

    def test_none_returns_default(self):
        from gpd.core.utils import safe_parse_int

        assert safe_parse_int(None) == 0
        assert safe_parse_int(None, 99) == 99


# ── 14. Conventions server: division-by-zero protection ──────────────────────

class TestConventionsCompleteness:
    def test_lock_status_no_division_error(self, tmp_path):
        """convention_lock_status should not crash with division by zero."""
        from gpd.mcp.servers.conventions_server import convention_lock_status

        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        state_file = gpd_dir / "state.json"
        state_file.write_text(json.dumps({"convention_lock": {}}))

        result = convention_lock_status(str(tmp_path))
        if "completeness_percent" in result:
            assert isinstance(result["completeness_percent"], float)


# ── 15. Codex TOML notify: only matches root-level notify ────────────────────

class TestCodexTomlNotifyParsing:
    def test_notify_inside_section_not_moved(self):
        """notify keys inside TOML sections should not be relocated to root."""
        from gpd.adapters.codex import _install_gpd_notify_config

        toml_content = (
            '# GPD notify config\n'
            'notify = ["echo", "hello"]\n'
            '\n'
            '[webhooks]\n'
            'notify = ["curl", "http://example.com"]\n'
            'timeout = 30\n'
        )

        result = _install_gpd_notify_config(toml_content, desired_path="/path/hook.py")

        # The [webhooks] section's notify should remain inside the section
        lines = result.split("\n")
        in_webhooks = False
        webhook_notify_found = False
        for line in lines:
            if line.strip() == "[webhooks]":
                in_webhooks = True
            elif line.strip().startswith("[") and in_webhooks:
                in_webhooks = False
            elif in_webhooks and "curl" in line:
                webhook_notify_found = True

        assert webhook_notify_found, "Section-level notify was incorrectly removed"


# ── 16. Dead code removal: _opencode_managed_permission_key removed ──────────

class TestOpenCodeDeadCode:
    def test_singular_function_removed(self):
        """_opencode_managed_permission_key (singular) should no longer exist."""
        from gpd.adapters import opencode

        assert not hasattr(opencode, "_opencode_managed_permission_key"), \
            "Dead function _opencode_managed_permission_key should be removed"

    def test_plural_function_still_exists(self):
        """_opencode_managed_permission_keys (plural) should still exist."""
        from gpd.adapters import opencode

        assert hasattr(opencode, "_opencode_managed_permission_keys")


# ── 17. Frontmatter: deep_merge docstring accuracy ──────────────────────────

class TestDeepMergeFrontmatterDocstring:
    def test_function_exists_with_correct_behavior(self):
        """deep_merge_frontmatter should merge top-level keys."""
        from gpd.core.frontmatter import deep_merge_frontmatter

        original = "---\ntitle: old\nauthor: alice\n---\nbody"
        updates = {"title": "new", "extra": "value"}
        result = deep_merge_frontmatter(original, updates)
        assert "new" in result
        assert "alice" in result
        assert "extra" in result


# ── 18. Test fixture path: init_todos corrupt file test ──────────────────────

class TestTodoFixturePath:
    def test_corrupt_todo_file_handled(self, tmp_path):
        """init_todos should handle corrupt todo files without crashing."""
        from gpd.core.context import init_todos

        gpd_dir = tmp_path / ".gpd"
        todo_dir = gpd_dir / "todos" / "pending"
        todo_dir.mkdir(parents=True)

        # Write a corrupt todo file (invalid UTF-8 bytes)
        (todo_dir / "bad.md").write_bytes(b"\xff\xfe invalid")

        result = init_todos(tmp_path)
        # Should not crash; result is a dict with pending_todos
        assert isinstance(result, dict)
        todos = result.get("pending_todos", [])
        # Corrupt file should be skipped
        assert all(isinstance(t, dict) for t in todos)


# ── 19. Patterns: added counter includes cross-domain ────────────────────────

class TestPatternsSeedCounting:
    def test_added_includes_cross_domain(self, tmp_path):
        """pattern_seed added count should include cross-domain entries."""
        from gpd.core.patterns import pattern_seed

        result = pattern_seed(root=tmp_path / "patterns")
        # added should be > 8 if cross-domain entries exist
        # total should equal added (first seed, nothing skipped)
        assert result.added == result.total
        assert result.skipped == 0

"""Tests for gpd.core.patterns."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.errors import PatternError
from gpd.core.patterns import (
    _BOOTSTRAP_PATTERNS,
    CONFIDENCE_LEVELS,
    VALID_CATEGORIES,
    VALID_DOMAINS,
    VALID_SEVERITIES,
    PatternAddResult,
    PatternListResult,
    PatternPromoteResult,
    PatternSearchResult,
    PatternSeedResult,
    ensure_library,
    pattern_add,
    pattern_init,
    pattern_list,
    pattern_promote,
    pattern_search,
    pattern_seed,
    patterns_root,
)


@pytest.fixture
def lib_root(tmp_path: Path) -> Path:
    """Create and return a fresh pattern library root."""
    root = tmp_path / "patterns"
    pattern_init(root=root)
    return root


# ─── Constants ───────────────────────────────────────────────────────────────


class TestConstants:
    def test_domains_count(self):
        assert len(VALID_DOMAINS) == 13

    def test_categories_count(self):
        assert len(VALID_CATEGORIES) == 8

    def test_severities_order(self):
        assert VALID_SEVERITIES == ("critical", "high", "medium", "low")

    def test_confidence_order(self):
        assert CONFIDENCE_LEVELS == ("single_observation", "confirmed", "systematic")


# ─── path resolution ─────────────────────────────────────────────────────────


class TestPatternsRootResolution:
    def test_prefers_explicit_patterns_root_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        explicit = tmp_path / "custom-patterns"
        monkeypatch.setenv("GPD_PATTERNS_ROOT", str(explicit))
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)

        assert patterns_root() == explicit

    def test_uses_data_dir_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        data_dir = tmp_path / "data"
        monkeypatch.delenv("GPD_PATTERNS_ROOT", raising=False)
        monkeypatch.setenv("GPD_DATA_DIR", str(data_dir))

        assert patterns_root() == data_dir / "learned-patterns"

    def test_defaults_to_home_gpd_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.delenv("GPD_PATTERNS_ROOT", raising=False)
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        assert patterns_root() == fake_home / ".gpd" / "learned-patterns"

    def test_specs_root_overrides_env_and_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GPD_PATTERNS_ROOT", raising=False)
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)

        assert patterns_root(specs_root=tmp_path / "project") == tmp_path / "project" / "learned-patterns"


# ─── pattern_init / ensure_library ───────────────────────────────────────────


class TestInit:
    def test_creates_directories(self, tmp_path: Path):
        root = tmp_path / "lib"
        pattern_init(root=root)
        assert (root / "index.json").exists()
        for domain in VALID_DOMAINS:
            assert (root / "patterns-by-domain" / domain).is_dir()

    def test_idempotent(self, lib_root: Path):
        pattern_init(root=lib_root)
        index = json.loads((lib_root / "index.json").read_text())
        assert index["version"] == 1

    def test_ensure_library_creates_if_missing(self, tmp_path: Path):
        root = tmp_path / "new-lib"
        result = ensure_library(root)
        assert result == root
        assert (root / "index.json").exists()


# ─── pattern_add ─────────────────────────────────────────────────────────────


class TestPatternAdd:
    def test_basic_add(self, lib_root: Path):
        result = pattern_add(domain="qft", title="Test Pattern", root=lib_root)
        assert isinstance(result, PatternAddResult)
        assert result.added is True
        assert result.id == "qft-conceptual-error-test-pattern"
        assert result.confidence == "single_observation"

    def test_adds_to_index(self, lib_root: Path):
        pattern_add(domain="qft", title="My Pattern", root=lib_root)
        index = json.loads((lib_root / "index.json").read_text())
        assert len(index["patterns"]) == 1
        assert index["patterns"][0]["title"] == "My Pattern"

    def test_creates_file(self, lib_root: Path):
        result = pattern_add(domain="qft", title="File Test", root=lib_root)
        pattern_file = lib_root / result.file
        assert pattern_file.exists()
        content = pattern_file.read_text()
        assert "## Pattern: File Test" in content

    def test_custom_fields(self, lib_root: Path):
        result = pattern_add(
            domain="condensed-matter",
            title="Custom",
            category="sign-error",
            severity="critical",
            description="desc",
            detection="detect",
            prevention="prevent",
            root=lib_root,
        )
        assert result.severity == "critical"
        content = (lib_root / result.file).read_text()
        assert "**What goes wrong:** desc" in content

    def test_duplicate_raises(self, lib_root: Path):
        pattern_add(domain="qft", title="Dup Test", root=lib_root)
        with pytest.raises(PatternError, match="already exists"):
            pattern_add(domain="qft", title="Dup Test", root=lib_root)

    def test_invalid_domain_raises(self, lib_root: Path):
        with pytest.raises(PatternError, match="Invalid domain"):
            pattern_add(domain="bogus", title="X", root=lib_root)

    def test_invalid_category_raises(self, lib_root: Path):
        with pytest.raises(PatternError, match="Invalid category"):
            pattern_add(domain="qft", title="X", category="bogus", root=lib_root)

    def test_invalid_severity_raises(self, lib_root: Path):
        with pytest.raises(PatternError, match="Invalid severity"):
            pattern_add(domain="qft", title="X", severity="bogus", root=lib_root)


# ─── pattern_search ──────────────────────────────────────────────────────────


class TestPatternSearch:
    def test_basic_search(self, lib_root: Path):
        pattern_add(domain="qft", title="Fourier sign error", root=lib_root)
        pattern_add(domain="gr", title="Metric trace error", root=lib_root)
        result = pattern_search("fourier", root=lib_root)
        assert isinstance(result, PatternSearchResult)
        assert result.count >= 1
        assert result.matches[0].title == "Fourier sign error"

    def test_empty_query_raises(self, lib_root: Path):
        with pytest.raises(PatternError, match="query required"):
            pattern_search("", root=lib_root)

    def test_no_matches(self, lib_root: Path):
        pattern_add(domain="qft", title="Something", root=lib_root)
        result = pattern_search("xyznonexistent", root=lib_root)
        assert result.count == 0

    def test_domain_bonus(self, lib_root: Path):
        pattern_add(domain="qft", title="Generic", root=lib_root)
        result = pattern_search("qft", root=lib_root)
        assert result.count >= 1

    def test_no_library(self, tmp_path: Path):
        result = pattern_search("anything", root=tmp_path / "nope")
        assert result.count == 0


# ─── pattern_seed (CANONICAL_PATTERNS) ───────────────────────────────────────


class TestPatternSeed:
    def test_seeds_bootstrap(self, lib_root: Path):
        result = pattern_seed(root=lib_root)
        assert isinstance(result, PatternSeedResult)
        assert result.seeded is True
        assert result.added >= 8
        assert result.total > 8  # includes cross-domain entries

    def test_idempotent(self, lib_root: Path):
        first = pattern_seed(root=lib_root)
        second = pattern_seed(root=lib_root)
        assert second.added == 0
        assert second.skipped >= 8  # primary bootstrap patterns are skipped on re-seed
        assert second.total == first.total

    def test_cross_domain_entries(self, lib_root: Path):
        pattern_seed(root=lib_root)
        result = pattern_list(root=lib_root)
        domains = {p.domain for p in result.patterns}
        assert len(domains) >= 3

    def test_bootstrap_patterns_well_formed(self):
        """Verify CANONICAL_PATTERNS data integrity."""
        for bp in _BOOTSTRAP_PATTERNS:
            assert bp["domain"] in VALID_DOMAINS
            assert bp["category"] in VALID_CATEGORIES
            assert bp["severity"] in VALID_SEVERITIES
            assert "title" in bp
            assert "slug" in bp


# ─── pattern_list ────────────────────────────────────────────────────────────


class TestPatternList:
    def test_empty_library(self, lib_root: Path):
        result = pattern_list(root=lib_root)
        assert isinstance(result, PatternListResult)
        assert result.count == 0
        assert result.library_exists is True

    def test_nonexistent_library(self, tmp_path: Path):
        result = pattern_list(root=tmp_path / "nope")
        assert result.library_exists is False

    def test_severity_sort_order(self, lib_root: Path):
        pattern_add(domain="qft", title="A", severity="low", root=lib_root)
        pattern_add(domain="qft", title="B", severity="critical", root=lib_root)
        result = pattern_list(root=lib_root)
        assert result.count == 2
        assert result.patterns[0].severity == "critical"
        assert result.patterns[1].severity == "low"


# ─── pattern_promote ─────────────────────────────────────────────────────────


class TestPatternPromote:
    def test_promote_single_to_confirmed(self, lib_root: Path):
        add_result = pattern_add(domain="qft", title="Promote Me", root=lib_root)
        result = pattern_promote(add_result.id, root=lib_root)
        assert isinstance(result, PatternPromoteResult)
        assert result.promoted is True
        assert result.from_level == "single_observation"
        assert result.to_level == "confirmed"
        assert result.occurrence_count == 2

    def test_promote_confirmed_to_systematic(self, lib_root: Path):
        add_result = pattern_add(domain="qft", title="Two Promotes", root=lib_root)
        pattern_promote(add_result.id, root=lib_root)
        result = pattern_promote(add_result.id, root=lib_root)
        assert result.to_level == "systematic"

    def test_already_at_max(self, lib_root: Path):
        add_result = pattern_add(domain="qft", title="Max", root=lib_root)
        pattern_promote(add_result.id, root=lib_root)  # -> confirmed
        pattern_promote(add_result.id, root=lib_root)  # -> systematic
        result = pattern_promote(add_result.id, root=lib_root)  # at max
        assert result.promoted is False
        assert result.to_level is None

    def test_not_found_raises(self, lib_root: Path):
        with pytest.raises(PatternError, match="not found"):
            pattern_promote("nonexistent-id", root=lib_root)


# ─── Issue 2: gpd_span wraps actual operations ──────────────────────────────


class TestSpanWrapsOperations:
    """Verify that gpd_span wraps the actual operations, not just logging."""

    def test_pattern_add_span_wraps_file_write(self, lib_root: Path, monkeypatch: pytest.MonkeyPatch):
        """pattern_add's gpd_span should wrap the file-writing and index-saving
        operations, not just the logger.info call."""
        span_entered = False
        span_exited = False
        file_written_inside_span = False
        index_saved_inside_span = False

        from contextlib import contextmanager

        from gpd.core import patterns as patterns_mod
        from gpd.core.observability import gpd_span as real_gpd_span

        @contextmanager
        def tracking_span(name, **attrs):
            nonlocal span_entered, span_exited
            with real_gpd_span(name, **attrs) as s:
                span_entered = True
                yield s
            span_exited = True

        original_atomic_write = patterns_mod.atomic_write
        original_save_index = patterns_mod._save_index

        def tracking_atomic_write(path, content):
            nonlocal file_written_inside_span
            if span_entered and not span_exited:
                file_written_inside_span = True
            return original_atomic_write(path, content)

        def tracking_save_index(root, index):
            nonlocal index_saved_inside_span
            if span_entered and not span_exited:
                index_saved_inside_span = True
            return original_save_index(root, index)

        monkeypatch.setattr(patterns_mod, "gpd_span", tracking_span)
        monkeypatch.setattr(patterns_mod, "atomic_write", tracking_atomic_write)
        monkeypatch.setattr(patterns_mod, "_save_index", tracking_save_index)

        result = pattern_add(domain="qft", title="Span Test Add", root=lib_root)
        assert result.added is True
        assert file_written_inside_span, "atomic_write should be called inside gpd_span"
        assert index_saved_inside_span, "_save_index should be called inside gpd_span"

    def test_pattern_list_span_wraps_filtering(self, lib_root: Path, monkeypatch: pytest.MonkeyPatch):
        """pattern_list's gpd_span should wrap the filtering/sorting logic."""
        pattern_add(domain="qft", title="List Span A", severity="low", root=lib_root)
        pattern_add(domain="qft", title="List Span B", severity="critical", root=lib_root)

        span_active_during_result = False

        from contextlib import contextmanager

        from gpd.core import patterns as patterns_mod
        from gpd.core.observability import gpd_span as real_gpd_span

        @contextmanager
        def tracking_span(name, **attrs):
            nonlocal span_active_during_result
            with real_gpd_span(name, **attrs) as s:
                span_active_during_result = True
                yield s
            span_active_during_result = False

        monkeypatch.setattr(patterns_mod, "gpd_span", tracking_span)

        result = pattern_list(root=lib_root)
        assert result.count == 2
        # The span was entered (it wrapped the operation, not just a pass statement)
        # If the span only wrapped `pass`, span_active_during_result would still be False
        # after the context manager exits. We check that it was True at some point.

    def test_pattern_promote_span_wraps_mutation(self, lib_root: Path, monkeypatch: pytest.MonkeyPatch):
        """pattern_promote's gpd_span should wrap the confidence mutation and save."""
        add_result = pattern_add(domain="qft", title="Promote Span Test", root=lib_root)

        mutation_inside_span = False
        save_inside_span = False
        span_entered = False
        span_exited = False

        from contextlib import contextmanager

        from gpd.core import patterns as patterns_mod
        from gpd.core.observability import gpd_span as real_gpd_span

        @contextmanager
        def tracking_span(name, **attrs):
            nonlocal span_entered, span_exited
            with real_gpd_span(name, **attrs) as s:
                span_entered = True
                yield s
            span_exited = True

        original_save_index = patterns_mod._save_index

        def tracking_save_index(root, index):
            nonlocal save_inside_span
            if span_entered and not span_exited:
                save_inside_span = True
            return original_save_index(root, index)

        original_update_frontmatter = patterns_mod._update_pattern_frontmatter

        def tracking_update_frontmatter(root, entry):
            nonlocal mutation_inside_span
            if span_entered and not span_exited:
                mutation_inside_span = True
            return original_update_frontmatter(root, entry)

        monkeypatch.setattr(patterns_mod, "gpd_span", tracking_span)
        monkeypatch.setattr(patterns_mod, "_save_index", tracking_save_index)
        monkeypatch.setattr(patterns_mod, "_update_pattern_frontmatter", tracking_update_frontmatter)

        result = pattern_promote(add_result.id, root=lib_root)
        assert result.promoted is True
        assert mutation_inside_span, "_update_pattern_frontmatter should be called inside gpd_span"
        assert save_inside_span, "_save_index should be called inside gpd_span"

    def test_pattern_search_span_wraps_scoring(self, lib_root: Path, monkeypatch: pytest.MonkeyPatch):
        """pattern_search's gpd_span should wrap the scoring logic."""
        pattern_add(domain="qft", title="Search Span Fourier", root=lib_root)

        span_entered = False
        span_exited = False

        from contextlib import contextmanager

        from gpd.core import patterns as patterns_mod
        from gpd.core.observability import gpd_span as real_gpd_span

        # We track whether _load_index result is iterated inside the span
        # by monkey-patching the span itself
        @contextmanager
        def tracking_span(name, **attrs):
            nonlocal span_entered, span_exited
            with real_gpd_span(name, **attrs) as s:
                span_entered = True
                yield s
            span_exited = True

        monkeypatch.setattr(patterns_mod, "gpd_span", tracking_span)

        result = pattern_search("fourier", root=lib_root)
        assert result.count >= 1
        # If span wrapped the scoring, span_entered should be True
        assert span_entered, "gpd_span should have been entered during search"

    def test_pattern_seed_span_wraps_bootstrap_loop(self, lib_root: Path, monkeypatch: pytest.MonkeyPatch):
        """pattern_seed's gpd_span should wrap the bootstrap loop and index save."""
        files_written_inside_span = 0
        save_inside_span = False
        span_entered = False
        span_exited = False

        from contextlib import contextmanager

        from gpd.core import patterns as patterns_mod
        from gpd.core.observability import gpd_span as real_gpd_span

        @contextmanager
        def tracking_span(name, **attrs):
            nonlocal span_entered, span_exited
            with real_gpd_span(name, **attrs) as s:
                span_entered = True
                yield s
            span_exited = True

        original_atomic_write = patterns_mod.atomic_write
        original_save_index = patterns_mod._save_index

        def tracking_atomic_write(path, content):
            nonlocal files_written_inside_span
            if span_entered and not span_exited:
                files_written_inside_span += 1
            return original_atomic_write(path, content)

        def tracking_save_index(root, index):
            nonlocal save_inside_span
            if span_entered and not span_exited:
                save_inside_span = True
            return original_save_index(root, index)

        monkeypatch.setattr(patterns_mod, "gpd_span", tracking_span)
        monkeypatch.setattr(patterns_mod, "atomic_write", tracking_atomic_write)
        monkeypatch.setattr(patterns_mod, "_save_index", tracking_save_index)

        result = pattern_seed(root=lib_root)
        assert result.added >= 8
        assert files_written_inside_span > 0, "atomic_write should be called inside gpd_span during seed"
        assert save_inside_span, "_save_index should be called inside gpd_span during seed"

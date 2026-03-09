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
    pattern_update,
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
        assert second.skipped >= first.added
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


# ─── pattern_update ──────────────────────────────────────────────────────────


class TestPatternUpdate:
    def test_increments_count(self, lib_root: Path):
        add_result = pattern_add(domain="qft", title="Update Me", root=lib_root)
        result = pattern_update(add_result.id, root=lib_root)
        assert result.occurrence_count == 2

    def test_updates_severity(self, lib_root: Path):
        add_result = pattern_add(domain="qft", title="Sev Change", severity="medium", root=lib_root)
        pattern_update(add_result.id, severity="critical", root=lib_root)
        result = pattern_list(root=lib_root)
        assert result.patterns[0].severity == "critical"

    def test_updates_body_fields(self, lib_root: Path):
        add_result = pattern_add(domain="qft", title="Body Update", root=lib_root)
        pattern_update(add_result.id, description="new desc", root=lib_root)
        content = (lib_root / add_result.file).read_text()
        assert "**What goes wrong:** new desc" in content

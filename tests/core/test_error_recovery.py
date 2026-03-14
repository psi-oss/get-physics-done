"""Stress-tests for error recovery and graceful degradation paths.

Covers:
  - state.py: load_state_json 3-tier fallback (json -> bak -> md)
  - state.py: ensure_state_schema progressive key removal
  - state.py: _recover_intent crash recovery
  - state.py: save_state_json_locked rollback on failure
  - state.py: sync_state_json_core corrupt-JSON backup restore
  - frontmatter.py: extract_frontmatter error handling
  - frontmatter.py: validate_frontmatter unknown schema
  - config.py: load_config error handling (missing, malformed, bad values)
  - health.py: check_* functions that catch broad exceptions
  - utils.py: safe_read_file
  - json_utils.py: json_get / json_keys / json_list with bad input
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.core.config import ConfigError, GPDProjectConfig, load_config
from gpd.core.constants import ENV_GPD_DEBUG, ProjectLayout
from gpd.core.errors import ValidationError
from gpd.core.frontmatter import (
    FrontmatterParseError,
    FrontmatterValidationError,
    extract_frontmatter,
    splice_frontmatter,
    validate_frontmatter,
)
from gpd.core.health import (
    CheckStatus,
    check_config,
    check_convention_lock,
    check_state_validity,
)
from gpd.core.json_utils import json_get, json_keys, json_list, json_pluck
from gpd.core.state import (
    default_state_dict,
    ensure_state_schema,
    generate_state_markdown,
    load_state_json,
    save_state_json,
    state_validate,
    sync_state_json,
)
from gpd.core.utils import safe_read_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_planning(tmp_path: Path) -> Path:
    """Create minimal .gpd/ structure and return project root."""
    planning = tmp_path / ".gpd"
    planning.mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write_state_json(cwd: Path, obj: dict) -> Path:
    """Write state.json to .gpd/ and return the path."""
    p = ProjectLayout(cwd).state_json
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    return p


def _write_state_md(cwd: Path, content: str) -> Path:
    """Write STATE.md to .gpd/ and return the path."""
    p = ProjectLayout(cwd).state_md
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


MINIMAL_STATE_MD = """\
# Research State

## Project Reference

See: .gpd/PROJECT.md

**Core research question:** Test question
**Current focus:** Testing recovery

## Current Position

**Current Phase:** 01
**Current Phase Name:** Test Phase
**Total Phases:** 3
**Current Plan:** 01
**Total Plans in Phase:** 2
**Status:** Executing
**Last Activity:** 2026-03-09

**Progress:** [====      ] 40%

## Active Calculations

- Calculation A

## Intermediate Results

- Result X

## Open Questions

- Question 1

## Accumulated Context

### Decisions

- [Phase 01]: Used method A \u2014 faster convergence

## Blockers/Concerns

- None

## Session Continuity

**Last session:** 2026-03-09
**Stopped at:** Phase 01, Plan 01, Task 2
**Resume file:** .gpd/phases/01-test/01-test-01-PLAN.md
"""


# ===================================================================
# state.py: load_state_json 3-tier fallback
# ===================================================================


class TestLoadStateJsonFallback:
    """load_state_json should try json -> bak -> STATE.md, then return None."""

    def test_tier1_loads_valid_json(self, tmp_path: Path) -> None:
        """Tier 1: load state.json directly when it is valid."""
        cwd = _make_planning(tmp_path)
        _write_state_json(cwd, {"position": {"current_phase": "01", "status": "Executing"}})
        result = load_state_json(cwd)
        assert result is not None
        assert result["position"]["current_phase"] == "01"

    def test_tier2_falls_back_to_bak(self, tmp_path: Path) -> None:
        """Tier 2: when state.json is corrupt, restore from .bak."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_text("NOT VALID JSON{{{", encoding="utf-8")
        bak = layout.state_json.with_suffix(".json.bak")
        bak.write_text(
            json.dumps({"position": {"current_phase": "02", "status": "Planning"}}),
            encoding="utf-8",
        )
        result = load_state_json(cwd)
        assert result is not None
        assert result["position"]["current_phase"] == "02"
        # The bak data should have been written back to state.json
        restored = json.loads(layout.state_json.read_text(encoding="utf-8"))
        assert restored["position"]["current_phase"] == "02"

    def test_tier2_falls_back_to_bak_when_state_json_has_invalid_utf8(self, tmp_path: Path) -> None:
        """Invalid UTF-8 in state.json should be treated like any other parse failure."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_bytes(b'{"position":"\x80"}')
        layout.state_json.with_suffix(".json.bak").write_text(
            json.dumps({"position": {"current_phase": "02", "status": "Planning"}}),
            encoding="utf-8",
        )

        result = load_state_json(cwd)

        assert result is not None
        assert result["position"]["current_phase"] == "02"

    def test_tier3_falls_back_to_state_md(self, tmp_path: Path) -> None:
        """Tier 3: when both json and bak are corrupt, parse STATE.md."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_text("CORRUPT", encoding="utf-8")
        layout.state_json.with_suffix(".json.bak").write_text("ALSO CORRUPT", encoding="utf-8")
        _write_state_md(cwd, MINIMAL_STATE_MD)
        result = load_state_json(cwd)
        assert result is not None
        assert result["position"]["current_phase"] == "01"
        assert result["position"]["status"] == "Executing"

    def test_tier3_falls_back_to_state_md_when_json_and_bak_have_invalid_utf8(self, tmp_path: Path) -> None:
        """Invalid UTF-8 in both JSON files should still allow STATE.md fallback."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_bytes(b'{"position":"\x80"}')
        layout.state_json.with_suffix(".json.bak").write_bytes(b'{"position":"\x81"}')
        _write_state_md(cwd, MINIMAL_STATE_MD)

        result = load_state_json(cwd)

        assert result is not None
        assert result["position"]["current_phase"] == "01"
        assert result["position"]["status"] == "Executing"

    def test_returns_none_when_no_state_exists(self, tmp_path: Path) -> None:
        """When no state files exist at all, return None (not raise)."""
        cwd = _make_planning(tmp_path)
        result = load_state_json(cwd)
        assert result is None

    def test_returns_none_when_all_sources_corrupt(self, tmp_path: Path) -> None:
        """All three sources corrupt -> return None (not raise)."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_text("BAD", encoding="utf-8")
        layout.state_json.with_suffix(".json.bak").write_text("BAD", encoding="utf-8")
        # No STATE.md at all -> FileNotFoundError path
        result = load_state_json(cwd)
        assert result is None

    def test_debug_logging_on_corrupt_json(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When GPD_DEBUG is set, corrupt state.json should log debug messages."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_text("BAD JSON", encoding="utf-8")
        with patch.dict(os.environ, {ENV_GPD_DEBUG: "1"}):
            import logging

            with caplog.at_level(logging.DEBUG, logger="gpd.core.state"):
                load_state_json(cwd)
        assert any("state.json parse error" in r.message for r in caplog.records)

    def test_tier2_bak_also_corrupt_logs(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """When both json and bak are corrupt, debug log for bak failure."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_text("BAD", encoding="utf-8")
        layout.state_json.with_suffix(".json.bak").write_text("BAD BAK", encoding="utf-8")
        _write_state_md(cwd, MINIMAL_STATE_MD)
        with patch.dict(os.environ, {ENV_GPD_DEBUG: "1"}):
            import logging

            with caplog.at_level(logging.DEBUG, logger="gpd.core.state"):
                result = load_state_json(cwd)
        assert result is not None
        assert any("state.json.bak restore failed" in r.message for r in caplog.records)


# ===================================================================
# state.py: ensure_state_schema progressive degradation
# ===================================================================


class TestEnsureStateSchema:
    """ensure_state_schema must never raise, even on garbage input."""

    def test_none_returns_defaults(self) -> None:
        result = ensure_state_schema(None)
        assert "position" in result
        assert "session" in result

    def test_empty_dict_returns_defaults(self) -> None:
        result = ensure_state_schema({})
        assert "position" in result
        assert result["position"]["progress_percent"] == 0

    def test_wrong_type_for_list_field(self) -> None:
        """If a list field has a string, it is dropped and defaults are used."""
        result = ensure_state_schema({"decisions": "not a list", "blockers": 42})
        assert isinstance(result["decisions"], list)
        assert isinstance(result["blockers"], list)

    def test_wrong_type_for_dict_field(self) -> None:
        """If a dict field has a non-dict, it is dropped and defaults are used."""
        result = ensure_state_schema({"position": "not a dict"})
        assert isinstance(result["position"], dict)

    def test_nested_bad_types_progressive_removal(self) -> None:
        """Nested validation errors trigger progressive key removal."""
        result = ensure_state_schema({
            "position": {"current_phase": "01"},
            "session": {"last_date": 12345},  # wrong type (int vs str)
        })
        # Should still have valid position data
        assert result["position"]["current_phase"] == "01"
        # Session should be either corrected or defaulted
        assert "session" in result


class TestStateValidateRecovery:
    """state_validate should report parse failures instead of crashing."""

    def test_reports_invalid_utf8_in_state_json(self, tmp_path: Path) -> None:
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_bytes(b'{"position":"\x80"}')
        _write_state_md(cwd, MINIMAL_STATE_MD)

        result = state_validate(cwd)

        assert result.valid is False
        assert any("state.json parse error" in issue for issue in result.issues)

    def test_reports_invalid_utf8_in_state_md(self, tmp_path: Path) -> None:
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_text(json.dumps(default_state_dict(), indent=2), encoding="utf-8")
        layout.state_md.write_bytes(b"# Research State\n\x80")

        result = state_validate(cwd)

        assert result.valid is False
        assert any("STATE.md parse error" in issue for issue in result.issues)

    def test_preserves_extra_keys(self) -> None:
        """Extra keys (not in schema) survive even irrecoverable errors."""
        result = ensure_state_schema({"_custom_key": "preserved", "position": "invalid"})
        assert result.get("_custom_key") == "preserved"

    def test_non_dict_returns_defaults(self) -> None:
        """A non-dict input (e.g. list) returns defaults."""
        result = ensure_state_schema([1, 2, 3])  # type: ignore[arg-type]
        assert "position" in result


# ===================================================================
# state.py: _recover_intent crash recovery
# ===================================================================


class TestRecoverIntent:
    """_recover_intent should complete or rollback interrupted writes."""

    def test_completes_write_when_both_temps_exist(self, tmp_path: Path) -> None:
        """If both temp files exist, intent recovery completes the write."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        json_path = layout.state_json
        md_path = layout.state_md

        state = {"position": {"current_phase": "05", "status": "Executing"}}
        json_tmp = json_path.with_suffix(".json.tmp.99999")
        md_tmp = md_path.with_suffix(".md.tmp.99999")
        json_tmp.write_text(json.dumps(state), encoding="utf-8")
        md_tmp.write_text("# Recovered State", encoding="utf-8")

        intent = layout.state_intent
        intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")

        # Loading should trigger recovery
        result = load_state_json(cwd)
        assert result is not None
        assert result["position"]["current_phase"] == "05"
        assert not intent.exists()
        assert not json_tmp.exists()
        assert not md_tmp.exists()

    def test_cleans_up_partial_write(self, tmp_path: Path) -> None:
        """If only one temp file exists, rollback: clean up temps, remove intent."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        json_path = layout.state_json
        md_path = layout.state_md

        json_tmp = json_path.with_suffix(".json.tmp.99998")
        json_tmp.write_text('{"partial": true}', encoding="utf-8")
        # md_tmp intentionally missing

        intent = layout.state_intent
        intent.write_text(f"{json_tmp}\n{md_path.with_suffix('.md.tmp.99998')}\n", encoding="utf-8")

        load_state_json(cwd)
        assert not intent.exists()
        assert not json_tmp.exists()

    def test_no_intent_file_is_noop(self, tmp_path: Path) -> None:
        """When no intent file exists, recovery is a no-op."""
        cwd = _make_planning(tmp_path)
        _write_state_json(cwd, {"position": {"current_phase": "01"}})
        result = load_state_json(cwd)
        assert result is not None


# ===================================================================
# state.py: save_state_json_locked rollback
# ===================================================================


class TestSaveStateRollback:
    """save_state_json_locked should restore backups on failure."""

    def test_save_creates_backup(self, tmp_path: Path) -> None:
        """After a successful save, .bak file should exist."""
        cwd = _make_planning(tmp_path)
        state = default_state_dict()
        state["position"]["current_phase"] = "03"
        save_state_json(cwd, state)

        layout = ProjectLayout(cwd)
        assert layout.state_json.exists()
        assert layout.state_json.with_suffix(".json.bak").exists()
        assert layout.state_md.exists()

        # Verify round-trip
        loaded = load_state_json(cwd)
        assert loaded is not None
        assert loaded["position"]["current_phase"] == "03"

    def test_save_rollback_on_md_generation_error(self, tmp_path: Path) -> None:
        """If markdown generation fails mid-save, original files are restored."""
        cwd = _make_planning(tmp_path)
        original_state = default_state_dict()
        original_state["position"]["current_phase"] = "01"
        save_state_json(cwd, original_state)

        layout = ProjectLayout(cwd)
        layout.state_json.read_text(encoding="utf-8")

        # Now try a save that fails during markdown generation
        bad_state = default_state_dict()
        bad_state["position"]["current_phase"] = "02"

        with patch("gpd.core.state.generate_state_markdown", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                save_state_json(cwd, bad_state)

        # Original state should be preserved
        restored = layout.state_json.read_text(encoding="utf-8")
        assert json.loads(restored)["position"]["current_phase"] == "01"


# ===================================================================
# state.py: sync_state_json_core corrupt JSON handling
# ===================================================================


class TestSyncStateJsonCorrupt:
    """sync_state_json_core should handle corrupt state.json gracefully."""

    def test_sync_with_corrupt_json_uses_bak(self, tmp_path: Path) -> None:
        """When state.json is corrupt but .bak exists, sync merges with bak."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)

        # Write corrupt json
        layout.state_json.write_text("CORRUPT JSON", encoding="utf-8")
        # Write valid bak
        bak_state = default_state_dict()
        bak_state["position"]["current_phase"] = "04"
        layout.state_json.with_suffix(".json.bak").write_text(
            json.dumps(bak_state, indent=2), encoding="utf-8"
        )

        result = sync_state_json(cwd, MINIMAL_STATE_MD)
        assert result is not None
        # Should have merged with bak data
        assert "position" in result

    def test_sync_with_no_existing_json(self, tmp_path: Path) -> None:
        """When no state.json exists, sync creates from scratch."""
        cwd = _make_planning(tmp_path)
        result = sync_state_json(cwd, MINIMAL_STATE_MD)
        assert result is not None
        assert result["position"]["current_phase"] == "01"
        # state.json should now exist
        layout = ProjectLayout(cwd)
        assert layout.state_json.exists()


# ===================================================================
# frontmatter.py: extract_frontmatter error handling
# ===================================================================


class TestFrontmatterErrorHandling:
    """extract_frontmatter should raise FrontmatterParseError on bad YAML."""

    def test_malformed_yaml_raises(self) -> None:
        content = "---\n: : : bad yaml [[\n---\n\nBody"
        with pytest.raises(FrontmatterParseError):
            extract_frontmatter(content)

    def test_non_dict_yaml_raises(self) -> None:
        """If YAML block parses to a list instead of dict, raise."""
        content = "---\n- item1\n- item2\n---\n\nBody"
        with pytest.raises(FrontmatterParseError, match="Expected mapping"):
            extract_frontmatter(content)

    def test_no_frontmatter_returns_empty_dict(self) -> None:
        """Content without frontmatter returns ({}, content)."""
        meta, body = extract_frontmatter("Just plain text\n\nMore text")
        assert meta == {}
        assert "Just plain text" in body

    def test_empty_frontmatter_returns_empty_dict(self) -> None:
        """Empty frontmatter (---\\n---) returns ({}, body)."""
        meta, body = extract_frontmatter("---\n---\n\nBody here")
        assert meta == {}
        assert "Body here" in body

    def test_bom_stripped(self) -> None:
        """BOM character at start of content is stripped."""
        content = "\ufeff---\nkey: value\n---\n\nBody"
        meta, body = extract_frontmatter(content)
        assert meta == {"key": "value"}
        assert "Body" in body

    def test_splice_frontmatter_on_malformed_propagates(self) -> None:
        """splice_frontmatter propagates FrontmatterParseError from extract."""
        content = "---\n: : : bad\n---\n\nBody"
        with pytest.raises(FrontmatterParseError):
            splice_frontmatter(content, {"new_key": "value"})


# ===================================================================
# frontmatter.py: validate_frontmatter error handling
# ===================================================================


class TestValidateFrontmatter:
    """validate_frontmatter should raise on unknown schema, report missing fields."""

    def test_unknown_schema_raises(self) -> None:
        with pytest.raises(FrontmatterValidationError, match="Unknown schema"):
            validate_frontmatter("---\nkey: val\n---\n\nBody", "nonexistent_schema")

    def test_missing_fields_reported(self) -> None:
        """A plan with missing required fields should report them."""
        content = "---\nphase: 01\nplan: 01\n---\n\nBody"
        result = validate_frontmatter(content, "plan")
        assert not result.valid
        assert len(result.missing) > 0
        assert "phase" not in result.missing  # present
        assert "plan" not in result.missing  # present

    def test_valid_plan_frontmatter(self) -> None:
        """A plan with all required fields passes."""
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value within tolerance\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main benchmark figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      applies_to: [claim-main]\n"
            "      must_surface: true\n"
            "      required_actions: [read, compare, cite]\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches reference within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match without numerical comparison\n"
            "      reason: Would allow false progress without the decisive benchmark\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
            "---\n\nBody"
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid

    def test_malformed_yaml_in_validate(self) -> None:
        """Malformed YAML in validate propagates as FrontmatterParseError."""
        content = "---\n: : bad\n---\n\nBody"
        with pytest.raises(FrontmatterParseError):
            validate_frontmatter(content, "plan")


# ===================================================================
# config.py: load_config error handling
# ===================================================================


class TestConfigErrorHandling:
    """load_config should return defaults on missing file, raise on malformed."""

    def test_missing_config_returns_defaults(self, tmp_path: Path) -> None:
        """When config.json doesn't exist, return default GPDProjectConfig."""
        cwd = _make_planning(tmp_path)
        config = load_config(cwd)
        assert isinstance(config, GPDProjectConfig)
        assert config.model_profile.value == "review"

    def test_malformed_json_raises_config_error(self, tmp_path: Path) -> None:
        """Malformed JSON in config.json should raise ConfigError."""
        cwd = _make_planning(tmp_path)
        config_path = ProjectLayout(cwd).config_json
        config_path.write_text("NOT JSON {{{", encoding="utf-8")
        with pytest.raises(ConfigError, match="Malformed config.json"):
            load_config(cwd)

    def test_non_object_json_raises_config_error(self, tmp_path: Path) -> None:
        """JSON that parses to a list (not object) should raise ConfigError."""
        cwd = _make_planning(tmp_path)
        config_path = ProjectLayout(cwd).config_json
        config_path.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ConfigError, match="must be a JSON object"):
            load_config(cwd)

    def test_invalid_enum_value_raises_config_error(self, tmp_path: Path) -> None:
        """Invalid enum value in config should raise ConfigError."""
        cwd = _make_planning(tmp_path)
        config_path = ProjectLayout(cwd).config_json
        config_path.write_text(json.dumps({"model_profile": "nonexistent-profile"}), encoding="utf-8")
        with pytest.raises(ConfigError, match="Invalid config.json values"):
            load_config(cwd)

    def test_valid_config_loads(self, tmp_path: Path) -> None:
        """Valid config.json loads correctly."""
        cwd = _make_planning(tmp_path)
        config_path = ProjectLayout(cwd).config_json
        config_path.write_text(
            json.dumps({"model_profile": "deep-theory", "commit_docs": False}),
            encoding="utf-8",
        )
        config = load_config(cwd)
        assert config.model_profile.value == "deep-theory"
        assert config.commit_docs is False

    def test_empty_object_returns_defaults(self, tmp_path: Path) -> None:
        """Empty {} config.json returns all defaults."""
        cwd = _make_planning(tmp_path)
        config_path = ProjectLayout(cwd).config_json
        config_path.write_text("{}", encoding="utf-8")
        config = load_config(cwd)
        assert config == GPDProjectConfig()

# ===================================================================
# health.py: check_* functions graceful degradation
# ===================================================================


class TestHealthCheckGracefulDegradation:
    """Health check functions should never raise, always return HealthCheck."""

    def test_check_state_validity_no_files(self, tmp_path: Path) -> None:
        """check_state_validity with no state files returns FAIL, not raise."""
        cwd = _make_planning(tmp_path)
        result = check_state_validity(cwd)
        assert result.status == CheckStatus.FAIL
        assert any("not found" in issue for issue in result.issues)

    def test_check_state_validity_corrupt_json(self, tmp_path: Path) -> None:
        """check_state_validity with corrupt state.json returns FAIL."""
        cwd = _make_planning(tmp_path)
        layout = ProjectLayout(cwd)
        layout.state_json.write_text("CORRUPT JSON", encoding="utf-8")
        result = check_state_validity(cwd)
        assert result.status == CheckStatus.FAIL
        assert any("parse error" in issue or "not found" in issue for issue in result.issues)

    def test_check_config_missing_file(self, tmp_path: Path) -> None:
        """check_config with no config.json returns WARN (not raise)."""
        cwd = _make_planning(tmp_path)
        result = check_config(cwd)
        assert result.status == CheckStatus.WARN
        assert any("not found" in w for w in result.warnings)

    def test_check_config_malformed(self, tmp_path: Path) -> None:
        """check_config with malformed JSON returns FAIL (not raise)."""
        cwd = _make_planning(tmp_path)
        config_path = ProjectLayout(cwd).config_json
        config_path.write_text("NOT JSON", encoding="utf-8")
        result = check_config(cwd)
        assert result.status == CheckStatus.FAIL
        assert any("parse error" in issue for issue in result.issues)

    def test_check_convention_lock_no_state(self, tmp_path: Path) -> None:
        """check_convention_lock with no state.json returns WARN (not raise)."""
        cwd = _make_planning(tmp_path)
        result = check_convention_lock(cwd)
        assert result.status == CheckStatus.WARN

    def test_check_convention_lock_no_convention_section(self, tmp_path: Path) -> None:
        """check_convention_lock with state.json missing convention_lock returns WARN."""
        cwd = _make_planning(tmp_path)
        _write_state_json(cwd, {"position": {"current_phase": "01"}})
        result = check_convention_lock(cwd)
        assert result.status == CheckStatus.WARN


# ===================================================================
# utils.py: safe_* functions
# ===================================================================


class TestSafeParseFunctions:
    """safe_read_file never raises."""

    def test_safe_read_file_missing(self, tmp_path: Path) -> None:
        assert safe_read_file(tmp_path / "nonexistent.txt") is None

    def test_safe_read_file_directory(self, tmp_path: Path) -> None:
        """Reading a directory returns None (not raise)."""
        assert safe_read_file(tmp_path) is None

    def test_safe_read_file_permission_error(self, tmp_path: Path) -> None:
        """Reading a file with permission error returns None."""
        f = tmp_path / "noperm.txt"
        f.write_text("content")
        f.chmod(0o000)
        try:
            assert safe_read_file(f) is None
        finally:
            f.chmod(0o644)


# ===================================================================
# json_utils.py: error handling
# ===================================================================


class TestJsonUtilsErrorHandling:
    """json_utils functions should handle invalid input gracefully."""

    def test_json_get_invalid_json_with_default(self) -> None:
        """json_get with invalid JSON and a default returns the default."""
        assert json_get("NOT JSON", ".key", default="fallback") == "fallback"

    def test_json_get_invalid_json_no_default_raises(self) -> None:
        """json_get with invalid JSON and no default raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid JSON"):
            json_get("NOT JSON", ".key")

    def test_json_get_missing_key_returns_empty(self) -> None:
        """json_get for a missing key returns empty string."""
        assert json_get('{"a": 1}', ".b") == ""

    def test_json_get_missing_key_with_default(self) -> None:
        """json_get for a missing key with default returns the default."""
        assert json_get('{"a": 1}', ".b", default="nope") == "nope"

    def test_json_keys_invalid_json(self) -> None:
        """json_keys with invalid JSON returns empty string."""
        assert json_keys("CORRUPT", ".") == ""

    def test_json_list_invalid_json(self) -> None:
        """json_list with invalid JSON returns empty string."""
        assert json_list("CORRUPT", ".") == ""

    def test_json_pluck_invalid_json(self) -> None:
        """json_pluck with invalid JSON returns empty string."""
        assert json_pluck("CORRUPT", ".items", "name") == ""


# ===================================================================
# state.py: generate_state_markdown with ensure_state_schema
# ===================================================================


class TestGenerateMarkdownFromBadState:
    """generate_state_markdown calls ensure_state_schema, so it should
    handle arbitrary dicts without crashing."""

    def test_empty_dict(self) -> None:
        md = generate_state_markdown({})
        assert "# Research State" in md

    def test_partial_state(self) -> None:
        md = generate_state_markdown({"position": {"current_phase": "07"}})
        assert "07" in md
        assert "# Research State" in md

    def test_none_values_in_position(self) -> None:
        """None values should produce placeholder characters, not crash."""
        state = default_state_dict()
        state["position"]["current_phase"] = None
        state["position"]["status"] = None
        md = generate_state_markdown(state)
        assert "# Research State" in md


# ===================================================================
# state.py: full save/load round-trip under adversity
# ===================================================================


class TestSaveLoadRoundTrip:
    """Verify save_state_json -> load_state_json preserves data."""

    def test_roundtrip_preserves_all_fields(self, tmp_path: Path) -> None:
        cwd = _make_planning(tmp_path)
        state = default_state_dict()
        state["position"]["current_phase"] = "03"
        state["position"]["status"] = "Executing"
        state["decisions"] = [{"phase": "01", "summary": "Use SI units", "rationale": "Standard"}]
        state["blockers"] = ["Waiting for data"]

        save_state_json(cwd, state)
        loaded = load_state_json(cwd)

        assert loaded is not None
        assert loaded["position"]["current_phase"] == "03"
        assert loaded["position"]["status"] == "Executing"
        assert len(loaded["decisions"]) == 1
        assert loaded["decisions"][0]["summary"] == "Use SI units"
        assert loaded["blockers"] == ["Waiting for data"]

    def test_overwrite_preserves_new_state(self, tmp_path: Path) -> None:
        """A second save overwrites the first completely."""
        cwd = _make_planning(tmp_path)
        state1 = default_state_dict()
        state1["position"]["current_phase"] = "01"
        save_state_json(cwd, state1)

        state2 = default_state_dict()
        state2["position"]["current_phase"] = "02"
        save_state_json(cwd, state2)

        loaded = load_state_json(cwd)
        assert loaded is not None
        assert loaded["position"]["current_phase"] == "02"

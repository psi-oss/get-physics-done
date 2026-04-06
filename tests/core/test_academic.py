"""Tests for gpd.core.academic — academic platform experiment support."""

import json
from pathlib import Path

import pytest

from gpd.core.academic import (
    AcademicArtifact,
    AcademicEvent,
    AcademicSessionSummary,
    academic_session_summary,
    capture_artifact,
    check_budget_guard,
    log_academic_event,
)
from gpd.core.config import GPDProjectConfig, PlatformMode, check_credit_budget, is_academic_mode
from gpd.core.errors import ConfigError


# ─── Config helpers ───────────────────────────────────────────────────────────


class TestIsAcademicMode:
    def test_standard_mode_returns_false(self):
        cfg = GPDProjectConfig()
        assert not is_academic_mode(cfg)

    def test_academic_mode_returns_true(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC)
        assert is_academic_mode(cfg)


class TestCheckCreditBudget:
    def test_unlimited_budget(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=None)
        has_budget, remaining = check_credit_budget(cfg)
        assert has_budget is True
        assert remaining is None

    def test_budget_with_remaining(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=100, credit_used=30)
        has_budget, remaining = check_credit_budget(cfg)
        assert has_budget is True
        assert remaining == 70

    def test_budget_exhausted(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=100, credit_used=100)
        has_budget, remaining = check_credit_budget(cfg)
        assert has_budget is False
        assert remaining == 0

    def test_budget_over_used(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=50, credit_used=80)
        has_budget, remaining = check_credit_budget(cfg)
        assert has_budget is False
        assert remaining == 0


# ─── Budget guard ─────────────────────────────────────────────────────────────


class TestCheckBudgetGuard:
    def test_standard_mode_no_op(self):
        cfg = GPDProjectConfig()
        check_budget_guard(cfg)  # should not raise

    def test_academic_unlimited_no_op(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=None)
        check_budget_guard(cfg)  # should not raise

    def test_academic_with_remaining_no_op(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=100, credit_used=50)
        check_budget_guard(cfg)  # should not raise

    def test_academic_exhausted_raises(self):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=100, credit_used=100)
        with pytest.raises(ConfigError, match="credit budget exhausted"):
            check_budget_guard(cfg)


# ─── Event logging ────────────────────────────────────────────────────────────


class TestLogAcademicEvent:
    def test_standard_mode_returns_none(self, tmp_path: Path):
        cfg = GPDProjectConfig()
        result = log_academic_event(tmp_path, cfg, event_type="agent_invocation")
        assert result is None

    def test_academic_mode_logs_event(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=100, credit_used=10)
        result = log_academic_event(
            tmp_path,
            cfg,
            event_type="agent_invocation",
            agent="gpd-planner",
            credit_cost=5,
            phase="1",
            plan="01-setup",
        )
        assert result is not None
        assert isinstance(result, AcademicEvent)
        assert result.event_type == "agent_invocation"
        assert result.agent == "gpd-planner"
        assert result.credit_cost == 5
        assert result.credit_remaining == 90

    def test_event_persisted_to_jsonl(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC)
        log_academic_event(tmp_path, cfg, event_type="checkpoint_reached")

        log_path = tmp_path / "GPD" / "academic" / "events.jsonl"
        assert log_path.exists()
        lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1
        evt = json.loads(lines[0])
        assert evt["event_type"] == "checkpoint_reached"

    def test_multiple_events_appended(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC)
        log_academic_event(tmp_path, cfg, event_type="agent_invocation", agent="gpd-planner")
        log_academic_event(tmp_path, cfg, event_type="agent_invocation", agent="gpd-executor")

        log_path = tmp_path / "GPD" / "academic" / "events.jsonl"
        lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 2


# ─── Artifact capture ────────────────────────────────────────────────────────


class TestCaptureArtifact:
    def test_standard_mode_returns_none(self, tmp_path: Path):
        cfg = GPDProjectConfig()
        result = capture_artifact(tmp_path, cfg, artifact_type="derivation", path="output/eq1.tex")
        assert result is None

    def test_capture_disabled_returns_none(self, tmp_path: Path):
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, artifact_capture=False)
        result = capture_artifact(tmp_path, cfg, artifact_type="derivation", path="output/eq1.tex")
        assert result is None

    def test_academic_mode_captures_artifact(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC)
        result = capture_artifact(
            tmp_path,
            cfg,
            artifact_type="derivation",
            path="output/eq1.tex",
            agent="gpd-executor",
            description="Derived equation of motion",
            provenance={"source": "lagrangian.tex", "method": "euler-lagrange"},
            reproducibility={"seed": 42, "model": "tier-1"},
        )
        assert result is not None
        assert isinstance(result, AcademicArtifact)
        assert result.artifact_type == "derivation"
        assert result.path == "output/eq1.tex"
        assert result.provenance["method"] == "euler-lagrange"

    def test_artifact_persisted_to_jsonl(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC)
        capture_artifact(tmp_path, cfg, artifact_type="plot", path="figures/fig1.png")

        art_path = tmp_path / "GPD" / "academic" / "artifacts.jsonl"
        assert art_path.exists()
        lines = [ln for ln in art_path.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1
        art = json.loads(lines[0])
        assert art["artifact_type"] == "plot"
        assert art["path"] == "figures/fig1.png"


# ─── Session summary ─────────────────────────────────────────────────────────


class TestAcademicSessionSummary:
    def test_standard_mode_returns_none(self, tmp_path: Path):
        cfg = GPDProjectConfig()
        result = academic_session_summary(tmp_path, cfg)
        assert result is None

    def test_empty_academic_session(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=500, credit_used=0)
        result = academic_session_summary(tmp_path, cfg)
        assert result is not None
        assert result.credit_budget == 500
        assert result.credit_used == 0
        assert result.credit_remaining == 500
        assert result.event_count == 0
        assert result.artifact_count == 0

    def test_summary_with_events_and_artifacts(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        cfg = GPDProjectConfig(platform_mode=PlatformMode.ACADEMIC, credit_budget=100, credit_used=25)

        # Log some events
        log_academic_event(tmp_path, cfg, event_type="agent_invocation", credit_cost=10)
        log_academic_event(tmp_path, cfg, event_type="agent_invocation", credit_cost=15)
        log_academic_event(tmp_path, cfg, event_type="checkpoint_reached")

        # Capture an artifact
        capture_artifact(tmp_path, cfg, artifact_type="derivation", path="eq.tex")

        result = academic_session_summary(tmp_path, cfg)
        assert result is not None
        assert result.event_count == 3
        assert result.artifact_count == 1
        assert result.events_by_type["agent_invocation"] == 2
        assert result.events_by_type["checkpoint_reached"] == 1
        assert result.credit_remaining == 75


# ─── Config integration ──────────────────────────────────────────────────────


class TestPlatformModeEnum:
    def test_standard_value(self):
        assert PlatformMode.STANDARD.value == "standard"

    def test_academic_value(self):
        assert PlatformMode.ACADEMIC.value == "academic"


class TestGPDProjectConfigAcademicDefaults:
    def test_defaults(self):
        cfg = GPDProjectConfig()
        assert cfg.platform_mode == PlatformMode.STANDARD
        assert cfg.credit_budget is None
        assert cfg.credit_used == 0
        assert cfg.artifact_capture is True

    def test_academic_config(self):
        cfg = GPDProjectConfig(
            platform_mode=PlatformMode.ACADEMIC,
            credit_budget=1000,
            credit_used=50,
            artifact_capture=True,
        )
        assert cfg.platform_mode == PlatformMode.ACADEMIC
        assert cfg.credit_budget == 1000
        assert cfg.credit_used == 50

"""Tests for gpd.core.config."""

import json
from pathlib import Path

import pytest

from gpd.core.config import (
    AGENT_DEFAULT_TIERS,
    MODEL_PROFILES,
    AutonomyMode,
    BranchingStrategy,
    GPDProjectConfig,
    ModelProfile,
    ModelTier,
    ResearchMode,
    ReviewCadence,
    _valid_runtime_names,
    load_config,
    resolve_agent_tier,
    resolve_model,
    resolve_tier,
)
from gpd.core.errors import ConfigError

# ─── Enum values ────────────────────────────────────────────────────────────────


class TestEnums:
    def test_autonomy_values(self):
        assert AutonomyMode.SUPERVISED.value == "supervised"
        assert AutonomyMode.BALANCED.value == "balanced"
        assert AutonomyMode.YOLO.value == "yolo"

    def test_research_mode_values(self):
        assert ResearchMode.EXPLORE.value == "explore"
        assert ResearchMode.BALANCED.value == "balanced"
        assert ResearchMode.EXPLOIT.value == "exploit"
        assert ResearchMode.ADAPTIVE.value == "adaptive"

    def test_review_cadence_values(self):
        assert ReviewCadence.DENSE.value == "dense"
        assert ReviewCadence.ADAPTIVE.value == "adaptive"
        assert ReviewCadence.SPARSE.value == "sparse"

    def test_model_profile_values(self):
        assert ModelProfile.DEEP_THEORY.value == "deep-theory"
        assert ModelProfile.NUMERICAL.value == "numerical"
        assert ModelProfile.EXPLORATORY.value == "exploratory"
        assert ModelProfile.REVIEW.value == "review"
        assert ModelProfile.PAPER_WRITING.value == "paper-writing"

    def test_model_tier_values(self):
        assert ModelTier.TIER_1.value == "tier-1"
        assert ModelTier.TIER_2.value == "tier-2"
        assert ModelTier.TIER_3.value == "tier-3"

    def test_branching_strategy_values(self):
        assert BranchingStrategy.NONE.value == "none"
        assert BranchingStrategy.PER_PHASE.value == "per-phase"
        assert BranchingStrategy.PER_MILESTONE.value == "per-milestone"


# ─── MODEL_PROFILES table ──────────────────────────────────────────────────────


class TestModelProfiles:
    def test_all_23_agents_present(self):
        assert len(MODEL_PROFILES) == 23

    def test_all_agents_have_5_profiles(self):
        profiles = {"deep-theory", "numerical", "exploratory", "review", "paper-writing"}
        for agent, mapping in MODEL_PROFILES.items():
            assert set(mapping.keys()) == profiles, f"{agent} missing profiles"

    def test_planner_always_tier_1(self):
        for profile, tier in MODEL_PROFILES["gpd-planner"].items():
            assert tier == ModelTier.TIER_1, f"planner {profile} should be tier-1"

    def test_research_mapper_mostly_tier_3(self):
        tiers = MODEL_PROFILES["gpd-research-mapper"]
        assert tiers["deep-theory"] == ModelTier.TIER_2
        assert tiers["numerical"] == ModelTier.TIER_3

    def test_agent_default_tiers_match_agents(self):
        assert set(AGENT_DEFAULT_TIERS.keys()) == set(MODEL_PROFILES.keys())


# ─── GPDProjectConfig defaults ────────────────────────────────────────────────────────


class TestGPDProjectConfigDefaults:
    def test_defaults(self):
        cfg = GPDProjectConfig()
        assert cfg.model_profile == ModelProfile.REVIEW
        assert cfg.autonomy == AutonomyMode.BALANCED
        assert cfg.review_cadence == ReviewCadence.ADAPTIVE
        assert cfg.research_mode == ResearchMode.BALANCED
        assert cfg.commit_docs is True
        assert cfg.parallelization is True
        assert cfg.max_unattended_minutes_per_plan == 45
        assert cfg.max_unattended_minutes_per_wave == 90
        assert cfg.checkpoint_after_n_tasks == 3
        assert cfg.checkpoint_after_first_load_bearing_result is True
        assert cfg.checkpoint_before_downstream_dependent_tasks is True
        assert cfg.branching_strategy == BranchingStrategy.NONE
        assert cfg.model_overrides is None


# ─── load_config ────────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path: Path):
        cfg = load_config(tmp_path)
        assert cfg == GPDProjectConfig()

    def test_empty_object(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text("{}")
        cfg = load_config(tmp_path)
        assert cfg.model_profile == ModelProfile.REVIEW

    def test_custom_values(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "model_profile": "deep-theory",
                    "autonomy": "yolo",
                    "review_cadence": "dense",
                    "research_mode": "explore",
                    "commit_docs": False,
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.model_profile == ModelProfile.DEEP_THEORY
        assert cfg.autonomy == AutonomyMode.YOLO
        assert cfg.review_cadence == ReviewCadence.DENSE
        assert cfg.research_mode == ResearchMode.EXPLORE
        assert cfg.commit_docs is False

    @pytest.mark.parametrize(
        "invalid_value",
        ["manual", "guided", "autonomous"],
    )
    def test_invalid_autonomy_values_raise_config_error(
        self,
        tmp_path: Path,
        invalid_value: str,
    ) -> None:
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"autonomy": invalid_value}))

        with pytest.raises(ConfigError, match="Invalid config.json values"):
            load_config(tmp_path)

    def test_nested_section_fallback(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "planning": {"commit_docs": False},
                    "execution": {
                        "review_cadence": "sparse",
                        "max_unattended_minutes_per_plan": 30,
                        "checkpoint_after_n_tasks": 2,
                    },
                    "git": {"branching_strategy": "per-phase"},
                    "workflow": {"research": False, "verifier": False},
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.commit_docs is False
        assert cfg.review_cadence == ReviewCadence.SPARSE
        assert cfg.max_unattended_minutes_per_plan == 30
        assert cfg.checkpoint_after_n_tasks == 2
        assert cfg.branching_strategy == BranchingStrategy.PER_PHASE
        assert cfg.research is False
        assert cfg.verifier is False

    def test_gitignored_planning_dir_forces_commit_docs_false(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"commit_docs": True}))
        monkeypatch.setattr("gpd.core.config._planning_dir_is_gitignored", lambda _: True)

        cfg = load_config(tmp_path)

        assert cfg.commit_docs is False

    def test_malformed_json_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text("{bad json")
        with pytest.raises(ConfigError, match="Malformed config.json"):
            load_config(tmp_path)

    def test_physics_section_is_rejected_by_current_config_schema(self, tmp_path: Path) -> None:
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps({"physics": {"unit_system": "natural"}}),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `physics`"):
            load_config(tmp_path)

    def test_model_overrides(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "model_overrides": {
                        "codex": {"tier-1": "o3", "tier-2": "gpt-4.1"},
                        "claude-code": {"tier-1": "opus"},
                    },
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.model_overrides == {
            "codex": {"tier-1": "o3", "tier-2": "gpt-4.1"},
            "claude-code": {"tier-1": "opus"},
        }

    def test_invalid_model_overrides_runtime_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps({"model_overrides": {"unknown-runtime": {"tier-1": "foo"}}})
        )
        with pytest.raises(ConfigError, match="model_overrides contains unknown runtime"):
            load_config(tmp_path)

    def test_invalid_model_overrides_tier_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps({"model_overrides": {"codex": {"tier-x": "foo"}}})
        )
        with pytest.raises(ConfigError, match="model_overrides\\['codex'\\] contains unknown tier"):
            load_config(tmp_path)

    def test_model_overrides_runtime_lookup_failure_raises_config_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps({"model_overrides": {"codex": {"tier-1": "gpt-5"}}})
        )

        _valid_runtime_names.cache_clear()

        def _raise_runtime_lookup_failure() -> list[str]:
            raise FileNotFoundError("runtime catalog missing")

        monkeypatch.setattr("gpd.adapters.runtime_catalog.list_runtime_names", _raise_runtime_lookup_failure)

        with pytest.raises(ConfigError, match="Unable to resolve supported runtimes"):
            load_config(tmp_path)

        _valid_runtime_names.cache_clear()

# ─── resolve_agent_tier ─────────────────────────────────────────────────────────


class TestResolveAgentTier:
    def test_known_agent_and_profile(self):
        tier = resolve_agent_tier("gpd-planner", ModelProfile.DEEP_THEORY)
        assert tier == ModelTier.TIER_1

    def test_executor_numerical(self):
        tier = resolve_agent_tier("gpd-executor", "numerical")
        assert tier == ModelTier.TIER_2

    def test_unknown_agent_raises(self):
        with pytest.raises(ConfigError, match="Unknown agent 'gpd-unknown'"):
            resolve_agent_tier("gpd-unknown", "review")

    def test_unknown_profile_falls_back_to_review(self):
        tier = resolve_agent_tier("gpd-planner", "nonexistent")
        assert tier == ModelTier.TIER_1  # planner review is tier-1

    def test_registry_only_agent_falls_back_to_default_tier(self, monkeypatch: pytest.MonkeyPatch):
        import gpd.registry as content_registry

        monkeypatch.setattr(content_registry, "list_agents", lambda: ["gpd-registry-only"])

        tier = resolve_agent_tier("gpd-registry-only", "review")

        assert tier == ModelTier.TIER_2


# ─── resolve_model ──────────────────────────────────────────────────────────────


class TestResolveModel:
    def test_default_config(self, tmp_path: Path):
        model = resolve_model(tmp_path, "gpd-planner")
        assert model is None

    def test_with_runtime_specific_override(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "model_overrides": {
                        "claude-code": {"tier-1": "opus"},
                        "codex": {"tier-1": "gpt-5"},
                    },
                }
            )
        )
        model = resolve_model(tmp_path, "gpd-planner", runtime="claude-code")
        assert model == "opus"

    def test_without_override_for_active_runtime_returns_none(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "model_overrides": {
                        "claude-code": {"tier-1": "opus"},
                    }
                }
            )
        )
        model = resolve_model(tmp_path, "gpd-planner", runtime="codex")
        assert model is None


class TestResolveTier:
    def test_project_resolve_tier_uses_profile(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps({"model_profile": "paper-writing"})
        )
        tier = resolve_tier(tmp_path, "gpd-project-researcher")
        assert tier == ModelTier.TIER_3

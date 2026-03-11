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
    load_config,
    resolve_agent_tier,
    resolve_model,
    resolve_tier,
)
from gpd.core.errors import ConfigError

# ─── Enum values ────────────────────────────────────────────────────────────────


class TestEnums:
    def test_autonomy_values(self):
        assert AutonomyMode.BABYSIT.value == "babysit"
        assert AutonomyMode.BALANCED.value == "balanced"
        assert AutonomyMode.YOLO.value == "yolo"

    def test_research_mode_values(self):
        assert ResearchMode.EXPLORE.value == "explore"
        assert ResearchMode.BALANCED.value == "balanced"
        assert ResearchMode.EXPLOIT.value == "exploit"
        assert ResearchMode.ADAPTIVE.value == "adaptive"

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
        assert cfg.research_mode == ResearchMode.BALANCED
        assert cfg.commit_docs is True
        assert cfg.parallelization is True
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
                    "research_mode": "explore",
                    "commit_docs": False,
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.model_profile == ModelProfile.DEEP_THEORY
        assert cfg.autonomy == AutonomyMode.YOLO
        assert cfg.research_mode == ResearchMode.EXPLORE
        assert cfg.commit_docs is False

    def test_nested_section_fallback(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "planning": {"commit_docs": False},
                    "git": {"branching_strategy": "per-phase"},
                    "workflow": {"research": False, "verifier": False},
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.commit_docs is False
        assert cfg.branching_strategy == BranchingStrategy.PER_PHASE
        assert cfg.research is False
        assert cfg.verifier is False

    def test_removed_mode_key_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"mode": "yolo"}))
        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `mode`"):
            load_config(tmp_path)

    def test_removed_depth_key_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"depth": "standard"}))
        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `depth`"):
            load_config(tmp_path)

    def test_parallelization_must_be_bool(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"parallelization": {"enabled": False}}))
        with pytest.raises(
            ConfigError,
            match=r"Unsupported config\.json keys: `parallelization\.enabled`",
        ):
            load_config(tmp_path)

    def test_plan_checker_requires_current_key(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"workflow": {"plan_check": False}}))
        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `workflow\.plan_check`"):
            load_config(tmp_path)

    def test_removed_search_gitignored_key_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"planning": {"search_gitignored": True}}))
        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `planning\.search_gitignored`"):
            load_config(tmp_path)

    def test_removed_brave_search_key_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"brave_search": True}))
        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `brave_search`"):
            load_config(tmp_path)

    def test_malformed_json_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text("{bad json")
        with pytest.raises(ConfigError, match="Malformed config.json"):
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

    def test_removed_model_map_key_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"model_map": {"tier-1": "opus"}}))
        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `model_map`"):
            load_config(tmp_path)

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

# ─── resolve_agent_tier ─────────────────────────────────────────────────────────


class TestResolveAgentTier:
    def test_known_agent_and_profile(self):
        tier = resolve_agent_tier("gpd-planner", ModelProfile.DEEP_THEORY)
        assert tier == ModelTier.TIER_1

    def test_executor_numerical(self):
        tier = resolve_agent_tier("gpd-executor", "numerical")
        assert tier == ModelTier.TIER_2

    def test_unknown_agent_falls_back(self):
        tier = resolve_agent_tier("gpd-unknown", "review")
        assert tier == ModelTier.TIER_2

    def test_unknown_profile_falls_back_to_review(self):
        tier = resolve_agent_tier("gpd-planner", "nonexistent")
        assert tier == ModelTier.TIER_1  # planner review is tier-1


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

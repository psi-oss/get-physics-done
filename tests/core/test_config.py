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
    get_cost_per_million,
    load_config,
    resolve_agent_tier,
    resolve_model,
)
from gpd.core.errors import ConfigError

# ─── Enum values ────────────────────────────────────────────────────────────────


class TestEnums:
    def test_autonomy_values(self):
        assert AutonomyMode.SUPERVISED.value == "supervised"
        assert AutonomyMode.GUIDED.value == "guided"
        assert AutonomyMode.AUTONOMOUS.value == "autonomous"
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
    def test_all_17_agents_present(self):
        assert len(MODEL_PROFILES) == 17

    def test_all_agents_have_5_profiles(self):
        profiles = {"deep-theory", "numerical", "exploratory", "review", "paper-writing"}
        for agent, mapping in MODEL_PROFILES.items():
            assert set(mapping.keys()) == profiles, f"{agent} missing profiles"

    def test_planner_always_tier_1(self):
        for profile, tier in MODEL_PROFILES["gpd-planner"].items():
            assert tier == ModelTier.TIER_1, f"planner {profile} should be tier-1"

    def test_theory_mapper_mostly_tier_3(self):
        tiers = MODEL_PROFILES["gpd-theory-mapper"]
        assert tiers["deep-theory"] == ModelTier.TIER_2
        assert tiers["numerical"] == ModelTier.TIER_3

    def test_agent_default_tiers_match_agents(self):
        assert set(AGENT_DEFAULT_TIERS.keys()) == set(MODEL_PROFILES.keys())


# ─── GPDProjectConfig defaults ────────────────────────────────────────────────────────


class TestGPDProjectConfigDefaults:
    def test_defaults(self):
        cfg = GPDProjectConfig()
        assert cfg.model_profile == ModelProfile.REVIEW
        assert cfg.autonomy == AutonomyMode.GUIDED
        assert cfg.research_mode == ResearchMode.BALANCED
        assert cfg.commit_docs is True
        assert cfg.search_gitignored is False
        assert cfg.parallelization is True
        assert cfg.branching_strategy == BranchingStrategy.NONE
        assert cfg.model_map is None
        assert cfg.cost_per_million is None


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
                    "autonomy": "autonomous",
                    "research_mode": "explore",
                    "commit_docs": False,
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.model_profile == ModelProfile.DEEP_THEORY
        assert cfg.autonomy == AutonomyMode.AUTONOMOUS
        assert cfg.research_mode == ResearchMode.EXPLORE
        assert cfg.commit_docs is False

    def test_nested_section_fallback(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "planning": {"commit_docs": False, "search_gitignored": True},
                    "git": {"branching_strategy": "per-phase"},
                    "workflow": {"research": False, "verifier": False},
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.commit_docs is False
        assert cfg.search_gitignored is True
        assert cfg.branching_strategy == BranchingStrategy.PER_PHASE
        assert cfg.research is False
        assert cfg.verifier is False

    def test_removed_mode_key_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"mode": "yolo"}))
        with pytest.raises(ConfigError, match="`mode` was removed; use `autonomy`"):
            load_config(tmp_path)

    def test_removed_depth_key_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"depth": "standard"}))
        with pytest.raises(ConfigError, match="`depth` was removed; use `research_mode` and `model_profile`"):
            load_config(tmp_path)

    def test_parallelization_must_be_bool(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"parallelization": {"enabled": False}}))
        with pytest.raises(
            ConfigError,
            match="`parallelization.enabled` object form was removed; set `parallelization` to true or false",
        ):
            load_config(tmp_path)

    def test_plan_checker_requires_current_key(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(json.dumps({"workflow": {"plan_check": False}}))
        with pytest.raises(ConfigError, match="`workflow.plan_check` was removed; use `workflow.plan_checker`"):
            load_config(tmp_path)

    def test_malformed_json_raises(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text("{bad json")
        with pytest.raises(ConfigError, match="Malformed config.json"):
            load_config(tmp_path)

    def test_model_map_override(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "model_map": {"tier-1": "o3", "tier-2": "gpt-4.1"},
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.model_map == {"tier-1": "o3", "tier-2": "gpt-4.1"}

    def test_cost_per_million_override(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "cost_per_million": {
                        "tier-1": {"input": 10, "output": 30},
                    },
                }
            )
        )
        cfg = load_config(tmp_path)
        assert cfg.cost_per_million is not None
        assert cfg.cost_per_million["tier-1"].input == 10.0


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
        # Default profile is "review", planner review is tier-1
        assert model == "tier-1"

    def test_with_model_map(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "model_map": {"tier-1": "opus"},
                }
            )
        )
        model = resolve_model(tmp_path, "gpd-planner")
        assert model == "opus"


# ─── get_cost_per_million ───────────────────────────────────────────────────────


class TestGetCostPerMillion:
    def test_defaults(self):
        costs = get_cost_per_million()
        assert "tier-1" in costs
        assert costs["tier-1"].input == 15.0
        assert costs["tier-1"].output == 75.0

    def test_project_override(self, tmp_path: Path):
        (tmp_path / ".gpd").mkdir()
        (tmp_path / ".gpd" / "config.json").write_text(
            json.dumps(
                {
                    "cost_per_million": {
                        "tier-1": {"input": 10, "output": 30},
                    },
                }
            )
        )
        costs = get_cost_per_million(tmp_path)
        assert costs["tier-1"].input == 10.0
        # tier-2 falls back to default
        assert costs["tier-2"].input == 3.0

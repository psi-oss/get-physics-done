"""Tests for gpd.core.config."""

import builtins
import json
import re
from pathlib import Path

import pytest

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
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
    apply_config_update,
    canonical_config_key,
    effective_config_value,
    load_config,
    resolve_agent_tier,
    resolve_model,
    resolve_tier,
    supported_config_keys,
)
from gpd.core.errors import ConfigError

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


def _load_raw_config(tmp_path: Path, raw: dict[str, object]) -> GPDProjectConfig:
    (tmp_path / "GPD").mkdir()
    (tmp_path / "GPD" / "config.json").write_text(json.dumps(raw), encoding="utf-8")
    return load_config(tmp_path)


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
    def test_all_28_agents_present(self):
        assert len(MODEL_PROFILES) == 28

    def test_all_agents_have_5_profiles(self):
        profiles = {profile.value for profile in ModelProfile}
        for agent, mapping in MODEL_PROFILES.items():
            assert set(mapping.keys()) == profiles, f"{agent} missing profiles"
            assert all(isinstance(tier, ModelTier) for tier in mapping.values())

    def test_planner_always_tier_1(self):
        for profile, tier in MODEL_PROFILES["gpd-planner"].items():
            assert tier == ModelTier.TIER_1, f"planner {profile} should be tier-1"

    def test_research_mapper_mostly_tier_3(self):
        tiers = MODEL_PROFILES["gpd-research-mapper"]
        assert tiers["deep-theory"] == ModelTier.TIER_2
        assert tiers["numerical"] == ModelTier.TIER_3

    def test_agent_default_tiers_match_agents(self):
        assert set(AGENT_DEFAULT_TIERS.keys()) == set(MODEL_PROFILES.keys())
        assert AGENT_DEFAULT_TIERS == {
            agent: mapping[ModelProfile.REVIEW.value] for agent, mapping in MODEL_PROFILES.items()
        }


# ─── GPDProjectConfig defaults ────────────────────────────────────────────────────────


class TestGPDProjectConfigDefaults:
    def test_defaults(self):
        cfg = GPDProjectConfig()
        assert cfg.model_profile == ModelProfile.REVIEW
        assert cfg.autonomy == AutonomyMode.SUPERVISED
        assert cfg.review_cadence == ReviewCadence.DENSE
        assert cfg.research_mode == ResearchMode.BALANCED
        assert cfg.commit_docs is True
        assert cfg.parallelization is True
        assert cfg.max_unattended_minutes_per_plan == 15
        assert cfg.max_unattended_minutes_per_wave == 30
        assert cfg.checkpoint_after_n_tasks == 1
        assert cfg.checkpoint_after_first_load_bearing_result is True
        assert cfg.checkpoint_before_downstream_dependent_tasks is True
        assert cfg.project_usd_budget is None
        assert cfg.session_usd_budget is None
        assert cfg.branching_strategy == BranchingStrategy.NONE
        assert cfg.model_overrides is None


class TestConfigKeyContracts:
    def test_supported_config_keys_are_writable_aliases_only(self) -> None:
        keys = supported_config_keys()

        assert len(keys) == 41
        assert all(section not in keys for section in ("execution", "workflow", "git"))
        assert {
            "execution.review_cadence": "review_cadence",
            "planning.commit_docs": "commit_docs",
            "workflow.research": "research",
            "git.branching_strategy": "branching_strategy",
            "execution_preferences.strict_wait": "strict_wait",
        } == {
            alias: canonical_config_key(alias)
            for alias in (
                "execution.review_cadence",
                "planning.commit_docs",
                "workflow.research",
                "git.branching_strategy",
                "execution_preferences.strict_wait",
            )
        }
        assert canonical_config_key("execution") is None

    def test_effective_section_values_render_in_stable_shape(self) -> None:
        cfg = GPDProjectConfig()

        assert effective_config_value(cfg, "execution") == (
            True,
            {
                "review_cadence": "dense",
                "max_unattended_minutes_per_plan": 15,
                "max_unattended_minutes_per_wave": 30,
                "checkpoint_after_n_tasks": 1,
                "checkpoint_after_first_load_bearing_result": True,
                "checkpoint_before_downstream_dependent_tasks": True,
                "project_usd_budget": None,
                "session_usd_budget": None,
            },
        )
        assert effective_config_value(cfg, "git") == (
            True,
            {
                "branching_strategy": "none",
                "phase_branch_template": "gpd/phase-{phase}-{slug}",
                "milestone_branch_template": "gpd/{milestone}-{slug}",
            },
        )
        assert effective_config_value(cfg, "execution_preferences") == (
            True,
            {
                "strict_wait": False,
                "never_interrupt_running_workers": False,
                "never_auto_close_child_agents": False,
            },
        )

    def test_mixed_storage_paths_are_preserved_for_nested_alias_updates(self) -> None:
        updated, canonical = apply_config_update({"review_cadence": "sparse"}, "execution.review_cadence", "adaptive")
        assert canonical == "review_cadence"
        assert updated == {"execution": {"review_cadence": "adaptive"}}

        updated, canonical = apply_config_update({"planning": {"commit_docs": False}}, "planning.commit_docs", True)
        assert canonical == "commit_docs"
        assert updated == {"commit_docs": True}

        updated, canonical = apply_config_update({"workflow": {"research": False}}, "workflow.research", True)
        assert canonical == "research"
        assert updated == {"research": True}

        updated, canonical = apply_config_update(
            {
                "git": {
                    "branching_strategy": "per-phase",
                    "phase_branch_template": "custom-phase",
                    "milestone_branch_template": "custom-milestone",
                }
            },
            "git.branching_strategy",
            "per-milestone",
        )
        assert canonical == "branching_strategy"
        assert updated == {
            "branching_strategy": "per-milestone",
            "git": {
                "phase_branch_template": "custom-phase",
                "milestone_branch_template": "custom-milestone",
            },
        }

    @pytest.mark.parametrize(
        "raw",
        [
            {"research": False, "workflow": {"research": False}},
            {"branching_strategy": "per-phase", "git": {"branching_strategy": "per-phase"}},
            {"strict_wait": True, "execution_preferences": {"strict_wait": True}},
        ],
    )
    def test_identical_duplicate_aliases_are_accepted_across_sections(
        self,
        tmp_path: Path,
        raw: dict[str, object],
    ) -> None:
        _load_raw_config(tmp_path, raw)

    @pytest.mark.parametrize(
        "raw",
        [
            {"review_cadence": "dense", "execution": {"review_cadence": "sparse"}},
            {"commit_docs": True, "planning": {"commit_docs": False}},
            {"research": True, "workflow": {"research": False}},
            {"branching_strategy": "none", "git": {"branching_strategy": "per-phase"}},
            {"strict_wait": True, "execution_preferences": {"strict_wait": False}},
        ],
    )
    def test_conflicting_duplicate_aliases_raise_for_all_nested_alias_sections(
        self,
        tmp_path: Path,
        raw: dict[str, object],
    ) -> None:
        with pytest.raises(ConfigError, match="Conflicting duplicate config aliases"):
            _load_raw_config(tmp_path, raw)

    @pytest.mark.parametrize(
        ("raw", "unsupported_key"),
        [
            ({"parallelization": {}}, "parallelization"),
            ({"parallelization": {"x": True}}, "parallelization.x"),
            ({"execution": {"unknown": True}}, "execution.unknown"),
            ({"git": {"unknown": True}}, "git.unknown"),
        ],
    )
    def test_unsupported_nested_schema_keys_stay_rejected(
        self,
        tmp_path: Path,
        raw: dict[str, object],
        unsupported_key: str,
    ) -> None:
        with pytest.raises(ConfigError, match=rf"Unsupported config\.json keys: `{re.escape(unsupported_key)}`"):
            _load_raw_config(tmp_path, raw)

    def test_effective_model_overrides_are_copy_isolated(self) -> None:
        runtime_name = _RUNTIME_DESCRIPTORS[0].runtime_name
        cfg = GPDProjectConfig(model_overrides={runtime_name: {"tier-1": "runtime-tier-1-model"}})

        found, value = effective_config_value(cfg, "model_overrides")
        assert found is True
        assert value == {runtime_name: {"tier-1": "runtime-tier-1-model"}}
        assert value is not cfg.model_overrides

        assert isinstance(value, dict)
        value[runtime_name]["tier-1"] = "mutated-model"

        assert cfg.model_overrides == {runtime_name: {"tier-1": "runtime-tier-1-model"}}


# ─── Dense cadence forces first-result gate ────────────────────────────────────


class TestDenseCadenceForcesFirstResultGate:
    def test_dense_cadence_with_disabled_gate_rejects_config(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "review_cadence": "dense",
                    "checkpoint_after_first_load_bearing_result": False,
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(
            ConfigError,
            match=r"review_cadence=dense requires checkpoint_after_first_load_bearing_result=true",
        ):
            load_config(tmp_path)

    def test_apply_config_update_rejects_dense_with_disabled_first_result_gate(
        self,
    ) -> None:
        """Write-path: setting checkpoint_after_first_load_bearing_result=False
        on a dense config must fail through apply_config_update, not only
        through load_config."""
        raw: dict[str, object] = {"review_cadence": "dense"}
        with pytest.raises(
            ConfigError,
            match=r"review_cadence=dense requires checkpoint_after_first_load_bearing_result=true",
        ):
            apply_config_update(raw, "checkpoint_after_first_load_bearing_result", False)

    def test_apply_config_update_rejects_dense_cadence_on_disabled_gate_config(
        self,
    ) -> None:
        """Inverse of the above: setting review_cadence=dense on a config
        that already has first-result gate disabled must also fail."""
        raw: dict[str, object] = {"checkpoint_after_first_load_bearing_result": False}
        with pytest.raises(
            ConfigError,
            match=r"review_cadence=dense requires checkpoint_after_first_load_bearing_result=true",
        ):
            apply_config_update(raw, "review_cadence", "dense")

    def test_dense_cadence_with_enabled_gate_loads_cleanly(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "review_cadence": "dense",
                    "checkpoint_after_first_load_bearing_result": True,
                }
            ),
            encoding="utf-8",
        )

        cfg = load_config(tmp_path)

        assert cfg.review_cadence == ReviewCadence.DENSE
        assert cfg.checkpoint_after_first_load_bearing_result is True

    def test_non_dense_cadence_permits_disabled_gate(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "review_cadence": "adaptive",
                    "checkpoint_after_first_load_bearing_result": False,
                }
            ),
            encoding="utf-8",
        )

        cfg = load_config(tmp_path)

        assert cfg.review_cadence == ReviewCadence.ADAPTIVE
        assert cfg.checkpoint_after_first_load_bearing_result is False


# ─── load_config ────────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path: Path):
        cfg = load_config(tmp_path)
        assert cfg == GPDProjectConfig()

    def test_empty_object(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text("{}", encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg.model_profile == ModelProfile.REVIEW

    def test_custom_values(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "model_profile": "deep-theory",
                    "autonomy": "yolo",
                    "review_cadence": "dense",
                    "research_mode": "explore",
                    "commit_docs": False,
                    "execution": {
                        "project_usd_budget": 12.5,
                        "session_usd_budget": 2.25,
                    },
                }
            ),
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        assert cfg.model_profile == ModelProfile.DEEP_THEORY
        assert cfg.autonomy == AutonomyMode.YOLO
        assert cfg.review_cadence == ReviewCadence.DENSE
        assert cfg.research_mode == ResearchMode.EXPLORE
        assert cfg.commit_docs is False
        assert cfg.project_usd_budget == 12.5
        assert cfg.session_usd_budget == 2.25

    @pytest.mark.parametrize(
        "invalid_value",
        ["manual", "guided", "autonomous"],
    )
    def test_invalid_autonomy_values_raise_config_error(
        self,
        tmp_path: Path,
        invalid_value: str,
    ) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(json.dumps({"autonomy": invalid_value}), encoding="utf-8")

        with pytest.raises(ConfigError, match="Invalid config.json values"):
            load_config(tmp_path)

    @pytest.mark.parametrize("invalid_budget", [0, -1, -0.5])
    def test_invalid_budget_values_raise_config_error(
        self,
        tmp_path: Path,
        invalid_budget: float,
    ) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"execution": {"project_usd_budget": invalid_budget}}), encoding="utf-8"
        )

        with pytest.raises(ConfigError, match="Invalid config.json values"):
            load_config(tmp_path)

    def test_nested_section_fallback(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
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
            ),
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        assert cfg.commit_docs is False
        assert cfg.review_cadence == ReviewCadence.SPARSE
        assert cfg.max_unattended_minutes_per_plan == 30
        assert cfg.checkpoint_after_n_tasks == 2
        assert cfg.branching_strategy == BranchingStrategy.PER_PHASE
        assert cfg.research is False
        assert cfg.verifier is False

    @pytest.mark.parametrize(
        "section",
        ["git", "execution", "execution_preferences", "planning", "workflow"],
    )
    @pytest.mark.parametrize("invalid_value", ["not-an-object", ["not-an-object"]])
    def test_known_nested_sections_must_be_objects(
        self,
        tmp_path: Path,
        section: str,
        invalid_value: object,
    ) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({section: invalid_value}),
            encoding="utf-8",
        )

        with pytest.raises(
            ConfigError,
            match=rf"Invalid config\.json section types: `{section}` must be a JSON object",
        ):
            load_config(tmp_path)

    def test_execution_preferences_string_booleans_use_model_validation(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "strict_wait": "false",
                    "execution_preferences": {
                        "never_interrupt_running_workers": "true",
                        "never_auto_close_child_agents": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        cfg = load_config(tmp_path)

        assert cfg.execution_preferences.strict_wait is False
        assert cfg.execution_preferences.never_interrupt_running_workers is True
        assert cfg.execution_preferences.never_auto_close_child_agents is False

    def test_execution_preferences_invalid_boolean_string_raises_config_error(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"execution_preferences": {"strict_wait": "definitely"}}),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="Invalid config.json values"):
            load_config(tmp_path)

    def test_identical_root_and_nested_aliases_are_accepted(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "review_cadence": "sparse",
                    "execution": {"review_cadence": "sparse"},
                    "commit_docs": False,
                    "planning": {"commit_docs": False},
                }
            ),
            encoding="utf-8",
        )

        cfg = load_config(tmp_path)

        assert cfg.review_cadence == ReviewCadence.SPARSE
        assert cfg.commit_docs is False

    def test_conflicting_root_and_nested_aliases_raise_config_error(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "review_cadence": "dense",
                    "execution": {"review_cadence": "sparse"},
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match="Conflicting duplicate config aliases"):
            load_config(tmp_path)

    def test_gitignored_planning_dir_forces_commit_docs_false(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(json.dumps({"commit_docs": True}), encoding="utf-8")
        monkeypatch.setattr("gpd.core.config._planning_dir_is_gitignored", lambda _: True)

        cfg = load_config(tmp_path)

        assert cfg.commit_docs is False

    def test_malformed_json_raises(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text("{bad json", encoding="utf-8")
        with pytest.raises(ConfigError, match="Malformed config.json"):
            load_config(tmp_path)

    def test_physics_section_is_rejected_by_current_config_schema(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"physics": {"unit_system": "natural"}}),
            encoding="utf-8",
        )

        with pytest.raises(ConfigError, match=r"Unsupported config\.json keys: `physics`"):
            load_config(tmp_path)

    def test_model_overrides(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        overrides = {
            descriptor.runtime_name: {"tier-1": f"{descriptor.runtime_name}-tier-1"}
            for descriptor in _RUNTIME_DESCRIPTORS
        }
        (tmp_path / "GPD" / "config.json").write_text(json.dumps({"model_overrides": overrides}), encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg.model_overrides == overrides

    def test_model_overrides_preserve_runtime_native_model_strings(self, tmp_path: Path) -> None:
        runtime_name = _RUNTIME_DESCRIPTORS[0].runtime_name
        exact_model = "Provider/OpenAI:GPT-5[Reasoning=High]"
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"model_overrides": {runtime_name: {"tier-1": exact_model}}}),
            encoding="utf-8",
        )

        cfg = load_config(tmp_path)

        assert cfg.model_overrides == {runtime_name: {"tier-1": exact_model}}

    def test_invalid_model_overrides_runtime_raises(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"model_overrides": {"unknown-runtime": {"tier-1": "foo"}}}), encoding="utf-8"
        )
        with pytest.raises(ConfigError, match="model_overrides contains unknown runtime"):
            load_config(tmp_path)

    def test_invalid_model_overrides_tier_raises(self, tmp_path: Path):
        runtime_name = _RUNTIME_DESCRIPTORS[0].runtime_name
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"model_overrides": {runtime_name: {"tier-x": "foo"}}}), encoding="utf-8"
        )
        expected_match = re.escape(f"model_overrides['{runtime_name}'] contains unknown tier")
        with pytest.raises(ConfigError, match=expected_match):
            load_config(tmp_path)

    def test_model_overrides_runtime_lookup_failure_raises_config_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        runtime_name = _RUNTIME_DESCRIPTORS[0].runtime_name
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"model_overrides": {runtime_name: {"tier-1": "gpt-5.4"}}}), encoding="utf-8"
        )

        _valid_runtime_names.cache_clear()

        def _raise_runtime_lookup_failure() -> list[str]:
            raise FileNotFoundError("runtime catalog missing")

        monkeypatch.setattr("gpd.adapters.runtime_catalog.list_runtime_names", _raise_runtime_lookup_failure)

        with pytest.raises(ConfigError, match="Unable to resolve supported runtimes"):
            load_config(tmp_path)

        _valid_runtime_names.cache_clear()

    def test_model_overrides_accept_runtime_display_name_and_normalize_to_canonical_id(self, tmp_path: Path) -> None:
        descriptor = next(
            descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.display_name != descriptor.runtime_name
        )
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"model_overrides": {descriptor.display_name: {"tier-1": "gpt-5.4"}}}),
            encoding="utf-8",
        )

        cfg = load_config(tmp_path)

        assert cfg.model_overrides == {descriptor.runtime_name: {"tier-1": "gpt-5.4"}}

    def test_model_overrides_reject_duplicate_canonical_and_display_runtime_entries(self, tmp_path: Path) -> None:
        descriptor = next(
            descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.display_name != descriptor.runtime_name
        )
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "model_overrides": {
                        descriptor.runtime_name: {"tier-1": "canonical-model"},
                        descriptor.display_name: {"tier-2": "display-model"},
                    }
                }
            ),
            encoding="utf-8",
        )

        expected_match = re.escape(
            f"model_overrides contains duplicate runtime entries for '{descriptor.runtime_name}'"
        )
        with pytest.raises(ConfigError, match=expected_match):
            load_config(tmp_path)


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

    def test_unknown_profile_fails_closed(self):
        with pytest.raises(ConfigError, match="Unknown model profile 'nonexistent'"):
            resolve_agent_tier("gpd-planner", "nonexistent")

    def test_registry_only_agent_without_model_profile_mapping_fails_closed(self, monkeypatch: pytest.MonkeyPatch):
        import gpd.registry as content_registry

        monkeypatch.setattr(content_registry, "list_agents", lambda: ["gpd-registry-only"])

        with pytest.raises(ConfigError, match="No model tier mapping configured for agent 'gpd-registry-only'"):
            resolve_agent_tier("gpd-registry-only", "review")

    def test_missing_agent_profile_mapping_fails_closed(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setitem(MODEL_PROFILES["gpd-planner"], ModelProfile.REVIEW.value, None)

        with pytest.raises(ConfigError, match=r"MODEL_PROFILES\['gpd-planner'\]\['review'\] must be a ModelTier"):
            resolve_agent_tier("gpd-planner", ModelProfile.REVIEW)

    def test_registry_import_failure_falls_back_to_default_agent_names(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        original_import = builtins.__import__

        def _missing_registry(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "gpd.registry":
                raise ModuleNotFoundError("No module named 'gpd.registry'")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _missing_registry)

        tier = resolve_agent_tier("gpd-planner", "review")

        assert tier == ModelTier.TIER_1

    def test_registry_runtime_failure_surfaces_config_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import gpd.registry as content_registry

        monkeypatch.setattr(
            content_registry, "list_agents", lambda: (_ for _ in ()).throw(RuntimeError("registry boom"))
        )

        with pytest.raises(ConfigError, match="Unable to resolve known agent names from registry"):
            resolve_agent_tier("gpd-planner", "review")


# ─── resolve_model ──────────────────────────────────────────────────────────────


class TestResolveModel:
    def test_default_config(self, tmp_path: Path):
        model = resolve_model(tmp_path, "gpd-planner")
        assert model is None

    @pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
    def test_with_runtime_specific_override(self, tmp_path: Path, descriptor) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "model_overrides": {
                        runtime_descriptor.runtime_name: {"tier-1": f"{runtime_descriptor.runtime_name}-tier-1"}
                        for runtime_descriptor in _RUNTIME_DESCRIPTORS
                    },
                }
            ),
            encoding="utf-8",
        )
        model = resolve_model(tmp_path, "gpd-planner", runtime=descriptor.runtime_name)
        assert model == f"{descriptor.runtime_name}-tier-1"

    @pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
    def test_without_override_for_active_runtime_returns_none(self, tmp_path: Path, descriptor) -> None:
        foreign_descriptor = next(
            candidate for candidate in _RUNTIME_DESCRIPTORS if candidate.runtime_name != descriptor.runtime_name
        )
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps(
                {
                    "model_overrides": {
                        foreign_descriptor.runtime_name: {"tier-1": f"{foreign_descriptor.runtime_name}-tier-1"}
                    }
                }
            ),
            encoding="utf-8",
        )
        model = resolve_model(tmp_path, "gpd-planner", runtime=descriptor.runtime_name)
        assert model is None

    def test_unknown_runtime_argument_raises_config_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Unknown runtime 'not-a-runtime'"):
            resolve_model(tmp_path, "gpd-planner", runtime="not-a-runtime")

    @pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
    def test_normalizes_runtime_display_names_before_override_lookup(self, tmp_path: Path, descriptor) -> None:
        display_name = descriptor.display_name
        if display_name == descriptor.runtime_name:
            pytest.skip(f"{descriptor.runtime_name} has no distinct display name")

        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(
            json.dumps({"model_overrides": {descriptor.runtime_name: {"tier-1": f"{descriptor.runtime_name}-tier-1"}}}),
            encoding="utf-8",
        )

        model = resolve_model(tmp_path, "gpd-planner", runtime=display_name)

        assert model == f"{descriptor.runtime_name}-tier-1"


class TestResolveTier:
    def test_project_resolve_tier_uses_profile(self, tmp_path: Path):
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text(json.dumps({"model_profile": "paper-writing"}), encoding="utf-8")
        tier = resolve_tier(tmp_path, "gpd-project-researcher")
        assert tier == ModelTier.TIER_3

    def test_phase_researcher_resolve_tier_defaults_to_tier_2(self, tmp_path: Path) -> None:
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "config.json").write_text("{}", encoding="utf-8")

        tier = resolve_tier(tmp_path, "gpd-phase-researcher")

        assert tier == ModelTier.TIER_2

    def test_project_researcher_agent_tier_tracks_profile_specific_overrides(self) -> None:
        assert resolve_agent_tier("gpd-project-researcher", ModelProfile.REVIEW) == ModelTier.TIER_2
        assert resolve_agent_tier("gpd-project-researcher", ModelProfile.PAPER_WRITING) == ModelTier.TIER_3

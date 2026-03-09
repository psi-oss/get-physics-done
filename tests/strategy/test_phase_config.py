"""Tests for gpd.strategy.phase_config — phase detection + PhaseConfigProvider."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from gpd.strategy.phase_config import (
    DEFAULT_PHASE_CONFIGS,
    PHASE_DERIVATION,
    PHASE_FORMULATION,
    PHASE_VALIDATION,
    PhaseConfig,
    PhaseConfigProvider,
    detect_phase,
    load_phase_configs,
    load_phase_configs_from_yaml,
)

# ---------------------------------------------------------------------------
# PhaseConfig dataclass
# ---------------------------------------------------------------------------


class TestPhaseConfig:
    def test_defaults(self):
        cfg = PhaseConfig()
        assert cfg.c_puct == 1.2
        assert cfg.prior_multipliers == {}
        assert cfg.bundle_period == 10
        assert cfg.verification_threshold == 0.5
        assert cfg.compaction_enabled is False

    def test_frozen(self):
        cfg = PhaseConfig()
        with pytest.raises(AttributeError):
            cfg.c_puct = 5.0  # type: ignore[misc]

    def test_custom_values(self):
        cfg = PhaseConfig(c_puct=3.0, bundle_period=20, compaction_enabled=True)
        assert cfg.c_puct == 3.0
        assert cfg.bundle_period == 20
        assert cfg.compaction_enabled is True


# ---------------------------------------------------------------------------
# DEFAULT_PHASE_CONFIGS
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_all_three_phases_present(self):
        assert set(DEFAULT_PHASE_CONFIGS) == {
            PHASE_FORMULATION,
            PHASE_DERIVATION,
            PHASE_VALIDATION,
        }

    def test_formulation_has_high_cpuct(self):
        assert DEFAULT_PHASE_CONFIGS[PHASE_FORMULATION].c_puct > DEFAULT_PHASE_CONFIGS[PHASE_DERIVATION].c_puct

    def test_validation_has_low_cpuct(self):
        assert DEFAULT_PHASE_CONFIGS[PHASE_VALIDATION].c_puct < DEFAULT_PHASE_CONFIGS[PHASE_DERIVATION].c_puct

    def test_validation_has_compaction(self):
        assert DEFAULT_PHASE_CONFIGS[PHASE_VALIDATION].compaction_enabled is True

    def test_formulation_and_derivation_no_compaction(self):
        assert DEFAULT_PHASE_CONFIGS[PHASE_FORMULATION].compaction_enabled is False
        assert DEFAULT_PHASE_CONFIGS[PHASE_DERIVATION].compaction_enabled is False


# ---------------------------------------------------------------------------
# detect_phase
# ---------------------------------------------------------------------------


class TestDetectPhase:
    def test_formulation_early(self):
        stats = {"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 3}
        assert detect_phase(stats) == PHASE_FORMULATION

    def test_derivation_mid(self):
        stats = {"budget_fraction_remaining": 0.5, "avg_score": 0.3, "node_count": 20}
        assert detect_phase(stats) == PHASE_DERIVATION

    def test_validation_low_budget(self):
        stats = {"budget_fraction_remaining": 0.2, "avg_score": 0.3, "node_count": 50}
        assert detect_phase(stats) == PHASE_VALIDATION

    def test_validation_high_score(self):
        stats = {"budget_fraction_remaining": 0.5, "avg_score": 0.7, "node_count": 30}
        assert detect_phase(stats) == PHASE_VALIDATION

    def test_empty_stats_returns_formulation(self):
        assert detect_phase({}) == PHASE_FORMULATION

    def test_boundary_budget_0_7_node_10(self):
        """budget=0.7, node_count=10 — not early (node_count >= 10), not late, mid score."""
        stats = {"budget_fraction_remaining": 0.7, "avg_score": 0.3, "node_count": 10}
        assert detect_phase(stats) == PHASE_DERIVATION

    def test_boundary_budget_0_3_exact(self):
        """budget=0.3 boundary — exactly 0.3 keeps derivation (< 0.3 needed for validation)."""
        stats = {"budget_fraction_remaining": 0.3, "avg_score": 0.4, "node_count": 20}
        assert detect_phase(stats) == PHASE_DERIVATION


# ---------------------------------------------------------------------------
# load_phase_configs_from_yaml
# ---------------------------------------------------------------------------


class TestLoadYaml:
    def test_valid_yaml(self, tmp_path: Path):
        yaml_file = tmp_path / "phases.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "formulation": {"c_puct": 5.0, "bundle_period": 3},
                    "derivation": {"verification_threshold": 0.9},
                }
            )
        )
        configs = load_phase_configs_from_yaml(yaml_file)
        assert configs["formulation"].c_puct == 5.0
        assert configs["formulation"].bundle_period == 3
        assert configs["derivation"].verification_threshold == 0.9

    def test_unknown_phase_skipped(self, tmp_path: Path):
        yaml_file = tmp_path / "phases.yaml"
        yaml_file.write_text(yaml.dump({"formulation": {"c_puct": 1.0}, "mystery": {"c_puct": 9.9}}))
        configs = load_phase_configs_from_yaml(yaml_file)
        assert "mystery" not in configs
        assert "formulation" in configs

    def test_non_mapping_raises(self, tmp_path: Path):
        yaml_file = tmp_path / "phases.yaml"
        yaml_file.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="Expected YAML mapping"):
            load_phase_configs_from_yaml(yaml_file)

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_phase_configs_from_yaml(tmp_path / "nonexistent.yaml")

    def test_malformed_yaml(self, tmp_path: Path):
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(":\n  - :\n    {bad")
        with pytest.raises(yaml.YAMLError):
            load_phase_configs_from_yaml(yaml_file)

    def test_invalid_phase_entry_skipped(self, tmp_path: Path):
        yaml_file = tmp_path / "phases.yaml"
        yaml_file.write_text(yaml.dump({"formulation": "not_a_dict", "derivation": {"c_puct": 2.0}}))
        configs = load_phase_configs_from_yaml(yaml_file)
        assert "formulation" not in configs
        assert "derivation" in configs

    def test_prior_multipliers_parsed(self, tmp_path: Path):
        yaml_file = tmp_path / "phases.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "validation": {
                        "prior_multipliers": {"Work": 2.0, "Plan": 0.5},
                    }
                }
            )
        )
        configs = load_phase_configs_from_yaml(yaml_file)
        assert configs["validation"].prior_multipliers == {"Work": 2.0, "Plan": 0.5}


# ---------------------------------------------------------------------------
# load_phase_configs (merged)
# ---------------------------------------------------------------------------


class TestLoadPhaseConfigs:
    def test_defaults_without_files(self):
        configs = load_phase_configs(project_dir=None)
        assert set(configs) >= {PHASE_FORMULATION, PHASE_DERIVATION, PHASE_VALIDATION}

    def test_project_override(self, tmp_path: Path):
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "phase_config.yaml").write_text(yaml.dump({"derivation": {"c_puct": 99.0}}))
        configs = load_phase_configs(project_dir=tmp_path)
        assert configs["derivation"].c_puct == 99.0
        # Other phases unaffected
        assert configs["formulation"].c_puct == DEFAULT_PHASE_CONFIGS["formulation"].c_puct


# ---------------------------------------------------------------------------
# PhaseConfigProvider
# ---------------------------------------------------------------------------


class TestPhaseConfigProvider:
    def test_first_call_returns_overrides(self):
        provider = PhaseConfigProvider()
        stats = {"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 2}
        result = provider.get_overrides(stats)
        assert result is not None
        assert "c_puct" in result
        assert "prior_multipliers" in result

    def test_same_phase_returns_none(self):
        provider = PhaseConfigProvider()
        stats = {"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 2}
        provider.get_overrides(stats)
        result = provider.get_overrides(stats)
        assert result is None

    def test_phase_transition_returns_new_overrides(self):
        provider = PhaseConfigProvider()
        early = {"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 2}
        late = {"budget_fraction_remaining": 0.1, "avg_score": 0.8, "node_count": 100}

        result1 = provider.get_overrides(early)
        assert result1 is not None
        assert provider.last_phase == PHASE_FORMULATION

        result2 = provider.get_overrides(late)
        assert result2 is not None
        assert provider.last_phase == PHASE_VALIDATION

    def test_custom_configs(self):
        custom = {
            PHASE_FORMULATION: PhaseConfig(c_puct=10.0),
        }
        provider = PhaseConfigProvider(phase_configs=custom)
        stats = {"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 2}
        result = provider.get_overrides(stats)
        assert result is not None
        assert result["c_puct"] == 10.0

    def test_missing_phase_config_returns_none(self):
        provider = PhaseConfigProvider(phase_configs={})
        stats = {"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 2}
        result = provider.get_overrides(stats)
        assert result is None

    def test_configs_property_returns_copy(self):
        provider = PhaseConfigProvider()
        configs = provider.configs
        assert isinstance(configs, dict)
        configs["injected"] = PhaseConfig()  # type: ignore[assignment]
        assert "injected" not in provider.configs

    def test_last_phase_initially_none(self):
        provider = PhaseConfigProvider()
        assert provider.last_phase is None

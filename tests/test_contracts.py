"""Tests for gpd.contracts — Pydantic models ConventionLock and GPDConfig."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from gpd.contracts import ConventionLock, GPDConfig


# ---------------------------------------------------------------------------
# ConventionLock
# ---------------------------------------------------------------------------


class TestConventionLock:
    def test_empty_construction(self):
        lock = ConventionLock()
        assert lock.metric_signature is None
        assert lock.custom_conventions == {}

    def test_all_fields_none_by_default(self):
        lock = ConventionLock()
        physics_fields = [f for f in ConventionLock.model_fields if f != "custom_conventions"]
        for field_name in physics_fields:
            assert getattr(lock, field_name) is None, f"{field_name} should default to None"

    def test_set_physics_fields(self):
        lock = ConventionLock(
            metric_signature="(-, +, +, +)",
            fourier_convention="physics",
            natural_units="c = hbar = 1",
            gauge_choice="Lorenz",
        )
        assert lock.metric_signature == "(-, +, +, +)"
        assert lock.fourier_convention == "physics"
        assert lock.natural_units == "c = hbar = 1"
        assert lock.gauge_choice == "Lorenz"

    def test_custom_conventions(self):
        lock = ConventionLock(custom_conventions={"my_key": "my_val", "other": "stuff"})
        assert lock.custom_conventions == {"my_key": "my_val", "other": "stuff"}

    def test_json_roundtrip(self):
        lock = ConventionLock(
            metric_signature="(+, -, -, -)",
            coordinate_system="spherical",
            custom_conventions={"foo": "bar"},
        )
        data = json.loads(lock.model_dump_json())
        restored = ConventionLock.model_validate(data)
        assert restored == lock

    def test_dict_roundtrip(self):
        lock = ConventionLock(spin_basis="helicity", levi_civita_sign="+1")
        d = lock.model_dump()
        restored = ConventionLock.model_validate(d)
        assert restored == lock

    def test_model_dump_excludes_none(self):
        lock = ConventionLock(metric_signature="(-, +, +, +)")
        d = lock.model_dump(exclude_none=True)
        assert "metric_signature" in d
        assert "fourier_convention" not in d

    def test_has_18_physics_fields(self):
        lock = ConventionLock()
        physics_fields = [f for f in ConventionLock.model_fields if f != "custom_conventions"]
        assert len(physics_fields) == 18

    def test_extra_fields_forbidden(self):
        """ConventionLock uses default Pydantic behavior — extra fields are ignored."""
        # Pydantic v2 default is to ignore extra fields (no error)
        lock = ConventionLock.model_validate({"metric_signature": "+---", "bogus_field": "hi"})
        assert lock.metric_signature == "+---"
        assert not hasattr(lock, "bogus_field")

    def test_from_empty_dict(self):
        lock = ConventionLock.model_validate({})
        assert lock.metric_signature is None
        assert lock.custom_conventions == {}

    def test_custom_conventions_must_be_dict(self):
        with pytest.raises(ValidationError):
            ConventionLock.model_validate({"custom_conventions": "not a dict"})


# ---------------------------------------------------------------------------
# GPDConfig
# ---------------------------------------------------------------------------


class TestGPDConfig:
    def test_defaults(self):
        cfg = GPDConfig()
        assert cfg.enabled is False
        assert cfg.conventions_enabled is True
        assert cfg.verification_enabled is True
        assert cfg.protocols_enabled is True
        assert cfg.errors_enabled is True
        assert cfg.patterns_enabled is True
        assert cfg.bundle == "default"
        assert cfg.bundle_overlays == ["physics"]

    def test_enabled_override(self):
        cfg = GPDConfig(enabled=True)
        assert cfg.enabled is True

    def test_disable_components(self):
        cfg = GPDConfig(
            enabled=True,
            conventions_enabled=False,
            verification_enabled=False,
        )
        assert cfg.conventions_enabled is False
        assert cfg.verification_enabled is False
        # Others still at defaults
        assert cfg.protocols_enabled is True

    def test_custom_bundle_overlays(self):
        cfg = GPDConfig(bundle_overlays=["physics", "astro"])
        assert cfg.bundle_overlays == ["physics", "astro"]

    def test_empty_overlays(self):
        cfg = GPDConfig(bundle_overlays=[])
        assert cfg.bundle_overlays == []

    def test_json_roundtrip(self):
        cfg = GPDConfig(enabled=True, bundle="custom", bundle_overlays=["a", "b"])
        data = json.loads(cfg.model_dump_json())
        restored = GPDConfig.model_validate(data)
        assert restored == cfg

    def test_dict_roundtrip(self):
        cfg = GPDConfig(enabled=True, patterns_enabled=False)
        restored = GPDConfig.model_validate(cfg.model_dump())
        assert restored == cfg

    def test_from_empty_dict(self):
        cfg = GPDConfig.model_validate({})
        assert cfg.enabled is False
        assert cfg.bundle == "default"

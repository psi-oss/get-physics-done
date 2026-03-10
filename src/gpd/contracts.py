"""GPD contracts -- shared data types for convention locks and configuration.

Defines the core Pydantic models used across GPD for physics convention
locking (metric signature, Fourier convention, units, etc.) and
top-level project configuration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConventionLock(BaseModel):
    metric_signature: str | None = None
    fourier_convention: str | None = None
    natural_units: str | None = None
    gauge_choice: str | None = None
    regularization_scheme: str | None = None
    renormalization_scheme: str | None = None
    coordinate_system: str | None = None
    spin_basis: str | None = None
    state_normalization: str | None = None
    coupling_convention: str | None = None
    index_positioning: str | None = None
    time_ordering: str | None = None
    commutation_convention: str | None = None
    levi_civita_sign: str | None = None
    generator_normalization: str | None = None
    covariant_derivative_sign: str | None = None
    gamma_matrix_convention: str | None = None
    creation_annihilation_order: str | None = None
    custom_conventions: dict[str, str] = Field(default_factory=dict)


class GPDConfig(BaseModel):
    enabled: bool = False
    conventions_enabled: bool = True
    verification_enabled: bool = True
    protocols_enabled: bool = True
    errors_enabled: bool = True
    patterns_enabled: bool = True
    bundle: str = "default"
    bundle_overlays: list[str] = Field(
        default_factory=lambda: ["physics"],
        description="Domain overlay names merged on top of the base bundle (e.g. ['physics'])",
    )

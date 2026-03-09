"""GPD contracts — types for convention locks, verification, protocols, errors, and configuration.

These types were originally in a shared contracts package but are inlined here so GPD
works standalone without external platform packages.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PhysicsDomainGPD(StrEnum):
    QFT = "qft"
    CONDENSED_MATTER = "condensed_matter"
    STAT_MECH = "stat_mech"
    GR_COSMOLOGY = "gr_cosmology"
    AMO = "amo"
    NUCLEAR_PARTICLE = "nuclear_particle"
    ASTROPHYSICS = "astrophysics"
    MATHEMATICAL_PHYSICS = "mathematical_physics"
    QUANTUM_INFO = "quantum_info"
    SOFT_MATTER = "soft_matter"
    FLUID_PLASMA = "fluid_plasma"
    CLASSICAL_MECHANICS = "classical_mechanics"


class VerificationResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    INCONCLUSIVE = "inconclusive"


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


class VerificationCheck(BaseModel):
    check_id: str
    name: str
    domain: str
    result: VerificationResult
    evidence: str
    confidence: float = Field(ge=0, le=1)


class VerificationReport(BaseModel):
    checks: list[VerificationCheck] = Field(default_factory=list)
    overall_passed: bool = False
    coverage_percent: float = Field(default=0.0, ge=0, le=100)
    gap_analysis: list[str] = Field(default_factory=list)


class PhysicsProtocol(BaseModel):
    name: str
    domain: str
    steps: list[str] = Field(default_factory=list)
    checkpoints: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


class ErrorClass(BaseModel):
    id: int
    name: str
    description: str
    detection_strategy: str
    example: str
    domains: list[str] = Field(default_factory=list)


GPD_MCP_TOOLS: dict[str, str] = {
    "conventions_enabled": "gpd-conventions",
    "verification_enabled": "gpd-verification",
    "protocols_enabled": "gpd-protocols",
    "errors_enabled": "gpd-errors",
    "patterns_enabled": "gpd-patterns",
    "state_enabled": "gpd-state",
    "skills_enabled": "gpd-skills",
}


class GPDConfig(BaseModel):
    enabled: bool = False
    conventions_enabled: bool = True
    verification_enabled: bool = True
    protocols_enabled: bool = True
    errors_enabled: bool = True
    patterns_enabled: bool = True
    state_enabled: bool = True
    skills_enabled: bool = True
    bundle: str = "default"
    bundle_overlays: list[str] = Field(
        default_factory=lambda: ["physics"],
        description="Domain overlay names merged on top of the base bundle (e.g. ['physics'])",
    )

    def enabled_tool_names(self) -> list[str]:
        return [tool_name for flag, tool_name in GPD_MCP_TOOLS.items() if getattr(self, flag, True)]

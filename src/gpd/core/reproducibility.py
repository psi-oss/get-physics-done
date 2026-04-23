"""Machine-readable reproducibility manifest validation primitives."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    ValidationInfo,
    field_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

from gpd.core.kernel import Fail, Pass, RegistryBase
from gpd.core.kernel import run as run_kernel

__all__ = [
    "RequiredPackage",
    "SystemRequirements",
    "InputDataset",
    "GeneratedDataset",
    "ExternalDependency",
    "ExecutionStep",
    "ExpectedNumericalResult",
    "OutputFileExpectation",
    "ResourceRequirement",
    "RandomSeedRecord",
    "PlatformDifference",
    "EnvironmentSpecification",
    "ReproducibilityManifest",
    "ReproducibilityManifestRegistry",
    "ReproducibilityIssue",
    "ReproducibilityValidationResult",
    "build_reproducibility_kernel_verdict",
    "compute_sha256",
    "validate_reproducibility_manifest",
    "verify_output_checksum",
]

_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")
_STRICT_FROZEN_MODEL_CONFIG = ConfigDict(frozen=True, extra="forbid")


class RequiredPackage(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    package: str
    version: str
    purpose: str = ""


class SystemRequirements(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    operating_systems: list[str] = Field(default_factory=list)
    architectures: list[str] = Field(default_factory=list)
    compiler: str = ""
    gpu: str = ""


class InputDataset(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    name: str
    source: str
    version_or_date: str
    download_url: str = ""
    checksum_sha256: str
    license: str = ""
    transformations: str = ""


class GeneratedDataset(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    name: str
    script: str
    parameters: dict[str, str] = Field(default_factory=dict)
    size: str = ""
    checksum_sha256: str


class ExternalDependency(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    resource: str
    access_method: str
    restrictions: str = ""


class ExecutionStep(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    name: str
    command: str
    outputs: list[str] = Field(default_factory=list)
    stochastic: StrictBool = False
    expected_wall_time: str = ""
    parallel_group: str = ""


class ExpectedNumericalResult(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    quantity: str
    expected_value: str
    tolerance: str
    script: str
    figure_or_table: str = ""


class OutputFileExpectation(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    path: str
    description: str = ""
    approximate_size: str = ""
    checksum_sha256: str = ""
    approximate_checksum: StrictBool = False


class ResourceRequirement(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    step: str
    cpu_cores: StrictInt
    memory_gb: StrictFloat
    gpu: str = ""
    wall_time: str = ""
    notes: str = ""

    @field_validator("memory_gb", mode="before")
    @classmethod
    def _normalize_memory_gb(cls, value: object) -> object:
        if isinstance(value, bool) or isinstance(value, str):
            raise ValueError("Input should be a valid number")
        if isinstance(value, int):
            return float(value)
        return value


class RandomSeedRecord(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    computation: str
    seed: str
    purpose: str = ""


class PlatformDifference(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    platform: str
    issue: str
    workaround: str = ""


class EnvironmentSpecification(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    python_version: str
    package_manager: str
    virtual_environment: str = ""
    required_packages: list[RequiredPackage] = Field(default_factory=list)
    lock_file: str = ""
    system_requirements: SystemRequirements = Field(default_factory=SystemRequirements)


class ReproducibilityManifest(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    paper_title: str
    date: str
    contact: str = ""
    environment: EnvironmentSpecification
    input_data: list[InputDataset] = Field(default_factory=list)
    generated_data: list[GeneratedDataset] = Field(default_factory=list)
    external_dependencies: list[ExternalDependency] = Field(default_factory=list)
    execution_steps: list[ExecutionStep] = Field(default_factory=list)
    expected_results: list[ExpectedNumericalResult] = Field(default_factory=list)
    output_files: list[OutputFileExpectation] = Field(default_factory=list)
    resource_requirements: list[ResourceRequirement] = Field(default_factory=list)
    minimum_viable: str = ""
    recommended: str = ""
    random_seeds: list[RandomSeedRecord] = Field(default_factory=list)
    seeding_strategy: str = ""
    known_platform_differences: list[PlatformDifference] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    manifest_created: str = ""
    last_verified: str = ""
    last_verified_platform: str = ""

    @field_validator("paper_title", "date")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field cannot be empty")
        return value

    @field_validator("random_seeds")
    @classmethod
    def _seed_records_reference_stochastic_steps(
        cls,
        value: list[RandomSeedRecord],
        info: ValidationInfo,
    ) -> list[RandomSeedRecord]:
        execution_steps = info.data.get("execution_steps", [])
        stochastic_steps = {
            step.name
            for step in execution_steps
            if isinstance(step, ExecutionStep) and step.stochastic
        }
        unknown_seed_targets = sorted(
            {
                seed.computation
                for seed in value
                if seed.computation not in stochastic_steps
            }
        )
        if unknown_seed_targets:
            formatted = ", ".join(f"'{step_name}'" for step_name in unknown_seed_targets)
            raise ValueError(
                f"seed records reference non-stochastic or unknown execution steps: {formatted}"
            )
        return value


class ReproducibilityIssue(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    severity: str
    field: str
    message: str


class ReproducibilityValidationResult(BaseModel):
    model_config = _STRICT_FROZEN_MODEL_CONFIG

    valid: bool
    issues: list[ReproducibilityIssue] = Field(default_factory=list)
    warnings: list[ReproducibilityIssue] = Field(default_factory=list)
    checksum_coverage_percent: float = 0.0
    stochastic_seed_coverage_percent: float = 100.0
    ready_for_review: bool = False


class ReproducibilityManifestRegistry(RegistryBase):
    """Kernel-compatible registry wrapper for reproducibility manifests."""

    def __init__(
        self,
        manifest: ReproducibilityManifest,
        validation: ReproducibilityValidationResult,
        raw_bytes: bytes,
    ) -> None:
        super().__init__(raw_bytes)
        self.manifest = manifest
        self.validation = validation

    @classmethod
    def from_manifest(
        cls,
        manifest: ReproducibilityManifest,
        validation: ReproducibilityValidationResult,
    ) -> ReproducibilityManifestRegistry:
        payload = manifest.model_dump(mode="json")
        raw_bytes = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return cls(manifest=manifest, validation=validation, raw_bytes=raw_bytes)

    def stats(self) -> dict[str, int]:
        return {
            "input_data": len(self.manifest.input_data),
            "generated_data": len(self.manifest.generated_data),
            "execution_steps": len(self.manifest.execution_steps),
            "expected_results": len(self.manifest.expected_results),
            "output_files": len(self.manifest.output_files),
            "random_seeds": len(self.manifest.random_seeds),
        }


def _format_schema_issue(error: dict[str, object]) -> ReproducibilityIssue:
    """Return one schema-validation issue in reproducibility-result format."""

    location = ".".join(str(part) for part in error.get("loc", ()) if str(part)) or "manifest"
    message = str(error.get("msg", "validation failed")).strip() or "validation failed"
    input_value = error.get("input")

    if message == "Field required":
        detail = f"{location} is required."
    elif "valid dictionary" in message.lower():
        detail = f"{location} must be an object, not {type(input_value).__name__}."
    elif "valid list" in message.lower():
        detail = f"{location} must be an array, not {type(input_value).__name__}."
    else:
        detail = message[0].upper() + message[1:] + ("." if not message.endswith(".") else "")

    return ReproducibilityIssue(
        severity="error",
        field=location,
        message=detail,
    )


def _schema_validation_result(exc: PydanticValidationError) -> ReproducibilityValidationResult:
    """Convert manifest schema errors into a structured validation result."""

    issues: list[ReproducibilityIssue] = []
    seen: set[tuple[str, str]] = set()
    for error in exc.errors():
        issue = _format_schema_issue(error)
        key = (issue.field, issue.message)
        if key in seen:
            continue
        seen.add(key)
        issues.append(issue)
    return ReproducibilityValidationResult(valid=False, issues=issues)


def compute_sha256(path: Path) -> str:
    """Compute a SHA-256 checksum for a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_exact_version(version: str) -> bool:
    stripped = version.strip()
    if not stripped:
        return False
    for token in ("<", ">", "=", "~", "!", "*", "^"):
        if token in stripped:
            return False
    return bool(re.fullmatch(r"[A-Za-z0-9_.+-]+", stripped))


def _has_valid_checksum(checksum: str) -> bool:
    return bool(_CHECKSUM_RE.fullmatch(checksum.strip().lower()))


def _has_approximate_checksum_marker(checksum: str) -> bool:
    return checksum.strip().lower().startswith("approx:")


def verify_output_checksum(path: Path, expected_checksum: str) -> bool:
    """Verify a file against an expected SHA-256 checksum."""
    return compute_sha256(path) == expected_checksum.strip().lower()


def validate_reproducibility_manifest(
    manifest: ReproducibilityManifest | dict,
    *,
    project_root: Path | None = None,
) -> ReproducibilityValidationResult:
    """Validate a structured reproducibility manifest.

    When ``project_root`` is provided, referenced paths (input dataset
    sources, generated dataset scripts, execution step inputs/outputs, output
    file paths) are checked for existence relative to that root, and missing
    targets surface as structured ``ReproducibilityIssue`` entries. This is
    what stops the paper builder from emitting provenance paths like
    ``project-evidence/...`` that point at files nobody will find later.
    """
    if isinstance(manifest, ReproducibilityManifest):
        manifest_obj = manifest
    else:
        if not isinstance(manifest, dict):
            return ReproducibilityValidationResult(
                valid=False,
                issues=[
                    ReproducibilityIssue(
                        severity="error",
                        field="manifest",
                        message="reproducibility manifest must be a JSON object.",
                    )
                ],
            )
        try:
            manifest_obj = ReproducibilityManifest.model_validate(manifest)
        except PydanticValidationError as exc:
            return _schema_validation_result(exc)

    issues: list[ReproducibilityIssue] = []
    warnings: list[ReproducibilityIssue] = []

    env = manifest_obj.environment
    if not env.required_packages:
        issues.append(
            ReproducibilityIssue(
                severity="error",
                field="environment.required_packages",
                message="At least one required package must be pinned.",
            )
        )
    for index, pkg in enumerate(env.required_packages):
        if not _is_exact_version(pkg.version):
            issues.append(
                ReproducibilityIssue(
                    severity="error",
                    field=f"environment.required_packages[{index}].version",
                    message=f"Package '{pkg.package}' is not pinned to an exact version.",
                )
            )
    if not env.lock_file.strip():
        issues.append(
            ReproducibilityIssue(
                severity="error",
                field="environment.lock_file",
                message="A lock file is required for reproducibility.",
            )
        )

    checksum_items = 0
    checksum_ok = 0
    for index, dataset in enumerate(manifest_obj.input_data):
        checksum_items += 1
        if _has_valid_checksum(dataset.checksum_sha256):
            checksum_ok += 1
        else:
            issues.append(
                ReproducibilityIssue(
                    severity="error",
                    field=f"input_data[{index}].checksum_sha256",
                    message=f"Input dataset '{dataset.name}' is missing a valid SHA-256 checksum.",
                )
            )
    for index, dataset in enumerate(manifest_obj.generated_data):
        checksum_items += 1
        if _has_valid_checksum(dataset.checksum_sha256):
            checksum_ok += 1
        else:
            issues.append(
                ReproducibilityIssue(
                    severity="error",
                    field=f"generated_data[{index}].checksum_sha256",
                    message=f"Generated dataset '{dataset.name}' is missing a valid SHA-256 checksum.",
                )
            )
    for index, output_file in enumerate(manifest_obj.output_files):
        checksum_items += 1
        raw_checksum = output_file.checksum_sha256.strip()
        valid_checksum = _has_valid_checksum(raw_checksum)
        approximate_checksum = bool(raw_checksum) and (
            output_file.approximate_checksum or _has_approximate_checksum_marker(raw_checksum)
        )
        if valid_checksum:
            checksum_ok += 1
        elif approximate_checksum:
            warnings.append(
                ReproducibilityIssue(
                    severity="warning",
                    field=f"output_files[{index}].checksum_sha256",
                    message=f"Output file '{output_file.path}' uses an approximate checksum.",
                )
            )
        else:
            issues.append(
                ReproducibilityIssue(
                    severity="error",
                    field=f"output_files[{index}].checksum_sha256",
                    message=f"Output file '{output_file.path}' is missing a valid checksum.",
                )
            )
    checksum_coverage = round((100.0 * checksum_ok / checksum_items), 2) if checksum_items else 0.0

    if not manifest_obj.execution_steps:
        issues.append(
            ReproducibilityIssue(
                severity="error",
                field="execution_steps",
                message="Execution steps are required to reproduce results.",
            )
        )
    if not manifest_obj.expected_results and not manifest_obj.output_files:
        issues.append(
            ReproducibilityIssue(
                severity="error",
                field="expected_results",
                message="Expected results or output files must be provided.",
            )
        )
    if not manifest_obj.resource_requirements:
        warnings.append(
            ReproducibilityIssue(
                severity="warning",
                field="resource_requirements",
                message="Computational resource requirements are not documented.",
            )
        )

    step_names = {step.name for step in manifest_obj.execution_steps}
    resource_steps = {requirement.step for requirement in manifest_obj.resource_requirements}
    missing_requirements = sorted(step_names - resource_steps)
    for step_name in missing_requirements:
        warnings.append(
            ReproducibilityIssue(
                severity="warning",
                field="resource_requirements",
                message=f"No resource requirement recorded for execution step '{step_name}'.",
            )
        )

    stochastic_steps = {step.name for step in manifest_obj.execution_steps if step.stochastic}
    seeded_steps = {seed.computation for seed in manifest_obj.random_seeds}
    covered_stochastic = len(stochastic_steps & seeded_steps)
    seed_coverage = round((100.0 * covered_stochastic / len(stochastic_steps)), 2) if stochastic_steps else 100.0
    if stochastic_steps and not manifest_obj.seeding_strategy.strip():
        issues.append(
            ReproducibilityIssue(
                severity="error",
                field="seeding_strategy",
                message="A seeding strategy is required for stochastic computations.",
            )
        )
    for step_name in sorted(stochastic_steps - seeded_steps):
        issues.append(
            ReproducibilityIssue(
                severity="error",
                field="random_seeds",
                message=f"Missing seed record for stochastic execution step '{step_name}'.",
            )
        )

    if len(manifest_obj.verification_steps) < 3:
        warnings.append(
            ReproducibilityIssue(
                severity="warning",
                field="verification_steps",
                message="Verification steps should include at least a pipeline rerun, numerical comparison, and artifact inspection.",
            )
        )
    if not manifest_obj.minimum_viable.strip():
        warnings.append(
            ReproducibilityIssue(
                severity="warning",
                field="minimum_viable",
                message="Minimum viable resource guidance is missing.",
            )
        )
    if not manifest_obj.recommended.strip():
        warnings.append(
            ReproducibilityIssue(
                severity="warning",
                field="recommended",
                message="Recommended resource guidance is missing.",
            )
        )
    if not manifest_obj.last_verified.strip():
        warnings.append(
            ReproducibilityIssue(
                severity="warning",
                field="last_verified",
                message="Manifest has not recorded a last verified timestamp.",
            )
        )
    if manifest_obj.last_verified.strip() and not manifest_obj.last_verified_platform.strip():
        warnings.append(
            ReproducibilityIssue(
                severity="warning",
                field="last_verified_platform",
                message="Last verified platform should be recorded when last_verified is set.",
            )
        )

    if project_root is not None:
        for index, dataset in enumerate(manifest_obj.input_data):
            if dataset.source.strip() and not (project_root / dataset.source).exists():
                issues.append(
                    ReproducibilityIssue(
                        severity="error",
                        field=f"input_data[{index}].source",
                        message=f"input_data[{index}].source path '{dataset.source}' does not exist under project root.",
                    )
                )
        for index, dataset in enumerate(manifest_obj.generated_data):
            script = getattr(dataset, "script", None)
            if isinstance(script, str) and script.strip() and not (project_root / script).exists():
                issues.append(
                    ReproducibilityIssue(
                        severity="error",
                        field=f"generated_data[{index}].script",
                        message=f"generated_data[{index}].script path '{script}' does not exist under project root.",
                    )
                )
        for step_index, step in enumerate(manifest_obj.execution_steps):
            for output_index, output_path in enumerate(getattr(step, "outputs", []) or []):
                if isinstance(output_path, str) and output_path.strip() and not (project_root / output_path).exists():
                    issues.append(
                        ReproducibilityIssue(
                            severity="error",
                            field=f"execution_steps[{step_index}].outputs[{output_index}]",
                            message=(
                                f"execution step output '{output_path}' does not exist under project root."
                            ),
                        )
                    )
        for index, output_file in enumerate(manifest_obj.output_files):
            if output_file.path.strip() and not (project_root / output_file.path).exists():
                issues.append(
                    ReproducibilityIssue(
                        severity="error",
                        field=f"output_files[{index}].path",
                        message=f"output_files[{index}].path '{output_file.path}' does not exist under project root.",
                    )
                )

    valid = len(issues) == 0
    ready = valid and checksum_coverage == 100.0 and seed_coverage == 100.0 and not warnings
    return ReproducibilityValidationResult(
        valid=valid,
        issues=issues,
        warnings=warnings,
        checksum_coverage_percent=checksum_coverage,
        stochastic_seed_coverage_percent=seed_coverage,
        ready_for_review=ready,
    )


def build_reproducibility_kernel_verdict(
    manifest: ReproducibilityManifest,
    *,
    validation: ReproducibilityValidationResult | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a content-addressed kernel verdict for a reproducibility manifest."""
    validation_result = validation or validate_reproducibility_manifest(manifest)
    registry = ReproducibilityManifestRegistry.from_manifest(manifest, validation_result)

    def manifest_valid(reg: RegistryBase) -> object:
        typed = reg
        if not isinstance(typed, ReproducibilityManifestRegistry):
            return Fail("reproducibility manifest registry type mismatch")
        if typed.validation.valid:
            return Pass("manifest passes structural reproducibility validation")
        first_issue = typed.validation.issues[0].message if typed.validation.issues else "manifest is invalid"
        return Fail(first_issue)

    def checksum_coverage_complete(reg: RegistryBase) -> object:
        typed = reg
        if not isinstance(typed, ReproducibilityManifestRegistry):
            return Fail("reproducibility manifest registry type mismatch")
        coverage = typed.validation.checksum_coverage_percent
        if coverage == 100.0:
            return Pass("all declared checksums are covered")
        return Fail(f"checksum coverage is {coverage:.2f}%")

    def stochastic_seed_coverage_complete(reg: RegistryBase) -> object:
        typed = reg
        if not isinstance(typed, ReproducibilityManifestRegistry):
            return Fail("reproducibility manifest registry type mismatch")
        coverage = typed.validation.stochastic_seed_coverage_percent
        if coverage == 100.0:
            return Pass("all stochastic steps have explicit seeds")
        return Fail(f"stochastic seed coverage is {coverage:.2f}%")

    def review_ready_metadata(reg: RegistryBase) -> object:
        typed = reg
        if not isinstance(typed, ReproducibilityManifestRegistry):
            return Fail("reproducibility manifest registry type mismatch")
        if typed.validation.ready_for_review:
            return Pass("manifest is review-ready")
        if typed.validation.warnings:
            return Fail(typed.validation.warnings[0].message)
        return Fail("manifest is not review-ready")

    return run_kernel(
        registry,
        {
            "manifest_valid": manifest_valid,
            "checksum_coverage_complete": checksum_coverage_complete,
            "stochastic_seed_coverage_complete": stochastic_seed_coverage_complete,
            "review_ready_metadata": review_ready_metadata,
        },
        predicates_source=Path(__file__),
        generated_at=generated_at,
    )

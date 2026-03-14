"""Machine-readable reproducibility manifest validation primitives."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

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
    "ReproducibilityIssue",
    "ReproducibilityValidationResult",
    "compute_sha256",
    "validate_reproducibility_manifest",
    "verify_output_checksum",
]

_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")


class RequiredPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    package: str
    version: str
    purpose: str = ""


class SystemRequirements(BaseModel):
    model_config = ConfigDict(frozen=True)

    operating_systems: list[str] = Field(default_factory=list)
    architectures: list[str] = Field(default_factory=list)
    compiler: str = ""
    gpu: str = ""


class InputDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    source: str
    version_or_date: str
    download_url: str = ""
    checksum_sha256: str
    license: str = ""
    transformations: str = ""


class GeneratedDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    script: str
    parameters: dict[str, str] = Field(default_factory=dict)
    size: str = ""
    checksum_sha256: str


class ExternalDependency(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource: str
    access_method: str
    restrictions: str = ""


class ExecutionStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    command: str
    outputs: list[str] = Field(default_factory=list)
    stochastic: bool = False
    expected_wall_time: str = ""
    parallel_group: str = ""


class ExpectedNumericalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    quantity: str
    expected_value: str
    tolerance: str
    script: str
    figure_or_table: str = ""


class OutputFileExpectation(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    description: str = ""
    approximate_size: str = ""
    checksum_sha256: str = ""
    approximate_checksum: bool = False


class ResourceRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: str
    cpu_cores: int
    memory_gb: float
    gpu: str = ""
    wall_time: str = ""
    notes: str = ""


class RandomSeedRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    computation: str
    seed: str
    purpose: str = ""


class PlatformDifference(BaseModel):
    model_config = ConfigDict(frozen=True)

    platform: str
    issue: str
    workaround: str = ""


class EnvironmentSpecification(BaseModel):
    model_config = ConfigDict(frozen=True)

    python_version: str
    package_manager: str
    virtual_environment: str = ""
    required_packages: list[RequiredPackage] = Field(default_factory=list)
    lock_file: str = ""
    system_requirements: SystemRequirements = Field(default_factory=SystemRequirements)


class ReproducibilityManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class ReproducibilityIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: str
    field: str
    message: str


class ReproducibilityValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    issues: list[ReproducibilityIssue] = Field(default_factory=list)
    warnings: list[ReproducibilityIssue] = Field(default_factory=list)
    checksum_coverage_percent: float = 0.0
    stochastic_seed_coverage_percent: float = 100.0
    ready_for_review: bool = False


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


def validate_reproducibility_manifest(manifest: ReproducibilityManifest | dict) -> ReproducibilityValidationResult:
    """Validate a structured reproducibility manifest."""
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
            checksum_ok += 1
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
    checksum_coverage = round((100.0 * checksum_ok / checksum_items), 2) if checksum_items else 100.0

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

    valid = len(issues) == 0
    blocking_warnings = [w for w in warnings if "approximate" not in w.message.lower()]
    ready = valid and checksum_coverage == 100.0 and seed_coverage == 100.0 and not blocking_warnings
    return ReproducibilityValidationResult(
        valid=valid,
        issues=issues,
        warnings=warnings,
        checksum_coverage_percent=checksum_coverage,
        stochastic_seed_coverage_percent=seed_coverage,
        ready_for_review=ready,
    )

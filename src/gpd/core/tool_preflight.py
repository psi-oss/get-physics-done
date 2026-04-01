"""Plan-scoped specialized-tool requirement parsing and preflight helpers."""

from __future__ import annotations

import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from gpd.mcp.managed_integrations import (
    WOLFRAM_MANAGED_INTEGRATION,
    WOLFRAM_MANAGED_SERVER_KEY,
    get_managed_integration,
)

_TOOL_ALIASES = {
    "mathematica": "wolfram",
    "wolfram_language": "wolfram",
    "wolframlanguage": "wolfram",
    "wolframscript": "wolfram",
}
_SUPPORTED_TOOLS = {"wolfram", "command"}


class PlanToolPreflightError(ValueError):
    """Raised when plan tool requirements are malformed."""


class PlanToolRequirement(BaseModel):
    """Machine-checkable specialized tool requirement declared by a plan."""

    model_config = ConfigDict(extra="forbid")

    id: str = ""
    tool: str
    purpose: str
    required: bool = True
    fallback: str = ""
    command: str | None = None

    @field_validator("id", "purpose", "fallback")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("tool")
    @classmethod
    def _normalize_tool(cls, value: str) -> str:
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        normalized = _TOOL_ALIASES.get(normalized, normalized)
        if normalized not in _SUPPORTED_TOOLS:
            supported = ", ".join(sorted(_SUPPORTED_TOOLS | set(_TOOL_ALIASES)))
            raise ValueError(f"tool must be one of: {supported}")
        return normalized

    @field_validator("command")
    @classmethod
    def _normalize_command(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @model_validator(mode="after")
    def _validate_tool_specific_fields(self) -> PlanToolRequirement:
        if not self.id:
            self.id = self.tool
        if not self.purpose:
            raise ValueError("purpose must be a non-empty string")
        if self.tool == "command" and not self.command:
            raise ValueError("command tool requires a non-empty command")
        if self.tool != "command" and self.command is not None:
            raise ValueError("command is only allowed when tool=command")
        return self


class PlanToolCheck(BaseModel):
    """One specialized-tool requirement evaluated against the current machine."""

    model_config = ConfigDict(extra="forbid")

    id: str
    tool: str
    purpose: str
    status: str
    available: bool
    blocking: bool
    detail: str
    provider: str
    fallback: str = ""
    required: bool = True


_TOOL_REQUIREMENTS_ADAPTER = TypeAdapter(list[PlanToolRequirement])


class PlanToolPreflightResult(BaseModel):
    """Summary of specialized-tool readiness for a PLAN.md file."""

    model_config = ConfigDict(extra="forbid")

    plan_path: str
    validation_passed: bool = True
    valid: bool
    passed: bool
    requirements: list[PlanToolCheck] = Field(default_factory=list)
    checks: list[PlanToolCheck] = Field(default_factory=list)
    blocking_conditions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    guidance: str = ""


@dataclass(frozen=True, slots=True)
class _ToolSpec:
    provider: str
    command: str | None
    warning: str = ""


_TOOL_SPECS: dict[str, _ToolSpec] = {
    "wolfram": _ToolSpec(
        provider="wolframscript",
        command="wolframscript",
        warning="Availability is PATH-based or shared-integration config only; live execution and license state are not proven.",
    ),
}

_WOLFRAM_CAVEAT = "Availability is config-level only; live execution and license state are not proven."


def _format_validation_error(exc: PydanticValidationError) -> str:
    messages: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        msg = str(error.get("msg", "invalid value"))
        messages.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(messages) if messages else str(exc)


def parse_plan_tool_requirements(raw: object) -> list[PlanToolRequirement]:
    """Parse optional ``tool_requirements`` frontmatter."""

    if raw is None:
        return []
    if raw == []:
        raise PlanToolPreflightError("must not be empty when present")
    try:
        return _TOOL_REQUIREMENTS_ADAPTER.validate_python(raw)
    except PydanticValidationError as exc:
        raise PlanToolPreflightError(_format_validation_error(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise PlanToolPreflightError(str(exc)) from exc


def _probe_tool(requirement: PlanToolRequirement, *, cwd: Path | None = None) -> tuple[bool, str, str, list[str]]:
    if requirement.tool == "command":
        command = requirement.command or ""
        try:
            argv = shlex.split(command) if command else []
        except ValueError as exc:
            return False, f"could not parse command requirement: {exc}", "command", []
        executable = argv[0] if argv else ""
        path = shutil.which(executable) if executable else None
        if path:
            return True, f"{executable} found at {Path(path).resolve(strict=False)}", "command", []
        return False, f"{executable} not found on PATH", "command", []

    if requirement.tool == "wolfram":
        path = shutil.which("wolframscript")
        warnings = [_WOLFRAM_CAVEAT]
        if path:
            return (
                True,
                f"wolframscript found at {Path(path).resolve(strict=False)}",
                "wolframscript",
                warnings,
            )

        integration = get_managed_integration("wolfram")
        if integration is not None and integration.is_configured(cwd=cwd, strict=True):
            endpoint = integration.resolved_endpoint(cwd=cwd, strict=True)
            return (
                True,
                (
                    "shared Wolfram integration configured via "
                    f"{integration.api_key_env_var} for {endpoint}"
                ),
                WOLFRAM_MANAGED_SERVER_KEY,
                warnings,
            )

        detail = (
            "wolframscript not found on PATH and shared Wolfram integration is not configured "
            f"(missing {WOLFRAM_MANAGED_INTEGRATION.api_key_env_var})"
        )
        return False, detail, WOLFRAM_MANAGED_SERVER_KEY, warnings

    spec = _TOOL_SPECS.get(requirement.tool)
    if spec is None or spec.command is None:
        return False, f"no probe implemented for tool {requirement.tool}", "unknown", []

    path = shutil.which(spec.command)
    warnings = [spec.warning] if spec.warning else []
    if path:
        return True, f"{spec.command} found at {Path(path).resolve(strict=False)}", spec.provider, warnings
    return False, f"{spec.command} not found on PATH", spec.provider, warnings


def build_plan_tool_preflight(
    plan_path: Path,
    *,
    requirements: list[PlanToolRequirement] | None = None,
) -> PlanToolPreflightResult:
    """Return machine-local specialized-tool readiness for a plan."""

    from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter, validate_frontmatter

    resolved_path = plan_path.expanduser().resolve(strict=False)
    if not resolved_path.exists():
        return PlanToolPreflightResult(
            plan_path=str(resolved_path),
            validation_passed=False,
            valid=False,
            passed=False,
            errors=[f"Plan not found: {resolved_path}"],
            guidance=f"Plan not found: {resolved_path}",
        )

    active_requirements = requirements
    if active_requirements is None:
        try:
            content = resolved_path.read_text(encoding="utf-8")
        except OSError as exc:
            return PlanToolPreflightResult(
                plan_path=str(resolved_path),
                validation_passed=False,
                valid=False,
                passed=False,
                errors=[f"Could not read plan: {exc}"],
                guidance=f"Could not read plan: {exc}",
            )

        try:
            meta, _body = extract_frontmatter(content)
        except FrontmatterParseError as exc:
            return PlanToolPreflightResult(
                plan_path=str(resolved_path),
                validation_passed=False,
                valid=False,
                passed=False,
                errors=[f"Could not parse plan frontmatter: {exc}"],
                guidance=f"Could not parse plan frontmatter: {exc}",
            )

        validation = validate_frontmatter(content, "plan", source_path=resolved_path)
        validation_errors = [f"Missing required frontmatter field: {field}" for field in validation.missing]
        validation_errors.extend(validation.errors)
        if validation_errors:
            return PlanToolPreflightResult(
                plan_path=str(resolved_path),
                validation_passed=False,
                valid=False,
                passed=False,
                errors=validation_errors,
                guidance="Fix invalid PLAN frontmatter before specialized-tool preflight can pass.",
            )

        try:
            active_requirements = parse_plan_tool_requirements(meta.get("tool_requirements"))
        except PlanToolPreflightError as exc:
            return PlanToolPreflightResult(
                plan_path=str(resolved_path),
                validation_passed=False,
                valid=False,
                passed=False,
                errors=[f"Invalid tool_requirements: {exc}"],
                guidance=f"Invalid tool_requirements: {exc}",
            )

    if not active_requirements:
        return PlanToolPreflightResult(
            plan_path=str(resolved_path),
            validation_passed=True,
            valid=True,
            passed=True,
            requirements=[],
            checks=[],
            guidance="No machine-checkable specialized tool requirements declared.",
        )

    checks: list[PlanToolCheck] = []
    blocking_conditions: list[str] = []
    warnings: list[str] = []
    blocking_missing = False
    for requirement in active_requirements:
        try:
            available, detail, provider, probe_warnings = _probe_tool(requirement, cwd=resolved_path.parent)
        except RuntimeError as exc:
            available = False
            detail = str(exc)
            provider = WOLFRAM_MANAGED_SERVER_KEY if requirement.tool == "wolfram" else requirement.tool
            probe_warnings = []
        status = "available" if available else "missing"
        check = PlanToolCheck(
            id=requirement.id,
            tool=requirement.tool,
            purpose=requirement.purpose,
            status=status,
            available=available,
            blocking=requirement.required and not available,
            detail=detail,
            provider=provider,
            fallback=requirement.fallback,
            required=requirement.required,
        )
        checks.append(check)
        warnings.extend(probe_warnings)
        if available:
            continue
        if requirement.required:
            blocking_missing = True
            blocking_conditions.append(f"{requirement.id}: {detail}")
            if requirement.fallback:
                warnings.append(
                    f"Required tool {requirement.tool} is unavailable; declared fallback may preserve the scientific intent."
                )
            else:
                warnings.append(
                    f"Required tool {requirement.tool} is unavailable and no fallback is declared."
                )
        elif requirement.fallback:
            warnings.append(
                f"Preferred tool {requirement.tool} is unavailable; use the declared fallback."
            )
        else:
            warnings.append(
                f"Preferred tool {requirement.tool} is unavailable and no fallback is declared."
            )

    missing_preferred_with_fallback = any(
        (not check.available) and (not check.blocking) and bool(check.fallback)
        for check in checks
    )
    missing_preferred_without_fallback = any(
        (not check.available) and (not check.blocking) and not check.fallback
        for check in checks
    )
    guidance = (
        "Install or enable the missing required specialized tools, or revise the plan before execution."
        if blocking_missing
        else (
            "Proceed using declared fallback paths for unavailable preferred tools."
            if missing_preferred_with_fallback
            else (
                "Optional specialized tools are unavailable; continue only if the plan can genuinely proceed without them."
                if missing_preferred_without_fallback
                else "All declared specialized tools are available through local or configured capabilities."
            )
        )
    )
    return PlanToolPreflightResult(
        plan_path=str(resolved_path),
        validation_passed=True,
        valid=True,
        passed=not blocking_missing,
        requirements=checks,
        checks=checks,
        blocking_conditions=blocking_conditions,
        warnings=warnings,
        guidance=guidance,
    )

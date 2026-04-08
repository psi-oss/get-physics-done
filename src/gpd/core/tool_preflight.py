"""Plan-scoped specialized-tool requirement parsing and preflight helpers."""

from __future__ import annotations

import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from gpd.core.root_resolution import resolve_project_root
from gpd.core.utils import normalize_ascii_slug
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
_KNOWLEDGE_GATE_VALUES = {"off", "warn", "block"}


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


class KnowledgeDependencyCheck(BaseModel):
    """One explicit knowledge dependency evaluated against the current project state."""

    model_config = ConfigDict(extra="forbid")

    knowledge_id: str
    status: str
    resolved: bool
    runtime_active: bool
    blocking: bool
    detail: str
    record_path: str | None = None
    successor: str | None = None
    review_fresh: bool | None = None


_TOOL_REQUIREMENTS_ADAPTER = TypeAdapter(list[PlanToolRequirement])


def _validate_unique_tool_requirement_ids(requirements: list[PlanToolRequirement]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for requirement in requirements:
        if requirement.id in seen:
            duplicates.append(requirement.id)
            continue
        seen.add(requirement.id)
    if duplicates:
        duplicate_list = ", ".join(repr(item) for item in duplicates)
        raise PlanToolPreflightError(f"tool_requirements[].id values must be unique; duplicate ids: {duplicate_list}")


class PlanToolPreflightResult(BaseModel):
    """Summary of specialized-tool readiness for a PLAN.md file."""

    model_config = ConfigDict(extra="forbid")

    plan_path: str
    validation_passed: bool = True
    valid: bool
    passed: bool
    knowledge_gate: str = "off"
    knowledge_deps: list[str] = Field(default_factory=list)
    requirements: list[PlanToolCheck] = Field(default_factory=list)
    checks: list[PlanToolCheck] = Field(default_factory=list)
    knowledge_dependency_checks: list[KnowledgeDependencyCheck] = Field(default_factory=list)
    blocking_conditions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    guidance: str = ""


@dataclass(frozen=True, slots=True)
class _ToolSpec:
    provider: str
    command: str | None
    warning: str = ""


@dataclass(frozen=True, slots=True)
class _CommandRunnerPolicy:
    option_flags_with_value: frozenset[str] = frozenset()
    selector_delimiter: str | None = None


@dataclass(frozen=True, slots=True)
class _KnowledgeDependencyEvaluation:
    checks: list[KnowledgeDependencyCheck]
    warnings: list[str]
    blocking_conditions: list[str]
    guidance: str

    @property
    def has_issues(self) -> bool:
        return bool(self.warnings or self.blocking_conditions)


_TOOL_SPECS: dict[str, _ToolSpec] = {
    "wolfram": _ToolSpec(
        provider="wolframscript",
        command="wolframscript",
        warning="Availability is PATH-based or shared-integration config only; live execution and license state are not proven.",
    ),
}

_WOLFRAM_CAVEAT = "Availability is config-level only; live execution and license state are not proven."
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
_PYTHON_LAUNCHER_RE = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|pythonw(?:\d+(?:\.\d+)*)?|pypy(?:\d+(?:\.\d+)*)?|py)(?:\.exe)?$")
_COMMAND_RUNNER_POLICIES: dict[str, _CommandRunnerPolicy] = {
    "uv": _CommandRunnerPolicy(option_flags_with_value=frozenset({"--python", "-p", "--with", "-w", "--from", "--project"})),
    "poetry": _CommandRunnerPolicy(),
    "pipx": _CommandRunnerPolicy(option_flags_with_value=frozenset({"--spec", "--python", "-p", "--index-url", "-i", "--pip-args"})),
    "hatch": _CommandRunnerPolicy(option_flags_with_value=frozenset({"--env", "-e", "--project"}), selector_delimiter=":"),
    "pixi": _CommandRunnerPolicy(option_flags_with_value=frozenset({"--manifest-path", "-m", "--project", "-p", "--cwd", "-C"})),
}
_PYTHON_COMMAND_FLAGS_WITH_VALUES = frozenset({"-W", "-X"})
_ENV_FLAG_WITH_VALUE = {"-u", "-S", "-C"}
_ENV_FLAG_WITHOUT_VALUE = {"-i", "-0", "-v"}
_SHELL_LAUNCHERS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "mksh", "ash"})


def _format_validation_error(exc: PydanticValidationError) -> str:
    messages: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        msg = str(error.get("msg", "invalid value"))
        messages.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(messages) if messages else str(exc)


def _parse_knowledge_gate(raw: object) -> str:
    if raw is None:
        return "off"
    if raw is False:
        return "off"
    if not isinstance(raw, str):
        raise PlanToolPreflightError("knowledge_gate: expected a string")
    gate_value = raw.strip()
    if not gate_value:
        raise PlanToolPreflightError("knowledge_gate: expected a non-empty string")
    if gate_value not in _KNOWLEDGE_GATE_VALUES:
        raise PlanToolPreflightError("knowledge_gate: must be one of off, warn, block")
    return gate_value


def _parse_knowledge_deps(raw: object) -> list[str]:
    if raw is None:
        return []
    if raw == []:
        return []
    if not isinstance(raw, list):
        raise PlanToolPreflightError("knowledge_deps: expected a list")

    dependencies: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str):
            raise PlanToolPreflightError(f"knowledge_deps: entry {index} must be a non-empty string")
        knowledge_id = item.strip()
        if not knowledge_id:
            raise PlanToolPreflightError(f"knowledge_deps: entry {index} must be a non-empty string")
        if (
            not knowledge_id.startswith("K-")
            or not knowledge_id[2:]
            or normalize_ascii_slug(knowledge_id[2:]) != knowledge_id[2:]
        ):
            raise PlanToolPreflightError(
                f"knowledge_deps: entry {index} must use canonical K-{{ascii-hyphen-slug}} format"
            )
        if knowledge_id in seen and knowledge_id not in duplicates:
            duplicates.append(knowledge_id)
        seen.add(knowledge_id)
        dependencies.append(knowledge_id)

    if duplicates:
        joined = ", ".join(duplicates)
        raise PlanToolPreflightError(f"knowledge_deps: duplicate ids are not allowed: {joined}")

    return dependencies


def parse_plan_tool_requirements(raw: object) -> list[PlanToolRequirement]:
    """Parse optional ``tool_requirements`` frontmatter."""

    if raw is None:
        return []
    if raw == []:
        return []
    try:
        requirements = _TOOL_REQUIREMENTS_ADAPTER.validate_python(raw)
        _validate_unique_tool_requirement_ids(requirements)
        return requirements
    except PydanticValidationError as exc:
        raise PlanToolPreflightError(_format_validation_error(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise PlanToolPreflightError(str(exc)) from exc


def _split_command_argv(command: str) -> tuple[list[str] | None, str | None]:
    try:
        return shlex.split(command, posix=True) if command else [], None
    except ValueError as exc:
        return None, f"could not parse command requirement: {exc}"


def _env_wrapped_argv(argv: list[str]) -> tuple[list[str] | None, str | None]:
    index = 1
    while index < len(argv):
        token = argv[index]
        if token == "--":
            index += 1
            break
        if _ENV_ASSIGNMENT_RE.fullmatch(token):
            index += 1
            continue
        if token in _ENV_FLAG_WITHOUT_VALUE:
            index += 1
            continue
        if token in _ENV_FLAG_WITH_VALUE:
            if index + 1 >= len(argv):
                return None, f"env option {token} requires a value"
            if token == "-S":
                return _split_command_argv(argv[index + 1])
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return argv[index:], None

    if index < len(argv):
        return argv[index:], None
    return [argv[0]], None


def _shell_wrapped_command(argv: list[str]) -> str | None:
    if not argv:
        return None
    launcher = Path(argv[0]).name.casefold()
    if launcher not in _SHELL_LAUNCHERS:
        return None

    for index, token in enumerate(argv[1:], start=1):
        if token == "--":
            break
        if token in {"-c", "--command"}:
            if index + 1 < len(argv):
                return argv[index + 1]
            return None
        if token.startswith("-") and "c" in token[1:]:
            if index + 1 < len(argv):
                return argv[index + 1]
            return None
        break
    return None


def _unwrap_command_runner(argv: list[str]) -> tuple[list[str] | None, str | None]:
    if len(argv) < 2:
        return argv, None
    launcher = _normalized_launcher_name(argv[0])
    policy = _COMMAND_RUNNER_POLICIES.get(launcher)
    if policy is None or argv[1] != "run":
        return argv, None

    working = argv[2:]
    index = 0
    while index < len(working):
        token = working[index]
        if token == "--":
            index += 1
            break
        if token in policy.option_flags_with_value:
            if index + 1 >= len(working):
                return None, f"{launcher} run option {token} requires a value"
            index += 2
            continue
        if any(token.startswith(f"{flag}=") for flag in policy.option_flags_with_value):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        break

    if index >= len(working):
        return [], None

    target_argv = working[index:]
    if policy.selector_delimiter and target_argv:
        selector = target_argv[0]
        if policy.selector_delimiter in selector:
            _prefix, candidate = selector.rsplit(policy.selector_delimiter, 1)
            if _is_python_launcher(candidate):
                return [candidate, *target_argv[1:]], None
    return target_argv, None


def _command_target_argv(argv: list[str]) -> tuple[list[str] | None, str | None]:
    working = list(argv)

    while working and _ENV_ASSIGNMENT_RE.fullmatch(working[0]):
        working.pop(0)

    if not working:
        return [], None

    if Path(working[0]).name == "env":
        env_argv, parse_error = _env_wrapped_argv(working)
        if parse_error is not None:
            return None, parse_error
        if env_argv == [working[0]]:
            return working, None
        return _command_target_argv(env_argv or [])

    shell_command = _shell_wrapped_command(working)
    if shell_command is not None:
        nested_argv, parse_error = _split_command_argv(shell_command)
        if parse_error is not None:
            return None, parse_error
        return _command_target_argv(nested_argv or [])

    runner_argv, runner_error = _unwrap_command_runner(working)
    if runner_error is not None:
        return None, runner_error
    if runner_argv != working:
        return _command_target_argv(runner_argv or [])

    return working, None


def _command_executable_from_argv(argv: list[str]) -> tuple[str | None, str | None]:
    working = list(argv)

    while working and _ENV_ASSIGNMENT_RE.fullmatch(working[0]):
        working.pop(0)

    if not working:
        return None, "command requirement must include an executable"

    if Path(working[0]).name == "env":
        env_argv, parse_error = _env_wrapped_argv(working)
        if parse_error is not None:
            return None, parse_error
        if env_argv == [working[0]]:
            return working[0], None
        return _command_executable_from_argv(env_argv or [])

    shell_command = _shell_wrapped_command(working)
    if shell_command is not None:
        nested_argv, parse_error = _split_command_argv(shell_command)
        if parse_error is not None:
            return None, parse_error
        return _command_executable_from_argv(nested_argv or [])

    return working[0], None


def _command_executable(command: str) -> tuple[str | None, str | None]:
    """Return the executable token from a shell command requirement.

    The probe must track the real dependency even when the command is wrapped
    in ``env`` assignments or a shell launcher such as ``bash -lc 'solver'``.
    This keeps preflight aligned with the model-visible `tool_requirements`
    contract instead of reporting the outer wrapper as sufficient.
    """

    argv, parse_error = _split_command_argv(command)
    if parse_error is not None:
        return None, parse_error
    return _command_executable_from_argv(argv or [])


def _normalized_launcher_name(token: str) -> str:
    name = Path(token).name.casefold()
    if name.endswith(".exe"):
        return name[:-4]
    return name


def _is_python_launcher(token: str) -> bool:
    return _PYTHON_LAUNCHER_RE.fullmatch(_normalized_launcher_name(token)) is not None


def _workspace_roots_for_command(cwd: Path | None) -> list[Path]:
    if cwd is None:
        return []
    roots = [cwd]
    src_root = cwd / "src"
    if src_root.is_dir():
        roots.append(src_root)
    return roots


def _path_within_workspace_roots(path: Path, *, cwd: Path | None) -> bool:
    """Return whether a resolved command target stays inside the allowed project roots."""

    for root in _workspace_roots_for_command(cwd):
        try:
            path.relative_to(root.resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def _missing_python_script_target_issue(target: str, *, cwd: Path | None) -> str | None:
    target_path = Path(target).expanduser()
    candidate_paths: list[Path] = []

    if target_path.is_absolute():
        candidate_paths.append(target_path.resolve(strict=False))
    elif cwd is not None:
        candidate_paths.append((cwd / target_path).resolve(strict=False))

    if not candidate_paths:
        return None

    out_of_workspace: list[Path] = []
    for candidate_path in candidate_paths:
        if not candidate_path.exists():
            continue
        if _path_within_workspace_roots(candidate_path, cwd=cwd):
            return None
        out_of_workspace.append(candidate_path)

    if out_of_workspace:
        formatted_paths = ", ".join(str(path) for path in out_of_workspace)
        return (
            f"repo-local script target must stay within the project roots: {target} "
            f"(resolved outside {formatted_paths})"
        )

    formatted_candidates = ", ".join(str(path) for path in candidate_paths)
    return f"repo-local script target not found: {target} (looked under {formatted_candidates})"


def _module_namespace_exists(module_name: str, *, cwd: Path | None) -> bool:
    module_path = Path(*module_name.split("."))
    if not module_path.parts:
        return False
    namespace = module_path.parts[0]
    for root in _workspace_roots_for_command(cwd):
        if (root / namespace).exists():
            return True
    return False


def _missing_python_module_target_issue(module_name: str, *, cwd: Path | None) -> str | None:
    if not _module_namespace_exists(module_name, cwd=cwd):
        return None

    module_path = Path(*module_name.split("."))
    candidate_paths: list[Path] = []
    for root in _workspace_roots_for_command(cwd):
        candidate_paths.append((root / f"{module_path}.py").resolve(strict=False))
        candidate_paths.append((root / module_path / "__init__.py").resolve(strict=False))
        candidate_paths.append((root / module_path / "__main__.py").resolve(strict=False))

    for candidate_path in candidate_paths:
        if candidate_path.exists():
            return None

    formatted_candidates = ", ".join(str(path) for path in candidate_paths)
    return f"repo-local module target not found: {module_name} (looked under {formatted_candidates})"


def _command_target_issue(command: str, *, cwd: Path | None) -> str | None:
    argv, parse_error = _split_command_argv(command)
    if parse_error is not None:
        return parse_error
    target_argv, target_parse_error = _command_target_argv(argv or [])
    if target_parse_error is not None:
        return target_parse_error
    if not target_argv or not _is_python_launcher(target_argv[0]):
        return None

    command_argv = target_argv[1:]
    if not command_argv:
        return None

    index = 0
    while index < len(command_argv):
        token = command_argv[index]
        if token == "--":
            index += 1
            break
        if token == "-c":
            return None
        if token == "-m":
            if index + 1 >= len(command_argv):
                return "python -m requires a module target"
            return _missing_python_module_target_issue(command_argv[index + 1], cwd=cwd)
        if token in _PYTHON_COMMAND_FLAGS_WITH_VALUES:
            if token in {"-W", "-X"}:
                if index + 1 >= len(command_argv):
                    return f"{token} requires a value"
                index += 2
            else:
                index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        break

    if index >= len(command_argv):
        return None

    target = command_argv[index]
    if target == "-":
        return None
    return _missing_python_script_target_issue(target, cwd=cwd)


def _probe_tool(requirement: PlanToolRequirement, *, cwd: Path | None = None) -> tuple[bool, str, str, list[str]]:
    if requirement.tool == "command":
        command = requirement.command or ""
        executable, parse_error = _command_executable(command)
        if parse_error is not None:
            return False, parse_error, "command", []
        path = shutil.which(executable) if executable else None
        if path:
            target_issue = _command_target_issue(command, cwd=cwd)
            if target_issue is not None:
                return False, target_issue, "command", []
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
        if integration is not None and integration.is_configured(cwd=cwd):
            endpoint = integration.resolved_endpoint(cwd=cwd)
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


def _knowledge_dependency_status(record) -> str:
    if record.runtime_active:
        return "ok"
    if record.status == "superseded":
        return "superseded"
    if record.status == "stable" and (record.review_fresh is False or record.stale is True):
        return "stale_review"
    if record.status in {"draft", "in_review"}:
        return "not_runtime_active"
    return "not_runtime_active"


def _knowledge_dependency_detail(
    *,
    dep_id: str,
    status: str,
    record,
    successor: str | None,
    resolution_reason: str | None,
) -> str:
    if status == "ok":
        return f"{dep_id} is runtime-active at {record.path}"
    if status == "missing":
        return resolution_reason or f"knowledge doc not found for {dep_id}"
    if status == "ambiguous":
        return resolution_reason or f"multiple knowledge docs match {dep_id}"
    if status == "superseded":
        if successor:
            return (
                f"{dep_id} is superseded by {successor}; update knowledge_deps to the runtime-active successor"
            )
        return f"{dep_id} is superseded; update knowledge_deps to the runtime-active successor"
    if status == "stale_review":
        return f"{dep_id} is stable but its approval review is stale"
    if status == "not_runtime_active":
        return f"{dep_id} exists but is not runtime-active"
    return resolution_reason or f"{dep_id} failed knowledge dependency validation"


def _evaluate_knowledge_dependencies(
    project_root: Path,
    *,
    knowledge_deps: list[str],
    knowledge_gate: str,
) -> _KnowledgeDependencyEvaluation:
    if knowledge_gate == "off" or not knowledge_deps:
        return _KnowledgeDependencyEvaluation(checks=[], warnings=[], blocking_conditions=[], guidance="")

    from gpd.core.knowledge_index import iter_knowledge_supersession_chain, resolve_knowledge_doc

    checks: list[KnowledgeDependencyCheck] = []
    warnings: list[str] = []
    blocking_conditions: list[str] = []
    guidance_fragments: list[str] = []

    for dep_id in knowledge_deps:
        resolution = resolve_knowledge_doc(project_root, dep_id)
        record = resolution.record
        successor: str | None = None
        if record is None:
            if resolution.candidates:
                status = "ambiguous"
                detail = resolution.reason or f"multiple knowledge docs match {dep_id}"
            else:
                status = "missing"
                detail = resolution.reason or f"knowledge doc not found for {dep_id}"
            resolved = False
            runtime_active = False
            review_fresh = None
            record_path = None
        else:
            status = _knowledge_dependency_status(record)
            resolved = True
            runtime_active = record.runtime_active
            review_fresh = record.review_fresh
            record_path = record.path
            if status == "superseded":
                chain = iter_knowledge_supersession_chain(project_root, dep_id)
                if len(chain) > 1:
                    successor = chain[1].knowledge_id
            detail = _knowledge_dependency_detail(
                dep_id=dep_id,
                status=status,
                record=record,
                successor=successor,
                resolution_reason=resolution.reason,
            )

        blocking = knowledge_gate == "block" and status in {
            "missing",
            "ambiguous",
            "not_runtime_active",
            "stale_review",
            "superseded",
        }
        check = KnowledgeDependencyCheck(
            knowledge_id=dep_id,
            status=status,
            resolved=resolved,
            runtime_active=runtime_active,
            blocking=blocking,
            detail=detail,
            record_path=record_path,
            successor=successor,
            review_fresh=review_fresh,
        )
        checks.append(check)

        if status == "ok":
            continue

        message = f"{dep_id}: {detail}"
        warnings.append(message)
        guidance_fragments.append(message)
        if blocking:
            blocking_conditions.append(message)

    if blocking_conditions:
        guidance = "Resolve explicit knowledge dependency blockers before execution."
        if guidance_fragments:
            guidance = f"{guidance} {' '.join(guidance_fragments)}"
    elif warnings:
        guidance = "Review explicit knowledge dependency warnings before execution."
        guidance = f"{guidance} {' '.join(guidance_fragments)}"
    else:
        guidance = "Explicit knowledge dependencies are runtime-active."

    return _KnowledgeDependencyEvaluation(
        checks=checks,
        warnings=warnings,
        blocking_conditions=blocking_conditions,
        guidance=guidance,
    )


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
            knowledge_gate="off",
            knowledge_deps=[],
            errors=[f"Plan not found: {resolved_path}"],
            guidance=f"Plan not found: {resolved_path}",
        )

    command_workspace_root = resolve_project_root(resolved_path.parent, require_layout=True) or resolved_path.parent
    try:
        content = resolved_path.read_text(encoding="utf-8")
    except OSError as exc:
        return PlanToolPreflightResult(
            plan_path=str(resolved_path),
            validation_passed=False,
            valid=False,
            passed=False,
            knowledge_gate="off",
            knowledge_deps=[],
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
            knowledge_gate="off",
            knowledge_deps=[],
            errors=[f"Could not parse plan frontmatter: {exc}"],
            guidance=f"Could not parse plan frontmatter: {exc}",
        )

    try:
        knowledge_gate = _parse_knowledge_gate(meta.get("knowledge_gate"))
        knowledge_deps = _parse_knowledge_deps(meta.get("knowledge_deps"))
    except PlanToolPreflightError as exc:
        return PlanToolPreflightResult(
            plan_path=str(resolved_path),
            validation_passed=False,
            valid=False,
            passed=False,
            knowledge_gate="off",
            knowledge_deps=[],
            errors=[f"Invalid knowledge dependency controls: {exc}"],
            guidance=f"Invalid knowledge dependency controls: {exc}",
        )

    validation_errors: list[str] = []
    if requirements is None:
        validation = validate_frontmatter(content, "plan", source_path=resolved_path)
        validation_errors = [f"Missing required frontmatter field: {field}" for field in validation.missing]
        validation_errors.extend(validation.errors)
        if isinstance(meta.get("knowledge_gate"), bool) and meta.get("knowledge_gate") is False:
            validation_errors = [
                error for error in validation_errors if error != "knowledge_gate: expected a string"
            ]
        if validation_errors:
            return PlanToolPreflightResult(
                plan_path=str(resolved_path),
                validation_passed=False,
                valid=False,
                passed=False,
                knowledge_gate=knowledge_gate,
                knowledge_deps=knowledge_deps,
                errors=validation_errors,
                guidance="Fix invalid PLAN frontmatter before specialized-tool preflight can pass.",
            )

    active_requirements = requirements
    if active_requirements is None:
        try:
            active_requirements = parse_plan_tool_requirements(meta.get("tool_requirements"))
        except PlanToolPreflightError as exc:
            return PlanToolPreflightResult(
                plan_path=str(resolved_path),
                validation_passed=False,
                valid=False,
                passed=False,
                knowledge_gate=knowledge_gate,
                knowledge_deps=knowledge_deps,
                errors=[f"Invalid tool_requirements: {exc}"],
                guidance=f"Invalid tool_requirements: {exc}",
            )

    knowledge_eval = _evaluate_knowledge_dependencies(
        command_workspace_root,
        knowledge_deps=knowledge_deps,
        knowledge_gate=knowledge_gate,
    )

    has_tool_requirements = bool(active_requirements)

    if not has_tool_requirements and not knowledge_deps:
        return PlanToolPreflightResult(
            plan_path=str(resolved_path),
            validation_passed=True,
            valid=True,
            passed=True,
            knowledge_gate=knowledge_gate,
            knowledge_deps=knowledge_deps,
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
            available, detail, provider, probe_warnings = _probe_tool(requirement, cwd=command_workspace_root)
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

    warnings.extend(knowledge_eval.warnings)
    blocking_conditions.extend(knowledge_eval.blocking_conditions)

    missing_preferred_with_fallback = any(
        (not check.available) and (not check.blocking) and bool(check.fallback)
        for check in checks
    )
    missing_preferred_without_fallback = any(
        (not check.available) and (not check.blocking) and not check.fallback
        for check in checks
    )
    guidance = (
        "Install or enable the missing required specialized tools, or revise the plan before execution. Do not invent results or placeholder artifacts for unavailable required tools."
        if blocking_missing
        else (
            "Proceed using declared fallback paths for unavailable preferred tools. If the fallback cannot produce the required evidence, report the gap instead of inventing outputs."
            if missing_preferred_with_fallback
            else (
                "Optional specialized tools are unavailable; continue only if the plan can genuinely proceed without them. Otherwise report the gap instead of fabricating outputs."
                if missing_preferred_without_fallback
                else "All declared specialized tools are available through local or configured capabilities."
            )
        )
    )
    if not has_tool_requirements:
        guidance = (
            knowledge_eval.guidance
            if knowledge_eval.has_issues
            else (
                "Explicit knowledge dependencies are runtime-active."
                if knowledge_deps and knowledge_gate != "off"
                else "No machine-checkable specialized tool requirements declared."
            )
        )
    elif knowledge_eval.guidance and knowledge_eval.has_issues:
        guidance = f"{guidance} {knowledge_eval.guidance}"
    return PlanToolPreflightResult(
        plan_path=str(resolved_path),
        validation_passed=True,
        valid=True,
        passed=not blocking_missing and not bool(knowledge_eval.blocking_conditions),
        knowledge_gate=knowledge_gate,
        knowledge_deps=knowledge_deps,
        requirements=checks,
        checks=checks,
        knowledge_dependency_checks=knowledge_eval.checks,
        blocking_conditions=blocking_conditions,
        warnings=warnings,
        guidance=guidance,
    )

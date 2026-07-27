"""MCP server for GPD convention management.

Thin MCP wrapper around ``gpd.core.conventions`` (lock state, key/value
normalization, diffing) and ``gpd.core.convention_checks`` (the shared
ASSERT_CONVENTION and subfield-defaults payload builders). Exposes convention
lock operations as MCP tools for solver agents.

Usage:
    python -m gpd.mcp.servers.conventions_server
    # or via entry point:
    gpd-mcp-conventions
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeVar

from mcp.server.fastmcp import FastMCP
from pydantic import Field, WithJsonSchema

from gpd.contracts import ConventionLock
from gpd.core.constants import ProjectLayout

# Convention payload builders and the project-lock loading path live in core so the
# MCP tools and the `gpd convention` CLI subcommands emit identical envelopes; the
# names are re-exported here to keep this module the stable import surface.
from gpd.core.convention_checks import (  # noqa: F401
    SUBFIELD_DEFAULTS,
    assert_convention_validate_payload,
    subfield_defaults_payload,
)
from gpd.core.convention_checks import (
    load_lock_from_project as _load_lock_from_project,
)
from gpd.core.convention_checks import (
    recoverable_state_payload as _recoverable_state_payload,
)
from gpd.core.conventions import (
    CONVENTION_OPTIONS,
    KEY_ALIASES,
    KNOWN_CONVENTIONS,
    ConventionSetResult,
    convention_list,
    convention_lock_data_from_state_payload,
    convention_lock_from_state_payload,
    normalize_key,
    normalize_value,
)
from gpd.core.conventions import (
    convention_check as _convention_check,
)
from gpd.core.conventions import (
    convention_diff as _convention_diff,
)
from gpd.core.conventions import (
    convention_set as _convention_set,
)
from gpd.core.errors import ConventionError
from gpd.core.observability import gpd_span
from gpd.mcp.servers import (
    ABSOLUTE_PROJECT_DIR_SCHEMA,
    configure_mcp_logging,
    mutating_tool_annotations,
    read_only_tool_annotations,
    resolve_absolute_project_dir,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)

T = TypeVar("T")

logger = configure_mcp_logging("gpd-conventions")

mcp = FastMCP("gpd-conventions")

_CONVENTION_MUTATION_TOOL_ANNOTATIONS = mutating_tool_annotations(destructive=True, idempotent=False)

AbsoluteProjectDirInput = Annotated[str, WithJsonSchema(ABSOLUTE_PROJECT_DIR_SCHEMA)]

_CUSTOM_CONVENTION_KEY_BODY = r"[A-Za-z0-9][A-Za-z0-9_-]*"
_CUSTOM_CONVENTION_KEY_PATTERN = rf"^{_CUSTOM_CONVENTION_KEY_BODY}$"
_CONVENTION_VALUE_PATTERN = r"^(?!\s*(?:null|none|undefined)\s*$)\S(?:.*\S)?$"

ConventionKeyInput = Annotated[
    str,
    WithJsonSchema(
        {
            "description": "Use one canonical convention field name, one of the short aliases, or a custom key with the custom:<slug> prefix.",
            "anyOf": [
                {"type": "string", "enum": KNOWN_CONVENTIONS},
                {"type": "string", "enum": list(KEY_ALIASES)},
                {
                    "type": "string",
                    "pattern": rf"^custom:{_CUSTOM_CONVENTION_KEY_BODY}$",
                    "description": "Custom keys must be non-empty slugs such as custom:<slug>.",
                },
            ],
        }
    ),
]
ConventionValueInput = Annotated[
    str,
    WithJsonSchema(
        {
            "type": "string",
            "minLength": 1,
            "pattern": _CONVENTION_VALUE_PATTERN,
            "description": "Convention values must be non-empty and must not be blank or placeholder strings like null, none, or undefined.",
        }
    ),
]
SubfieldDomainInput = Annotated[
    str,
    Field(min_length=1, pattern=r"\S"),
    WithJsonSchema(
        {
            "type": "string",
            "minLength": 1,
            "pattern": r"\S",
            "enum": sorted(SUBFIELD_DEFAULTS),
            "description": "Non-empty physics subfield domain key.",
        }
    ),
]


# ─── Project I/O ──────────────────────────────────────────────────────────────


def _update_lock_in_project(
    project_dir: str,
    mutate_fn: Callable[[ConventionLock], T],
) -> tuple[ConventionLock, T]:
    """Atomically load, mutate, and save a convention lock.

    Holds the file lock for the entire read-modify-write cycle so that
    concurrent ``convention_set`` calls cannot lose each other's writes
    (TOCTOU race).

    Returns (updated_lock, result_of_mutate_fn).
    """
    from gpd.core.state import save_state_json_locked
    from gpd.core.utils import file_lock

    cwd = Path(project_dir)
    state_path = ProjectLayout(cwd).state_json
    with file_lock(state_path):
        raw = _recoverable_state_payload(cwd, acquire_lock=False, recover_intent=True)
        lock_data = convention_lock_data_from_state_payload(raw, source_label="state.json")
        lock = convention_lock_from_state_payload(raw, source_label="state.json")

        # --- mutate ---
        result = mutate_fn(lock)

        # --- write (only when the lock was actually changed) ---
        new_lock_data = lock.model_dump(exclude_none=True)
        if new_lock_data != lock_data:
            raw["convention_lock"] = new_lock_data
            save_state_json_locked(cwd, raw)

    return lock, result


# ─── MCP Tools ────────────────────────────────────────────────────────────────


@mcp.tool(annotations=read_only_tool_annotations())
def convention_lock_status(project_dir: AbsoluteProjectDirInput) -> dict:
    """Get the current convention lock state for a GPD project.

    Returns all set conventions and lists which of the 18 standard
    fields are still unset.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.conventions.lock_status"):
        try:
            lock = _load_lock_from_project(str(cwd))
            result = convention_list(lock)

            set_fields = [k for k, e in result.conventions.items() if e.is_set and e.canonical]
            unset_fields = [k for k in KNOWN_CONVENTIONS if k not in set_fields]
            custom = {k: e.value for k, e in result.conventions.items() if not e.canonical and e.is_set}

            return stable_mcp_response(
                {
                    "lock": lock.model_dump(exclude_none=True),
                    "set_count": result.set_count,
                    "total_standard_fields": result.canonical_total,
                    "set_fields": set_fields,
                    "unset_fields": unset_fields,
                    "custom_conventions": custom,
                    "completeness_percent": round(len(set_fields) / max(result.canonical_total, 1) * 100, 1),
                }
            )
        except (ConventionError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=_CONVENTION_MUTATION_TOOL_ANNOTATIONS)
def convention_set(
    project_dir: AbsoluteProjectDirInput,
    key: ConventionKeyInput,
    value: ConventionValueInput,
    force: bool = False,
    allow_nonstandard: bool = False,
) -> dict:
    """Set a convention in the project's convention lock.

    Standard convention fields warn when the value is outside known options.
    Set allow_nonstandard=True to mark that choice as intentional.
    Use force=True to override an already-set convention (dangerous
    mid-project -- can invalidate prior derivations).

    Key must be one of the canonical convention fields, one of the short
    aliases, or a custom key in the form ``custom:<slug>`` (for example
    ``custom:my_convention``).
    Value must be non-empty and must not be a blank or placeholder string.
    """
    cwd = resolve_absolute_project_dir(project_dir)
    if cwd is None:
        return stable_mcp_error("project_dir must be an absolute path")
    with gpd_span("mcp.conventions.set", convention_key=key):
        try:
            # Validate custom key eagerly (before acquiring the file lock).
            if key.startswith("custom:"):
                custom_key = key[len("custom:") :]
                if not custom_key:
                    raise ConventionError("Custom convention key cannot be empty")
                if not re.fullmatch(_CUSTOM_CONVENTION_KEY_PATTERN, custom_key):
                    raise ConventionError(
                        "Custom convention keys must be non-empty slugs using letters, numbers, underscores, or hyphens"
                    )

            def _mutate(lock: ConventionLock) -> ConventionSetResult:
                if key.startswith("custom:"):
                    return _convention_set(lock, key[len("custom:") :], value, force=force)
                return _convention_set(lock, key, value, force=force)

            # Atomic read-modify-write under file lock to prevent TOCTOU races.
            _lock, result = _update_lock_in_project(str(cwd), _mutate)
        except (ConventionError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)

        if not result.updated:
            return stable_mcp_response(
                {
                    "status": "already_set",
                    "key": result.key,
                    "current_value": result.previous,
                    "requested_value": result.value,
                    "message": result.hint or f"Convention '{result.key}' already set. Use force=True to override.",
                }
            )

        response: dict[str, object] = {
            "status": "set",
            "key": result.key,
            "value": result.value,
            "type": "custom" if result.custom else "standard",
        }
        if result.previous is not None:
            response["previous_value"] = result.previous
            response["forced"] = True

        # Warn about non-standard values for known fields
        canonical = normalize_key(key)
        options = CONVENTION_OPTIONS.get(canonical, [])
        if options:
            normalized_options = [normalize_value(canonical, o) for o in options]
            if result.value not in options and result.value not in normalized_options:
                response["non_standard"] = True
                response["known_options"] = options
                response["allow_nonstandard"] = allow_nonstandard
                response["warning"] = f"Non-standard value '{result.value}' for '{canonical}'. Known options: {options}"

        return stable_mcp_response(response)


@mcp.tool(annotations=read_only_tool_annotations())
def convention_check(lock: dict) -> dict:
    """Validate a convention lock for completeness and consistency.

    Checks which fields are set, flags missing critical conventions,
    and identifies potential inconsistencies between related fields.
    """
    with gpd_span("mcp.conventions.check"):
        try:
            parsed = ConventionLock(**lock)
            result = _convention_check(parsed)

            # Critical fields that should almost always be set
            critical = {"metric_signature", "fourier_convention", "natural_units"}
            missing_critical = [m.key for m in result.missing if m.key in critical]

            # Consistency checks beyond what conventions.py provides
            issues: list[str] = []
            metric = parsed.metric_signature
            fourier = parsed.fourier_convention
            units = parsed.natural_units

            if metric and fourier:
                if "euclidean" in (metric or "").lower() and fourier == "QFT":
                    issues.append(
                        "Euclidean metric with QFT Fourier convention may cause sign issues. Check Wick rotation conventions."
                    )

            if units == "SI" and metric and ("(-,+,+,+)" in (metric or "") or "mostly-plus" in (metric or "").lower()):
                issues.append(
                    "SI units with mostly-plus signature: ensure c factors are explicit in all relativistic expressions."
                )

            if parsed.renormalization_scheme and not parsed.regularization_scheme:
                issues.append(
                    "Renormalization scheme set without regularization scheme. These are typically specified together."
                )

            return stable_mcp_response(
                {
                    "valid": len(missing_critical) == 0,
                    "completeness_percent": round(result.set_count / max(result.total, 1) * 100, 1),
                    "set_fields": [s.key for s in result.set_conventions],
                    "unset_fields": [m.key for m in result.missing],
                    "missing_critical": missing_critical,
                    "issues": issues,
                    "total_standard_fields": result.total,
                }
            )
        except (ConventionError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def convention_diff(lock_a: dict, lock_b: dict) -> dict:
    """Compare two convention lock dictionaries and identify differences.

    Useful for detecting convention drift between phases or comparing
    a plan's conventions against the project lock.
    """
    with gpd_span("mcp.conventions.diff"):
        try:
            parsed_a = ConventionLock(**lock_a)
            parsed_b = ConventionLock(**lock_b)
            result = _convention_diff(parsed_a, parsed_b)
        except (ConventionError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)

    critical_fields = {"metric_signature", "fourier_convention", "natural_units"}
    diffs: list[dict[str, object]] = []

    for d in result.changed:
        diffs.append(
            {
                "field": d.key,
                "value_a": d.from_value,
                "value_b": d.to_value,
                "severity": "critical" if d.key in critical_fields else "warning",
            }
        )
    for d in result.added:
        diffs.append(
            {
                "field": d.key,
                "value_a": None,
                "value_b": d.to_value,
                "severity": "info",
            }
        )
    for d in result.removed:
        diffs.append(
            {
                "field": d.key,
                "value_a": d.from_value,
                "value_b": None,
                "severity": "info",
            }
        )

    return stable_mcp_response(
        {
            "identical": len(diffs) == 0,
            "diff_count": len(diffs),
            "diffs": diffs,
            "critical_diffs": [d for d in diffs if d["severity"] == "critical"],
        }
    )


@mcp.tool(annotations=read_only_tool_annotations())
def assert_convention_validate(file_content: str, lock: dict) -> dict:
    """Verify ASSERT_CONVENTION lines in a file against the project lock.

    Scans for convention assertion comments in the format:
        % ASSERT_CONVENTION: key=value, key=value, ...
        # ASSERT_CONVENTION: key=value, key=value, ...
        <!-- ASSERT_CONVENTION: key=value, key=value, ... -->

    Every derivation artifact must include at least one ASSERT_CONVENTION line.
    Missing assertions are treated as invalid, not advisory, because downstream
    verification depends on those headers matching the convention lock.

    Returns mismatches and missing assertions.
    """
    with gpd_span("mcp.conventions.assert_validate"):
        return assert_convention_validate_payload(file_content, lock)


@mcp.tool(annotations=read_only_tool_annotations())
def subfield_defaults(domain: SubfieldDomainInput) -> dict:
    """Return recommended default conventions for a physics domain.

    Provides sensible starting conventions for common subfields.
    These are recommendations, not requirements.

    Valid domains: qft, condensed_matter, stat_mech, gr_cosmology,
    amo, nuclear_particle, astrophysics, mathematical_physics,
    algebraic_qft, string_field_theory, quantum_info, soft_matter, fluid_plasma,
    classical_mechanics.
    """
    with gpd_span("mcp.conventions.subfield_defaults", domain=domain):
        return subfield_defaults_payload(domain)


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server via stdio transport."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Conventions MCP Server")


tighten_registered_tool_contracts(mcp)


if __name__ == "__main__":
    main()

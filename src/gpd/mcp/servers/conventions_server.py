"""MCP server for GPD convention management.

Thin MCP wrapper around gpd.core.conventions. Exposes convention lock
operations as MCP tools for solver agents.

Usage:
    python -m gpd.mcp.servers.conventions_server
    # or via entry point:
    gpd-mcp-conventions
"""

import json
import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeVar

from mcp.server.fastmcp import FastMCP
from pydantic import WithJsonSchema

from gpd.contracts import ConventionLock
from gpd.core.constants import ProjectLayout
from gpd.core.conventions import (
    KEY_ALIASES,
    KNOWN_CONVENTIONS,
    ConventionSetResult,
    convention_list,
    normalize_key,
    normalize_value,
    validate_assertions,
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
from gpd.mcp.servers import stable_mcp_error, stable_mcp_response

T = TypeVar("T")

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-conventions")

mcp = FastMCP("gpd-conventions")

# ─── Convention Field Metadata (for MCP tool responses) ──────────────────────

# Valid options per field — enriches responses beyond what conventions.py tracks.
CONVENTION_OPTIONS: dict[str, list[str]] = {
    "metric_signature": ["(+,-,-,-)", "(-,+,+,+)", "Euclidean (+,+,+,+)", "mostly-minus", "mostly-plus", "euclidean"],
    "fourier_convention": ["physics", "math", "symmetric", "QFT"],
    "natural_units": ["natural", "SI", "CGS", "lattice"],
    "gauge_choice": ["Coulomb", "Lorenz", "axial", "Feynman", "light-cone"],
    "regularization_scheme": ["dim-reg", "cutoff", "lattice", "zeta", "PV"],
    "renormalization_scheme": ["MS-bar", "on-shell", "MOM", "lattice"],
    "coordinate_system": ["Cartesian", "spherical", "cylindrical", "light-cone"],
    "spin_basis": ["Dirac", "Weyl", "Majorana"],
    "state_normalization": ["relativistic", "non-relativistic", "box"],
    "coupling_convention": ["g", "g^2", "g^2/(4pi)", "alpha=g^2/(4pi)"],
    "index_positioning": ["Einstein", "explicit"],
    "time_ordering": ["time-ordered", "anti-time-ordered", "path-ordered"],
    "commutation_convention": ["canonical", "anti-canonical"],
    "levi_civita_sign": ["+1", "-1"],
    "generator_normalization": ["delta/2", "delta"],
    "covariant_derivative_sign": ["D=d-igA", "D=d+igA"],
    "gamma_matrix_convention": ["Dirac", "Weyl", "Majorana"],
    "creation_annihilation_order": ["normal", "anti-normal", "Weyl"],
}

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

# ─── Subfield Default Conventions ─────────────────────────────────────────────

SUBFIELD_DEFAULTS: dict[str, dict[str, str]] = {
    "qft": {
        "natural_units": "natural",
        "metric_signature": "mostly-minus",
        "fourier_convention": "physics",
        "index_positioning": "Einstein",
        "state_normalization": "relativistic",
        "levi_civita_sign": "+1",
        "generator_normalization": "delta/2",
        "creation_annihilation_order": "normal",
    },
    "condensed_matter": {
        "natural_units": "natural",
        "metric_signature": "euclidean",
        "fourier_convention": "physics",
        "state_normalization": "non-relativistic",
        "creation_annihilation_order": "normal",
    },
    "stat_mech": {
        "natural_units": "natural",
        "fourier_convention": "physics",
        "state_normalization": "non-relativistic",
    },
    "gr_cosmology": {
        "natural_units": "natural",
        "metric_signature": "mostly-plus",
        "fourier_convention": "physics",
        "index_positioning": "Einstein",
        "coordinate_system": "spherical",
    },
    "amo": {
        "natural_units": "SI",
        "state_normalization": "non-relativistic",
        "coordinate_system": "spherical",
    },
    "nuclear_particle": {
        "natural_units": "natural",
        "metric_signature": "mostly-minus",
        "fourier_convention": "physics",
        "state_normalization": "relativistic",
        "levi_civita_sign": "+1",
    },
    "astrophysics": {
        "natural_units": "CGS",
        "coordinate_system": "spherical",
    },
    "mathematical_physics": {
        "natural_units": "natural",
        "index_positioning": "Einstein",
    },
    "algebraic_qft": {
        "natural_units": "natural",
        "metric_signature": "mostly-minus",
        "fourier_convention": "physics",
        "index_positioning": "Einstein",
        "state_normalization": "relativistic",
    },
    "string_field_theory": {
        "natural_units": "natural",
        "fourier_convention": "physics",
        "index_positioning": "Einstein",
        "creation_annihilation_order": "normal",
    },
    "quantum_info": {
        "natural_units": "natural",
        "state_normalization": "non-relativistic",
    },
    "soft_matter": {
        "natural_units": "SI",
        "coordinate_system": "Cartesian",
    },
    "fluid_plasma": {
        "natural_units": "CGS",
        "coordinate_system": "Cartesian",
    },
    "classical_mechanics": {
        "natural_units": "SI",
        "coordinate_system": "Cartesian",
    },
}


# ─── Project I/O ──────────────────────────────────────────────────────────────


def _load_lock_from_project(project_dir: str) -> ConventionLock:
    """Load convention lock from project state.json."""
    state_path = ProjectLayout(Path(project_dir)).state_json
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ConventionLock()
    except json.JSONDecodeError as e:
        raise ConventionError(f"Malformed state.json: {e}") from e


    if not isinstance(raw, dict):
        return ConventionLock()
    lock_data = raw.get("convention_lock", {})
    if not isinstance(lock_data, dict):
        return ConventionLock()
    return ConventionLock(**lock_data)


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

    state_path = ProjectLayout(Path(project_dir)).state_json
    cwd = Path(project_dir)
    with file_lock(state_path):
        # --- read ---
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raw = {}
        except json.JSONDecodeError as e:
            raise ConventionError(f"Malformed state.json: {e}") from e


        if not isinstance(raw, dict):
            raw = {}
        lock_data = raw.get("convention_lock", {})
        if not isinstance(lock_data, dict):
            lock_data = {}
        lock = ConventionLock(**lock_data)

        # --- mutate ---
        result = mutate_fn(lock)

        # --- write (only when the lock was actually changed) ---
        new_lock_data = lock.model_dump(exclude_none=True)
        if new_lock_data != lock_data:
            raw["convention_lock"] = new_lock_data
            save_state_json_locked(cwd, raw)

    return lock, result


# ─── MCP Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
def convention_lock_status(project_dir: str) -> dict:
    """Get the current convention lock state for a GPD project.

    Returns all set conventions and lists which of the 18 standard
    fields are still unset.
    """
    with gpd_span("mcp.conventions.lock_status"):
        try:
            lock = _load_lock_from_project(project_dir)
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


@mcp.tool()
def convention_set(
    project_dir: str,
    key: ConventionKeyInput,
    value: ConventionValueInput,
    force: bool = False,
) -> dict:
    """Set a convention in the project's convention lock.

    Standard convention fields are validated against known options.
    Use force=True to override an already-set convention (dangerous
    mid-project -- can invalidate prior derivations).

    Key must be one of the canonical convention fields, one of the short
    aliases, or a custom key in the form ``custom:<slug>`` (for example
    ``custom:my_convention``).
    Value must be non-empty and must not be a blank or placeholder string.
    """
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
            _lock, result = _update_lock_in_project(project_dir, _mutate)
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
                    "message": result.hint
                    or f"Convention '{result.key}' already set. Use force=True to override.",
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
                response["warning"] = f"Non-standard value '{result.value}' for '{canonical}'. Known options: {options}"

        return stable_mcp_response(response)


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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
    from gpd.core.conventions import parse_assert_conventions

    with gpd_span("mcp.conventions.assert_validate"):
        try:
            parsed_lock = ConventionLock(**lock)
            assertions = parse_assert_conventions(file_content)
            mismatches = validate_assertions(file_content, parsed_lock, filename="<mcp_input>")
        except (ConventionError, OSError, ValueError, TimeoutError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)

    if not assertions:
        return stable_mcp_response(
            {
                "valid": False,
                "assertions_found": 0,
                "message": "No ASSERT_CONVENTION lines found. Every derivation file must include at least one.",
                "mismatches": [],
                "assertions": [],
            }
        )

    return stable_mcp_response(
        {
            "valid": len(mismatches) == 0,
            "assertions_found": len(assertions),
            "assertions": [{"key": k, "value": v} for k, v in assertions],
            "mismatches": [
                {
                    "key": m.key,
                    "file_value": m.file_value,
                    "lock_value": m.lock_value,
                    "message": (
                        f"Convention mismatch: file declares {m.key}={m.file_value} "
                        f"but lock has {m.key}={m.lock_value}"
                    ),
                }
                for m in mismatches
            ],
        }
    )


@mcp.tool()
def subfield_defaults(domain: str) -> dict:
    """Return recommended default conventions for a physics domain.

    Provides sensible starting conventions for common subfields.
    These are recommendations, not requirements.

    Valid domains: qft, condensed_matter, stat_mech, gr_cosmology,
    amo, nuclear_particle, astrophysics, mathematical_physics,
    algebraic_qft, string_field_theory, quantum_info, soft_matter, fluid_plasma,
    classical_mechanics.
    """
    with gpd_span("mcp.conventions.subfield_defaults", domain=domain):
        defaults = SUBFIELD_DEFAULTS.get(domain)
    if defaults is None:
        return stable_mcp_response(
            {
                "found": False,
                "domain": domain,
                "available_domains": sorted(SUBFIELD_DEFAULTS.keys()),
                "message": f"No defaults for domain '{domain}'.",
            }
        )

    return stable_mcp_response(
        {
            "found": True,
            "domain": domain,
            "defaults": defaults,
            "field_count": len(defaults),
            "unset_fields": [f for f in KNOWN_CONVENTIONS if f not in defaults],
            "message": (
                f"Recommended conventions for {domain}. "
                f"Sets {len(defaults)} of {len(KNOWN_CONVENTIONS)} standard fields."
            ),
        }
    )


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server via stdio transport."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Conventions MCP Server")


if __name__ == "__main__":
    main()

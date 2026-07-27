"""Transport-neutral convention surfaces shared by the MCP server and the CLI.

Owns the recommended per-domain convention defaults, the ASSERT_CONVENTION
validation payload, and the project-state lock loading path so the
``gpd-conventions`` MCP tools and the ``gpd convention`` CLI subcommands emit the
same envelopes for the same inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

from gpd.contracts import ConventionLock
from gpd.core.constants import ProjectLayout
from gpd.core.conventions import (
    KNOWN_CONVENTIONS,
    check_assertions,
    convention_lock_from_state_payload,
    parse_assert_conventions,
    required_assertion_keys,
)
from gpd.core.envelopes import stable_mcp_error, stable_mcp_response
from gpd.core.errors import ConventionError

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


def recoverable_state_payload(
    project_root: Path,
    *,
    acquire_lock: bool = True,
    recover_intent: bool = False,
) -> dict[str, object]:
    """Return recoverable project state or fail closed when state exists but is unusable."""
    from gpd.core.state import peek_state_json

    layout = ProjectLayout(project_root)
    if layout.state_json.exists():
        try:
            primary_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConventionError(f"Malformed state.json: {exc}") from exc
        except FileNotFoundError:
            primary_state = None
        except OSError:
            primary_state = None
        else:
            if isinstance(primary_state, dict):
                return primary_state
    state_files_exist = any(path.exists() for path in (layout.state_json, layout.state_json_backup, layout.state_md))
    if acquire_lock:
        state_obj, _integrity_issues, _state_source = peek_state_json(
            project_root,
            recover_intent=recover_intent,
            surface_blocked_project_contract=True,
        )
    else:
        from gpd.core.state import _load_state_json_with_integrity_issues

        state_obj, _integrity_issues, _state_source = _load_state_json_with_integrity_issues(
            project_root,
            persist_recovery=False,
            recover_intent=recover_intent,
            surface_blocked_project_contract=True,
            acquire_lock=False,
        )
    if isinstance(state_obj, dict):
        return state_obj
    if state_files_exist:
        raise ConventionError("Project state exists but is not recoverable")
    return {}


def load_lock_from_project(project_dir: str) -> ConventionLock:
    """Load convention lock from project state.json."""
    project_root = Path(project_dir)
    raw = recoverable_state_payload(project_root, recover_intent=False)
    return convention_lock_from_state_payload(raw, source_label="project state")


# ─── Response payloads ────────────────────────────────────────────────────────


def assert_convention_validate_payload(file_content: str, lock: dict) -> dict[str, object]:
    """Return the ASSERT_CONVENTION validation envelope for one file against one lock."""

    try:
        parsed_lock = ConventionLock(**lock)
        assertions = parse_assert_conventions(file_content)
        result = check_assertions(
            file_content,
            parsed_lock,
            filename="<mcp_input>",
            require_assertions=True,
            required_keys=required_assertion_keys(parsed_lock),
        )
    except (ConventionError, OSError, ValueError, TimeoutError) as exc:
        return stable_mcp_error(exc)
    except Exception as exc:  # pragma: no cover - defensive envelope
        return stable_mcp_error(exc)

    if result.missing_required_assertions:
        return stable_mcp_response(
            {
                "valid": False,
                "assertions_found": result.assertion_count,
                "message": "No ASSERT_CONVENTION lines found. Every derivation file must include at least one.",
                "required_keys": result.required_keys,
                "missing_required_keys": result.missing_required_keys,
                "mismatches": [],
                "assertions": [],
            }
        )

    return stable_mcp_response(
        {
            "valid": result.passed,
            "assertions_found": result.assertion_count,
            "assertions": [{"key": k, "value": v} for k, v in assertions],
            "required_keys": result.required_keys,
            "missing_required_keys": result.missing_required_keys,
            "mismatches": [
                {
                    "key": m.key,
                    "file_value": m.file_value,
                    "lock_value": m.lock_value,
                    "message": (
                        f"Convention mismatch: file declares {m.key}={m.file_value} but lock has {m.key}={m.lock_value}"
                    ),
                }
                for m in result.mismatches
            ],
        }
    )


def subfield_defaults_payload(domain: object) -> dict[str, object]:
    """Return the recommended-default envelope for one physics subfield domain."""

    if not isinstance(domain, str) or not domain.strip():
        return stable_mcp_error("domain must be a non-empty string")
    domain = domain.strip()
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

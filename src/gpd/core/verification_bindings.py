"""Canonical contract-binding targets for contract-aware verification checks.

These names are the single source of truth for the ``binding.<target>_ids``
request surface. ``gpd.mcp.verification_contract_policy`` re-exports them for the
MCP policy text, and ``gpd.core.contract_checks`` uses them to validate bindings
for both the MCP and CLI surfaces.
"""

from __future__ import annotations

VERIFICATION_BINDING_TARGETS = (
    "observable",
    "claim",
    "deliverable",
    "acceptance_test",
    "reference",
    "forbidden_proxy",
)
VERIFICATION_BINDING_FIELD_NAMES = tuple(f"binding.{target}_ids" for target in VERIFICATION_BINDING_TARGETS)

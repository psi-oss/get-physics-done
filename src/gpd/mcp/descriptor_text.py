"""Shared text for public MCP descriptors and skill-server payloads."""

from __future__ import annotations

SKILL_BEHAVIORAL_GUARDRAIL_HINT = (
    "Use scientific skepticism and critical thinking without treating the user as an adversary. Treat missing "
    "evidence or artifacts as missing, blocked, failed, or inconclusive, and never fabricate references, results, "
    "files, or completion state."
)

SKILLS_SERVER_DESCRIPTION = (
    "GPD skill discovery and routing. Tools for listing, retrieving, auto-routing, "
    "and indexing GPD workflow skills for runtime context assembly. Treat missing evidence or artifacts as "
    "missing, blocked, failed, or inconclusive; never fabricate fallback outputs."
)

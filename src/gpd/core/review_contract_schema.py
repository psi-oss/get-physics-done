"""Shared review-contract vocabulary used across validation and prompts."""

from __future__ import annotations

REVIEW_CONTRACT_FRONTMATTER_KEY = "review-contract"
REVIEW_CONTRACT_PROMPT_WRAPPER_KEY = "review_contract"
REVIEW_CONTRACT_WRAPPER_KEYS = (
    REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
    REVIEW_CONTRACT_FRONTMATTER_KEY,
)
REVIEW_CONTRACT_MODES = ("publication", "review")
REVIEW_CONTRACT_REQUIRED_STATES = ("phase_executed",)
REVIEW_CONTRACT_CONDITIONAL_WHENS = (
    "theorem-bearing claims are present",
    "theorem-bearing manuscripts are present",
)
REVIEW_CONTRACT_PREFLIGHT_CHECKS = (
    "command_context",
    "project_state",
    "knowledge_target",
    "knowledge_document",
    "knowledge_review_freshness",
    "roadmap",
    "conventions",
    "research_artifacts",
    "verification_reports",
    "manuscript",
    "artifact_manifest",
    "bibliography_audit",
    "bibliography_audit_clean",
    "compiled_manuscript",
    "publication_blockers",
    "review_ledger",
    "review_ledger_valid",
    "referee_decision",
    "referee_decision_valid",
    "publication_review_outcome",
    "reproducibility_manifest",
    "reproducibility_ready",
    "manuscript_proof_review",
    "referee_report_source",
    "phase_lookup",
    "phase_artifacts",
    "phase_summaries",
    "phase_proof_review",
)

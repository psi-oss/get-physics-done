"""Tiny dependency-free strings shared by model-visible prompt wrappers."""

from __future__ import annotations

__all__ = [
    "agent_visibility_note",
    "command_visibility_note",
    "REVIEW_CONTRACT_CONDITIONAL_WHENS",
    "REVIEW_CONTRACT_FRONTMATTER_KEY",
    "REVIEW_CONTRACT_MODES",
    "REVIEW_CONTRACT_PREFLIGHT_CHECKS",
    "REVIEW_CONTRACT_PROMPT_WRAPPER_KEY",
    "REVIEW_CONTRACT_REQUIRED_STATES",
    "REVIEW_CONTRACT_WRAPPER_KEYS",
    "review_contract_visibility_note",
]

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


def _join_disjunction(values: tuple[str, ...]) -> str:
    return " or ".join(f"`{value}`" for value in values)


def agent_visibility_note() -> str:
    return (
        "Model-visible agent requirements. Follow this YAML. "
        "Closed schema; no extra keys. "
        "Use only the declared enum values for `commit_authority`, `surface`, `role_family`, "
        "`artifact_write_authority`, and `shared_state_authority`."
    )


def command_visibility_note() -> str:
    return (
        "Model-visible command constraints. Follow this YAML. "
        "Closed schema; no extra keys. "
        "Strict booleans only. "
        "Use only declared values for `context_mode` and `agent`; "
        "`project_reentry_capable` must be `true` or `false`."
    )


def review_contract_visibility_note() -> str:
    review_modes = _join_disjunction(REVIEW_CONTRACT_MODES)
    conditional_whens = _join_disjunction(REVIEW_CONTRACT_CONDITIONAL_WHENS)
    return (
        "Review contract schema. Follow this YAML. "
        "Closed schema; no extra keys. "
        f"`{REVIEW_CONTRACT_PROMPT_WRAPPER_KEY}` is the wrapper key; `schema_version` must be `1`; "
        f"`review_mode` must be {review_modes}; "
        f"`conditional_requirements[].when` must be one of {conditional_whens}; "
        "`conditional_requirements[].blocking_preflight_checks` must reuse declared `preflight_checks`."
    )

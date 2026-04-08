"""Shared strings for model-visible prompt wrappers."""

from __future__ import annotations

from gpd.core.model_visible_sections import (
    MODEL_VISIBLE_CLOSED_SCHEMA_PHRASE,
    render_model_visible_note,
)

__all__ = [
    "agent_visibility_note",
    "command_visibility_note",
    "MODEL_VISIBLE_CLOSED_SCHEMA_PHRASE",
    "AGENT_ARTIFACT_WRITE_AUTHORITIES",
    "AGENT_COMMIT_AUTHORITIES",
    "AGENT_ROLE_FAMILIES",
    "AGENT_SHARED_STATE_AUTHORITIES",
    "AGENT_SURFACES",
    "VALID_CONTEXT_MODES",
    "REVIEW_CONTRACT_CONDITIONAL_WHENS",
    "REVIEW_CONTRACT_FRONTMATTER_KEY",
    "REVIEW_CONTRACT_MODES",
    "REVIEW_CONTRACT_PREFLIGHT_CHECKS",
    "REVIEW_CONTRACT_PROMPT_WRAPPER_KEY",
    "REVIEW_CONTRACT_REQUIRED_STATES",
    "REVIEW_CONTRACT_WRAPPER_KEYS",
    "SKEPTICAL_RIGOR_GUARDRAILS_HEADING",
    "review_contract_visibility_note",
    "skeptical_rigor_guardrails_section",
]

REVIEW_CONTRACT_FRONTMATTER_KEY = "review-contract"
REVIEW_CONTRACT_PROMPT_WRAPPER_KEY = "review_contract"
REVIEW_CONTRACT_WRAPPER_KEYS = (
    REVIEW_CONTRACT_PROMPT_WRAPPER_KEY,
    REVIEW_CONTRACT_FRONTMATTER_KEY,
)
SKEPTICAL_RIGOR_GUARDRAILS_HEADING = "Scientific Rigor Guardrails"
VALID_CONTEXT_MODES = ("global", "projectless", "project-aware", "project-required")
AGENT_COMMIT_AUTHORITIES = ("direct", "orchestrator")
AGENT_SURFACES = ("public", "internal")
AGENT_ROLE_FAMILIES = ("worker", "analysis", "verification", "review", "coordination")
AGENT_ARTIFACT_WRITE_AUTHORITIES = ("scoped_write", "read_only")
AGENT_SHARED_STATE_AUTHORITIES = ("return_only", "direct")
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
_EPISTEMIC_GUARDRAIL_CLAUSES = (
    "Apply scientific skepticism and critical thinking. Stress-test both the user's preferred explanation and your own first impression without treating the user as an adversary.",
    "Prefer skeptical verification, disconfirming evidence, and explicit uncertainty over agreeable affirmation.",
    "Do not claim any result, citation, file, or artifact exists unless you directly observed it in the provided context or produced it in this session.",
    "If search, execution, or generation fails, report the failure plainly instead of inventing fallback content.",
)


def _join_disjunction(values: tuple[str, ...]) -> str:
    return " or ".join(f"`{value}`" for value in values)


def _command_agent_labels() -> tuple[str, ...]:
    try:
        from gpd.registry import canonical_agent_names
    except Exception:
        return ()
    return canonical_agent_names()


def agent_visibility_note() -> str:
    return render_model_visible_note(
        "Agent YAML rules.",
        "`tools` is a list of tool names;",
        f"`commit_authority` must be {_join_disjunction(AGENT_COMMIT_AUTHORITIES)};",
        f"`surface` must be {_join_disjunction(AGENT_SURFACES)};",
        f"`role_family` must be {_join_disjunction(AGENT_ROLE_FAMILIES)};",
        f"`artifact_write_authority` must be {_join_disjunction(AGENT_ARTIFACT_WRITE_AUTHORITIES)};",
        f"`shared_state_authority` must be {_join_disjunction(AGENT_SHARED_STATE_AUTHORITIES)}.",
        *_EPISTEMIC_GUARDRAIL_CLAUSES,
    )


def command_visibility_note() -> str:
    agent_labels = _command_agent_labels()
    agent_clause = (
        f"`agent` when present must be one of {_join_disjunction(agent_labels)};"
        if agent_labels
        else "`agent` when present must match a built-in canonical agent label exactly;"
    )
    return render_model_visible_note(
        "Command YAML rules.",
        "Strict booleans only.",
        f"`context_mode` must be {_join_disjunction(VALID_CONTEXT_MODES)};",
        "`allowed_tools` is a list of tool names when present;",
        "`requires` is a closed mapping when present; only `files` is supported.",
        "`requires.files` is a string or list of strings.",
        "Empty optional fields may be omitted.",
        agent_clause,
        "`project_reentry_capable` must be `true` or `false` and may be `true` only when `context_mode` is `project-required`.",
        "Missing required files or other decisive evidence are blocking for strong claims; do not treat omissions or proxies as success.",
        *_EPISTEMIC_GUARDRAIL_CLAUSES,
    )


def review_contract_visibility_note() -> str:
    review_modes = _join_disjunction(REVIEW_CONTRACT_MODES)
    conditional_whens = _join_disjunction(REVIEW_CONTRACT_CONDITIONAL_WHENS)
    required_states = _join_disjunction(REVIEW_CONTRACT_REQUIRED_STATES)
    preflight_checks = _join_disjunction(REVIEW_CONTRACT_PREFLIGHT_CHECKS)
    return render_model_visible_note(
        "Review-contract YAML rules.",
        f"`{REVIEW_CONTRACT_PROMPT_WRAPPER_KEY}` is the wrapper key; `schema_version` must be the integer `1`;",
        "Empty optional fields may be omitted.",
        f"`review_mode` must be {review_modes};",
        f"`required_state` when present must be {required_states};",
        "`required_outputs`, `required_evidence`, `blocking_conditions`, `preflight_checks`, and `stage_artifacts` are lists when present;",
        f"`preflight_checks` entries must be {preflight_checks};",
        f"`conditional_requirements[].when` must be one of {conditional_whens};",
        "`conditional_requirements[].blocking_preflight_checks` is a list when present and its entries must also appear in the top-level `preflight_checks` list.",
        "Each `conditional_requirements[].when` value may appear at most once.",
        "List fields reject blank entries and duplicates.",
        "Each conditional requirement must declare at least one non-empty field.",
        "Missing required outputs or evidence must stay explicit; do not omit, invent, or replace them with proxies.",
        *_EPISTEMIC_GUARDRAIL_CLAUSES,
    )


def skeptical_rigor_guardrails_section() -> str:
    return (
        f"## {SKEPTICAL_RIGOR_GUARDRAILS_HEADING}\n\n"
        "- Use scientific skepticism and critical thinking by default: look for contradictions, missing anchors, overclaims, "
        "and failure modes before endorsing a result.\n"
        "- Stress-test claims, including the user's preferred interpretation and your own first impression, without "
        "framing the user as an opponent.\n"
        "- Agreement is not evidence. Do not mirror a preferred conclusion or a document's self-description unless "
        "the supporting evidence is actually present.\n"
        "- Ground claims in inspected artifacts, cited sources, executed checks, or explicitly labeled background knowledge.\n"
        "- If information or artifacts cannot be found, produced, read, verified, or reproduced, report that plainly and "
        "keep the status missing, failed, blocked, or inconclusive.\n"
        "- Never fabricate references, numbers, derivations, files, figures, tables, logs, summaries, proofs, or claimed "
        "task completion. Do not use ungrounded fallback content as a substitute for missing evidence or failed execution.\n"
        "- When certainty is not warranted, narrow the claim, lower confidence, and name the weakest anchor or "
        "disconfirming check still needed.\n"
    )

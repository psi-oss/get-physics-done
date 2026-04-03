"""Focused regressions for CLAIMS{round_suffix}.json schema visibility in review-reader prompts."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

from gpd.adapters.install_utils import expand_at_includes
from gpd.mcp.paper.models import (
    ClaimIndex,
    ClaimRecord,
    ClaimType,
    ProofAuditRecord,
    ProofAuditStatus,
    ReviewConfidence,
    ReviewFinding,
    ReviewIssueSeverity,
    ReviewRecommendation,
    ReviewStageKind,
    ReviewSupportStatus,
    StageReviewReport,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"


def _between(text: str, start: str, end: str) -> str:
    _, start_marker, tail = text.partition(start)
    assert start_marker, f"Missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"Missing marker: {end}"
    return body


def _assert_schema_tokens_visible(text: str) -> None:
    for token in (*ClaimIndex.model_fields, *ClaimRecord.model_fields):
        assert f"`{token}`" in text or f'"{token}"' in text, f"Missing schema token: {token}"
    for claim_type in ClaimType:
        assert claim_type.value in text, f"Missing claim type: {claim_type.value}"
    for claim_kind in get_args(ClaimRecord.model_fields["claim_kind"].annotation):
        assert claim_kind in text, f"Missing claim kind: {claim_kind}"


def _assert_stage_review_schema_tokens_visible(text: str) -> None:
    for token in (*StageReviewReport.model_fields, *ReviewFinding.model_fields):
        assert f"`{token}`" in text or f'"{token}"' in text, f"Missing schema token: {token}"
    for token in ProofAuditRecord.model_fields:
        assert f"`{token}`" in text or f'"{token}"' in text, f"Missing proof-audit schema token: {token}"
    for severity in ReviewIssueSeverity:
        assert severity.value in text, f"Missing severity: {severity.value}"
    for support_status in ReviewSupportStatus:
        assert support_status.value in text, f"Missing support status: {support_status.value}"
    for confidence in ReviewConfidence:
        assert confidence.value in text, f"Missing confidence: {confidence.value}"
    for recommendation in ReviewRecommendation:
        assert recommendation.value in text, f"Missing recommendation: {recommendation.value}"
    for status in ProofAuditStatus:
        assert status.value in text, f"Missing proof-audit status: {status.value}"


def _assert_stage_review_contract_visible(text: str, stage_kind: str) -> None:
    _assert_stage_review_schema_tokens_visible(text)
    assert f"`stage_id` and `stage_kind` must both be `{stage_kind}`" in text
    assert "JSON `round` field must agree" in text
    assert "`manuscript_path` must be non-empty" in text
    assert "must exactly match the sibling `CLAIMS{round_suffix}.json`" in text
    assert "`claims_reviewed` must be an array of Stage 1 `CLM-...` claim IDs" in text
    assert "`manuscript_sha256` must exactly match the sibling `CLAIMS{round_suffix}.json`" in text
    assert "`manuscript_sha256` must be the lowercase 64-hex digest" in text
    assert "closed schema" in text
    assert "do not invent extra keys" in text
    assert "`claim_ids` must reuse Stage 1 `CLM-...` claim IDs" in text
    assert "`issue_id` must use `REF-...`" in text


def test_review_reader_prompt_surfaces_full_claim_index_schema() -> None:
    review_reader = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    claims_schema = _between(
        review_reader,
        "Required schema for `CLAIMS{round_suffix}.json` (`ClaimIndex`):",
        "Required schema for `STAGE-reader{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):",
    )

    _assert_schema_tokens_visible(claims_schema)
    assert "closed schema" in claims_schema
    assert "do not invent extra keys" in claims_schema
    assert "do not omit them" in claims_schema
    assert "must be non-empty" in claims_schema
    assert "lowercase 64-hex digest" in claims_schema
    assert "CLM-[A-Za-z0-9][A-Za-z0-9_-]*" in claims_schema
    assert "theorem-bearing" in claims_schema
    assert "Do not silently drop statement parameters" in claims_schema
    assert "CLAIMS.json" not in claims_schema
    assert "round-specific variant when instructed" not in claims_schema


def test_review_reader_prompt_surfaces_full_stage_review_schema() -> None:
    review_reader = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    stage_schema = _between(
        review_reader,
        "Required schema for `STAGE-reader{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):",
        "</artifact_format>",
    )

    _assert_stage_review_contract_visible(stage_schema, ReviewStageKind.reader.value)
    assert "not the final referee decision" in stage_schema
    assert "STAGE-reader.json" not in stage_schema
    assert "round-specific variant when instructed" not in stage_schema


def test_peer_review_panel_reference_surfaces_stage1_claim_index_schema() -> None:
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    claims_schema = _between(
        panel,
        "Stage 1 `CLAIMS{round_suffix}.json` must follow this compact `ClaimIndex` shape:",
        "The final adjudicator JSON artifacts must follow these canonical schemas:",
    )

    _assert_schema_tokens_visible(claims_schema)
    assert "closed schema" in claims_schema
    assert "do not invent extra keys" in claims_schema
    assert "required `ClaimIndex` metadata" in claims_schema
    assert "lowercase 64-hex digest" in claims_schema
    assert "CLM-[A-Za-z0-9][A-Za-z0-9_-]*" in claims_schema
    assert "Stage 1 `CLAIMS.json` must follow this compact `ClaimIndex` shape:" not in panel


def test_expanded_review_reader_prompt_keeps_claim_index_metadata_visible() -> None:
    expanded = expand_at_includes(
        (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd/specs",
        "/runtime/",
    )

    assert "Peer Review Panel Protocol" in expanded
    assert '"manuscript_path": "paper/topic_stem.tex"' in expanded
    assert '"manuscript_sha256": "<sha256>"' in expanded
    assert '"supporting_artifacts": ["paper/figures/main-result.pdf"]' in expanded


def test_review_literature_prompt_surfaces_full_stage_review_schema() -> None:
    literature = (AGENTS_DIR / "gpd-review-literature.md").read_text(encoding="utf-8")
    stage_schema = _between(
        literature,
        "Required schema for `STAGE-literature{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):",
        "Required finding coverage:",
    )

    _assert_stage_review_contract_visible(stage_schema, ReviewStageKind.literature.value)
    assert "GPD/review/STAGE-literature{round_suffix}.json" in literature
    assert "STAGE-literature.json" not in literature


def test_stage_review_agents_surface_compact_stage_review_schema() -> None:
    for agent_name, marker, stage_kind in (
        (
            "gpd-review-math.md",
            "Required schema for `STAGE-math{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):",
            "math",
        ),
        (
            "gpd-review-physics.md",
            "Required schema for `STAGE-physics{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):",
            "physics",
        ),
        (
            "gpd-review-significance.md",
            "Required schema for `STAGE-interestingness{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):",
            "interestingness",
        ),
    ):
        expanded = expand_at_includes(
            (AGENTS_DIR / agent_name).read_text(encoding="utf-8"),
            REPO_ROOT / "src/gpd/specs",
            "/runtime/",
        )
        schema = _between(expanded, marker, "Required finding coverage:")
        _assert_stage_review_contract_visible(schema, stage_kind)
        assert "do not collapse them to prose or scalars" in schema
        assert "{round_suffix}.json" in expanded
        assert "round-specific variant" not in expanded


def test_review_math_prompt_requires_theorem_to_proof_audits() -> None:
    review_math = (AGENTS_DIR / "gpd-review-math.md").read_text(encoding="utf-8")

    assert "audit theorem-to-proof alignment explicitly" in review_math
    assert "emit exactly one `proof_audits[]` entry" in review_math
    assert "`claim_id` is also present in `claims_reviewed`" in review_math
    assert "Do not emit proof audits for unreviewed claims" in review_math
    assert "do not repeat `claim_id` values" in review_math
    assert "The 3-5-step sampling rule does not waive full theorem inventory coverage" in review_math
    assert "silently specialized proof" in review_math
    assert "never use `alignment_status: not_applicable`" in review_math
    assert "Aligned theorem-bearing audits must include non-empty `proof_locations`" in review_math
    assert "`issue_id` must match `REF-[A-Za-z0-9][A-Za-z0-9_-]*`" in review_math


def test_check_proof_prompt_requires_fail_closed_proof_inventory_and_adversarial_probe() -> None:
    check_proof = (AGENTS_DIR / "gpd-check-proof.md").read_text(encoding="utf-8")

    assert "You are the proof-critique specialist for theorem-bearing work." in check_proof
    assert "`reviewer: gpd-check-proof`" in check_proof
    assert "`manuscript_path: path/to/manuscript.tex`" in check_proof
    assert "`manuscript_sha256: <lowercase 64-hex digest>`" in check_proof
    assert "`round: <review round number>`" in check_proof
    assert "must exactly match the active theorem-bearing Stage 1 claim IDs under review" in check_proof
    assert "must be non-empty, every entry must resolve to a readable proof artifact" in check_proof
    assert "must exactly match the active manuscript snapshot under review" in check_proof
    assert "must exactly match the active review round" in check_proof
    assert "## Proof Inventory" in check_proof
    assert "## Coverage Ledger" in check_proof
    assert "### Named-Parameter Coverage" in check_proof
    assert "### Hypothesis Coverage" in check_proof
    assert "### Quantifier / Domain Coverage" in check_proof
    assert "### Conclusion-Clause Coverage" in check_proof
    assert "## Adversarial Probe" in check_proof
    assert "Exact claim / theorem text" in check_proof
    assert "If a named parameter from the statement never appears in the proof logic, mark it as uncovered and fail closed." in check_proof
    assert "For manuscript-scoped artifacts, do not omit `manuscript_path`, `manuscript_sha256`, or `round`" in check_proof
    assert "must exactly bind to the active review context supplied by the orchestrator" in check_proof
    assert "fail closed instead of approximating" in check_proof
    assert "Do not rewrite the theorem into the special case that was actually proved." in check_proof


def test_referee_and_panel_prompts_require_mandatory_theorem_bearing_proof_artifacts() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")

    assert "Treat theorem-bearing status from the full Stage 1 claim record" in referee
    assert "central theorem-bearing claim" in referee
    assert "matching passed `PROOF-REDTEAM{round_suffix}.md` artifact" in referee

    assert "When theorem-bearing claims exist, `PROOF-REDTEAM{round_suffix}.md` is mandatory Stage 6 input" in panel
    assert "missing, invalid, or non-passing `PROOF-REDTEAM{round_suffix}.md` artifact is itself a blocking stage-integrity failure" in panel
    assert "every reviewed theorem-bearing Stage 1 claim must receive exactly one `proof_audits[]` entry" in panel
    assert "must also appear in `claims_reviewed`" in panel
    assert "theorem-bearing audits must resolve to `aligned`, `partially_aligned`, or `misaligned`" in panel
    assert "Every nested `ReviewFinding.issue_id` must match `REF-[A-Za-z0-9][A-Za-z0-9_-]*`." in panel

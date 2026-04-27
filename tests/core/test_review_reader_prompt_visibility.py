"""Prompt-visibility assertions for the review agents."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes
from gpd.mcp.paper.models import (
    ReviewConfidence,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    ReviewRecommendation,
    ReviewStageKind,
    ReviewSupportStatus,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
SPEC_ROOT = REPO_ROOT / "src/gpd/specs"


def _read(agent_name: str) -> str:
    return (AGENTS_DIR / agent_name).read_text(encoding="utf-8")


def _expanded(agent_name: str) -> str:
    return expand_at_includes(_read(agent_name), SPEC_ROOT, "/runtime/")


def _enum_line(field_name: str, enum_type: type[object]) -> str:
    values = " | ".join(member.value for member in enum_type)
    return f"{field_name}: {values}"


def _assert_shared_contract_pointer(text: str, contract_fragment: str) -> None:
    assert "references/publication/peer-review-panel.md" in text
    assert contract_fragment in text
    assert "Do not restate that schema here." in text
    assert "Required schema for" not in text
    assert "closed schema; do not invent extra keys" not in text


def test_review_reader_prompt_keeps_shared_contract_visible() -> None:
    review_reader = _read("gpd-review-reader.md")
    _assert_shared_contract_pointer(
        review_reader,
        "full `ClaimIndex` and `StageReviewReport` contracts",
    )
    assert "Stage 1 must also emit `GPD/review/CLAIMS{round_suffix}.json`." in review_reader
    assert "Capture theorem kind, explicit hypotheses, and free target parameters for theorem-like claims." in review_reader
    assert "Keep `proof_audits` empty in this stage." in review_reader
    assert "Focus `findings` on overclaiming, missing promised deliverables, and claim-structure blockers." in review_reader

    expanded = _expanded("gpd-review-reader.md")
    assert "Peer Review Panel Protocol" not in expanded
    assert "Stage 1 `CLAIMS{round_suffix}.json` must follow this compact `ClaimIndex` shape:" not in expanded
    assert "StageReviewReport`, nested `ReviewFinding`, and nested `ProofAuditRecord` entries use a closed schema" not in expanded


def test_review_stage_prompts_keep_only_stage_specific_deltas() -> None:
    cases = (
        (
            "gpd-review-literature.md",
            "full `StageReviewReport` contract",
            (
                "Keep `proof_audits` empty in this stage.",
                "Focus `findings` on claimed advance, directly relevant prior work, missing or misused citations, and novelty assessment.",
                "Escalate to `reject` when prior work already contains the main result or the novelty framing is materially false.",
                "Escalate to `major_revision` when literature positioning needs substantial repair.",
            ),
        ),
        (
            "gpd-review-math.md",
            "full `StageReviewReport` contract",
            (
                "For every reviewed theorem-bearing Stage 1 claim, emit exactly one `proof_audits[]` entry whose `claim_id` is also present in `claims_reviewed`.",
                "Do not emit proof audits for unreviewed claims, and do not repeat `claim_id` values.",
                "The theorem-to-proof audit must record what the proof actually uses, what it silently specializes away, and any remaining coverage gaps.",
                "Keep the focus on key equations, limits, cross-checks, approximation notes, and theorem-to-proof alignment.",
                "`recommendation_ceiling` must drop to `major_revision` or `reject` for central theorem-proof gaps or missing audits.",
            ),
        ),
        (
            "gpd-review-physics.md",
            "full `StageReviewReport` contract",
            (
                "Keep `proof_audits` empty in this stage unless the workflow explicitly asks for a theorem-to-proof spot check.",
                "Focus `findings` on stated physical assumptions, regime of validity, supported physical conclusions, and unsupported or overstated connections.",
                "Treat formal resemblance as insufficient evidence for a physical conclusion.",
                "Escalate `recommendation_ceiling` to `major_revision` or worse whenever central physical conclusions outrun the actual evidence.",
            ),
        ),
        (
            "gpd-review-significance.md",
            "full `StageReviewReport` contract",
            (
                "Keep `proof_audits` empty in this stage.",
                "Focus `findings` on why the result might matter, why it might not, venue fit, and claim proportionality.",
                "Be explicit when the paper is technically competent but scientifically mediocre.",
                "Escalate `recommendation_ceiling` to `reject` for PRL/Nature-style venues when significance or venue fit is weak.",
                "Escalate to at least `major_revision` when the paper is technically competent but physically uninteresting or overclaimed.",
            ),
        ),
    )

    for agent_name, contract_fragment, deltas in cases:
        text = _read(agent_name)
        _assert_shared_contract_pointer(text, contract_fragment)
        for fragment in deltas:
            assert fragment in text

        expanded = _expanded(agent_name)
        assert "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" in expanded
        assert "Peer Review Panel Protocol" not in expanded
        assert "Stage 1 `CLAIMS{round_suffix}.json` must follow this compact `ClaimIndex` shape:" not in expanded
        assert "StageReviewReport`, nested `ReviewFinding`, and nested `ProofAuditRecord` entries use a closed schema" not in expanded


def test_peer_review_panel_protocol_surfaces_full_review_enum_vocabularies() -> None:
    protocol = (SPEC_ROOT / "references" / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    review_reader = _read("gpd-review-reader.md")
    expanded = _expanded("gpd-review-reader.md")
    expected_lines = (
        _enum_line("stage_kind", ReviewStageKind),
        _enum_line("findings[].severity", ReviewIssueSeverity),
        _enum_line("findings[].support_status", ReviewSupportStatus),
        _enum_line("confidence", ReviewConfidence),
        _enum_line("recommendation_ceiling", ReviewRecommendation),
        _enum_line("issues[].opened_by_stage", ReviewStageKind),
        _enum_line("issues[].status", ReviewIssueStatus),
        _enum_line("final_recommendation", ReviewRecommendation),
        _enum_line("final_confidence", ReviewConfidence),
    )

    for line in expected_lines:
        assert line in protocol
    assert "references/publication/peer-review-panel.md" in review_reader
    assert "Peer Review Panel Protocol" not in expanded

"""Pydantic models for paper configuration, output, and review metadata."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from gpd.mcp.paper.bibliography import BibliographyAudit

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{64}$")]
ClaimId = Annotated[str, Field(pattern=r"^CLM-[A-Za-z0-9][A-Za-z0-9_-]*$")]
ReviewIssueId = Annotated[str, Field(pattern=r"^REF-[A-Za-z0-9][A-Za-z0-9_-]*$")]


class Author(BaseModel):
    """Paper author with affiliation."""

    name: str
    email: str = ""
    affiliation: str = ""


class Section(BaseModel):
    """A paper section with title and LaTeX content."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(alias="heading")
    content: str
    label: str = ""


class FigureRef(BaseModel):
    """Reference to a figure file with metadata."""

    path: Path
    caption: str
    label: str
    width: str = r"\columnwidth"
    double_column: bool = False


class ArtifactSourceRef(BaseModel):
    """A source artifact or upstream input associated with an emitted paper artifact."""

    path: str
    role: str = ""


class ArtifactRecord(BaseModel):
    """Machine-readable record for an emitted paper artifact."""

    artifact_id: str
    category: Literal["tex", "bib", "figure", "pdf", "audit"]
    path: str
    sha256: str
    produced_by: str
    sources: list[ArtifactSourceRef] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ArtifactManifest(BaseModel):
    """Manifest describing the concrete paper artifacts emitted by the build."""

    version: int = 1
    paper_title: str
    journal: str
    created_at: str
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class ClaimType(StrEnum):
    """Types of manuscript claims that deserve explicit referee scrutiny."""

    main_result = "main_result"
    novelty = "novelty"
    significance = "significance"
    physical_interpretation = "physical_interpretation"
    generality = "generality"
    method = "method"


class ReviewStageKind(StrEnum):
    """Staged peer-review passes for fresh-context reviewers."""

    reader = "reader"
    literature = "literature"
    math = "math"
    physics = "physics"
    interestingness = "interestingness"
    meta = "meta"


class ReviewRecommendation(StrEnum):
    """Canonical referee recommendations."""

    accept = "accept"
    minor_revision = "minor_revision"
    major_revision = "major_revision"
    reject = "reject"


class ReviewConfidence(StrEnum):
    """Confidence tag for staged review outputs."""

    high = "high"
    medium = "medium"
    low = "low"


class ReviewIssueSeverity(StrEnum):
    """Severity levels for staged review findings."""

    critical = "critical"
    major = "major"
    minor = "minor"
    suggestion = "suggestion"


class ReviewSupportStatus(StrEnum):
    """Whether a claim is actually supported by the cited manuscript evidence."""

    supported = "supported"
    partially_supported = "partially_supported"
    unsupported = "unsupported"
    unclear = "unclear"


class ReviewIssueStatus(StrEnum):
    """Lifecycle status for an issue in the review ledger."""

    open = "open"
    carried_forward = "carried_forward"
    resolved = "resolved"


class ClaimRecord(BaseModel):
    """Compact claim index emitted before specialist review passes."""

    model_config = ConfigDict(extra="forbid")

    claim_id: ClaimId
    claim_type: ClaimType
    text: str
    artifact_path: str
    section: str = ""
    equation_refs: list[str] = Field(default_factory=list)
    figure_refs: list[str] = Field(default_factory=list)
    supporting_artifacts: list[str] = Field(default_factory=list)


class ClaimIndex(BaseModel):
    """Machine-readable index of manuscript claims for staged peer review."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    manuscript_path: str
    manuscript_sha256: Sha256Hex
    claims: list[ClaimRecord] = Field(default_factory=list)


class ReviewFinding(BaseModel):
    """One staged-review finding tied to specific claims and evidence."""

    model_config = ConfigDict(extra="forbid")

    issue_id: ReviewIssueId
    claim_ids: list[ClaimId] = Field(default_factory=list)
    severity: ReviewIssueSeverity
    summary: str
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    manuscript_locations: list[str] = Field(default_factory=list)
    support_status: ReviewSupportStatus = ReviewSupportStatus.unclear
    blocking: bool = False
    required_action: str = ""


class StageReviewReport(BaseModel):
    """Compact artifact written by one fresh-context review stage."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    round: int = 1
    stage_id: str
    stage_kind: ReviewStageKind
    manuscript_path: str
    manuscript_sha256: Sha256Hex
    claims_reviewed: list[ClaimId] = Field(default_factory=list)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    confidence: ReviewConfidence
    recommendation_ceiling: ReviewRecommendation


class ReviewIssue(BaseModel):
    """Issue carried into the canonical referee ledger."""

    model_config = ConfigDict(extra="forbid")

    issue_id: ReviewIssueId
    opened_by_stage: ReviewStageKind
    severity: ReviewIssueSeverity
    blocking: bool = False
    claim_ids: list[ClaimId] = Field(default_factory=list)
    summary: str
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    required_action: str = ""
    status: ReviewIssueStatus = ReviewIssueStatus.open


class ReviewLedger(BaseModel):
    """Persistent issue ledger shared between peer review and author response."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    round: int = 1
    manuscript_path: str
    issues: list[ReviewIssue] = Field(default_factory=list)


class ReviewPanelBundle(BaseModel):
    """Bundle tying staged review artifacts to the final referee decision."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    round: int = 1
    manuscript_path: str
    target_journal: str = "unspecified"
    claim_index_path: str
    stage_reports: list[str] = Field(default_factory=list)
    review_ledger_path: str
    decision_path: str
    final_recommendation: ReviewRecommendation
    final_confidence: ReviewConfidence
    final_report_path: str
    final_report_tex_path: str = ""


class JournalSpec(BaseModel):
    """Specification for a journal's LaTeX configuration."""

    key: str
    document_class: str
    class_options: list[str]
    bib_style: str
    column_width_cm: float
    double_width_cm: float
    max_height_cm: float
    dpi: int
    preferred_formats: list[str]
    compiler: str = "pdflatex"
    texlive_package: str
    required_tex_files: list[str] = Field(default_factory=list)
    install_hint: str = ""


class PaperConfig(BaseModel):
    """Complete configuration for generating a paper."""

    title: str
    authors: list[Author]
    abstract: str
    sections: list[Section]
    figures: list[FigureRef] = Field(default_factory=list)
    acknowledgments: str = ""
    bib_file: str = "references"
    journal: str = "prl"
    appendix_sections: list[Section] = Field(default_factory=list)
    attribution_footer: str = "Generated with Get Physics Done"


class PaperOutput(BaseModel):
    """Output from the paper build pipeline."""

    tex_content: str
    bib_content: str
    figures_dir: Path | None = None
    pdf_path: Path | None = None
    bibliography_audit_path: Path | None = None
    bibliography_audit: BibliographyAudit | None = None
    manifest_path: Path | None = None
    manifest: ArtifactManifest | None = None
    success: bool
    errors: list[str] = Field(default_factory=list)

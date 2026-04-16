"""Pydantic models for paper configuration, output, and review metadata."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationInfo, field_validator, model_validator

from gpd.contracts import statement_looks_theorem_like
from gpd.mcp.paper.bibliography import BibliographyAudit

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ClaimId = Annotated[str, Field(pattern=r"^CLM-[A-Za-z0-9][A-Za-z0-9_-]*$")]
ReviewIssueId = Annotated[str, Field(pattern=r"^REF-[A-Za-z0-9][A-Za-z0-9_-]*$")]
BuilderJournalKey = Literal["prl", "apj", "mnras", "nature", "jhep", "jfm"]
_LEGACY_LABEL_PREFIXES = ("sec:", "fig:", "app:")
_BIB_FILE_STEM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
REQUIRED_GPD_ACKNOWLEDGMENT = (
    "This research made use of Get Physics Done (GPD) and was supported in part by a "
    "GPD Research Grant from Physical Superintelligence PBC (PSI)."
)


def _require_nonempty_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def _normalize_label_id(value: str, *, allow_blank: bool) -> str:
    normalized = value.strip()
    if not normalized:
        if allow_blank:
            return ""
        raise ValueError("label must be a non-empty string")
    for prefix in _LEGACY_LABEL_PREFIXES:
        if normalized.startswith(prefix):
            raise ValueError(
                f"label must omit the legacy {prefix!r} prefix; use the bare identifier because the renderer adds it"
            )
    return normalized


def normalize_acknowledgments(value: str) -> str:
    """Ensure the required GPD acknowledgment is always present exactly once."""

    normalized = value.strip()
    if not normalized:
        return REQUIRED_GPD_ACKNOWLEDGMENT
    normalized_compact = " ".join(normalized.split())
    required_compact = " ".join(REQUIRED_GPD_ACKNOWLEDGMENT.split())
    if required_compact in normalized_compact:
        return normalized
    return f"{normalized}\n\n{REQUIRED_GPD_ACKNOWLEDGMENT}"


class Author(BaseModel):
    """Paper author with affiliation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str = ""
    affiliation: str = ""

    @field_validator("name")
    @classmethod
    def _validate_nonempty_name(cls, value: str) -> str:
        return _require_nonempty_text(value, field_name="name")


class Section(BaseModel):
    """A paper section with title and LaTeX content."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: str = Field(alias="heading")
    content: str
    label: str = ""

    @field_validator("title", "content")
    @classmethod
    def _validate_nonempty_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_nonempty_text(value, field_name=info.field_name)

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str) -> str:
        return _normalize_label_id(value, allow_blank=True)


class FigureRef(BaseModel):
    """Reference to a figure file with metadata."""

    model_config = ConfigDict(extra="forbid")

    path: Path
    caption: str
    label: str
    width: str = r"\columnwidth"
    double_column: StrictBool = False

    @field_validator("caption")
    @classmethod
    def _validate_nonempty_caption(cls, value: str) -> str:
        return _require_nonempty_text(value, field_name="caption")

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str) -> str:
        return _normalize_label_id(value, allow_blank=False)


class ArtifactSourceRef(BaseModel):
    """A source artifact or upstream input associated with an emitted paper artifact."""

    model_config = ConfigDict(extra="forbid")

    path: str
    role: str = ""


class ArtifactRecord(BaseModel):
    """Machine-readable record for an emitted paper artifact."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    category: Literal["tex", "bib", "figure", "pdf", "audit"]
    path: str
    sha256: Sha256Hex
    produced_by: str
    sources: list[ArtifactSourceRef] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ArtifactManifest(BaseModel):
    """Manifest describing the concrete paper artifacts emitted by the build."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    paper_title: str
    journal: BuilderJournalKey
    created_at: str
    artifacts: list[ArtifactRecord] = Field(default_factory=list)

    @field_validator("paper_title")
    @classmethod
    def _validate_paper_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("paper_title must be a non-empty string")
        return normalized

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("created_at must be a non-empty ISO 8601 timestamp")
        try:
            datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at must be an ISO 8601 timestamp") from exc
        return normalized


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


class ProofAuditStatus(StrEnum):
    """Whether a theorem statement and its proof actually line up."""

    aligned = "aligned"
    partially_aligned = "partially_aligned"
    misaligned = "misaligned"
    not_applicable = "not_applicable"


class ProofAuditRecord(BaseModel):
    """Structured theorem-to-proof audit emitted by the math review stage."""

    model_config = ConfigDict(extra="forbid")

    claim_id: ClaimId
    theorem_assumptions_checked: list[str] = Field(default_factory=list)
    theorem_parameters_checked: list[str] = Field(default_factory=list)
    proof_locations: list[str] = Field(default_factory=list)
    uncovered_assumptions: list[str] = Field(default_factory=list)
    uncovered_parameters: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    alignment_status: ProofAuditStatus = ProofAuditStatus.not_applicable
    notes: str = ""

    @model_validator(mode="after")
    def _aligned_audits_cannot_report_gaps(self) -> ProofAuditRecord:
        if self.alignment_status != ProofAuditStatus.aligned:
            return self
        if not self.proof_locations:
            raise ValueError("aligned proof_audits must include proof_locations")
        if not self.theorem_assumptions_checked and not self.theorem_parameters_checked:
            raise ValueError(
                "aligned proof_audits must record at least one checked assumption or checked parameter"
            )
        if self.uncovered_assumptions or self.uncovered_parameters or self.coverage_gaps:
            raise ValueError(
                "aligned proof_audits cannot list uncovered assumptions, uncovered parameters, or coverage gaps"
            )
        return self


class ClaimRecord(BaseModel):
    """Compact claim index emitted before specialist review passes."""

    model_config = ConfigDict(extra="forbid")

    claim_id: ClaimId
    claim_type: ClaimType
    claim_kind: Literal["theorem", "lemma", "corollary", "proposition", "result", "claim", "other"] = "other"
    text: str
    artifact_path: str
    section: str = ""
    equation_refs: list[str] = Field(default_factory=list)
    figure_refs: list[str] = Field(default_factory=list)
    supporting_artifacts: list[str] = Field(default_factory=list)
    theorem_assumptions: list[str] = Field(default_factory=list)
    theorem_parameters: list[str] = Field(default_factory=list)

    @property
    def theorem_bearing(self) -> bool:
        return (
            self.claim_kind in {"theorem", "lemma", "corollary", "proposition", "claim"}
            or bool(self.theorem_assumptions)
            or bool(self.theorem_parameters)
            or statement_looks_theorem_like(self.text)
        )


class ClaimIndex(BaseModel):
    """Machine-readable index of manuscript claims for staged peer review."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    manuscript_path: str
    manuscript_sha256: Sha256Hex
    claims: list[ClaimRecord] = Field(default_factory=list)

    @field_validator("manuscript_path")
    @classmethod
    def _nonempty_manuscript_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("manuscript_path must be non-empty")
        return normalized


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
    blocking: StrictBool = False
    required_action: str = ""


class StageReviewReport(BaseModel):
    """Compact artifact written by one fresh-context review stage."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    round: int = Field(default=1, gt=0)
    stage_id: str
    stage_kind: ReviewStageKind
    manuscript_path: str
    manuscript_sha256: Sha256Hex
    claims_reviewed: list[ClaimId] = Field(default_factory=list)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    proof_audits: list[ProofAuditRecord] = Field(default_factory=list)
    confidence: ReviewConfidence
    recommendation_ceiling: ReviewRecommendation

    @field_validator("manuscript_path")
    @classmethod
    def _nonempty_manuscript_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("manuscript_path must be non-empty")
        return normalized

    @model_validator(mode="after")
    def _stage_id_matches_stage_kind(self) -> StageReviewReport:
        expected_stage_id = self.stage_kind.value
        if self.stage_id != expected_stage_id:
            raise ValueError(f"stage_id must equal stage_kind ({expected_stage_id})")
        return self

    @model_validator(mode="after")
    def _proof_audit_claim_ids_must_be_unique(self) -> StageReviewReport:
        proof_audit_claim_ids = [audit.claim_id for audit in self.proof_audits]
        duplicates = sorted(
            claim_id for claim_id, count in Counter(proof_audit_claim_ids).items() if count > 1
        )
        if duplicates:
            raise ValueError("proof_audits must not repeat claim_id values: " + ", ".join(duplicates))
        return self


class ReviewIssue(BaseModel):
    """Issue carried into the canonical referee ledger."""

    model_config = ConfigDict(extra="forbid")

    issue_id: ReviewIssueId
    opened_by_stage: ReviewStageKind
    severity: ReviewIssueSeverity
    blocking: StrictBool = False
    claim_ids: list[ClaimId] = Field(default_factory=list)
    summary: str
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    required_action: str = ""
    status: ReviewIssueStatus = ReviewIssueStatus.open


class ReviewLedger(BaseModel):
    """Persistent issue ledger shared between peer review and author response."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    round: int = Field(default=1, gt=0)
    manuscript_path: str
    issues: list[ReviewIssue] = Field(default_factory=list)

    @field_validator("manuscript_path")
    @classmethod
    def _nonempty_manuscript_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("manuscript_path must be non-empty")
        return normalized


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


class PaperToolchainCapability(BaseModel):
    """Machine-local paper toolchain capability summary.

    This is intentionally scoped to the shared build environment.  It covers
    the compiler and helper binaries that influence paper generation, but not
    journal-specific class/package readiness.
    """

    model_config = ConfigDict(extra="forbid")

    compiler: str = "pdflatex"
    compiler_available: bool = False
    compiler_path: str | None = None
    distribution: str | None = None
    bibtex_available: bool | None = None
    bibliography_support_available: bool = False
    latexmk_available: bool | None = None
    kpsewhich_available: bool | None = None
    available: bool = False
    full_toolchain_available: bool = False
    paper_build_ready: bool = False
    arxiv_submission_ready: bool = False
    readiness_state: Literal["blocked", "degraded", "ready"] = "blocked"
    message: str = ""
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_derived_status_fields(self) -> PaperToolchainCapability:
        compiler_available = bool(self.compiler_available)
        bibtex_available = self.bibtex_available is True
        latexmk_available = self.latexmk_available is True
        kpsewhich_available = self.kpsewhich_available is True

        self.available = compiler_available
        self.bibliography_support_available = compiler_available and bibtex_available
        self.paper_build_ready = compiler_available
        self.full_toolchain_available = (
            compiler_available and bibtex_available and latexmk_available and kpsewhich_available
        )
        self.arxiv_submission_ready = self.bibliography_support_available and kpsewhich_available
        if not compiler_available:
            self.readiness_state = "blocked"
        elif bibtex_available:
            self.readiness_state = "ready"
        else:
            self.readiness_state = "degraded"
        return self


class PaperConfig(BaseModel):
    """Complete configuration for generating a paper."""

    model_config = ConfigDict(extra="forbid")

    title: str
    authors: list[Author]
    abstract: str
    sections: list[Section]
    figures: list[FigureRef] = Field(default_factory=list)
    acknowledgments: str = REQUIRED_GPD_ACKNOWLEDGMENT
    bib_file: str = "references"
    journal: BuilderJournalKey = "prl"
    appendix_sections: list[Section] = Field(default_factory=list)
    attribution_footer: str = "Generated with Get Physics Done"
    output_filename: str | None = None

    @field_validator("title", "abstract")
    @classmethod
    def _validate_nonempty_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_nonempty_text(value, field_name=info.field_name)

    @field_validator("bib_file")
    @classmethod
    def _validate_bib_file(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("bib_file must be a non-empty stem")
        if not _BIB_FILE_STEM_RE.fullmatch(normalized):
            raise ValueError(
                "bib_file must be a stem-safe filename without path separators or extensions"
            )
        return normalized

    @field_validator("output_filename")
    @classmethod
    def _validate_output_filename(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
            raise ValueError("output_filename must be a filename stem, not a path")
        return normalized

    @model_validator(mode="after")
    def _ensure_required_acknowledgment(self) -> PaperConfig:
        self.acknowledgments = normalize_acknowledgments(self.acknowledgments)
        return self


_MAX_FILENAME_LENGTH = 60
_FILENAME_TOKEN_RE = re.compile(r"[a-z0-9]+")
_OUTPUT_FILENAME_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "the",
        "to",
        "via",
        "with",
    }
)
_FALLBACK_OUTPUT_FILENAME = "paper_draft"


def _title_filename_tokens(title: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return [match.group(0) for match in _FILENAME_TOKEN_RE.finditer(ascii_title)]


def _select_topic_filename_tokens(tokens: list[str]) -> list[str]:
    if not tokens:
        return []

    meaningful = [token for token in tokens if token not in _OUTPUT_FILENAME_STOPWORDS]
    selected = meaningful[:3]
    if len(selected) >= 2 or len(tokens) == 1:
        return selected or tokens[:1]

    for token in tokens:
        if token in selected:
            continue
        selected.append(token)
        if len(selected) >= min(3, len(tokens)):
            break
    return selected[:3] or tokens[:1]


def derive_output_filename(config: PaperConfig) -> str:
    """Derive a filesystem-safe output filename (without extension) from *config*.

    Resolution order:
    1. ``config.output_filename`` if explicitly provided.
    2. Topic-derived short slug from ``config.title`` using 2-3 salient words
       joined with underscores and truncated to 60 characters.
    3. ``"paper_draft"`` as the ultimate fallback when the title is empty.
    """
    if config.output_filename:
        return config.output_filename

    tokens = _title_filename_tokens(config.title.strip())
    selected_tokens = _select_topic_filename_tokens(tokens)
    slug = "_".join(selected_tokens)[:_MAX_FILENAME_LENGTH].strip("_")

    if not slug:
        return _FALLBACK_OUTPUT_FILENAME

    return slug


SUPPORTED_PAPER_JOURNALS = frozenset(get_args(PaperConfig.model_fields["journal"].annotation))


def is_supported_paper_journal(journal: object) -> bool:
    """Return whether *journal* is one of the builder's supported journal keys."""

    return isinstance(journal, str) and journal in SUPPORTED_PAPER_JOURNALS


class PaperOutput(BaseModel):
    """Output from the paper build pipeline."""

    tex_content: str
    bib_content: str
    tex_path: Path
    figures_dir: Path | None = None
    pdf_path: Path | None = None
    bibliography_audit_path: Path | None = None
    bibliography_audit: BibliographyAudit | None = None
    reference_bibtex_keys: dict[str, str] = Field(default_factory=dict)
    manifest_path: Path | None = None
    manifest: ArtifactManifest | None = None
    success: bool
    errors: list[str] = Field(default_factory=list)
    citation_warnings: list[str] = Field(default_factory=list)

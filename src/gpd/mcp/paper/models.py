"""Pydantic models for paper configuration, output, and review metadata."""

from __future__ import annotations

import posixpath
import re
import unicodedata
from collections import Counter
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationInfo, field_validator, model_validator

from gpd.contracts import statement_looks_theorem_like
from gpd.mcp.paper.bibliography import BibliographyAudit, CitationSource

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ClaimId = Annotated[str, Field(pattern=r"^CLM-[A-Za-z0-9][A-Za-z0-9_-]*$")]
ReviewIssueId = Annotated[str, Field(pattern=r"^REF-[A-Za-z0-9][A-Za-z0-9_-]*$")]
BuilderJournalKey = Literal["prl", "apj", "mnras", "nature", "jhep", "jfm"]
SourceNoteId = Annotated[str, Field(pattern=r"^NOTE-[A-Za-z0-9][A-Za-z0-9_-]*$")]
ResultId = Annotated[str, Field(pattern=r"^RES-[A-Za-z0-9][A-Za-z0-9_-]*$")]
FigureAssetId = Annotated[str, Field(pattern=r"^FIG-[A-Za-z0-9][A-Za-z0-9_-]*$")]
_LEGACY_LABEL_PREFIXES = ("sec:", "fig:", "app:")
_BIB_FILE_STEM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SUBJECT_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
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


def _normalize_nonempty_string_list(
    values: list[str],
    *,
    field_name: str,
    allow_empty: bool = True,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = _require_nonempty_text(item, field_name=field_name)
        if value in seen:
            raise ValueError(f"{field_name} must not contain duplicate entries")
        seen.add(value)
        normalized.append(value)
    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must contain at least one entry")
    return normalized


def _duplicate_items(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


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


def _normalize_publication_path_label(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    compact = posixpath.normpath(normalized)
    return "" if compact == "." else compact


def _display_publication_path(project_root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    resolved_root = project_root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


class PublicationPathSemantics(BaseModel):
    """Typed path views for one resolved publication subject."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_path: str = ""
    artifact_base_path: str = ""
    manuscript_root_path: str = ""
    manuscript_entrypoint_path: str = ""
    subject_relative_entrypoint_path: str = ""
    artifact_manifest_path_kind: Literal["artifact_base_relative"] = "artifact_base_relative"
    review_manuscript_path_kind: Literal["project_relative_or_absolute"] = "project_relative_or_absolute"

    @field_validator(
        "subject_path",
        "artifact_base_path",
        "manuscript_root_path",
        "manuscript_entrypoint_path",
        "subject_relative_entrypoint_path",
    )
    @classmethod
    def _normalize_path_labels(cls, value: str) -> str:
        return _normalize_publication_path_label(value)

    @classmethod
    def from_paths(
        cls,
        project_root: Path,
        *,
        subject_path: Path | None,
        artifact_base_path: Path | None,
        manuscript_root_path: Path | None,
        manuscript_entrypoint_path: Path | None,
    ) -> PublicationPathSemantics | None:
        if (
            subject_path is None
            and artifact_base_path is None
            and manuscript_root_path is None
            and manuscript_entrypoint_path is None
        ):
            return None

        subject_relative_entrypoint = ""
        if artifact_base_path is not None and manuscript_entrypoint_path is not None:
            resolved_base = artifact_base_path.resolve(strict=False)
            resolved_entrypoint = manuscript_entrypoint_path.resolve(strict=False)
            try:
                subject_relative_entrypoint = resolved_entrypoint.relative_to(resolved_base).as_posix()
            except ValueError:
                subject_relative_entrypoint = resolved_entrypoint.name

        return cls(
            subject_path=_display_publication_path(project_root, subject_path),
            artifact_base_path=_display_publication_path(project_root, artifact_base_path),
            manuscript_root_path=_display_publication_path(project_root, manuscript_root_path),
            manuscript_entrypoint_path=_display_publication_path(project_root, manuscript_entrypoint_path),
            subject_relative_entrypoint_path=subject_relative_entrypoint,
        )


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


class WritePaperAuthoringSourceNote(BaseModel):
    """One explicit external-authoring source note consumed by ``gpd:write-paper``."""

    model_config = ConfigDict(extra="forbid")

    id: SourceNoteId
    path: str
    summary: str

    @field_validator("path", "summary")
    @classmethod
    def _validate_nonempty_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_nonempty_text(value, field_name=info.field_name)


class WritePaperAuthoringResult(BaseModel):
    """One optional result bundle with explicit upstream note bindings."""

    model_config = ConfigDict(extra="forbid")

    id: ResultId
    summary: str
    source_note_ids: list[SourceNoteId]

    @field_validator("summary")
    @classmethod
    def _validate_nonempty_summary(cls, value: str) -> str:
        return _require_nonempty_text(value, field_name="summary")

    @field_validator("source_note_ids")
    @classmethod
    def _validate_source_note_ids(cls, value: list[str]) -> list[str]:
        return _normalize_nonempty_string_list(value, field_name="source_note_ids", allow_empty=False)


class WritePaperAuthoringFigure(BaseModel):
    """One optional figure candidate with explicit upstream note bindings."""

    model_config = ConfigDict(extra="forbid")

    id: FigureAssetId
    path: str
    caption: str
    source_note_ids: list[SourceNoteId]

    @field_validator("path", "caption")
    @classmethod
    def _validate_nonempty_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_nonempty_text(value, field_name=info.field_name)

    @field_validator("source_note_ids")
    @classmethod
    def _validate_source_note_ids(cls, value: list[str]) -> list[str]:
        return _normalize_nonempty_string_list(value, field_name="source_note_ids", allow_empty=False)


class WritePaperAuthoringClaimEvidence(BaseModel):
    """Explicit claim-to-evidence bindings for bounded external authoring."""

    model_config = ConfigDict(extra="forbid")

    source_note_ids: list[SourceNoteId] = Field(default_factory=list)
    result_ids: list[ResultId] = Field(default_factory=list)
    figure_ids: list[FigureAssetId] = Field(default_factory=list)
    citation_source_ids: list[str] = Field(default_factory=list)

    @field_validator("source_note_ids", "result_ids", "figure_ids", "citation_source_ids")
    @classmethod
    def _validate_reference_ids(cls, value: list[str], info: ValidationInfo) -> list[str]:
        return _normalize_nonempty_string_list(value, field_name=info.field_name)

    @model_validator(mode="after")
    def _require_at_least_one_binding(self) -> WritePaperAuthoringClaimEvidence:
        if not any((self.source_note_ids, self.result_ids, self.figure_ids, self.citation_source_ids)):
            raise ValueError(
                "evidence must bind at least one source note, result, figure, or citation source"
            )
        return self


class WritePaperAuthoringClaim(BaseModel):
    """One publication claim backed by explicit external-authoring evidence links."""

    model_config = ConfigDict(extra="forbid")

    id: ClaimId
    statement: str
    evidence: WritePaperAuthoringClaimEvidence

    @field_validator("statement")
    @classmethod
    def _validate_nonempty_statement(cls, value: str) -> str:
        return _require_nonempty_text(value, field_name="statement")


class WritePaperAuthoringInput(BaseModel):
    """Closed-schema intake manifest for bounded ``gpd:write-paper`` external authoring."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    title: str
    authors: list[Author]
    target_journal: BuilderJournalKey
    subject_slug: str | None = None
    central_claim: str
    claims: list[WritePaperAuthoringClaim]
    source_notes: list[WritePaperAuthoringSourceNote]
    results: list[WritePaperAuthoringResult] = Field(default_factory=list)
    figures: list[WritePaperAuthoringFigure] = Field(default_factory=list)
    citation_sources: list[CitationSource]
    notation_note: str = ""

    @field_validator("title", "central_claim")
    @classmethod
    def _validate_nonempty_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_nonempty_text(value, field_name=info.field_name)

    @field_validator("subject_slug")
    @classmethod
    def _validate_subject_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not _SUBJECT_SLUG_RE.fullmatch(normalized):
            raise ValueError("subject_slug must be lowercase kebab-case like 'curvature-flow-bounds'")
        return normalized

    @field_validator("citation_sources")
    @classmethod
    def _validate_citation_sources(cls, value: list[CitationSource]) -> list[CitationSource]:
        if not value:
            raise ValueError("citation_sources must contain at least one entry")

        seen_reference_ids: set[str] = set()
        for index, source in enumerate(value):
            reference_id = source.reference_id.strip() if isinstance(source.reference_id, str) else ""
            if not reference_id:
                raise ValueError(f"citation_sources[{index}].reference_id must be a non-empty string")
            if reference_id in seen_reference_ids:
                raise ValueError(f"citation_sources[{index}].reference_id duplicates {reference_id!r}")
            seen_reference_ids.add(reference_id)
            if not source.title.strip():
                raise ValueError(f"citation_sources[{index}].title must be a non-empty string")
        return value

    @model_validator(mode="after")
    def _validate_reference_integrity(self) -> WritePaperAuthoringInput:
        if not self.authors:
            raise ValueError("authors must contain at least one entry")
        if not self.claims:
            raise ValueError("claims must contain at least one entry")
        if not self.source_notes:
            raise ValueError("source_notes must contain at least one entry")

        note_ids = [note.id for note in self.source_notes]
        duplicate_note_ids = _duplicate_items(note_ids)
        if duplicate_note_ids:
            raise ValueError(f"source_notes duplicate id(s): {', '.join(duplicate_note_ids)}")
        note_id_set = set(note_ids)

        result_ids = [result.id for result in self.results]
        duplicate_result_ids = _duplicate_items(result_ids)
        if duplicate_result_ids:
            raise ValueError(f"results duplicate id(s): {', '.join(duplicate_result_ids)}")
        result_id_set = set(result_ids)

        figure_ids = [figure.id for figure in self.figures]
        duplicate_figure_ids = _duplicate_items(figure_ids)
        if duplicate_figure_ids:
            raise ValueError(f"figures duplicate id(s): {', '.join(duplicate_figure_ids)}")
        figure_id_set = set(figure_ids)

        claim_ids = [claim.id for claim in self.claims]
        duplicate_claim_ids = _duplicate_items(claim_ids)
        if duplicate_claim_ids:
            raise ValueError(f"claims duplicate id(s): {', '.join(duplicate_claim_ids)}")

        citation_source_ids = [
            source.reference_id.strip() for source in self.citation_sources if isinstance(source.reference_id, str)
        ]
        citation_source_id_set = set(citation_source_ids)

        for result in self.results:
            missing_source_notes = sorted(note_id for note_id in result.source_note_ids if note_id not in note_id_set)
            if missing_source_notes:
                raise ValueError(
                    f"results[{result.id}].source_note_ids reference missing source note id(s): "
                    + ", ".join(missing_source_notes)
                )

        for figure in self.figures:
            missing_source_notes = sorted(note_id for note_id in figure.source_note_ids if note_id not in note_id_set)
            if missing_source_notes:
                raise ValueError(
                    f"figures[{figure.id}].source_note_ids reference missing source note id(s): "
                    + ", ".join(missing_source_notes)
                )

        for claim in self.claims:
            missing_source_notes = sorted(
                note_id for note_id in claim.evidence.source_note_ids if note_id not in note_id_set
            )
            if missing_source_notes:
                raise ValueError(
                    f"claims[{claim.id}].evidence.source_note_ids reference missing source note id(s): "
                    + ", ".join(missing_source_notes)
                )

            missing_results = sorted(result_id for result_id in claim.evidence.result_ids if result_id not in result_id_set)
            if missing_results:
                raise ValueError(
                    f"claims[{claim.id}].evidence.result_ids reference missing result id(s): "
                    + ", ".join(missing_results)
                )

            missing_figures = sorted(
                figure_id for figure_id in claim.evidence.figure_ids if figure_id not in figure_id_set
            )
            if missing_figures:
                raise ValueError(
                    f"claims[{claim.id}].evidence.figure_ids reference missing figure id(s): "
                    + ", ".join(missing_figures)
                )

            missing_citation_sources = sorted(
                citation_id
                for citation_id in claim.evidence.citation_source_ids
                if citation_id not in citation_source_id_set
            )
            if missing_citation_sources:
                raise ValueError(
                    f"claims[{claim.id}].evidence.citation_source_ids reference missing citation source id(s): "
                    + ", ".join(missing_citation_sources)
                )

        return self


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
            raise ValueError("aligned proof_audits must record at least one checked assumption or checked parameter")
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
            self.claim_kind in {"theorem", "lemma", "corollary", "proposition"}
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
        duplicates = sorted(claim_id for claim_id, count in Counter(proof_audit_claim_ids).items() if count > 1)
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
    pdftotext_available: bool | None = None
    available: bool = False
    full_toolchain_available: bool = False
    paper_build_ready: bool = False
    arxiv_submission_ready: bool = False
    pdf_review_ready: bool = False
    readiness_state: Literal["blocked", "degraded", "ready"] = "blocked"
    message: str = ""
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_derived_status_fields(self) -> PaperToolchainCapability:
        compiler_available = bool(self.compiler_available)
        bibtex_available = self.bibtex_available is True
        latexmk_available = self.latexmk_available is True
        kpsewhich_available = self.kpsewhich_available is True
        pdftotext_available = self.pdftotext_available is True

        self.available = compiler_available
        self.bibliography_support_available = compiler_available and bibtex_available
        self.paper_build_ready = compiler_available
        self.full_toolchain_available = (
            compiler_available
            and bibtex_available
            and latexmk_available
            and kpsewhich_available
            and pdftotext_available
        )
        self.arxiv_submission_ready = self.bibliography_support_available and kpsewhich_available
        self.pdf_review_ready = pdftotext_available
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
            raise ValueError("bib_file must be a stem-safe filename without path separators or extensions")
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

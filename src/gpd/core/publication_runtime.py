"""Shared publication runtime snapshots for manuscript-root and review gating."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.core.manuscript_artifacts import (
    PublicationSubjectResolution,
    resolve_current_publication_subject,
    resolve_explicit_publication_subject,
)
from gpd.core.proof_review import ProofReviewStatus, resolve_manuscript_proof_review_status
from gpd.core.publication_review_paths import (
    manuscript_matches_review_artifact_path,
    review_artifact_round,
    review_round_suffix,
)
from gpd.core.reference_ingestion import ManuscriptReferenceStatusIngestion, ingest_manuscript_reference_status
from gpd.core.state import load_state_json
from gpd.mcp.paper.review_artifacts import read_referee_decision, read_review_ledger

__all__ = [
    "PublicationResponseArtifacts",
    "PublicationReviewArtifacts",
    "PublicationRuntimeSnapshot",
    "publication_blockers_for_project",
    "publication_runtime_snapshot_context",
    "resolve_latest_publication_response_artifacts",
    "resolve_latest_publication_review_artifacts",
    "resolve_publication_runtime_snapshot",
]

_REVIEW_LEDGER_FILENAME_RE = re.compile(r"^REVIEW-LEDGER(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_REFEREE_DECISION_FILENAME_RE = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_AUTHOR_RESPONSE_FILENAME_RE = re.compile(r"^AUTHOR-RESPONSE(?P<round_suffix>-R(?P<round>\d+))?\.md$")
_REFEREE_RESPONSE_FILENAME_RE = re.compile(r"^REFEREE_RESPONSE(?P<round_suffix>-R(?P<round>\d+))?\.md$")
_PUBLICATION_BLOCKER_PATTERNS = (
    re.compile(r"\bpublication\b"),
    re.compile(r"\b(arxiv|submission|manuscript)\b"),
    re.compile(r"\b(peer review|peer-review|review round|referee)\b"),
    re.compile(r"\b(journal|venue)\b"),
)


def _relative_path(project_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _looks_like_publication_blocker(text: str) -> bool:
    lowered = text.casefold().strip()
    return any(pattern.search(lowered) for pattern in _PUBLICATION_BLOCKER_PATTERNS)


def publication_blockers_for_project(cwd: Path) -> tuple[str, ...]:
    """Return unresolved publication blockers from state.json."""

    state_obj = load_state_json(cwd)
    if not isinstance(state_obj, dict):
        return ()

    raw_blockers = state_obj.get("blockers") or []
    blockers: list[str] = []
    for item in raw_blockers:
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            lowered = text.lower()
            if "[resolved]" in lowered or "~~" in text:
                continue
            if _looks_like_publication_blocker(text):
                blockers.append(text)
        elif isinstance(item, dict) and not item.get("resolved", False):
            text = str(item.get("text") or item.get("description") or "").strip()
            labels = " ".join(
                str(item.get(key) or "").strip()
                for key in ("kind", "type", "category", "tag", "scope")
                if str(item.get(key) or "").strip()
            )
            if text and (_looks_like_publication_blocker(text) or (labels and _looks_like_publication_blocker(labels))):
                blockers.append(text)
    return tuple(blockers)


@dataclass(frozen=True, slots=True)
class PublicationReviewArtifacts:
    """Latest review-round artifacts for one manuscript snapshot."""

    round_number: int
    round_suffix: str
    review_ledger: Path | None = None
    referee_decision: Path | None = None
    referee_report_md: Path | None = None
    referee_report_tex: Path | None = None
    proof_redteam: Path | None = None
    state: str = "missing"
    detail: str = ""
    missing_artifacts: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.review_ledger is not None and self.referee_decision is not None and self.state == "complete"

    def to_context_dict(self, project_root: Path) -> dict[str, object]:
        return {
            "round_number": self.round_number,
            "round_suffix": self.round_suffix,
            "review_ledger": _relative_path(project_root, self.review_ledger),
            "referee_decision": _relative_path(project_root, self.referee_decision),
            "referee_report_md": _relative_path(project_root, self.referee_report_md),
            "referee_report_tex": _relative_path(project_root, self.referee_report_tex),
            "proof_redteam": _relative_path(project_root, self.proof_redteam),
            "state": self.state,
            "detail": self.detail,
            "complete": self.complete,
            "missing_artifacts": list(self.missing_artifacts),
        }


@dataclass(frozen=True, slots=True)
class PublicationResponseArtifacts:
    """Latest paired author/referee response artifacts for one manuscript snapshot."""

    round_number: int
    round_suffix: str
    author_response: Path | None = None
    referee_response: Path | None = None
    state: str = "missing"
    detail: str = ""
    missing_artifacts: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.author_response is not None and self.referee_response is not None and self.state == "complete"

    def to_context_dict(self, project_root: Path) -> dict[str, object]:
        return {
            "round_number": self.round_number,
            "round_suffix": self.round_suffix,
            "author_response": _relative_path(project_root, self.author_response),
            "referee_response": _relative_path(project_root, self.referee_response),
            "state": self.state,
            "detail": self.detail,
            "complete": self.complete,
            "missing_artifacts": list(self.missing_artifacts),
        }


@dataclass(frozen=True, slots=True)
class PublicationRuntimeSnapshot:
    """Shared publication state for manuscript-root, review-round, and response gating."""

    publication_subject: PublicationSubjectResolution
    manuscript_reference_status: ManuscriptReferenceStatusIngestion
    manuscript_proof_review_status: ProofReviewStatus
    latest_review_artifacts: PublicationReviewArtifacts | None
    latest_response_artifacts: PublicationResponseArtifacts | None
    publication_blockers: tuple[str, ...] = ()

    @property
    def manuscript_resolution(self):
        return self.publication_subject.as_manuscript_resolution()

    @property
    def manuscript_artifacts(self):
        return self.publication_subject.as_manuscript_artifacts()

    def to_context_dict(self, project_root: Path) -> dict[str, object]:
        subject = self.publication_subject
        resolution = subject.as_manuscript_resolution()
        artifacts = subject.as_manuscript_artifacts()
        reference_status = self.manuscript_reference_status
        proof_status = self.manuscript_proof_review_status
        review_artifacts = self.latest_review_artifacts
        response_artifacts = self.latest_response_artifacts

        derived_reference_status = {
            record.reference_id: record.to_context_dict() for record in reference_status.reference_status
        }

        payload: dict[str, object] = {
            "publication_subject": subject.to_context_dict(),
            "publication_subject_status": subject.status,
            "publication_subject_source": subject.source,
            "publication_subject_detail": subject.detail,
            "publication_artifact_base": _relative_path(project_root, subject.artifact_base),
            "manuscript_resolution_status": resolution.status,
            "manuscript_resolution_detail": resolution.detail,
            "manuscript_root": _relative_path(project_root, artifacts.manuscript_root),
            "manuscript_entrypoint": _relative_path(project_root, artifacts.manuscript_entrypoint),
            "artifact_manifest_path": _relative_path(project_root, artifacts.artifact_manifest),
            "bibliography_audit_path": reference_status.bibliography_audit_path
            or _relative_path(project_root, artifacts.bibliography_audit),
            "reproducibility_manifest_path": _relative_path(project_root, artifacts.reproducibility_manifest),
            "manuscript_reference_status_warnings": list(reference_status.reference_status_warnings),
            "derived_manuscript_reference_status": derived_reference_status,
            "derived_manuscript_reference_status_count": len(derived_reference_status),
            "derived_manuscript_reference_status_warnings": list(reference_status.reference_status_warnings),
            "manuscript_reference_subject_status": reference_status.subject_resolution_status,
            "manuscript_reference_subject_detail": reference_status.subject_resolution_detail,
            "derived_manuscript_proof_review_status": proof_status.to_context_dict(project_root),
            "publication_blockers": list(self.publication_blockers),
            "publication_blocker_count": len(self.publication_blockers),
        }

        if review_artifacts is not None:
            payload.update(
                {
                    "latest_review_round": review_artifacts.round_number,
                    "latest_review_round_suffix": review_artifacts.round_suffix,
                    "latest_review_ledger": _relative_path(project_root, review_artifacts.review_ledger),
                    "latest_referee_decision": _relative_path(project_root, review_artifacts.referee_decision),
                    "latest_referee_report_md": _relative_path(project_root, review_artifacts.referee_report_md),
                    "latest_referee_report_tex": _relative_path(project_root, review_artifacts.referee_report_tex),
                    "latest_proof_redteam": _relative_path(project_root, review_artifacts.proof_redteam),
                    "latest_review_artifacts": review_artifacts.to_context_dict(project_root),
                }
            )
        else:
            payload.update(
                {
                    "latest_review_round": None,
                    "latest_review_round_suffix": None,
                    "latest_review_ledger": None,
                    "latest_referee_decision": None,
                    "latest_referee_report_md": None,
                    "latest_referee_report_tex": None,
                    "latest_proof_redteam": None,
                    "latest_review_artifacts": None,
                }
            )

        if response_artifacts is not None:
            payload.update(
                {
                    "latest_response_round": response_artifacts.round_number,
                    "latest_response_round_suffix": response_artifacts.round_suffix,
                    "latest_author_response": _relative_path(project_root, response_artifacts.author_response),
                    "latest_referee_response": _relative_path(project_root, response_artifacts.referee_response),
                    "latest_response_artifacts": response_artifacts.to_context_dict(project_root),
                }
            )
        else:
            payload.update(
                {
                    "latest_response_round": None,
                    "latest_response_round_suffix": None,
                    "latest_author_response": None,
                    "latest_referee_response": None,
                    "latest_response_artifacts": None,
                }
            )
        return payload


def _latest_round_number(*round_maps: dict[int, Path | None]) -> int | None:
    rounds: set[int] = set()
    for round_map in round_maps:
        rounds.update(round_map)
    if not rounds:
        return None
    return max(rounds)


def _round_file_map(
    review_dir: Path,
    *,
    filename_pattern: re.Pattern[str],
    glob_pattern: str,
) -> dict[int, Path]:
    round_map: dict[int, Path] = {}
    for path in sorted(review_dir.glob(glob_pattern)):
        details = review_artifact_round(path, pattern=filename_pattern)
        if details is None:
            continue
        round_number, _round_suffix = details
        round_map[round_number] = path
    return round_map


def _review_artifact_state(
    *,
    review_ledger: Path | None,
    referee_decision: Path | None,
    manuscript_entrypoint: Path | None,
    project_root: Path,
) -> tuple[str, str, tuple[str, ...]]:
    missing: list[str] = []
    if review_ledger is None:
        missing.append("review_ledger")
    if referee_decision is None:
        missing.append("referee_decision")
    if missing:
        return "partial", f"missing review artifact(s): {', '.join(missing)}", tuple(missing)

    try:
        ledger = read_review_ledger(review_ledger)
    except (OSError, json.JSONDecodeError, PydanticValidationError) as exc:
        return "invalid", f"review ledger could not be loaded: {exc}", ()
    try:
        decision = read_referee_decision(referee_decision)
    except (OSError, json.JSONDecodeError, PydanticValidationError) as exc:
        return "invalid", f"referee decision could not be loaded: {exc}", ()

    if manuscript_entrypoint is not None:
        ledger_matches = manuscript_matches_review_artifact_path(
            ledger.manuscript_path,
            manuscript_entrypoint,
            cwd=project_root,
        )
        decision_matches = manuscript_matches_review_artifact_path(
            decision.manuscript_path,
            manuscript_entrypoint,
            cwd=project_root,
        )
        if not ledger_matches or not decision_matches:
            return "mismatched", "review ledger or referee decision does not match the resolved publication subject", ()

    return "complete", "latest review round is complete for the active manuscript", ()


def _coerce_publication_subject(
    project_root: Path,
    *,
    manuscript_entrypoint: Path | None = None,
    publication_subject: PublicationSubjectResolution | None = None,
) -> PublicationSubjectResolution:
    if publication_subject is not None:
        return publication_subject
    if manuscript_entrypoint is not None:
        return resolve_explicit_publication_subject(
            project_root,
            manuscript_entrypoint,
            allow_markdown=True,
        )
    return resolve_current_publication_subject(project_root, allow_markdown=True)


def resolve_latest_publication_review_artifacts(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
    *,
    publication_subject: PublicationSubjectResolution | None = None,
) -> PublicationReviewArtifacts | None:
    """Resolve the latest review-round bundle for the current manuscript."""

    subject = _coerce_publication_subject(
        project_root,
        manuscript_entrypoint=manuscript_entrypoint,
        publication_subject=publication_subject,
    )
    if not subject.resolved or subject.manuscript_entrypoint is None:
        return None

    review_dir = project_root / "GPD" / "review"
    if not review_dir.exists():
        return None

    ledger_by_round = _round_file_map(
        review_dir,
        filename_pattern=_REVIEW_LEDGER_FILENAME_RE,
        glob_pattern="REVIEW-LEDGER*.json",
    )
    decision_by_round = _round_file_map(
        review_dir,
        filename_pattern=_REFEREE_DECISION_FILENAME_RE,
        glob_pattern="REFEREE-DECISION*.json",
    )
    round_numbers = sorted({*ledger_by_round, *decision_by_round}, reverse=True)
    for round_number in round_numbers:
        round_suffix = review_round_suffix(round_number)
        review_ledger = ledger_by_round.get(round_number)
        referee_decision = decision_by_round.get(round_number)
        referee_report_md = review_dir / f"REFEREE-REPORT{round_suffix}.md"
        referee_report_tex = review_dir / f"REFEREE-REPORT{round_suffix}.tex"
        proof_redteam = review_dir / f"PROOF-REDTEAM{round_suffix}.md"

        state, detail, missing_artifacts = _review_artifact_state(
            review_ledger=review_ledger,
            referee_decision=referee_decision,
            manuscript_entrypoint=subject.manuscript_entrypoint,
            project_root=project_root,
        )
        if state == "mismatched":
            continue

        return PublicationReviewArtifacts(
            round_number=round_number,
            round_suffix=round_suffix,
            review_ledger=review_ledger,
            referee_decision=referee_decision,
            referee_report_md=referee_report_md if referee_report_md.exists() else None,
            referee_report_tex=referee_report_tex if referee_report_tex.exists() else None,
            proof_redteam=proof_redteam if proof_redteam.exists() else None,
            state=state,
            detail=detail,
            missing_artifacts=missing_artifacts,
        )
    return None


def resolve_latest_publication_response_artifacts(
    project_root: Path,
    *,
    publication_subject: PublicationSubjectResolution | None = None,
    review_artifacts: PublicationReviewArtifacts | None = None,
) -> PublicationResponseArtifacts | None:
    """Resolve the latest paired response artifacts for the current manuscript."""

    subject = _coerce_publication_subject(
        project_root,
        publication_subject=publication_subject,
    )
    if not subject.resolved:
        return None

    review_dir = project_root / "GPD" / "review"
    if not review_dir.exists():
        return None

    review_bundle = review_artifacts or resolve_latest_publication_review_artifacts(
        project_root,
        publication_subject=subject,
    )
    if review_bundle is None:
        return None

    author_by_round = _round_file_map(
        review_dir,
        filename_pattern=_AUTHOR_RESPONSE_FILENAME_RE,
        glob_pattern="AUTHOR-RESPONSE*.md",
    )
    referee_by_round = _round_file_map(
        review_dir,
        filename_pattern=_REFEREE_RESPONSE_FILENAME_RE,
        glob_pattern="REFEREE_RESPONSE*.md",
    )
    round_number = review_bundle.round_number
    round_suffix = review_round_suffix(round_number)
    author_response = author_by_round.get(round_number)
    referee_response = referee_by_round.get(round_number)
    missing: list[str] = []
    if author_response is None:
        missing.append("author_response")
    if referee_response is None:
        missing.append("referee_response")
    if missing:
        return PublicationResponseArtifacts(
            round_number=round_number,
            round_suffix=round_suffix,
            author_response=author_response,
            referee_response=referee_response,
            state="partial",
            detail="missing response artifact(s): " + ", ".join(missing),
            missing_artifacts=tuple(missing),
        )

    return PublicationResponseArtifacts(
        round_number=round_number,
        round_suffix=round_suffix,
        author_response=author_response,
        referee_response=referee_response,
        state="complete",
        detail="latest paired response artifacts are complete",
    )


def resolve_publication_runtime_snapshot(
    project_root: Path,
    *,
    publication_subject: PublicationSubjectResolution | None = None,
    persist_manuscript_proof_review_manifest: bool = False,
) -> PublicationRuntimeSnapshot:
    """Resolve the publication runtime state needed for bootstrap and review gates."""

    subject = publication_subject or resolve_current_publication_subject(project_root, allow_markdown=True)
    manuscript_reference_status = ingest_manuscript_reference_status(
        project_root,
        publication_subject=subject,
    )
    manuscript_proof_review_status = (
        resolve_manuscript_proof_review_status(
            project_root,
            subject.manuscript_entrypoint,
            persist_manifest=persist_manuscript_proof_review_manifest,
        )
        if subject.manuscript_entrypoint is not None
        else ProofReviewStatus(
            scope="manuscript",
            state="not_reviewed",
            can_rely_on_prior_review=False,
            detail="no resolved publication subject is available to anchor proof review freshness",
        )
    )
    latest_review_artifacts = resolve_latest_publication_review_artifacts(
        project_root,
        publication_subject=subject,
    )
    latest_response_artifacts = resolve_latest_publication_response_artifacts(
        project_root,
        publication_subject=subject,
        review_artifacts=latest_review_artifacts,
    )
    publication_blockers = publication_blockers_for_project(project_root)
    return PublicationRuntimeSnapshot(
        publication_subject=subject,
        manuscript_reference_status=manuscript_reference_status,
        manuscript_proof_review_status=manuscript_proof_review_status,
        latest_review_artifacts=latest_review_artifacts,
        latest_response_artifacts=latest_response_artifacts,
        publication_blockers=publication_blockers,
    )


def publication_runtime_snapshot_context(
    project_root: Path,
    *,
    publication_subject: PublicationSubjectResolution | None = None,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Return the canonical publication runtime snapshot as a context payload."""

    return resolve_publication_runtime_snapshot(
        project_root,
        publication_subject=publication_subject,
        persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
    ).to_context_dict(project_root)

"""Shared publication runtime snapshots for manuscript-root and review gating."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.core.constants import ProjectLayout
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
from gpd.core.manuscript_artifacts import (
    ManuscriptArtifacts,
    ManuscriptResolution,
    PublicationSubjectResolution,
    locate_publication_artifact,
    resolve_current_manuscript_artifacts,
    resolve_current_manuscript_resolution,
    resolve_current_publication_subject,
    resolve_explicit_publication_subject,
)
from gpd.core.peer_review_mode import (
    PEER_REVIEW_INTERACTIVE_MODE,
    PEER_REVIEW_INVALID_SUBJECT_MODE,
    PEER_REVIEW_PROJECT_BACKED_MODE,
    PEER_REVIEW_STANDALONE_MODE,
    resolve_peer_review_mode_details,
)
from gpd.core.proof_review import (
    ProofReviewStatus,
    publication_lineage_mode,
    publication_lineage_roots,
    resolve_manuscript_proof_review_status,
)
from gpd.core.publication_review_paths import (
    manuscript_matches_review_artifact_path,
    review_round_suffix,
)
from gpd.core.publication_rounds import (
    latest_publication_round_number,
    publication_response_round_path_maps,
    publication_review_round_path_maps,
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
class PublicationRuntimeTarget:
    """Resolved publication/peer-review target used for runtime snapshots."""

    mode: str
    detail: str
    project_context_role: str
    subject_path: Path | None = None
    target_path: Path | None = None
    target_root: Path | None = None


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
    target: PublicationRuntimeTarget
    manuscript_resolution: ManuscriptResolution
    manuscript_artifacts: ManuscriptArtifacts
    manuscript_reference_status: ManuscriptReferenceStatusIngestion
    manuscript_proof_review_status: ProofReviewStatus
    latest_review_artifacts: PublicationReviewArtifacts | None
    latest_response_artifacts: PublicationResponseArtifacts | None
    publication_blockers: tuple[str, ...] = ()

    def to_context_dict(self, project_root: Path) -> dict[str, object]:
        subject = self.publication_subject
        resolution = self.manuscript_resolution
        artifacts = self.manuscript_artifacts
        reference_status = self.manuscript_reference_status
        proof_status = self.manuscript_proof_review_status
        review_artifacts = self.latest_review_artifacts
        response_artifacts = self.latest_response_artifacts
        publication_lineage_root = None
        publication_lineage_review_dir = None
        publication_lineage_mode_value = None
        if subject.manuscript_entrypoint is not None:
            publication_lineage_mode_value = publication_lineage_mode(project_root, subject.manuscript_entrypoint)
            publication_lineage_root, publication_lineage_review_dir = _publication_lineage_roots_for_subject(
                project_root,
                subject,
            )

        derived_reference_status = {
            record.reference_id: record.to_context_dict() for record in reference_status.reference_status
        }

        payload: dict[str, object] = {
            "publication_subject": subject.to_context_dict(),
            "publication_subject_slug": subject.publication_subject_slug,
            "publication_subject_status": subject.status,
            "publication_subject_source": subject.source,
            "publication_subject_detail": subject.detail,
            "publication_artifact_base": _relative_path(project_root, subject.artifact_base),
            "publication_lineage_mode": publication_lineage_mode_value,
            "publication_lineage_root": _relative_path(project_root, publication_lineage_root),
            "publication_lineage_review_dir": _relative_path(project_root, publication_lineage_review_dir),
            "publication_target_mode": self.target.mode,
            "publication_target_detail": self.target.detail,
            "publication_target_project_context_role": self.target.project_context_role,
            "publication_target_path": _relative_path(project_root, self.target.target_path),
            "publication_target_root": _relative_path(project_root, self.target.target_root),
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


def _project_backed_target_mode(target: PublicationRuntimeTarget) -> bool:
    return target.mode in {"project_manuscript", "project_explicit_manuscript"}


def _resolve_publication_runtime_target(project_root: Path, subject: str | None) -> PublicationRuntimeTarget:
    mode_resolution = resolve_peer_review_mode_details(
        project_root,
        subject,
        workspace_cwd=project_root,
        display_cwd=project_root,
    )
    current_artifacts = resolve_current_manuscript_artifacts(project_root, allow_markdown=True)

    if mode_resolution.resolved_mode == PEER_REVIEW_PROJECT_BACKED_MODE:
        explicit_subject = (
            resolve_explicit_publication_subject(
                project_root,
                mode_resolution.resolved_target,
                allow_markdown=True,
            )
            if mode_resolution.subject and mode_resolution.resolved_target is not None
            else None
        )
        return PublicationRuntimeTarget(
            mode="project_explicit_manuscript" if mode_resolution.subject else "project_manuscript",
            detail=mode_resolution.mode_reason,
            project_context_role="authoritative",
            subject_path=mode_resolution.subject_path,
            target_path=mode_resolution.resolved_target or current_artifacts.manuscript_entrypoint,
            target_root=(
                explicit_subject.manuscript_root
                if explicit_subject is not None and explicit_subject.manuscript_root is not None
                else current_artifacts.manuscript_root
            ),
        )

    if mode_resolution.resolved_mode == PEER_REVIEW_STANDALONE_MODE:
        target_root: Path | None = None
        if mode_resolution.subject_path is not None and mode_resolution.subject_path.exists():
            if mode_resolution.subject_path.is_dir():
                target_root = mode_resolution.subject_path
            else:
                target_root = mode_resolution.subject_path.parent
        elif mode_resolution.resolved_target is not None:
            target_root = mode_resolution.resolved_target.parent
        elif mode_resolution.subject_path is not None:
            target_root = mode_resolution.subject_path.parent
        return PublicationRuntimeTarget(
            mode="external_artifact",
            detail=mode_resolution.mode_reason,
            project_context_role="carry_forward_only",
            subject_path=mode_resolution.subject_path,
            target_path=mode_resolution.resolved_target,
            target_root=target_root,
        )

    fallback_root = mode_resolution.subject_path.parent if mode_resolution.subject_path is not None else None
    if mode_resolution.resolved_mode == PEER_REVIEW_INTERACTIVE_MODE:
        return PublicationRuntimeTarget(
            mode="interactive_intake",
            detail=mode_resolution.mode_reason,
            project_context_role="carry_forward_only",
            subject_path=mode_resolution.subject_path,
            target_root=fallback_root,
        )
    if mode_resolution.resolved_mode == PEER_REVIEW_INVALID_SUBJECT_MODE:
        return PublicationRuntimeTarget(
            mode="invalid_explicit_target",
            detail=mode_resolution.mode_reason,
            project_context_role="carry_forward_only",
            subject_path=mode_resolution.subject_path,
            target_root=fallback_root,
        )
    return PublicationRuntimeTarget(
        mode="project_manuscript",
        detail=mode_resolution.mode_reason,
        project_context_role="authoritative",
        subject_path=mode_resolution.subject_path,
        target_path=current_artifacts.manuscript_entrypoint,
        target_root=current_artifacts.manuscript_root,
    )


def _resolve_target_manuscript_artifacts(
    project_root: Path,
    target: PublicationRuntimeTarget,
    current_artifacts: ManuscriptArtifacts,
) -> ManuscriptArtifacts:
    if _project_backed_target_mode(target):
        return current_artifacts

    manuscript_root = target.target_root
    return ManuscriptArtifacts(
        project_root=project_root,
        manuscript_root=manuscript_root,
        manuscript_entrypoint=target.target_path,
        artifact_manifest=(
            locate_publication_artifact(manuscript_root, "ARTIFACT-MANIFEST.json")
            if manuscript_root is not None
            else None
        ),
        bibliography_audit=(
            locate_publication_artifact(manuscript_root, "BIBLIOGRAPHY-AUDIT.json")
            if manuscript_root is not None
            else None
        ),
        reproducibility_manifest=(
            locate_publication_artifact(manuscript_root, "reproducibility-manifest.json")
            if manuscript_root is not None
            else None
        ),
    )


def _resolve_target_manuscript_resolution(
    target: PublicationRuntimeTarget,
    current_resolution: ManuscriptResolution,
    artifacts: ManuscriptArtifacts,
) -> ManuscriptResolution:
    if _project_backed_target_mode(target):
        return current_resolution
    if target.target_path is not None:
        return ManuscriptResolution(
            status="resolved",
            manuscript_root=artifacts.manuscript_root,
            manuscript_entrypoint=target.target_path,
            detail=target.detail,
        )
    if target.mode == "invalid_explicit_target":
        return ManuscriptResolution(
            status="invalid",
            manuscript_root=artifacts.manuscript_root,
            manuscript_entrypoint=None,
            detail=target.detail,
        )
    return ManuscriptResolution(
        status="missing",
        manuscript_root=artifacts.manuscript_root,
        manuscript_entrypoint=None,
        detail=target.detail,
    )


def _resolve_target_manuscript_reference_status(
    project_root: Path,
    artifacts: ManuscriptArtifacts,
    *,
    allow_project_fallback: bool,
    manuscript_resolution: ManuscriptResolution | None = None,
) -> ManuscriptReferenceStatusIngestion:
    if artifacts.manuscript_root is None:
        if allow_project_fallback:
            return ingest_manuscript_reference_status(project_root)
        return ManuscriptReferenceStatusIngestion()

    subject_status = manuscript_resolution.status if manuscript_resolution is not None else "resolved"
    subject_detail = (
        manuscript_resolution.detail
        if manuscript_resolution is not None
        else "publication runtime resolved manuscript artifacts"
    )
    subject = PublicationSubjectResolution(
        project_root=project_root,
        status=subject_status,
        source="explicit_target",
        detail=subject_detail,
        target_path=artifacts.manuscript_entrypoint,
        manuscript_root=artifacts.manuscript_root,
        manuscript_entrypoint=artifacts.manuscript_entrypoint,
        artifact_base=artifacts.manuscript_root,
        artifact_manifest=artifacts.artifact_manifest,
        bibliography_audit=artifacts.bibliography_audit,
        reproducibility_manifest=artifacts.reproducibility_manifest,
    )
    return ingest_manuscript_reference_status(project_root, publication_subject=subject)


def _target_not_reviewed_status(detail: str) -> ProofReviewStatus:
    return ProofReviewStatus(
        scope="manuscript",
        state="not_reviewed",
        can_rely_on_prior_review=False,
        detail=detail,
    )


def _first_existing_path(*candidates: Path) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _review_artifact_state(
    *,
    review_ledger: Path | None,
    referee_decision: Path | None,
    manuscript_entrypoint: Path | None,
    project_root: Path,
    round_number: int,
) -> tuple[str, str, tuple[str, ...]]:
    missing: list[str] = []
    ledger = None
    decision = None
    if review_ledger is None:
        missing.append("review_ledger")
    else:
        try:
            ledger = read_review_ledger(review_ledger)
        except (OSError, json.JSONDecodeError, PydanticValidationError) as exc:
            return "invalid", f"review ledger could not be loaded: {exc}", ()

    if referee_decision is None:
        missing.append("referee_decision")
    else:
        try:
            decision = read_referee_decision(referee_decision)
        except (OSError, json.JSONDecodeError, PydanticValidationError) as exc:
            return "invalid", f"referee decision could not be loaded: {exc}", ()

    if ledger is not None and ledger.round != round_number:
        return (
            "invalid",
            f"review ledger round {ledger.round} does not match review artifact round {round_number}",
            (),
        )

    if manuscript_entrypoint is not None:
        mismatched: list[str] = []
        if ledger is not None and not manuscript_matches_review_artifact_path(
            ledger.manuscript_path,
            manuscript_entrypoint,
            cwd=project_root,
        ):
            mismatched.append("review ledger")
        if decision is not None and not manuscript_matches_review_artifact_path(
            decision.manuscript_path,
            manuscript_entrypoint,
            cwd=project_root,
        ):
            mismatched.append("referee decision")
        if mismatched:
            return (
                "mismatched",
                " or ".join(mismatched) + " does not match the resolved publication subject",
                (),
            )

    if missing:
        return "partial", f"missing review artifact(s): {', '.join(missing)}", tuple(missing)

    return "complete", "latest review round is complete for the active manuscript", ()


def _publication_lineage_roots_for_subject(
    project_root: Path,
    subject: PublicationSubjectResolution,
) -> tuple[Path, Path]:
    layout = ProjectLayout(project_root)
    if subject.manuscript_entrypoint is None:
        return layout.gpd, layout.gpd / "review"
    return publication_lineage_roots(project_root, subject.manuscript_entrypoint)


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


def _metadata_round_value(metadata: dict[str, object]) -> int | None:
    for field_name in ("round", "response_round", "review_round"):
        value = metadata.get(field_name)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _metadata_text(metadata: dict[str, object], *field_names: str) -> str:
    for field_name in field_names:
        value = metadata.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _path_metadata_matches_project_path(value: str, expected_path: Path | None, *, project_root: Path) -> bool:
    if expected_path is None:
        return True
    return manuscript_matches_review_artifact_path(value, expected_path, cwd=project_root)


def _response_artifact_metadata_errors(
    path: Path,
    *,
    project_root: Path,
    manuscript_entrypoint: Path | None,
    round_number: int,
    round_suffix: str,
    review_artifacts: PublicationReviewArtifacts | None,
    binding_required: bool,
) -> tuple[str, ...]:
    try:
        metadata, _body = extract_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FrontmatterParseError) as exc:
        return (f"{path.name} metadata could not be loaded: {exc}",)

    if not metadata:
        return (f"{path.name} has no response frontmatter binding",) if binding_required else ()

    errors: list[str] = []
    metadata_round = _metadata_round_value(metadata)
    if metadata_round is None:
        if binding_required:
            errors.append(f"{path.name} response frontmatter is missing `round`")
    elif metadata_round != round_number:
        errors.append(f"{path.name} round {metadata_round} does not match active review round {round_number}")

    manuscript_path = _metadata_text(metadata, "manuscript_path", "manuscript")
    if manuscript_entrypoint is not None:
        if not manuscript_path:
            if binding_required:
                errors.append(f"{path.name} response frontmatter is missing `manuscript_path`")
        elif not manuscript_matches_review_artifact_path(manuscript_path, manuscript_entrypoint, cwd=project_root):
            errors.append(f"{path.name} manuscript_path does not match the active manuscript")

    response_to = _metadata_text(metadata, "response_to", "referee_report")
    if response_to and Path(response_to).name != f"REFEREE-REPORT{round_suffix}.md":
        errors.append(f"{path.name} response_to does not match round suffix {round_suffix or '(round 1)'}")

    review_ledger = _metadata_text(metadata, "review_ledger")
    if (
        review_ledger
        and review_artifacts is not None
        and not _path_metadata_matches_project_path(
            review_ledger,
            review_artifacts.review_ledger,
            project_root=project_root,
        )
    ):
        errors.append(f"{path.name} review_ledger does not match the active review artifact")

    referee_decision = _metadata_text(metadata, "referee_decision")
    if (
        referee_decision
        and review_artifacts is not None
        and not _path_metadata_matches_project_path(
            referee_decision,
            review_artifacts.referee_decision,
            project_root=project_root,
        )
    ):
        errors.append(f"{path.name} referee_decision does not match the active review artifact")

    return tuple(errors)


def _response_artifact_binding_state(
    *,
    project_root: Path,
    author_response: Path,
    referee_response: Path,
    manuscript_entrypoint: Path | None,
    round_number: int,
    round_suffix: str,
    review_artifacts: PublicationReviewArtifacts | None,
    binding_required: bool,
) -> tuple[str, str]:
    errors: list[str] = []
    for path in (author_response, referee_response):
        errors.extend(
            _response_artifact_metadata_errors(
                path,
                project_root=project_root,
                manuscript_entrypoint=manuscript_entrypoint,
                round_number=round_number,
                round_suffix=round_suffix,
                review_artifacts=review_artifacts,
                binding_required=binding_required,
            )
        )
    if not errors:
        return "complete", "latest paired response artifacts are complete"
    if all("no response frontmatter binding" in error or "missing `" in error for error in errors):
        return "unbound", "; ".join(errors[:3])
    return "mismatched", "; ".join(errors[:3])


def resolve_latest_publication_review_artifacts(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
    *,
    publication_subject: PublicationSubjectResolution | None = None,
) -> PublicationReviewArtifacts | None:
    """Resolve the latest review-round bundle for one manuscript snapshot."""

    subject = _coerce_publication_subject(
        project_root,
        manuscript_entrypoint=manuscript_entrypoint,
        publication_subject=publication_subject,
    )

    if subject.resolved and subject.manuscript_entrypoint is not None:
        resolved_manuscript = subject.manuscript_entrypoint
        publication_root, review_dir = _publication_lineage_roots_for_subject(project_root, subject)
    elif manuscript_entrypoint is not None:
        layout = ProjectLayout(project_root)
        resolved_manuscript = manuscript_entrypoint
        publication_root, review_dir = layout.gpd, layout.gpd / "review"
    else:
        return None

    if not review_dir.exists():
        return None

    ledger_by_round, decision_by_round = publication_review_round_path_maps(
        project_root,
        manuscript=resolved_manuscript,
    )
    round_numbers = sorted({*ledger_by_round, *decision_by_round}, reverse=True)
    for round_number in round_numbers:
        review_ledger = ledger_by_round.get(round_number)
        referee_decision = decision_by_round.get(round_number)
        round_suffix = review_round_suffix(round_number)
        referee_report_md = _first_existing_path(
            publication_root / f"REFEREE-REPORT{round_suffix}.md",
            review_dir / f"REFEREE-REPORT{round_suffix}.md",
        )
        referee_report_tex = _first_existing_path(
            publication_root / f"REFEREE-REPORT{round_suffix}.tex",
            review_dir / f"REFEREE-REPORT{round_suffix}.tex",
        )
        proof_redteam = review_dir / f"PROOF-REDTEAM{round_suffix}.md"

        state, detail, missing_artifacts = _review_artifact_state(
            review_ledger=review_ledger,
            referee_decision=referee_decision,
            manuscript_entrypoint=resolved_manuscript,
            project_root=project_root,
            round_number=round_number,
        )
        if state == "mismatched":
            continue

        return PublicationReviewArtifacts(
            round_number=round_number,
            round_suffix=round_suffix,
            review_ledger=review_ledger,
            referee_decision=referee_decision,
            referee_report_md=referee_report_md,
            referee_report_tex=referee_report_tex,
            proof_redteam=proof_redteam if proof_redteam.exists() else None,
            state=state,
            detail=detail,
            missing_artifacts=missing_artifacts,
        )
    return None


def resolve_latest_publication_response_artifacts(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
    *,
    publication_subject: PublicationSubjectResolution | None = None,
    review_artifacts: PublicationReviewArtifacts | None = None,
) -> PublicationResponseArtifacts | None:
    """Resolve the latest paired response artifacts for the current manuscript."""

    subject = _coerce_publication_subject(
        project_root,
        manuscript_entrypoint=manuscript_entrypoint,
        publication_subject=publication_subject,
    )
    resolved_manuscript = subject.manuscript_entrypoint if subject.resolved else manuscript_entrypoint
    if subject.resolved and subject.manuscript_entrypoint is not None:
        _publication_root, review_dir = _publication_lineage_roots_for_subject(project_root, subject)
    elif manuscript_entrypoint is not None:
        layout = ProjectLayout(project_root)
        review_dir = layout.gpd / "review"
    else:
        return None
    if not review_dir.exists():
        return None

    author_by_round, referee_by_round = publication_response_round_path_maps(
        project_root,
        manuscript=resolved_manuscript,
        include_review_roots_for_author_response=True,
    )
    round_number = (
        review_artifacts.round_number
        if review_artifacts is not None
        else latest_publication_round_number(
            author_by_round,
            referee_by_round,
        )
    )
    if round_number is None:
        return None
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

    binding_required = subject.source == "explicit_target" and resolved_manuscript is not None
    state, detail = _response_artifact_binding_state(
        project_root=project_root,
        author_response=author_response,
        referee_response=referee_response,
        manuscript_entrypoint=resolved_manuscript,
        round_number=round_number,
        round_suffix=round_suffix,
        review_artifacts=review_artifacts,
        binding_required=binding_required,
    )
    return PublicationResponseArtifacts(
        round_number=round_number,
        round_suffix=round_suffix,
        author_response=author_response,
        referee_response=referee_response,
        state=state,
        detail=detail,
    )


def resolve_publication_runtime_snapshot(
    project_root: Path,
    *,
    publication_subject: PublicationSubjectResolution | None = None,
    subject: str | None = None,
    persist_manuscript_proof_review_manifest: bool = False,
) -> PublicationRuntimeSnapshot:
    """Resolve the publication runtime state needed for bootstrap and review gates."""

    target_subject = subject
    if target_subject is None and publication_subject is not None:
        subject_path = publication_subject.target_path or publication_subject.manuscript_entrypoint
        if subject_path is not None:
            target_subject = subject_path.as_posix()

    target = _resolve_publication_runtime_target(project_root, target_subject)
    current_resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=True)
    current_artifacts = resolve_current_manuscript_artifacts(project_root, allow_markdown=True)
    explicit_project_subject = None
    if publication_subject is None and target.mode == "project_explicit_manuscript" and target.target_path is not None:
        explicit_project_subject = resolve_explicit_publication_subject(
            project_root,
            target.target_path,
            allow_markdown=True,
        )

    if publication_subject is not None:
        resolved_subject = publication_subject
        manuscript_artifacts = publication_subject.as_manuscript_artifacts()
        manuscript_resolution = publication_subject.as_manuscript_resolution()
    elif explicit_project_subject is not None and explicit_project_subject.resolved:
        resolved_subject = explicit_project_subject
        manuscript_artifacts = explicit_project_subject.as_manuscript_artifacts()
        manuscript_resolution = explicit_project_subject.as_manuscript_resolution()
    else:
        manuscript_artifacts = _resolve_target_manuscript_artifacts(project_root, target, current_artifacts)
        manuscript_resolution = _resolve_target_manuscript_resolution(target, current_resolution, manuscript_artifacts)
        if _project_backed_target_mode(target):
            resolved_subject = resolve_current_publication_subject(project_root, allow_markdown=True)
        elif manuscript_artifacts.manuscript_entrypoint is None:
            resolved_subject = PublicationSubjectResolution(
                project_root=project_root,
                status=manuscript_resolution.status,
                source="explicit_target",
                detail=manuscript_resolution.detail,
                target_path=target.target_path or target.subject_path,
                manuscript_root=manuscript_artifacts.manuscript_root,
                manuscript_entrypoint=None,
                artifact_base=manuscript_artifacts.manuscript_root,
                artifact_manifest=manuscript_artifacts.artifact_manifest,
                bibliography_audit=manuscript_artifacts.bibliography_audit,
                reproducibility_manifest=manuscript_artifacts.reproducibility_manifest,
            )
        else:
            resolved_subject = _coerce_publication_subject(
                project_root,
                manuscript_entrypoint=manuscript_artifacts.manuscript_entrypoint,
            )
    allow_project_fallback = _project_backed_target_mode(target)
    manuscript_reference_status = (
        ingest_manuscript_reference_status(project_root, publication_subject=resolved_subject)
        if resolved_subject.resolved
        else _resolve_target_manuscript_reference_status(
            project_root,
            manuscript_artifacts,
            allow_project_fallback=allow_project_fallback,
            manuscript_resolution=manuscript_resolution,
        )
    )
    if manuscript_artifacts.manuscript_entrypoint is not None:
        manuscript_proof_review_status = resolve_manuscript_proof_review_status(
            project_root,
            manuscript_artifacts.manuscript_entrypoint,
            persist_manifest=persist_manuscript_proof_review_manifest,
        )
        latest_review_artifacts = resolve_latest_publication_review_artifacts(
            project_root,
            manuscript_artifacts.manuscript_entrypoint,
            publication_subject=resolved_subject,
        )
    elif allow_project_fallback:
        manuscript_proof_review_status = resolve_manuscript_proof_review_status(
            project_root,
            persist_manifest=persist_manuscript_proof_review_manifest,
        )
        latest_review_artifacts = resolve_latest_publication_review_artifacts(
            project_root,
            publication_subject=resolved_subject,
        )
    else:
        manuscript_proof_review_status = _target_not_reviewed_status(
            "no resolved explicit peer-review target is available to anchor proof review freshness"
        )
        latest_review_artifacts = None
    latest_response_artifacts = (
        resolve_latest_publication_response_artifacts(
            project_root,
            manuscript_artifacts.manuscript_entrypoint,
            publication_subject=resolved_subject,
            review_artifacts=latest_review_artifacts,
        )
        if manuscript_artifacts.manuscript_entrypoint is not None or allow_project_fallback
        else None
    )
    publication_blockers = publication_blockers_for_project(project_root) if allow_project_fallback else ()
    return PublicationRuntimeSnapshot(
        publication_subject=resolved_subject,
        target=target,
        manuscript_resolution=manuscript_resolution,
        manuscript_artifacts=manuscript_artifacts,
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
    subject: str | None = None,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Return the canonical publication runtime snapshot as a context payload."""

    return resolve_publication_runtime_snapshot(
        project_root,
        publication_subject=publication_subject,
        subject=subject,
        persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
    ).to_context_dict(project_root)

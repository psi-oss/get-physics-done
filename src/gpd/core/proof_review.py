"""Proof-review freshness helpers for phase verification and manuscript math review."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import PROOF_AUDIT_REVIEWER, statement_looks_theorem_like
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
from gpd.core.manuscript_artifacts import resolve_current_manuscript_entrypoint
from gpd.core.referee_policy import validate_stage_review_artifact_alignment
from gpd.core.reproducibility import compute_sha256
from gpd.mcp.paper.review_artifacts import read_claim_index, read_stage_review_report

__all__ = [
    "MANUSCRIPT_PROOF_REVIEW_MANIFEST_NAME",
    "ProofReviewStatus",
    "manuscript_has_theorem_bearing_claim_inventory",
    "manuscript_has_theorem_bearing_language",
    "manuscript_has_theorem_bearing_review_anchor",
    "manuscript_requires_theorem_bearing_review",
    "manuscript_proof_review_manifest_path",
    "phase_proof_review_manifest_path",
    "resolve_manuscript_proof_review_status",
    "resolve_phase_proof_review_status",
]

MANUSCRIPT_PROOF_REVIEW_MANIFEST_NAME = "PROOF-REVIEW-MANIFEST.json"
_PHASE_PROOF_REVIEW_MANIFEST_SUFFIX = "-PROOF-REVIEW-MANIFEST.json"
_PHASE_PROOF_AFFECTING_EXTENSIONS = frozenset(
    {
        ".md",
        ".tex",
        ".txt",
        ".py",
        ".ipynb",
        ".jl",
        ".f90",
        ".m",
        ".wl",
        ".wls",
        ".nb",
        ".yaml",
        ".yml",
        ".bib",
    }
)
_MANUSCRIPT_PROOF_AFFECTING_EXTENSIONS = frozenset(
    {
        ".tex",
        ".md",
        ".bib",
        ".bst",
        ".sty",
        ".cls",
        ".txt",
    }
)
_STAGE_MATH_FILENAME_RE = re.compile(r"^STAGE-math(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_THEOREM_STYLE_MANUSCRIPT_RE = re.compile(
    r"(\\begin\{(?:theorem|lemma|corollary|proposition|claim|proof)\})"
    r"|(\\newtheorem\{)"
    r"|(^\s{0,3}\#{1,6}\s*(?:theorem|lemma|corollary|proposition|claim|proof)\b)"
    r"|(^\s*(?:theorem|lemma|corollary|proposition|claim|proof)\b[\s.:])",
    re.IGNORECASE | re.MULTILINE,
)
_PROOF_REDTEAM_REQUIRED_STATUS_VALUES = frozenset({"passed", "gaps_found", "human_needed"})
_PROOF_REDTEAM_REQUIRED_SCOPE_STATUS_VALUES = frozenset({"matched", "narrower_than_claim", "mismatched", "unclear"})
_PROOF_REDTEAM_REQUIRED_QUANTIFIER_STATUS_VALUES = frozenset({"matched", "narrowed", "mismatched", "unclear"})
_PROOF_REDTEAM_REQUIRED_COUNTEREXAMPLE_STATUS_VALUES = frozenset(
    {"none_found", "counterexample_found", "not_attempted", "narrowed_claim"}
)


@dataclass(frozen=True, slots=True)
class _MathReviewAnchor:
    stage_artifact: Path
    claim_index_artifact: Path
    round_number: int
    round_suffix: str
    proof_bearing: bool
    theorem_claim_ids: tuple[str, ...]
    proof_artifact_paths: tuple[str, ...]
    validation_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ProofRedteamStructuredAudit:
    missing_parameter_symbols: tuple[str, ...]
    missing_hypothesis_ids: tuple[str, ...]
    coverage_gaps: tuple[str, ...]
    scope_status: str
    quantifier_status: str
    counterexample_status: str


@dataclass(frozen=True, slots=True)
class ProofReviewStatus:
    """Freshness status for prior proof review over a file set."""

    scope: str
    state: str
    can_rely_on_prior_review: bool
    detail: str
    manifest_path: Path | None = None
    anchor_artifact: Path | None = None
    watched_files: tuple[Path, ...] = ()
    changed_files: tuple[Path, ...] = ()
    manifest_bootstrapped: bool = False

    def to_context_dict(self, project_root: Path) -> dict[str, object]:
        return {
            "scope": self.scope,
            "state": self.state,
            "can_rely_on_prior_review": self.can_rely_on_prior_review,
            "detail": self.detail,
            "manifest_path": _relative_path(project_root, self.manifest_path),
            "anchor_artifact": _relative_path(project_root, self.anchor_artifact),
            "watched_files": [_relative_path(project_root, path) for path in self.watched_files],
            "watched_file_count": len(self.watched_files),
            "changed_files": [_relative_path(project_root, path) for path in self.changed_files],
            "changed_file_count": len(self.changed_files),
            "manifest_bootstrapped": self.manifest_bootstrapped,
        }


def phase_proof_review_manifest_path(verification_path: Path) -> Path:
    """Return the canonical proof-review manifest path for a phase verification artifact."""

    if verification_path.name.endswith("-VERIFICATION.md"):
        stem = verification_path.name[: -len("-VERIFICATION.md")]
        return verification_path.with_name(f"{stem}{_PHASE_PROOF_REVIEW_MANIFEST_SUFFIX}")
    return verification_path.with_name(MANUSCRIPT_PROOF_REVIEW_MANIFEST_NAME)


def manuscript_proof_review_manifest_path(manuscript_entrypoint: Path) -> Path:
    """Return the manuscript-local proof-review manifest path."""

    return manuscript_entrypoint.parent / MANUSCRIPT_PROOF_REVIEW_MANIFEST_NAME


def manuscript_has_theorem_bearing_review_anchor(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
) -> bool:
    """Return whether the latest matching staged math review marks the manuscript as theorem-bearing."""

    entrypoint = manuscript_entrypoint or resolve_current_manuscript_entrypoint(project_root, allow_markdown=True)
    if entrypoint is None:
        return False
    anchor = _latest_matching_math_review_anchor(project_root, entrypoint)
    return bool(anchor and anchor.proof_bearing)


def manuscript_has_theorem_bearing_claim_inventory(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
) -> bool:
    """Return whether the latest matching staged claim inventory is theorem-bearing."""

    entrypoint = manuscript_entrypoint or resolve_current_manuscript_entrypoint(project_root, allow_markdown=True)
    if entrypoint is None:
        return False

    review_dir = project_root / "GPD" / "review"
    if not review_dir.exists():
        return False

    resolved_manuscript = _resolve_review_manuscript_path(project_root, entrypoint.as_posix())
    matches: list[tuple[int, int, bool]] = []
    for path in sorted(review_dir.glob("CLAIMS*.json")):
        match = _claim_round_details(path)
        if match is None:
            continue
        round_number, _round_suffix = match
        try:
            claim_index = read_claim_index(path)
        except (OSError, json.JSONDecodeError, PydanticValidationError):
            continue
        if _resolve_review_manuscript_path(project_root, claim_index.manuscript_path) != resolved_manuscript:
            continue
        matches.append(
            (
                round_number,
                path.stat().st_mtime_ns,
                any(claim.theorem_bearing for claim in claim_index.claims),
            )
        )

    if not matches:
        return False
    _, _, theorem_bearing = max(matches)
    return theorem_bearing


def manuscript_has_theorem_bearing_language(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
) -> bool:
    """Return whether manuscript text itself looks theorem-bearing."""

    entrypoint = manuscript_entrypoint or resolve_current_manuscript_entrypoint(project_root, allow_markdown=True)
    if entrypoint is None or not entrypoint.exists():
        return False

    manuscript_paths: list[Path] = [entrypoint]
    for candidate in sorted(entrypoint.parent.rglob("*")):
        if candidate == entrypoint or not candidate.is_file():
            continue
        if candidate.suffix.lower() not in {".tex", ".md"}:
            continue
        manuscript_paths.append(candidate)

    for manuscript_path in manuscript_paths:
        try:
            content = manuscript_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _THEOREM_STYLE_MANUSCRIPT_RE.search(content):
            return True
        if statement_looks_theorem_like(content):
            return True
    return False


def manuscript_requires_theorem_bearing_review(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
) -> bool:
    """Return whether a manuscript should be treated as theorem-bearing."""

    entrypoint = manuscript_entrypoint or resolve_current_manuscript_entrypoint(project_root, allow_markdown=True)
    return entrypoint is not None and (
        manuscript_has_theorem_bearing_language(project_root, entrypoint)
        or manuscript_has_theorem_bearing_review_anchor(project_root, entrypoint)
        or manuscript_has_theorem_bearing_claim_inventory(project_root, entrypoint)
    )


def _resolve_review_artifacts(project_root: Path, artifact_paths: tuple[str, ...]) -> tuple[Path, ...]:
    """Resolve review artifact paths against the project root."""

    return tuple(_resolve_review_manuscript_path(project_root, path) for path in artifact_paths if path.strip())


def resolve_phase_proof_review_status(
    project_root: Path,
    phase_dir: Path | None,
    *,
    persist_manifest: bool = False,
) -> ProofReviewStatus:
    """Resolve freshness for a phase-scoped proof review."""

    if phase_dir is None or not phase_dir.exists():
        return ProofReviewStatus(
            scope="phase",
            state="not_reviewed",
            can_rely_on_prior_review=False,
            detail="phase directory not found; no prior proof review artifact is available",
        )

    verification_path = _latest_phase_verification_artifact(phase_dir)
    if verification_path is None:
        return ProofReviewStatus(
            scope="phase",
            state="not_reviewed",
            can_rely_on_prior_review=False,
            detail="no prior phase verification artifact is available to anchor proof review freshness",
        )

    manifest_path = phase_proof_review_manifest_path(verification_path)
    watched_files = _collect_phase_watched_files(phase_dir, verification_path, manifest_path)
    return _resolve_status(
        project_root,
        scope="phase",
        anchor_artifact=verification_path,
        manifest_path=manifest_path,
        watched_files=watched_files,
        persist_manifest=persist_manifest,
    )


def resolve_manuscript_proof_review_status(
    project_root: Path,
    manuscript_entrypoint: Path | None = None,
    *,
    persist_manifest: bool = False,
) -> ProofReviewStatus:
    """Resolve freshness for manuscript-scoped proof review."""

    entrypoint = manuscript_entrypoint or resolve_current_manuscript_entrypoint(project_root, allow_markdown=True)
    if entrypoint is None:
        return ProofReviewStatus(
            scope="manuscript",
            state="not_reviewed",
            can_rely_on_prior_review=False,
            detail="no manuscript entrypoint is available to anchor proof review freshness",
        )

    review_anchor = _latest_matching_math_review_anchor(project_root, entrypoint)
    actual_manuscript_sha256 = compute_sha256(entrypoint)
    watched_files = _collect_manuscript_watched_files(entrypoint.parent)
    manifest_path = manuscript_proof_review_manifest_path(entrypoint)
    if review_anchor is None:
        return ProofReviewStatus(
            scope="manuscript",
            state="not_reviewed",
            can_rely_on_prior_review=False,
            detail="no prior staged math review artifact matches the active manuscript",
            manifest_path=manifest_path,
            watched_files=watched_files,
        )
    if review_anchor.validation_errors:
        return ProofReviewStatus(
            scope="manuscript",
            state="invalid_required_artifact",
            can_rely_on_prior_review=False,
            detail=(
                f"{_relative_path(project_root, review_anchor.stage_artifact)} is not a valid proof-review anchor: "
                + "; ".join(review_anchor.validation_errors[:3])
            ),
            manifest_path=manifest_path,
            anchor_artifact=review_anchor.stage_artifact,
            watched_files=_with_extra_watched_files(
                watched_files,
                review_anchor.stage_artifact,
                review_anchor.claim_index_artifact,
            ),
        )

    anchor_artifact = review_anchor.stage_artifact
    watched_files = _with_extra_watched_files(
        watched_files,
        review_anchor.stage_artifact,
        review_anchor.claim_index_artifact,
    )
    watched_files = _with_extra_watched_files(
        watched_files,
        _resolve_review_artifacts(project_root, review_anchor.proof_artifact_paths),
    )
    if review_anchor.proof_bearing:
        proof_redteam_path = project_root / "GPD" / "review" / f"PROOF-REDTEAM{review_anchor.round_suffix}.md"
        watched_files = _with_extra_watched_files(watched_files, proof_redteam_path)
        if not proof_redteam_path.exists():
            return ProofReviewStatus(
                scope="manuscript",
                state="missing_required_artifact",
                can_rely_on_prior_review=False,
                detail=(
                    "proof-bearing manuscript review requires "
                    f"{_relative_path(project_root, proof_redteam_path)} to exist with `status: passed`"
                ),
                manifest_path=manifest_path,
                anchor_artifact=proof_redteam_path,
                watched_files=watched_files,
            )
        proof_redteam_status, proof_redteam_error = _read_proof_redteam_status(
            proof_redteam_path,
            project_root=project_root,
            expected_manuscript_path=_relative_path(project_root, entrypoint),
            expected_manuscript_sha256=actual_manuscript_sha256,
            expected_round=review_anchor.round_number,
            expected_claim_ids=review_anchor.theorem_claim_ids,
            expected_proof_artifact_paths=review_anchor.proof_artifact_paths,
        )
        if proof_redteam_error is not None:
            return ProofReviewStatus(
                scope="manuscript",
                state="invalid_required_artifact",
                can_rely_on_prior_review=False,
                detail=f"{_relative_path(project_root, proof_redteam_path)} is invalid: {proof_redteam_error}",
                manifest_path=manifest_path,
                anchor_artifact=proof_redteam_path,
                watched_files=watched_files,
            )
        if proof_redteam_status != "passed":
            return ProofReviewStatus(
                scope="manuscript",
                state="open_required_artifact",
                can_rely_on_prior_review=False,
                detail=(
                    f"{_relative_path(project_root, proof_redteam_path)} reports status `{proof_redteam_status}`; "
                    "proof-bearing manuscript review requires `status: passed`"
                ),
                manifest_path=manifest_path,
                anchor_artifact=proof_redteam_path,
                watched_files=watched_files,
            )
        anchor_artifact = proof_redteam_path

    return _resolve_status(
        project_root,
        scope="manuscript",
        anchor_artifact=anchor_artifact,
        manifest_path=manifest_path,
        watched_files=watched_files,
        persist_manifest=persist_manifest,
    )


def _resolve_status(
    project_root: Path,
    *,
    scope: str,
    anchor_artifact: Path,
    manifest_path: Path,
    watched_files: tuple[Path, ...],
    persist_manifest: bool,
) -> ProofReviewStatus:
    current_hashes = {_relative_path(project_root, path): compute_sha256(path) for path in watched_files}

    if manifest_path.exists():
        try:
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_records = _manifest_records(manifest_payload, scope=scope)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return ProofReviewStatus(
                scope=scope,
                state="invalid_manifest",
                can_rely_on_prior_review=False,
                detail=f"proof-review manifest is invalid: {exc}",
                manifest_path=manifest_path,
                anchor_artifact=anchor_artifact,
                watched_files=watched_files,
            )

        expected_hashes = manifest_records["hashes"]
        changed_labels = sorted(
            path for path in expected_hashes.keys() & current_hashes.keys() if expected_hashes[path] != current_hashes[path]
        )
        missing_labels = sorted(path for path in expected_hashes.keys() - current_hashes.keys())
        unexpected_labels = sorted(path for path in current_hashes.keys() - expected_hashes.keys())
        changed_files = tuple(project_root / path for path in [*changed_labels, *missing_labels, *unexpected_labels])

        if changed_files:
            return ProofReviewStatus(
                scope=scope,
                state="stale",
                can_rely_on_prior_review=False,
                detail=(
                    f"proof-review manifest is stale: {', '.join([*changed_labels, *missing_labels, *unexpected_labels][:3])}"
                ),
                manifest_path=manifest_path,
                anchor_artifact=anchor_artifact,
                watched_files=watched_files,
                changed_files=changed_files,
            )

        return ProofReviewStatus(
            scope=scope,
            state="fresh",
            can_rely_on_prior_review=True,
            detail=(
                f"{_relative_path(project_root, manifest_path)} matches {len(watched_files)} proof-affecting file(s)"
            ),
            manifest_path=manifest_path,
            anchor_artifact=anchor_artifact,
            watched_files=watched_files,
        )

    anchor_mtime = anchor_artifact.stat().st_mtime_ns
    changed_files = tuple(path for path in watched_files if path.stat().st_mtime_ns > anchor_mtime)
    if changed_files:
        return ProofReviewStatus(
            scope=scope,
            state="stale",
            can_rely_on_prior_review=False,
            detail=(
                f"{len(changed_files)} proof-affecting file(s) changed after {_relative_path(project_root, anchor_artifact)}: "
                + ", ".join(_relative_path(project_root, path) for path in changed_files[:3])
            ),
            manifest_path=manifest_path,
            anchor_artifact=anchor_artifact,
            watched_files=watched_files,
            changed_files=changed_files,
        )

    manifest_bootstrapped = False
    if persist_manifest:
        _write_manifest(
            manifest_path,
            scope=scope,
            anchor_artifact=anchor_artifact,
            watched_files=current_hashes,
        )
        manifest_bootstrapped = True

    detail = (
        f"{_relative_path(project_root, manifest_path)} bootstrapped from {_relative_path(project_root, anchor_artifact)}"
        if manifest_bootstrapped
        else (
            f"no proof-review manifest yet, but {len(watched_files)} proof-affecting file(s) are not newer than "
            f"{_relative_path(project_root, anchor_artifact)}"
        )
    )
    return ProofReviewStatus(
        scope=scope,
        state="fresh",
        can_rely_on_prior_review=True,
        detail=detail,
        manifest_path=manifest_path,
        anchor_artifact=anchor_artifact,
        watched_files=watched_files,
        manifest_bootstrapped=manifest_bootstrapped,
    )


def _write_manifest(
    manifest_path: Path,
    *,
    scope: str,
    anchor_artifact: Path,
    watched_files: dict[str, str],
) -> None:
    manifest_payload = {
        "version": 1,
        "scope": scope,
        "created_at": datetime.now(UTC).isoformat(),
        "anchor_artifact": anchor_artifact.as_posix(),
        "watched_files": [{"path": path, "sha256": sha256} for path, sha256 in sorted(watched_files.items())],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")


def _manifest_records(payload: object, *, scope: str) -> dict[str, dict[str, str]]:
    if not isinstance(payload, dict):
        raise ValueError("manifest payload must be a JSON object")
    if payload.get("version") != 1:
        raise ValueError("manifest version must be 1")
    if payload.get("scope") != scope:
        raise ValueError(f'manifest scope must be "{scope}"')
    watched_files = payload.get("watched_files")
    if not isinstance(watched_files, list):
        raise ValueError("manifest watched_files must be a list")

    hashes: dict[str, str] = {}
    for record in watched_files:
        if not isinstance(record, dict):
            raise ValueError("manifest watched_files entries must be objects")
        rel_path = str(record.get("path") or "").strip()
        sha256 = str(record.get("sha256") or "").strip().lower()
        if not rel_path:
            raise ValueError("manifest watched_files entries must include a non-empty path")
        if len(sha256) != 64:
            raise ValueError(f"manifest watched_files entry for {rel_path} is missing a valid sha256")
        hashes[rel_path] = sha256
    return {"hashes": hashes}


def _latest_phase_verification_artifact(phase_dir: Path) -> Path | None:
    candidates = sorted(path for path in phase_dir.glob("*VERIFICATION.md") if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _collect_phase_watched_files(phase_dir: Path, verification_path: Path, manifest_path: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(phase_dir.rglob("*")):
        if not path.is_file():
            continue
        if path == verification_path or path == manifest_path:
            continue
        if path.name.startswith("."):
            continue
        if path.name.endswith("-VERIFICATION.md") or path.name.endswith("-VALIDATION.md"):
            continue
        if path.suffix.lower() not in _PHASE_PROOF_AFFECTING_EXTENSIONS:
            continue
        files.append(path)
    return tuple(files)


def _collect_manuscript_watched_files(manuscript_root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(manuscript_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name == MANUSCRIPT_PROOF_REVIEW_MANIFEST_NAME or path.name.startswith("."):
            continue
        if path.suffix.lower() not in _MANUSCRIPT_PROOF_AFFECTING_EXTENSIONS:
            continue
        files.append(path)
    return tuple(files)


def _with_extra_watched_files(*groups: tuple[Path, ...] | Path) -> tuple[Path, ...]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for group in groups:
        if isinstance(group, Path):
            candidates = (group,)
        else:
            candidates = group
        for path in candidates:
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            ordered.append(path)
    return tuple(ordered)


def _latest_matching_math_review_anchor(project_root: Path, manuscript_entrypoint: Path) -> _MathReviewAnchor | None:
    review_dir = project_root / "GPD" / "review"
    if not review_dir.exists():
        return None

    matches: list[tuple[int, int, _MathReviewAnchor]] = []
    resolved_manuscript = _resolve_review_manuscript_path(project_root, manuscript_entrypoint.as_posix())
    expected_manuscript_path = _relative_path(project_root, manuscript_entrypoint)
    for path in sorted(review_dir.glob("STAGE-math*.json")):
        round_details = _math_review_round_details(path)
        if round_details is None:
            continue
        round_number, round_suffix = round_details
        claim_index_path = review_dir / f"CLAIMS{round_suffix}.json"
        theorem_claim_ids: list[str] = []
        proof_artifact_paths: list[str] = []
        validation_errors: list[str] = []
        claim_index = None
        claim_index_matches_current = False
        try:
            claim_index = read_claim_index(claim_index_path)
        except (OSError, json.JSONDecodeError, PydanticValidationError) as exc:
            validation_errors.append(f"{claim_index_path.name} could not be loaded: {exc}")
        else:
            claim_index_matches_current = (
                _resolve_review_manuscript_path(project_root, claim_index.manuscript_path) == resolved_manuscript
            )
            if claim_index_matches_current:
                theorem_claim_ids = sorted(claim.claim_id for claim in claim_index.claims if claim.theorem_bearing)
                proof_artifact_paths = sorted(
                    {
                        claim.artifact_path
                        for claim in claim_index.claims
                        if claim.claim_id in theorem_claim_ids and claim.artifact_path.strip()
                    }
                )
                if expected_manuscript_path is not None and expected_manuscript_path not in proof_artifact_paths:
                    proof_artifact_paths.append(expected_manuscript_path)

        try:
            report = read_stage_review_report(path)
        except (OSError, json.JSONDecodeError, PydanticValidationError) as exc:
            if not claim_index_matches_current:
                continue
            validation_errors.append(f"{path.name} could not be loaded: {exc}")
            matches.append(
                (
                    round_number,
                    path.stat().st_mtime_ns,
                    _MathReviewAnchor(
                        stage_artifact=path,
                        claim_index_artifact=claim_index_path,
                        round_number=round_number,
                        round_suffix=round_suffix,
                        proof_bearing=bool(theorem_claim_ids),
                        theorem_claim_ids=tuple(theorem_claim_ids),
                        proof_artifact_paths=tuple(path_text for path_text in proof_artifact_paths if path_text),
                        validation_errors=tuple(validation_errors),
                    ),
                )
            )
            continue
        report_matches_current = _resolve_review_manuscript_path(project_root, report.manuscript_path) == resolved_manuscript
        if not report_matches_current and not claim_index_matches_current:
            continue
        if claim_index is not None:
            validation_errors.extend(
                validate_stage_review_artifact_alignment(
                    report,
                    artifact_path=path,
                    claim_index=claim_index,
                    expected_manuscript_path=expected_manuscript_path,
                )
            )
            if theorem_claim_ids:
                missing_reviewed_claims = sorted(
                    claim_id for claim_id in theorem_claim_ids if claim_id not in set(report.claims_reviewed)
                )
                if missing_reviewed_claims:
                    validation_errors.append(
                        f"{path.name} theorem-bearing claims must appear in claims_reviewed: "
                        + ", ".join(missing_reviewed_claims)
                    )
        proof_bearing = bool(report.proof_audits) or bool(theorem_claim_ids)
        matches.append(
            (
                round_number,
                path.stat().st_mtime_ns,
                _MathReviewAnchor(
                    stage_artifact=path,
                    claim_index_artifact=claim_index_path,
                    round_number=round_number,
                    round_suffix=round_suffix,
                    proof_bearing=proof_bearing,
                    theorem_claim_ids=tuple(theorem_claim_ids),
                    proof_artifact_paths=tuple(path_text for path_text in proof_artifact_paths if path_text),
                    validation_errors=tuple(validation_errors),
                ),
            )
        )

    if not matches:
        return None
    _, _, latest = max(matches)
    return latest


def _math_review_round_details(path: Path) -> tuple[int, str] | None:
    match = _STAGE_MATH_FILENAME_RE.fullmatch(path.name)
    if match is None:
        return None
    round_text = match.group("round")
    round_number = int(round_text) if round_text else 1
    return round_number, match.group("round_suffix") or ""


def _claim_round_details(path: Path) -> tuple[int, str] | None:
    if path.name == "CLAIMS.json":
        return 1, ""
    if path.name.startswith("CLAIMS-R") and path.name.endswith(".json"):
        round_text = path.name[len("CLAIMS-R") : -len(".json")]
        if round_text.isdigit():
            round_number = int(round_text)
            return round_number, f"-R{round_number}"
    return None


def _read_proof_redteam_status(
    path: Path,
    *,
    project_root: Path,
    expected_manuscript_path: str | None = None,
    expected_manuscript_sha256: str | None = None,
    expected_round: int | None = None,
    expected_claim_ids: tuple[str, ...] = (),
    expected_proof_artifact_paths: tuple[str, ...] = (),
) -> tuple[str | None, str | None]:
    try:
        meta, body = extract_frontmatter(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, str(exc)
    except FrontmatterParseError as exc:
        return None, str(exc)

    raw_status = meta.get("status")
    if not isinstance(raw_status, str) or not raw_status.strip():
        return None, "top-level frontmatter `status` is missing"
    status = raw_status.strip().lower()
    if status not in _PROOF_REDTEAM_REQUIRED_STATUS_VALUES:
        return None, "top-level frontmatter `status` must be one of: passed, gaps_found, human_needed"

    reviewer = meta.get("reviewer")
    if reviewer != PROOF_AUDIT_REVIEWER:
        return None, f"top-level frontmatter `reviewer` must be `{PROOF_AUDIT_REVIEWER}`"

    claim_ids = meta.get("claim_ids")
    if not isinstance(claim_ids, list) or any(not isinstance(item, str) or not item.strip() for item in claim_ids):
        return None, "top-level frontmatter `claim_ids` must be a list of strings"
    normalized_claim_ids = tuple(dict.fromkeys(item.strip() for item in claim_ids))
    if expected_claim_ids and set(normalized_claim_ids) != set(expected_claim_ids):
        return None, "top-level frontmatter `claim_ids` does not match the theorem-bearing claims under review"

    proof_artifact_paths = meta.get("proof_artifact_paths")
    if (
        not isinstance(proof_artifact_paths, list)
        or not proof_artifact_paths
        or any(not isinstance(item, str) or not item.strip() for item in proof_artifact_paths)
    ):
        return None, "top-level frontmatter `proof_artifact_paths` must be a non-empty list of strings"
    normalized_proof_artifact_paths = tuple(dict.fromkeys(item.strip() for item in proof_artifact_paths))
    for proof_artifact_path in normalized_proof_artifact_paths:
        resolved_proof_artifact_path = _resolve_review_manuscript_path(project_root, proof_artifact_path)
        if not resolved_proof_artifact_path.exists() or not resolved_proof_artifact_path.is_file():
            return None, f"proof_artifact_paths entry does not resolve to a readable file: {proof_artifact_path}"
    if expected_proof_artifact_paths:
        missing_expected_paths = sorted(
            expected_path
            for expected_path in expected_proof_artifact_paths
            if expected_path not in normalized_proof_artifact_paths
        )
        if missing_expected_paths:
            return None, "proof_artifact_paths does not cover the expected proof artifacts under review"

    if expected_manuscript_path is not None:
        raw_manuscript_path = meta.get("manuscript_path")
        if not isinstance(raw_manuscript_path, str) or not raw_manuscript_path.strip():
            return None, "top-level frontmatter `manuscript_path` is missing"
        resolved_artifact_path = _resolve_review_manuscript_path(project_root, raw_manuscript_path.strip())
        resolved_expected_path = _resolve_review_manuscript_path(project_root, expected_manuscript_path)
        if resolved_artifact_path != resolved_expected_path:
            return None, "top-level frontmatter `manuscript_path` does not match the active manuscript"

    if expected_manuscript_sha256 is not None:
        raw_manuscript_sha256 = meta.get("manuscript_sha256")
        if not isinstance(raw_manuscript_sha256, str) or len(raw_manuscript_sha256.strip()) != 64:
            return None, "top-level frontmatter `manuscript_sha256` must be a lowercase 64-hex digest"
        if raw_manuscript_sha256.strip().lower() != expected_manuscript_sha256.lower():
            return None, "top-level frontmatter `manuscript_sha256` does not match the active manuscript"

    if expected_round is not None:
        raw_round = meta.get("round")
        try:
            round_number = int(raw_round)
        except (TypeError, ValueError):
            return None, "top-level frontmatter `round` must be an integer"
        if round_number != expected_round:
            return None, "top-level frontmatter `round` does not match the active review round"

    structured_audit, structured_audit_error = _read_proof_redteam_structured_audit(meta)
    if structured_audit_error is not None:
        return None, structured_audit_error

    required_sections = (
        "# Proof Redteam",
        "## Proof Inventory",
        "## Coverage Ledger",
        "## Adversarial Probe",
        "## Verdict",
        "## Required Follow-Up",
    )
    missing_sections = [section for section in required_sections if section not in body]
    if missing_sections:
        return None, f"proof-redteam body is missing required sections: {', '.join(missing_sections)}"

    exact_claim_line = _first_meaningful_line(_section_body(body, "## Proof Inventory"))
    if exact_claim_line is None or not exact_claim_line.lower().startswith("- exact claim / theorem text:"):
        return None, "proof-redteam Proof Inventory must start with the exact claim / theorem text"
    if exact_claim_line.rstrip().endswith(":"):
        return None, "proof-redteam exact claim / theorem text must not be blank"

    required_subsections = (
        "### Named-Parameter Coverage",
        "### Hypothesis Coverage",
        "### Quantifier / Domain Coverage",
        "### Conclusion-Clause Coverage",
    )
    for subsection in required_subsections:
        if not _section_has_substantive_content(body, subsection):
            return None, f"proof-redteam coverage subsection is empty: {subsection}"

    adversarial_probe_body = _section_body(body, "## Adversarial Probe")
    if "Probe type:" not in adversarial_probe_body or "Result:" not in adversarial_probe_body:
        return None, "proof-redteam Adversarial Probe must record both probe type and result"

    verdict_body = _section_body(body, "## Verdict")
    if "Scope status:" not in verdict_body or "Quantifier status:" not in verdict_body or "Counterexample status:" not in verdict_body:
        return None, "proof-redteam Verdict must include scope, quantifier, and counterexample status lines"

    if status == "passed":
        structured_failures: list[str] = []
        if structured_audit.missing_parameter_symbols:
            structured_failures.append(
                "missing_parameter_symbols=" + ", ".join(structured_audit.missing_parameter_symbols)
            )
        if structured_audit.missing_hypothesis_ids:
            structured_failures.append("missing_hypothesis_ids=" + ", ".join(structured_audit.missing_hypothesis_ids))
        if structured_audit.coverage_gaps:
            structured_failures.append("coverage_gaps=" + ", ".join(structured_audit.coverage_gaps[:3]))
        if structured_audit.scope_status != "matched":
            structured_failures.append(f"scope_status={structured_audit.scope_status}")
        if structured_audit.quantifier_status != "matched":
            structured_failures.append(f"quantifier_status={structured_audit.quantifier_status}")
        if structured_audit.counterexample_status != "none_found":
            structured_failures.append(f"counterexample_status={structured_audit.counterexample_status}")
        if structured_failures:
            return None, (
                "proof-redteam `status: passed` is inconsistent with structured audit fields: "
                + "; ".join(structured_failures)
            )

    return status, None


def _read_proof_redteam_structured_audit(meta: dict[str, object]) -> tuple[_ProofRedteamStructuredAudit | None, str | None]:
    missing_parameter_symbols, error = _read_proof_redteam_string_list(meta, "missing_parameter_symbols")
    if error is not None:
        return None, error
    missing_hypothesis_ids, error = _read_proof_redteam_string_list(meta, "missing_hypothesis_ids")
    if error is not None:
        return None, error
    coverage_gaps, error = _read_proof_redteam_string_list(meta, "coverage_gaps")
    if error is not None:
        return None, error
    scope_status, error = _read_proof_redteam_status_value(meta, "scope_status", _PROOF_REDTEAM_REQUIRED_SCOPE_STATUS_VALUES)
    if error is not None:
        return None, error
    quantifier_status, error = _read_proof_redteam_status_value(
        meta,
        "quantifier_status",
        _PROOF_REDTEAM_REQUIRED_QUANTIFIER_STATUS_VALUES,
    )
    if error is not None:
        return None, error
    counterexample_status, error = _read_proof_redteam_status_value(
        meta,
        "counterexample_status",
        _PROOF_REDTEAM_REQUIRED_COUNTEREXAMPLE_STATUS_VALUES,
    )
    if error is not None:
        return None, error
    return (
        _ProofRedteamStructuredAudit(
            missing_parameter_symbols=missing_parameter_symbols,
            missing_hypothesis_ids=missing_hypothesis_ids,
            coverage_gaps=coverage_gaps,
            scope_status=scope_status,
            quantifier_status=quantifier_status,
            counterexample_status=counterexample_status,
        ),
        None,
    )


def _read_proof_redteam_string_list(meta: dict[str, object], field_name: str) -> tuple[tuple[str, ...], str | None]:
    if field_name not in meta:
        return (), f"top-level frontmatter `{field_name}` is missing"
    value = meta.get(field_name)
    if not isinstance(value, list):
        return (), f"top-level frontmatter `{field_name}` must be a list of strings"
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return (), f"top-level frontmatter `{field_name}` must be a list of strings"
    return tuple(dict.fromkeys(item.strip() for item in value)), None


def _read_proof_redteam_status_value(
    meta: dict[str, object],
    field_name: str,
    allowed_values: frozenset[str],
) -> tuple[str, str | None]:
    if field_name not in meta:
        return "", f"top-level frontmatter `{field_name}` is missing"
    value = meta.get(field_name)
    if not isinstance(value, str) or not value.strip():
        allowed = ", ".join(sorted(allowed_values))
        return "", f"top-level frontmatter `{field_name}` must be one of: {allowed}"
    normalized = value.strip().lower()
    if normalized not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        return "", f"top-level frontmatter `{field_name}` must be one of: {allowed}"
    return normalized, None


def _section_body(body: str, heading: str) -> str:
    start = body.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    remaining = body[start:]
    next_heading_offsets = [offset for marker in ("\n## ", "\n### ", "\n# ") if (offset := remaining.find(marker)) >= 0]
    if not next_heading_offsets:
        return remaining
    return remaining[: min(next_heading_offsets)]


def _first_meaningful_line(section_body: str) -> str | None:
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if line:
            return line
    return None


def _section_has_substantive_content(body: str, heading: str) -> bool:
    section_body = _section_body(body, heading)
    pipe_lines = 0
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {"| --- | --- | --- | --- |", "| --- | --- | --- | --- | --- |"}:
            continue
        if line.startswith("|"):
            pipe_lines += 1
            continue
        if line.startswith("-"):
            return True
    return pipe_lines >= 2


def _resolve_review_manuscript_path(project_root: Path, manuscript_path: str) -> Path:
    artifact_path = Path(manuscript_path).expanduser()
    if not artifact_path.is_absolute():
        artifact_path = project_root / artifact_path
    return artifact_path.resolve(strict=False)


def _relative_path(project_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()

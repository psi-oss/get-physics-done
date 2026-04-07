"""Artifact-driven paper-quality input construction."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import (
    ComparisonVerdict,
    ContractResults,
    ConventionLock,
    ResearchContract,
    parse_comparison_verdicts_data_strict,
    parse_contract_results_data_artifact,
)
from gpd.core.constants import STANDALONE_VALIDATION, VALIDATION_SUFFIX, ProjectLayout
from gpd.core.conventions import check_assertions, convention_check
from gpd.core.errors import GPDError
from gpd.core.frontmatter import (
    FrontmatterParseError,
    _find_matching_plan_contract,
    _parse_comparison_verdicts,
    _summary_contract_errors,
    _validate_contract_mapping,
    extract_frontmatter,
)
from gpd.core.manuscript_artifacts import locate_publication_artifact, resolve_current_manuscript_resolution
from gpd.core.paper_quality import (
    BinaryCheck,
    CitationsQualityInput,
    CompletenessQualityInput,
    ConventionsQualityInput,
    CoverageMetric,
    FiguresQualityInput,
    PaperQualityInput,
    ResultsQualityInput,
    VerificationConfidence,
    VerificationQualityInput,
    validate_tex_draft,
)
from gpd.mcp.paper.bibliography import BibliographyAudit
from gpd.mcp.paper.models import ArtifactManifest, PaperConfig, is_supported_paper_journal

__all__ = ["build_paper_quality_input"]


_PLACEHOLDER_RE = re.compile(r"TODO|FIXME|PENDING|TBD|\\text\{\[PENDING\]\}")
_MISSING_CITE_RE = re.compile(r"\\cite\{MISSING:")
_ABSTRACT_RE = re.compile(
    r"(\\begin\{abstract\}[\s\S]*?\\end\{abstract\}|^\s{0,3}#{1,6}\s*abstract\b)",
    re.IGNORECASE | re.MULTILINE,
)
_INTRO_RE = re.compile(
    r"(\\section\*?\{[^}]*introduction[^}]*\}|^\s{0,3}#{1,6}\s*introduction\b)",
    re.IGNORECASE | re.MULTILINE,
)
_CONCLUSION_RE = re.compile(
    r"(\\section\*?\{[^}]*conclusion[^}]*\}|^\s{0,3}#{1,6}\s*conclusion\b)",
    re.IGNORECASE | re.MULTILINE,
)
_SUPPLEMENT_RE = re.compile(r"appendix|supplement", re.IGNORECASE)
_CITE_RE = re.compile(r"\\cite\{([^}]*)\}")
_BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
_DERIVATION_ARTIFACT_RE = re.compile(r"(?i)^derivation-(?!state\.).+\.(?:md|markdown|tex|py)$")
_DERIVATION_ARTIFACT_SUFFIXES = (".md", ".markdown", ".tex", ".py")
_MANUSCRIPT_CONTENT_SUFFIXES = (".tex", ".md")


class _FigureTrackerEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    label: str = ""
    kind: str = "figure"
    role: str = "other"
    path: str = ""
    contract_ids: list[str] = Field(default_factory=list)
    decisive: bool = False
    has_units: bool = False
    has_uncertainty: bool = False
    referenced_in_text: bool = False
    caption_self_contained: bool = False
    colorblind_safe: bool = False
    comparison_sources: list[str] = Field(default_factory=list)

    @property
    def stable_keys(self) -> set[str]:
        keys = {self.id, self.label, self.path, *(self.contract_ids or [])}
        return {key for key in keys if key}


class _ContractCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_targets: int = 0
    satisfied_targets: int = 0
    confidences: list[VerificationConfidence] = Field(default_factory=list)
    latest_report_passed: bool = False
    requires_decisive_comparison: bool = False
    comparison_verdicts_valid: bool = True
    contract_results_seen: bool = False
    contract_results_parse_ok: bool = True
    contract_results_alignment_ok: bool = True


class _ManuscriptReferenceStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_id: str = ""
    bibtex_key: str = ""
    title: str = ""
    resolution_status: str = ""
    verification_status: str = ""
    cited_in_text: bool = False


def _coverage_metric(satisfied: int, total: int) -> CoverageMetric:
    return CoverageMetric(satisfied=satisfied, total=total)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _load_json(path: Path) -> dict[str, object]:
    text = _read_text(path)
    if text is None:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_artifact_manifest(path: Path | None) -> ArtifactManifest | None:
    if path is None or not path.exists():
        return None
    payload = _load_json(path)
    if not payload:
        return None
    try:
        return ArtifactManifest.model_validate(payload)
    except PydanticValidationError:
        return None


def _load_bibliography_audit(path: Path | None) -> BibliographyAudit | None:
    if path is None or not path.exists():
        return None
    payload = _load_json(path)
    if not payload:
        return None
    try:
        return BibliographyAudit.model_validate(payload)
    except PydanticValidationError:
        return None


def _load_convention_lock(project_root: Path) -> ConventionLock | None:
    payload = _load_json(project_root / "GPD" / "state.json")
    lock_data = payload.get("convention_lock")
    if not isinstance(lock_data, dict):
        return None
    try:
        return ConventionLock.model_validate(lock_data)
    except PydanticValidationError:
        return None


def _extract_meta(path: Path, *, parse_errors: list[str] | None = None) -> dict[str, object]:
    content = _read_text(path)
    if content is None:
        return {}
    try:
        meta, _ = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        if parse_errors is not None:
            parse_errors.append(f"{path.name}: {exc}")
        return {}
    return meta


def _plan_contract_for_artifact(
    path: Path,
    meta: dict[str, object],
    *,
    project_root: Path,
) -> ResearchContract | None:
    """Return the canonical plan contract for one phase artifact when available."""

    contract_data = meta.get("contract")
    if isinstance(contract_data, dict):
        return _validate_contract_mapping(
            contract_data,
            enforce_plan_semantics=True,
            project_root=project_root,
        ).contract
    return _find_matching_plan_contract(path.parent, meta, project_root=project_root).contract


def _collect_manuscript_content(
    manuscript_dir: Path,
    *,
    entrypoint: Path | None,
) -> tuple[list[Path], str]:
    content_files: list[Path] = []
    seen: set[Path] = set()

    def add_candidate(path: Path) -> None:
        if path in seen or not path.exists() or not path.is_file():
            return
        if path.suffix.lower() not in _MANUSCRIPT_CONTENT_SUFFIXES:
            return
        seen.add(path)
        content_files.append(path)

    if entrypoint is not None:
        add_candidate(entrypoint)

    for candidate in sorted(
        path
        for path in manuscript_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in _MANUSCRIPT_CONTENT_SUFFIXES
    ):
        add_candidate(candidate)

    bodies = []
    for content_file in content_files:
        text = _read_text(content_file)
        if text is not None:
            bodies.append(text)
    return content_files, "\n".join(bodies)


def _first_existing_path(*candidates: Path) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_manuscript_config(manuscript_dir: Path) -> dict[str, object]:
    config_path = _first_existing_path(manuscript_dir / "PAPER-CONFIG.json")
    if config_path is None:
        return {}
    payload = _load_json(config_path)
    if not payload:
        return {}
    try:
        return PaperConfig.model_validate(payload).model_dump(mode="python")
    except PydanticValidationError:
        return payload


def _best_effort_manuscript_root(project_root: Path) -> Path | None:
    resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=True)
    if resolution.status == "resolved" and resolution.manuscript_root is not None:
        return resolution.manuscript_root
    if resolution.status == "ambiguous":
        return None

    candidates: list[Path] = []
    for root_name in ("paper", "manuscript", "draft"):
        candidate = project_root / root_name
        if not candidate.exists() or not candidate.is_dir():
            continue
        has_publication_artifacts = any(
            (candidate / artifact_name).exists()
            for artifact_name in (
                "PAPER-CONFIG.json",
                "ARTIFACT-MANIFEST.json",
                "BIBLIOGRAPHY-AUDIT.json",
                "FIGURE_TRACKER.md",
                "reproducibility-manifest.json",
            )
        )
        has_manuscript_content = any(
            path.is_file() and path.suffix.lower() in _MANUSCRIPT_CONTENT_SUFFIXES for path in candidate.rglob("*")
        )
        if has_publication_artifacts or has_manuscript_content:
            candidates.append(candidate)

    return candidates[0] if len(candidates) == 1 else None


def _derivation_artifacts(project_root: Path) -> list[Path]:
    gpd_root = project_root / "GPD"
    if not gpd_root.exists():
        return []
    return sorted(
        path
        for path in gpd_root.rglob("derivation-*")
        if path.is_file()
        and path.suffix.lower() in _DERIVATION_ARTIFACT_SUFFIXES
        and _DERIVATION_ARTIFACT_RE.fullmatch(path.name)
    )


def _build_conventions_input(project_root: Path) -> ConventionsQualityInput:
    lock = _load_convention_lock(project_root)
    lock_check = convention_check(lock) if lock is not None else None
    derivation_paths = _derivation_artifacts(project_root)

    if not derivation_paths:
        coverage = CoverageMetric(not_applicable=True)
    elif lock is None or lock_check is None or lock_check.set_count == 0:
        coverage = CoverageMetric(satisfied=0, total=len(derivation_paths))
    else:
        satisfied = 0
        for path in derivation_paths:
            content = _read_text(path)
            if content is None:
                continue
            assertion_check = check_assertions(
                content,
                lock,
                filename=str(path.relative_to(project_root)),
                require_assertions=True,
            )
            if assertion_check.passed:
                satisfied += 1
        coverage = _coverage_metric(satisfied, len(derivation_paths))

    return ConventionsQualityInput(
        convention_lock_complete=BinaryCheck(passed=bool(lock_check and lock_check.complete)),
        assert_convention_coverage=coverage,
        notation_consistent=BinaryCheck(not_applicable=True),
    )


def _available_citation_keys(manuscript_dir: Path, bibliography_audit: BibliographyAudit | None) -> set[str]:
    keys: set[str] = set()

    if bibliography_audit is not None:
        for entry in bibliography_audit.entries:
            if entry.key.strip():
                keys.add(entry.key.strip())

    for bib_path in sorted(manuscript_dir.glob("*.bib")):
        content = _read_text(bib_path)
        if content is None:
            continue
        keys.update(match.group(1).strip() for match in _BIB_ENTRY_RE.finditer(content) if match.group(1).strip())

    return keys


def _manuscript_reference_status(
    bibliography_audit: BibliographyAudit | None,
    *,
    cite_keys: set[str],
) -> list[_ManuscriptReferenceStatus]:
    if bibliography_audit is None:
        return []

    status_entries: list[_ManuscriptReferenceStatus] = []
    for entry in bibliography_audit.entries:
        reference_id = entry.reference_id.strip() if entry.reference_id else ""
        bibtex_key = entry.key.strip()
        if not reference_id and not bibtex_key:
            continue
        status_entries.append(
            _ManuscriptReferenceStatus(
                reference_id=reference_id,
                bibtex_key=bibtex_key,
                title=entry.title.strip(),
                resolution_status=entry.resolution_status,
                verification_status=entry.verification_status,
                cited_in_text=bibtex_key in cite_keys if bibtex_key else False,
            )
        )
    return status_entries


def _load_figure_registry(manuscript_dir: Path) -> list[_FigureTrackerEntry]:
    tracker_path = manuscript_dir / "FIGURE_TRACKER.md"
    meta = _extract_meta(tracker_path)
    raw = meta.get("figure_registry")
    if not isinstance(raw, list):
        return []

    entries: list[_FigureTrackerEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(_FigureTrackerEntry.model_validate(item))
        except PydanticValidationError:
            continue
    return entries


def _parse_comparison_verdict_entries(
    value: object,
    *,
    errors: list[str] | None = None,
) -> list[ComparisonVerdict]:
    try:
        return parse_comparison_verdicts_data_strict(value)
    except ValueError as exc:
        if errors is not None and value is not None:
            errors.append(str(exc))
        return []


def _comparison_verdict_key(verdict: ComparisonVerdict) -> tuple[str, str | None, str | None, str]:
    return (verdict.subject_id, verdict.reference_id, verdict.metric, verdict.verdict)


def _merge_comparison_verdict(existing: ComparisonVerdict, incoming: ComparisonVerdict) -> ComparisonVerdict:
    updates: dict[str, object] = {}

    if existing.subject_kind == "other" and incoming.subject_kind != "other":
        updates["subject_kind"] = incoming.subject_kind
    if existing.subject_role == "other" and incoming.subject_role != "other":
        updates["subject_role"] = incoming.subject_role
    if existing.comparison_kind == "other" and incoming.comparison_kind != "other":
        updates["comparison_kind"] = incoming.comparison_kind

    for field in ("reference_id", "metric", "threshold", "recommended_action", "notes"):
        existing_value = getattr(existing, field)
        incoming_value = getattr(incoming, field)
        if existing_value in (None, "") and incoming_value not in (None, ""):
            updates[field] = incoming_value

    return existing.model_copy(update=updates) if updates else existing


def _collect_comparison_verdicts(
    project_root: Path,
    *,
    manuscript_root: Path | None,
) -> tuple[list[ComparisonVerdict], bool]:
    verdicts_by_key: dict[tuple[str, str | None, str | None, str], ComparisonVerdict] = {}
    parse_errors: list[str] = []
    layout = ProjectLayout(project_root)
    phase_root = project_root / "GPD" / "phases"

    candidate_roots = [
        phase_root,
        project_root / "GPD" / "comparisons",
    ]
    if manuscript_root is not None:
        candidate_roots.append(manuscript_root)
    for root in candidate_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if root == phase_root and not _is_contract_coverage_artifact(path, layout):
                continue
            meta = _extract_meta(path, parse_errors=parse_errors)
            for verdict in _parse_comparison_verdict_entries(meta.get("comparison_verdicts"), errors=parse_errors):
                key = _comparison_verdict_key(verdict)
                existing = verdicts_by_key.get(key)
                verdicts_by_key[key] = verdict if existing is None else _merge_comparison_verdict(existing, verdict)
    return list(verdicts_by_key.values()), not parse_errors


def _resolve_paper_journal(artifact_manifest: ArtifactManifest | None, paper_config: dict[str, object]) -> str:
    """Return the supported journal key to use for quality scoring.

    Manifest journals are preferred when they are supported builder keys.
    Unsupported manifest journals fall back to a supported PAPER-CONFIG journal
    instead of overriding it.
    """

    manifest_journal = artifact_manifest.journal if artifact_manifest is not None else None
    config_journal = paper_config.get("journal")

    if is_supported_paper_journal(manifest_journal):
        return manifest_journal
    if is_supported_paper_journal(config_journal):
        return str(config_journal)
    return "generic"


def _manifest_metadata_matches_active_entrypoint(
    artifact_manifest: ArtifactManifest | None,
    *,
    manuscript_root: Path | None,
    manuscript_entrypoint: Path | None,
) -> bool:
    """Return whether manifest metadata matches the currently resolved manuscript entrypoint."""
    if artifact_manifest is None or manuscript_root is None or manuscript_entrypoint is None:
        return False
    resolved_entrypoint = manuscript_entrypoint.resolve(strict=False)
    for artifact in artifact_manifest.artifacts:
        if artifact.category != "tex":
            continue
        candidate = manuscript_root / artifact.path
        if candidate.exists() and candidate.resolve(strict=False) == resolved_entrypoint:
            return True
    return False


def _is_contract_coverage_artifact(path: Path, layout: ProjectLayout) -> bool:
    """Return whether a phase markdown file participates in contract coverage."""
    filename = path.name
    return (
        layout.is_plan_file(filename)
        or layout.is_summary_file(filename)
        or layout.is_verification_file(filename)
        or filename.endswith(VALIDATION_SUFFIX)
        or filename == STANDALONE_VALIDATION
    )


def _collect_contract_coverage(project_root: Path) -> _ContractCoverage:
    total_claims: set[str] = set()
    total_deliverables: set[str] = set()
    total_tests: set[str] = set()
    passed_claims: set[str] = set()
    passed_deliverables: set[str] = set()
    passed_tests: set[str] = set()
    confidences: list[VerificationConfidence] = []
    latest_verified_at = ""
    latest_report_passed = False
    requires_decisive_comparison = False
    comparison_verdicts_valid = True
    contract_results_seen = False
    contract_results_parse_ok = True
    contract_results_alignment_ok = True
    frontmatter_parse_errors = False

    phases_root = project_root / "GPD" / "phases"
    if not phases_root.exists():
        return _ContractCoverage()
    layout = ProjectLayout(project_root)

    for path in sorted(phases_root.rglob("*.md")):
        if not _is_contract_coverage_artifact(path, layout):
            continue
        parse_errors: list[str] = []
        meta = _extract_meta(path, parse_errors=parse_errors)
        if parse_errors:
            frontmatter_parse_errors = True
        plan_contract = _plan_contract_for_artifact(path, meta, project_root=project_root)
        if plan_contract is not None:
            total_claims.update(claim.id for claim in plan_contract.claims)
            total_deliverables.update(deliverable.id for deliverable in plan_contract.deliverables)
            total_tests.update(test.id for test in plan_contract.acceptance_tests)
            if any(test.kind in {"benchmark", "cross_method"} for test in plan_contract.acceptance_tests):
                requires_decisive_comparison = True
            if any(
                reference.role == "benchmark" or "compare" in reference.required_actions
                for reference in plan_contract.references
            ):
                requires_decisive_comparison = True

        raw_results = meta.get("contract_results")
        contract_alignment_errors: list[str] = []
        contract_results: ContractResults | None = None
        if "contract_results" in meta or parse_errors:
            contract_results_seen = True
            if parse_errors:
                contract_results_parse_ok = False
                contract_results_alignment_ok = False
            elif not isinstance(raw_results, dict):
                contract_results_parse_ok = False
                contract_results_alignment_ok = False
            else:
                try:
                    contract_results = parse_contract_results_data_artifact(raw_results)
                except (PydanticValidationError, TypeError, ValueError):
                    contract_results = None
                    contract_results_parse_ok = False
                    contract_results_alignment_ok = False
                else:
                    if plan_contract is None:
                        contract_results_alignment_ok = False
                    else:
                        comparison_verdicts: list[ComparisonVerdict] = []
                        try:
                            comparison_verdicts = _parse_comparison_verdicts(meta)
                        except (PydanticValidationError, TypeError, ValueError) as exc:
                            contract_alignment_errors.append(f"comparison_verdicts: {exc}")
                        if not contract_alignment_errors:
                            contract_alignment_errors = _summary_contract_errors(
                                plan_contract,
                                contract_results,
                                comparison_verdicts,
                            )
                        if comparison_verdicts and contract_alignment_errors:
                            comparison_verdicts_valid = False

                        if not contract_alignment_errors:
                            expected_claim_ids = {claim.id for claim in plan_contract.claims}
                            expected_deliverable_ids = {deliverable.id for deliverable in plan_contract.deliverables}
                            expected_test_ids = {test.id for test in plan_contract.acceptance_tests}
                            passed_claims.update(
                                claim_id
                                for claim_id, entry in contract_results.claims.items()
                                if claim_id in expected_claim_ids and entry.status == "passed"
                            )
                            passed_deliverables.update(
                                deliverable_id
                                for deliverable_id, entry in contract_results.deliverables.items()
                                if deliverable_id in expected_deliverable_ids and entry.status == "passed"
                            )
                            passed_tests.update(
                                test_id
                                for test_id, entry in contract_results.acceptance_tests.items()
                                if test_id in expected_test_ids and entry.status == "passed"
                            )
                            for expected_ids, entries in (
                                (expected_claim_ids, contract_results.claims),
                                (expected_deliverable_ids, contract_results.deliverables),
                                (expected_test_ids, contract_results.acceptance_tests),
                            ):
                                for entry_id, entry in entries.items():
                                    if entry_id not in expected_ids:
                                        continue
                                    for evidence in entry.evidence:
                                        if evidence.confidence == "high":
                                            confidences.append(VerificationConfidence.independently_confirmed)
                                        elif evidence.confidence == "medium":
                                            confidences.append(VerificationConfidence.structurally_present)
                                        elif evidence.confidence == "low":
                                            confidences.append(VerificationConfidence.unable_to_verify)
                                        else:
                                            confidences.append(VerificationConfidence.unreliable)
                        else:
                            contract_results_alignment_ok = False

        verified_at = str(meta.get("verified") or meta.get("completed") or "")
        status = str(meta.get("status") or "")
        is_verification_report = path.name.endswith("VERIFICATION.md")
        report_has_valid_contract_ledger = (
            plan_contract is not None and contract_results is not None and not contract_alignment_errors
        )
        if is_verification_report and verified_at >= latest_verified_at:
            latest_verified_at = verified_at
            latest_report_passed = status == "passed" and report_has_valid_contract_ledger

    total_targets = len(total_claims) + len(total_deliverables) + len(total_tests)
    satisfied_targets = len(passed_claims) + len(passed_deliverables) + len(passed_tests)
    return _ContractCoverage(
        total_targets=total_targets,
        satisfied_targets=satisfied_targets,
        confidences=confidences,
        latest_report_passed=latest_report_passed,
        requires_decisive_comparison=requires_decisive_comparison,
        comparison_verdicts_valid=comparison_verdicts_valid and not frontmatter_parse_errors,
        contract_results_seen=contract_results_seen,
        contract_results_parse_ok=contract_results_parse_ok,
        contract_results_alignment_ok=contract_results_alignment_ok,
    )


def _find_verdict_for_entry(
    entry: _FigureTrackerEntry,
    verdicts: list[ComparisonVerdict],
    project_root: Path,
) -> list[ComparisonVerdict]:
    matched: dict[tuple[str, str | None, str | None, str], ComparisonVerdict] = {}

    def _record(verdict: ComparisonVerdict) -> None:
        key = _comparison_verdict_key(verdict)
        existing = matched.get(key)
        matched[key] = verdict if existing is None else _merge_comparison_verdict(existing, verdict)

    for verdict in verdicts:
        if verdict.subject_id in entry.stable_keys:
            _record(verdict)

    for rel_path in entry.comparison_sources:
        path = project_root / rel_path
        meta = _extract_meta(path)
        for verdict in _parse_comparison_verdict_entries(meta.get("comparison_verdicts")):
            _record(verdict)
    return list(matched.values())


def _build_figures_input(
    figure_registry: list[_FigureTrackerEntry],
    verdicts: list[ComparisonVerdict],
    project_root: Path,
    *,
    comparison_required: bool,
) -> tuple[FiguresQualityInput, ResultsQualityInput]:
    if not figure_registry:
        comparison_missing_inventory = comparison_required
        figures = FiguresQualityInput(
            decisive_artifacts_labeled_with_units=CoverageMetric()
            if comparison_missing_inventory
            else CoverageMetric(not_applicable=True),
            decisive_artifacts_uncertainty_qualified=CoverageMetric()
            if comparison_missing_inventory
            else CoverageMetric(not_applicable=True),
            decisive_artifacts_referenced_in_text=CoverageMetric()
            if comparison_missing_inventory
            else CoverageMetric(not_applicable=True),
            decisive_artifact_roles_clear=CoverageMetric()
            if comparison_missing_inventory
            else CoverageMetric(not_applicable=True),
        )
        return figures, ResultsQualityInput(
            comparison_with_prior_work_present=BinaryCheck(
                passed=False if comparison_missing_inventory else bool(verdicts),
                not_applicable=not comparison_missing_inventory,
            ),
            physical_interpretation_present=BinaryCheck(not_applicable=True),
            decisive_artifacts_with_explicit_verdicts=CoverageMetric()
            if comparison_missing_inventory
            else CoverageMetric(not_applicable=True),
            decisive_artifacts_benchmark_anchored=CoverageMetric()
            if comparison_missing_inventory
            else CoverageMetric(not_applicable=True),
            decisive_comparison_failures_scoped=BinaryCheck(
                passed=False,
                not_applicable=not comparison_missing_inventory,
            ),
        )

    total_figures = len(figure_registry)
    decisive_entries = [
        entry for entry in figure_registry if entry.decisive or entry.role in {"smoking_gun", "benchmark", "comparison"}
    ]
    decisive_inventory_missing = comparison_required and not decisive_entries

    decisive_with_verdict = 0
    decisive_with_anchor = 0
    decisive_failures_scoped = True
    uncertainty_count = 0

    for entry in decisive_entries:
        if entry.has_uncertainty:
            uncertainty_count += 1
        entry_verdicts = _find_verdict_for_entry(entry, verdicts, project_root)
        decisive_entry_verdicts = [verdict for verdict in entry_verdicts if verdict.subject_role == "decisive"]
        if decisive_entry_verdicts:
            decisive_with_verdict += 1
        if any(verdict.reference_id for verdict in decisive_entry_verdicts):
            decisive_with_anchor += 1
        for verdict in decisive_entry_verdicts:
            if verdict.verdict in {"fail", "tension"} and not (verdict.recommended_action or verdict.notes):
                decisive_failures_scoped = False

    if decisive_inventory_missing:
        decisive_artifacts_labeled_with_units = CoverageMetric()
        decisive_artifacts_uncertainty_qualified = CoverageMetric()
        decisive_artifacts_referenced_in_text = CoverageMetric()
        decisive_artifact_roles_clear = CoverageMetric()
        decisive_uncertainties_present = CoverageMetric()
        decisive_artifacts_with_explicit_verdicts = CoverageMetric()
        decisive_artifacts_benchmark_anchored = CoverageMetric()
        comparison_with_prior_work_present = BinaryCheck(passed=False, not_applicable=False)
        decisive_comparison_failures_scoped = BinaryCheck(passed=False, not_applicable=False)
    else:
        decisive_artifacts_labeled_with_units = (
            _coverage_metric(sum(1 for entry in decisive_entries if entry.has_units), len(decisive_entries))
            if decisive_entries
            else CoverageMetric(not_applicable=True)
        )
        decisive_artifacts_uncertainty_qualified = (
            _coverage_metric(uncertainty_count, len(decisive_entries))
            if decisive_entries
            else CoverageMetric(not_applicable=True)
        )
        decisive_artifacts_referenced_in_text = (
            _coverage_metric(sum(1 for entry in decisive_entries if entry.referenced_in_text), len(decisive_entries))
            if decisive_entries
            else CoverageMetric(not_applicable=True)
        )
        decisive_artifact_roles_clear = (
            _coverage_metric(sum(1 for entry in decisive_entries if entry.role and entry.role != "other"), len(decisive_entries))
            if decisive_entries
            else CoverageMetric(not_applicable=True)
        )
        decisive_uncertainties_present = (
            _coverage_metric(uncertainty_count, len(decisive_entries))
            if decisive_entries
            else CoverageMetric()
        )
        decisive_artifacts_with_explicit_verdicts = (
            _coverage_metric(decisive_with_verdict, len(decisive_entries))
            if decisive_entries
            else CoverageMetric(not_applicable=True)
        )
        decisive_artifacts_benchmark_anchored = (
            _coverage_metric(decisive_with_anchor, len(decisive_entries))
            if decisive_entries
            else CoverageMetric(not_applicable=True)
        )
        comparison_with_prior_work_present = BinaryCheck(
            passed=bool(verdicts),
            not_applicable=not comparison_required,
        )
        decisive_comparison_failures_scoped = BinaryCheck(
            passed=decisive_failures_scoped,
            not_applicable=not decisive_entries,
        )

    figures = FiguresQualityInput(
        axes_labeled_with_units=_coverage_metric(sum(1 for entry in figure_registry if entry.has_units), total_figures),
        error_bars_present=_coverage_metric(sum(1 for entry in figure_registry if entry.has_uncertainty), total_figures),
        referenced_in_text=_coverage_metric(sum(1 for entry in figure_registry if entry.referenced_in_text), total_figures),
        captions_self_contained=_coverage_metric(
            sum(1 for entry in figure_registry if entry.caption_self_contained),
            total_figures,
        ),
        colorblind_safe=_coverage_metric(sum(1 for entry in figure_registry if entry.colorblind_safe), total_figures),
        decisive_artifacts_labeled_with_units=decisive_artifacts_labeled_with_units,
        decisive_artifacts_uncertainty_qualified=decisive_artifacts_uncertainty_qualified,
        decisive_artifacts_referenced_in_text=decisive_artifacts_referenced_in_text,
        decisive_artifact_roles_clear=decisive_artifact_roles_clear,
    )
    results = ResultsQualityInput(
        uncertainties_present=decisive_uncertainties_present,
        comparison_with_prior_work_present=comparison_with_prior_work_present,
        physical_interpretation_present=BinaryCheck(not_applicable=True),
        decisive_artifacts_with_explicit_verdicts=decisive_artifacts_with_explicit_verdicts,
        decisive_artifacts_benchmark_anchored=decisive_artifacts_benchmark_anchored,
        decisive_comparison_failures_scoped=decisive_comparison_failures_scoped,
    )
    return figures, results


def build_paper_quality_input(project_root: Path) -> PaperQualityInput:
    """Build a conservative :class:`PaperQualityInput` from project artifacts."""

    root = Path(project_root)
    manuscript_resolution = resolve_current_manuscript_resolution(root, allow_markdown=True)
    if manuscript_resolution.status in {"ambiguous", "invalid"}:
        raise GPDError(
            "paper-quality artifact resolution requires an unambiguous manuscript root; "
            f"found {manuscript_resolution.status}: {manuscript_resolution.detail}"
        )

    paper_dir = manuscript_resolution.manuscript_root or _best_effort_manuscript_root(root)
    manuscript_entrypoint = manuscript_resolution.manuscript_entrypoint
    artifact_manifest = None
    bibliography_audit = None
    paper_config: dict[str, object] = {}
    manuscript_files: list[Path] = []
    manuscript_content = ""
    if paper_dir is not None:
        artifact_manifest = _load_artifact_manifest(
            locate_publication_artifact(paper_dir, "ARTIFACT-MANIFEST.json")
        )
        bibliography_audit = _load_bibliography_audit(
            locate_publication_artifact(paper_dir, "BIBLIOGRAPHY-AUDIT.json")
        )
        paper_config = _load_manuscript_config(paper_dir)
        manuscript_files, manuscript_content = _collect_manuscript_content(
            paper_dir,
            entrypoint=manuscript_entrypoint,
        )
    trusted_artifact_manifest = (
        artifact_manifest
        if _manifest_metadata_matches_active_entrypoint(
            artifact_manifest,
            manuscript_root=paper_dir,
            manuscript_entrypoint=manuscript_entrypoint,
        )
        else None
    )
    title = (
        trusted_artifact_manifest.paper_title
        if trusted_artifact_manifest is not None
        else str(paper_config.get("title") or paper_config.get("paper_title") or "")
    )
    journal = _resolve_paper_journal(trusted_artifact_manifest, paper_config)

    figure_registry = _load_figure_registry(paper_dir) if paper_dir is not None else {}
    verdicts, verdicts_parse_ok = _collect_comparison_verdicts(
        root,
        manuscript_root=paper_dir,
    )
    contract_coverage = _collect_contract_coverage(root)
    figures, results = _build_figures_input(
        figure_registry,
        verdicts,
        root,
        comparison_required=contract_coverage.requires_decisive_comparison,
    )

    placeholder_count = len(_PLACEHOLDER_RE.findall(manuscript_content))
    missing_cites = len(_MISSING_CITE_RE.findall(manuscript_content))
    draft_findings = validate_tex_draft(manuscript_content)
    empty_citation_commands = sum(1 for finding in draft_findings if finding.check == "empty_citation_command")
    empty_reference_commands = sum(1 for finding in draft_findings if finding.check == "empty_reference_command")
    cite_keys = list(
        dict.fromkeys(
            part.strip()
            for match in _CITE_RE.findall(manuscript_content)
            for part in match.split(",")
            if part.strip()
        )
    )
    required_sections = 3
    present_sections = 0
    if _ABSTRACT_RE.search(manuscript_content):
        present_sections += 1
    if _INTRO_RE.search(manuscript_content):
        present_sections += 1
    if _CONCLUSION_RE.search(manuscript_content):
        present_sections += 1

    resolved_sources = bibliography_audit.resolved_sources if bibliography_audit is not None else 0
    total_sources = bibliography_audit.total_sources if bibliography_audit is not None else 0
    partial_sources = bibliography_audit.partial_sources if bibliography_audit is not None else 0
    unverified_sources = bibliography_audit.unverified_sources if bibliography_audit is not None else 0
    failed_sources = bibliography_audit.failed_sources if bibliography_audit is not None else 0
    available_citation_keys = _available_citation_keys(paper_dir, bibliography_audit) if paper_dir is not None else set()

    if cite_keys:
        resolved_citations = sum(1 for key in cite_keys if key in available_citation_keys)
        citation_key_coverage = _coverage_metric(resolved_citations, len(cite_keys))
    elif total_sources:
        citation_key_coverage = _coverage_metric(resolved_sources, total_sources)
    else:
        citation_key_coverage = CoverageMetric()
    citation_audit_applicable = bibliography_audit is not None or bool(cite_keys) or missing_cites > 0
    citation_audit_passed = (
        bibliography_audit is not None and failed_sources == 0 and partial_sources == 0 and unverified_sources == 0
    )

    manuscript_reference_status = _manuscript_reference_status(bibliography_audit, cite_keys=set(cite_keys))
    manuscript_reference_bridge_complete = bool(manuscript_reference_status) and all(
        status.reference_id and status.bibtex_key for status in manuscript_reference_status
    )

    journal_extra_checks: dict[str, bool] = {}
    raw_journal_extra_checks = paper_config.get("journal_extra_checks")
    if isinstance(raw_journal_extra_checks, dict):
        journal_extra_checks.update(raw_journal_extra_checks)
    journal_extra_checks["manuscript_reference_status_present"] = bool(manuscript_reference_status)
    journal_extra_checks["manuscript_reference_bridge_complete"] = manuscript_reference_bridge_complete
    journal_extra_checks["empty_citation_commands_absent"] = empty_citation_commands == 0
    journal_extra_checks["empty_reference_commands_absent"] = empty_reference_commands == 0
    if contract_coverage.contract_results_seen:
        journal_extra_checks["contract_results_parse_ok"] = contract_coverage.contract_results_parse_ok
        journal_extra_checks["contract_results_alignment_ok"] = contract_coverage.contract_results_alignment_ok
    journal_extra_checks["comparison_verdicts_valid"] = verdicts_parse_ok and contract_coverage.comparison_verdicts_valid

    citations = CitationsQualityInput(
        citation_keys_resolve=citation_key_coverage,
        missing_placeholders=BinaryCheck(passed=missing_cites == 0),
        key_prior_work_cited=BinaryCheck(passed=bool(verdicts) or bool(cite_keys)),
        hallucination_free=BinaryCheck(
            passed=citation_audit_passed,
            not_applicable=not citation_audit_applicable,
        ),
    )
    completeness = CompletenessQualityInput(
        abstract_written_last=BinaryCheck(not_applicable=True),
        required_sections_present=_coverage_metric(present_sections, required_sections)
        if manuscript_files
        else CoverageMetric(),
        placeholders_cleared=BinaryCheck(passed=placeholder_count == 0),
        supplemental_cross_referenced=BinaryCheck(passed=bool(_SUPPLEMENT_RE.search(manuscript_content))),
    )
    conventions = _build_conventions_input(root)
    verification = VerificationQualityInput(
        report_passed=BinaryCheck(passed=contract_coverage.latest_report_passed),
        contract_targets_verified=_coverage_metric(contract_coverage.satisfied_targets, contract_coverage.total_targets)
        if contract_coverage.total_targets
        else CoverageMetric(not_applicable=True),
        key_result_confidences=contract_coverage.confidences,
    )

    return PaperQualityInput(
        title=title,
        journal=journal,
        figures=figures,
        citations=citations,
        completeness=completeness,
        conventions=conventions,
        verification=verification,
        results=results,
        journal_extra_checks=journal_extra_checks,
    )

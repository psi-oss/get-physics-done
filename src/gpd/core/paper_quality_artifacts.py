"""Artifact-driven paper-quality input construction."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import ComparisonVerdict, ContractResults, ResearchContract
from gpd.core.frontmatter import (
    FrontmatterParseError,
    _find_matching_plan_contract,
    _parse_comparison_verdicts,
    _summary_contract_errors,
    extract_frontmatter,
)
from gpd.core.paper_quality import (
    BinaryCheck,
    CitationsQualityInput,
    CompletenessQualityInput,
    CoverageMetric,
    FiguresQualityInput,
    PaperQualityInput,
    ResultsQualityInput,
    VerificationConfidence,
    VerificationQualityInput,
)

__all__ = ["build_paper_quality_input"]


_PLACEHOLDER_RE = re.compile(r"TODO|FIXME|PENDING|TBD|\\text\{\[PENDING\]\}")
_MISSING_CITE_RE = re.compile(r"\\cite\{MISSING:")
_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}[\s\S]*?\\end\{abstract\}", re.IGNORECASE)
_INTRO_RE = re.compile(r"\\section\*?\{[^}]*introduction[^}]*\}", re.IGNORECASE)
_CONCLUSION_RE = re.compile(r"\\section\*?\{[^}]*conclusion[^}]*\}", re.IGNORECASE)
_SUPPLEMENT_RE = re.compile(r"appendix|supplement", re.IGNORECASE)
_CITE_RE = re.compile(r"\\cite\{([^}]*)\}")
_BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")


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


def _extract_meta(path: Path) -> dict[str, object]:
    content = _read_text(path)
    if content is None:
        return {}
    try:
        meta, _ = extract_frontmatter(content)
    except FrontmatterParseError:
        return {}
    return meta


def _plan_contract_for_artifact(path: Path, meta: dict[str, object]) -> ResearchContract | None:
    """Return the canonical plan contract for one phase artifact when available."""

    contract_data = meta.get("contract")
    if isinstance(contract_data, dict):
        try:
            return ResearchContract.model_validate(contract_data)
        except PydanticValidationError:
            return None
    return _find_matching_plan_contract(path.parent, meta)


def _collect_tex_content(paper_dir: Path) -> tuple[list[Path], str]:
    tex_files = sorted(paper_dir.glob("*.tex"))
    bodies = []
    for tex_file in tex_files:
        text = _read_text(tex_file)
        if text is not None:
            bodies.append(text)
    return tex_files, "\n".join(bodies)


def _resolve_manuscript_dir(project_root: Path) -> Path:
    for name in ("paper", "manuscript", "draft"):
        candidate = project_root / name
        if candidate.exists():
            return candidate
    return project_root / "paper"


def _available_citation_keys(manuscript_dir: Path, bibliography_audit: dict[str, object]) -> set[str]:
    keys: set[str] = set()

    entries = bibliography_audit.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            if isinstance(key, str) and key.strip():
                keys.add(key.strip())

    for bib_path in sorted(manuscript_dir.glob("*.bib")):
        content = _read_text(bib_path)
        if content is None:
            continue
        keys.update(match.group(1).strip() for match in _BIB_ENTRY_RE.finditer(content) if match.group(1).strip())

    return keys


def _load_figure_registry(project_root: Path) -> list[_FigureTrackerEntry]:
    tracker_path = project_root / ".gpd" / "paper" / "FIGURE_TRACKER.md"
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


def _parse_comparison_verdict_entries(value: object) -> list[ComparisonVerdict]:
    if not isinstance(value, list):
        return []

    verdicts: list[ComparisonVerdict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            verdicts.append(ComparisonVerdict.model_validate(item))
        except PydanticValidationError:
            continue
    return verdicts


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


def _collect_comparison_verdicts(project_root: Path) -> list[ComparisonVerdict]:
    verdicts_by_key: dict[tuple[str, str | None, str | None, str], ComparisonVerdict] = {}

    candidate_roots = [
        project_root / ".gpd" / "phases",
        project_root / ".gpd" / "comparisons",
        project_root / "paper",
    ]
    for root in candidate_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            meta = _extract_meta(path)
            for verdict in _parse_comparison_verdict_entries(meta.get("comparison_verdicts")):
                key = _comparison_verdict_key(verdict)
                existing = verdicts_by_key.get(key)
                verdicts_by_key[key] = verdict if existing is None else _merge_comparison_verdict(existing, verdict)
    return list(verdicts_by_key.values())


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

    phases_root = project_root / ".gpd" / "phases"
    if not phases_root.exists():
        return _ContractCoverage()

    for path in sorted(phases_root.rglob("*.md")):
        meta = _extract_meta(path)
        plan_contract = _plan_contract_for_artifact(path, meta)
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
        if isinstance(raw_results, dict) and plan_contract is not None:
            try:
                contract_results = ContractResults.model_validate(raw_results)
            except PydanticValidationError:
                contract_results = None
            if contract_results is not None:
                try:
                    comparison_verdicts = _parse_comparison_verdicts(meta)
                except (PydanticValidationError, TypeError, ValueError):
                    comparison_verdicts = []
                contract_alignment_errors = _summary_contract_errors(
                    plan_contract,
                    contract_results,
                    comparison_verdicts,
                )
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

        verified_at = str(meta.get("verified") or meta.get("completed") or "")
        status = str(meta.get("status") or "")
        is_verification_report = path.name.endswith("VERIFICATION.md")
        report_has_valid_contract_ledger = contract_results is not None and not contract_alignment_errors
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
        return FiguresQualityInput(), ResultsQualityInput(
            comparison_with_prior_work_present=BinaryCheck(
                passed=bool(verdicts),
                not_applicable=not comparison_required,
            )
        )

    total_figures = len(figure_registry)
    decisive_entries = [
        entry for entry in figure_registry if entry.decisive or entry.role in {"smoking_gun", "benchmark", "comparison"}
    ]

    decisive_with_verdict = 0
    decisive_with_anchor = 0
    decisive_failures_scoped = True
    uncertainty_count = 0

    for entry in decisive_entries:
        if entry.has_uncertainty:
            uncertainty_count += 1
        entry_verdicts = _find_verdict_for_entry(entry, verdicts, project_root)
        if entry_verdicts:
            decisive_with_verdict += 1
        if any(verdict.reference_id for verdict in entry_verdicts):
            decisive_with_anchor += 1
        for verdict in entry_verdicts:
            if verdict.verdict in {"fail", "tension"} and not (verdict.recommended_action or verdict.notes):
                decisive_failures_scoped = False

    figures = FiguresQualityInput(
        axes_labeled_with_units=_coverage_metric(sum(1 for entry in figure_registry if entry.has_units), total_figures),
        error_bars_present=_coverage_metric(sum(1 for entry in figure_registry if entry.has_uncertainty), total_figures),
        referenced_in_text=_coverage_metric(sum(1 for entry in figure_registry if entry.referenced_in_text), total_figures),
        captions_self_contained=_coverage_metric(
            sum(1 for entry in figure_registry if entry.caption_self_contained),
            total_figures,
        ),
        colorblind_safe=_coverage_metric(sum(1 for entry in figure_registry if entry.colorblind_safe), total_figures),
        decisive_artifacts_labeled_with_units=_coverage_metric(
            sum(1 for entry in decisive_entries if entry.has_units),
            len(decisive_entries),
        )
        if decisive_entries
        else CoverageMetric(not_applicable=True),
        decisive_artifacts_uncertainty_qualified=_coverage_metric(
            uncertainty_count,
            len(decisive_entries),
        )
        if decisive_entries
        else CoverageMetric(not_applicable=True),
        decisive_artifacts_referenced_in_text=_coverage_metric(
            sum(1 for entry in decisive_entries if entry.referenced_in_text),
            len(decisive_entries),
        )
        if decisive_entries
        else CoverageMetric(not_applicable=True),
        decisive_artifact_roles_clear=_coverage_metric(
            sum(1 for entry in decisive_entries if entry.role and entry.role != "other"),
            len(decisive_entries),
        )
        if decisive_entries
        else CoverageMetric(not_applicable=True),
    )
    results = ResultsQualityInput(
        uncertainties_present=_coverage_metric(uncertainty_count, len(decisive_entries))
        if decisive_entries
        else CoverageMetric(),
        comparison_with_prior_work_present=BinaryCheck(
            passed=bool(verdicts),
            not_applicable=not comparison_required,
        ),
        physical_interpretation_present=BinaryCheck(),
        decisive_artifacts_with_explicit_verdicts=_coverage_metric(
            decisive_with_verdict,
            len(decisive_entries),
        )
        if decisive_entries
        else CoverageMetric(not_applicable=True),
        decisive_artifacts_benchmark_anchored=_coverage_metric(
            decisive_with_anchor,
            len(decisive_entries),
        )
        if decisive_entries
        else CoverageMetric(not_applicable=True),
        decisive_comparison_failures_scoped=BinaryCheck(
            passed=decisive_failures_scoped,
            not_applicable=not decisive_entries,
        ),
    )
    return figures, results


def build_paper_quality_input(project_root: Path) -> PaperQualityInput:
    """Build a conservative :class:`PaperQualityInput` from project artifacts."""

    root = Path(project_root)
    paper_dir = _resolve_manuscript_dir(root)
    artifact_manifest = _load_json(paper_dir / "ARTIFACT-MANIFEST.json")
    paper_config = _load_json(paper_dir / "PAPER-CONFIG.json")
    bibliography_audit = _load_json(paper_dir / "BIBLIOGRAPHY-AUDIT.json")

    tex_files, tex_content = _collect_tex_content(paper_dir)
    title = str(artifact_manifest.get("paper_title") or paper_config.get("title") or paper_config.get("paper_title") or "")
    journal = str(artifact_manifest.get("journal") or paper_config.get("journal") or "generic")

    figure_registry = _load_figure_registry(root)
    verdicts = _collect_comparison_verdicts(root)
    contract_coverage = _collect_contract_coverage(root)
    figures, results = _build_figures_input(
        figure_registry,
        verdicts,
        root,
        comparison_required=contract_coverage.requires_decisive_comparison,
    )

    placeholder_count = len(_PLACEHOLDER_RE.findall(tex_content))
    missing_cites = len(_MISSING_CITE_RE.findall(tex_content))
    cite_keys = list(dict.fromkeys(part.strip() for match in _CITE_RE.findall(tex_content) for part in match.split(",") if part.strip()))
    required_sections = 3
    present_sections = 0
    if _ABSTRACT_RE.search(tex_content):
        present_sections += 1
    if _INTRO_RE.search(tex_content):
        present_sections += 1
    if _CONCLUSION_RE.search(tex_content):
        present_sections += 1

    resolved_sources = int(bibliography_audit.get("resolved_sources") or 0)
    total_sources = int(bibliography_audit.get("total_sources") or 0)
    partial_sources = int(bibliography_audit.get("partial_sources") or 0)
    unverified_sources = int(bibliography_audit.get("unverified_sources") or 0)
    failed_sources = int(bibliography_audit.get("failed_sources") or 0)
    available_citation_keys = _available_citation_keys(paper_dir, bibliography_audit)

    if cite_keys:
        resolved_citations = sum(1 for key in cite_keys if key in available_citation_keys)
        citation_key_coverage = _coverage_metric(resolved_citations, len(cite_keys))
    elif total_sources:
        citation_key_coverage = _coverage_metric(resolved_sources, total_sources)
    else:
        citation_key_coverage = CoverageMetric()

    citations = CitationsQualityInput(
        citation_keys_resolve=citation_key_coverage,
        missing_placeholders=BinaryCheck(passed=missing_cites == 0),
        key_prior_work_cited=BinaryCheck(passed=bool(verdicts) or bool(cite_keys)),
        hallucination_free=BinaryCheck(
            passed=failed_sources == 0 and partial_sources == 0 and unverified_sources == 0,
            not_applicable=not bibliography_audit,
        ),
    )
    completeness = CompletenessQualityInput(
        abstract_written_last=BinaryCheck(),
        required_sections_present=_coverage_metric(present_sections, required_sections) if tex_files else CoverageMetric(),
        placeholders_cleared=BinaryCheck(passed=placeholder_count == 0),
        supplemental_cross_referenced=BinaryCheck(passed=bool(_SUPPLEMENT_RE.search(tex_content))),
    )
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
        verification=verification,
        results=results,
    )

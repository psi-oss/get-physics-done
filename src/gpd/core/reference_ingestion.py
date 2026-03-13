"""Structured ingestion of anchor artifacts from literature and research maps."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

__all__ = [
    "ArtifactReference",
    "ArtifactReferenceIntake",
    "ArtifactReferenceIngestion",
    "ingest_reference_artifacts",
]

_ALLOWED_ACTIONS = {"read", "use", "compare", "cite", "avoid"}
_ROLE_MAP = {
    "benchmark": "benchmark",
    "baseline": "benchmark",
    "method": "method",
    "definition": "definition",
    "background": "background",
    "prior artifact": "must_consider",
    "prior_artifact": "must_consider",
    "prior-artifact": "must_consider",
    "artifact": "must_consider",
    "user anchor": "must_consider",
    "must consider": "must_consider",
    "must_consider": "must_consider",
}
_PATH_HINT_RE = re.compile(r"(?:^|[`\s])(?:\.gpd/|\.?/)?[\w./-]+\.(?:md|txt|pdf|png|jpg|jpeg|csv|json|tex|ipynb|py)(?:$|[`)\s])")


@dataclass
class ArtifactReference:
    """Reference-like anchor derived from durable markdown artifacts."""

    id: str
    locator: str
    role: str = "other"
    why_it_matters: str = ""
    applies_to: list[str] = field(default_factory=list)
    must_surface: bool = True
    required_actions: list[str] = field(default_factory=list)
    source_artifacts: list[str] = field(default_factory=list)
    source_kind: str = "artifact"

    def to_context_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "locator": self.locator,
            "role": self.role,
            "why_it_matters": self.why_it_matters,
            "applies_to": list(self.applies_to),
            "must_surface": self.must_surface,
            "required_actions": list(self.required_actions),
            "source_artifacts": list(self.source_artifacts),
            "source_kind": self.source_kind,
        }


@dataclass
class ArtifactReferenceIntake:
    """Carry-forward inputs inferred from durable anchor artifacts."""

    must_read_refs: list[str] = field(default_factory=list)
    must_include_prior_outputs: list[str] = field(default_factory=list)
    user_asserted_anchors: list[str] = field(default_factory=list)
    known_good_baselines: list[str] = field(default_factory=list)
    context_gaps: list[str] = field(default_factory=list)
    crucial_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "must_read_refs": list(self.must_read_refs),
            "must_include_prior_outputs": list(self.must_include_prior_outputs),
            "user_asserted_anchors": list(self.user_asserted_anchors),
            "known_good_baselines": list(self.known_good_baselines),
            "context_gaps": list(self.context_gaps),
            "crucial_inputs": list(self.crucial_inputs),
        }


@dataclass
class ArtifactReferenceIngestion:
    """Structured anchor view derived from literature and research-map artifacts."""

    references: list[ArtifactReference] = field(default_factory=list)
    intake: ArtifactReferenceIntake = field(default_factory=ArtifactReferenceIntake)


def _append_unique(items: list[str], value: str | None) -> None:
    cleaned = _clean_text(value)
    if cleaned and cleaned not in items:
        items.append(cleaned)


def _clean_text(value: object) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == "`":
        text = text[1:-1].strip()
    return text.strip()


def _normalize_role(value: str | None) -> str:
    raw = _clean_text(value).lower()
    if not raw:
        return "other"
    return _ROLE_MAP.get(raw, _ROLE_MAP.get(raw.replace("/", " ").replace("-", " "), "other"))


def _normalize_actions(value: object) -> list[str]:
    if isinstance(value, list):
        tokens = [_clean_text(item).lower() for item in value]
    else:
        tokens = re.split(r"[,/|]", _clean_text(value).lower())
    result: list[str] = []
    for token in tokens:
        normalized = token.replace(" ", "_").replace("-", "_").strip("_")
        normalized = normalized.replace("must_", "")
        if normalized in _ALLOWED_ACTIONS and normalized not in result:
            result.append(normalized)
    return result


def _normalize_multi_value(value: object) -> list[str]:
    if isinstance(value, list):
        tokens = [_clean_text(item) for item in value]
    else:
        tokens = re.split(r"[,/|]", _clean_text(value))
    result: list[str] = []
    for token in tokens:
        cleaned = token.strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _looks_like_path(value: str | None) -> bool:
    text = _clean_text(value)
    return bool(text and _PATH_HINT_RE.search(text))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _reference_id(label: str, locator: str, prefix: str) -> str:
    clean_label = _clean_text(label)
    if clean_label and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", clean_label):
        return clean_label
    seed = clean_label or locator or prefix
    slug = _slug(seed)[:48]
    return f"{prefix}-{slug or 'anchor'}"


def _extract_section(content: str, heading: str) -> str | None:
    pattern = re.compile(rf"^##+\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return None
    remainder = content[match.end() :]
    next_heading = re.search(r"^##+\s+", remainder, re.MULTILINE)
    return remainder[: next_heading.start()].strip() if next_heading else remainder.strip()


def _parse_markdown_table(section: str) -> list[dict[str, str]]:
    lines = [line.rstrip() for line in section.splitlines()]
    start = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("|"):
            start = idx
            break
    if start is None or start + 1 >= len(lines):
        return []
    header_line = lines[start].strip()
    separator_line = lines[start + 1].strip()
    if not header_line.startswith("|") or not separator_line.startswith("|"):
        return []
    headers = [_clean_text(cell) for cell in header_line.strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[start + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [_clean_text(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(dict(zip(headers, cells, strict=False)))
    return rows


def _parse_bullet_blocks(section: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in section.splitlines():
        line = raw_line.rstrip()
        bullet = re.match(r"^(\s*)-\s+(.*)$", line)
        if not bullet:
            continue
        indent = len(bullet.group(1))
        text = _clean_text(bullet.group(2))
        if indent == 0:
            if current is not None:
                blocks.append(current)
            current = {"title": text, "details": []}
        elif current is not None:
            cast_details = current.setdefault("details", [])
            if isinstance(cast_details, list):
                cast_details.append(text)
    if current is not None:
        blocks.append(current)
    return blocks


def _parse_yaml_review_summary(content: str) -> dict[str, object] | None:
    for match in re.finditer(r"```yaml\s*\n(?P<body>.*?)```", content, re.DOTALL):
        body = match.group("body").strip()
        if "review_summary:" not in body:
            continue
        try:
            documents = list(yaml.safe_load_all(body))
        except yaml.YAMLError:
            continue
        for parsed in documents:
            if isinstance(parsed, dict) and isinstance(parsed.get("review_summary"), dict):
                return parsed["review_summary"]
    return None


def _merge_reference(records: dict[str, ArtifactReference], reference: ArtifactReference) -> None:
    by_id = records.get(reference.id)
    if by_id is not None:
        target = by_id
    else:
        target = None
        locator_key = reference.locator.casefold()
        for candidate in records.values():
            if candidate.locator.casefold() == locator_key:
                target = candidate
                break
    if target is None:
        records[reference.id] = reference
        return

    if reference.role != "other" and target.role == "other":
        target.role = reference.role
    if reference.why_it_matters:
        if target.why_it_matters and reference.why_it_matters not in target.why_it_matters:
            target.why_it_matters = f"{target.why_it_matters}; {reference.why_it_matters}"
        elif not target.why_it_matters:
            target.why_it_matters = reference.why_it_matters
    for value in reference.applies_to:
        _append_unique(target.applies_to, value)
    for value in reference.required_actions:
        _append_unique(target.required_actions, value)
    for value in reference.source_artifacts:
        _append_unique(target.source_artifacts, value)
    target.must_surface = target.must_surface or reference.must_surface


def _reference_from_active_anchor(
    *,
    label: str,
    locator: str | None,
    role: str | None,
    why_it_matters: str | None,
    actions: object,
    downstream: object,
    source_path: str,
    prefix: str,
) -> ArtifactReference:
    locator_value = _clean_text(locator) or _clean_text(label)
    return ArtifactReference(
        id=_reference_id(label, locator_value, prefix),
        locator=locator_value,
        role=_normalize_role(role),
        why_it_matters=_clean_text(why_it_matters),
        applies_to=_normalize_multi_value(downstream),
        required_actions=_normalize_actions(actions),
        source_artifacts=[source_path],
        source_kind="artifact",
    )


def _ingest_literature_review(content: str, source_path: str, result: ArtifactReferenceIngestion) -> None:
    summary = _parse_yaml_review_summary(content)
    if isinstance(summary, dict):
        if summary.get("active_anchors"):
            merged: dict[str, ArtifactReference] = {ref.id: ref for ref in result.references}
            for entry in summary.get("active_anchors", []):
                if not isinstance(entry, dict):
                    continue
                reference = _reference_from_active_anchor(
                    label=str(entry.get("anchor") or entry.get("locator") or "literature-anchor"),
                    locator=str(entry.get("locator") or entry.get("anchor") or ""),
                    role=str(entry.get("type") or entry.get("role") or "other"),
                    why_it_matters=str(entry.get("why_it_matters") or ""),
                    actions=entry.get("required_action") or entry.get("required_actions"),
                    downstream=entry.get("downstream_use") or entry.get("carry_forward_to"),
                    source_path=source_path,
                    prefix="lit-anchor",
                )
                _merge_reference(merged, reference)
            result.references = list(merged.values())
        for benchmark in summary.get("benchmark_values", []):
            if not isinstance(benchmark, dict):
                continue
            quantity = _clean_text(benchmark.get("quantity"))
            value = _clean_text(benchmark.get("value"))
            source = _clean_text(benchmark.get("source") or benchmark.get("source_ref"))
            baseline = " — ".join(part for part in [quantity, value, f"source: {source}" if source else ""] if part)
            _append_unique(result.intake.known_good_baselines, baseline)

    section = _extract_section(content, "Active Anchor Registry")
    if section:
        merged = {ref.id: ref for ref in result.references}
        for row in _parse_markdown_table(section):
            reference = _reference_from_active_anchor(
                label=row.get("Anchor", "") or row.get("Reference", ""),
                locator=row.get("Source / Locator") or row.get("Anchor", ""),
                role=row.get("Type"),
                why_it_matters=row.get("Why It Matters") or row.get("What It Constrains"),
                actions=row.get("Required Action"),
                downstream=row.get("Downstream Use") or row.get("Carry Forward To"),
                source_path=source_path,
                prefix="lit-anchor",
            )
            _merge_reference(merged, reference)
        result.references = list(merged.values())

    open_questions = _extract_section(content, "Open Questions")
    if open_questions:
        for block in _parse_bullet_blocks(open_questions):
            _append_unique(result.intake.context_gaps, str(block.get("title") or ""))


def _ingest_reference_map(content: str, source_path: str, result: ArtifactReferenceIngestion) -> None:
    section = _extract_section(content, "Active Anchor Registry")
    if section:
        merged = {ref.id: ref for ref in result.references}
        for row in _parse_markdown_table(section):
            reference = _reference_from_active_anchor(
                label=row.get("Anchor", "") or row.get("Source / Locator", ""),
                locator=row.get("Source / Locator") or row.get("Anchor", ""),
                role=row.get("Type"),
                why_it_matters=row.get("Why It Matters") or row.get("What It Constrains"),
                actions=row.get("Required Action"),
                downstream=row.get("Downstream Use") or row.get("Carry Forward To"),
                source_path=source_path,
                prefix="map-anchor",
            )
            _merge_reference(merged, reference)
        result.references = list(merged.values())

    benchmark_section = _extract_section(content, "Benchmarks and Comparison Targets")
    if benchmark_section:
        for block in _parse_bullet_blocks(benchmark_section):
            title = _clean_text(block.get("title"))
            source = ""
            compared_in = ""
            status = ""
            details = block.get("details")
            if isinstance(details, list):
                for detail in details:
                    detail_text = _clean_text(detail)
                    lower = detail_text.lower()
                    if lower.startswith("source:"):
                        source = _clean_text(detail_text.split(":", 1)[1])
                    elif lower.startswith("compared in:"):
                        compared_in = _clean_text(detail_text.split(":", 1)[1])
                    elif lower.startswith("status:"):
                        status = _clean_text(detail_text.split(":", 1)[1])
            baseline = " — ".join(part for part in [title, f"source: {source}" if source else "", status] if part)
            _append_unique(result.intake.known_good_baselines, baseline)
            if compared_in:
                _append_unique(result.intake.must_include_prior_outputs, compared_in)
                _append_unique(result.intake.crucial_inputs, compared_in)

    prior_section = _extract_section(content, "Prior Artifacts and Baselines")
    if prior_section:
        for block in _parse_bullet_blocks(prior_section):
            title = _clean_text(block.get("title"))
            match = re.match(r"^`?(?P<path>[^:`]+)`?\s*:\s*(?P<desc>.+)$", title)
            if match:
                path = _clean_text(match.group("path"))
                desc = _clean_text(match.group("desc"))
                _append_unique(result.intake.must_include_prior_outputs, path)
                _append_unique(result.intake.known_good_baselines, f"{path} — {desc}")
                _append_unique(result.intake.crucial_inputs, path)
            elif title:
                _append_unique(result.intake.known_good_baselines, title)

    open_questions = _extract_section(content, "Open Reference Questions")
    if open_questions:
        for block in _parse_bullet_blocks(open_questions):
            _append_unique(result.intake.context_gaps, str(block.get("title") or ""))


def _populate_intake_from_references(result: ArtifactReferenceIngestion) -> None:
    for reference in result.references:
        if "read" in reference.required_actions or reference.role in {"benchmark", "definition", "method"}:
            _append_unique(result.intake.must_read_refs, reference.locator)
        if reference.role == "benchmark":
            baseline = reference.locator
            if reference.why_it_matters:
                baseline = f"{baseline} — {reference.why_it_matters}"
            _append_unique(result.intake.known_good_baselines, baseline)
        if _looks_like_path(reference.locator) or reference.role == "must_consider":
            _append_unique(result.intake.must_include_prior_outputs, reference.locator)
            _append_unique(result.intake.crucial_inputs, reference.locator)


def ingest_reference_artifacts(
    cwd: Path,
    *,
    literature_review_files: list[str],
    research_map_reference_files: list[str],
) -> ArtifactReferenceIngestion:
    """Parse durable literature/research-map artifacts into anchor context."""

    result = ArtifactReferenceIngestion()

    for rel_path in literature_review_files:
        path = cwd / rel_path
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        _ingest_literature_review(content, rel_path, result)

    for rel_path in research_map_reference_files:
        path = cwd / rel_path
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        upper_name = path.name.upper()
        if upper_name == "REFERENCES.MD":
            _ingest_reference_map(content, rel_path, result)
        elif upper_name == "VALIDATION.MD":
            comparison_section = _extract_section(content, "Comparison with Literature")
            if comparison_section:
                for block in _parse_bullet_blocks(comparison_section):
                    _append_unique(result.intake.known_good_baselines, str(block.get("title") or ""))
                    details = block.get("details")
                    if isinstance(details, list):
                        for detail in details:
                            detail_text = _clean_text(detail)
                            lower = detail_text.lower()
                            if lower.startswith("comparison in:") or lower.startswith("file:"):
                                _append_unique(result.intake.must_include_prior_outputs, detail_text.split(":", 1)[1])
                                _append_unique(result.intake.crucial_inputs, detail_text.split(":", 1)[1])

    _populate_intake_from_references(result)
    result.references.sort(key=lambda item: (item.must_surface is False, item.role, item.id))
    return result

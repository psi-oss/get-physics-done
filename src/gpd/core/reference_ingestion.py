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
_ACTION_ALIASES = {
    "carry_forward": "use",
    "consult": "read",
    "cross_reference": "cite",
    "inspect": "read",
    "keep_visible": "use",
    "preserve": "use",
    "reference": "cite",
    "reuse": "use",
    "review": "read",
}
_ROLE_MAP = {
    "benchmark": "benchmark",
    "benchmark target": "benchmark",
    "baseline": "benchmark",
    "comparison target": "benchmark",
    "method": "method",
    "methods": "method",
    "definition": "definition",
    "background": "background",
    "prior artifact": "must_consider",
    "prior output": "must_consider",
    "prior result": "must_consider",
    "prior_artifact": "must_consider",
    "prior-artifact": "must_consider",
    "artifact": "must_consider",
    "required anchor": "must_consider",
    "user anchor": "must_consider",
    "must consider": "must_consider",
    "must_consider": "must_consider",
}
_KIND_MAP = {
    "paper": "paper",
    "dataset": "dataset",
    "prior artifact": "prior_artifact",
    "prior output": "prior_artifact",
    "prior_artifact": "prior_artifact",
    "prior-artifact": "prior_artifact",
    "artifact": "prior_artifact",
    "spec": "spec",
    "user anchor": "user_anchor",
    "user_anchor": "user_anchor",
}
_PATH_HINT_RE = re.compile(
    r"(?P<path>(?:\.gpd/|\.?/)?[\w./-]+\.(?:md|txt|pdf|png|jpg|jpeg|csv|json|ya?ml|tex|ipynb|py|bib))",
)
_ACTIVE_REFERENCE_REGISTRY_HEADINGS = (
    "Active Anchor Registry",
    "Active Reference Registry",
    "Anchor Registry",
    "Reference Registry",
    "Active Anchors",
    "Active References",
)
_OPEN_QUESTION_HEADINGS = (
    "Open Questions",
    "Open Reference Questions",
    "Context Gaps",
    "Outstanding Questions",
)
_BENCHMARK_HEADINGS = (
    "Benchmarks and Comparison Targets",
    "Comparison Targets",
    "Known Good Baselines",
    "Baseline Targets",
    "Benchmarks",
)
_PRIOR_OUTPUT_HEADINGS = (
    "Prior Artifacts and Baselines",
    "Prior Outputs and Baselines",
    "Prior Outputs",
    "Prior Artifacts",
    "Carry-Forward Outputs",
)
_VALIDATION_COMPARISON_HEADINGS = (
    "Comparison with Literature",
    "Comparison to Literature",
    "Literature Comparison",
    "External Comparison",
)
_DIRECT_INTAKE_SECTION_ALIASES = {
    "must_read_refs": (
        "Must-Read References",
        "Must Read References",
        "References To Read",
        "Required References",
    ),
    "must_include_prior_outputs": _PRIOR_OUTPUT_HEADINGS,
    "user_asserted_anchors": (
        "User-Asserted Anchors",
        "Required Anchors",
        "Anchors To Preserve",
    ),
    "known_good_baselines": (
        "Known-Good Baselines",
        "Known Good Baselines",
        "Baseline Targets",
    ),
    "context_gaps": _OPEN_QUESTION_HEADINGS,
    "crucial_inputs": (
        "Crucial Inputs",
        "Critical Inputs",
        "Required Inputs",
    ),
}


@dataclass
class ArtifactReference:
    """Reference-like anchor derived from durable markdown artifacts."""

    id: str
    locator: str
    aliases: list[str] = field(default_factory=list)
    kind: str = "other"
    role: str = "other"
    why_it_matters: str = ""
    applies_to: list[str] = field(default_factory=list)
    carry_forward_to: list[str] = field(default_factory=list)
    must_surface: bool = True
    required_actions: list[str] = field(default_factory=list)
    source_artifacts: list[str] = field(default_factory=list)
    source_kind: str = "artifact"

    def to_context_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "locator": self.locator,
            "aliases": list(self.aliases),
            "kind": self.kind,
            "role": self.role,
            "why_it_matters": self.why_it_matters,
            "applies_to": list(self.applies_to),
            "carry_forward_to": list(self.carry_forward_to),
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


def _normalize_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_text(value).lower()).strip()


def _normalize_role(value: str | None) -> str:
    raw = _normalize_token(value)
    if not raw:
        return "other"
    return _ROLE_MAP.get(raw, "other")


def _normalize_kind(value: str | None) -> str:
    raw = _normalize_token(value)
    if not raw:
        return "other"
    return _KIND_MAP.get(raw, "other")


def _normalize_actions(value: object) -> list[str]:
    if isinstance(value, list):
        tokens = [_clean_text(item).lower() for item in value]
    else:
        tokens = re.split(r"[,/|]", _clean_text(value).lower())
    result: list[str] = []
    for token in tokens:
        normalized = token.replace(" ", "_").replace("-", "_").strip("_")
        normalized = normalized.replace("must_", "")
        normalized = _ACTION_ALIASES.get(normalized, normalized)
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


def _first_non_empty(mapping: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = _clean_text(mapping.get(key))
        if value:
            return value
    return ""


def _looks_like_path(value: str | None) -> bool:
    return bool(_extract_paths(value))


def _extract_paths(value: object) -> list[str]:
    text = _clean_text(value)
    paths: list[str] = []
    for match in _PATH_HINT_RE.finditer(text):
        _append_unique(paths, match.group("path"))
    return paths


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _reference_id(label: str, locator: str, prefix: str) -> str:
    clean_label = _clean_text(label)
    if clean_label and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", clean_label):
        return clean_label
    seed = clean_label or locator or prefix
    slug = _slug(seed)[:48]
    return f"{prefix}-{slug or 'anchor'}"


def _reference_identity_tokens(*values: object) -> list[str]:
    tokens: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        normalized = _normalize_token(cleaned)
        if normalized and normalized not in tokens:
            tokens.append(normalized)
    return tokens


def _extract_section(content: str, heading: str) -> str | None:
    target = _normalize_token(heading)
    for match in re.finditer(r"^(?P<marks>#{1,6})\s+(?P<title>[^\n]+?)\s*$", content, re.MULTILINE):
        if _normalize_token(match.group("title")) != target:
            continue
        remainder = content[match.end() :]
        next_heading = re.search(r"^#{1,6}\s+", remainder, re.MULTILINE)
        return remainder[: next_heading.start()].strip() if next_heading else remainder.strip()
    return None


def _extract_first_section(content: str, headings: tuple[str, ...]) -> str | None:
    for heading in headings:
        section = _extract_section(content, heading)
        if section:
            return section
    return None


def _canonical_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {_normalize_token(key): value for key, value in mapping.items()}


def _mapping_value(mapping: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = _clean_text(mapping.get(_normalize_token(key)))
        if value:
            return value
    return ""


def _detail_mapping(details: object) -> dict[str, str]:
    mapping: dict[str, str] = {}
    freeform: list[str] = []
    if not isinstance(details, list):
        return mapping
    for detail in details:
        detail_text = _clean_text(detail)
        if not detail_text:
            continue
        if ":" not in detail_text:
            freeform.append(detail_text)
            continue
        key, value = detail_text.split(":", 1)
        canonical_key = _normalize_token(key)
        cleaned_value = _clean_text(value)
        if not canonical_key or not cleaned_value:
            continue
        if canonical_key in mapping:
            if cleaned_value not in mapping[canonical_key]:
                mapping[canonical_key] = f"{mapping[canonical_key]}; {cleaned_value}"
        else:
            mapping[canonical_key] = cleaned_value
    if freeform:
        mapping["freeform"] = "; ".join(freeform)
    return mapping


def _section_bullet_items(section: str) -> list[dict[str, object]]:
    return [block for block in _parse_bullet_blocks(section) if _clean_text(block.get("title"))]


def _append_paths(target: list[str], value: object) -> None:
    for path in _extract_paths(value):
        _append_unique(target, path)


def _parse_reference_block(
    block: dict[str, object],
    *,
    source_path: str,
    prefix: str,
) -> ArtifactReference:
    detail_map = _detail_mapping(block.get("details"))
    title = _clean_text(block.get("title"))
    label = _mapping_value(detail_map, "anchor", "reference", "label", "title") or title
    locator = _mapping_value(
        detail_map,
        "source / locator",
        "locator",
        "source",
        "path",
        "reference path",
    )
    if not locator and ":" in title:
        head, tail = title.split(":", 1)
        if _normalize_token(head) in {"anchor", "reference", "source", "locator"}:
            label = _clean_text(tail)
        elif _looks_like_path(head):
            locator = _clean_text(head)
            label = _clean_text(tail) or locator
    why = _mapping_value(
        detail_map,
        "why it matters",
        "what it constrains",
        "description",
        "notes",
        "reason",
    )
    if not why:
        why = _mapping_value(detail_map, "freeform")
    return _reference_from_active_anchor(
        anchor_id=_mapping_value(detail_map, "anchor id", "reference id", "id"),
        label=label,
        locator=locator or label,
        applies_to=_mapping_value(detail_map, "applies to", "subject ids", "subject ids / applies to"),
        kind=_mapping_value(detail_map, "kind", "artifact kind"),
        role=_mapping_value(detail_map, "type", "role", "kind"),
        why_it_matters=why,
        actions=_mapping_value(detail_map, "required action", "required actions", "action"),
        downstream=_mapping_value(detail_map, "downstream use", "carry forward to", "applies to"),
        source_path=source_path,
        prefix=prefix,
    )


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
    yaml_bodies: list[str] = []
    for match in re.finditer(r"```yaml\s*\n(?P<body>.*?)```", content, re.DOTALL):
        yaml_bodies.append(match.group("body").strip())
    stripped = content.lstrip()
    if stripped.startswith("---"):
        _, _, remainder = stripped.partition("---")
        body, separator, _ = remainder.partition("\n---")
        if separator:
            yaml_bodies.append(body.strip())
    for body in yaml_bodies:
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
            incoming_tokens = set(
                _reference_identity_tokens(
                    reference.id,
                    reference.locator,
                    *reference.aliases,
                )
            )
            for candidate in records.values():
                candidate_tokens = set(
                    _reference_identity_tokens(
                        candidate.id,
                        candidate.locator,
                        *candidate.aliases,
                    )
                )
                if incoming_tokens and candidate_tokens and incoming_tokens.intersection(candidate_tokens):
                    target = candidate
                    break
    if target is None:
        records[reference.id] = reference
        return

    if reference.kind != "other" and target.kind == "other":
        target.kind = reference.kind
    if reference.locator and not target.locator:
        target.locator = reference.locator
    if reference.role != "other" and target.role == "other":
        target.role = reference.role
    if reference.why_it_matters:
        if target.why_it_matters and reference.why_it_matters not in target.why_it_matters:
            target.why_it_matters = f"{target.why_it_matters}; {reference.why_it_matters}"
        elif not target.why_it_matters:
            target.why_it_matters = reference.why_it_matters
    for value in reference.applies_to:
        _append_unique(target.applies_to, value)
    for value in reference.carry_forward_to:
        _append_unique(target.carry_forward_to, value)
    for value in reference.required_actions:
        _append_unique(target.required_actions, value)
    for value in reference.source_artifacts:
        _append_unique(target.source_artifacts, value)
    for value in reference.aliases:
        _append_unique(target.aliases, value)
    target.must_surface = target.must_surface or reference.must_surface


def _reference_from_active_anchor(
    *,
    anchor_id: str | None,
    label: str,
    locator: str | None,
    applies_to: object | None = None,
    kind: str | None,
    role: str | None,
    why_it_matters: str | None,
    actions: object,
    downstream: object,
    source_path: str,
    prefix: str,
) -> ArtifactReference:
    locator_value = _clean_text(locator) or _clean_text(label)
    normalized_kind = _normalize_kind(kind)
    normalized_role = _normalize_role(role)
    normalized_actions = _normalize_actions(actions)
    if normalized_kind == "other" and _looks_like_path(locator_value):
        normalized_kind = "prior_artifact"
    if normalized_role == "other" and normalized_kind in {"prior_artifact", "user_anchor"}:
        normalized_role = "must_consider"
    alias_values: list[str] = []
    for alias in {_clean_text(label), _clean_text(locator), _clean_text(anchor_id)}:
        if alias and alias not in {locator_value, _clean_text(anchor_id)}:
            alias_values.append(alias)
    must_surface = normalized_role in {"benchmark", "definition", "method", "must_consider"} or bool(
        {"use", "compare", "avoid"} & set(normalized_actions)
    )
    return ArtifactReference(
        id=_clean_text(anchor_id) or _reference_id(label, locator_value, prefix),
        locator=locator_value,
        aliases=alias_values,
        kind=normalized_kind,
        role=normalized_role,
        why_it_matters=_clean_text(why_it_matters),
        applies_to=_normalize_multi_value(applies_to),
        carry_forward_to=_normalize_multi_value(downstream),
        must_surface=must_surface,
        required_actions=normalized_actions,
        source_artifacts=[source_path],
        source_kind="artifact",
    )


def _ingest_reference_registry_section(
    section: str,
    *,
    source_path: str,
    prefix: str,
    result: ArtifactReferenceIngestion,
) -> None:
    merged = {ref.id: ref for ref in result.references}
    for row in _parse_markdown_table(section):
        canonical_row = _canonical_mapping(row)
        reference = _reference_from_active_anchor(
            anchor_id=_mapping_value(canonical_row, "anchor id", "reference id", "id"),
            label=_mapping_value(canonical_row, "anchor", "reference", "label", "source / locator"),
            locator=_mapping_value(canonical_row, "source / locator", "locator", "source", "reference", "anchor"),
            applies_to=_mapping_value(canonical_row, "applies to", "subject ids"),
            kind=_mapping_value(canonical_row, "kind", "artifact kind"),
            role=_mapping_value(canonical_row, "type", "role", "kind"),
            why_it_matters=_mapping_value(canonical_row, "why it matters", "what it constrains", "description"),
            actions=_mapping_value(canonical_row, "required action", "required actions", "action"),
            downstream=_mapping_value(canonical_row, "downstream use", "carry forward to", "applies to"),
            source_path=source_path,
            prefix=prefix,
        )
        _merge_reference(merged, reference)
    for block in _section_bullet_items(section):
        _merge_reference(merged, _parse_reference_block(block, source_path=source_path, prefix=prefix))
    result.references = list(merged.values())


def _ingest_direct_intake_sections(content: str, result: ArtifactReferenceIngestion) -> None:
    for intake_key, headings in _DIRECT_INTAKE_SECTION_ALIASES.items():
        section = _extract_first_section(content, headings)
        if not section:
            continue
        items = _section_bullet_items(section)
        target = getattr(result.intake, intake_key)
        for block in items:
            title = _clean_text(block.get("title"))
            detail_map = _detail_mapping(block.get("details"))
            if intake_key in {"must_include_prior_outputs", "crucial_inputs"}:
                _append_paths(target, title)
                for detail_value in detail_map.values():
                    _append_paths(target, detail_value)
                if title and not _looks_like_path(title):
                    _append_unique(target, title)
                continue
            if intake_key == "known_good_baselines" and title:
                _append_unique(target, title)
                continue
            if title:
                _append_unique(target, title)


def _ingest_benchmark_section(section: str, result: ArtifactReferenceIngestion) -> None:
    for block in _parse_bullet_blocks(section):
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
                elif lower.startswith("compared in:") or lower.startswith("comparison in:") or lower.startswith("file:"):
                    compared_in = _clean_text(detail_text.split(":", 1)[1])
                elif lower.startswith("status:"):
                    status = _clean_text(detail_text.split(":", 1)[1])
        baseline = " — ".join(part for part in [title, f"source: {source}" if source else "", status] if part)
        _append_unique(result.intake.known_good_baselines, baseline)
        if compared_in:
            _append_paths(result.intake.must_include_prior_outputs, compared_in)
            _append_paths(result.intake.crucial_inputs, compared_in)


def _ingest_prior_outputs_section(section: str, result: ArtifactReferenceIngestion) -> None:
    for block in _parse_bullet_blocks(section):
        title = _clean_text(block.get("title"))
        match = re.match(r"^`?(?P<path>[^:`]+)`?\s*:\s*(?P<desc>.+)$", title)
        if match:
            path = _clean_text(match.group("path"))
            desc = _clean_text(match.group("desc"))
            _append_unique(result.intake.must_include_prior_outputs, path)
            _append_unique(result.intake.known_good_baselines, f"{path} — {desc}")
            _append_unique(result.intake.crucial_inputs, path)
            continue
        paths = _extract_paths(title)
        if paths:
            for path in paths:
                _append_unique(result.intake.must_include_prior_outputs, path)
                _append_unique(result.intake.crucial_inputs, path)
            _append_unique(result.intake.known_good_baselines, title)
            continue
        if title:
            _append_unique(result.intake.known_good_baselines, title)


def _ingest_gap_section(section: str, result: ArtifactReferenceIngestion) -> None:
    for block in _parse_bullet_blocks(section):
        _append_unique(result.intake.context_gaps, str(block.get("title") or ""))


def _ingest_validation_comparison_section(section: str, result: ArtifactReferenceIngestion) -> None:
    for block in _parse_bullet_blocks(section):
        _append_unique(result.intake.known_good_baselines, str(block.get("title") or ""))
        details = block.get("details")
        if isinstance(details, list):
            for detail in details:
                detail_text = _clean_text(detail)
                lower = detail_text.lower()
                if lower.startswith("comparison in:") or lower.startswith("compared in:") or lower.startswith("file:"):
                    path_text = detail_text.split(":", 1)[1]
                    _append_paths(result.intake.must_include_prior_outputs, path_text)
                    _append_paths(result.intake.crucial_inputs, path_text)


def _ingest_literature_review(content: str, source_path: str, result: ArtifactReferenceIngestion) -> None:
    summary = _parse_yaml_review_summary(content)
    if isinstance(summary, dict):
        active_anchors = summary.get("active_anchors")
        if active_anchors:
            merged: dict[str, ArtifactReference] = {ref.id: ref for ref in result.references}
            for entry in active_anchors:
                if not isinstance(entry, dict):
                    continue
                reference = _reference_from_active_anchor(
                    anchor_id=str(entry.get("anchor_id") or ""),
                    label=str(entry.get("anchor") or entry.get("label") or entry.get("locator") or "literature-anchor"),
                    locator=str(entry.get("locator") or entry.get("source") or entry.get("anchor") or ""),
                    applies_to=entry.get("applies_to") or entry.get("subject_ids"),
                    kind=str(entry.get("kind") or ""),
                    role=str(entry.get("type") or entry.get("role") or "other"),
                    why_it_matters=str(entry.get("why_it_matters") or ""),
                    actions=entry.get("required_action") or entry.get("required_actions"),
                    downstream=entry.get("downstream_use") or entry.get("carry_forward_to"),
                    source_path=source_path,
                    prefix="lit-anchor",
                )
                _merge_reference(merged, reference)
            result.references = list(merged.values())
        for benchmark in summary.get("benchmark_values") or []:
            if not isinstance(benchmark, dict):
                if isinstance(benchmark, str):
                    _append_unique(result.intake.known_good_baselines, benchmark)
                continue
            quantity = _clean_text(benchmark.get("quantity"))
            value = _clean_text(benchmark.get("value"))
            source = _clean_text(benchmark.get("source"))
            baseline = " — ".join(part for part in [quantity, value, f"source: {source}" if source else ""] if part)
            _append_unique(result.intake.known_good_baselines, baseline)
        for token in _normalize_multi_value(summary.get("must_read_refs")):
            _append_unique(result.intake.must_read_refs, token)
        for token in _normalize_multi_value(summary.get("context_gaps")):
            _append_unique(result.intake.context_gaps, token)

    section = _extract_first_section(content, _ACTIVE_REFERENCE_REGISTRY_HEADINGS)
    if section:
        _ingest_reference_registry_section(section, source_path=source_path, prefix="lit-anchor", result=result)

    open_questions = _extract_first_section(content, _OPEN_QUESTION_HEADINGS)
    if open_questions:
        _ingest_gap_section(open_questions, result)
    _ingest_direct_intake_sections(content, result)


def _ingest_reference_map(content: str, source_path: str, result: ArtifactReferenceIngestion) -> None:
    section = _extract_first_section(content, _ACTIVE_REFERENCE_REGISTRY_HEADINGS)
    if section:
        _ingest_reference_registry_section(section, source_path=source_path, prefix="map-anchor", result=result)

    benchmark_section = _extract_first_section(content, _BENCHMARK_HEADINGS)
    if benchmark_section:
        _ingest_benchmark_section(benchmark_section, result)

    prior_section = _extract_first_section(content, _PRIOR_OUTPUT_HEADINGS)
    if prior_section:
        _ingest_prior_outputs_section(prior_section, result)

    open_questions = _extract_first_section(content, _OPEN_QUESTION_HEADINGS)
    if open_questions:
        _ingest_gap_section(open_questions, result)

    comparison_section = _extract_first_section(content, _VALIDATION_COMPARISON_HEADINGS)
    if comparison_section:
        _ingest_validation_comparison_section(comparison_section, result)

    _ingest_direct_intake_sections(content, result)


def _populate_intake_from_references(result: ArtifactReferenceIngestion) -> None:
    for reference in result.references:
        if "read" in reference.required_actions or reference.role in {"benchmark", "definition", "method"}:
            _append_unique(result.intake.must_read_refs, reference.id)
        if reference.role == "benchmark":
            baseline = reference.locator
            if reference.why_it_matters:
                baseline = f"{baseline} — {reference.why_it_matters}"
            _append_unique(result.intake.known_good_baselines, baseline)
        if _looks_like_path(reference.locator):
            _append_unique(result.intake.must_include_prior_outputs, reference.locator)
            _append_unique(result.intake.crucial_inputs, reference.locator)
        elif reference.role == "must_consider":
            _append_unique(result.intake.user_asserted_anchors, reference.locator)


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
        _ingest_reference_map(content, rel_path, result)

    _populate_intake_from_references(result)
    result.references.sort(key=lambda item: (item.must_surface is False, item.role, item.id))
    return result

"""Cross-phase result query commands for GPD.

Searches across all phase summary artifacts (`SUMMARY.md` and `*-SUMMARY.md`)
to find results by provides, requires, affects, equation, text, and assumption
references.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import ProjectLayout
from gpd.core.errors import QueryError
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import compare_phase_numbers, phase_unpad
from gpd.core.utils import phase_sort_key as _phase_sort_key

logger = logging.getLogger(__name__)

__all__ = [
    "AssumptionAffected",
    "AssumptionsResult",
    "DepsConsumer",
    "DepsProvider",
    "DepsResult",
    "QueryMatch",
    "QueryResult",
    "SummaryEntry",
    "VALID_SCOPES",
    "collect_all_markdown",
    "collect_phase_markdown",
    "collect_summaries",
    "extract_context",
    "extract_requires_values",
    "parse_phase_range",
    "query",
    "query_assumptions",
    "query_deps",
    "resolve_field",
    "term_matches",
]

# ─── Models ──────────────────────────────────────────────────────────────────────


VALID_SCOPES = frozenset({"summary", "phase", "all"})


class SummaryEntry(BaseModel):
    """A parsed markdown file from a phase directory (SUMMARY or other .md file)."""

    model_config = ConfigDict(frozen=True)

    phase: str
    dir_name: str
    file: str
    plan: str | None = None
    frontmatter: dict = Field(default_factory=dict)
    body: str = ""


class QueryMatch(BaseModel):
    """A single match from a cross-phase query."""

    model_config = ConfigDict(frozen=True)

    phase: str
    plan: str | None = None
    field: str
    value: str | None = None
    context: str | None = None


class QueryResult(BaseModel):
    """Result of a cross-phase query."""

    model_config = ConfigDict(frozen=True)

    matches: list[QueryMatch] = Field(default_factory=list)
    total: int = 0


class DepsProvider(BaseModel):
    """A phase/plan that provides a given identifier."""

    model_config = ConfigDict(frozen=True)

    phase: str
    plan: str | None = None
    value: object = None


class DepsConsumer(BaseModel):
    """A phase/plan that requires a given identifier."""

    model_config = ConfigDict(frozen=True)

    phase: str
    plan: str | None = None
    value: str = ""


class DepsResult(BaseModel):
    """Dependency trace for an identifier across phases."""

    model_config = ConfigDict(frozen=True)

    provides_by: DepsProvider | None = None
    provider_conflicts: list[DepsProvider] = Field(default_factory=list)
    required_by: list[DepsConsumer] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    direct_deps: list[str] = Field(default_factory=list)
    transitive_deps: list[str] = Field(default_factory=list)


class AssumptionAffected(BaseModel):
    """A phase affected by a given assumption."""

    model_config = ConfigDict(frozen=True)

    phase: str
    plan: str | None = None
    found_in: list[str] = Field(default_factory=list)
    context: str | None = None


class AssumptionsResult(BaseModel):
    """Result of an assumption impact query."""

    model_config = ConfigDict(frozen=True)

    assumption: str
    affected_phases: list[AssumptionAffected] = Field(default_factory=list)
    total: int = 0


# ─── Internal Helpers ────────────────────────────────────────────────────────


def _is_valid_phase_str(s: str) -> bool:
    """Check whether a string is a valid dotted-numeric phase number."""
    return bool(re.match(r"^\d+(\.\d+)*$", s))


def resolve_field(fm: dict, field_name: str) -> list:
    """Resolve provides/requires/affects arrays from frontmatter.

    Checks both top-level and dependency-graph nested fields.
    """
    if not fm or not isinstance(fm, dict):
        return []
    dep_graph = fm.get("dependency-graph")
    if isinstance(dep_graph, dict) and field_name in dep_graph:
        value = dep_graph.get(field_name)
    else:
        value = fm.get(field_name)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (str, dict)):
        return [value]
    return [value]


def _append_search_values(values: list[str], value: object) -> None:
    if value is None:
        return
    if isinstance(value, str):
        values.append(value)
        return
    if isinstance(value, list):
        for item in value:
            _append_search_values(values, item)
        return
    if isinstance(value, dict):
        for item in value.values():
            _append_search_values(values, item)
        return
    values.append(str(value))


def _search_values_from_item(value: object, *preferred_keys: str) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict) and preferred_keys:
        matched_any = False
        for key in preferred_keys:
            if key in value:
                matched_any = True
                _append_search_values(values, value.get(key))
        if matched_any:
            return values
    _append_search_values(values, value)
    return values


def extract_requires_values(requires_arr: list) -> list[str]:
    """Extract the searchable values from a requires array.

    Handles string items, object items with phase/provides keys, and mixed.
    """
    values: list[str] = []
    for item in requires_arr:
        if isinstance(item, str):
            values.append(item)
        elif isinstance(item, dict):
            for key in ("provides", "phase"):
                _append_search_values(values, item.get(key))
    return values


def _strip_phase_locator_prefix(value: str) -> str | None:
    """Return the dependency identifier from ``PHASE-PLAN: identifier`` strings."""

    prefix, separator, suffix = value.partition(":")
    if not separator or not suffix.strip():
        return None
    phase_token, dash, plan_token = prefix.strip().partition("-")
    if not dash:
        return None
    if not _is_valid_phase_str(phase_token) or not _is_valid_phase_str(plan_token):
        return None
    identifier = suffix.strip()
    return identifier or None


def extract_requires_identifiers(requires_arr: list) -> list[str]:
    """Extract result identifiers from a requires array for dependency tracing."""

    values: list[str] = []
    for item in requires_arr:
        if isinstance(item, str):
            values.append(item)
            stripped = _strip_phase_locator_prefix(item)
            if stripped is not None:
                values.append(stripped)
        elif isinstance(item, dict):
            _append_search_values(values, item.get("provides"))
    return values


def term_matches(term: str, value: str) -> bool:
    """Check whether a term matches (case-insensitive substring) against a value."""
    if not term or not value:
        return False
    return str(term).lower() in str(value).lower()


def _normalize_identifier(value: object) -> str:
    """Return a normalized identifier token for exact dependency matching."""
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().casefold()).strip()


def _normalized_identifier_matches(identifier: str, value: object, *preferred_keys: str) -> bool:
    """Check whether any normalized token in value matches identifier exactly."""
    normalized_identifier = _normalize_identifier(identifier)
    if not normalized_identifier:
        return False
    for candidate in _search_values_from_item(value, *preferred_keys):
        if _normalize_identifier(candidate) == normalized_identifier:
            return True
    return False


def parse_phase_range(range_str: str | None) -> tuple[str, str] | None:
    """Parse a phase range string like "1-5" or "3" or "2.1.1".

    Returns (min_str, max_str) or None if unparseable.
    """
    if not range_str:
        return None
    s = str(range_str).strip()
    parts = s.split("-")
    if len(parts) == 1:
        if not _is_valid_phase_str(parts[0]):
            return None
        return (parts[0], parts[0])
    if len(parts) == 2:
        if not _is_valid_phase_str(parts[0]) or not _is_valid_phase_str(parts[1]):
            return None
        if compare_phase_numbers(parts[0], parts[1]) > 0:
            logger.warning("Inverted phase range '%s'; swapping to '%s-%s'", range_str, parts[1], parts[0])
            parts[0], parts[1] = parts[1], parts[0]
        return (parts[0], parts[1])
    return None


def extract_context(text: str, term: str, radius: int = 75) -> str | None:
    """Extract a context snippet around the first occurrence of a term.

    Returns up to 2*radius characters of surrounding text, or None if not found.
    """
    if not text or not term:
        return None
    lower_text = text.lower()
    lower_term = str(term).lower()
    idx = lower_text.find(lower_term)
    if idx == -1:
        return None

    start = max(0, idx - radius)
    end = min(len(text), idx + len(lower_term) + radius)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _serialize_search_value(value: object) -> str:
    """Serialize structured frontmatter values without failing on YAML-native scalars."""
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except TypeError:
        return str(value)


def _load_result_registry_state(cwd: Path) -> dict[str, object]:
    """Load state for read-only result-registry projection without repair writes."""

    from gpd.core.state import peek_state_json

    data, _issues, _state_source = peek_state_json(
        cwd,
        recover_intent=False,
        surface_blocked_project_contract=True,
        acquire_lock=False,
    )
    return data if isinstance(data, dict) else {}


def _registry_context(*values: object) -> str | None:
    parts = [str(value) for value in values if value]
    return " | ".join(parts) if parts else None


def _registry_result_matches(
    result: object,
    *,
    provides: str | None,
    requires: str | None,
    equation: str | None,
    text: str | None,
) -> bool:
    """Return whether a canonical result should be included in a query search."""

    if provides and not _normalized_identifier_matches(provides, getattr(result, "id", None)):
        return False

    if requires and not any(
        _normalized_identifier_matches(requires, dependency) for dependency in getattr(result, "depends_on", []) or []
    ):
        return False

    if equation and not term_matches(equation, getattr(result, "equation", None) or ""):
        return False

    if text:
        searchable_values = (
            getattr(result, "id", None),
            getattr(result, "description", None),
            getattr(result, "equation", None),
            getattr(result, "validity", None),
        )
        if not any(term_matches(text, str(value or "")) for value in searchable_values):
            return False

    return bool(provides or requires or equation or text)


def _append_registry_search_matches(
    cwd: Path,
    matches: list[QueryMatch],
    *,
    provides: str | None,
    requires: str | None,
    equation: str | None,
    text: str | None,
    parsed_range: tuple[str, str] | None,
) -> None:
    """Append matches from the canonical intermediate-result registry."""

    from gpd.core.results import result_list

    state = _load_result_registry_state(cwd)
    if not state:
        return

    for result in result_list(state):
        phase = getattr(result, "phase", None) or ""
        if parsed_range and phase:
            phase_norm = phase_unpad(phase)
            min_norm = phase_unpad(parsed_range[0])
            max_norm = phase_unpad(parsed_range[1])
            if compare_phase_numbers(phase_norm, min_norm) < 0 or compare_phase_numbers(phase_norm, max_norm) > 0:
                continue
        if not _registry_result_matches(
            result,
            provides=provides,
            requires=requires,
            equation=equation,
            text=text,
        ):
            continue
        matches.append(
            QueryMatch(
                phase=phase,
                plan=None,
                field="result_registry",
                value=getattr(result, "id", None),
                context=_registry_context(
                    getattr(result, "equation", None),
                    getattr(result, "description", None),
                    getattr(result, "validity", None),
                ),
            )
        )


def _dependency_ids_from_items(items: list[object]) -> list[str]:
    return [str(item.id) for item in items if getattr(item, "id", None)]


# ─── Commands ────────────────────────────────────────────────────────────────


@instrument_gpd_function("query.collect_summaries")
def collect_summaries(cwd: Path) -> list[SummaryEntry]:
    """Enumerate all phase directories and collect parsed SUMMARY files."""
    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    results: list[SummaryEntry] = []

    if not phases_dir.is_dir():
        return results

    phase_dirs = sorted(
        [d for d in phases_dir.iterdir() if d.is_dir()],
        key=lambda d: _phase_sort_key(d.name),
    )

    for dir_path in phase_dirs:
        phase_match = re.match(r"^(\d+(?:\.\d+)*)", dir_path.name)
        phase_num = phase_match.group(1) if phase_match else dir_path.name

        try:
            files = list(dir_path.iterdir())
        except OSError:
            continue

        summaries = [f for f in files if layout.is_summary_file(f.name)]

        for summary_file in summaries:
            try:
                content = summary_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.debug("Skipping %s: invalid UTF-8", summary_file.name)
                continue
            except OSError:
                continue

            # Use canonical frontmatter parser from gpd.core.frontmatter
            try:
                fm, body = extract_frontmatter(content)
            except FrontmatterParseError:
                logger.debug("Skipping %s: YAML parse error", summary_file.name)
                continue

            # Derive plan identifier from filename
            plan_id = summary_file.name
            plan_id = layout.strip_summary_suffix(summary_file.name) or None

            results.append(
                SummaryEntry(
                    phase=phase_num,
                    dir_name=dir_path.name,
                    file=summary_file.name,
                    plan=plan_id,
                    frontmatter=fm,
                    body=body,
                )
            )

    return results


@instrument_gpd_function("query.collect_phase_markdown")
def collect_phase_markdown(cwd: Path) -> list[SummaryEntry]:
    """Enumerate all phase directories and collect non-SUMMARY .md files."""
    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    results: list[SummaryEntry] = []

    if not phases_dir.is_dir():
        return results

    phase_dirs = sorted(
        [d for d in phases_dir.iterdir() if d.is_dir()],
        key=lambda d: _phase_sort_key(d.name),
    )

    for dir_path in phase_dirs:
        phase_match = re.match(r"^(\d+(?:\.\d+)*)", dir_path.name)
        phase_num = phase_match.group(1) if phase_match else dir_path.name

        try:
            files = list(dir_path.iterdir())
        except OSError:
            continue

        md_files = [
            f for f in files
            if f.suffix.lower() == ".md" and not layout.is_summary_file(f.name)
        ]

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            try:
                fm, body = extract_frontmatter(content)
            except FrontmatterParseError:
                fm = {}
                body = content

            results.append(
                SummaryEntry(
                    phase=phase_num,
                    dir_name=dir_path.name,
                    file=md_file.name,
                    plan=md_file.stem,
                    frontmatter=fm,
                    body=body,
                )
            )

    return results


@instrument_gpd_function("query.collect_all_markdown")
def collect_all_markdown(cwd: Path) -> list[SummaryEntry]:
    """Collect all .md files across the entire GPD project directory."""
    layout = ProjectLayout(cwd)
    gpd_dir = layout.gpd
    results: list[SummaryEntry] = []

    if not gpd_dir.is_dir():
        return results

    for md_file in gpd_dir.rglob("*.md"):
        if not md_file.is_file():
            continue

        rel = md_file.relative_to(gpd_dir)
        parts = rel.parts
        phase_num = ""
        dir_name = ""
        if len(parts) >= 2 and parts[0] == "phases":
            dir_name = parts[1]
            phase_match = re.match(r"^(\d+(?:\.\d+)*)", dir_name)
            phase_num = phase_match.group(1) if phase_match else dir_name
        else:
            dir_name = str(rel.parent)

        try:
            content = md_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        try:
            fm, body = extract_frontmatter(content)
        except FrontmatterParseError:
            fm = {}
            body = content

        results.append(
            SummaryEntry(
                phase=phase_num,
                dir_name=dir_name,
                file=md_file.name,
                plan=md_file.stem,
                frontmatter=fm,
                body=body,
            )
        )

    return sorted(results, key=lambda e: (_phase_sort_key(e.dir_name), e.file))


@instrument_gpd_function("query.search")
def query(
    cwd: Path,
    *,
    provides: str | None = None,
    requires: str | None = None,
    affects: str | None = None,
    equation: str | None = None,
    phase_range: str | None = None,
    text: str | None = None,
    scope: str = "summary",
) -> QueryResult:
    """Search across phase results.

    Scans markdown files according to ``scope``: ``summary`` (default,
    SUMMARY files only), ``phase`` (all .md in phase dirs), or ``all``
    (entire GPD directory).  Frontmatter filters (provides/requires/affects)
    always use SUMMARY files regardless of scope.
    """
    if scope not in VALID_SCOPES:
        raise QueryError(f"invalid scope {scope!r}; expected one of: {', '.join(sorted(VALID_SCOPES))}")

    # provides/requires/affects are SUMMARY-specific frontmatter fields.
    # equation and text search body content, so they respect --scope.
    has_frontmatter_filter = any([provides, requires, affects])

    if has_frontmatter_filter:
        entries = collect_summaries(cwd)
    elif scope == "summary":
        entries = collect_summaries(cwd)
    elif scope == "phase":
        entries = collect_summaries(cwd) + collect_phase_markdown(cwd)
    elif scope == "all":
        entries = collect_all_markdown(cwd)
    else:
        entries = collect_summaries(cwd)

    matches: list[QueryMatch] = []
    parsed_range = parse_phase_range(phase_range)

    for entry in entries:
        phase = entry.phase
        plan = entry.plan
        fm = entry.frontmatter
        body = entry.body

        # Phase range filter (use phase_unpad for consistent comparison)
        if parsed_range:
            phase_norm = phase_unpad(phase)
            min_norm = phase_unpad(parsed_range[0])
            max_norm = phase_unpad(parsed_range[1])
            if compare_phase_numbers(phase_norm, min_norm) < 0 or compare_phase_numbers(phase_norm, max_norm) > 0:
                continue

        fm_provides = resolve_field(fm, "provides")
        fm_requires = resolve_field(fm, "requires")
        fm_affects = resolve_field(fm, "affects")

        # Search provides
        if provides:
            for p in fm_provides:
                display = p if isinstance(p, str) else _serialize_search_value(p)
                search_vals = _search_values_from_item(p, "name", "provides")
                if _any_match(provides, search_vals):
                    matches.append(
                        QueryMatch(
                            phase=phase,
                            plan=plan,
                            field="provides",
                            value=display,
                            context=extract_context(body, provides),
                        )
                    )
                    break

        # Search requires
        if requires:
            for r in fm_requires:
                display = r if isinstance(r, str) else _serialize_search_value(r)
                search_vals = _search_values_from_item(r, "provides", "phase")
                if _any_match(requires, search_vals):
                    matches.append(
                        QueryMatch(
                            phase=phase,
                            plan=plan,
                            field="requires",
                            value=display,
                            context=extract_context(body, requires),
                        )
                    )
                    break

        # Search affects
        if affects:
            for a in fm_affects:
                display = a if isinstance(a, str) else _serialize_search_value(a)
                search_vals = _search_values_from_item(a, "name", "affects")
                if _any_match(affects, search_vals):
                    matches.append(
                        QueryMatch(
                            phase=phase,
                            plan=plan,
                            field="affects",
                            value=display,
                            context=extract_context(body, affects),
                        )
                    )
                    break

        # Search for equation in body text and frontmatter
        if equation:
            equation_hits: list[str] = []
            if _search_fm_values(fm, equation):
                equation_hits.append("frontmatter")
            if term_matches(equation, body):
                equation_hits.append("body")
            if equation_hits:
                matches.append(
                    QueryMatch(
                        phase=phase,
                        plan=plan,
                        field="equation",
                        value=equation,
                        context=extract_context(body, equation),
                    )
                )

        # Free text search across everything
        if text:
            full_content = _serialize_search_value(fm) + "\n" + body
            if term_matches(text, full_content):
                matches.append(
                    QueryMatch(phase=phase, plan=plan, field="text", value=text, context=extract_context(body, text))
                )

        # If no specific filter, include all summaries
        if not provides and not requires and not affects and not equation and not text:
            matches.append(QueryMatch(phase=phase, plan=plan, field="all", value=None, context=body[:200].strip()))

    if not affects:
        _append_registry_search_matches(
            cwd,
            matches,
            provides=provides,
            requires=requires,
            equation=equation,
            text=text,
            parsed_range=parsed_range,
        )

    return QueryResult(matches=matches, total=len(matches))


@instrument_gpd_function("query.deps")
def query_deps(cwd: Path, identifier: str) -> DepsResult:
    """Trace what depends on a given result identifier.

    Finds the phase/plan that provides it, and all phases whose requires
    field references this identifier using exact normalized ID matching.

    Raises ValueError if identifier is empty.
    """
    if not identifier:
        raise QueryError("identifier required for query-deps")

    summaries = collect_summaries(cwd)
    provider_matches: list[DepsProvider] = []
    required_by: list[DepsConsumer] = []
    registry_depends_on: list[str] = []
    registry_direct_deps: list[str] = []
    registry_transitive_deps: list[str] = []

    for entry in summaries:
        phase = entry.phase
        plan = entry.plan
        fm = entry.frontmatter

        fm_provides = resolve_field(fm, "provides")
        fm_requires = resolve_field(fm, "requires")

        # Check if this summary provides the identifier
        for p in fm_provides:
            if _normalized_identifier_matches(identifier, p, "name", "provides"):
                provider_matches.append(DepsProvider(phase=phase, plan=plan, value=p))
                break

        # Check if this summary requires the identifier
        requires_values = extract_requires_identifiers(fm_requires)
        for rv in requires_values:
            if _normalized_identifier_matches(identifier, rv):
                required_by.append(DepsConsumer(phase=phase, plan=plan, value=rv))
                break

    state = _load_result_registry_state(cwd)
    if state:
        from gpd.core.errors import ResultNotFoundError
        from gpd.core.results import result_deps, result_downstream, result_search

        try:
            deps = result_deps(state, identifier)
        except ResultNotFoundError:
            deps = None
        if deps is not None:
            provider_matches.append(
                DepsProvider(
                    phase=deps.result.phase or "",
                    plan=None,
                    value=deps.result.id,
                )
            )
            registry_depends_on = list(deps.depends_on)
            registry_direct_deps = _dependency_ids_from_items(list(deps.direct_deps))
            registry_transitive_deps = _dependency_ids_from_items(list(deps.transitive_deps))

            try:
                downstream = result_downstream(state, identifier)
            except ResultNotFoundError:
                downstream = None
            if downstream is not None:
                for dependent in downstream.direct_dependents:
                    if not any(item.value == dependent.id for item in required_by):
                        required_by.append(DepsConsumer(phase=dependent.phase or "", plan=None, value=dependent.id))
        else:
            for dependent in result_search(state, depends_on=identifier).matches:
                if not any(item.value == dependent.id for item in required_by):
                    required_by.append(DepsConsumer(phase=dependent.phase or "", plan=None, value=dependent.id))

    return DepsResult(
        provides_by=provider_matches[-1] if provider_matches else None,
        provider_conflicts=provider_matches[:-1],
        required_by=required_by,
        depends_on=registry_depends_on,
        direct_deps=registry_direct_deps,
        transitive_deps=registry_transitive_deps,
    )


@instrument_gpd_function("query.assumptions")
def query_assumptions(cwd: Path, assumption: str) -> AssumptionsResult:
    """Find all phases that rely on a given assumption.

    Searches in approximations, conventions, key-decisions, body text,
    and general frontmatter for the given term.

    Raises ValueError if assumption is empty.
    """
    if not assumption:
        raise QueryError("assumption term required for query-assumptions")

    summaries = collect_summaries(cwd)
    affected: list[AssumptionAffected] = []

    for entry in summaries:
        phase = entry.phase
        plan = entry.plan
        fm = entry.frontmatter
        body = entry.body
        match_locations: list[str] = []

        # Check frontmatter fields related to assumptions
        approximations = fm.get("approximations") or fm.get("assumptions") or []
        conventions = fm.get("conventions") or []
        key_decisions = fm.get("key-decisions") or []

        # Search in approximations/assumptions
        if isinstance(approximations, list):
            for a in approximations:
                a_str = a if isinstance(a, str) else _serialize_search_value(a)
                if term_matches(assumption, a_str):
                    match_locations.append("approximations")
                    break
        elif isinstance(approximations, str) and term_matches(assumption, approximations):
            match_locations.append("approximations")

        # Search in conventions
        if isinstance(conventions, list):
            for c in conventions:
                c_str = c if isinstance(c, str) else _serialize_search_value(c)
                if term_matches(assumption, c_str):
                    match_locations.append("conventions")
                    break
        elif isinstance(conventions, str) and term_matches(assumption, conventions):
            match_locations.append("conventions")

        # Search in key-decisions
        if isinstance(key_decisions, list):
            for d in key_decisions:
                d_str = d if isinstance(d, str) else _serialize_search_value(d)
                if term_matches(assumption, d_str):
                    match_locations.append("key-decisions")
                    break
        elif isinstance(key_decisions, str) and term_matches(assumption, key_decisions):
            match_locations.append("key-decisions")

        # Search in body text
        if term_matches(assumption, body):
            match_locations.append("body")

        # Fallback: search all frontmatter
        if not match_locations:
            fm_str = _serialize_search_value(fm)
            if term_matches(assumption, fm_str):
                match_locations.append("frontmatter")

        if match_locations:
            affected.append(
                AssumptionAffected(
                    phase=phase,
                    plan=plan,
                    found_in=match_locations,
                    context=extract_context(body, assumption),
                )
            )

    from gpd.core.results import result_list

    state = _load_result_registry_state(cwd)
    for result in result_list(state):
        searchable_values = (
            getattr(result, "id", None),
            getattr(result, "description", None),
            getattr(result, "equation", None),
            getattr(result, "validity", None),
        )
        if not any(term_matches(assumption, str(value or "")) for value in searchable_values):
            continue
        affected.append(
            AssumptionAffected(
                phase=getattr(result, "phase", None) or "",
                plan=None,
                found_in=["result_registry"],
                context=_registry_context(
                    getattr(result, "equation", None),
                    getattr(result, "description", None),
                    getattr(result, "validity", None),
                ),
            )
        )

    return AssumptionsResult(
        assumption=assumption,
        affected_phases=affected,
        total=len(affected),
    )


# ─── Private Helpers ─────────────────────────────────────────────────────────


def _any_match(term: str, values: list[str]) -> bool:
    """Check if term matches any value in the list."""
    return any(term_matches(term, v) for v in values)


def _search_fm_values(obj: object, term: str) -> bool:
    """Recursively search frontmatter values for a term match."""
    if obj is None:
        return False
    if isinstance(obj, str):
        return term_matches(term, obj)
    if isinstance(obj, list):
        return any(_search_fm_values(item, term) for item in obj)
    if isinstance(obj, dict):
        return any(_search_fm_values(v, term) for v in obj.values())
    return term_matches(term, str(obj))

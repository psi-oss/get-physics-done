"""Cross-phase result query commands for GPD.

Searches across all phase SUMMARY files to find results by provides, requires,
affects, equation, text, and assumption references.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import STANDALONE_SUMMARY, SUMMARY_SUFFIX, ProjectLayout
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


class SummaryEntry(BaseModel):
    """A parsed SUMMARY file from a phase directory."""

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
    required_by: list[DepsConsumer] = Field(default_factory=list)


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


def term_matches(term: str, value: str) -> bool:
    """Check whether a term matches (case-insensitive substring) against a value."""
    if not term or not value:
        return False
    return str(term).lower() in str(value).lower()


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


# ─── Commands ────────────────────────────────────────────────────────────────


@instrument_gpd_function("query.collect_summaries")
def collect_summaries(cwd: Path) -> list[SummaryEntry]:
    """Enumerate all phase directories and collect parsed SUMMARY files."""
    phases_dir = ProjectLayout(cwd).phases_dir
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

        summaries = [f for f in files if f.name.endswith(SUMMARY_SUFFIX) or f.name == STANDALONE_SUMMARY]

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
            if plan_id.upper().endswith(SUMMARY_SUFFIX.upper()):
                plan_id = plan_id[: -len(SUMMARY_SUFFIX)]
            elif plan_id.upper() == STANDALONE_SUMMARY.upper():
                plan_id = ""
            plan_id = plan_id or None

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
) -> QueryResult:
    """Search across all phase results.

    Scans all .gpd/phases/SUMMARY.md files, matching frontmatter fields
    and body text against the provided search terms.
    """
    summaries = collect_summaries(cwd)
    matches: list[QueryMatch] = []
    parsed_range = parse_phase_range(phase_range)

    for entry in summaries:
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

    return QueryResult(matches=matches, total=len(matches))


@instrument_gpd_function("query.deps")
def query_deps(cwd: Path, identifier: str) -> DepsResult:
    """Trace what depends on a given result identifier.

    Finds the phase/plan that provides it, and all phases whose requires
    field references this identifier.

    Raises ValueError if identifier is empty.
    """
    if not identifier:
        raise QueryError("identifier required for query-deps")

    summaries = collect_summaries(cwd)
    provides_by: DepsProvider | None = None
    required_by: list[DepsConsumer] = []

    for entry in summaries:
        phase = entry.phase
        plan = entry.plan
        fm = entry.frontmatter

        fm_provides = resolve_field(fm, "provides")
        fm_requires = resolve_field(fm, "requires")

        # Check if this summary provides the identifier
        for p in fm_provides:
            search_vals = _search_values_from_item(p, "name", "provides")
            for sv in search_vals:
                if term_matches(identifier, sv):
                    # Prefer exact match
                    if provides_by is None or str(sv).lower() == str(identifier).lower():
                        provides_by = DepsProvider(phase=phase, plan=plan, value=p)
                    break

        # Check if this summary requires the identifier
        requires_values = extract_requires_values(fm_requires)
        for rv in requires_values:
            if term_matches(identifier, rv):
                required_by.append(DepsConsumer(phase=phase, plan=plan, value=rv))
                break

    return DepsResult(provides_by=provides_by, required_by=required_by)


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

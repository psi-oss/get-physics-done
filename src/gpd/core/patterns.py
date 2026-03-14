"""Cross-project physics pattern library management.

Manages a library of learned error patterns organized by physics domain.
Patterns capture sign errors, factor errors, convention pitfalls, and other
recurring issues that persist across GPD projects.

Storage layout::

    {patterns_root}/
        index.json
        patterns-by-domain/{domain}/{category}-{slug}.md

Public API
----------
pattern_init     — create directory structure + empty index
pattern_add      — add a new pattern
pattern_list     — list with optional filters
pattern_search   — keyword search
pattern_promote  — promote confidence level
pattern_seed     — initialize with canonical physics patterns
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import (
    ENV_DATA_DIR,
    ENV_PATTERNS_ROOT,
    PATTERNS_BY_DOMAIN_DIR,
    PATTERNS_DIR_NAME,
    PATTERNS_INDEX_FILENAME,
    PLANNING_DIR_NAME,
    SEED_PATTERN_INITIAL_OCCURRENCES,
)
from gpd.core.errors import PatternError
from gpd.core.observability import gpd_span, instrument_gpd_function
from gpd.core.utils import atomic_write, file_lock, generate_slug

logger = logging.getLogger(__name__)

__all__ = [
    "CONFIDENCE_LEVELS",
    "ConfidenceLevel",
    "PatternAddResult",
    "PatternCategory",
    "PatternDomain",
    "PatternEntry",
    "PatternIndex",
    "PatternListResult",
    "PatternPromoteResult",
    "PatternSearchResult",
    "PatternSeedResult",
    "PatternSeverity",
    "patterns_root",
    "VALID_CATEGORIES",
    "VALID_DOMAINS",
    "VALID_SEVERITIES",
    "ensure_library",
    "pattern_add",
    "pattern_init",
    "pattern_list",
    "pattern_promote",
    "pattern_search",
    "pattern_seed",
]

# ─── Enums ────────────────────────────────────────────────────────────────────


class PatternDomain(StrEnum):
    """Physics domains for pattern classification."""

    QFT = "qft"
    CONDENSED_MATTER = "condensed-matter"
    STAT_MECH = "stat-mech"
    GR = "gr"
    AMO = "amo"
    NUCLEAR = "nuclear"
    CLASSICAL = "classical"
    FLUID = "fluid"
    PLASMA = "plasma"
    ASTRO = "astro"
    MATHEMATICAL = "mathematical"
    SOFT_MATTER = "soft-matter"
    QUANTUM_INFO = "quantum-info"


class PatternCategory(StrEnum):
    """Error category for pattern classification."""

    SIGN_ERROR = "sign-error"
    FACTOR_ERROR = "factor-error"
    CONVENTION_PITFALL = "convention-pitfall"
    CONVERGENCE_ISSUE = "convergence-issue"
    APPROXIMATION_FAILURE = "approximation-failure"
    NUMERICAL_INSTABILITY = "numerical-instability"
    CONCEPTUAL_ERROR = "conceptual-error"
    DIMENSIONAL_ERROR = "dimensional-error"


class PatternSeverity(StrEnum):
    """Severity level for patterns."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceLevel(StrEnum):
    """Confidence progression for patterns."""

    SINGLE_OBSERVATION = "single_observation"
    CONFIRMED = "confirmed"
    SYSTEMATIC = "systematic"


#: Convenience sets for validation.
VALID_DOMAINS: frozenset[str] = frozenset(e.value for e in PatternDomain)
VALID_CATEGORIES: frozenset[str] = frozenset(e.value for e in PatternCategory)
VALID_SEVERITIES: tuple[str, ...] = tuple(e.value for e in PatternSeverity)
CONFIDENCE_LEVELS: tuple[str, ...] = tuple(e.value for e in ConfidenceLevel)

_SEVERITY_ORDER = {s: i for i, s in enumerate(VALID_SEVERITIES)}
_CONFIDENCE_ORDER = {c: i for i, c in enumerate(CONFIDENCE_LEVELS)}
_CONFIDENCE_PROMOTION: dict[str, str | None] = {
    "single_observation": "confirmed",
    "confirmed": "systematic",
    "systematic": None,
}

# ─── Pydantic Models ─────────────────────────────────────────────────────────


class PatternEntry(BaseModel):
    """A single pattern in the library index."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    file: str
    domain: str
    category: str
    severity: str
    confidence: str
    title: str
    first_seen: str
    last_seen: str
    occurrence_count: int = 1
    tags: list[str] = Field(default_factory=list)


class PatternIndex(BaseModel):
    """Root index for the pattern library."""

    version: int = 1
    patterns: list[PatternEntry] = Field(default_factory=list)


class PatternAddResult(BaseModel):
    """Returned by :func:`pattern_add`."""

    added: bool = True
    id: str
    file: str
    severity: str
    confidence: str = "single_observation"


class PatternListResult(BaseModel):
    """Returned by :func:`pattern_list`."""

    patterns: list[PatternEntry] = Field(default_factory=list)
    count: int = 0
    library_exists: bool = True


class PatternPromoteResult(BaseModel):
    """Returned by :func:`pattern_promote`."""

    promoted: bool
    id: str
    from_level: str
    to_level: str | None = None
    occurrence_count: int = 0
    reason: str | None = None


class PatternSearchResult(BaseModel):
    """Returned by :func:`pattern_search`."""

    matches: list[PatternEntry] = Field(default_factory=list)
    count: int = 0
    query: str = ""
    library_exists: bool = True


class PatternSeedResult(BaseModel):
    """Returned by :func:`pattern_seed`."""

    seeded: bool = True
    added: int
    skipped: int
    total: int


# ─── Path Resolution ─────────────────────────────────────────────────────────


def patterns_root(specs_root: Path | None = None) -> Path:
    """Resolve the patterns library root directory.

    Precedence: *specs_root* argument > ``GPD_PATTERNS_ROOT`` env >
    ``GPD_DATA_DIR`` env > ``~/.gpd/learned-patterns``.
    """
    if specs_root is not None:
        return specs_root / PATTERNS_DIR_NAME

    explicit = os.environ.get(ENV_PATTERNS_ROOT, "").strip()
    if explicit:
        return Path(explicit) if Path(explicit).is_absolute() else Path.cwd() / explicit

    data_dir = os.environ.get(ENV_DATA_DIR, "").strip()
    if data_dir:
        return Path(data_dir) / PATTERNS_DIR_NAME

    return Path.home() / PLANNING_DIR_NAME / PATTERNS_DIR_NAME


# ─── Index I/O ───────────────────────────────────────────────────────────────


def _load_index(root: Path) -> PatternIndex | None:
    """Load index.json as a Pydantic model. Returns ``None`` if absent."""
    index_path = root / PATTERNS_INDEX_FILENAME
    try:
        content = index_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        return PatternIndex.model_validate_json(content)
    except ValueError as exc:
        raise PatternError(f"Malformed {index_path}: {exc}") from exc


def _save_index(root: Path, index: PatternIndex) -> None:
    """Persist the pattern index with file locking."""
    index_path = root / PATTERNS_INDEX_FILENAME
    with file_lock(index_path):
        atomic_write(index_path, index.model_dump_json(indent=2) + "\n")


def _today_iso() -> str:
    return date.today().isoformat()


def _generate_tags(title: str, description: str) -> list[str]:
    """Extract up to 10 keyword tags from title + description."""
    words = re.sub(r"[^a-z0-9\s-]", "", (title + " " + description).lower()).split()
    unique = list(dict.fromkeys(w for w in words if len(w) > 2))
    return unique[:10]


def _build_pattern_md(
    *,
    domain: str,
    category: str,
    severity: str,
    confidence: str,
    first_seen: str,
    last_seen: str,
    occurrence_count: int,
    title: str,
    description: str = "",
    detection: str = "",
    prevention: str = "",
    example: str = "",
    test_value: str = "",
    root_cause: str = "",
) -> str:
    """Build the markdown content for a pattern file."""
    return "\n".join(
        [
            "---",
            f"domain: {domain}",
            f"category: {category}",
            f"severity: {severity}",
            f"confidence: {confidence}",
            f"first_seen: {first_seen}",
            f"last_seen: {last_seen}",
            f"occurrence_count: {occurrence_count}",
            "---",
            "",
            f"## Pattern: {title}",
            "",
            f"**What goes wrong:** {description or '[To be filled]'}",
            "",
            f"**Why it happens:** {root_cause or '[Root cause to be documented]'}",
            "",
            f"**How to detect:** {detection or '[Detection method to be documented]'}",
            "",
            f"**How to prevent:** {prevention or '[Prevention guidance to be documented]'}",
            "",
            f"**Example:** {example or '[Example to be added]'}",
            "",
            f"**Test value:** {test_value or '[Numerical test to be added]'}",
            "",
        ]
    )


# ─── Library Init ─────────────────────────────────────────────────────────────


def ensure_library(root: Path | None = None) -> Path:
    """Ensure the pattern library directory structure and index exist.

    Returns the patterns root path. Idempotent.
    """
    if root is None:
        root = patterns_root()
    if _load_index(root) is not None:
        return root

    root.mkdir(parents=True, exist_ok=True)
    domains_dir = root / PATTERNS_BY_DOMAIN_DIR
    for domain in VALID_DOMAINS:
        (domains_dir / domain).mkdir(parents=True, exist_ok=True)

    index_path = root / PATTERNS_INDEX_FILENAME
    if not index_path.exists():
        _save_index(root, PatternIndex())
    return root


def pattern_init(root: Path | None = None) -> Path:
    """Create directory structure and empty index. Returns patterns root."""
    return ensure_library(root)


# ─── Public API ───────────────────────────────────────────────────────────────


@instrument_gpd_function("patterns.add")
def pattern_add(
    *,
    domain: str,
    title: str,
    category: str = "conceptual-error",
    severity: str = "medium",
    description: str = "",
    detection: str = "",
    prevention: str = "",
    example: str = "",
    test_value: str = "",
    root: Path | None = None,
) -> PatternAddResult:
    """Add a new pattern to the library.

    Raises:
        ValueError: On invalid domain/category/severity or duplicate ID.
    """
    if domain not in VALID_DOMAINS:
        raise PatternError(f"Invalid domain {domain!r}. Valid: {sorted(VALID_DOMAINS)}")
    if category not in VALID_CATEGORIES:
        raise PatternError(f"Invalid category {category!r}. Valid: {sorted(VALID_CATEGORIES)}")
    if severity not in VALID_SEVERITIES:
        raise PatternError(f"Invalid severity {severity!r}. Valid: {', '.join(VALID_SEVERITIES)}")

    lib_root = ensure_library(root)
    index = _load_index(lib_root) or PatternIndex()

    slug = generate_slug(title)
    if slug is None:
        raise PatternError("title cannot be empty")
    pattern_id = f"{domain}-{category}-{slug}"

    if any(p.id == pattern_id for p in index.patterns):
        raise PatternError(f"Pattern {pattern_id!r} already exists. Use pattern_promote() to update confidence.")

    today = _today_iso()
    rel_path = f"{PATTERNS_BY_DOMAIN_DIR}/{domain}/{category}-{slug}.md"
    full_path = lib_root / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    with gpd_span("patterns.add", **{"gpd.pattern_id": pattern_id, "gpd.domain": domain}):
        content = _build_pattern_md(
            domain=domain,
            category=category,
            severity=severity,
            confidence="single_observation",
            first_seen=today,
            last_seen=today,
            occurrence_count=1,
            title=title,
            description=description,
            detection=detection,
            prevention=prevention,
            example=example,
            test_value=test_value,
        )
        atomic_write(full_path, content)

        tags = _generate_tags(title, description)
        index.patterns.append(
            PatternEntry(
                id=pattern_id,
                file=rel_path,
                domain=domain,
                category=category,
                severity=severity,
                confidence="single_observation",
                title=title,
                first_seen=today,
                last_seen=today,
                occurrence_count=1,
                tags=tags,
            )
        )
        _save_index(lib_root, index)

        logger.info("pattern_added", extra={"id": pattern_id, "domain": domain, "severity": severity})

    return PatternAddResult(id=pattern_id, file=rel_path, severity=severity)


@instrument_gpd_function("patterns.list")
def pattern_list(
    *,
    domain: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    root: Path | None = None,
) -> PatternListResult:
    """List patterns with optional filters, sorted by severity then confidence."""
    lib_root = root or patterns_root()
    index = _load_index(lib_root)
    if index is None:
        return PatternListResult(library_exists=False)

    with gpd_span("patterns.list"):
        patterns = list(index.patterns)
        if domain:
            patterns = [p for p in patterns if p.domain == domain]
        if category:
            patterns = [p for p in patterns if p.category == category]
        if severity:
            patterns = [p for p in patterns if p.severity == severity]

        patterns.sort(
            key=lambda p: (
                _SEVERITY_ORDER.get(p.severity, 3),
                _CONFIDENCE_ORDER.get(p.confidence, 2),
                -p.occurrence_count,
            )
        )

    return PatternListResult(patterns=patterns, count=len(patterns))


@instrument_gpd_function("patterns.promote")
def pattern_promote(pattern_id: str, *, root: Path | None = None) -> PatternPromoteResult:
    """Promote a pattern's confidence level.

    single_observation -> confirmed -> systematic.

    Raises:
        ValueError: If pattern not found or library not initialized.
    """
    lib_root = root or patterns_root()
    index = _load_index(lib_root)
    if index is None:
        raise PatternError("Pattern library not initialized. Call pattern_init() first.")

    entry = next((p for p in index.patterns if p.id == pattern_id), None)
    if entry is None:
        raise PatternError(f"Pattern {pattern_id!r} not found")

    current = entry.confidence
    next_level = _CONFIDENCE_PROMOTION.get(current)

    if next_level is None:
        return PatternPromoteResult(
            promoted=False,
            id=pattern_id,
            from_level=current,
            occurrence_count=entry.occurrence_count,
            reason="already_at_maximum",
        )

    with gpd_span("patterns.promote", **{"gpd.pattern_id": pattern_id, "gpd.to": next_level}):
        entry.confidence = next_level
        entry.last_seen = _today_iso()
        entry.occurrence_count += 1

        # Update pattern file frontmatter
        _update_pattern_frontmatter(lib_root, entry)
        _save_index(lib_root, index)

        logger.info("pattern_promoted", extra={"id": pattern_id, "from": current, "to": next_level})

    return PatternPromoteResult(
        promoted=True,
        id=pattern_id,
        from_level=current,
        to_level=next_level,
        occurrence_count=entry.occurrence_count,
    )


@instrument_gpd_function("patterns.search")
def pattern_search(query: str, *, root: Path | None = None) -> PatternSearchResult:
    """Search patterns by keyword with relevance scoring.

    Raises:
        PatternError: If query is empty.
    """
    if not query or not query.strip():
        raise PatternError("Search query required")

    lib_root = root or patterns_root()
    index = _load_index(lib_root)
    if index is None:
        return PatternSearchResult(query=query, library_exists=False)

    with gpd_span("patterns.search", **{"gpd.query": query}):
        terms = [t for t in query.lower().split() if len(t) > 1]
        scored: list[tuple[int, PatternEntry]] = []

        for p in index.patterns:
            searchable = " ".join([p.title, p.domain, p.category, *p.tags]).lower()
            score = 0
            for term in terms:
                if term in searchable:
                    score += 1
                if term in p.tags:
                    score += 2
                if p.domain == term or p.category == term:
                    score += 3
            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: -x[0])
        matches = [p for _, p in scored]

    return PatternSearchResult(matches=matches, count=len(matches), query=query)


def _update_pattern_frontmatter(root: Path, entry: PatternEntry) -> None:
    """Update frontmatter fields in the pattern markdown file."""
    full_path = root / entry.file
    try:
        content = full_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    content = re.sub(r"^confidence:\s*\S+", f"confidence: {entry.confidence}", content, flags=re.MULTILINE)
    content = re.sub(r"^last_seen:\s*\S+", f"last_seen: {entry.last_seen}", content, flags=re.MULTILINE)
    content = re.sub(
        r"^occurrence_count:\s*\d+",
        f"occurrence_count: {entry.occurrence_count}",
        content,
        flags=re.MULTILINE,
    )
    atomic_write(full_path, content)


# ─── Seed — bootstrap patterns ───────────────────────────────────────────────

_BOOTSTRAP_PATTERNS: list[dict[str, object]] = [
    {
        "domain": "qft",
        "category": "sign-error",
        "severity": "critical",
        "title": "Sign error in Fourier convention switch",
        "slug": "fourier-convention-switch",
        "domains_extra": ["condensed-matter"],
        "description": "When combining expressions derived with different Fourier conventions, sign errors appear in interference terms, propagators, and response functions.",
        "detection": "Check the sign of the imaginary part of response functions. Verify retarded/advanced structure.",
        "prevention": "Lock Fourier convention at project start. Insert explicit conversion factors when combining.",
        "tags": ["fourier", "sign", "convention", "propagator", "response-function"],
    },
    {
        "domain": "condensed-matter",
        "category": "factor-error",
        "severity": "high",
        "title": "Missing factor of 2pi in density of states",
        "slug": "density-of-states-2pi",
        "domains_extra": ["stat-mech", "qft"],
        "description": "The density of states picks up factors of 2pi from Fourier convention and momentum measure.",
        "detection": "Check dimensional analysis. Verify free-particle DOS reproduces known results.",
        "prevention": "Always write momentum integration measure explicitly with (2pi)^d factor.",
        "tags": ["density-of-states", "factor", "2pi", "momentum", "integration-measure"],
    },
    {
        "domain": "qft",
        "category": "conceptual-error",
        "severity": "critical",
        "title": "Wrong branch cut in analytic continuation",
        "slug": "analytic-continuation-branch-cut",
        "domains_extra": ["condensed-matter"],
        "description": "Choosing the wrong Riemann sheet when analytically continuing flips the sign of Im[G].",
        "detection": "Check spectral function positivity A(k,w) >= 0. Check causality G^R(t<0) = 0.",
        "prevention": "Always continue iwn -> w + ie for retarded functions. Verify poles in lower half-plane.",
        "tags": ["analytic-continuation", "matsubara", "branch-cut", "retarded", "spectral-function"],
    },
    {
        "domain": "qft",
        "category": "sign-error",
        "severity": "critical",
        "title": "Metric signature mismatch in propagator",
        "slug": "metric-signature-mismatch",
        "description": "Mixing (+,-,-,-) and (-,+,+,+) conventions in the same calculation.",
        "detection": "Check what k^2 = m^2 means. If on-shell condition looks wrong, suspect signature mismatch.",
        "prevention": "State metric signature at top of every derivation. Check external source conventions.",
        "tags": ["metric", "signature", "propagator", "sign", "east-coast", "west-coast"],
    },
    {
        "domain": "stat-mech",
        "category": "factor-error",
        "severity": "high",
        "title": "Missing 1/N! for identical particles",
        "slug": "gibbs-factor-overcounting",
        "domains_extra": ["qft"],
        "description": "Classical partition function for N identical particles requires 1/N! Gibbs factor.",
        "detection": "Check entropy extensivity. Check mixing entropy vanishes for identical gases.",
        "prevention": "Always include 1/(N! h^{3N}) in classical partition functions.",
        "tags": ["gibbs", "overcounting", "partition-function", "symmetry-factor"],
    },
    {
        "domain": "qft",
        "category": "factor-error",
        "severity": "high",
        "title": "Confusing coupling constant conventions",
        "slug": "coupling-constant-conventions",
        "description": "Different sources define coupling as g, g^2, g^2/(4pi), alpha. Combining without converting gives wrong coefficients.",
        "detection": "Check tree-level amplitude. Verify alpha ~ 1/137.",
        "prevention": "Convert all couplings to single convention before combining.",
        "tags": ["coupling", "alpha", "convention", "fine-structure", "normalization"],
    },
    {
        "domain": "qft",
        "category": "dimensional-error",
        "severity": "high",
        "title": "Dimensional mismatch when restoring hbar and c",
        "slug": "natural-units-restoration",
        "domains_extra": ["gr", "condensed-matter", "stat-mech"],
        "description": "When converting from natural units to SI, each quantity needs specific powers of hbar and c.",
        "detection": "Check final expression has correct SI dimensions. Evaluate numerically in both systems.",
        "prevention": "Use systematic procedure based on mass dimension.",
        "tags": ["natural-units", "hbar", "dimensional-analysis", "unit-conversion"],
    },
    {
        "domain": "qft",
        "category": "sign-error",
        "severity": "critical",
        "title": "Wrong sign in Wick rotation",
        "slug": "wick-rotation-sign",
        "description": "Wick rotation t -> -i*tau must respect pole structure. Direction depends on metric signature.",
        "detection": "Check Euclidean action is bounded below. Verify Euclidean propagator is positive.",
        "prevention": "With (+,-,-,-), rotate k0 -> ik4 counterclockwise. Verify Minkowski -> Euclidean mapping.",
        "tags": ["wick-rotation", "euclidean", "sign", "pole", "analytic-continuation"],
    },
]


@instrument_gpd_function("patterns.seed")
def pattern_seed(*, root: Path | None = None) -> PatternSeedResult:
    """Seed the library with canonical physics bootstrap patterns.

    Idempotent — skips patterns that already exist.
    """
    lib_root = ensure_library(root)
    index = _load_index(lib_root) or PatternIndex()
    today = _today_iso()
    existing_ids = {p.id for p in index.patterns}

    added = 0
    skipped = 0

    with gpd_span("patterns.seed"):
        for bp in _BOOTSTRAP_PATTERNS:
            domain = str(bp["domain"])
            category = str(bp["category"])
            slug = str(bp.get("slug", ""))
            pattern_id = f"{domain}-{category}-{slug}"
            rel_path = f"{PATTERNS_BY_DOMAIN_DIR}/{domain}/{category}-{slug}.md"
            tags = list(bp.get("tags", [])) if isinstance(bp.get("tags"), list) else []

            if pattern_id in existing_ids:
                skipped += 1
            else:
                full_path = lib_root / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)

                content = _build_pattern_md(
                    domain=domain,
                    category=category,
                    severity=str(bp["severity"]),
                    confidence="systematic",
                    first_seen=today,
                    last_seen=today,
                    occurrence_count=SEED_PATTERN_INITIAL_OCCURRENCES,
                    title=str(bp["title"]),
                    description=str(bp.get("description", "")),
                    detection=str(bp.get("detection", "")),
                    prevention=str(bp.get("prevention", "")),
                    root_cause="See cross-project-patterns.md for root cause analysis.",
                )
                atomic_write(full_path, content)

                entry = PatternEntry(
                    id=pattern_id,
                    file=rel_path,
                    domain=domain,
                    category=category,
                    severity=str(bp["severity"]),
                    confidence="systematic",
                    title=str(bp["title"]),
                    first_seen=today,
                    last_seen=today,
                    occurrence_count=SEED_PATTERN_INITIAL_OCCURRENCES,
                    tags=tags,
                )
                index.patterns.append(entry)
                existing_ids.add(pattern_id)
                added += 1

            # Cross-domain entries
            for extra_domain in bp.get("domains_extra", []):
                extra_domain = str(extra_domain)
                extra_id = f"{extra_domain}-{category}-{slug}"
                if extra_id in existing_ids:
                    skipped += 1
                    continue
                extra_rel = f"{PATTERNS_BY_DOMAIN_DIR}/{extra_domain}/{category}-{slug}.md"
                extra_path = lib_root / extra_rel
                extra_path.parent.mkdir(parents=True, exist_ok=True)

                extra_content = _build_pattern_md(
                    domain=extra_domain,
                    category=category,
                    severity=str(bp["severity"]),
                    confidence="systematic",
                    first_seen=today,
                    last_seen=today,
                    occurrence_count=SEED_PATTERN_INITIAL_OCCURRENCES,
                    title=str(bp["title"]),
                    description=str(bp.get("description", "")),
                    detection=str(bp.get("detection", "")),
                    prevention=str(bp.get("prevention", "")),
                    root_cause=f"See primary pattern at `{rel_path}`.",
                )
                atomic_write(extra_path, extra_content)

                index.patterns.append(
                    PatternEntry(
                        id=extra_id,
                        file=extra_rel,
                        domain=extra_domain,
                        category=category,
                        severity=str(bp["severity"]),
                        confidence="systematic",
                        title=str(bp["title"]),
                        first_seen=today,
                        last_seen=today,
                        occurrence_count=SEED_PATTERN_INITIAL_OCCURRENCES,
                        tags=tags,
                    )
                )
                existing_ids.add(extra_id)
                added += 1

        _save_index(lib_root, index)

        logger.info("patterns_seeded", extra={"added": added, "skipped": skipped, "total": len(index.patterns)})

    return PatternSeedResult(added=added, skipped=skipped, total=len(index.patterns))

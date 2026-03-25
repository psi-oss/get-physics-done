"""Convention lock management for GPD physics research.

Provides the 18-field convention lock system: set/list/diff/check operations,
ASSERT_CONVENTION parsing from LaTeX/Python/Markdown files, key alias
normalization, and value sanitization.

Key features:
- KEY_ALIASES: 13 short aliases (e.g., "metric" -> "metric_signature")
  for CLI ergonomics.
- VALUE_ALIASES: Normalizes variant notations (e.g., "+---" -> "mostly-minus").
- ASSERT_CONVENTION parsing: Scans file content for convention assertions in
  Markdown/LaTeX/Python comments.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.contracts import ConventionLock
from gpd.core.errors import ConventionError
from gpd.core.observability import instrument_gpd_function

logger = logging.getLogger(__name__)

__all__ = [
    "KNOWN_CONVENTIONS",
    "CONVENTION_LABELS",
    "KEY_ALIASES",
    "VALUE_ALIASES",
    "ConventionSetResult",
    "ConventionEntry",
    "ConventionListResult",
    "ConventionDiff",
    "ConventionDiffResult",
    "ConventionCheckResult",
    "AssertionMismatch",
    "normalize_key",
    "normalize_value",
    "is_bogus_value",
    "sanitize_value",
    "convention_set",
    "convention_list",
    "convention_diff",
    "convention_diff_phases",
    "convention_check",
    "parse_assert_conventions",
    "validate_assertions",
]

# --- Canonical Convention Fields (18) ---
# Derived from ConventionLock model fields to prevent drift.

KNOWN_CONVENTIONS: list[str] = [name for name in ConventionLock.model_fields if name != "custom_conventions"]

# Explicit label map (not auto-generated from field names, which would produce
# incorrect casing like "Levi civita sign" instead of "Levi-Civita sign").
CONVENTION_LABELS: dict[str, str] = {
    "metric_signature": "Metric signature",
    "fourier_convention": "Fourier convention",
    "natural_units": "Natural units",
    "gauge_choice": "Gauge choice",
    "regularization_scheme": "Regularization scheme",
    "renormalization_scheme": "Renormalization scheme",
    "coordinate_system": "Coordinate system",
    "spin_basis": "Spin basis",
    "state_normalization": "State normalization",
    "coupling_convention": "Coupling convention",
    "index_positioning": "Index positioning",
    "time_ordering": "Time ordering",
    "commutation_convention": "Commutation convention",
    "levi_civita_sign": "Levi-Civita sign",
    "generator_normalization": "Generator normalization",
    "covariant_derivative_sign": "Covariant derivative sign",
    "gamma_matrix_convention": "Gamma matrix convention",
    "creation_annihilation_order": "Creation/annihilation order",
}

# Short aliases (physicist-friendly) -> canonical convention_lock field names.
KEY_ALIASES: dict[str, str] = {
    "metric": "metric_signature",
    "fourier": "fourier_convention",
    "units": "natural_units",
    "gauge": "gauge_choice",
    "regularization": "regularization_scheme",
    "renorm": "renormalization_scheme",
    "renormalization": "renormalization_scheme",
    "coordinates": "coordinate_system",
    "spin": "spin_basis",
    "normalization": "state_normalization",
    "coupling": "coupling_convention",
    "index": "index_positioning",
    "ordering": "time_ordering",
    "commutator": "commutation_convention",
}

# Per-field value normalization: variant notations -> canonical form.
# Physicists write metric signatures as (+,-,-,-) or (-,+,+,+) but the
# canonical form in the lock may be "mostly-plus" or "mostly-minus".
VALUE_ALIASES: dict[str, dict[str, str]] = {
    "metric_signature": {
        "(+,-,-,-)": "mostly-minus",
        "(+,\u2212,\u2212,\u2212)": "mostly-minus",
        "+---": "mostly-minus",
        "mostly_minus": "mostly-minus",
        "(-,+,+,+)": "mostly-plus",
        "(\u2212,+,+,+)": "mostly-plus",
        "-+++": "mostly-plus",
        "mostly_plus": "mostly-plus",
        "(+,+,+,+)": "euclidean",
        "Euclidean (+,+,+,+)": "euclidean",
        "++++": "euclidean",
    },
}

# Values that should be treated as "unset" (prevent string-vs-null confusion)
_BOGUS_VALUES = frozenset({"", "null", "undefined", "none"})

# Regex for ASSERT_CONVENTION lines:
#   <!-- ASSERT_CONVENTION: key=value, key=value -->  (Markdown)
#   % ASSERT_CONVENTION: key=value, key=value         (LaTeX)
#   # ASSERT_CONVENTION: key=value, key=value         (Python)
_ASSERT_LINE_RE = re.compile(
    r"^\s*(?:<!--|[%#])\s*ASSERT_CONVENTION[:\s]+(.+?)(?:\s*-->)?\s*$",
    re.MULTILINE,
)
_KV_PAIR_RE = re.compile(r"^(\w+)\s*=\s*(.+)$")


# --- Result Types ---


class ConventionSetResult(BaseModel):
    """Result of setting a convention."""

    model_config = ConfigDict(frozen=True)

    updated: bool
    key: str
    value: str | None = None
    previous: str | None = None
    custom: bool = False
    reason: str | None = None
    hint: str | None = None


class ConventionEntry(BaseModel):
    """A single convention entry in a check result."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str = ""
    value: str | None = None
    is_set: bool = False
    canonical: bool = True


class ConventionListResult(BaseModel):
    """Result of listing all conventions."""

    model_config = ConfigDict(frozen=True)

    conventions: dict[str, ConventionEntry]
    total: int
    set_count: int
    unset_count: int
    canonical_total: int


class ConventionDiff(BaseModel):
    """A single difference between two convention locks."""

    model_config = ConfigDict(frozen=True)

    key: str
    from_value: str | None = None
    to_value: str | None = None


class ConventionDiffResult(BaseModel):
    """Result of diffing two convention locks."""

    model_config = ConfigDict(frozen=True)

    changed: list[ConventionDiff] = Field(default_factory=list)
    added: list[ConventionDiff] = Field(default_factory=list)
    removed: list[ConventionDiff] = Field(default_factory=list)
    note: str | None = None


class ConventionCheckResult(BaseModel):
    """Result of checking convention completeness."""

    model_config = ConfigDict(frozen=True)

    complete: bool
    missing: list[ConventionEntry]
    set_conventions: list[ConventionEntry]
    custom: list[ConventionEntry]
    total: int
    set_count: int
    missing_count: int
    custom_count: int


class AssertionMismatch(BaseModel):
    """A convention assertion that doesn't match the lock."""

    model_config = ConfigDict(frozen=True)

    file: str
    key: str
    file_value: str
    lock_value: str


# --- Key/Value Normalization ---


def normalize_key(key: str) -> str:
    """Resolve a short/alias key to the canonical convention_lock field name."""
    return KEY_ALIASES.get(key, key)


def normalize_value(canonical_key: str, value: str) -> str:
    """Normalize a convention value for comparison using field-specific aliases."""
    aliases = VALUE_ALIASES.get(canonical_key)
    if not aliases:
        return value
    return aliases.get(value, value)


def is_bogus_value(value: object) -> bool:
    """Return True if the value should be treated as unset."""
    if value is None:
        return True
    return str(value).strip().lower() in _BOGUS_VALUES


def sanitize_value(value: str) -> str:
    """Sanitize a convention value: collapse newlines, strip whitespace.

    Raises ConventionError for empty or bogus values.
    """
    cleaned = re.sub(r"[\r\n]+", " ", value).strip()
    if cleaned.lower() in _BOGUS_VALUES:
        raise ConventionError(f"Convention value cannot be empty or bogus ({cleaned!r}).")
    return cleaned


# --- Convention Operations ---


@instrument_gpd_function("conventions.set")
def convention_set(lock: ConventionLock, key: str, value: str, *, force: bool = False) -> ConventionSetResult:
    """Set a convention value on the lock.

    If the convention is already set to a different value, requires force=True
    to overwrite (immutability gate).

    Returns a ConventionSetResult indicating what happened.

    Raises ConventionError for empty/bogus values.
    """
    cleaned = sanitize_value(value)
    canonical_key = normalize_key(key)
    cleaned = normalize_value(canonical_key, cleaned)
    is_custom = canonical_key not in KNOWN_CONVENTIONS

    if is_custom:
        previous = lock.custom_conventions.get(canonical_key)
    else:
        previous = getattr(lock, canonical_key, None)

    # Immutability gate: require force to overwrite existing non-null convention
    if previous is not None and not is_bogus_value(previous) and previous != cleaned and not force:
        return ConventionSetResult(
            updated=False,
            key=canonical_key,
            value=cleaned,
            previous=previous,
            custom=is_custom,
            reason="convention_already_set",
            hint="Use force=True to overwrite an existing convention",
        )

    # Apply the update
    if is_custom:
        lock.custom_conventions[canonical_key] = cleaned
    else:
        setattr(lock, canonical_key, cleaned)

    return ConventionSetResult(
        updated=True,
        key=canonical_key,
        value=cleaned,
        previous=previous,
        custom=is_custom,
    )


def convention_list(lock: ConventionLock) -> ConventionListResult:
    """List all conventions with their set/unset status."""
    conventions: dict[str, ConventionEntry] = {}

    # Canonical conventions
    for key in KNOWN_CONVENTIONS:
        val = getattr(lock, key, None)
        conventions[key] = ConventionEntry(
            key=key,
            label=CONVENTION_LABELS.get(key, key.replace("_", " ").title()),
            value=val,
            is_set=not is_bogus_value(val),
            canonical=True,
        )

    # Custom conventions
    for key, val in lock.custom_conventions.items():
        label = key.replace("_", " ").title()
        conventions[key] = ConventionEntry(
            key=key,
            label=label,
            value=val,
            is_set=not is_bogus_value(val),
            canonical=False,
        )

    set_count = sum(1 for c in conventions.values() if c.is_set)
    total = len(conventions)
    return ConventionListResult(
        conventions=conventions,
        total=total,
        set_count=set_count,
        unset_count=total - set_count,
        canonical_total=len(KNOWN_CONVENTIONS),
    )


@instrument_gpd_function("conventions.diff")
def convention_diff(lock_a: ConventionLock, lock_b: ConventionLock) -> ConventionDiffResult:
    """Compare two convention locks and return differences."""
    changed: list[ConventionDiff] = []
    added: list[ConventionDiff] = []
    removed: list[ConventionDiff] = []

    # Compare canonical fields
    for key in KNOWN_CONVENTIONS:
        val_a = getattr(lock_a, key, None)
        val_b = getattr(lock_b, key, None)
        norm_a = normalize_value(key, val_a) if val_a is not None else None
        norm_b = normalize_value(key, val_b) if val_b is not None else None
        if norm_a is None and norm_b is not None:
            added.append(ConventionDiff(key=key, to_value=norm_b))
        elif norm_a is not None and norm_b is None:
            removed.append(ConventionDiff(key=key, from_value=norm_a))
        elif norm_a is not None and norm_b is not None and norm_a != norm_b:
            changed.append(ConventionDiff(key=key, from_value=norm_a, to_value=norm_b))

    # Compare custom conventions
    all_custom_keys = set(lock_a.custom_conventions) | set(lock_b.custom_conventions)
    for key in sorted(all_custom_keys):
        val_a = lock_a.custom_conventions.get(key)
        val_b = lock_b.custom_conventions.get(key)
        norm_a = normalize_value(key, val_a) if val_a is not None else None
        norm_b = normalize_value(key, val_b) if val_b is not None else None
        if norm_a is None and norm_b is not None:
            added.append(ConventionDiff(key=key, to_value=norm_b))
        elif norm_a is not None and norm_b is None:
            removed.append(ConventionDiff(key=key, from_value=norm_a))
        elif norm_a is not None and norm_b is not None and norm_a != norm_b:
            changed.append(ConventionDiff(key=key, from_value=norm_a, to_value=norm_b))

    return ConventionDiffResult(changed=changed, added=added, removed=removed)


def _extract_phase_conventions(cwd: Path, phase_id: str) -> dict[str, str] | None:
    """Extract convention mentions from a phase's SUMMARY frontmatter and body.

    Extracts convention mentions from frontmatter and body text:
    1. Parse YAML frontmatter for conventions/convention_lock fields
    2. Scan body text for "Convention Label: value" patterns

    Returns a dict of convention key -> value, or None if phase not found.
    """
    from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
    from gpd.core.phases import find_phase

    info = find_phase(cwd, phase_id)
    if not info:
        return None

    phase_dir = cwd / info.directory
    conventions: dict[str, str] = {}

    for summary_name in info.summaries:
        summary_path = phase_dir / summary_name
        if not summary_path.is_file():
            continue

        try:
            content = summary_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        try:
            fm, _body = extract_frontmatter(content)
        except FrontmatterParseError:
            fm = {}

        # Check frontmatter for convention-related fields
        fm_conventions = fm.get("conventions")
        if isinstance(fm_conventions, dict):
            conventions.update({k: str(v) for k, v in fm_conventions.items() if v is not None})
        elif isinstance(fm_conventions, list):
            for conv in fm_conventions:
                match = re.match(r"^([^=:]+?)\s*[=:]\s*(.+)$", str(conv))
                if match:
                    conventions[match.group(1).strip()] = match.group(2).strip()

        fm_lock = fm.get("convention_lock")
        if isinstance(fm_lock, dict):
            for k, v in fm_lock.items():
                if k != "custom_conventions":
                    if v is not None:
                        conventions[k] = str(v)
            custom = fm_lock.get("custom_conventions")
            if isinstance(custom, dict):
                conventions.update({k: str(v) for k, v in custom.items() if v is not None})

        # Scan body for "Convention Label: value" patterns
        for key in KNOWN_CONVENTIONS:
            label = CONVENTION_LABELS.get(key, key.replace("_", " ").title())
            escaped = re.escape(label)
            pattern = re.compile(
                rf"(?:^|\n)\s*[-*]?\s*{escaped}:\s*(.+?)\s*$",
                re.IGNORECASE | re.MULTILINE,
            )
            match = pattern.search(content)
            if match and key not in conventions:
                conventions[key] = match.group(1).strip()

    return conventions if conventions else None


@instrument_gpd_function("conventions.diff_phases")
def convention_diff_phases(
    cwd: Path,
    phase1: str | None = None,
    phase2: str | None = None,
) -> ConventionDiffResult:
    """Diff convention mentions across two phase SUMMARYs.

    Extracts conventions from phase summary frontmatter and body text,
    then computes the diff. Falls back to current state convention_lock
    if no convention data is found in either phase.
    """
    import json

    from gpd.core.state import load_state_json

    if not phase1 or not phase2:
        state_data = load_state_json(cwd) or {}
        lock_data = state_data.get("convention_lock", {})
        return ConventionDiffResult(
            note=(
                f"Two phase identifiers required for convention diff. Current convention_lock: {json.dumps(lock_data)}"
            ),
        )

    conv1 = _extract_phase_conventions(cwd, phase1)
    conv2 = _extract_phase_conventions(cwd, phase2)

    conv1_empty = not conv1 or len(conv1) == 0
    conv2_empty = not conv2 or len(conv2) == 0

    if conv1_empty and conv2_empty:
        state_data = load_state_json(cwd) or {}
        lock_data = state_data.get("convention_lock", {})
        return ConventionDiffResult(
            note=(
                f"Could not find convention data for phases {phase1} and {phase2}. "
                f"Current convention_lock: {json.dumps(lock_data)}"
            ),
        )

    changed: list[ConventionDiff] = []
    added: list[ConventionDiff] = []
    removed: list[ConventionDiff] = []

    # Normalize keys before comparison
    norm_conv1 = {normalize_key(k): v for k, v in (conv1 or {}).items()}
    norm_conv2 = {normalize_key(k): v for k, v in (conv2 or {}).items()}
    all_keys = set(norm_conv1) | set(norm_conv2)

    for key in sorted(all_keys):
        val1 = norm_conv1.get(key)
        val2 = norm_conv2.get(key)
        norm1 = normalize_value(key, str(val1)) if val1 is not None else None
        norm2 = normalize_value(key, str(val2)) if val2 is not None else None
        if norm1 is None and norm2 is not None:
            added.append(ConventionDiff(key=key, to_value=norm2))
        elif norm1 is not None and norm2 is None:
            removed.append(ConventionDiff(key=key, from_value=norm1))
        elif norm1 is not None and norm2 is not None and norm1 != norm2:
            changed.append(ConventionDiff(key=key, from_value=norm1, to_value=norm2))

    note = None
    if not conv1:
        note = f"No convention data found in phase {phase1} summaries."
    elif not conv2:
        note = f"No convention data found in phase {phase2} summaries."

    return ConventionDiffResult(changed=changed, added=added, removed=removed, note=note)


@instrument_gpd_function("conventions.check")
def convention_check(lock: ConventionLock) -> ConventionCheckResult:
    """Check convention completeness: which canonical fields are set vs missing."""
    missing: list[ConventionEntry] = []
    set_conventions: list[ConventionEntry] = []
    custom: list[ConventionEntry] = []

    for key in KNOWN_CONVENTIONS:
        val = getattr(lock, key, None)
        label = CONVENTION_LABELS.get(key, key.replace("_", " ").title())
        if is_bogus_value(val):
            missing.append(ConventionEntry(key=key, label=label, is_set=False, canonical=True))
        else:
            set_conventions.append(ConventionEntry(key=key, label=label, value=val, is_set=True, canonical=True))

    for key, val in lock.custom_conventions.items():
        if val is not None and not is_bogus_value(val):
            custom.append(ConventionEntry(key=key, value=val, is_set=True, canonical=False))

    return ConventionCheckResult(
        complete=len(missing) == 0,
        missing=missing,
        set_conventions=set_conventions,
        custom=custom,
        total=len(KNOWN_CONVENTIONS),
        set_count=len(set_conventions),
        missing_count=len(missing),
        custom_count=len(custom),
    )


# --- ASSERT_CONVENTION Parsing ---


def parse_assert_conventions(content: str) -> list[tuple[str, str]]:
    """Parse ASSERT_CONVENTION directives from file content.

    Supports three comment formats:
        <!-- ASSERT_CONVENTION: key=value, key=value -->  (Markdown/HTML)
        % ASSERT_CONVENTION: key=value, key=value         (LaTeX)
        # ASSERT_CONVENTION: key=value, key=value         (Python)

    Returns a list of (canonical_key, value) pairs.
    """
    pairs: list[tuple[str, str]] = []
    for match in _ASSERT_LINE_RE.finditer(content):
        payload = match.group(1)
        # Split on commas followed by a key= pattern to avoid splitting
        # values that contain commas (e.g., metric=(-,+,+,+))
        raw_pairs = re.split(r",\s*(?=\w+=)", payload)
        for raw in raw_pairs:
            raw = raw.strip()
            kv = _KV_PAIR_RE.match(raw)
            if not kv:
                continue
            key = normalize_key(kv.group(1).strip())
            val = kv.group(2).strip()
            pairs.append((key, val))
    return pairs


@instrument_gpd_function("conventions.validate_assertions")
def validate_assertions(
    content: str,
    lock: ConventionLock,
    *,
    filename: str = "<unknown>",
) -> list[AssertionMismatch]:
    """Validate ASSERT_CONVENTION directives in file content against a lock.

    Returns a list of mismatches (empty = all assertions match or no assertions found).
    """
    mismatches: list[AssertionMismatch] = []
    assertions = parse_assert_conventions(content)

    for key, asserted_value in assertions:
        # Look up the lock value: canonical field, then custom_conventions
        lock_value: str | None = None
        if key in KNOWN_CONVENTIONS:
            lock_value = getattr(lock, key, None)
        if lock_value is None:
            lock_value = lock.custom_conventions.get(key)

        if lock_value is None:
            # Convention not set in lock — skip (can't validate)
            continue

        # Normalize both values for comparison
        norm_lock = normalize_value(key, str(lock_value).strip())
        norm_asserted = normalize_value(key, asserted_value)

        if norm_lock != norm_asserted:
            mismatches.append(
                AssertionMismatch(
                    file=filename,
                    key=key,
                    file_value=asserted_value,
                    lock_value=str(lock_value),
                )
            )

    return mismatches

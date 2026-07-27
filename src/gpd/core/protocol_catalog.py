"""Transport-neutral catalog of GPD physics computation protocols.

Owns everything about the protocol documents in ``specs/references/protocols/``:
authoritative file loading, domain-manifest validation, section / step /
checkpoint extraction, frontmatter normalization, keyword routing, and the query
payloads served for a protocol lookup. Nothing here knows about MCP, transports,
or response envelopes, so the same catalog backs the MCP server and the CLI.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable, Mapping
from functools import lru_cache
from pathlib import Path

from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
from gpd.core.observability import gpd_span
from gpd.specs import SPECS_DIR

__all__ = [
    "MAX_ROUTED_PROTOCOLS",
    "PROTOCOLS_DIR",
    "PROTOCOL_DOMAINS_MANIFEST",
    "PROTOCOL_USAGE_CAUTION",
    "ProtocolStore",
    "available_protocol_names",
    "extract_protocol_sections",
    "extract_protocol_steps_and_checkpoints",
    "get_protocol_store",
    "load_protocol_domain_manifest",
    "load_protocol_parts",
    "parse_protocol_domain_manifest",
    "protocol_checkpoints_payload",
    "protocol_detail_payload",
    "protocol_domain_values",
    "protocol_listing_payload",
    "protocol_route_payload",
    "route_keyword_score",
    "route_name_score",
    "tokenize_route_text",
]

logger = logging.getLogger(__name__)

PROTOCOLS_DIR = SPECS_DIR / "references" / "protocols"
PROTOCOL_DOMAINS_MANIFEST = PROTOCOLS_DIR / "protocol-domains.json"

#: Number of routed protocols surfaced by :func:`protocol_route_payload`.
MAX_ROUTED_PROTOCOLS = 10

PROTOCOL_USAGE_CAUTION = (
    "Protocol content is methodological guidance only. Do not claim any step, checkpoint, artifact, or result was "
    "completed unless it was actually executed or observed. Missing inputs remain blockers, not invitations to improvise."
)

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^(\d+\.|[-*])\s+")
_FRONTMATTER_LEADING_BLANKS_RE = re.compile(r"^(?:[ \t]*\r?\n)+(?=---[ \t]*\r?\n)")
_FRONTMATTER_OPEN_RE = re.compile(r"^---[ \t]*(?:\r?\n|$)")
_FRONTMATTER_BLOCK_RE = re.compile(r"^---[ \t]*\r?\n(?:[\s\S]*?\r?\n)?---[ \t]*(?:\r?\n|$)")

_STEP_SECTION_KEYWORDS = ("step", "procedure", "method", "organization", "approach")
_CHECKPOINT_SECTION_KEYWORDS = ("verification", "checkpoint", "check", "common pitfall", "common error")


def extract_protocol_sections(body: str) -> list[dict[str, str | int]]:
    """Extract H2/H3 sections from markdown body."""
    sections: list[dict[str, str | int]] = []
    matches = list(_HEADING_RE.finditer(body))
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        sections.append({"level": level, "title": title, "content": content})
    return sections


def _list_item_texts(content: str) -> list[str]:
    """Return the text of every ordered/unordered list item in *content*."""
    items: list[str] = []
    for line in content.split("\n"):
        stripped = line.strip()
        if _LIST_ITEM_RE.match(stripped):
            items.append(_LIST_ITEM_RE.sub("", stripped).strip())
    return items


def extract_protocol_steps_and_checkpoints(body: str) -> tuple[list[str], list[str]]:
    """Extract procedural steps and verification checkpoints from the body.

    Parses sections once and extracts both in a single pass (avoids
    duplicate ``extract_protocol_sections`` calls).
    """
    steps: list[str] = []
    checkpoints: list[str] = []
    for section in extract_protocol_sections(body):
        title_lower = str(section["title"]).lower()
        if any(kw in title_lower for kw in _STEP_SECTION_KEYWORDS):
            steps.extend(_list_item_texts(str(section["content"])))
        elif any(kw in title_lower for kw in _CHECKPOINT_SECTION_KEYWORDS):
            checkpoints.extend(_list_item_texts(str(section["content"])))
    return steps, checkpoints


def _has_unclosed_frontmatter(text: str) -> bool:
    """Return whether *text* opens a frontmatter block that is never closed."""
    candidate = _FRONTMATTER_LEADING_BLANKS_RE.sub("", text.lstrip("\ufeff"), count=1)
    return bool(_FRONTMATTER_OPEN_RE.match(candidate)) and not _FRONTMATTER_BLOCK_RE.match(candidate)


def load_protocol_parts(path: Path) -> tuple[dict[str, object], str]:
    """Read one authoritative protocol document or fail closed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Failed to read {path}: {exc}") from exc

    if _has_unclosed_frontmatter(text):
        raise ValueError(f"Malformed frontmatter in {path}: Unclosed frontmatter block")
    try:
        meta, body = extract_frontmatter(text)
    except FrontmatterParseError as exc:
        raise ValueError(f"Malformed frontmatter in {path}: {exc}") from exc
    return meta, body


# ---------------------------------------------------------------------------
# Domain manifest
# ---------------------------------------------------------------------------


def parse_protocol_domain_manifest(manifest_path: Path) -> dict[str, str]:
    """Load and validate the authoritative protocol-domain manifest at *manifest_path*."""
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read protocol domain manifest {manifest_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Protocol domain manifest must be a JSON object")

    allowed_keys = {"schema_version", "protocol_domains"}
    extra_keys = sorted(str(key) for key in raw if str(key) not in allowed_keys)
    if extra_keys:
        raise ValueError(f"Protocol domain manifest has unexpected keys: {', '.join(extra_keys)}")

    schema_version = raw.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError(f"Unsupported protocol domain manifest schema_version: {raw.get('schema_version')!r}")

    protocol_domains = raw.get("protocol_domains")
    if not isinstance(protocol_domains, dict) or not protocol_domains:
        raise ValueError("Protocol domain manifest must include a non-empty protocol_domains object")

    domains: dict[str, str] = {}
    for protocol_name, domain in protocol_domains.items():
        if not isinstance(protocol_name, str) or not protocol_name.strip():
            raise ValueError("Protocol domain manifest contains a blank protocol name")
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError(f"Protocol domain manifest for {protocol_name!r} must be a non-empty string")
        normalized_name = protocol_name.strip()
        normalized_domain = domain.strip()
        if normalized_name in domains:
            raise ValueError(f"Protocol domain manifest contains duplicate protocol {normalized_name!r}")
        domains[normalized_name] = normalized_domain
    return domains


@lru_cache(maxsize=1)
def load_protocol_domain_manifest() -> dict[str, str]:
    """Load the authoritative protocol-domain manifest shipped with the specs."""
    return parse_protocol_domain_manifest(PROTOCOL_DOMAINS_MANIFEST)


def protocol_domain_values(manifest: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return the authoritative protocol-domain enum values."""
    resolved = load_protocol_domain_manifest() if manifest is None else manifest
    return tuple(sorted(set(resolved.values())))


# ---------------------------------------------------------------------------
# Frontmatter normalization
# ---------------------------------------------------------------------------


def _normalize_protocol_tier(raw: object, *, protocol_name: str) -> int:
    """Return an integer tier for protocol sorting and ranking."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"Protocol {protocol_name!r} has invalid frontmatter: tier must be an integer, got {raw!r}")
    return raw


def _normalize_protocol_load_when(raw: object, *, protocol_name: str) -> list[str]:
    """Return a validated ``load_when`` keyword list for protocol routing."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(
            f"Protocol {protocol_name!r} has invalid frontmatter: load_when must be a list of non-empty strings"
        )

    cleaned: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(
                f"Protocol {protocol_name!r} has invalid frontmatter: load_when contains non-string entry {item!r}"
            )
        stripped = item.strip()
        if not stripped:
            raise ValueError(
                f"Protocol {protocol_name!r} has invalid frontmatter: load_when entries must be non-empty strings"
            )
        cleaned.append(stripped)
    return cleaned


def _normalize_protocol_context_cost(raw: object, *, protocol_name: str) -> str:
    """Return a validated string ``context_cost`` label for protocol metadata."""
    if not isinstance(raw, str):
        raise ValueError(
            f"Protocol {protocol_name!r} has invalid frontmatter: context_cost must be a non-empty string, got {raw!r}"
        )
    stripped = raw.strip()
    if not stripped:
        raise ValueError(f"Protocol {protocol_name!r} has invalid frontmatter: context_cost must be a non-empty string")
    return stripped


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def tokenize_route_text(text: str) -> list[str]:
    """Return lower-cased alphanumeric tokens for routing comparisons."""
    return [_normalize_route_token(token) for token in re.findall(r"[a-z0-9]+", text.casefold())]


def _normalize_route_token(token: str) -> str:
    """Normalize morphology-heavy routing tokens to a stable lexical stem."""
    for suffix in ("ization", "isation", "ative", "ation", "ments", "ment", "ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def _contains_token_sequence(haystack: list[str], needle: list[str]) -> bool:
    """Return whether ``needle`` appears as a contiguous token sequence in ``haystack``."""
    if not needle or len(needle) > len(haystack):
        return False
    sequence_length = len(needle)
    return any(
        haystack[index : index + sequence_length] == needle for index in range(len(haystack) - sequence_length + 1)
    )


def route_keyword_score(keyword: str, query_tokens: list[str]) -> int:
    """Return a score for one routing keyword against tokenized query text."""
    keyword_tokens = tokenize_route_text(keyword)
    if not keyword_tokens:
        return 0
    if len(keyword_tokens) == 1:
        return 10 if keyword_tokens[0] in query_tokens else 0
    if _contains_token_sequence(query_tokens, keyword_tokens):
        return 10 + len(keyword_tokens)
    if any(token in query_tokens and len(token) >= 7 for token in keyword_tokens):
        return 4
    return 0


def route_name_score(name: str, query_tokens: list[str]) -> int:
    """Return a score for one protocol name against tokenized query text."""
    name_tokens = tokenize_route_text(name.replace("-", " "))
    if not name_tokens:
        return 0
    if len(name_tokens) == 1:
        return 5 if name_tokens[0] in query_tokens else 0
    if _contains_token_sequence(query_tokens, name_tokens):
        return 5 + len(name_tokens)
    if any(token in query_tokens and len(token) >= 7 for token in name_tokens):
        return 2
    return 0


# ---------------------------------------------------------------------------
# Protocol store
# ---------------------------------------------------------------------------


class ProtocolStore:
    """In-memory store of parsed protocol files."""

    def __init__(
        self,
        protocols_dir: Path,
        *,
        domain_manifest_loader: Callable[[], Mapping[str, str]] = load_protocol_domain_manifest,
    ) -> None:
        self._protocols: dict[str, dict[str, object]] = {}
        self._load_all(protocols_dir, domain_manifest_loader)

    def _load_all(self, protocols_dir: Path, domain_manifest_loader: Callable[[], Mapping[str, str]]) -> None:
        with gpd_span("protocols.load_all", protocols_dir=str(protocols_dir)):
            self._do_load(protocols_dir, domain_manifest_loader)

    def _do_load(self, protocols_dir: Path, domain_manifest_loader: Callable[[], Mapping[str, str]]) -> None:
        if not protocols_dir.is_dir():
            raise OSError(f"Protocols directory not found: {protocols_dir}")
        domain_manifest = domain_manifest_loader()
        protocol_files = sorted(protocols_dir.glob("*.md"))
        if not protocol_files:
            raise ValueError(f"No protocol files found in {protocols_dir}")
        protocol_names = {path.stem for path in protocol_files}
        for path in protocol_files:
            name = path.stem
            meta, body = load_protocol_parts(path)
            load_when = _normalize_protocol_load_when(meta.get("load_when", []), protocol_name=name)
            tier = _normalize_protocol_tier(meta.get("tier", 2), protocol_name=name)
            context_cost = _normalize_protocol_context_cost(meta.get("context_cost", "medium"), protocol_name=name)

            domain = _protocol_domain(name, domain_manifest)
            steps, checkpoints = extract_protocol_steps_and_checkpoints(body)

            # Extract title from first H1
            title_match = _TITLE_RE.search(body)
            title = title_match.group(1).strip() if title_match else name.replace("-", " ").title()

            self._protocols[name] = {
                "name": name,
                "title": title,
                "domain": domain,
                "tier": tier,
                "context_cost": context_cost,
                "load_when": load_when,
                "steps": steps,
                "checkpoints": checkpoints,
                "body": body,
            }

        unused_manifest_entries = sorted(name for name in domain_manifest if name not in protocol_names)
        if unused_manifest_entries:
            raise ValueError(
                "Protocol domain manifest has entries without protocol files: " + ", ".join(unused_manifest_entries)
            )

        logger.info("Loaded %d protocols from %s", len(self._protocols), protocols_dir)

    def get(self, name: str) -> dict[str, object] | None:
        """Get a protocol by name (stem of the .md file)."""
        return self._protocols.get(name)

    def list_all(self, domain: str | None = None) -> list[dict[str, object]]:
        """List protocols, optionally filtered by domain."""
        if domain is not None and domain not in self.domains:
            raise ValueError(f"Unknown protocol domain: {domain}")
        result = []
        for p in self._protocols.values():
            if domain and p["domain"] != domain:
                continue
            result.append(
                {
                    "name": p["name"],
                    "title": p["title"],
                    "domain": p["domain"],
                    "tier": p["tier"],
                    "context_cost": p["context_cost"],
                    "load_when": p["load_when"],
                }
            )
        return sorted(result, key=lambda x: (x["tier"], str(x["name"])))

    def route(self, computation_type: str) -> list[dict[str, object]]:
        """Find protocols matching a computation type description.

        Matches against load_when keywords and protocol names using exact token or
        contiguous token-sequence matching. This avoids short acronym substrings
        from leaking into unrelated queries.
        """
        query_tokens = tokenize_route_text(computation_type)
        scored: list[tuple[int, dict[str, object]]] = []

        for p in self._protocols.values():
            score = 0
            for keyword in p["load_when"]:
                if isinstance(keyword, str):
                    score += route_keyword_score(keyword, query_tokens)

            score += route_name_score(str(p["name"]), query_tokens)

            if score > 0 and p["tier"] == 1:
                score += 2

            if score > 0:
                scored.append(
                    (
                        score,
                        {
                            "name": p["name"],
                            "title": p["title"],
                            "domain": p["domain"],
                            "tier": p["tier"],
                            "context_cost": p["context_cost"],
                            "relevance_score": score,
                        },
                    )
                )

        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored]

    @property
    def domains(self) -> list[str]:
        """List all unique domains."""
        return sorted({str(p["domain"]) for p in self._protocols.values()})


_store: ProtocolStore | None = None
_store_lock = threading.Lock()


def get_protocol_store() -> ProtocolStore:
    """Return the lazily-initialised shared protocol store (thread-safe)."""
    global _store  # noqa: PLW0603
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = ProtocolStore(PROTOCOLS_DIR)
        return _store


def _protocol_domain(name: str, domain_manifest: Mapping[str, str]) -> str:
    """Return the authoritative domain for one protocol name."""
    try:
        return domain_manifest[name]
    except KeyError as exc:
        raise ValueError(f"Protocol {name!r} is missing domain metadata in {PROTOCOL_DOMAINS_MANIFEST.name}") from exc


# ---------------------------------------------------------------------------
# Query payloads
# ---------------------------------------------------------------------------


def available_protocol_names(store: ProtocolStore) -> list[str]:
    """Return every protocol name in *store*, tier-ordered like ``list_all``."""
    return [str(protocol["name"]) for protocol in store.list_all()]


def protocol_detail_payload(store: ProtocolStore, name: str) -> dict[str, object] | None:
    """Return the full protocol record for *name*, or ``None`` when unknown."""
    protocol = store.get(name)
    if protocol is None:
        return None
    return {
        "name": protocol["name"],
        "title": protocol["title"],
        "domain": protocol["domain"],
        "tier": protocol["tier"],
        "context_cost": protocol["context_cost"],
        "load_when": protocol["load_when"],
        "steps": protocol["steps"],
        "checkpoints": protocol["checkpoints"],
        "content": protocol["body"],
        "usage_caution": PROTOCOL_USAGE_CAUTION,
    }


def protocol_listing_payload(store: ProtocolStore, domain: str | None = None) -> dict[str, object]:
    """Return the protocol listing, optionally filtered by *domain*."""
    protocols = store.list_all(domain)
    return {
        "count": len(protocols),
        "protocols": protocols,
        "available_domains": store.domains,
    }


def protocol_route_payload(store: ProtocolStore, computation_type: str) -> dict[str, object]:
    """Return the top protocol matches for a computation-type description."""
    matches = store.route(computation_type)
    return {
        "query": computation_type,
        "match_count": len(matches),
        "protocols": matches[:MAX_ROUTED_PROTOCOLS],
        "usage_caution": PROTOCOL_USAGE_CAUTION,
    }


def protocol_checkpoints_payload(store: ProtocolStore, name: str) -> dict[str, object] | None:
    """Return the verification checkpoints for *name*, or ``None`` when unknown."""
    protocol = store.get(name)
    if protocol is None:
        return None
    checkpoints = protocol["checkpoints"]
    return {
        "name": protocol["name"],
        "title": protocol["title"],
        "checkpoints": checkpoints,
        "checkpoint_count": len(checkpoints),
        "usage_caution": PROTOCOL_USAGE_CAUTION,
    }

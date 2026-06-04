"""Source normalization helpers for ``gpd:ideate``."""

from __future__ import annotations

import re
import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gpd.core.arxiv_source_download import normalize_arxiv_id
from gpd.core.constants import KNOWLEDGE_DIR_NAME, PLANNING_DIR_NAME
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

__all__ = [
    "IdeateArgumentContext",
    "IdeateSourceKind",
    "IdeateSourceManifest",
    "IdeateSourceRecord",
    "IdeateSourceStatus",
    "normalize_arxiv_id",
    "normalize_ideate_sources",
    "parse_ideate_arguments",
]


IdeateSourceKind = Literal["arxiv", "pdf", "tex", "knowledge_doc", "directory_item", "topic", "blocked"]
IdeateSourceStatus = Literal["pending", "completed", "reused", "blocked"]

_SUPPORTED_PAPER_SUFFIXES = frozenset({".pdf", ".tex"})
_IGNORED_DIRECTORY_FILENAMES = frozenset({"artifact-manifest.json", "paper-config.json"})


@dataclass(frozen=True, slots=True)
class IdeateSourceRecord:
    """One source row in an ideation source manifest."""

    source_id: str
    kind: IdeateSourceKind
    input: str
    normalized_ref: str
    status: IdeateSourceStatus
    digest_path: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def input_type(self) -> IdeateSourceKind:
        """Compatibility alias for older source-intake callers."""

        return self.kind

    @property
    def normalized_input(self) -> str:
        """Compatibility alias for older source-intake callers."""

        return self.normalized_ref

    @property
    def digestion_status(self) -> IdeateSourceStatus:
        """Compatibility alias for older source-intake callers."""

        return self.status

    def to_dict(self) -> dict[str, object]:
        """Return the blackboard-ready manifest row."""

        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "input": self.input,
            "normalized_ref": self.normalized_ref,
            "status": self.status,
            "digest_path": self.digest_path,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class IdeateSourceManifest:
    """Normalized ideation source manifest."""

    sources: tuple[IdeateSourceRecord, ...]
    topic: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def has_usable_sources(self) -> bool:
        """Return True when at least one source can be digested or reused."""

        return any(source.kind not in {"blocked", "topic"} and source.status != "blocked" for source in self.sources)

    @property
    def blocked(self) -> bool:
        """Return True when ideation has no usable source-grounding rows."""

        return not self.has_usable_sources

    @property
    def source_inputs(self) -> tuple[str, ...]:
        """Return normalized refs that represent source inputs, excluding topic rows."""

        return tuple(
            source.normalized_ref
            for source in self.sources
            if source.kind not in {"blocked", "topic"} and source.status != "blocked"
        )

    @property
    def knowledge_docs(self) -> tuple[str, ...]:
        """Return reused knowledge document paths referenced by the manifest."""

        docs: list[str] = []
        for source in self.sources:
            if source.digest_path and source.digest_path not in docs:
                docs.append(source.digest_path)
        return tuple(docs)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable source manifest."""

        return {
            "sources": [source.to_dict() for source in self.sources],
            "topic": self.topic,
            "source_inputs": list(self.source_inputs),
            "knowledge_docs": list(self.knowledge_docs),
            "warnings": list(self.warnings),
            "blocked": self.blocked,
        }


@dataclass(frozen=True, slots=True)
class IdeateArgumentContext:
    """Parsed ideation source arguments."""

    raw_arguments: tuple[str, ...]
    source_inputs: tuple[str, ...]
    max_papers: int | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _KdocIndex:
    by_arxiv: dict[str, str]
    by_path_key: dict[str, str]


@dataclass(frozen=True, slots=True)
class _NormalizedInput:
    records: tuple[IdeateSourceRecord, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _DirectoryScan:
    selected: tuple[Path, ...]
    warnings: tuple[str, ...]


def parse_ideate_arguments(arguments: str | Sequence[str] | None) -> IdeateArgumentContext:
    """Parse source arguments and source-intake flags for ``gpd:ideate``."""

    tokens = _argument_tokens(arguments)
    source_tokens: list[str] = []
    warnings: list[str] = []
    max_papers: int | None = None

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--max-papers":
            max_papers, index = _consume_positive_int_flag(tokens, index, "--max-papers", warnings=warnings)
            continue
        if token.startswith("--max-papers="):
            max_papers = _parse_positive_int_value(token.split("=", 1)[1], "--max-papers", warnings)
            index += 1
            continue
        source_tokens.append(token)
        index += 1

    return IdeateArgumentContext(
        raw_arguments=tuple(tokens),
        source_inputs=_combine_plain_topic_tokens(source_tokens),
        max_papers=max_papers,
        warnings=tuple(warnings),
    )


def normalize_ideate_sources(
    raw_inputs: Sequence[str],
    *,
    workspace_root: Path | str,
    max_papers: int | None = None,
) -> IdeateSourceManifest:
    """Normalize mixed ideation inputs into a side-effect-free source manifest."""

    root = Path(workspace_root).expanduser().resolve(strict=False)
    inputs = tuple(str(item).strip() for item in raw_inputs if str(item).strip())
    if not inputs:
        return IdeateSourceManifest(
            sources=(),
            topic=None,
            warnings=("No source inputs were supplied; source-grounded ideation requires papers or knowledge docs.",),
        )

    limit = _normalize_max_papers(max_papers)
    manifest_warnings: list[str] = []
    if max_papers is not None and limit is None:
        manifest_warnings.append(f"--max-papers must be a positive integer, got {max_papers!r}; ignoring it.")

    kdoc_index = _build_kdoc_index(root)
    records: list[IdeateSourceRecord] = []
    seen_keys: dict[str, int] = {}
    topic: str | None = None

    for raw in inputs:
        normalized = _normalize_one_input(raw, root=root, max_papers=limit, kdoc_index=kdoc_index)
        manifest_warnings.extend(normalized.warnings)
        for record in normalized.records:
            key = _dedupe_key(record)
            existing_index = seen_keys.get(key)
            if existing_index is not None:
                warning = f"Duplicate ideate source skipped: {record.input}"
                manifest_warnings.append(warning)
                records[existing_index] = _with_warnings(records[existing_index], (warning,))
                continue
            seen_keys[key] = len(records)
            records.append(record)
            if record.kind == "topic" and topic is None:
                topic = record.normalized_ref

    return IdeateSourceManifest(
        sources=tuple(_with_source_id(record, index + 1) for index, record in enumerate(records)),
        topic=topic,
        warnings=tuple(manifest_warnings),
    )


def _argument_tokens(arguments: str | Sequence[str] | None) -> tuple[str, ...]:
    if arguments is None:
        return ()
    if isinstance(arguments, str):
        try:
            return tuple(shlex.split(arguments))
        except ValueError:
            return tuple(part for part in arguments.split() if part)
    if len(arguments) == 1 and isinstance(arguments[0], str) and " " in arguments[0]:
        return _argument_tokens(arguments[0])
    return tuple(str(item) for item in arguments)


def _consume_positive_int_flag(
    tokens: Sequence[str],
    index: int,
    flag: str,
    *,
    warnings: list[str],
) -> tuple[int | None, int]:
    if index + 1 >= len(tokens):
        warnings.append(f"{flag} expected a positive integer; ignoring it.")
        return None, index + 1
    return _parse_positive_int_value(tokens[index + 1], flag, warnings), index + 2


def _parse_positive_int_value(value: str, flag: str, warnings: list[str]) -> int | None:
    try:
        parsed = int(value)
    except ValueError:
        warnings.append(f"{flag} expected a positive integer, got {value!r}; ignoring it.")
        return None
    if parsed < 1:
        warnings.append(f"{flag} expected a positive integer, got {value!r}; ignoring it.")
        return None
    return parsed


def _combine_plain_topic_tokens(tokens: Sequence[str]) -> tuple[str, ...]:
    combined: list[str] = []
    topic_parts: list[str] = []

    def flush_topic() -> None:
        if topic_parts:
            combined.append(" ".join(topic_parts))
            topic_parts.clear()

    for token in tokens:
        if _looks_like_topic_token(token):
            topic_parts.append(token)
            continue
        flush_topic()
        combined.append(token)
    flush_topic()
    return tuple(combined)


def _looks_like_topic_token(token: str) -> bool:
    if not token or token.startswith("--"):
        return False
    if _try_normalize_arxiv_id(token) is not None:
        return False
    suffix = Path(token).suffix.lower()
    if suffix in _SUPPORTED_PAPER_SUFFIXES or suffix == ".md":
        return False
    return not _looks_like_path_token(token)


def _normalize_max_papers(max_papers: int | None) -> int | None:
    if max_papers is None or isinstance(max_papers, bool) or max_papers < 1:
        return None
    return max_papers


def _normalize_one_input(
    raw: str,
    *,
    root: Path,
    max_papers: int | None,
    kdoc_index: _KdocIndex,
) -> _NormalizedInput:
    arxiv_id = _try_normalize_arxiv_id(raw)
    if arxiv_id is not None:
        digest_path = _match_kdoc_for_arxiv(arxiv_id, kdoc_index) or ""
        return _NormalizedInput(
            records=(
                IdeateSourceRecord(
                    source_id="",
                    kind="arxiv",
                    input=raw,
                    normalized_ref=arxiv_id,
                    status="reused" if digest_path else "pending",
                    digest_path=digest_path,
                ),
            ),
        )

    candidate_path = _resolve_input_path(raw, root)
    if candidate_path.exists() and candidate_path.is_dir():
        return _normalize_directory(raw, candidate_path, root=root, max_papers=max_papers, kdoc_index=kdoc_index)

    suffix = candidate_path.suffix.lower()
    if suffix in _SUPPORTED_PAPER_SUFFIXES:
        return _NormalizedInput(
            records=(_normalize_paper_path(raw, candidate_path, suffix=suffix, root=root, kdoc_index=kdoc_index),)
        )
    if suffix == ".md":
        return _NormalizedInput(records=(_normalize_markdown_path(raw, candidate_path, root=root),))
    if candidate_path.exists() and candidate_path.is_file():
        return _NormalizedInput(
            records=(
                IdeateSourceRecord(
                    source_id="",
                    kind="blocked",
                    input=raw,
                    normalized_ref=_relative_posix(candidate_path, root),
                    status="blocked",
                    warnings=(f"Unsupported ideate source file type: {raw}",),
                ),
            ),
        )
    if _looks_like_path_token(raw):
        return _NormalizedInput(
            records=(
                IdeateSourceRecord(
                    source_id="",
                    kind="blocked",
                    input=raw,
                    normalized_ref=raw,
                    status="blocked",
                    warnings=(f"Ideate source path does not exist: {raw}",),
                ),
            ),
        )
    return _NormalizedInput(
        records=(
            IdeateSourceRecord(
                source_id="",
                kind="topic",
                input=raw,
                normalized_ref=raw,
                status="blocked",
                warnings=("Topic-only ideation cannot make source-grounded claims until sources are supplied.",),
            ),
        ),
    )


def _normalize_directory(
    raw: str,
    directory: Path,
    *,
    root: Path,
    max_papers: int | None,
    kdoc_index: _KdocIndex,
) -> _NormalizedInput:
    scan = _scan_directory_sources(directory, root=root, max_papers=max_papers)
    if not scan.selected:
        return _NormalizedInput(
            records=(
                IdeateSourceRecord(
                    source_id="",
                    kind="blocked",
                    input=raw,
                    normalized_ref=_relative_posix(directory, root),
                    status="blocked",
                    warnings=("Directory contains no supported .tex or .pdf paper sources.", *scan.warnings),
                ),
            ),
            warnings=scan.warnings,
        )

    records = [
        _normalize_paper_path(
            _relative_posix(path, root),
            path,
            suffix=path.suffix.lower(),
            root=root,
            kdoc_index=kdoc_index,
            kind="directory_item",
        )
        for path in scan.selected
    ]
    if scan.warnings:
        records[0] = _with_warnings(records[0], scan.warnings)
    return _NormalizedInput(records=tuple(records), warnings=scan.warnings)


def _scan_directory_sources(directory: Path, *, root: Path, max_papers: int | None) -> _DirectoryScan:
    paper_candidates = [
        path
        for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        if path.is_file()
        and not path.name.startswith(".")
        and path.name.lower() not in _IGNORED_DIRECTORY_FILENAMES
        and path.suffix.lower() in _SUPPORTED_PAPER_SUFFIXES
    ]

    warnings: list[str] = []
    by_stem: dict[str, Path] = {}
    for path in paper_candidates:
        key = _paper_group_key(path)
        existing = by_stem.get(key)
        if existing is None:
            by_stem[key] = path
            continue
        if existing.suffix.lower() == ".pdf" and path.suffix.lower() == ".tex":
            by_stem[key] = path
            warnings.append(
                f"Skipped {_relative_posix(existing, root)} because {_relative_posix(path, root)} has the same stem "
                "and .tex is preferred."
            )
            continue
        warnings.append(
            f"Skipped {_relative_posix(path, root)} because {_relative_posix(existing, root)} has the same stem."
        )

    selected = tuple(path for _key, path in sorted(by_stem.items(), key=lambda item: item[1].name.casefold()))
    if max_papers is None or len(selected) <= max_papers:
        return _DirectoryScan(selected=selected, warnings=tuple(warnings))

    kept = selected[:max_papers]
    for path in selected[max_papers:]:
        warnings.append(f"Skipped {_relative_posix(path, root)} because --max-papers {max_papers} was reached.")
    return _DirectoryScan(selected=kept, warnings=tuple(warnings))


def _normalize_paper_path(
    raw: str,
    path: Path,
    *,
    suffix: str,
    root: Path,
    kdoc_index: _KdocIndex,
    kind: IdeateSourceKind | None = None,
) -> IdeateSourceRecord:
    paper_kind: IdeateSourceKind = "pdf" if suffix == ".pdf" else "tex"
    record_kind = kind or paper_kind
    normalized_ref = _relative_posix(path, root)
    arxiv_id = _try_normalize_arxiv_id(path.stem)
    digest_path = _match_kdoc_for_path(path, root, kdoc_index) or (
        _match_kdoc_for_arxiv(arxiv_id, kdoc_index) if arxiv_id is not None else ""
    )
    if not path.exists():
        return IdeateSourceRecord(
            source_id="",
            kind=paper_kind,
            input=raw,
            normalized_ref=normalized_ref,
            status="blocked",
            warnings=(f"{paper_kind.upper()} source does not exist: {raw}",),
        )
    return IdeateSourceRecord(
        source_id="",
        kind=record_kind,
        input=raw,
        normalized_ref=normalized_ref,
        status="reused" if digest_path else "pending",
        digest_path=digest_path or "",
    )


def _normalize_markdown_path(raw: str, path: Path, *, root: Path) -> IdeateSourceRecord:
    normalized_ref = _relative_posix(path, root)
    if not path.exists():
        return IdeateSourceRecord(
            source_id="",
            kind="knowledge_doc" if _looks_like_knowledge_doc_ref(path, root) else "blocked",
            input=raw,
            normalized_ref=normalized_ref,
            status="blocked",
            warnings=(f"Knowledge document does not exist: {raw}",),
        )
    if _is_knowledge_doc_path(path, root):
        return IdeateSourceRecord(
            source_id="",
            kind="knowledge_doc",
            input=raw,
            normalized_ref=normalized_ref,
            status="reused",
            digest_path=normalized_ref,
        )
    return IdeateSourceRecord(
        source_id="",
        kind="blocked",
        input=raw,
        normalized_ref=normalized_ref,
        status="blocked",
        warnings=(f"Markdown source is not an existing GPD knowledge document: {raw}",),
    )


def _build_kdoc_index(root: Path) -> _KdocIndex:
    by_arxiv: dict[str, str] = {}
    by_path_key: dict[str, str] = {}
    knowledge_dir = root / PLANNING_DIR_NAME / KNOWLEDGE_DIR_NAME
    if not knowledge_dir.is_dir():
        return _KdocIndex(by_arxiv=by_arxiv, by_path_key=by_path_key)

    for path in sorted(knowledge_dir.glob("K-*.md")):
        rel = _relative_posix(path, root)
        by_path_key.setdefault(rel.casefold(), rel)
        by_path_key.setdefault(path.name.casefold(), rel)
        try:
            meta, _body = extract_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, FrontmatterParseError):
            continue
        for value in _knowledge_source_values(meta.get("sources")):
            for arxiv_id in _arxiv_ids_from_text(value):
                by_arxiv.setdefault(arxiv_id.casefold(), rel)
                by_arxiv.setdefault(_versionless_arxiv_id(arxiv_id).casefold(), rel)
            for path_key in _path_keys_from_text(value):
                by_path_key.setdefault(path_key, rel)
    return _KdocIndex(by_arxiv=by_arxiv, by_path_key=by_path_key)


def _knowledge_source_values(value: object) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        values.extend(_source_record_values(value))
    elif isinstance(value, Sequence):
        for item in value:
            if isinstance(item, dict):
                values.extend(_source_record_values(item))
            elif isinstance(item, str):
                values.append(item)
    return tuple(item.strip() for item in values if item.strip())


def _source_record_values(record: dict[object, object]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("arxiv_id", "url", "locator", "reference_id"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    artifacts = record.get("source_artifacts")
    if isinstance(artifacts, Sequence) and not isinstance(artifacts, str):
        values.extend(str(item) for item in artifacts if str(item).strip())
    return tuple(values)


def _arxiv_ids_from_text(value: str) -> tuple[str, ...]:
    ids: list[str] = []
    for token in (value, *_candidate_reference_tokens(value)):
        arxiv_id = _try_normalize_arxiv_id(token)
        if arxiv_id is not None and arxiv_id not in ids:
            ids.append(arxiv_id)
    return tuple(ids)


def _candidate_reference_tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token.strip().strip("'\"`.,;:()[]{}<>")
        for token in re.split(r"\s+", value)
        if token.strip().strip("'\"`.,;:()[]{}<>")
    )


def _path_keys_from_text(value: str) -> tuple[str, ...]:
    keys: list[str] = []
    for token in _candidate_reference_tokens(value):
        suffix = Path(token).suffix.lower()
        if suffix in _SUPPORTED_PAPER_SUFFIXES:
            keys.extend(_path_keys(token))
    return tuple(dict.fromkeys(keys))


def _match_kdoc_for_arxiv(arxiv_id: str, index: _KdocIndex) -> str:
    return index.by_arxiv.get(arxiv_id.casefold()) or index.by_arxiv.get(_versionless_arxiv_id(arxiv_id).casefold(), "")


def _match_kdoc_for_path(path: Path, root: Path, index: _KdocIndex) -> str:
    for key in _path_keys(_relative_posix(path, root)):
        match = index.by_path_key.get(key)
        if match:
            return match
    return ""


def _paper_group_key(path: Path) -> str:
    arxiv_id = _try_normalize_arxiv_id(path.stem)
    return arxiv_id.casefold() if arxiv_id is not None else path.stem.casefold()


def _path_keys(value: str) -> tuple[str, ...]:
    normalized = value.replace("\\", "/").strip()
    path = Path(normalized)
    keys = [normalized.casefold(), path.name.casefold()]
    if path.stem:
        keys.append(path.stem.casefold())
    return tuple(dict.fromkeys(keys))


def _dedupe_key(record: IdeateSourceRecord) -> str:
    if record.digest_path:
        return f"digest:{record.digest_path.casefold()}"
    if record.kind == "arxiv":
        return f"arxiv:{record.normalized_ref.casefold()}"
    if record.kind in {"pdf", "tex", "directory_item"}:
        arxiv_id = _try_normalize_arxiv_id(Path(record.normalized_ref).stem)
        if arxiv_id is not None:
            return f"arxiv:{arxiv_id.casefold()}"
        return f"path:{record.normalized_ref.casefold()}"
    return f"{record.kind}:{record.normalized_ref.casefold()}"


def _with_source_id(record: IdeateSourceRecord, index: int) -> IdeateSourceRecord:
    return IdeateSourceRecord(
        source_id=f"SRC-{index:03d}",
        kind=record.kind,
        input=record.input,
        normalized_ref=record.normalized_ref,
        status=record.status,
        digest_path=record.digest_path,
        warnings=record.warnings,
    )


def _with_warnings(record: IdeateSourceRecord, warnings: Sequence[str]) -> IdeateSourceRecord:
    merged = (*record.warnings, *(warning for warning in warnings if warning))
    return IdeateSourceRecord(
        source_id=record.source_id,
        kind=record.kind,
        input=record.input,
        normalized_ref=record.normalized_ref,
        status=record.status,
        digest_path=record.digest_path,
        warnings=tuple(dict.fromkeys(merged)),
    )


def _try_normalize_arxiv_id(value: str) -> str | None:
    try:
        return normalize_arxiv_id(value)
    except ValueError:
        return None


def _versionless_arxiv_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id, flags=re.IGNORECASE)


def _resolve_input_path(raw: str, root: Path) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else root / path


def _relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _looks_like_path_token(token: str) -> bool:
    if token.startswith(("./", "../", "~/", "/", "@")):
        return True
    return "/" in token or "\\" in token


def _looks_like_knowledge_doc_ref(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return (
        len(relative.parts) == 3
        and relative.parts[0] == PLANNING_DIR_NAME
        and relative.parts[1] == KNOWLEDGE_DIR_NAME
        and relative.name.startswith("K-")
        and relative.suffix.lower() == ".md"
    )


def _is_knowledge_doc_path(path: Path, root: Path) -> bool:
    return path.is_file() and _looks_like_knowledge_doc_ref(path, root)

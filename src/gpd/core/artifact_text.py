"""Shared text-surface helpers for manuscript and source-file artifacts."""

from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

SurfaceKind = Literal["native", "companion", "generated"]

TEXT_LIKE_ARTIFACT_SUFFIXES: frozenset[str] = frozenset(
    {
        ".bib",
        ".csv",
        ".ipynb",
        ".json",
        ".markdown",
        ".md",
        ".py",
        ".rst",
        ".tex",
        ".tsv",
        ".txt",
        ".yaml",
        ".yml",
    }
)
OOXML_DOCUMENT_SUFFIXES: frozenset[str] = frozenset({".docx"})
OOXML_SPREADSHEET_SUFFIXES: frozenset[str] = frozenset({".xlsx", ".xlsm"})
PEER_REVIEW_ARTIFACT_SUFFIXES: frozenset[str] = frozenset(
    {
        ".csv",
        ".docx",
        ".xlsm",
        ".md",
        ".pdf",
        ".tex",
        ".tsv",
        ".txt",
        ".xlsx",
    }
)
DIGEST_KNOWLEDGE_SOURCE_SUFFIXES: frozenset[str] = frozenset(
    {
        *TEXT_LIKE_ARTIFACT_SUFFIXES,
        ".docx",
        ".pdf",
        ".xlsm",
        ".xlsx",
    }
)

_WORDPROCESSING_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_SPREADSHEET_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_SPREADSHEET_REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
_OFFICEDOC_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


__all__ = [
    "ArtifactTextError",
    "ArtifactTextMaterialization",
    "ArtifactTextProbe",
    "ArtifactTextSurface",
    "DIGEST_KNOWLEDGE_SOURCE_SUFFIXES",
    "OOXML_DOCUMENT_SUFFIXES",
    "OOXML_SPREADSHEET_SUFFIXES",
    "PEER_REVIEW_ARTIFACT_SUFFIXES",
    "TEXT_LIKE_ARTIFACT_SUFFIXES",
    "load_artifact_text_surface",
    "materialize_artifact_text_surface",
    "probe_artifact_text_surface",
]


class ArtifactTextError(ValueError):
    """Raised when an artifact cannot be converted into readable text."""


@dataclass(frozen=True, slots=True)
class ArtifactTextProbe:
    """Readiness status for one artifact text surface."""

    ready: bool
    detail: str
    surface_kind: SurfaceKind | None = None
    surface_path: Path | None = None
    helper_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ArtifactTextSurface:
    """In-memory text surface for one artifact."""

    source_path: Path
    text: str
    detail: str
    surface_kind: SurfaceKind


@dataclass(frozen=True, slots=True)
class ArtifactTextMaterialization:
    """Materialized text-surface file for one artifact."""

    source_path: Path
    output_path: Path
    detail: str
    surface_kind: SurfaceKind
    text_length: int


def _decode_text_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _read_text_like_artifact(path: Path) -> str:
    try:
        return _decode_text_bytes(path.read_bytes())
    except OSError as exc:
        raise ArtifactTextError(str(exc)) from exc


def _pdf_companion_text(path: Path) -> Path | None:
    companion = path.with_suffix(".txt")
    return companion if companion.exists() and companion.is_file() else None


def _pypdf_available() -> bool:
    """Return True when pypdf can be imported."""
    try:
        import pypdf  # noqa: F401

        return True
    except ImportError:
        return False


def _normalize_zip_target(base_name: str, target: str) -> str:
    normalized = posixpath.normpath(posixpath.join(posixpath.dirname(base_name), target))
    return normalized.removeprefix("./")


def _load_ooxml_xml(archive: zipfile.ZipFile, member_name: str, *, invalid_detail: str) -> ET.Element:
    try:
        payload = archive.read(member_name)
    except KeyError as exc:
        raise ArtifactTextError(invalid_detail) from exc
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ArtifactTextError(invalid_detail) from exc


def _read_docx_text(path: Path) -> str:
    invalid_detail = "DOCX review target is not a valid OOXML document"
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                raise ArtifactTextError("DOCX review target is missing word/document.xml")
            document_members = ["word/document.xml"] + sorted(
                name
                for name in names
                if name.startswith("word/") and name.rsplit("/", 1)[-1].startswith(("header", "footer"))
            )
            paragraphs: list[str] = []
            for member_name in document_members:
                root = _load_ooxml_xml(archive, member_name, invalid_detail=invalid_detail)
                for paragraph in root.findall(".//w:p", _WORDPROCESSING_NS):
                    fragments: list[str] = []
                    for node in paragraph.iter():
                        tag = node.tag.rsplit("}", 1)[-1]
                        if tag in {"t", "instrText"} and node.text:
                            fragments.append(node.text)
                        elif tag == "tab":
                            fragments.append("\t")
                        elif tag in {"br", "cr"}:
                            fragments.append("\n")
                    paragraph_text = "".join(fragments).strip()
                    if paragraph_text:
                        paragraphs.append(paragraph_text)
    except zipfile.BadZipFile as exc:
        raise ArtifactTextError(invalid_detail) from exc
    except OSError as exc:
        raise ArtifactTextError(str(exc)) from exc
    return "\n\n".join(paragraphs).strip()


def _xlsx_string_item_text(item: ET.Element | None) -> str:
    if item is None:
        return ""
    return "".join(node.text or "" for node in item.findall(".//main:t", _SPREADSHEET_NS)).strip()


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _load_ooxml_xml(
        archive,
        "xl/sharedStrings.xml",
        invalid_detail="XLSX review target has invalid xl/sharedStrings.xml",
    )
    return [_xlsx_string_item_text(item) for item in root.findall("main:si", _SPREADSHEET_NS)]


def _xlsx_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook_root = _load_ooxml_xml(
        archive,
        "xl/workbook.xml",
        invalid_detail="XLSX review target is missing or has invalid xl/workbook.xml",
    )
    rels_root = _load_ooxml_xml(
        archive,
        "xl/_rels/workbook.xml.rels",
        invalid_detail="XLSX review target is missing or has invalid xl/_rels/workbook.xml.rels",
    )
    relationships = {
        rel.attrib.get("Id", ""): _normalize_zip_target("xl/workbook.xml", rel.attrib.get("Target", ""))
        for rel in rels_root.findall("rel:Relationship", _SPREADSHEET_REL_NS)
        if rel.attrib.get("Id") and rel.attrib.get("Target")
    }
    targets: list[tuple[str, str]] = []
    for sheet in workbook_root.findall("main:sheets/main:sheet", _SPREADSHEET_NS):
        name = sheet.attrib.get("name", "").strip() or "Sheet"
        rel_id = sheet.attrib.get(_OFFICEDOC_REL_ID, "").strip()
        target = relationships.get(rel_id)
        if target:
            targets.append((name, target))
    if not targets:
        raise ArtifactTextError("XLSX review target does not declare any readable worksheets")
    return targets


def _xlsx_cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t", "n")
    if cell_type == "inlineStr":
        return _xlsx_string_item_text(cell.find("main:is", _SPREADSHEET_NS))
    value_node = cell.find("main:v", _SPREADSHEET_NS)
    raw_value = (value_node.text or "").strip() if value_node is not None and value_node.text is not None else ""
    if not raw_value:
        formula_node = cell.find("main:f", _SPREADSHEET_NS)
        return f"={formula_node.text.strip()}" if formula_node is not None and formula_node.text else ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (IndexError, ValueError):
            return raw_value
    if cell_type == "b":
        return "TRUE" if raw_value == "1" else "FALSE"
    return raw_value


def _read_xlsx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _xlsx_shared_strings(archive)
            lines: list[str] = []
            for sheet_name, member_name in _xlsx_sheet_targets(archive):
                sheet_root = _load_ooxml_xml(
                    archive,
                    member_name,
                    invalid_detail=f"XLSX review target is missing or has invalid {member_name}",
                )
                lines.append(f"# Sheet: {sheet_name}")
                for row in sheet_root.findall("main:sheetData/main:row", _SPREADSHEET_NS):
                    values = [_xlsx_cell_text(cell, shared_strings) for cell in row.findall("main:c", _SPREADSHEET_NS)]
                    row_text = "\t".join(value for value in values if value)
                    if row_text:
                        lines.append(row_text)
                lines.append("")
    except zipfile.BadZipFile as exc:
        raise ArtifactTextError("XLSX review target is not a valid OOXML spreadsheet") from exc
    except OSError as exc:
        raise ArtifactTextError(str(exc)) from exc
    return "\n".join(lines).strip()


def _extract_pdf_text(path: Path) -> str:
    companion = _pdf_companion_text(path)
    if companion is not None:
        return _read_text_like_artifact(companion)
    try:
        import pypdf
    except ImportError as exc:
        raise ArtifactTextError(
            "PDF text extraction requires pypdf. "
            "Install it with: pip install 'get-physics-done[arxiv]'"
        ) from exc
    try:
        reader = pypdf.PdfReader(str(path))
        text_parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(text_parts)
    except Exception as exc:
        raise ArtifactTextError(f"PDF text extraction failed: {exc}") from exc


def probe_artifact_text_surface(path: Path) -> ArtifactTextProbe:
    """Return whether *path* can be converted into a readable text surface."""

    suffix = path.suffix.lower()
    if suffix in TEXT_LIKE_ARTIFACT_SUFFIXES:
        detail_map = {
            ".csv": "CSV review target can be read directly as delimited text",
            ".tsv": "TSV review target can be read directly as delimited text",
        }
        detail = detail_map.get(suffix, "text review target can be read directly")
        return ArtifactTextProbe(ready=True, detail=detail, surface_kind="native")
    if suffix == ".pdf":
        companion = _pdf_companion_text(path)
        if companion is not None:
            return ArtifactTextProbe(
                ready=True,
                detail=f"PDF intake can use companion text file {companion.as_posix()}",
                surface_kind="companion",
                surface_path=companion,
            )
        if _pypdf_available():
            return ArtifactTextProbe(
                ready=True,
                detail="pypdf available for PDF review intake",
                surface_kind="generated",
            )
        return ArtifactTextProbe(
            ready=False,
            detail=(
                "PDF text extraction requires pypdf. "
                "Install it with: pip install 'get-physics-done[arxiv]'"
            ),
        )
    if suffix in OOXML_DOCUMENT_SUFFIXES:
        _read_docx_text(path)
        return ArtifactTextProbe(
            ready=True,
            detail="DOCX review target can be converted using built-in OOXML text extraction",
            surface_kind="generated",
        )
    if suffix in OOXML_SPREADSHEET_SUFFIXES:
        _read_xlsx_text(path)
        return ArtifactTextProbe(
            ready=True,
            detail="XLSX review target can be converted using built-in OOXML spreadsheet extraction",
            surface_kind="generated",
        )
    return ArtifactTextProbe(ready=False, detail=f"unsupported artifact text surface for suffix `{suffix or '(none)'}`")


def load_artifact_text_surface(path: Path) -> ArtifactTextSurface:
    """Return the readable text surface for *path*."""

    suffix = path.suffix.lower()
    if suffix in TEXT_LIKE_ARTIFACT_SUFFIXES:
        return ArtifactTextSurface(
            source_path=path,
            text=_read_text_like_artifact(path),
            detail=probe_artifact_text_surface(path).detail,
            surface_kind="native",
        )
    if suffix == ".pdf":
        companion = _pdf_companion_text(path)
        if companion is not None:
            return ArtifactTextSurface(
                source_path=path,
                text=_read_text_like_artifact(companion),
                detail=f"PDF intake can use companion text file {companion.as_posix()}",
                surface_kind="companion",
            )
        return ArtifactTextSurface(
            source_path=path,
            text=_extract_pdf_text(path),
            detail="pypdf available for PDF review intake",
            surface_kind="generated",
        )
    if suffix in OOXML_DOCUMENT_SUFFIXES:
        return ArtifactTextSurface(
            source_path=path,
            text=_read_docx_text(path),
            detail="DOCX review target can be converted using built-in OOXML text extraction",
            surface_kind="generated",
        )
    if suffix in OOXML_SPREADSHEET_SUFFIXES:
        return ArtifactTextSurface(
            source_path=path,
            text=_read_xlsx_text(path),
            detail="XLSX review target can be converted using built-in OOXML spreadsheet extraction",
            surface_kind="generated",
        )
    raise ArtifactTextError(f"unsupported artifact text surface for suffix `{suffix or '(none)'}`")


def materialize_artifact_text_surface(source_path: Path, output_path: Path) -> ArtifactTextMaterialization:
    """Write the readable text surface for *source_path* into *output_path*."""

    surface = load_artifact_text_surface(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(surface.text, encoding="utf-8")
    return ArtifactTextMaterialization(
        source_path=source_path,
        output_path=output_path,
        detail=surface.detail,
        surface_kind=surface.surface_kind,
        text_length=len(surface.text),
    )

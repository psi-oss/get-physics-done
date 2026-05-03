"""Executable validation for managed arXiv submission packages."""

from __future__ import annotations

import dataclasses
import re
import tarfile
from pathlib import Path, PurePosixPath

from gpd.core.constants import ProjectLayout
from gpd.core.utils import normalize_ascii_slug

__all__ = [
    "ArxivPackageCheck",
    "ArxivPackageValidationResult",
    "validate_arxiv_package",
]

ARXIV_TARBALL_NAME = "arxiv-submission.tar.gz"
MAX_ARXIV_PACKAGE_BYTES = 50 * 1024 * 1024

_AUXILIARY_EXACT_NAMES = {
    "missfont.log",
}
_AUXILIARY_SUFFIXES = {
    ".aux",
    ".bbl-save-error",
    ".bcf",
    ".blg",
    ".dvi",
    ".fdb_latexmk",
    ".fls",
    ".lof",
    ".log",
    ".lot",
    ".out",
    ".run.xml",
    ".synctex",
    ".synctex.gz",
    ".toc",
}
_BIB_SOURCE_SUFFIXES = {".bib"}
_EMPTY_REFERENCE_RE = re.compile(r"\\(?:cite\w*|ref|eqref|autoref|cref|Cref)\s*(?:\[[^\]]*\])*\{\s*\}")
_CITATION_RE = re.compile(r"\\(?:cite\w*|parencite|textcite)\s*(?:\[[^\]]*\])*\{([^}]*)\}")
_BIBLIOGRAPHY_COMMAND_RE = re.compile(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\{")
_BBL_INPUT_RE = re.compile(r"\\(?:input|include)\s*\{[^}]*\.bbl\}")
_PLACEHOLDER_RE = re.compile(
    r"(?:RESULT\s+PENDING|PLACEHOLDER|TODO|FIXME|\\todo\s*\{|\\cite\w*\s*(?:\[[^\]]*\])*\{\s*MISSING:)",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True)
class ArxivPackageCheck:
    """One blocking arXiv package validation check."""

    name: str
    passed: bool
    blocking: bool
    detail: str


@dataclasses.dataclass(frozen=True)
class ArxivPackageValidationResult:
    """Validation result for one managed arXiv package root."""

    passed: bool
    project_root: str
    subject_slug: str
    package_root: str
    submission_dir: str
    tarball: str
    manuscript_entrypoint: str
    root_entrypoint: str
    materialized: bool
    checks: list[ArxivPackageCheck]
    submission_files: list[str]
    tarball_entries: list[str]


def _resolve_project_path(project_root: Path, path: str | Path | None, default: Path) -> Path:
    if path is None:
        candidate = default
    else:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
    return candidate.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(project_root.resolve(strict=False)).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _is_auxiliary_name(name: str) -> bool:
    lowered = PurePosixPath(name).name.lower()
    if lowered in _AUXILIARY_EXACT_NAMES:
        return True
    if lowered.endswith("~") or lowered.startswith(".#"):
        return True
    return any(lowered.endswith(suffix) for suffix in _AUXILIARY_SUFFIXES)


def _is_bib_source_name(name: str) -> bool:
    return any(PurePosixPath(name).name.lower().endswith(suffix) for suffix in _BIB_SOURCE_SUFFIXES)


def _strip_latex_comments(text: str) -> str:
    stripped_lines: list[str] = []
    for line in text.splitlines():
        comment_index = None
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            probe = index - 1
            while probe >= 0 and line[probe] == "\\":
                backslashes += 1
                probe -= 1
            if backslashes % 2 == 0:
                comment_index = index
                break
        stripped_lines.append(line if comment_index is None else line[:comment_index])
    return "\n".join(stripped_lines)


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _scan_tex_payload(
    *,
    root_entrypoint: str,
    tex_payloads: dict[str, str],
    packaged_names: set[str],
) -> list[str]:
    issues: list[str] = []
    normalized_payloads = {name: _strip_latex_comments(text) for name, text in tex_payloads.items()}
    for name, text in normalized_payloads.items():
        if _EMPTY_REFERENCE_RE.search(text):
            issues.append(f"{name} contains an empty citation or reference command")
        placeholder = _PLACEHOLDER_RE.search(text)
        if placeholder is not None:
            issues.append(f"{name} contains unresolved placeholder marker {placeholder.group(0)!r}")
        if _BIBLIOGRAPHY_COMMAND_RE.search(text):
            issues.append(f"{name} still contains bibliography commands; inline .bbl content or input a .bbl file")

    combined_text = "\n".join(normalized_payloads.values())
    citation_keys = [
        key.strip()
        for match in _CITATION_RE.finditer(combined_text)
        for key in match.group(1).split(",")
        if key.strip()
    ]
    has_bibliography_material = (
        "\\begin{thebibliography}" in combined_text
        or bool(_BBL_INPUT_RE.search(combined_text))
        or any(name.lower().endswith(".bbl") for name in packaged_names)
    )
    if citation_keys and not has_bibliography_material:
        issues.append(
            f"{root_entrypoint} has citation commands but no inlined thebibliography or packaged .bbl material"
        )
    return issues


def _submission_tree_payload(
    *,
    project_root: Path,
    submission_dir: Path,
) -> tuple[list[str], list[str], dict[str, str]]:
    file_names: list[str] = []
    issues: list[str] = []
    tex_payloads: dict[str, str] = {}
    for path in sorted(submission_dir.rglob("*")):
        display = _display_path(project_root, path)
        relative = path.relative_to(submission_dir).as_posix()
        if path.is_symlink():
            issues.append(f"{display} is a symlink; arXiv packages must not contain symlinks")
            continue
        if path.is_dir():
            continue
        file_names.append(relative)
        if _is_auxiliary_name(relative):
            issues.append(f"{relative} is a LaTeX auxiliary/editor artifact and must be excluded")
        if _is_bib_source_name(relative):
            issues.append(f"{relative} is a .bib source; package .bbl or inlined bibliography material instead")
        if path.suffix.lower() == ".tex":
            tex_payloads[relative] = _read_text_file(path)
    return file_names, issues, tex_payloads


def _tarball_payload(tarball: Path) -> tuple[list[str], list[str], dict[str, str]]:
    entries: list[str] = []
    issues: list[str] = []
    tex_payloads: dict[str, str] = {}
    try:
        with tarfile.open(tarball, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                name = member.name.replace("\\", "/")
                entries.append(name)
                pure = PurePosixPath(name)
                if name.startswith("/") or pure.is_absolute() or ".." in pure.parts or not name.strip():
                    issues.append(f"{name!r} is not a safe relative tarball entry")
                if member.issym() or member.islnk():
                    issues.append(f"{name} is a link entry; arXiv packages must not contain links")
                if member.isdir():
                    continue
                if _is_auxiliary_name(name):
                    issues.append(f"{name} is a LaTeX auxiliary/editor artifact and must be excluded")
                if _is_bib_source_name(name):
                    issues.append(f"{name} is a .bib source; package .bbl or inlined bibliography material instead")
                if PurePosixPath(name).suffix.lower() == ".tex":
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        issues.append(f"{name} could not be read from the tarball")
                    else:
                        tex_payloads[name] = extracted.read(member.size + 1).decode("utf-8", errors="replace")
    except (tarfile.TarError, OSError) as exc:
        issues.append(f"could not read tarball: {exc}")
    return entries, issues, tex_payloads


def _materialize_tarball(*, submission_dir: Path, tarball: Path) -> None:
    tarball.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "w:gz") as archive:
        for path in sorted(submission_dir.rglob("*")):
            if path.is_dir():
                continue
            archive.add(path, arcname=path.relative_to(submission_dir).as_posix(), recursive=False)


def validate_arxiv_package(
    *,
    project_root: Path,
    subject_slug: str,
    manuscript_entrypoint: str | Path,
    submission_dir: str | Path | None = None,
    tarball: str | Path | None = None,
    materialize: bool = False,
) -> ArxivPackageValidationResult:
    """Validate one managed arXiv package tree and tarball.

    This helper intentionally does not resolve manuscripts or review freshness.
    Callers must pass the strict review-preflight result into this boundary.
    """

    project_root = project_root.resolve(strict=False)
    subject_slug = subject_slug.strip()
    layout = ProjectLayout(project_root)
    package_root = layout.publication_arxiv_dir(subject_slug).resolve(strict=False)
    default_submission_dir = package_root / "submission"
    default_tarball = package_root / ARXIV_TARBALL_NAME
    submission_path = _resolve_project_path(project_root, submission_dir, default_submission_dir)
    tarball_path = _resolve_project_path(project_root, tarball, default_tarball)
    manuscript_path = _resolve_project_path(project_root, manuscript_entrypoint, project_root / manuscript_entrypoint)
    root_entrypoint = manuscript_path.name

    checks: list[ArxivPackageCheck] = []

    def add_check(name: str, passed: bool, detail: str) -> None:
        checks.append(ArxivPackageCheck(name=name, passed=passed, blocking=True, detail=detail))

    managed_root_valid = (
        bool(subject_slug)
        and normalize_ascii_slug(subject_slug) == subject_slug
        and _is_relative_to(package_root, layout.publication_dir)
    )
    add_check(
        "managed_arxiv_root",
        managed_root_valid,
        (
            f"package root is {_display_path(project_root, package_root)}"
            if managed_root_valid
            else (
                "publication subject slug must be a non-empty lowercase kebab-case slug "
                "that stays under the managed GPD publication root"
            )
        ),
    )
    submission_under_root = _is_relative_to(submission_path, package_root)
    add_check(
        "submission_dir_under_managed_arxiv_root",
        submission_under_root,
        (
            f"{_display_path(project_root, submission_path)} is under {_display_path(project_root, package_root)}"
            if submission_under_root
            else (
                f"{_display_path(project_root, submission_path)} escapes managed arXiv root "
                f"{_display_path(project_root, package_root)}"
            )
        ),
    )
    tarball_under_root = _is_relative_to(tarball_path, package_root)
    add_check(
        "tarball_under_managed_arxiv_root",
        tarball_under_root,
        (
            f"{_display_path(project_root, tarball_path)} is under {_display_path(project_root, package_root)}"
            if tarball_under_root
            else (
                f"{_display_path(project_root, tarball_path)} escapes managed arXiv root "
                f"{_display_path(project_root, package_root)}"
            )
        ),
    )
    add_check(
        "tarball_name",
        tarball_path.name == ARXIV_TARBALL_NAME,
        (
            f"tarball filename is {ARXIV_TARBALL_NAME}"
            if tarball_path.name == ARXIV_TARBALL_NAME
            else f"expected tarball filename {ARXIV_TARBALL_NAME}, got {tarball_path.name}"
        ),
    )

    submission_files: list[str] = []
    submission_tex_payloads: dict[str, str] = {}
    submission_ready_for_materialize = False
    if not submission_path.exists():
        add_check(
            "submission_dir_exists",
            False,
            f"missing submission tree {_display_path(project_root, submission_path)}",
        )
    elif not submission_path.is_dir():
        add_check(
            "submission_dir_exists",
            False,
            f"submission path must be a directory: {_display_path(project_root, submission_path)}",
        )
    else:
        add_check("submission_dir_exists", True, f"{_display_path(project_root, submission_path)} exists")
        submission_files, submission_issues, submission_tex_payloads = _submission_tree_payload(
            project_root=project_root,
            submission_dir=submission_path,
        )
        add_check(
            "submission_entrypoint_at_root",
            root_entrypoint in submission_files,
            (
                f"{root_entrypoint} is present at the submission tree root"
                if root_entrypoint in submission_files
                else f"missing root-level submission entrypoint {root_entrypoint}"
            ),
        )
        add_check(
            "submission_tree_excludes_auxiliary_files",
            not submission_issues,
            "submission tree contains only packageable files"
            if not submission_issues
            else "; ".join(submission_issues[:5]),
        )
        tex_issues = _scan_tex_payload(
            root_entrypoint=root_entrypoint,
            tex_payloads=submission_tex_payloads,
            packaged_names=set(submission_files),
        )
        add_check(
            "submission_tex_ready",
            not tex_issues,
            "submission TeX files have no unresolved placeholders, empty refs, or bibliography-command residue"
            if not tex_issues
            else "; ".join(tex_issues[:5]),
        )
        submission_ready_for_materialize = (
            root_entrypoint in submission_files and not submission_issues and not tex_issues
        )

    materialized = False
    if materialize:
        if (
            submission_ready_for_materialize
            and submission_under_root
            and tarball_under_root
            and tarball_path.name == ARXIV_TARBALL_NAME
        ):
            try:
                _materialize_tarball(submission_dir=submission_path, tarball=tarball_path)
            except OSError as exc:
                add_check("tarball_materialized", False, f"could not materialize tarball: {exc}")
            else:
                materialized = True
                add_check(
                    "tarball_materialized",
                    True,
                    f"materialized {_display_path(project_root, tarball_path)} from submission tree",
                )
        else:
            add_check(
                "tarball_materialized",
                False,
                "submission tree and managed tarball path must pass before materialization",
            )

    tarball_entries: list[str] = []
    if not tarball_path.exists():
        add_check("tarball_exists", False, f"missing tarball {_display_path(project_root, tarball_path)}")
    elif not tarball_path.is_file():
        add_check("tarball_exists", False, f"tarball path must be a file: {_display_path(project_root, tarball_path)}")
    else:
        add_check("tarball_exists", True, f"{_display_path(project_root, tarball_path)} exists")
        size = tarball_path.stat().st_size
        add_check(
            "tarball_size",
            size <= MAX_ARXIV_PACKAGE_BYTES,
            (
                f"tarball size {size} bytes is within the {MAX_ARXIV_PACKAGE_BYTES} byte limit"
                if size <= MAX_ARXIV_PACKAGE_BYTES
                else f"tarball size {size} bytes exceeds the {MAX_ARXIV_PACKAGE_BYTES} byte limit"
            ),
        )
        tarball_entries, tarball_issues, tarball_tex_payloads = _tarball_payload(tarball_path)
        add_check(
            "tarball_entries_safe",
            not tarball_issues,
            "tarball entries are safe relative package files" if not tarball_issues else "; ".join(tarball_issues[:5]),
        )
        add_check(
            "tarball_entrypoint_at_root",
            root_entrypoint in tarball_entries,
            (
                f"{root_entrypoint} is present at the tarball root"
                if root_entrypoint in tarball_entries
                else f"missing root-level tarball entrypoint {root_entrypoint}"
            ),
        )
        tarball_tex_issues = _scan_tex_payload(
            root_entrypoint=root_entrypoint,
            tex_payloads=tarball_tex_payloads,
            packaged_names=set(tarball_entries),
        )
        add_check(
            "tarball_tex_ready",
            not tarball_tex_issues,
            "tarball TeX files have no unresolved placeholders, empty refs, or bibliography-command residue"
            if not tarball_tex_issues
            else "; ".join(tarball_tex_issues[:5]),
        )

    passed = all(check.passed or not check.blocking for check in checks)
    return ArxivPackageValidationResult(
        passed=passed,
        project_root=project_root.as_posix(),
        subject_slug=subject_slug,
        package_root=_display_path(project_root, package_root),
        submission_dir=_display_path(project_root, submission_path),
        tarball=_display_path(project_root, tarball_path),
        manuscript_entrypoint=_display_path(project_root, manuscript_path),
        root_entrypoint=root_entrypoint,
        materialized=materialized,
        checks=checks,
        submission_files=submission_files,
        tarball_entries=tarball_entries,
    )

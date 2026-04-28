"""Helpers for the repository's manual release workflows.

The GitHub workflow files are the operational docs for the admin-owned release
process. This module keeps the version/changelog mutations out of YAML so the
release logic stays testable and the set of updated public files remains
centralized in one place.

`prepare` updates reviewable release content, while `stamp-publish-date` is
reserved for the actual publish workflow once the real release day is known.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


class ReleaseError(RuntimeError):
    """Raised when release inputs or tracked release surfaces are invalid."""


@dataclass(frozen=True)
class ReleaseMetadata:
    previous_version: str
    version: str
    bump: str
    release_branch: str
    release_notes: str


@dataclass(frozen=True)
class PublishDateMetadata:
    release_date: str
    release_year: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class PypiProbeResult:
    status: str
    message: str | None = None


DEFAULT_PYPI_PACKAGE_NAME = "get-physics-done"
PYPI_VERSION_PUBLISHED = "published"
PYPI_VERSION_NOT_PUBLISHED = "not-published"
PYPI_VERSION_UNKNOWN = "unknown"
PYPI_STATUS_ALREADY_PUBLISHED = "already-published"
PYPI_STATUS_RECOVERED = "recovered"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _replace_once(
    text: str,
    pattern: str,
    replacement: str,
    *,
    description: str,
    flags: int = 0,
) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise ReleaseError(f"Could not update {description}.")
    return updated


def current_release_date() -> str:
    return datetime.now(UTC).date().isoformat()


def _validate_release_date(release_date: str) -> str:
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", release_date):
            raise ValueError(release_date)
        datetime.strptime(release_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ReleaseError("Release date must use ISO format YYYY-MM-DD.") from exc
    return release_date


def _append_github_outputs(github_output: Path | None, outputs: dict[str, str]) -> None:
    if github_output is None:
        return
    with github_output.open("a", encoding="utf-8") as fh:
        for key, value in outputs.items():
            fh.write(f"{key}={value}\n")


def _pypi_version_json_url(package_name: str, version: str) -> str:
    encoded_package = urllib.parse.quote(package_name, safe="")
    encoded_version = urllib.parse.quote(version, safe="")
    return f"https://pypi.org/pypi/{encoded_package}/{encoded_version}/json"


def probe_pypi_version(package_name: str, version: str, *, timeout: float = 20.0) -> PypiProbeResult:
    """Return whether a specific PyPI project version is visible."""

    url = _pypi_version_json_url(package_name, version)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status == 200:
                return PypiProbeResult(PYPI_VERSION_PUBLISHED)
            return PypiProbeResult(
                PYPI_VERSION_UNKNOWN,
                f"PyPI version check returned HTTP {response.status}",
            )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return PypiProbeResult(PYPI_VERSION_NOT_PUBLISHED)
        return PypiProbeResult(PYPI_VERSION_UNKNOWN, f"PyPI version check returned HTTP {exc.code}")
    except Exception as exc:
        return PypiProbeResult(PYPI_VERSION_UNKNOWN, f"PyPI version check failed: {exc}")


def record_pypi_preflight_status(
    package_name: str,
    version: str,
    *,
    github_output: Path | None = None,
) -> str:
    probe = probe_pypi_version(package_name, version)
    if probe.status == PYPI_VERSION_PUBLISHED:
        status = PYPI_STATUS_ALREADY_PUBLISHED
        print(f"::notice::{package_name} {version} is already published on PyPI; skipping PyPI publish.")
    else:
        status = PYPI_VERSION_NOT_PUBLISHED
        if probe.status == PYPI_VERSION_UNKNOWN:
            if probe.message:
                print(probe.message, file=sys.stderr)
            print(
                f"::warning::Could not determine whether {package_name} {version} is already on PyPI; "
                "attempting trusted publish."
            )

    _append_github_outputs(github_output, {"status": status})
    return status


def record_pypi_publish_status(
    package_name: str,
    version: str,
    *,
    pre_publish_status: str,
    publish_outcome: str,
    github_output: Path | None = None,
) -> str:
    if pre_publish_status == PYPI_STATUS_ALREADY_PUBLISHED:
        status = PYPI_STATUS_ALREADY_PUBLISHED
    elif pre_publish_status != PYPI_VERSION_NOT_PUBLISHED:
        raise ReleaseError(f"Unsupported PyPI pre-publish status: {pre_publish_status!r}.")
    elif publish_outcome == "success":
        status = PYPI_VERSION_PUBLISHED
    else:
        probe = probe_pypi_version(package_name, version)
        if probe.status == PYPI_VERSION_PUBLISHED:
            print(f"::warning::PyPI publish failed, but {package_name} {version} is now published; continuing.")
            status = PYPI_STATUS_RECOVERED
        else:
            if probe.message:
                print(probe.message, file=sys.stderr)
            raise ReleaseError(f"PyPI publish did not complete and {package_name} {version} is not published.")

    _append_github_outputs(github_output, {"status": status})
    return status


def parse_current_version(pyproject_text: str) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', pyproject_text, re.M)
    if not match:
        raise ReleaseError("Could not parse version from pyproject.toml.")
    return match.group(1)


def bump_version(version: str, bump: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ReleaseError(f"Unsupported semantic version: {version!r}.")

    major, minor, patch = (int(part) for part in match.groups())
    if bump == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump == "minor":
        minor += 1
        patch = 0
    elif bump == "patch":
        patch += 1
    else:
        raise ReleaseError(f"Unsupported bump type: {bump!r}.")

    return f"{major}.{minor}.{patch}"


def update_changelog_text(changelog_text: str, new_version: str) -> tuple[str, str]:
    match = re.search(r"^## vNEXT\s*\n(.*?)(?=^## v|\Z)", changelog_text, re.M | re.S)
    if not match:
        raise ReleaseError("No ## vNEXT section found in CHANGELOG.md.")

    release_notes = match.group(1).strip()
    if not release_notes:
        raise ReleaseError("## vNEXT section in CHANGELOG.md is empty.")

    updated = (
        changelog_text[: match.start()]
        + f"## vNEXT\n\n## v{new_version}\n\n{release_notes}\n\n"
        + changelog_text[match.end() :]
    )
    return updated.rstrip() + "\n", release_notes


def extract_release_notes(changelog_text: str, version: str) -> str:
    headings = list(re.finditer(r"^## v(\S+)", changelog_text, re.M))
    for index, heading in enumerate(headings):
        if heading.group(1) != version:
            continue
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(changelog_text)
        return changelog_text[start:end].strip()
    raise ReleaseError(f"Could not find ## v{version} in CHANGELOG.md.")


def update_pyproject_text(pyproject_text: str, new_version: str) -> str:
    return _replace_once(
        pyproject_text,
        r'^(version\s*=\s*")[^"]+(")\s*$',
        rf"\g<1>{new_version}\g<2>",
        description="pyproject.toml version",
        flags=re.M,
    )


def update_package_json_text(package_json_text: str, new_version: str) -> str:
    try:
        package_json = json.loads(package_json_text)
    except json.JSONDecodeError as exc:
        raise ReleaseError("Could not parse package.json.") from exc

    if not isinstance(package_json, dict):
        raise ReleaseError("package.json must contain a JSON object.")

    for key in ("version", "gpdPythonVersion"):
        if key not in package_json:
            raise ReleaseError(f"Could not update package.json {key}.")
        package_json[key] = new_version

    return json.dumps(package_json, indent=2) + "\n"


def update_citation_version_text(citation_text: str, new_version: str) -> str:
    return _replace_once(
        citation_text,
        r"^version:\s*[^\n]+$",
        f"version: {new_version}",
        description="CITATION.cff version",
        flags=re.M,
    )


def update_citation_release_date_text(citation_text: str, release_date: str) -> str:
    return _replace_once(
        citation_text,
        r"^date-released:\s*'[^']+'$",
        f"date-released: '{release_date}'",
        description="CITATION.cff date-released",
        flags=re.M,
    )


def update_readme_version_text(readme_text: str, new_version: str) -> str:
    updated = _replace_once(
        readme_text,
        r"(^  version = \{)[^}]+(\},\s*$)",
        rf"\g<1>{new_version}\g<2>",
        description="README.md citation BibTeX version",
        flags=re.M,
    )
    return _replace_once(
        updated,
        r"Physical Superintelligence PBC \(\d{4}\)\. Get Physics Done \(GPD\) \(Version [^)]+\)\.",
        lambda match: re.sub(r"Version [^)]+", f"Version {new_version}", match.group(0)),
        description="README.md citation text version",
    )


def update_readme_release_year_text(readme_text: str, release_year: str) -> str:
    updated = _replace_once(
        readme_text,
        r"(^  year = \{)\d{4}(\},\s*$)",
        rf"\g<1>{release_year}\g<2>",
        description="README.md citation BibTeX year",
        flags=re.M,
    )
    return _replace_once(
        updated,
        r"Physical Superintelligence PBC \(\d{4}\)\. Get Physics Done \(GPD\) \(Version [^)]+\)\.",
        lambda match: re.sub(r"\(\d{4}\)", f"({release_year})", match.group(0), count=1),
        description="README.md citation text year",
    )


def prepare_release(repo_root: Path, bump: str) -> ReleaseMetadata:
    pyproject_path = repo_root / "pyproject.toml"
    package_json_path = repo_root / "package.json"
    changelog_path = repo_root / "CHANGELOG.md"
    citation_path = repo_root / "CITATION.cff"
    readme_path = repo_root / "README.md"

    pyproject_text = _read_text(pyproject_path)
    package_json_text = _read_text(package_json_path)
    changelog_text = _read_text(changelog_path)
    citation_text = _read_text(citation_path)
    readme_text = _read_text(readme_path)

    previous_version = parse_current_version(pyproject_text)
    new_version = bump_version(previous_version, bump)

    updated_pyproject = update_pyproject_text(pyproject_text, new_version)
    updated_package_json = update_package_json_text(package_json_text, new_version)
    updated_changelog, release_notes = update_changelog_text(changelog_text, new_version)
    updated_citation = update_citation_version_text(citation_text, new_version)
    updated_readme = update_readme_version_text(readme_text, new_version)

    _write_text(pyproject_path, updated_pyproject)
    _write_text(package_json_path, updated_package_json)
    _write_text(changelog_path, updated_changelog)
    _write_text(citation_path, updated_citation)
    _write_text(readme_path, updated_readme)

    return ReleaseMetadata(
        previous_version=previous_version,
        version=new_version,
        bump=bump,
        release_branch=f"release/v{new_version}",
        release_notes=release_notes,
    )


def stamp_publish_date(repo_root: Path, *, release_date: str | None = None) -> PublishDateMetadata:
    release_date = _validate_release_date(release_date or current_release_date())
    release_year = release_date.split("-", 1)[0]

    citation_path = repo_root / "CITATION.cff"
    readme_path = repo_root / "README.md"

    citation_text = _read_text(citation_path)
    readme_text = _read_text(readme_path)

    updated_citation = update_citation_release_date_text(citation_text, release_date)
    updated_readme = update_readme_release_year_text(readme_text, release_year)

    changed_files: list[str] = []
    if updated_citation != citation_text:
        _write_text(citation_path, updated_citation)
        changed_files.append(citation_path.name)
    if updated_readme != readme_text:
        _write_text(readme_path, updated_readme)
        changed_files.append(readme_path.name)

    return PublishDateMetadata(
        release_date=release_date,
        release_year=release_year,
        changed_files=tuple(changed_files),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Helpers for the manual release workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Update release files for the next version.")
    prepare_parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root.")
    prepare_parser.add_argument("--bump", choices=("patch", "minor", "major"), required=True)

    stamp_parser = subparsers.add_parser(
        "stamp-publish-date",
        help="Update publish-date metadata after the release PR has been merged.",
    )
    stamp_parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root.")
    stamp_parser.add_argument(
        "--release-date",
        help="Override the release date written to CITATION.cff (YYYY-MM-DD).",
    )

    show_version_parser = subparsers.add_parser("show-version", help="Print the current release version.")
    show_version_parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root.")

    release_notes_parser = subparsers.add_parser("release-notes", help="Print release notes for a version.")
    release_notes_parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root.")
    release_notes_parser.add_argument("--version", required=True, help="Version heading to extract.")

    pypi_preflight_parser = subparsers.add_parser(
        "pypi-preflight",
        help="Record whether the release version already exists on PyPI before publishing.",
    )
    pypi_preflight_parser.add_argument("--package", default=DEFAULT_PYPI_PACKAGE_NAME, help="PyPI project name.")
    pypi_preflight_parser.add_argument("--version", required=True, help="Release version to probe.")
    pypi_preflight_parser.add_argument("--github-output", type=Path, help="Path to the GitHub Actions output file.")

    pypi_status_parser = subparsers.add_parser(
        "pypi-publish-status",
        help="Record the final PyPI publish status after the trusted publishing step.",
    )
    pypi_status_parser.add_argument("--package", default=DEFAULT_PYPI_PACKAGE_NAME, help="PyPI project name.")
    pypi_status_parser.add_argument("--version", required=True, help="Release version to verify.")
    pypi_status_parser.add_argument("--pre-publish-status", required=True, help="Status from pypi-preflight.")
    pypi_status_parser.add_argument("--publish-outcome", required=True, help="GitHub Actions outcome for publish step.")
    pypi_status_parser.add_argument("--github-output", type=Path, help="Path to the GitHub Actions output file.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = getattr(args, "repo", Path(".")).resolve()

    try:
        if args.command == "prepare":
            metadata = prepare_release(repo_root, args.bump)
            json.dump(asdict(metadata), sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0

        if args.command == "stamp-publish-date":
            metadata = stamp_publish_date(repo_root, release_date=args.release_date)
            json.dump(asdict(metadata), sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0

        if args.command == "show-version":
            sys.stdout.write(parse_current_version(_read_text(repo_root / "pyproject.toml")))
            sys.stdout.write("\n")
            return 0

        if args.command == "release-notes":
            release_notes = extract_release_notes(_read_text(repo_root / "CHANGELOG.md"), args.version)
            sys.stdout.write(release_notes)
            if not release_notes.endswith("\n"):
                sys.stdout.write("\n")
            return 0

        if args.command == "pypi-preflight":
            status = record_pypi_preflight_status(args.package, args.version, github_output=args.github_output)
            sys.stdout.write(f"{status}\n")
            return 0

        if args.command == "pypi-publish-status":
            status = record_pypi_publish_status(
                args.package,
                args.version,
                pre_publish_status=args.pre_publish_status,
                publish_outcome=args.publish_outcome,
                github_output=args.github_output,
            )
            sys.stdout.write(f"{status}\n")
            return 0
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

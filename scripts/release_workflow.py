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
import tomllib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


class ReleaseError(RuntimeError):
    """Raised when release inputs or tracked release surfaces are invalid."""


REQUIRED_NPM_PACK_FILES = frozenset(
    {
        "src/gpd/adapters/runtime_catalog.json",
        "src/gpd/core/public_surface_contract.json",
    }
)


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


def parse_current_version(pyproject_text: str) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', pyproject_text, re.M)
    if not match:
        raise ReleaseError("Could not parse version from pyproject.toml.")
    return match.group(1)


def parse_package_versions(package_json_text: str) -> tuple[str, str]:
    try:
        package_json = json.loads(package_json_text)
    except json.JSONDecodeError as exc:
        raise ReleaseError("Could not parse package.json metadata.") from exc

    if not isinstance(package_json, dict):
        raise ReleaseError("package.json root must be an object.")

    version = package_json.get("version")
    python_version = package_json.get("gpdPythonVersion")
    if not isinstance(version, str) or not version:
        raise ReleaseError('package.json must define a string "version".')
    if not isinstance(python_version, str) or not python_version:
        raise ReleaseError('package.json must define a string "gpdPythonVersion".')

    return version, python_version


def validate_release_metadata_sources(pyproject_text: str, package_json_text: str) -> str:
    pyproject_version = parse_current_version(pyproject_text)
    package_version, python_version = parse_package_versions(package_json_text)
    if package_version != pyproject_version or python_version != pyproject_version:
        raise ReleaseError(
            "Version source-of-truth mismatch: "
            f'pyproject.toml={pyproject_version!r}, package.json["version"]={package_version!r}, '
            f'package.json["gpdPythonVersion"]={python_version!r}.'
        )
    return pyproject_version


def validate_package_data_rules(pyproject_text: str, package_json_text: str) -> None:
    try:
        pyproject = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError as exc:
        raise ReleaseError("Could not parse pyproject.toml metadata.") from exc

    try:
        package_json = json.loads(package_json_text)
    except json.JSONDecodeError as exc:
        raise ReleaseError("Could not parse package.json metadata.") from exc
    files = package_json.get("files")
    if not isinstance(files, list) or any(not isinstance(entry, str) or not entry for entry in files):
        raise ReleaseError('package.json "files" must be a list of non-empty strings.')
    if len(files) != len(set(files)):
        raise ReleaseError('package.json "files" entries must be unique.')
    if "bin/" in files:
        raise ReleaseError('package.json "files" must list the bootstrap entrypoint explicitly as "bin/install.js", not "bin/".')
    if "bin/install.js" not in files:
        raise ReleaseError('package.json "files" must include "bin/install.js".')

    try:
        wheel_target = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
        artifacts = wheel_target["artifacts"]
        force_include = wheel_target["force-include"]
    except KeyError as exc:
        raise ReleaseError("Missing wheel package-data configuration in pyproject.toml.") from exc

    if not isinstance(artifacts, list) or any(not isinstance(pattern, str) or not pattern for pattern in artifacts):
        raise ReleaseError('pyproject.toml wheel "artifacts" must be a list of non-empty strings.')
    if len(artifacts) != len(set(artifacts)):
        raise ReleaseError('pyproject.toml wheel "artifacts" entries must be unique.')

    if not isinstance(force_include, dict) or any(
        not isinstance(source, str) or not source or not isinstance(dest, str) or not dest
        for source, dest in force_include.items()
    ):
        raise ReleaseError('pyproject.toml wheel "force-include" must map non-empty strings to non-empty strings.')
    destinations = list(force_include.values())
    if len(destinations) != len(set(destinations)):
        raise ReleaseError('pyproject.toml wheel "force-include" destinations must be unique.')

    invalid_destinations = [dest for dest in destinations if dest.startswith("/") or ".." in Path(dest).parts]
    if invalid_destinations:
        joined = ", ".join(sorted(invalid_destinations))
        raise ReleaseError(
            'pyproject.toml wheel "force-include" destinations must be relative paths; '
            f"found: {joined}."
        )


def validate_npm_pack_manifest(entries: list[dict[str, object]]) -> None:
    if not entries:
        raise ReleaseError("npm pack output did not describe any package entries.")

    file_paths: set[str] = set()
    for entry in entries:
        files = entry.get("files")
        if not isinstance(files, list):
            raise ReleaseError("npm pack entry is missing a files list.")
        for candidate in files:
            path_value = candidate.get("path")
            if isinstance(path_value, str) and path_value:
                file_paths.add(path_value)

    missing = REQUIRED_NPM_PACK_FILES - file_paths
    if missing:
        joined = ", ".join(sorted(missing))
        raise ReleaseError(f"npm pack is missing required resources: {joined}.")


def preflight_release_sync(repo_root: Path) -> None:
    validate_package_data_rules(_read_text(repo_root / "pyproject.toml"), _read_text(repo_root / "package.json"))


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


def extract_vnext_notes(changelog_text: str) -> str:
    match = re.search(r"^## vNEXT\s*\n(.*?)(?=^## v|\Z)", changelog_text, re.M | re.S)
    if not match:
        raise ReleaseError("No ## vNEXT section found in CHANGELOG.md.")

    body = match.group(1).strip()
    if not body:
        raise ReleaseError("## vNEXT section in CHANGELOG.md is empty.")
    return body


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
    updated = _replace_once(
        package_json_text,
        r'("version":\s*")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
        description="package.json version",
    )
    return _replace_once(
        updated,
        r'("gpdPythonVersion":\s*")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
        description="package.json gpdPythonVersion",
    )


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

    previous_version = validate_release_metadata_sources(pyproject_text, package_json_text)
    validate_package_data_rules(pyproject_text, package_json_text)
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

    preflight_parser = subparsers.add_parser("preflight-sync", help="Validate release packaging metadata before publishing.")
    preflight_parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root.")

    pack_parser = subparsers.add_parser(
        "verify-npm-pack",
        help="Validate npm pack --dry-run --json output.",
    )
    pack_parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root.")
    pack_parser.add_argument(
        "--input",
        type=Path,
        default=Path("tmp/npm-pack-dry-run.json"),
        help="Path to the JSON output from npm pack --dry-run --json.",
    )

    release_notes_parser = subparsers.add_parser("release-notes", help="Print release notes for a version.")
    release_notes_parser.add_argument("--repo", type=Path, default=Path("."), help="Repository root.")
    release_notes_parser.add_argument("--version", required=True, help="Version heading to extract.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo.resolve()

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
            pyproject_text = _read_text(repo_root / "pyproject.toml")
            package_json_text = _read_text(repo_root / "package.json")
            validate_package_data_rules(pyproject_text, package_json_text)
            sys.stdout.write(validate_release_metadata_sources(pyproject_text, package_json_text))
            sys.stdout.write("\n")
            return 0

        if args.command == "preflight-sync":
            preflight_release_sync(repo_root)
            sys.stdout.write("Release packaging metadata is in sync.\n")
            return 0

        if args.command == "verify-npm-pack":
            entries = json.loads(_read_text(repo_root / args.input))
            validate_npm_pack_manifest(entries)
            sys.stdout.write("npm pack manifest includes required runtime resources.\n")
            return 0

        if args.command == "release-notes":
            release_notes = extract_release_notes(_read_text(repo_root / "CHANGELOG.md"), args.version)
            sys.stdout.write(release_notes)
            if not release_notes.endswith("\n"):
                sys.stdout.write("\n")
            return 0
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

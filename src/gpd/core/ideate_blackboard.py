"""Deterministic artifact helpers for ``gpd:ideate`` sessions."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from pathlib import Path

import yaml

from gpd.core.constants import IDEATE_FILE_PREFIX, ProjectLayout
from gpd.core.frontmatter import extract_frontmatter, reconstruct_frontmatter
from gpd.core.utils import atomic_write, file_lock, normalize_ascii_slug

__all__ = [
    "BlackboardUpdate",
    "IdeateArtifactPaths",
    "IdeateSession",
    "TranscriptTurn",
    "allocate_ideate_session",
    "append_transcript_turn",
    "initialize_ideate_artifacts",
    "merge_blackboard_update",
    "render_ideate_blackboard",
    "render_ideate_transcript",
    "render_ideation_report",
    "replace_blackboard_section",
    "slugify_ideate_topic",
]


_COMMAND_NAME = "gpd:ideate"
_SCHEMA_VERSION = 2
_DEFAULT_TOPIC_SLUG = "untitled-topic"
_DEFAULT_TOPIC_DISPLAY = "Untitled topic"
_VALID_BLACKBOARD_STATUSES = {"active", "paused", "archived", "promoted"}
_PARTICIPANTS = (
    "user",
    "gpd-paper-digester",
    "gpd-ideator",
    "gpd-ideation-critic",
)
_BLACKBOARD_SECTIONS = (
    "Session",
    "User Preferences",
    "Source Manifest",
    "Source Digests",
    "Cross-Paper Model",
    "Tensions And Confusions",
    "Candidate Ideas",
    "Critic Notes",
    "Vetoed Ideas",
    "Ranked Questions",
    "Next Experiments Or Calculations",
    "Open Steering Questions",
)
_SECTION_ALIAS_MAP = {
    "session": "Session",
    "user_preferences": "User Preferences",
    "source_manifest": "Source Manifest",
    "source_digests": "Source Digests",
    "cross_paper_model": "Cross-Paper Model",
    "tensions_and_confusions": "Tensions And Confusions",
    "tensions": "Tensions And Confusions",
    "candidate_ideas": "Candidate Ideas",
    "ideas": "Candidate Ideas",
    "critic_notes": "Critic Notes",
    "vetoed_ideas": "Vetoed Ideas",
    "ranked_questions": "Ranked Questions",
    "next_experiments_or_calculations": "Next Experiments Or Calculations",
    "next_steps": "Next Experiments Or Calculations",
    "open_steering_questions": "Open Steering Questions",
}
_HEADING_RE_TEMPLATE = r"(?m)^##[ \t]+{heading}[ \t]*$"
_TURN_HEADING_RE = re.compile(r"(?m)^##[ \t]+Turn[ \t]+(\d+)\b.*$")


@dataclass(frozen=True, slots=True)
class IdeateArtifactPaths:
    """Sibling artifact paths for one ``gpd:ideate`` session."""

    blackboard: Path
    transcript: Path
    report: Path

    @property
    def all(self) -> tuple[Path, Path, Path]:
        return (self.blackboard, self.transcript, self.report)

    @property
    def blackboards_dir(self) -> Path:
        return self.blackboard.parent

    @property
    def blackboard_path(self) -> Path:
        return self.blackboard

    @property
    def transcript_path(self) -> Path:
        return self.transcript

    @property
    def report_path(self) -> Path:
        return self.report


@dataclass(frozen=True, slots=True)
class IdeateSession:
    """Allocated session metadata and artifact paths."""

    workspace_root: Path
    topic: str
    topic_slug: str
    session_slug: str
    created: date
    turn_budget: int
    source_inputs: tuple[str, ...]
    knowledge_docs: tuple[str, ...]
    source_manifest: Mapping[str, object]
    paths: IdeateArtifactPaths

    @property
    def day_compact(self) -> str:
        return self.created.strftime("%Y%m%d")

    @property
    def blackboard_id(self) -> str:
        return f"BB-{self.day_compact}-{self.session_slug}"

    @property
    def transcript_id(self) -> str:
        return f"TR-{self.day_compact}-{self.session_slug}"

    @property
    def report_id(self) -> str:
        return f"IR-{self.day_compact}-{self.session_slug}"

    @property
    def stem(self) -> str:
        return self.paths.blackboard.stem

    @property
    def blackboard_path(self) -> Path:
        return self.paths.blackboard

    @property
    def transcript_path(self) -> Path:
        return self.paths.transcript

    @property
    def report_path(self) -> Path:
        return self.paths.report


@dataclass(frozen=True, slots=True, init=False)
class TranscriptTurn:
    """One cleaned transcript turn supplied by the parent workflow."""

    turn_number: int | None
    turn_id: str
    thread_id: str
    entries: tuple[tuple[str, str], ...]
    summary: str

    def __init__(
        self,
        *,
        turn_id: str,
        thread_id: str,
        turn_number: int | None = None,
        entries: Mapping[str, object] | Sequence[object] = (),
        messages: Mapping[str, object] | Sequence[object] = (),
        role: str = "orchestrator",
        content: str = "",
        summary: str = "",
        **_: object,
    ) -> None:
        object.__setattr__(self, "turn_number", _coerce_optional_int(turn_number))
        object.__setattr__(self, "turn_id", str(turn_id).strip())
        object.__setattr__(self, "thread_id", str(thread_id).strip())
        object.__setattr__(
            self,
            "entries",
            _normalize_transcript_entries(entries or messages, role=role, content=content),
        )
        object.__setattr__(self, "summary", str(summary).strip())


@dataclass(frozen=True, slots=True, init=False)
class BlackboardUpdate:
    """Durable blackboard changes supplied by the parent workflow."""

    turn: int | None
    status: str | None
    source_manifest: Mapping[str, object] | None
    sections: tuple[tuple[str, str], ...]

    def __init__(
        self,
        *,
        turn: int | None = None,
        status: object | None = None,
        source_manifest: Mapping[str, object] | None = None,
        sections: Mapping[str, object] | Sequence[object] = (),
        user_preferences: object = (),
        source_digests: object = (),
        cross_paper_model: object = (),
        tensions_and_confusions: object = (),
        candidate_ideas: object = (),
        critic_notes: object = (),
        vetoed_ideas: object = (),
        ranked_questions: object = (),
        next_experiments_or_calculations: object = (),
        open_steering_questions: object = (),
        **_: object,
    ) -> None:
        section_items: list[tuple[str, str]] = []
        section_items.extend(_normalize_section_updates(sections))
        aliases = {
            "user_preferences": user_preferences,
            "source_digests": source_digests,
            "cross_paper_model": cross_paper_model,
            "tensions_and_confusions": tensions_and_confusions,
            "candidate_ideas": candidate_ideas,
            "critic_notes": critic_notes,
            "vetoed_ideas": vetoed_ideas,
            "ranked_questions": ranked_questions,
            "next_experiments_or_calculations": next_experiments_or_calculations,
            "open_steering_questions": open_steering_questions,
        }
        for alias, values in aliases.items():
            text = _render_update_content(values)
            if text:
                section_items.append((_SECTION_ALIAS_MAP[alias], text))
        object.__setattr__(self, "turn", _coerce_optional_int(turn))
        object.__setattr__(self, "status", _normalize_blackboard_status(status))
        object.__setattr__(self, "source_manifest", source_manifest)
        object.__setattr__(self, "sections", tuple(section_items))


def slugify_ideate_topic(topic: str) -> str:
    """Return a stable non-empty slug for an ideation topic."""

    return normalize_ascii_slug(topic) or _DEFAULT_TOPIC_SLUG


def allocate_ideate_session(
    workspace_root: Path | str,
    topic: str,
    *,
    today: date | None = None,
    turn_budget: int = 1,
    source_inputs: Sequence[object] = (),
    knowledge_docs: Sequence[object] = (),
    source_manifest: Mapping[str, object] | None = None,
) -> IdeateSession:
    """Allocate same-stem blackboard, transcript, and report paths."""

    root = Path(workspace_root).expanduser().resolve(strict=False)
    created = today or date.today()
    budget = int(turn_budget)
    if budget < 1:
        raise ValueError("turn_budget must be at least 1")

    topic_text = str(topic).strip()
    topic_slug = slugify_ideate_topic(topic_text)
    blackboards_dir = ProjectLayout(root).blackboards_dir
    day = created.isoformat()

    collision = 1
    while True:
        session_slug = topic_slug if collision == 1 else f"{topic_slug}-{collision}"
        stem = f"{IDEATE_FILE_PREFIX}-{day}-{session_slug}"
        paths = IdeateArtifactPaths(
            blackboard=blackboards_dir / f"{stem}.md",
            transcript=blackboards_dir / f"{stem}-transcript.md",
            report=blackboards_dir / f"{stem}-report.md",
        )
        if not any(path.exists() for path in paths.all):
            return IdeateSession(
                workspace_root=root,
                topic=topic_text,
                topic_slug=topic_slug,
                session_slug=session_slug,
                created=created,
                turn_budget=budget,
                source_inputs=_string_tuple(source_inputs),
                knowledge_docs=_string_tuple(knowledge_docs),
                source_manifest=source_manifest or _default_source_manifest(),
                paths=paths,
            )
        collision += 1


def initialize_ideate_artifacts(session: IdeateSession) -> IdeateArtifactPaths:
    """Write the blackboard, transcript, and report files for *session*."""

    existing = [path for path in session.paths.all if path.exists()]
    if existing:
        raise FileExistsError(f"ideate artifact already exists: {existing[0]}")

    rendered = (
        (session.paths.blackboard, render_ideate_blackboard(session)),
        (session.paths.transcript, render_ideate_transcript(session)),
        (session.paths.report, render_ideation_report(session)),
    )
    created_paths: list[Path] = []
    try:
        for path, content in rendered:
            atomic_write(path, content)
            created_paths.append(path)
    except Exception:
        for path in reversed(created_paths):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return session.paths


def render_ideate_blackboard(session: IdeateSession) -> str:
    """Render the initial ideation blackboard Markdown from its template."""

    related = _session_related_paths(session)
    meta = _base_frontmatter(session) | {
        "blackboard_schema_version": _SCHEMA_VERSION,
        "blackboard_id": session.blackboard_id,
        "status": "active",
        "turn": 0,
        "turn_budget": session.turn_budget,
        "participants": [{"role": role} for role in _PARTICIPANTS],
        "related_artifacts": {
            "transcript": related["transcript"],
            "report": related["report"],
        },
    }
    return _render_template(
        "ideate-blackboard.md",
        session,
        meta,
        transcript_path=related["transcript"],
        report_path=related["report"],
        source_manifest_yaml=_yaml_block(session.source_manifest),
    )


def render_ideate_transcript(session: IdeateSession) -> str:
    """Render the initial cleaned transcript Markdown from its template."""

    related = _session_related_paths(session)
    meta = _base_frontmatter(session) | {
        "transcript_schema_version": _SCHEMA_VERSION,
        "transcript_id": session.transcript_id,
        "blackboard_id": session.blackboard_id,
        "turn_count": 0,
        "related_artifacts": {
            "blackboard": related["blackboard"],
            "report": related["report"],
        },
    }
    return _render_template(
        "ideate-transcript.md",
        session,
        meta,
        blackboard_path=related["blackboard"],
        report_path=related["report"],
    )


def render_ideation_report(session: IdeateSession) -> str:
    """Render the initial ideation report Markdown from its template."""

    related = _session_related_paths(session)
    meta = _base_frontmatter(session) | {
        "ideation_report_schema_version": _SCHEMA_VERSION,
        "report_id": session.report_id,
        "blackboard_id": session.blackboard_id,
        "related_artifacts": {
            "blackboard": related["blackboard"],
            "transcript": related["transcript"],
        },
    }
    return _render_template(
        "ideation-report.md",
        session,
        meta,
        blackboard_path=related["blackboard"],
        transcript_path=related["transcript"],
    )


def append_transcript_turn(path: Path | str, turn: TranscriptTurn, *, updated: date | None = None) -> None:
    """Append one cleaned turn to a transcript under an advisory file lock."""

    transcript_path = Path(path)
    with file_lock(transcript_path):
        content = transcript_path.read_text(encoding="utf-8")
        meta, body = extract_frontmatter(content)
        existing_turns = _turn_numbers(body)
        if existing_turns != list(range(1, len(existing_turns) + 1)):
            raise ValueError("existing transcript turn headings must be contiguous")
        if not turn.turn_id:
            raise ValueError("turn_id must be nonblank")
        if not turn.thread_id:
            raise ValueError("thread_id must be nonblank")
        next_turn_number = len(existing_turns) + 1
        if turn.turn_number is not None and turn.turn_number != next_turn_number:
            raise ValueError(f"turn_number must be the next contiguous turn ({next_turn_number})")
        meta["turn_count"] = next_turn_number
        meta["updated"] = (updated or date.today()).isoformat()
        updated_body = _append_turn_body(body, _render_transcript_turn(turn, next_turn_number))
        atomic_write(transcript_path, reconstruct_frontmatter(meta, updated_body))


def replace_blackboard_section(path: Path | str, heading: str, content: str, *, updated: date | None = None) -> None:
    """Replace one blackboard section body without interpreting its content."""

    blackboard_path = Path(path)
    canonical_heading = _canonical_section_heading(heading)
    with file_lock(blackboard_path):
        raw = blackboard_path.read_text(encoding="utf-8")
        meta, body = extract_frontmatter(raw)
        meta["updated"] = (updated or date.today()).isoformat()
        updated_body = _replace_section_body(body, canonical_heading, _ensure_trailing_newline(content.strip()))
        atomic_write(blackboard_path, reconstruct_frontmatter(meta, updated_body))


def merge_blackboard_update(path: Path | str, update: BlackboardUpdate, *, updated: date | None = None) -> None:
    """Merge durable workflow updates into a blackboard."""

    blackboard_path = Path(path)
    with file_lock(blackboard_path):
        raw = blackboard_path.read_text(encoding="utf-8")
        meta, body = extract_frontmatter(raw)
        if update.turn is not None:
            meta["turn"] = update.turn
        if update.status is not None:
            meta["status"] = update.status
        meta["updated"] = (updated or date.today()).isoformat()
        if update.source_manifest is not None:
            body = _replace_section_body(
                body,
                "Source Manifest",
                "```yaml\n" + _yaml_block(update.source_manifest) + "\n```\n",
            )
        for heading, content in update.sections:
            body = _append_to_section(body, heading, content)
        atomic_write(blackboard_path, reconstruct_frontmatter(meta, _ensure_trailing_newline(body.rstrip())))


def _base_frontmatter(session: IdeateSession) -> dict[str, object]:
    return {
        "command": _COMMAND_NAME,
        "created": session.created.isoformat(),
        "updated": session.created.isoformat(),
        "topic": session.topic,
        "topic_slug": session.topic_slug,
        "session_slug": session.session_slug,
        "source_inputs": list(session.source_inputs),
        "knowledge_docs": list(session.knowledge_docs),
    }


def _default_source_manifest() -> dict[str, object]:
    return {"source_manifest": {"sources": []}}


def _session_related_paths(session: IdeateSession) -> dict[str, str]:
    return {
        "blackboard": _relative_posix(session.paths.blackboard, session.workspace_root),
        "transcript": _relative_posix(session.paths.transcript, session.workspace_root),
        "report": _relative_posix(session.paths.report, session.workspace_root),
    }


def _relative_posix(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix().lstrip("/")


def _render_template(name: str, session: IdeateSession, meta: Mapping[str, object], **values: object) -> str:
    template = files("gpd.specs").joinpath("templates", name).read_text(encoding="utf-8")
    substitutions = {
        "frontmatter": _frontmatter_block(dict(meta)),
        "blackboard_id": session.blackboard_id,
        "transcript_id": session.transcript_id,
        "report_id": session.report_id,
        "topic_display": session.topic or _DEFAULT_TOPIC_DISPLAY,
        "created": session.created.isoformat(),
        "turn_budget": str(session.turn_budget),
    }
    substitutions.update({key: str(value) for key, value in values.items()})
    if "{{frontmatter}}" not in template:
        return _render_documented_template(name, template, session, meta, substitutions)
    for key, value in substitutions.items():
        template = template.replace("{{" + key + "}}", value)
    return _ensure_trailing_newline(template)


def _render_documented_template(
    name: str,
    template: str,
    session: IdeateSession,
    meta: Mapping[str, object],
    substitutions: Mapping[str, str],
) -> str:
    if name == "ideate-blackboard.md":
        body = _render_blackboard_body_from_template(template, session, substitutions)
    elif name == "ideate-transcript.md":
        body = _render_initial_transcript_body(session, substitutions)
    elif name == "ideation-report.md":
        body = _render_report_body_from_template(template, session)
    else:
        raise ValueError(f"unsupported ideate template: {name}")
    return _ensure_trailing_newline(reconstruct_frontmatter(dict(meta), body))


def _render_blackboard_body_from_template(
    template: str,
    session: IdeateSession,
    substitutions: Mapping[str, str],
) -> str:
    title, headings = _required_markdown_outline(template, default_title="# Ideation Blackboard")
    lines = [_topic_title(title, session), ""]
    for heading in headings:
        lines.extend([f"## {heading}", ""])
        if heading == "Session":
            lines.extend(
                [
                    f"- Blackboard: {session.blackboard_id}",
                    f"- Topic: {session.topic or _DEFAULT_TOPIC_DISPLAY}",
                    f"- Created: {session.created.isoformat()}",
                    f"- Turn budget: {session.turn_budget}",
                    f"- Transcript: {substitutions.get('transcript_path', '')}",
                    f"- Report: {substitutions.get('report_path', '')}",
                ]
            )
        elif heading == "Source Manifest":
            lines.extend(["```yaml", substitutions.get("source_manifest_yaml", _yaml_block(_default_source_manifest())), "```"])
        else:
            lines.append("None recorded.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_initial_transcript_body(session: IdeateSession, substitutions: Mapping[str, str]) -> str:
    return (
        f"# Ideation Transcript: {session.topic or _DEFAULT_TOPIC_DISPLAY}\n\n"
        "## Session\n\n"
        f"- Transcript: {session.transcript_id}\n"
        f"- Blackboard: {session.blackboard_id}\n"
        f"- Topic: {session.topic or _DEFAULT_TOPIC_DISPLAY}\n"
        f"- Created: {session.created.isoformat()}\n"
        f"- Blackboard file: {substitutions.get('blackboard_path', '')}\n"
        f"- Report file: {substitutions.get('report_path', '')}\n\n"
        "## Turns\n\n"
        "No turns recorded.\n"
    )


def _render_report_body_from_template(template: str, session: IdeateSession) -> str:
    title, headings = _required_markdown_outline(template, default_title="# Ideation Report")
    lines = [_topic_title(title, session), ""]
    for heading in headings:
        lines.extend([f"## {heading}", "", "None recorded.", ""])
    return "\n".join(lines).rstrip() + "\n"


def _required_markdown_outline(template: str, *, default_title: str) -> tuple[str, tuple[str, ...]]:
    marker = "```markdown"
    start = template.find(marker)
    if start == -1:
        return default_title, ()
    block_start = start + len(marker)
    block_end = template.find("```", block_start)
    if block_end == -1:
        return default_title, ()
    title = default_title
    headings: list[str] = []
    for raw_line in template[block_start:block_end].splitlines():
        line = raw_line.strip()
        if line.startswith("# ") and title == default_title:
            title = line
        elif line.startswith("## "):
            headings.append(line[3:].strip())
    return title, tuple(headings)


def _topic_title(title: str, session: IdeateSession) -> str:
    return title.replace("<Topic>", session.topic or _DEFAULT_TOPIC_DISPLAY)


def _frontmatter_block(meta: dict[str, object]) -> str:
    text = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=999999).rstrip()
    return f"---\n{text}\n---"


def _yaml_block(value: Mapping[str, object]) -> str:
    return yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True, width=999999).rstrip()


def _string_tuple(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, Mapping):
        iterable = values.values()
    elif isinstance(values, (str, Path)):
        iterable = (values,)
    else:
        try:
            iterable = iter(values)
        except TypeError:
            iterable = (values,)

    result: list[str] = []
    for value in iterable:
        text = _stringify_value(value)
        if text:
            result.append(text)
    return tuple(result)


def _stringify_value(value: object) -> str:
    if isinstance(value, Path):
        return value.as_posix()
    return str(value).strip()


def _coerce_optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_blackboard_status(status: object | None) -> str | None:
    if status is None:
        return None
    text = str(status).strip()
    if text in _VALID_BLACKBOARD_STATUSES:
        return text
    raise ValueError("status must be one of active, paused, archived, promoted")


def _normalize_transcript_entries(
    entries: Mapping[str, object] | Sequence[object],
    *,
    role: str,
    content: str,
) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    if isinstance(entries, Mapping):
        iterable = entries.items()
    elif isinstance(entries, (str, Path)):
        iterable = (entries,)
    else:
        iterable = entries
    for item in iterable:
        label = ""
        text = ""
        if isinstance(item, tuple) and len(item) == 2:
            label = str(item[0]).strip()
            text = _stringify_value(item[1])
        elif isinstance(item, Mapping):
            label = _stringify_value(item.get("role") or item.get("speaker") or item.get("label"))
            text = _stringify_value(item.get("content") or item.get("text") or item.get("message"))
        else:
            text = _stringify_value(item)
        if text:
            normalized.append((label or role or "orchestrator", text))
    if not normalized and content.strip():
        normalized.append((role or "orchestrator", content.strip()))
    return tuple(normalized)


def _normalize_section_updates(sections: Mapping[str, object] | Sequence[object]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(sections, Mapping):
        iterable = sections.items()
    else:
        iterable = sections
    for item in iterable:
        if isinstance(item, tuple) and len(item) == 2:
            heading = _canonical_section_heading(_stringify_value(item[0]))
            content = _render_update_content(item[1])
        elif isinstance(item, Mapping):
            heading = _canonical_section_heading(_stringify_value(item.get("section") or item.get("heading")))
            content = _render_update_content(item.get("content") or item.get("items") or item.get("values"))
        else:
            continue
        if heading and content:
            rows.append((heading, content))
    return rows


def _render_update_content(values: object) -> str:
    if values is None:
        return ""
    if isinstance(values, str):
        return values.strip()
    if isinstance(values, Mapping):
        return _yaml_block(values)
    items = _string_tuple(values)
    if not items:
        return ""
    return "\n".join(_bullet_lines(items))


def _canonical_section_heading(raw: str) -> str:
    text = raw.strip()
    if text in _BLACKBOARD_SECTIONS:
        return text
    alias_key = text.lower().replace(" ", "_").replace("-", "_")
    if alias_key in _SECTION_ALIAS_MAP:
        return _SECTION_ALIAS_MAP[alias_key]
    normalized = normalize_ascii_slug(text) or ""
    for section in _BLACKBOARD_SECTIONS:
        if normalized == (normalize_ascii_slug(section) or ""):
            return section
    return text


def _render_transcript_turn(turn: TranscriptTurn, turn_number: int) -> str:
    lines = [
        f"## Turn {turn_number}",
        "",
        "Metadata:",
        "",
        f"- turn_id: {turn.turn_id}",
        f"- thread_id: {turn.thread_id}",
        "",
    ]
    if turn.summary:
        lines.extend(["### Summary", "", turn.summary, ""])
    for role, content in turn.entries:
        lines.extend([f"### {role}", "", content, ""])
    return "\n".join(lines).rstrip() + "\n"


def _append_turn_body(body: str, rendered_turn: str) -> str:
    body = body.rstrip()
    if "No turns recorded." in body:
        body = body.replace("No turns recorded.", "").rstrip()
    return _ensure_trailing_newline(body + "\n\n" + rendered_turn.rstrip())


def _turn_numbers(body: str) -> list[int]:
    return [int(match.group(1)) for match in _TURN_HEADING_RE.finditer(body)]


def _replace_section_body(body: str, heading: str, content: str) -> str:
    match = _section_heading_re(heading).search(body)
    if match is None:
        addition = f"\n\n## {heading}\n\n{content.strip()}\n"
        return _ensure_trailing_newline(body.rstrip() + addition)
    next_heading = re.search(r"(?m)^##[ \t]+", body[match.end() :])
    section_start = match.end()
    section_end = len(body) if next_heading is None else match.end() + next_heading.start()
    replacement = "\n\n" + content.strip() + "\n\n"
    return body[:section_start] + replacement + body[section_end:]


def _append_to_section(body: str, heading: str, content: str) -> str:
    canonical_heading = _canonical_section_heading(heading)
    match = _section_heading_re(canonical_heading).search(body)
    if match is None:
        return _ensure_trailing_newline(body.rstrip() + f"\n\n## {canonical_heading}\n\n{content.strip()}\n")
    next_heading = re.search(r"(?m)^##[ \t]+", body[match.end() :])
    section_start = match.end()
    section_end = len(body) if next_heading is None else match.end() + next_heading.start()
    before = body[:section_start]
    section_body = body[section_start:section_end].strip()
    after = body[section_end:]
    new_content = content.strip()
    if not section_body or section_body in {"None recorded.", "None identified."}:
        merged = new_content
    else:
        merged = section_body.rstrip() + "\n\n" + new_content
    return before + "\n\n" + merged + "\n\n" + after.lstrip("\n")


def _section_heading_re(heading: str) -> re.Pattern[str]:
    return re.compile(_HEADING_RE_TEMPLATE.format(heading=re.escape(heading)))


def _bullet_lines(items: Sequence[str]) -> list[str]:
    lines: list[str] = []
    for item in items:
        clean = item.strip()
        if not clean:
            continue
        if clean.startswith(("- ", "* ")):
            lines.append(f"- {clean[2:].strip()}")
        else:
            lines.append("- " + clean.replace("\n", "\n  "))
    return lines


def _ensure_trailing_newline(content: str) -> str:
    return content if content.endswith("\n") else content + "\n"

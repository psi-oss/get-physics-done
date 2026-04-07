from __future__ import annotations

import re
import tomllib
from pathlib import Path

from gpd.adapters.install_utils import compile_markdown_for_runtime, project_markdown_for_runtime

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
DEFAULT_BODY_MARKER = "Prompt body"
DEFAULT_REQUIRED_OUTPUT = "GPD/review/REFEREE-DECISION{round_suffix}.json"
DEFAULT_PROOF_OUTPUT = "GPD/review/PROOF-REDTEAM{round_suffix}.md"
DEFAULT_CONDITIONAL_WHEN = "theorem-bearing claims are present"
_REVIEW_CONTRACT_SECTION_RE = re.compile(
    r"## Review Contract\r?\n\r?\n.*?```yaml\r?\n.*?\r?\n```",
    flags=re.DOTALL,
)


def build_review_contract_fixture_markdown(
    *,
    command_name: str = "gpd:peer-review",
    body_marker: str = DEFAULT_BODY_MARKER,
    conditional_when: str = DEFAULT_CONDITIONAL_WHEN,
) -> str:
    return (
        "---\n"
        f"name: {command_name}\n"
        "description: D\n"
        "review-contract:\n"
        "  review_mode: publication\n"
        "  schema_version: 1\n"
        "  required_outputs:\n"
        f"    - {DEFAULT_REQUIRED_OUTPUT}\n"
        "  conditional_requirements:\n"
        f"    - when: {conditional_when}\n"
        "      required_outputs:\n"
        f"        - {DEFAULT_PROOF_OUTPUT}\n"
        "---\n"
        f"{body_marker}"
    )


def compile_review_contract_fixture_for_runtime(
    runtime: str,
    *,
    command_name: str = "gpd:peer-review",
    body_marker: str = DEFAULT_BODY_MARKER,
    conditional_when: str = DEFAULT_CONDITIONAL_WHEN,
) -> str:
    return compile_markdown_for_runtime(
        build_review_contract_fixture_markdown(
            command_name=command_name,
            body_marker=body_marker,
            conditional_when=conditional_when,
        ),
        runtime=runtime,
        path_prefix="/prefix/",
    )


def compile_review_contract_command_for_runtime(
    command_name: str,
    runtime: str,
    *,
    path_prefix: str = "/runtime/",
) -> str:
    return project_markdown_for_runtime(
        read_command_source(command_name),
        runtime=runtime,
        path_prefix=path_prefix,
        src_root=REPO_ROOT / "src/gpd",
        command_name=command_name,
    )


def extract_review_contract_section(content: str) -> str:
    match = _REVIEW_CONTRACT_SECTION_RE.search(content)
    if match is None:
        try:
            prompt = tomllib.loads(content).get("prompt")
        except tomllib.TOMLDecodeError:
            prompt = None
        if isinstance(prompt, str):
            match = _REVIEW_CONTRACT_SECTION_RE.search(prompt)
    assert match is not None, "Missing Review Contract section"
    return match.group(0)


def assert_review_contract_prompt_surface(
    content: str,
    *,
    body_marker: str = DEFAULT_BODY_MARKER,
    conditional_when: str = DEFAULT_CONDITIONAL_WHEN,
) -> str:
    section = extract_review_contract_section(content)

    assert content.count("## Review Contract") == 1
    assert "review_contract:" in section
    assert "review-contract:" not in section
    assert "review_mode: publication" in section
    assert DEFAULT_REQUIRED_OUTPUT in section
    assert "conditional_requirements:" in section
    assert f"when: {conditional_when}" in section
    assert DEFAULT_PROOF_OUTPUT in section
    assert content.index("## Review Contract") < content.index(body_marker)

    return section


def read_command_source(command_name: str) -> str:
    return (COMMANDS_DIR / f"{command_name}.md").read_text(encoding="utf-8")

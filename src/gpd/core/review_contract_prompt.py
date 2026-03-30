"""Helpers for surfacing review contracts inside model-visible prompt bodies."""

from __future__ import annotations


def extract_frontmatter_block(frontmatter: str, field_name: str) -> str:
    """Return one top-level YAML frontmatter block, preserving raw formatting."""

    lines = frontmatter.split("\n")
    prefix = f"{field_name}:"
    collected: list[str] = []
    collecting = False

    for line in lines:
        stripped = line.strip()
        is_top_level = line == line.lstrip()
        if not collecting:
            if is_top_level and stripped.startswith(prefix):
                collected.append(line.rstrip())
                collecting = True
            continue
        if is_top_level and stripped:
            break
        collected.append(line.rstrip())

    while collected and not collected[-1]:
        collected.pop()
    return "\n".join(collected)


def render_review_contract_prompt(yaml_block: str) -> str:
    """Render a model-visible review-contract section from raw YAML."""

    block = yaml_block.strip()
    if not block:
        return ""
    return (
        "## Review Contract\n\n"
        "This command is enforced against the following hard review contract. "
        "Satisfy it directly in the generated artifacts.\n\n"
        f"```yaml\n{block}\n```"
    )


def prepend_review_contract_prompt(body: str, yaml_block: str) -> str:
    """Front-load a review contract ahead of the substantive prompt body."""

    section = render_review_contract_prompt(yaml_block)
    if not section:
        return body
    if not body:
        return section
    return f"{section}\n\n{body}"

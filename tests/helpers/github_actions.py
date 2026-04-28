from __future__ import annotations

import re
from pathlib import Path

import yaml


class GitHubActionsLoader(yaml.SafeLoader):
    """PyYAML loader compatible with GitHub Actions' YAML 1.2-style `on` key."""


GitHubActionsLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
GitHubActionsLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def load_github_actions_workflow(path: Path) -> dict[str, object]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=GitHubActionsLoader)

    assert isinstance(data, dict), f"{path} must parse to a mapping"
    assert "on" in data, f"{path} must preserve `on` as a string key"
    assert True not in data, f"{path} parsed the `on` key as a boolean"
    return data

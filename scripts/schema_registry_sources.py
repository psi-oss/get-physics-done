"""List canonical schema and registry ownership sources."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SchemaRegistrySource:
    path: str
    description: str
    pattern: bool = False


CANONICAL_SOURCES: Sequence[SchemaRegistrySource] = (
    SchemaRegistrySource(
        "src/gpd/adapters/runtime_catalog.json",
        "Runtime catalog payload that drives install flags and runtime selection.",
    ),
    SchemaRegistrySource(
        "src/gpd/adapters/runtime_catalog_schema.json",
        "Schema shape that validates every runtime catalog entry.",
    ),
    SchemaRegistrySource(
        "src/gpd/adapters/runtime_catalog.py",
        "Catalog loader, validator, and adapter registry helpers.",
    ),
    SchemaRegistrySource(
        "src/gpd/mcp/builtin_servers.py",
        "Builder for the MCP registry whose output lands under infra/gpd-*.json.",
    ),
    SchemaRegistrySource(
        "infra/gpd-*.json",
        "Generated MCP descriptor payloads derived from builtin servers.",
        pattern=True,
    ),
    SchemaRegistrySource(
        "src/gpd/core/public_surface_contract.json",
        "Public surface contract that documents CLI command contracts.",
    ),
    SchemaRegistrySource(
        "src/gpd/core/public_surface_contract_schema.json",
        "Schema that constrains the public surface contract structure.",
    ),
    SchemaRegistrySource(
        "src/gpd/core/public_surface_contract.py",
        "Validator and loader for the public surface contract schema.",
    ),
    SchemaRegistrySource(
        "src/gpd/core/model_visible_sections.py",
        "Shared rendering rules that keep schema sections visible to models.",
    ),
    SchemaRegistrySource(
        "src/gpd/specs/templates/",
        "Canonical contract and prompt templates referenced by runtime prompts.",
    ),
)


def render_table() -> str:
    header = "| Source | Description |"
    separator = "|--------|-------------|"
    rows = [f"| `{source.path}` | {source.description} |" for source in CANONICAL_SOURCES]
    return "\n".join((header, separator, *rows))


def main() -> None:
    print(render_table())


if __name__ == "__main__":
    main()

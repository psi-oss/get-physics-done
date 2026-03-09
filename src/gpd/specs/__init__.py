"""GPD physics specs — agents, references, protocols, templates, workflows."""

from pathlib import Path

SPECS_DIR = Path(__file__).parent


def specs_path(*parts: str) -> Path:
    """Resolve a path relative to the specs directory."""
    return SPECS_DIR.joinpath(*parts)


__all__ = ["SPECS_DIR", "specs_path"]

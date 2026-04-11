"""GPD -- Get Physics Done: unified physics research orchestration."""

from importlib import import_module
import sys

if sys.version_info < (3, 11):
    raise RuntimeError(
        "get-physics-done requires Python 3.11+; "
        f"current interpreter is Python {sys.version_info.major}.{sys.version_info.minor}"
    )

__version__ = import_module("gpd.version").__version__

__all__ = ["__version__"]

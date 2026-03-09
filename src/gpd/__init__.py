"""GPD -- Get Physics Done: unified physics research orchestration."""

# Allow other packages (e.g. gpd-strategy) to extend the gpd namespace
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from gpd.version import __version__

__all__ = ["__version__"]

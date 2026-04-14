"""Validate runtime catalog JSON through the adapter-owned loader."""

from __future__ import annotations

from gpd.adapters import runtime_catalog


def validate_runtime_catalog_schema() -> None:
    """Fail if runtime catalog schema or entries drift from adapter contracts."""

    runtime_catalog._load_runtime_catalog_schema_shape.cache_clear()
    runtime_catalog._load_catalog.cache_clear()
    try:
        runtime_catalog.iter_runtime_descriptors()
    finally:
        runtime_catalog._load_runtime_catalog_schema_shape.cache_clear()
        runtime_catalog._load_catalog.cache_clear()


def main() -> None:
    validate_runtime_catalog_schema()
    print("Runtime catalog schema guard passed.")


if __name__ == "__main__":
    main()

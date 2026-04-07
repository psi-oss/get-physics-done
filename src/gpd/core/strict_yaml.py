"""Shared strict YAML loading utilities."""

from __future__ import annotations

import yaml

__all__ = ["StrictYAMLLoader", "load_strict_yaml"]


class StrictYAMLLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys at any depth."""


def _strict_yaml_construct_mapping(loader: yaml.SafeLoader, node, deep: bool = False) -> dict[object, object]:
    """Construct one YAML mapping while rejecting duplicate keys."""

    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            is_duplicate = key in mapping
        except TypeError as exc:  # pragma: no cover - defensive YAML safety guard
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found unhashable key {key!r}",
                key_node.start_mark,
            ) from exc
        if is_duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictYAMLLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _strict_yaml_construct_mapping)


def load_strict_yaml(content: str) -> object:
    """Load YAML while rejecting duplicate mapping keys."""

    return yaml.load(content, Loader=StrictYAMLLoader)

"""Tests for shared strict YAML loading behavior."""

from __future__ import annotations

import pytest
import yaml

from gpd.core.strict_yaml import load_strict_yaml


def test_load_strict_yaml_rejects_duplicate_mapping_keys() -> None:
    payload = "name: first\nname: second\n"

    with pytest.raises(yaml.constructor.ConstructorError, match="found duplicate key"):
        load_strict_yaml(payload)

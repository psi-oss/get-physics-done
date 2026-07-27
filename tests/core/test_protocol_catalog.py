"""Tests for the transport-neutral protocol catalog in gpd.core.protocol_catalog."""

from __future__ import annotations

import json

import pytest

from gpd.core.protocol_catalog import (
    MAX_ROUTED_PROTOCOLS,
    PROTOCOL_DOMAINS_MANIFEST,
    PROTOCOL_USAGE_CAUTION,
    PROTOCOLS_DIR,
    ProtocolStore,
    available_protocol_names,
    extract_protocol_sections,
    extract_protocol_steps_and_checkpoints,
    protocol_checkpoints_payload,
    protocol_detail_payload,
    protocol_domain_values,
    protocol_listing_payload,
    protocol_route_payload,
)

_KNOWN_PROTOCOL = "perturbation-theory"
_KNOWN_DOMAIN = "gr_cosmology"


@pytest.fixture(scope="module")
def store() -> ProtocolStore:
    return ProtocolStore(PROTOCOLS_DIR)


def _routed_query(store: ProtocolStore, name: str) -> str:
    protocol = store.get(name)
    assert protocol is not None
    return " ".join(str(keyword) for keyword in protocol["load_when"])


def test_catalog_loads_every_shipped_protocol_file(store: ProtocolStore) -> None:
    listed = store.list_all()
    shipped_names = {path.stem for path in PROTOCOLS_DIR.glob("*.md")}

    assert len(listed) >= 40
    assert {str(entry["name"]) for entry in listed} == shipped_names
    assert [entry["tier"] for entry in listed] == sorted(int(entry["tier"]) for entry in listed)


def test_protocol_detail_payload_exposes_parsed_protocol_fields(store: ProtocolStore) -> None:
    payload = protocol_detail_payload(store, _KNOWN_PROTOCOL)

    assert payload is not None
    assert payload["name"] == _KNOWN_PROTOCOL
    assert payload["domain"] == "core_derivation"
    assert isinstance(payload["title"], str) and payload["title"].strip()
    assert payload["load_when"], "perturbation-theory ships routing keywords"
    assert len(payload["steps"]) > 0
    assert len(payload["checkpoints"]) > 0
    assert payload["content"].lstrip().startswith("#")
    assert payload["usage_caution"] == PROTOCOL_USAGE_CAUTION

    sections = extract_protocol_sections(str(payload["content"]))
    assert len(sections) > 1
    assert all(1 <= int(section["level"]) <= 4 for section in sections)
    assert all(str(section["title"]).strip() for section in sections)


def test_unknown_protocol_name_is_rejected_with_the_available_name_list(store: ProtocolStore) -> None:
    assert protocol_detail_payload(store, "no-such-protocol") is None
    assert protocol_checkpoints_payload(store, "no-such-protocol") is None

    available = available_protocol_names(store)
    assert "no-such-protocol" not in available
    assert _KNOWN_PROTOCOL in available
    assert available == [str(entry["name"]) for entry in store.list_all()]


def test_routing_ranks_the_protocol_owning_the_query_keywords_first(store: ProtocolStore) -> None:
    payload = protocol_route_payload(store, _routed_query(store, _KNOWN_PROTOCOL))
    ranked = payload["protocols"]

    assert ranked[0]["name"] == _KNOWN_PROTOCOL
    assert ranked[0]["relevance_score"] > ranked[1]["relevance_score"]
    assert payload["match_count"] >= len(ranked)
    assert len(ranked) <= MAX_ROUTED_PROTOCOLS
    assert payload["usage_caution"] == PROTOCOL_USAGE_CAUTION


def test_routing_ranks_a_natural_language_query_against_load_when_keywords(store: ProtocolStore) -> None:
    payload = protocol_route_payload(store, "one-loop Feynman diagram with a symmetry factor and Ward identity check")

    assert payload["protocols"][0]["name"] == _KNOWN_PROTOCOL
    assert payload["query"] == "one-loop Feynman diagram with a symmetry factor and Ward identity check"


def test_listing_payload_domain_filter_returns_only_that_domain(store: ProtocolStore) -> None:
    unfiltered = protocol_listing_payload(store)
    filtered = protocol_listing_payload(store, _KNOWN_DOMAIN)

    assert {str(entry["domain"]) for entry in filtered["protocols"]} == {_KNOWN_DOMAIN}
    assert 0 < filtered["count"] < unfiltered["count"]
    assert filtered["count"] == len(filtered["protocols"])
    assert filtered["available_domains"] == unfiltered["available_domains"] == store.domains


def test_listing_payload_rejects_a_domain_outside_the_manifest(store: ProtocolStore) -> None:
    with pytest.raises(ValueError, match="Unknown protocol domain: typo-domain"):
        protocol_listing_payload(store, "typo-domain")


def test_domain_values_match_the_shipped_manifest_and_loaded_store(store: ProtocolStore) -> None:
    manifest = json.loads(PROTOCOL_DOMAINS_MANIFEST.read_text(encoding="utf-8"))

    assert protocol_domain_values() == tuple(sorted(set(manifest["protocol_domains"].values())))
    assert list(protocol_domain_values()) == store.domains


def test_checkpoints_payload_is_populated_for_a_protocol_with_checkpoints(store: ProtocolStore) -> None:
    payload = protocol_checkpoints_payload(store, _KNOWN_PROTOCOL)

    assert payload is not None
    assert payload["name"] == _KNOWN_PROTOCOL
    assert payload["checkpoint_count"] == len(payload["checkpoints"])
    assert payload["checkpoint_count"] > 0
    assert all(isinstance(item, str) and item.strip() for item in payload["checkpoints"])
    assert payload["usage_caution"] == PROTOCOL_USAGE_CAUTION


def test_steps_and_checkpoints_split_by_section_heading() -> None:
    body = (
        "# Demo Protocol\n"
        "## Procedure\n"
        "1. Identify the small parameter\n"
        "2. Expand to desired order\n"
        "## Verification Checkpoints\n"
        "- Check the convergence radius\n"
        "## Notes\n"
        "- Not a step or a checkpoint\n"
    )

    steps, checkpoints = extract_protocol_steps_and_checkpoints(body)

    assert steps == ["Identify the small parameter", "Expand to desired order"]
    assert checkpoints == ["Check the convergence radius"]


def test_store_fails_closed_on_a_protocol_missing_domain_metadata(tmp_path) -> None:
    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "demo.md").write_text("---\ntier: 1\n---\n# Demo\n", encoding="utf-8")

    with pytest.raises(ValueError, match="'demo' is missing domain metadata"):
        ProtocolStore(protocols_dir, domain_manifest_loader=dict)

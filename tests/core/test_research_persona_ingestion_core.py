from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from gpd.core.research_persona import ResearchPersonaPatch
from gpd.core.research_persona_ingestion import (
    ResearchPersonaEvidencePacket,
    ResearchPersonaSourceDocument,
    build_research_persona_evidence_packet_from_sources,
    build_research_persona_ingestion_payload,
    build_research_persona_patch_from_sources,
    normalize_research_persona_source_document,
    summarize_research_persona_evidence_packet,
)

KIND_INTERVIEW = "interview"
KIND_USER_STATEMENT = "user_statement"
KIND_PAPER = "paper_import"
KIND_BIBTEX = "bibtex_import"
PRIVATE_LABEL = "private_local"
PROJECT_LABEL = "project_private"
PUBLIC_LABEL = "safe_to_share"
NEVER_LABEL = "never_prompt"
CONFIDENCE_INFERRED = "inferred"
CONFIDENCE_CONFIRMED = "confirmed"
SECRET_NEVER_PROMPT_TOKEN = "SECRET_NEVER_PROMPT_PERSONA_8128"

COMMON_PERSONA_TEXT = """
Research areas: conformal bootstrap; quantum field theory
Tools: Python, Mathematica, pytest
Collaborators: Ada Lovelace; Emmy Noether
Expertise: spectral methods; symbolic computation
Workstyle: Prefers concise proof-first implementation plans
Scientific taste: Values solvable toy models and fundamental theory
"""


def _facts_by_category(patch: ResearchPersonaPatch) -> dict[str, list[str]]:
    facts: dict[str, list[str]] = {}
    for operation in patch.operations:
        assert operation.fact is not None
        facts.setdefault(operation.fact.category, []).append(operation.fact.value)
    return facts


def _fact_privacies(patch: ResearchPersonaPatch) -> dict[str, set[str]]:
    labels: dict[str, set[str]] = {}
    for operation in patch.operations:
        assert operation.fact is not None
        labels.setdefault(operation.fact.category, set()).add(operation.fact.privacy)
    return labels


def test_source_document_normalizes_metadata_and_rejects_empty_sources() -> None:
    document = normalize_research_persona_source_document(
        {
            "source_kind": KIND_INTERVIEW,
            "text": "  Tools: Python  ",
            "metadata": {" Research Areas ": ["quantum gravity", "scattering amplitudes"], "blank": ""},
            "safe_to_share": True,
        }
    )

    assert isinstance(document, ResearchPersonaSourceDocument)
    assert document.source_kind == KIND_INTERVIEW
    assert document.metadata["research_areas"]
    assert "blank" not in document.metadata
    assert document.safe_to_share is True

    with pytest.raises(ValidationError):
        ResearchPersonaSourceDocument(source_kind=KIND_INTERVIEW)


def test_ingestion_payload_accepts_common_source_json_aliases() -> None:
    payloads = [
        {
            "kind": "paper",
            "title": "Alias-normalized profile paper",
            "summary": "Research areas: conformal bootstrap",
        },
        {"sources": [{"type": "bib", "content": "@article{alias2026,title={Alias BibTeX},year={2026}}"}]},
        {"documents": [{"kind": "user", "statement": "Tools: Python"}]},
    ]

    for source_document in payloads:
        payload = build_research_persona_ingestion_payload(source_document=source_document)
        patch = ResearchPersonaPatch.model_validate(payload["patch"])

        assert patch.operations


def test_build_patch_extracts_common_persona_fields_without_storage_side_effects() -> None:
    patch = build_research_persona_patch_from_sources(
        [
            {
                "source_kind": KIND_USER_STATEMENT,
                "text": COMMON_PERSONA_TEXT,
                "title": "approved interview notes",
            }
        ]
    )
    facts = _facts_by_category(patch)
    expected_categories = {
        "collaborator",
        "expertise",
        "research_area",
        "scientific_taste",
        "tool",
        "workstyle",
    }

    assert isinstance(patch, ResearchPersonaPatch)
    assert {operation.op for operation in patch.operations} == {"upsert_fact"}
    assert expected_categories <= set(facts)
    assert {operation.fact.confidence for operation in patch.operations if operation.fact} == {CONFIDENCE_INFERRED}
    assert {operation.fact.privacy for operation in patch.operations if operation.fact} == {PRIVATE_LABEL}
    assert patch.evidence
    assert not patch.tombstones


def test_confirmed_flag_is_the_only_default_route_to_confirmed_facts() -> None:
    inferred = build_research_persona_patch_from_sources([{"source_kind": KIND_INTERVIEW, "text": "Tools: Julia"}])
    confirmed = build_research_persona_patch_from_sources(
        [{"source_kind": KIND_INTERVIEW, "text": "Tools: Julia", "confirmed": True}]
    )

    assert {operation.fact.confidence for operation in inferred.operations if operation.fact} == {CONFIDENCE_INFERRED}
    assert {operation.fact.confidence for operation in confirmed.operations if operation.fact} == {CONFIDENCE_CONFIRMED}


def test_paper_import_privacy_defaults_split_public_citations_from_project_notes() -> None:
    patch = build_research_persona_patch_from_sources(
        [
            {
                "source_kind": KIND_PAPER,
                "title": "Bootstrap Bounds for Toy Models",
                "text": "Research areas: scattering amplitudes\nTools: JAX",
                "metadata": {
                    "authors": "A. Researcher",
                    "year": 2026,
                    "doi": "10.1000/example",
                    "arxiv_id": "2606.00001",
                },
            }
        ]
    )
    labels = _fact_privacies(patch)

    assert labels["paper"] == {PUBLIC_LABEL}
    assert labels["reference"] == {PUBLIC_LABEL}
    assert labels["research_area"] == {PROJECT_LABEL}
    assert labels["tool"] == {PROJECT_LABEL}


def test_bibtex_ingestion_extracts_public_reference_facts() -> None:
    patch = build_research_persona_patch_from_sources(
        [
            {
                "source_kind": KIND_BIBTEX,
                "text": """
@article{demo2026,
  title={Deterministic Profiles for Physics Agents},
  author={Curie, Marie and Fermi, Enrico},
  year={2026},
  doi={10.1000/bib-demo},
  archivePrefix={arXiv},
  eprint={2606.00002}
}
""",
            }
        ]
    )
    facts = _facts_by_category(patch)
    labels = _fact_privacies(patch)

    assert facts["paper"]
    assert len(facts["reference"]) >= 2
    assert labels["paper"] == {PUBLIC_LABEL}
    assert labels["reference"] == {PUBLIC_LABEL}


def test_never_prompt_source_redacts_prompt_facing_packet_summary() -> None:
    packet = build_research_persona_evidence_packet_from_sources(
        [
            {
                "source_kind": KIND_USER_STATEMENT,
                "text": f"Tools: {SECRET_NEVER_PROMPT_TOKEN}",
                "locator": f"notes/{SECRET_NEVER_PROMPT_TOKEN}.md",
                "privacy": NEVER_LABEL,
            }
        ]
    )
    summary = summarize_research_persona_evidence_packet(packet)
    rendered = json.dumps(summary, sort_keys=True)

    assert isinstance(packet, ResearchPersonaEvidencePacket)
    assert packet.facts[0].privacy == NEVER_LABEL
    assert SECRET_NEVER_PROMPT_TOKEN not in rendered
    assert all(SECRET_NEVER_PROMPT_TOKEN not in (item.summary or "") for item in packet.evidence)
    assert all(item.locator == "never_prompt_source" for item in packet.evidence)


def test_safe_to_share_must_be_explicit_for_user_statements() -> None:
    private_patch = build_research_persona_patch_from_sources(
        [{"source_kind": KIND_USER_STATEMENT, "text": "Tools: Python"}]
    )
    public_patch = build_research_persona_patch_from_sources(
        [{"source_kind": KIND_USER_STATEMENT, "text": "Tools: Python", "safe_to_share": True}]
    )

    assert {operation.fact.privacy for operation in private_patch.operations if operation.fact} == {PRIVATE_LABEL}
    assert {operation.fact.privacy for operation in public_patch.operations if operation.fact} == {PUBLIC_LABEL}


def test_packet_summary_counts_without_fact_values() -> None:
    packet = build_research_persona_evidence_packet_from_sources(
        [{"source_kind": KIND_INTERVIEW, "text": COMMON_PERSONA_TEXT}]
    )
    summary = summarize_research_persona_evidence_packet(packet)

    assert summary["document_count"] == 1
    assert summary["evidence_count"] == 1
    assert summary["fact_count"] == len(packet.facts)
    assert set(summary["facts_by_category"]) >= {"tool", "workstyle"}
    assert "Python" not in json.dumps(summary)

"""Tests for gpd.strategy.type_bridge — bidirectional type conversions + adapters."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from agentic_builder.engine.blackboard_protocol import (
    BlackboardEntry as EngineEntry,
)
from agentic_builder.engine.blackboard_protocol import (
    BlackboardWriteRequest as EngineWriteRequest,
)
from agentic_builder.engine.blackboard_protocol import (
    CurationDecision as EngineCurationDecision,
)
from psi_contracts.blackboard import (
    BlackboardEntry as ContractEntry,
)
from psi_contracts.blackboard import (
    CurationDecision as ContractCurationDecision,
)

from gpd.strategy.type_bridge import (
    BlackboardStoreAdapter,
    WriteGateAdapter,
    contract_decision_to_engine,
    contract_entry_to_engine,
    dict_to_engine_entry,
    engine_decision_to_contract,
    engine_entry_to_contract,
    engine_write_request_to_contract,
)

# ---------------------------------------------------------------------------
# BlackboardEntry conversions
# ---------------------------------------------------------------------------


class TestEntryConversions:
    def test_engine_to_contract(self):
        engine = EngineEntry(
            entry_id="e1",
            kind="equation",
            content="E=mc^2",
            tags=["physics", "relativity"],
            source_branch="branch-1",
            confidence=0.95,
        )
        contract = engine_entry_to_contract(engine)
        assert contract.id == "e1"
        assert contract.node_type == "equation"
        assert contract.label == "equation"
        assert contract.content == "E=mc^2"
        assert contract.tags == ["physics", "relativity"]
        assert contract.confidence == 0.95
        assert contract.metadata["source_branch"] == "branch-1"

    def test_contract_to_engine(self):
        contract = ContractEntry(
            id="c1",
            node_type="result",
            label="Main result",
            content="x = 42",
            tags=["final"],
            confidence=0.8,
            metadata={"source_branch": "branch-2"},
        )
        engine = contract_entry_to_engine(contract)
        assert engine.entry_id == "c1"
        assert engine.kind == "result"
        assert engine.content == "x = 42"
        assert engine.tags == ["final"]
        assert engine.source_branch == "branch-2"
        assert engine.confidence == 0.8

    def test_contract_to_engine_no_metadata(self):
        contract = ContractEntry(
            id="c2",
            node_type="assumption",
            label="Assumption",
            content="assume x > 0",
            tags=[],
        )
        engine = contract_entry_to_engine(contract)
        assert engine.source_branch == ""

    def test_roundtrip_engine_contract_engine(self):
        original = EngineEntry(
            entry_id="rt1",
            kind="theorem",
            content="For all n...",
            tags=["math"],
            source_branch="br",
            confidence=0.99,
        )
        roundtripped = contract_entry_to_engine(engine_entry_to_contract(original))
        assert roundtripped.entry_id == original.entry_id
        assert roundtripped.kind == original.kind
        assert roundtripped.content == original.content
        assert roundtripped.tags == original.tags
        assert roundtripped.source_branch == original.source_branch
        assert roundtripped.confidence == original.confidence


# ---------------------------------------------------------------------------
# CurationDecision conversions
# ---------------------------------------------------------------------------


class TestDecisionConversions:
    def test_engine_to_contract(self):
        engine = EngineCurationDecision(approved=True, reason="looks good")
        contract = engine_decision_to_contract(engine)
        assert contract.approved is True
        assert contract.reason == "looks good"

    def test_contract_to_engine(self):
        contract = ContractCurationDecision(
            approved=False,
            reason="dimensional mismatch",
            suggested_edits="fix units",
        )
        engine = contract_decision_to_engine(contract)
        assert engine.approved is False
        assert engine.reason == "dimensional mismatch"

    def test_roundtrip(self):
        original = EngineCurationDecision(approved=True, reason="ok")
        rt = contract_decision_to_engine(engine_decision_to_contract(original))
        assert rt.approved == original.approved
        assert rt.reason == original.reason


# ---------------------------------------------------------------------------
# dict_to_engine_entry
# ---------------------------------------------------------------------------


class TestDictToEngine:
    def test_full_dict(self):
        row = {
            "node_id": "n1",
            "node_type": "equation",
            "content": "F=ma",
            "tags": json.dumps(["mechanics"]),
            "confidence": 0.9,
            "branch_node_id": "br1",
        }
        entry = dict_to_engine_entry(row)
        assert entry.entry_id == "n1"
        assert entry.kind == "equation"
        assert entry.content == "F=ma"
        assert entry.tags == ["mechanics"]
        assert entry.confidence == 0.9
        assert entry.source_branch == "br1"

    def test_tags_as_list(self):
        row = {"node_id": "n2", "node_type": "x", "content": "", "tags": ["a", "b"]}
        entry = dict_to_engine_entry(row)
        assert entry.tags == ["a", "b"]

    def test_missing_fields_get_defaults(self):
        entry = dict_to_engine_entry({})
        assert entry.entry_id == ""
        assert entry.kind == ""
        assert entry.content == ""
        assert entry.tags == []
        assert entry.confidence == 1.0
        assert entry.source_branch == ""

    def test_none_confidence(self):
        row = {"confidence": None}
        entry = dict_to_engine_entry(row)
        assert entry.confidence == 1.0

    def test_none_branch_node_id(self):
        row = {"branch_node_id": None}
        entry = dict_to_engine_entry(row)
        assert entry.source_branch == ""


# ---------------------------------------------------------------------------
# engine_write_request_to_contract
# ---------------------------------------------------------------------------


class TestWriteRequestConversion:
    def test_basic_conversion(self):
        req = EngineWriteRequest(
            kind="result",
            content="answer is 42",
            tags=["final"],
            source_branch="br",
            confidence=0.8,
        )
        contract = engine_write_request_to_contract(req)
        assert contract.kind == "result"
        assert contract.content == "answer is 42"
        assert contract.tags == ["final"]
        assert contract.source_branch == "br"
        assert contract.confidence == 0.8


# ---------------------------------------------------------------------------
# BlackboardStoreAdapter
# ---------------------------------------------------------------------------


class TestBlackboardStoreAdapter:
    def _make_adapter(self):
        store = MagicMock()
        adapter = BlackboardStoreAdapter(store, campaign_id="camp1")
        return adapter, store

    def test_query(self):
        adapter, store = self._make_adapter()
        store.query_nodes.return_value = [
            {"node_id": "n1", "node_type": "eq", "content": "x=1", "tags": "[]", "confidence": 0.5}
        ]
        results = adapter.query(tags=["physics"], kind="eq", limit=10)
        store.query_nodes.assert_called_once_with(tags=["physics"], node_types=["eq"], limit=10)
        assert len(results) == 1
        assert results[0].entry_id == "n1"

    def test_query_no_kind(self):
        adapter, store = self._make_adapter()
        store.query_nodes.return_value = []
        adapter.query(tags=["a"])
        store.query_nodes.assert_called_once_with(tags=["a"], node_types=None, limit=50)

    def test_get_found(self):
        adapter, store = self._make_adapter()
        store.get_node.return_value = {"node_id": "x", "node_type": "t", "content": "c", "tags": "[]"}
        result = adapter.get("x")
        assert result is not None
        assert result.entry_id == "x"

    def test_get_not_found(self):
        adapter, store = self._make_adapter()
        store.get_node.return_value = None
        assert adapter.get("missing") is None

    def test_search(self):
        adapter, store = self._make_adapter()
        store.search_text.return_value = [{"node_id": "s1", "node_type": "r", "content": "found", "tags": "[]"}]
        results = adapter.search("found", limit=5)
        store.search_text.assert_called_once_with("found", limit=5)
        assert len(results) == 1

    def test_request_write(self):
        adapter, store = self._make_adapter()
        req = EngineWriteRequest(
            kind="result",
            content="something",
            tags=["tag1"],
            confidence=0.7,
        )
        entry_id = adapter.request_write(req)
        assert isinstance(entry_id, str)
        assert len(entry_id) > 0
        store.add_node.assert_called_once()
        call_kwargs = store.add_node.call_args
        assert call_kwargs.kwargs["node_type"] == "result"
        assert call_kwargs.kwargs["content"] == "something"


# ---------------------------------------------------------------------------
# WriteGateAdapter
# ---------------------------------------------------------------------------


class TestWriteGateAdapter:
    @pytest.mark.asyncio
    async def test_evaluate_approved(self):
        curator = MagicMock()
        curator.evaluate = AsyncMock(return_value=ContractCurationDecision(approved=True, reason="ok"))
        adapter = WriteGateAdapter(curator)

        req = EngineWriteRequest(kind="eq", content="E=mc^2", tags=["physics"])
        decision = await adapter.evaluate(req, {"key": "val"})

        assert decision.approved is True
        assert decision.reason == "ok"
        curator.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_rejected(self):
        curator = MagicMock()
        curator.evaluate = AsyncMock(return_value=ContractCurationDecision(approved=False, reason="bad dimensions"))
        adapter = WriteGateAdapter(curator)

        req = EngineWriteRequest(kind="eq", content="x=1")
        decision = await adapter.evaluate(req, {})

        assert decision.approved is False
        assert "dimensions" in decision.reason

"""Type bridge — conversion functions between engine dataclasses and contract Pydantic models.

The MCTS engine (Layer 1) defines pure frozen dataclasses with zero framework
imports.  The contracts package (Layer 2) defines Pydantic BaseModels for
cross-tool/package boundaries.  This module provides bidirectional conversion
functions and adapter classes that bridge the two layers.

Architecture rationale for *intentional* duplication:
- engine types:   frozen dataclasses, stdlib-only, no validation overhead
- contract types: Pydantic models with field validators, serialization, OpenAPI
Both are needed — engine types for hot-path algorithms, contract types for
API boundaries.  The bridge functions here are the ONLY place where both are
imported together.

Also provides BlackboardStoreAdapter, which wraps the research-memory
BlackboardStore (Layer 1, returns raw dicts) and satisfies the engine
BlackboardReader / BlackboardWriter protocols.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
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
        BlackboardWriteRequest as ContractWriteRequest,
    )
    from psi_contracts.blackboard import (
        CurationDecision as ContractCurationDecision,
    )
    from research_memory.blackboard.store import BlackboardStore

    from gpd.strategy.curator import PhysicsCurator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BlackboardEntry conversions
# ---------------------------------------------------------------------------


def engine_entry_to_contract(entry: EngineEntry) -> ContractEntry:
    """Convert engine BlackboardEntry (dataclass) -> contract BlackboardEntry (Pydantic).

    Field mapping:
        engine.entry_id   -> contract.id
        engine.kind        -> contract.node_type
        engine.content     -> contract.content
        engine.tags        -> contract.tags
        engine.confidence  -> contract.confidence
        (no source_branch) -> contract.metadata["source_branch"]
        (no label)         -> contract.label = engine.kind
    """
    from psi_contracts.blackboard import BlackboardEntry as _ContractEntry

    return _ContractEntry(
        id=entry.entry_id,
        node_type=entry.kind,
        label=entry.kind,
        content=entry.content,
        tags=list(entry.tags),
        confidence=entry.confidence,
        metadata={"source_branch": entry.source_branch},
    )


def contract_entry_to_engine(entry: ContractEntry) -> EngineEntry:
    """Convert contract BlackboardEntry (Pydantic) -> engine BlackboardEntry (dataclass).

    Field mapping:
        contract.id        -> engine.entry_id
        contract.node_type -> engine.kind
        contract.content   -> engine.content
        contract.tags      -> engine.tags
        contract.confidence-> engine.confidence
        contract.metadata.get("source_branch", "") -> engine.source_branch
    """
    from agentic_builder.engine.blackboard_protocol import BlackboardEntry as _EngineEntry

    metadata = entry.metadata if hasattr(entry, "metadata") else {}
    source_branch = metadata.get("source_branch", "") if isinstance(metadata, dict) else ""

    return _EngineEntry(
        entry_id=entry.id,
        kind=entry.node_type,
        content=entry.content,
        tags=list(entry.tags),
        source_branch=source_branch,
        confidence=entry.confidence,
    )


# ---------------------------------------------------------------------------
# CurationDecision conversions
# ---------------------------------------------------------------------------


def engine_decision_to_contract(decision: EngineCurationDecision) -> ContractCurationDecision:
    """Convert engine CurationDecision (dataclass) -> contract CurationDecision (Pydantic).

    The contract version has an extra ``suggested_edits`` field (defaults to None).
    """
    from psi_contracts.blackboard import CurationDecision as _ContractDecision

    return _ContractDecision(
        approved=decision.approved,
        reason=decision.reason,
    )


def contract_decision_to_engine(decision: ContractCurationDecision) -> EngineCurationDecision:
    """Convert contract CurationDecision (Pydantic) -> engine CurationDecision (dataclass).

    The contract's ``suggested_edits`` field is dropped (engine doesn't have it).
    """
    from agentic_builder.engine.blackboard_protocol import CurationDecision as _EngineDecision

    return _EngineDecision(
        approved=decision.approved,
        reason=decision.reason,
    )


# ---------------------------------------------------------------------------
# Dict <-> engine entry conversion (for BlackboardStore raw dicts)
# ---------------------------------------------------------------------------


def dict_to_engine_entry(row: dict[str, object]) -> EngineEntry:
    """Convert a BlackboardStore row dict -> engine BlackboardEntry dataclass.

    BlackboardStore.query_nodes() returns dicts with keys matching the SQL schema:
    node_id, node_type, label, content, tags (JSON string), confidence, status,
    metadata (JSON string), campaign_id, branch_node_id, created_at.
    """
    import json

    from agentic_builder.engine.blackboard_protocol import BlackboardEntry as _EngineEntry

    tags_raw = row.get("tags", "[]")
    if isinstance(tags_raw, str):
        tags = json.loads(tags_raw)
    elif isinstance(tags_raw, list):
        tags = tags_raw
    else:
        tags = []

    confidence_raw = row.get("confidence", 1.0)
    confidence = float(confidence_raw) if confidence_raw is not None else 1.0

    return _EngineEntry(
        entry_id=str(row.get("node_id", "")),
        kind=str(row.get("node_type", "")),
        content=str(row.get("content", "")),
        tags=tags,
        source_branch=str(row.get("branch_node_id", "") or ""),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# BlackboardStoreAdapter
# ---------------------------------------------------------------------------


class BlackboardStoreAdapter:
    """Wraps a research-memory BlackboardStore and satisfies engine protocols.

    Implements:
    - BlackboardReader: query(), get(), search()
    - BlackboardWriter: request_write()

    The engine protocols return engine-level dataclasses. This adapter converts
    the raw dicts from BlackboardStore into engine BlackboardEntry objects.
    """

    def __init__(self, store: BlackboardStore, campaign_id: str = "") -> None:
        self._store = store
        self._campaign_id = campaign_id

    # -- BlackboardReader --

    def query(self, *, tags: list[str], kind: str | None = None, limit: int = 50) -> list[EngineEntry]:
        """Return entries matching tags and optional kind filter."""
        node_types = [kind] if kind else None
        rows = self._store.query_nodes(tags=tags, node_types=node_types, limit=limit)
        return [dict_to_engine_entry(r) for r in rows]

    def get(self, entry_id: str) -> EngineEntry | None:
        """Retrieve a single entry by its identifier."""
        row = self._store.get_node(entry_id)
        if row is None:
            return None
        return dict_to_engine_entry(row)

    def search(self, query: str, limit: int = 10) -> list[EngineEntry]:
        """Free-text search over entry content."""
        rows = self._store.search_text(query, limit=limit)
        return [dict_to_engine_entry(r) for r in rows]

    # -- BlackboardWriter --

    def request_write(self, request: EngineWriteRequest) -> str:
        """Submit a write request and return the assigned entry ID.

        Accepts an engine BlackboardWriteRequest dataclass.
        """
        entry_id = str(uuid4())
        tags = list(request.tags)
        self._store.add_node(
            node_id=entry_id,
            node_type=request.kind,
            label=request.kind,
            content=request.content,
            tags=tags,
            confidence=request.confidence,
            branch_node_id=getattr(request, "source_branch", None),
        )
        return entry_id


# ---------------------------------------------------------------------------
# WriteGateAdapter — bridges curator (contract types) to engine protocol
# ---------------------------------------------------------------------------


def engine_write_request_to_contract(request: EngineWriteRequest) -> ContractWriteRequest:
    """Convert engine BlackboardWriteRequest (dataclass) -> contract BlackboardWriteRequest (Pydantic)."""
    from psi_contracts.blackboard import BlackboardWriteRequest as _ContractWriteRequest

    return _ContractWriteRequest(
        kind=request.kind,
        content=request.content,
        tags=list(request.tags),
        source_branch=getattr(request, "source_branch", ""),
        confidence=getattr(request, "confidence", 1.0),
    )


class WriteGateAdapter:
    """Adapts a PhysicsCurator (contract types) to the engine WriteGateProvider protocol.

    The engine passes engine-level frozen dataclasses to ``evaluate()``.
    This adapter converts them to contract Pydantic models before calling
    the curator, then converts the contract CurationDecision back to an
    engine CurationDecision.
    """

    def __init__(self, curator: PhysicsCurator) -> None:
        self._curator = curator

    async def evaluate(self, request: EngineWriteRequest, current_state: dict[str, object]) -> EngineCurationDecision:
        """Bridge engine -> contract -> curator -> contract -> engine."""
        contract_request = engine_write_request_to_contract(request)
        contract_decision = await self._curator.evaluate(contract_request, current_state)
        return contract_decision_to_engine(contract_decision)

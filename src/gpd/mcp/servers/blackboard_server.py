"""MCP server for GPD blackboard knowledge graph.

Thin MCP wrapper around research_memory.blackboard.store.BlackboardStore.
Exposes search, retrieval, graph traversal, and write-proposal operations
as MCP tools for solver agents.

Usage:
    python -m gpd.mcp.servers.blackboard_server
    # or via entry point:
    gpd-mcp-blackboard
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

try:
    from research_memory.blackboard.store import BlackboardStore
except ImportError:
    raise ImportError(
        "GPD blackboard requires the research-memory package. Add research-memory to your dependencies."
    ) from None

from gpd.core.observability import gpd_span
from gpd.mcp.servers import run_mcp_server

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-blackboard")

mcp = FastMCP("gpd-blackboard")

# ---------------------------------------------------------------------------
# Lazy init
# ---------------------------------------------------------------------------

_store: BlackboardStore | None = None


def _get_store() -> BlackboardStore:
    """Lazy-init the blackboard store from env vars.

    Raises RuntimeError if BLACKBOARD_DB_PATH is not set — the MCP server
    must always be told where the run-specific blackboard lives.  Defaulting
    to a relative path would silently create databases in the repo root.
    """
    global _store
    if _store is None:
        db_path = os.environ.get("BLACKBOARD_DB_PATH", "")
        if not db_path:
            raise RuntimeError(
                "BLACKBOARD_DB_PATH environment variable not set. "
                "The blackboard MCP server requires an absolute path to the run-specific blackboard.db."
            )
        campaign_id = os.environ.get("CAMPAIGN_ID", "default")
        logger.info("Opening blackboard store: db=%s campaign=%s", db_path, campaign_id)
        _store = BlackboardStore(db_path=Path(db_path), campaign_id=campaign_id)
    return _store


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def search_blackboard(
    query: str,
    node_types: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
) -> dict[str, object]:
    """Search the blackboard knowledge graph for entries matching a query.

    Combines text search on labels/content with optional filters on
    node types and tags. Results are ordered by recency.

    Args:
        query: Free-text search query matched against labels and content.
        node_types: Optional list of node types to filter (e.g. ["equation", "result"]).
        tags: Optional list of tags — entries must have at least one matching tag.
        limit: Maximum results to return (default 20).
    """
    with gpd_span("mcp.blackboard.search", query=query):
        store = _get_store()
        entries = store.query_nodes(
            node_types=node_types,
            tags=tags,
            text_query=query,
            limit=limit,
        )
        return {
            "query": query,
            "match_count": len(entries),
            "entries": entries,
        }


@mcp.tool()
def get_entry(entry_id: str) -> dict[str, object]:
    """Get a full blackboard entry by ID, including its edges.

    Returns the entry content plus all outgoing and incoming edges,
    giving a complete picture of how this entry connects to the graph.

    Args:
        entry_id: Unique identifier of the blackboard entry.
    """
    with gpd_span("mcp.blackboard.get_entry", entry_id=entry_id):
        store = _get_store()
        node = store.get_node(entry_id)
        if node is None:
            return {"error": f"Entry '{entry_id}' not found", "entry_id": entry_id}
        outgoing = store.get_edges(entry_id, direction="outgoing")
        incoming = store.get_edges(entry_id, direction="incoming")
        return {
            "entry": node,
            "outgoing_edges": outgoing,
            "incoming_edges": incoming,
            "edge_count": len(outgoing) + len(incoming),
        }


@mcp.tool()
def get_subgraph(
    entry_id: str,
    depth: int = 2,
    edge_types: list[str] | None = None,
) -> dict[str, object]:
    """Get the neighborhood subgraph around an entry.

    Performs a BFS traversal from the given entry up to the specified
    depth, collecting all reachable nodes and edges. Optionally filter
    by edge type to follow only specific relation kinds.

    Args:
        entry_id: Starting entry ID for the traversal.
        depth: How many hops to traverse (default 2).
        edge_types: Optional list of edge types to follow (follows all if None).
    """
    with gpd_span("mcp.blackboard.get_subgraph", entry_id=entry_id, depth=depth):
        store = _get_store()

        root = store.get_node(entry_id)
        if root is None:
            return {"error": f"Entry '{entry_id}' not found", "entry_id": entry_id}

        visited_ids: set[str] = set()
        collected_edges: list[dict[str, object]] = []
        edge_ids_seen: set[str] = set()
        frontier: set[str] = {entry_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                if nid in visited_ids:
                    continue
                visited_ids.add(nid)
                edges = store.get_edges(nid, direction="both")
                for edge in edges:
                    etype = str(edge.get("edge_type", ""))
                    if edge_types and etype not in edge_types:
                        continue
                    eid = str(edge.get("edge_id", ""))
                    if eid not in edge_ids_seen:
                        edge_ids_seen.add(eid)
                        collected_edges.append(edge)
                    other = str(edge["dst"]) if str(edge["src"]) == nid else str(edge["src"])
                    if other not in visited_ids:
                        next_frontier.add(other)
            frontier = next_frontier

        # Include final-frontier nodes in visited set
        visited_ids.update(frontier)

        nodes: list[dict[str, object]] = []
        for nid in visited_ids:
            node = store.get_node(nid)
            if node is not None:
                nodes.append(node)

        return {
            "root_id": entry_id,
            "depth": depth,
            "node_count": len(nodes),
            "edge_count": len(collected_edges),
            "nodes": nodes,
            "edges": collected_edges,
        }


@mcp.tool()
def find_by_type(node_type: str, limit: int = 20) -> dict[str, object]:
    """Find all blackboard entries of a given type.

    Args:
        node_type: The node type to filter by (e.g. "equation", "assumption", "result").
        limit: Maximum results to return (default 20).
    """
    with gpd_span("mcp.blackboard.find_by_type", node_type=node_type):
        store = _get_store()
        entries = store.query_nodes(node_types=[node_type], limit=limit)
        return {
            "node_type": node_type,
            "match_count": len(entries),
            "entries": entries,
        }


@mcp.tool()
def find_related(entry_id: str, relation_type: str) -> dict[str, object]:
    """Follow typed edges from an entry to find related entries.

    Finds all entries connected to the given entry via outgoing edges
    of the specified type. For example, find all entries that a result
    "supports" or all assumptions an equation "depends_on".

    Args:
        entry_id: The source entry ID.
        relation_type: The edge type to follow (e.g. "supports", "depends_on", "derives_from").
    """
    with gpd_span("mcp.blackboard.find_related", entry_id=entry_id, relation_type=relation_type):
        store = _get_store()
        node = store.get_node(entry_id)
        if node is None:
            return {"error": f"Entry '{entry_id}' not found", "entry_id": entry_id}

        outgoing = store.get_edges(entry_id, direction="outgoing")
        matching_edges = [e for e in outgoing if str(e.get("edge_type", "")) == relation_type]

        related_nodes: list[dict[str, object]] = []
        for edge in matching_edges:
            target = store.get_node(str(edge["dst"]))
            if target is not None:
                related_nodes.append(target)

        return {
            "entry_id": entry_id,
            "relation_type": relation_type,
            "related_count": len(related_nodes),
            "related": related_nodes,
        }


@mcp.tool()
def propose_entry(
    kind: str,
    label: str,
    content: str,
    tags: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    confidence: float = 0.8,
) -> dict[str, object]:
    """Propose a new entry for the blackboard knowledge graph.

    Creates a write request that gets curated before becoming a
    permanent graph entry. The entry is added with metadata marking
    it as a proposal until the curator agent approves it.

    Args:
        kind: Entry type to create (maps to node_type, e.g. "equation", "result").
        label: Short human-readable label for the entry.
        content: Full content of the entry.
        tags: Optional tags for searchability.
        evidence_ids: Optional IDs of existing entries that support this proposal.
        confidence: Confidence score from 0 to 1 (default 0.8).
    """
    with gpd_span("mcp.blackboard.propose_entry", kind=kind):
        store = _get_store()
        request_id = uuid4().hex

        store.add_node(
            node_id=request_id,
            node_type=kind,
            label=label,
            content=content,
            tags=tags,
            confidence=confidence,
            metadata={"proposal": True, "curation_status": "pending"},
        )

        # Link evidence if provided
        linked_evidence = 0
        for eid in evidence_ids or []:
            if store.get_node(eid) is not None:
                store.add_edge(src=request_id, dst=eid, edge_type="supported_by")
                linked_evidence += 1

        return {
            "request_id": request_id,
            "status": "pending",
            "node_type": kind,
            "label": label,
            "evidence_linked": linked_evidence,
        }


@mcp.tool()
def list_entry_types() -> dict[str, object]:
    """List all node types present on the blackboard with their counts.

    Returns a summary of what kinds of entries exist and how many
    of each type are stored. Useful for understanding the current
    state of the knowledge graph.
    """
    with gpd_span("mcp.blackboard.list_entry_types"):
        store = _get_store()
        type_counts = store.count_by_type()
        return {
            "type_count": len(type_counts),
            "total_entries": sum(type_counts.values()),
            "types": type_counts,
        }


@mcp.tool()
def get_coverage(entry_ids: list[str]) -> dict[str, object]:
    """Assess evidence coverage for a set of blackboard entries.

    For each entry, counts incoming evidence edges and classifies
    whether the entry is well-supported (2+ evidence links) or
    needs more evidence. Useful for identifying weak spots in the
    knowledge graph.

    Args:
        entry_ids: List of entry IDs to assess.
    """
    with gpd_span("mcp.blackboard.get_coverage"):
        store = _get_store()
        results: list[dict[str, object]] = []

        for eid in entry_ids:
            node = store.get_node(eid)
            if node is None:
                results.append({"entry_id": eid, "found": False})
                continue

            incoming = store.get_edges(eid, direction="incoming")
            outgoing = store.get_edges(eid, direction="outgoing")
            evidence_count = len([e for e in incoming if str(e.get("edge_type", "")) == "supported_by"])

            results.append(
                {
                    "entry_id": eid,
                    "found": True,
                    "label": str(node.get("label", "")),
                    "confidence": node.get("confidence", 1.0),
                    "incoming_edges": len(incoming),
                    "outgoing_edges": len(outgoing),
                    "evidence_count": evidence_count,
                    "well_supported": evidence_count >= 2,
                }
            )

        well_supported = sum(1 for r in results if r.get("well_supported"))
        needs_evidence = sum(1 for r in results if r.get("found") and not r.get("well_supported"))

        return {
            "total_checked": len(entry_ids),
            "found": sum(1 for r in results if r.get("found")),
            "well_supported": well_supported,
            "needs_evidence": needs_evidence,
            "entries": results,
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-blackboard MCP server."""
    run_mcp_server(mcp, "GPD Blackboard MCP Server")


if __name__ == "__main__":
    main()

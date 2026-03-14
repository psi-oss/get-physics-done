"""Structural test: read_text calls near frontmatter parsing must be inside try blocks."""

import ast
from pathlib import Path


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Return a mapping from each node to its parent."""
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_read_text_call(node: ast.AST) -> bool:
    """Return True if *node* is a call like ``something.read_text(...)``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "read_text"
    )


def _is_extract_frontmatter(node: ast.AST) -> bool:
    """Return True if *node* is a call like ``_extract_frontmatter(...)``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_extract_frontmatter"
    )


def _has_try_ancestor(node: ast.AST, parents: dict, stop_at: ast.AST) -> bool:
    """Walk up from *node* towards *stop_at* and return True if a Try body is on the path."""
    current = node
    while current is not stop_at:
        parent = parents.get(current)
        if parent is None:
            break
        if isinstance(parent, ast.Try) and current in parent.body:
            return True
        current = parent
    return False


def test_read_text_calls_inside_try_blocks():
    """Ensure read_text() calls followed by _extract_frontmatter are protected by try/except."""
    source_path = Path(__file__).resolve().parents[2] / "src" / "gpd" / "core" / "phases.py"
    source = source_path.read_text()
    tree = ast.parse(source)
    parents = _build_parent_map(tree)

    violations: list[str] = []

    # Walk the entire AST looking for For loops.
    for for_node in ast.walk(tree):
        if not isinstance(for_node, ast.For):
            continue

        # Collect read_text and _extract_frontmatter calls anywhere in
        # this for-loop body (including nested structures).
        read_text_calls: list[ast.Call] = []
        fm_calls: list[ast.Call] = []
        for stmt in for_node.body:
            for child in ast.walk(stmt):
                if _is_read_text_call(child):
                    read_text_calls.append(child)
                if _is_extract_frontmatter(child):
                    fm_calls.append(child)

        if not (read_text_calls and fm_calls):
            continue

        # For each read_text call, verify it has a Try ancestor between
        # itself and the for-loop node.
        for call in read_text_calls:
            if not _has_try_ancestor(call, parents, stop_at=for_node):
                violations.append(
                    f"line {call.lineno}: read_text() call is outside try/except "
                    f"in a for-loop that also calls _extract_frontmatter"
                )

    assert not violations, (
        "read_text() calls must be inside try/except blocks when followed by "
        "_extract_frontmatter parsing. Unprotected calls:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )

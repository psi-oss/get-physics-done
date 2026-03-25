"""Consistency test: all state_server MCP tools must have error handling."""
import ast
from pathlib import Path

from gpd.core.state import default_state_dict, generate_state_markdown
from gpd.mcp.servers.state_server import get_progress


def _get_except_handler_names(handler: ast.ExceptHandler) -> set[str]:
    """Extract exception class names from an except handler.

    Handles both single exceptions (``except FooError``) and tuples
    (``except (FooError, BarError)``).
    """
    names: set[str] = set()
    if handler.type is None:
        # bare except — catches everything
        return {"*"}
    if isinstance(handler.type, ast.Name):
        names.add(handler.type.id)
    elif isinstance(handler.type, ast.Tuple):
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name):
                names.add(elt.id)
    return names


def _is_mcp_tool_decorator(node: ast.expr) -> bool:
    """Return True if *node* represents ``@mcp.tool()``."""
    # @mcp.tool()  ->  Call(func=Attribute(value=Name(id='mcp'), attr='tool'))
    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "mcp"
            and func.attr == "tool"
        ):
            return True
    return False


REQUIRED_EXCEPTIONS = {"GPDError", "OSError", "ValueError"}


def test_all_state_server_tools_have_error_handling():
    """Every @mcp.tool() in state_server.py must catch GPDError, OSError, ValueError."""
    source_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "gpd"
        / "mcp"
        / "servers"
        / "state_server.py"
    )
    source = source_path.read_text()
    tree = ast.parse(source, filename=str(source_path))

    tool_functions: list[ast.FunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if _is_mcp_tool_decorator(deco):
                    tool_functions.append(node)
                    break

    # Sanity: the server must expose at least one tool
    assert tool_functions, "No @mcp.tool() functions found — parser may be broken"

    missing_try: list[str] = []
    missing_exceptions: dict[str, set[str]] = {}

    for func in tool_functions:
        # Look for at least one Try node anywhere in the function body
        try_nodes = [n for n in ast.walk(func) if isinstance(n, ast.Try)]
        if not try_nodes:
            missing_try.append(func.name)
            continue

        # Collect all exception names caught across every handler in every
        # try/except inside the function.
        caught: set[str] = set()
        for try_node in try_nodes:
            for handler in try_node.handlers:
                caught |= _get_except_handler_names(handler)

        missing = REQUIRED_EXCEPTIONS - caught
        if missing:
            missing_exceptions[func.name] = missing

    errors: list[str] = []
    for name in missing_try:
        errors.append(f"  {name}(): missing try/except entirely")
    for name, missing in sorted(missing_exceptions.items()):
        errors.append(
            f"  {name}(): except handler does not catch {', '.join(sorted(missing))}"
        )

    assert not errors, (
        "MCP tool functions in state_server.py lack required error handling:\n"
        + "\n".join(errors)
    )


def test_state_server_has_expected_tool_count():
    """Guard against accidentally removing tools — expect at least 7."""
    source_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "gpd"
        / "mcp"
        / "servers"
        / "state_server.py"
    )
    source = source_path.read_text()
    tree = ast.parse(source, filename=str(source_path))

    tool_count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if _is_mcp_tool_decorator(deco):
                    tool_count += 1
                    break

    assert tool_count >= 7, (
        f"Expected at least 7 @mcp.tool() functions, found {tool_count}. "
        "Was a tool accidentally removed?"
    )


def test_get_progress_does_not_mutate_checkpoint_shelf_artifacts(tmp_path: Path) -> None:
    """Progress reads should not create, update, or delete checkpoint shelf files."""
    cwd = tmp_path
    planning = cwd / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()

    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["total_phases"] = 2
    state["position"]["status"] = "Executing"
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

    phase_one = planning / "phases" / "01-foundations"
    phase_one.mkdir()
    (phase_one / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_one / "01-SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    phase_two = planning / "phases" / "02-analysis"
    phase_two.mkdir()
    (phase_two / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_two / "02-SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    checkpoint_dir = cwd / "GPD" / "phase-checkpoints"
    checkpoint_dir.mkdir()
    stale_checkpoint = checkpoint_dir / "99-old-phase.md"
    stale_checkpoint.write_text("stale checkpoint\n", encoding="utf-8")
    checkpoints_index = cwd / "GPD" / "CHECKPOINTS.md"
    checkpoints_index.write_text("stale index\n", encoding="utf-8")

    result = get_progress(str(cwd))

    assert result["updated"] is True
    assert result["completed"] == 2
    assert result["total"] == 2
    assert "checkpoint_files" not in result
    assert not (checkpoint_dir / "01-foundations.md").exists()
    assert not (checkpoint_dir / "02-analysis.md").exists()
    assert stale_checkpoint.read_text(encoding="utf-8") == "stale checkpoint\n"
    assert stale_checkpoint.exists()
    assert checkpoints_index.read_text(encoding="utf-8") == "stale index\n"

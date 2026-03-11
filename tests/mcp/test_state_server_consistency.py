"""Consistency test: all state_server MCP tools must have error handling."""
import ast
from pathlib import Path


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

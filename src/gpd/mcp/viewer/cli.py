"""CLI commands for the GPD+ Frame Viewer."""

from __future__ import annotations

import json
import sys
import webbrowser

import typer
from rich.console import Console

viewer_app = typer.Typer(name="view", help="Lightweight frame viewer for MCP simulation outputs")

console = Console()

DEFAULT_PORT = 7890
DEFAULT_HOST = "127.0.0.1"


def _get_port(port: int) -> int:
    """Resolve viewer port, checking GPDPLUS_VIEWER_PORT env var."""
    if port != DEFAULT_PORT:
        return port
    import os

    return int(os.environ.get("GPDPLUS_VIEWER_PORT", str(DEFAULT_PORT)))


def _get_host(host: str) -> str:
    """Resolve viewer host, checking GPDPLUS_VIEWER_HOST env var."""
    if host != DEFAULT_HOST:
        return host
    import os

    return os.environ.get("GPDPLUS_VIEWER_HOST", DEFAULT_HOST)


@viewer_app.callback(invoke_without_command=True)
def start(
    ctx: typer.Context,
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Server host (e.g. 0.0.0.0 for all interfaces)"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open browser"),
) -> None:
    """Start the frame viewer server and open the browser.

    Usage:
        gpd-plus view                    # start on default port, open browser
        gpd-plus view --port 8080        # custom port
        gpd-plus view --host 0.0.0.0     # listen on all interfaces
        gpd-plus view --no-open          # don't open browser
    """
    if ctx.invoked_subcommand is not None:
        return

    port = _get_port(port)
    host = _get_host(host)

    console.print(f"[bold blue]GPD+ Frame Viewer[/] starting on http://{host}:{port}")
    console.print(
        f"  Push frames:  [dim]curl -X POST http://{host}:{port}/api/frame "
        '-H \'Content-Type: application/json\' -d \'\\{"data":"base64...","tool":"mujoco"\\}\'[/]'
    )
    console.print(f"  Health check: [dim]curl http://{host}:{port}/health[/]")
    console.print()

    if not no_open:
        webbrowser.open(f"http://{host}:{port}")

    import uvicorn

    from gpd.mcp.viewer.server import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")


@viewer_app.command()
def push(
    data: str = typer.Argument(None, help="Base64 frame data (or - for stdin)"),
    file: str = typer.Option("", "--file", "-f", help="JSON file with MCP response to extract frames from"),
    tool: str = typer.Option("", "--tool", "-t", help="MCP tool name"),
    label: str = typer.Option("", "--label", "-l", help="Frame label"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Viewer server port"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Viewer server host"),
) -> None:
    """Push a frame to a running viewer.

    Usage:
        gpd-plus view push "base64data..." --tool mujoco
        gpd-plus view push --file result.json --tool mujoco
        echo "base64..." | gpd-plus view push -
    """
    port = _get_port(port)
    host = _get_host(host)
    import httpx

    base_url = f"http://{host}:{port}"

    # Read from file (extract frames from MCP response JSON)
    if file:
        with open(file) as f:
            response = json.load(f)

        frames = _extract_frames(response, tool)
        if not frames:
            console.print("[yellow]No frames found in response.[/]")
            raise typer.Exit(code=1)

        resp = httpx.post(f"{base_url}/api/frames", json=[f.model_dump() for f in frames], timeout=30)
        resp.raise_for_status()
        result = resp.json()
        console.print(f"[green]Pushed {result['pushed']} frames[/] ({result['total']} total)")
        return

    # Read from stdin
    if data == "-":
        data = sys.stdin.read().strip()

    if not data:
        console.print("[red]No frame data provided.[/] Pass base64 data or use --file.")
        raise typer.Exit(code=1)

    payload = {"data": data, "tool": tool, "label": label, "format": "jpeg"}
    resp = httpx.post(f"{base_url}/api/frame", json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    console.print(f"[green]Frame pushed[/] (index {result['index']}, {result['total']} total)")


def _extract_frames(response: dict | list, tool_name: str) -> list:
    """Extract frame data from common MCP response shapes."""
    from gpd.mcp.viewer.server import Frame

    frames: list[Frame] = []

    # Direct frames array: {"frames": ["base64...", ...]}
    if isinstance(response, dict) and "frames" in response:
        raw_frames = response["frames"]
        for i, f in enumerate(raw_frames):
            if isinstance(f, str):
                frames.append(Frame(data=f, tool=tool_name, label=f"step {i}"))
            elif isinstance(f, dict):
                frames.append(
                    Frame(
                        data=f.get("data", f.get("image", "")),
                        tool=tool_name,
                        label=f.get("label", f"step {i}"),
                        format=f.get("format", "jpeg"),
                    )
                )

    # Nested in result: {"result": {"frames": [...]}}
    elif isinstance(response, dict) and "result" in response:
        return _extract_frames(response["result"], tool_name)

    # Content array (MCP standard): {"content": [{"type": "image", "data": "..."}]}
    elif isinstance(response, dict) and "content" in response:
        for i, item in enumerate(response["content"]):
            if isinstance(item, dict) and item.get("type") == "image":
                frames.append(
                    Frame(
                        data=item.get("data", ""),
                        tool=tool_name,
                        label=item.get("annotations", {}).get("label", f"frame {i}"),
                        format=item.get("mimeType", "image/jpeg").split("/")[-1],
                    )
                )

    # Single image: {"image": "base64...", "data": "base64..."}
    elif isinstance(response, dict):
        for key in ("image", "data", "frame", "visualization"):
            if key in response and isinstance(response[key], str) and len(response[key]) > 100:
                frames.append(Frame(data=response[key], tool=tool_name, label=key))
                break

    return frames

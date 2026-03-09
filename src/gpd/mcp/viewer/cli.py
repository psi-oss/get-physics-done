"""CLI commands for the GPD Frame Viewer."""

from __future__ import annotations

import json
import re
import sys
import webbrowser
from urllib import error as urllib_error
from urllib import request as urllib_request

import typer
from rich.console import Console

viewer_app = typer.Typer(name="view", help="Lightweight frame viewer for MCP simulation outputs")

console = Console()

DEFAULT_PORT = 7890
DEFAULT_HOST = "127.0.0.1"
FramePayload = dict[str, object]


def _get_port(port: int) -> int:
    """Resolve viewer port, checking GPD_VIEWER_PORT env var."""
    if port != DEFAULT_PORT:
        return port
    import os

    return int(os.environ.get("GPD_VIEWER_PORT", str(DEFAULT_PORT)))


def _get_host(host: str) -> str:
    """Resolve viewer host, checking GPD_VIEWER_HOST env var."""
    if host != DEFAULT_HOST:
        return host
    import os

    return os.environ.get("GPD_VIEWER_HOST", DEFAULT_HOST)


def _exit_with_error(message: str) -> None:
    console.print(message, style="red", highlight=False)
    raise typer.Exit(code=1)


def _handle_missing_viewer_dependency(exc: ModuleNotFoundError) -> None:
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", str(exc))
    missing = exc.name or (match.group(1) if match else "viewer dependency")
    _exit_with_error(
        "Viewer dependencies are not installed. "
        "Run: pip install 'get-physics-done[viewer]' "
        f"(missing module: {missing})."
    )


def _post_json(url: str, payload: object, *, timeout: float) -> dict[str, object]:
    """POST JSON with stdlib networking so `view push` has no extra dependency."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset("utf-8")
            raw = resp.read().decode(charset)
    except urllib_error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace").strip()
        msg = details or exc.reason
        raise RuntimeError(f"Viewer request failed ({exc.code}): {msg}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Could not reach viewer at {url}: {exc.reason}") from exc

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Viewer returned invalid JSON: {raw[:200]}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"Viewer returned unexpected response: {type(result).__name__}")
    return result


@viewer_app.callback(invoke_without_command=True)
def start(
    ctx: typer.Context,
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Server port"),
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Server host (e.g. 0.0.0.0 for all interfaces)"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open browser"),
) -> None:
    """Start the frame viewer server and open the browser.

    Usage:
        gpd view                    # start on default port, open browser
        gpd view --port 8080        # custom port
        gpd view --host 0.0.0.0     # listen on all interfaces
        gpd view --no-open          # don't open browser
    """
    if ctx.invoked_subcommand is not None:
        return

    port = _get_port(port)
    host = _get_host(host)

    try:
        import uvicorn

        from gpd.mcp.viewer.server import create_app
    except ModuleNotFoundError as exc:
        _handle_missing_viewer_dependency(exc)

    app = create_app()

    console.print(f"[bold blue]GPD Frame Viewer[/] starting on http://{host}:{port}")
    console.print(
        f"  Push frames:  [dim]curl -X POST http://{host}:{port}/api/frame "
        '-H \'Content-Type: application/json\' -d \'\\{"data":"base64...","tool":"mujoco"\\}\'[/]'
    )
    console.print(f"  Health check: [dim]curl http://{host}:{port}/health[/]")
    console.print()

    if not no_open:
        webbrowser.open(f"http://{host}:{port}")
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
        gpd view push "base64data..." --tool mujoco
        gpd view push --file result.json --tool mujoco
        echo "base64..." | gpd view push -
    """
    port = _get_port(port)
    host = _get_host(host)

    base_url = f"http://{host}:{port}"

    # Read from file (extract frames from MCP response JSON)
    if file:
        try:
            with open(file, encoding="utf-8") as f:
                response = json.load(f)
        except OSError as exc:
            _exit_with_error(f"Could not read JSON file {file!r}: {exc}")
        except json.JSONDecodeError as exc:
            _exit_with_error(f"Could not parse JSON file {file!r}: {exc}")

        frames = _extract_frames(response, tool)
        if not frames:
            console.print("[yellow]No frames found in response.[/]")
            raise typer.Exit(code=1)

        try:
            result = _post_json(f"{base_url}/api/frames", frames, timeout=30)
        except RuntimeError as exc:
            _exit_with_error(str(exc))
        console.print(f"[green]Pushed {result['pushed']} frames[/] ({result['total']} total)")
        return

    # Read from stdin
    if data == "-":
        data = sys.stdin.read().strip()

    if not data:
        console.print("[red]No frame data provided.[/] Pass base64 data or use --file.")
        raise typer.Exit(code=1)

    payload = {"data": data, "tool": tool, "label": label, "format": "jpeg"}
    try:
        result = _post_json(f"{base_url}/api/frame", payload, timeout=10)
    except RuntimeError as exc:
        _exit_with_error(str(exc))
    console.print(f"[green]Frame pushed[/] (index {result['index']}, {result['total']} total)")


def _extract_frames(response: dict | list, tool_name: str) -> list[FramePayload]:
    """Extract frame data from common MCP response shapes."""
    if isinstance(response, list):
        frames: list[FramePayload] = []
        for i, item in enumerate(response):
            payload = _coerce_frame_payload(item, tool_name, fallback_label=f"frame {i}")
            if payload is None:
                payload = _coerce_content_frame(item, tool_name, fallback_label=f"frame {i}")
            if payload is not None:
                frames.append(payload)
            elif isinstance(item, (dict, list)):
                frames.extend(_extract_frames(item, tool_name))
        return frames

    if not isinstance(response, dict):
        return []

    raw_frames = response.get("frames")
    if isinstance(raw_frames, list):
        frames: list[FramePayload] = []
        for i, item in enumerate(raw_frames):
            payload = _coerce_frame_payload(item, tool_name, fallback_label=f"step {i}")
            if payload is not None:
                frames.append(payload)
        if frames:
            return frames

    for key in ("result", "structuredContent"):
        nested = response.get(key)
        if isinstance(nested, (dict, list)):
            frames = _extract_frames(nested, tool_name)
            if frames:
                return frames

    raw_content = response.get("content")
    if isinstance(raw_content, list):
        frames = []
        for i, item in enumerate(raw_content):
            payload = _coerce_content_frame(item, tool_name, fallback_label=f"frame {i}")
            if payload is not None:
                frames.append(payload)
            elif isinstance(item, (dict, list)):
                frames.extend(_extract_frames(item, tool_name))
        if frames:
            return frames

    payload = _coerce_content_frame(response, tool_name, fallback_label=str(response.get("label", "frame")))
    if payload is not None:
        return [payload]

    for key in ("frame", "image", "visualization", "resource"):
        nested = response.get(key)
        if isinstance(nested, (dict, list)):
            frames = _extract_frames(nested, tool_name)
            if frames:
                return frames

    return []


def _coerce_content_frame(item: object, tool_name: str, *, fallback_label: str) -> FramePayload | None:
    if not isinstance(item, dict):
        return _coerce_frame_payload(item, tool_name, fallback_label=fallback_label)

    item_type = str(item.get("type", "")).lower()
    mime_type = str(item.get("mimeType", "")).lower()
    if item_type == "resource" and isinstance(item.get("resource"), dict):
        resource = item["resource"]
        merged = {**resource, **item}
        return _coerce_frame_payload(merged, tool_name, fallback_label=fallback_label)

    if item_type and item_type not in {"image", "input_image", "image_url", "resource"} and not _is_media_mime(mime_type):
        return None
    return _coerce_frame_payload(item, tool_name, fallback_label=fallback_label)


def _coerce_frame_payload(item: object, tool_name: str, *, fallback_label: str) -> FramePayload | None:
    if isinstance(item, str):
        if not _looks_like_image_payload(item):
            return None
        return _build_frame_payload(item, tool_name, fallback_label, format_hint=None)

    if not isinstance(item, dict):
        return None

    data = _extract_image_data(item)
    if not data:
        return None

    payload: FramePayload = _build_frame_payload(
        data,
        tool_name,
        _extract_label(item, fallback_label),
        format_hint=item.get("format") or item.get("mimeType"),
    )

    if (width := _coerce_int(item.get("width"))) is not None:
        payload["width"] = width
    if (height := _coerce_int(item.get("height"))) is not None:
        payload["height"] = height
    if (timestamp := _coerce_float(item.get("timestamp"))) is not None:
        payload["timestamp"] = timestamp
    return payload


def _build_frame_payload(data: str, tool_name: str, label: str, *, format_hint: object) -> FramePayload:
    return {
        "data": data,
        "tool": tool_name,
        "label": label,
        "format": _normalize_format(format_hint, data),
    }


def _extract_image_data(item: dict[str, object]) -> str | None:
    item_type = str(item.get("type", "")).lower()
    mime_type = str(item.get("mimeType", ""))

    image_url = item.get("image_url")
    if isinstance(image_url, dict):
        url = image_url.get("url")
        if isinstance(url, str) and url:
            return url
    if isinstance(image_url, str) and image_url:
        return image_url

    for key in ("image", "frame", "visualization", "blob"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value

    uri = item.get("uri")
    if isinstance(uri, str) and uri.startswith("data:"):
        return uri

    data = item.get("data")
    if isinstance(data, str) and data:
        if item_type in {"image", "input_image", "image_url"}:
            return data
        if _is_media_mime(mime_type) or item.get("format"):
            return data
        if _looks_like_image_payload(data):
            return data
    return None


def _extract_label(item: dict[str, object], fallback_label: str) -> str:
    annotations = item.get("annotations")
    annotation_label = annotations.get("label") if isinstance(annotations, dict) else None
    for value in (item.get("label"), annotation_label, item.get("title"), item.get("name"), fallback_label):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback_label


def _normalize_format(format_hint: object, data: str) -> str:
    candidate = str(format_hint).strip().lower() if format_hint else ""
    if not candidate and data.startswith("data:"):
        candidate = data[5:].split(";", 1)[0].lower()

    if "/" in candidate:
        candidate = candidate.split("/", 1)[1]
    candidate = candidate.split(";", 1)[0]
    return {
        "jpg": "jpeg",
        "jpe": "jpeg",
        "svg+xml": "svg",
        "x-glb": "glb",
        "gltf-binary": "glb",
    }.get(candidate, candidate or "jpeg")


def _looks_like_image_payload(value: str) -> bool:
    stripped = value.strip()
    if stripped.startswith("data:image/") or stripped.startswith("data:model/"):
        return True
    return len(stripped) >= 16 and re.fullmatch(r"[A-Za-z0-9+/=_-]+", stripped) is not None


def _is_media_mime(mime_type: str) -> bool:
    return mime_type.startswith("image/") or mime_type.startswith("model/")


def _coerce_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _coerce_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None

"""FastAPI server for streaming MCP visualization frames to a browser."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

MAX_FRAME_HISTORY = 200


class Frame(BaseModel):
    """A single visualization frame from an MCP tool."""

    data: str  # base64 data URI or raw base64 string
    tool: str = ""  # which MCP produced this
    label: str = ""  # e.g., "step 42" or "t=0.5s"
    timestamp: float = 0.0
    width: int = 0
    height: int = 0
    format: str = "jpeg"  # jpeg, png, glb


class FrameStore:
    """Thread-safe in-memory frame buffer with SSE broadcast."""

    def __init__(self) -> None:
        self.frames: deque[Frame] = deque(maxlen=MAX_FRAME_HISTORY)
        self._subscribers: list[asyncio.Queue[Frame | None]] = []
        self._lock = asyncio.Lock()

    async def push(self, frame: Frame) -> int:
        """Add a frame and notify all SSE subscribers. Returns frame index."""
        async with self._lock:
            self.frames.append(frame)
            idx = len(self.frames) - 1
            dead: list[asyncio.Queue[Frame | None]] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(frame)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)
            return idx

    async def subscribe(self) -> asyncio.Queue[Frame | None]:
        """Create a new subscriber queue."""
        q: asyncio.Queue[Frame | None] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[Frame | None]) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.store = FrameStore()
    app.state.start_time = time.time()
    yield


def create_app() -> FastAPI:
    """Create the viewer FastAPI app."""
    app = FastAPI(title="GPD+ Frame Viewer", lifespan=_lifespan)
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> object:
        return templates.TemplateResponse("viewer.html", {"request": request})

    @app.get("/health")
    async def health() -> dict[str, object]:
        store: FrameStore = app.state.store
        async with store._lock:
            frame_count = len(store.frames)
            sub_count = len(store._subscribers)
        return {
            "status": "running",
            "frames": frame_count,
            "subscribers": sub_count,
            "uptime_seconds": round(time.time() - app.state.start_time, 1),
        }

    @app.post("/api/frame")
    async def push_frame(frame: Frame) -> dict[str, object]:
        """Push a single frame to all connected viewers."""
        if not frame.timestamp:
            frame.timestamp = time.time()
        store: FrameStore = app.state.store
        idx = await store.push(frame)
        return {"ok": True, "index": idx, "total": len(store.frames)}

    @app.post("/api/frames")
    async def push_frames(frames: list[Frame]) -> dict[str, object]:
        """Push multiple frames at once (from a single step_simulation call)."""
        store: FrameStore = app.state.store
        now = time.time()
        for i, frame in enumerate(frames):
            if not frame.timestamp:
                frame.timestamp = now + (i * 0.001)
            await store.push(frame)
        return {"ok": True, "pushed": len(frames), "total": len(store.frames)}

    @app.post("/api/clear")
    async def clear_frames() -> dict[str, object]:
        """Clear all buffered frames. Call before starting a new simulation."""
        store: FrameStore = app.state.store
        async with store._lock:
            store.frames.clear()
            # Notify subscribers to clear their UI
            for q in store._subscribers:
                try:
                    q.put_nowait(None)  # sentinel for "clear"
                except asyncio.QueueFull:
                    pass
        return {"ok": True, "cleared": True}

    @app.get("/api/history")
    async def frame_history() -> list[dict[str, object]]:
        """Get all buffered frames (for late-joining viewers)."""
        store: FrameStore = app.state.store
        async with store._lock:
            return [{"index": i, **f.model_dump()} for i, f in enumerate(store.frames)]

    @app.get("/api/events")
    async def events(request: Request) -> EventSourceResponse:
        """SSE stream of new frames as they arrive."""
        store: FrameStore = app.state.store
        q = await store.subscribe()

        async def generator() -> AsyncGenerator[dict[str, str], None]:
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        frame = await asyncio.wait_for(q.get(), timeout=15.0)
                        if frame is None:
                            yield {"event": "clear", "data": "{}"}
                        else:
                            yield {"event": "frame", "data": frame.model_dump_json()}
                    except TimeoutError:
                        yield {"event": "ping", "data": json.dumps({"t": time.time()})}
            finally:
                await store.unsubscribe(q)

        return EventSourceResponse(generator())

    return app

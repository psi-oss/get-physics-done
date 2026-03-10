"""Tests for the MCP frame viewer CLI helpers."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from gpd.mcp.viewer.cli import _extract_frames, viewer_app

runner = CliRunner()


def test_extract_frames_prefers_structured_content_frames() -> None:
    response = {
        "result": {
            "structuredContent": {
                "frames": [
                    {
                        "data": "data:image/png;base64,AAAA",
                        "label": "step 0",
                        "format": "png",
                        "width": "640",
                        "height": 480,
                        "timestamp": "1.25",
                    }
                ]
            },
            "content": [
                {
                    "type": "image",
                    "data": "data:image/png;base64,BBBB",
                    "annotations": {"label": "duplicate"},
                }
            ],
        }
    }

    frames = _extract_frames(response, "mujoco")

    assert len(frames) == 1
    assert frames[0]["data"] == "data:image/png;base64,AAAA"
    assert frames[0]["label"] == "step 0"
    assert frames[0]["format"] == "png"
    assert frames[0]["tool"] == "mujoco"
    assert frames[0]["width"] == 640
    assert frames[0]["height"] == 480
    assert frames[0]["timestamp"] == 1.25


def test_extract_frames_supports_mcp_content_item_shapes() -> None:
    response = {
        "content": [
            {
                "type": "image",
                "data": "data:image/jpeg;base64,AAAA",
                "annotations": {"label": "camera"},
            },
            {
                "type": "input_image",
                "image_url": {"url": "data:image/png;base64,BBBB"},
                "title": "upload",
            },
            {
                "type": "resource",
                "resource": {
                    "uri": "data:model/gltf-binary;base64,CCCC",
                    "mimeType": "model/gltf-binary",
                },
                "name": "mesh",
            },
        ]
    }

    frames = _extract_frames(response, "sim")

    assert [frame["label"] for frame in frames] == ["camera", "upload", "mesh"]
    assert [frame["format"] for frame in frames] == ["jpeg", "png", "glb"]
    assert all(frame["tool"] == "sim" for frame in frames)


def test_extract_frames_supports_top_level_frame_lists() -> None:
    response = [
        "QUJDREVGR0hJSktMTQ==",
        {
            "data": "QkNERUZHSElKS0xNTg==",
            "mimeType": "image/png",
            "label": "raw-png",
        },
        {
            "frame": "data:image/jpeg;base64,DDDD",
            "label": "named-frame",
        },
    ]

    frames = _extract_frames(response, "viewer")

    assert len(frames) == 3
    assert frames[0]["label"] == "frame 0"
    assert frames[1]["label"] == "raw-png"
    assert frames[1]["format"] == "png"
    assert frames[2]["label"] == "named-frame"
    assert frames[2]["format"] == "jpeg"


def test_push_file_posts_extracted_frames(tmp_path: Path) -> None:
    response_file = tmp_path / "response.json"
    response_file.write_text(
        json.dumps(
            {
                "content": [
                    {"type": "image", "data": "data:image/jpeg;base64,AAAA", "annotations": {"label": "a"}},
                    {"type": "image", "data": "data:image/png;base64,BBBB", "annotations": {"label": "b"}},
                ]
            }
        ),
        encoding="utf-8",
    )

    with patch("gpd.mcp.viewer.cli._post_json", return_value={"pushed": 2, "total": 2}) as post_json:
        result = runner.invoke(
            viewer_app,
            ["push", "--file", str(response_file), "--tool", "mujoco", "--host", "localhost", "--port", "9000"],
        )

    assert result.exit_code == 0
    assert "Pushed 2 frames" in result.output
    post_json.assert_called_once()
    assert post_json.call_args.args[0] == "http://localhost:9000/api/frames"
    sent_frames = post_json.call_args.args[1]
    assert isinstance(sent_frames, list)
    assert [frame["label"] for frame in sent_frames] == ["a", "b"]
    assert all(frame["tool"] == "mujoco" for frame in sent_frames)
    assert post_json.call_args.kwargs["timeout"] == 30


def test_start_missing_viewer_dependencies_exits_cleanly() -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "uvicorn":
            raise ModuleNotFoundError("No module named 'uvicorn'")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        result = runner.invoke(viewer_app, ["--no-open"])

    assert result.exit_code == 1
    assert "Rerun the bootstrap" in result.output
    assert "npx github:physicalsuperintelligence/get-physics-done" in result.output
    assert "[viewer]" not in result.output
    assert "uvicorn" in result.output

"""Regression tests for the hook wiring documentation."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_hooks_doc_mentions_hook_files() -> None:
    content = _read("docs/hooks.md")
    assert "statusline.py" in content
    assert "notify.py" in content
    assert "runtime_detect.py" in content


def test_hooks_doc_documents_env_overrides() -> None:
    content = _read("docs/hooks.md")
    assert "GPD_ACTIVE_RUNTIME" in content
    assert "GPD_DISABLE_CHECKOUT_REEXEC" in content
    assert "GPD_DEBUG" in content


def test_onboarding_hub_links_hook_doc() -> None:
    content = _read("docs/README.md")
    assert "Hook wiring & advanced overrides" in content
    assert "./hooks.md" in content

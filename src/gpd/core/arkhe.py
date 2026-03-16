import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel
from gpd.core.errors import GPDError
from gpd.core.observability import instrument_gpd_function

if TYPE_CHECKING:
    pass

class ArkheResult(BaseModel):
    success: bool
    output: str
    error: str | None = None

def _get_binary_path(cwd: Path) -> Path | None:
    binary_name = "get-arkhe-done"
    search_paths = [
        cwd / "get-arkhe-done" / "target" / "debug" / binary_name,
        cwd / "get-arkhe-done" / "target" / "release" / binary_name,
        Path(os.environ.get("HOME", "")) / ".cargo" / "bin" / binary_name,
    ]
    for path in search_paths:
        if path.exists():
            return path
    return None

@instrument_gpd_function("arkhe.execute")
def execute_arkhe_binary(cwd: Path, command: str, args: list[str] | None = None) -> dict[str, object]:
    """Execute the get-arkhe-done Rust binary with given arguments."""

    binary_path = _get_binary_path(cwd)

    if binary_path is None:
        # Fallback to cargo run
        cmd_args = ["cargo", "run", "--quiet", "--manifest-path", str(cwd / "get-arkhe-done" / "Cargo.toml"), "--bin", "get-arkhe-done", "--", command]
    else:
        cmd_args = [str(binary_path), command]

    if args:
        cmd_args.extend(args)

    try:
        process = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False
        )

        return {
            "success": process.returncode == 0,
            "output": process.stdout,
            "error": process.stderr if process.returncode != 0 else None,
            "returncode": process.returncode
        }
    except Exception as exc:
        raise GPDError(f"Failed to execute Arkhe binary: {exc}") from exc

@instrument_gpd_function("arkhe.calculate_lambda")
def cmd_gtd_measure_lambda(cwd: Path) -> dict[str, object]:
    """Calculate and return lambda2 coherence metric."""
    return execute_arkhe_binary(cwd, "resonate")

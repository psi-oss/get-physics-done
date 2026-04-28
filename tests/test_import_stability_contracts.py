from __future__ import annotations

import ast
import json
import os
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
GPD_SRC_ROOT = SRC_ROOT / "gpd"
REPO_PYTHON = (
    REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt"
    else REPO_ROOT / ".venv" / "bin" / "python"
)
OPTIONAL_IMPORT_FAILURE_ALLOWLIST: dict[str, tuple[str, ...]] = {}
MAX_OPTIONAL_IMPORT_FAILURE_ALLOWLIST_ENTRIES = 3


def _repo_python_command() -> list[str]:
    if REPO_PYTHON.is_file():
        return [str(REPO_PYTHON)]
    return ["uv", "run", "python"]


def _top_level_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports


def _gpd_module_names() -> list[str]:
    modules: list[str] = []
    for path in sorted(GPD_SRC_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relpath = path.relative_to(SRC_ROOT).with_suffix("")
        if relpath.name == "__init__":
            module_name = ".".join(relpath.parts[:-1])
        else:
            module_name = ".".join(relpath.parts)
        if module_name:
            modules.append(module_name)
    return modules


def _optional_import_allowlist_entry_count() -> int:
    return sum(len(optional_imports) for optional_imports in OPTIONAL_IMPORT_FAILURE_ALLOWLIST.values())


def test_adapter_base_does_not_import_registry_at_module_import_time() -> None:
    imports = _top_level_imports(REPO_ROOT / "src" / "gpd" / "adapters" / "base.py")

    assert "gpd.registry" not in imports


def test_registry_import_remains_stable_after_adapter_package_import() -> None:
    result = subprocess.run(
        [
            *_repo_python_command(),
            "-c",
            "import gpd.adapters.base\nfrom gpd import registry\nprint(hasattr(registry, 'render_command_visibility_sections_from_frontmatter'))",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "True"


def test_key_entrypoint_modules_import_stably() -> None:
    result = subprocess.run(
        [
            *_repo_python_command(),
            "-c",
            (
                "import importlib; "
                "modules = ['gpd', 'gpd.cli', 'gpd.runtime_cli', 'gpd.mcp.servers.skills_server']; "
                "[importlib.import_module(name) for name in modules]; "
                "print(len(modules))"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "4"


def test_all_gpd_python_modules_import_without_unexpected_optional_dependency_failures() -> None:
    modules = _gpd_module_names()
    missing_allowlist_modules = sorted(set(OPTIONAL_IMPORT_FAILURE_ALLOWLIST) - set(modules))

    assert len(modules) > 100
    assert not missing_allowlist_modules
    assert _optional_import_allowlist_entry_count() <= MAX_OPTIONAL_IMPORT_FAILURE_ALLOWLIST_ENTRIES

    import_health = subprocess.run(
        [
            *_repo_python_command(),
            "-c",
            textwrap.dedent(
                """
                import importlib
                import json
                import os
                import traceback

                modules = json.loads(os.environ["MODULES_JSON"])
                optional_allowlist = {
                    module: set(import_names)
                    for module, import_names in json.loads(os.environ["OPTIONAL_ALLOWLIST_JSON"]).items()
                }
                imported = []
                allowed_optional_failures = []
                unexpected_failures = []

                for module in modules:
                    try:
                        importlib.import_module(module)
                    except ModuleNotFoundError as exc:
                        missing_import = exc.name or ""
                        if missing_import in optional_allowlist.get(module, set()):
                            allowed_optional_failures.append(
                                {"module": module, "missing_import": missing_import}
                            )
                            continue
                        unexpected_failures.append(
                            {
                                "module": module,
                                "error": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc(),
                            }
                        )
                    except Exception as exc:
                        unexpected_failures.append(
                            {
                                "module": module,
                                "error": f"{type(exc).__name__}: {exc}",
                                "traceback": traceback.format_exc(),
                            }
                        )
                    else:
                        imported.append(module)

                print(
                    json.dumps(
                        {
                            "allowed_optional_failures": allowed_optional_failures,
                            "imported_count": len(imported),
                            "module_count": len(modules),
                            "unexpected_failures": unexpected_failures,
                        },
                        sort_keys=True,
                    )
                )
                raise SystemExit(1 if unexpected_failures else 0)
                """
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "MODULES_JSON": json.dumps(modules),
            "OPTIONAL_ALLOWLIST_JSON": json.dumps(OPTIONAL_IMPORT_FAILURE_ALLOWLIST),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        timeout=30,
        check=False,
    )
    stdout_lines = [line for line in import_health.stdout.splitlines() if line.strip()]

    assert stdout_lines, import_health.stderr
    payload = json.loads(stdout_lines[-1])

    assert import_health.returncode == 0, json.dumps(payload["unexpected_failures"], indent=2)
    assert payload["module_count"] == len(modules)
    assert payload["imported_count"] + len(payload["allowed_optional_failures"]) == len(modules)

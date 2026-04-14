"""Import-order regression checks for contract modules."""

from __future__ import annotations

import os
import subprocess
import sys


def _run_import_order(order: tuple[str, ...]) -> None:
    env = os.environ.copy()
    src_path = os.path.join(os.getcwd(), "src")
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_path if not pythonpath else os.pathsep.join([src_path, pythonpath])
    script = (
        "import importlib, sys\n"
        "sys.path.insert(0, 'src')\n"
        f"modules = {order!r}\n"
        "for module_name in modules:\n"
        "    importlib.import_module(module_name)\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True, env=env, cwd=os.getcwd())


def test_import_contracts_before_validation() -> None:
    _run_import_order(("gpd.contracts", "gpd.core.contract_validation"))


def test_import_validation_before_contracts() -> None:
    _run_import_order(("gpd.core.contract_validation", "gpd.contracts"))

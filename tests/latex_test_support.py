from __future__ import annotations

from gpd.mcp.paper.models import PaperToolchainCapability


def latex_capability_payload(**overrides: object) -> dict[str, object]:
    # pdf_review_ready defaults to True here because tests construct this payload
    # to represent a fully-capable toolchain. In production, detect_latex_toolchain()
    # sets pdf_review_ready based on whether pypdf is importable.
    capability: dict[str, object] = {
        "compiler": "pdflatex",
        "compiler_available": True,
        "compiler_path": "/usr/bin/pdflatex",
        "distribution": "TeX Live",
        "bibtex_available": True,
        "latexmk_available": True,
        "kpsewhich_available": True,
        "pdf_review_ready": True,
        "readiness_state": "ready",
        "message": "pdflatex found (TeX Live): /usr/bin/pdflatex",
        "warnings": [],
    }
    capability.update(overrides)
    if "bibliography_support_available" not in capability:
        capability["bibliography_support_available"] = bool(capability.get("compiler_available")) and bool(
            capability.get("bibtex_available")
        )
    if "full_toolchain_available" not in capability:
        capability["full_toolchain_available"] = (
            bool(capability.get("compiler_available"))
            and bool(capability.get("bibtex_available"))
            and bool(capability.get("latexmk_available"))
            and bool(capability.get("kpsewhich_available"))
            and bool(capability.get("pdf_review_ready"))
        )
    return capability


def toolchain_capability(**overrides: object) -> PaperToolchainCapability:
    return PaperToolchainCapability.model_validate(latex_capability_payload(**overrides))

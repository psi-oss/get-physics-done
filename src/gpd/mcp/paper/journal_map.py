"""Domain-to-journal mapping and journal specifications.

Maps physics subdomains to appropriate journal defaults, and provides
complete LaTeX configuration for each supported journal.
"""

from __future__ import annotations

from gpd.mcp.paper.models import JournalSpec

# Journal specifications with LaTeX configuration, column widths, and DPI requirements.
# Sources: RevTeX 4.2 Author's Guide, AASTeX v6.3.1/v7.0 Guide, MNRAS Guide,
# Nature template, JHEP author manual.
JOURNAL_SPECS: dict[str, JournalSpec] = {
    "prl": JournalSpec(
        key="prl",
        document_class="revtex4-2",
        class_options=["aps", "prl", "twocolumn", "superscriptaddress"],
        bib_style="apsrev4-2",
        column_width_cm=8.6,
        double_width_cm=17.8,
        max_height_cm=24.0,
        dpi=600,
        preferred_formats=["pdf", "eps", "png"],
        compiler="pdflatex",
        texlive_package="revtex",
        required_tex_files=["apsrev4-2.bst"],
    ),
    "apj": JournalSpec(
        # Default to aastex631 for broader compatibility.
        # AASTeX v7.0 (aastex701) is available for users who have it installed;
        # it removes \affil and \altaffilmark commands from v6.
        key="apj",
        document_class="aastex631",
        class_options=["twocolumn"],
        bib_style="aasjournal",
        column_width_cm=8.9,
        double_width_cm=18.2,
        max_height_cm=24.5,
        dpi=300,
        preferred_formats=["pdf", "eps", "png"],
        compiler="pdflatex",
        texlive_package="aastex",
        required_tex_files=["aasjournal.bst"],
    ),
    "mnras": JournalSpec(
        key="mnras",
        document_class="mnras",
        class_options=["usenatbib"],
        bib_style="mnras",
        column_width_cm=8.4,
        double_width_cm=17.4,
        max_height_cm=24.0,
        dpi=300,
        preferred_formats=["pdf", "eps", "png"],
        compiler="pdflatex",
        texlive_package="mnras",
        required_tex_files=["mnras.bst"],
    ),
    "nature": JournalSpec(
        key="nature",
        document_class="article",
        class_options=["12pt"],
        bib_style="naturemag",
        column_width_cm=8.9,
        double_width_cm=18.3,
        max_height_cm=24.7,
        dpi=300,
        preferred_formats=["pdf", "eps", "tiff", "png"],
        compiler="pdflatex",
        texlive_package="latex-base",
        required_tex_files=["naturemag.bst"],
        install_hint="Install via: tlmgr install nature",
    ),
    "jhep": JournalSpec(
        # JHEP uses article + jheppub.sty with JHEP.bst for bibliography.
        key="jhep",
        document_class="article",
        class_options=["a4paper", "11pt"],
        bib_style="JHEP",
        column_width_cm=16.5,
        double_width_cm=16.5,
        max_height_cm=24.0,
        dpi=300,
        preferred_formats=["pdf", "eps", "png"],
        compiler="pdflatex",
        texlive_package="jhep",
        required_tex_files=["jheppub.sty", "JHEP.bst"],
        install_hint="Install the official JHEP author package so jheppub.sty and JHEP.bst are on your TeX path.",
    ),
    "jfm": JournalSpec(
        # Note: jfm.cls must be installed separately -- not in standard TeX Live.
        # Download from Cambridge University Press.
        key="jfm",
        document_class="jfm",
        class_options=[],
        bib_style="jfm",
        column_width_cm=8.3,
        double_width_cm=17.1,
        max_height_cm=24.0,
        dpi=300,
        preferred_formats=["pdf", "eps", "png"],
        compiler="pdflatex",
        texlive_package="jfm",
        required_tex_files=["jfm.bst"],
        install_hint="Install the official Cambridge JFM class bundle and place jfm.cls and jfm.bst on your TeX path.",
    ),
}

# Domain-to-journal mapping.
# Default: "prl" (most general physics journal).
DOMAIN_JOURNAL_MAP: dict[str, str] = {
    # Particle physics / HEP
    "particle_physics": "prl",
    "high_energy_physics": "prl",
    "quantum_field_theory": "prl",
    # Condensed matter
    "condensed_matter": "prl",
    "superconductivity": "prl",
    # Quantum
    "quantum_computing": "prl",
    "quantum_information": "prl",
    "quantum_optics": "prl",
    # Astrophysics
    "astrophysics": "apj",
    "cosmology": "apj",
    "stellar_physics": "apj",
    "exoplanets": "apj",
    "galaxies": "apj",
    # Observational astronomy
    "observational_astronomy": "mnras",
    "radio_astronomy": "mnras",
    "extragalactic": "mnras",
    # Fluid mechanics
    "fluid_mechanics": "jfm",
    "turbulence": "jfm",
    "computational_fluid_dynamics": "jfm",
    # General / interdisciplinary
    "general_physics": "prl",
    "biophysics": "nature",
    "materials_science": "nature",
    "nuclear_physics": "prl",
    "atomic_physics": "prl",
    "plasma_physics": "prl",
    "statistical_mechanics": "prl",
    "mathematical_physics": "prl",
    "optics": "prl",
    "acoustics": "prl",
    "geophysics": "nature",
    "climate_science": "nature",
}


def get_journal_for_domain(domain: str) -> str:
    """Return journal key for a physics domain, defaulting to 'prl'."""
    return DOMAIN_JOURNAL_MAP.get(domain, "prl")


def get_journal_spec(journal: str) -> JournalSpec:
    """Return the JournalSpec for a journal key.

    Raises:
        ValueError: If the journal key is not recognized.
    """
    if journal not in JOURNAL_SPECS:
        raise ValueError(f"Unknown journal: {journal!r}. Supported: {', '.join(JOURNAL_SPECS)}")
    return JOURNAL_SPECS[journal]


def list_journals() -> list[str]:
    """Return all supported journal keys."""
    return list(JOURNAL_SPECS.keys())

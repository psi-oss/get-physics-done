"""Pydantic models for the MCP discovery layer.

Defines the type system for tool entries, MCP status, physics categories,
source configuration, and catalog snapshots.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

OVERVIEW_PREVIEW_MAX_CHARS: int = 200
"""Maximum character length for tool overview/description previews.

Used when storing ToolEntry.overview and when building compact LLM prompts
to keep context size manageable.
"""


class MCPStatus(StrEnum):
    """Deployment status of an MCP tool."""

    available = "available"
    """Confirmed live on a hosted or local source."""

    stale = "stale"
    """In registry but not confirmed after a live check."""

    unavailable = "unavailable"
    """Confirmed not deployed."""

    unknown = "unknown"
    """Not yet checked."""


class CostProfile(BaseModel):
    """Per-tool compute cost metadata maintained in the catalog."""

    gpu_type: str = "CPU"
    estimated_seconds: float = 30.0
    cost_per_call_usd: float = 0.0
    last_updated: str = ""
    sample_count: int = 0  # For running average during cost learning


class ToolEntry(BaseModel):
    """A single MCP tool with its metadata and status."""

    name: str
    """MCP identifier (e.g., 'openfoam')."""

    description: str
    """Human-readable description."""

    source: str
    """Where this came from: 'modal', 'local', 'external', 'custom'."""

    status: MCPStatus = MCPStatus.unknown
    """Current deployment status."""

    categories: list[str] = Field(default_factory=list)
    """Physics categories this tool belongs to (derived from SKILLS_SUMMARY domains)."""

    domains: list[str] = Field(default_factory=list)
    """Raw domain strings from SKILLS_SUMMARY."""

    tools: list[dict[str, str]] = Field(default_factory=list)
    """Tool name/description pairs."""

    overview: str = ""
    """Brief overview from SKILLS_SUMMARY."""

    cost_profile: CostProfile = Field(default_factory=CostProfile)
    """Per-tool compute cost metadata."""

    last_checked: str = ""
    """ISO timestamp of last health check."""

    staleness_seconds: float = 0.0
    """Seconds since last check."""

    deployment_name: str = ""
    """Hosted deployment name for display."""


class PhysicsCategory(BaseModel):
    """A physics category for domain-based tool routing."""

    name: str
    """Category identifier (e.g., 'cfd')."""

    display_name: str
    """Human-readable name (e.g., 'Computational Fluid Dynamics')."""

    domain_keywords: list[str]
    """Keywords to match against SKILLS_SUMMARY domains (case-insensitive)."""

    preferred_mcps: list[str] = Field(default_factory=list)
    """Known good MCPs for this category."""


PHYSICS_CATEGORIES: list[PhysicsCategory] = [
    PhysicsCategory(
        name="cfd",
        display_name="Computational Fluid Dynamics",
        domain_keywords=["computational fluid dynamics", "cfd", "turbulence", "flow", "aerodynamics", "multiphase"],
        preferred_mcps=["openfoam", "su2", "dedalus", "palabos", "walberla", "basilisk"],
    ),
    PhysicsCategory(
        name="nbody",
        display_name="N-body / Astrophysics",
        domain_keywords=["n-body", "orbital", "gravitational", "cosmological", "galaxy", "sph"],
        preferred_mcps=["rebound", "gadget_4", "ramses", "phantom", "castro", "amrvac"],
    ),
    PhysicsCategory(
        name="fem",
        display_name="Finite Element Methods",
        domain_keywords=["finite element", "structural", "fea", "stress", "earthquake"],
        preferred_mcps=["calculix", "fenics", "deal_ii", "code_aster", "opensees", "febio"],
    ),
    PhysicsCategory(
        name="quantum",
        display_name="Quantum / Chemistry",
        domain_keywords=["quantum", "dft", "many-body", "ab initio", "molecular orbital"],
        preferred_mcps=["qutip", "psi4", "nwchem", "cp2k", "octopus", "yambo"],
    ),
    PhysicsCategory(
        name="md",
        display_name="Molecular Dynamics",
        domain_keywords=["molecular dynamics", "biomolecular", "polymer", "lennard-jones"],
        preferred_mcps=["lammps", "gromacs", "hoomd", "plumed"],
    ),
    PhysicsCategory(
        name="climate",
        display_name="Climate / Ocean / Atmosphere",
        domain_keywords=["weather", "climate", "ocean", "atmosphere", "circulation"],
        preferred_mcps=["wrf", "openifs", "cesm", "mpas", "roms", "mitgcm"],
    ),
    PhysicsCategory(
        name="multiphysics",
        display_name="Multi-physics / Rigid Body",
        domain_keywords=["multi-physics", "coupled", "fsi", "rigid body", "robotics"],
        preferred_mcps=["precice", "chrono", "omniverse", "mujoco"],
    ),
    PhysicsCategory(
        name="bio",
        display_name="Bio / Medical Physics",
        domain_keywords=["biomechanics", "drug discovery", "radiation therapy"],
        preferred_mcps=["febio", "autodock_vina", "matrad"],
    ),
    PhysicsCategory(
        name="geophysics",
        display_name="Geophysics",
        domain_keywords=["seismic", "ice sheet", "geochemistry", "crustal"],
        preferred_mcps=["specfem3d", "sw4", "pism", "pylith", "phreeqc"],
    ),
    PhysicsCategory(
        name="em_plasma",
        display_name="Electromagnetic / Plasma",
        domain_keywords=["plasma", "laser", "particle-in-cell", "pic", "spin dynamics", "electromagnetic"],
        preferred_mcps=["smilei", "osiris", "hipace", "vampire", "geant4"],
    ),
    PhysicsCategory(
        name="databases",
        display_name="Databases / Catalogs",
        domain_keywords=["astronomical database", "protein database", "catalog", "archive"],
        preferred_mcps=["mast", "ned", "simbad", "vizier", "uniprot_rest_api"],
    ),
    PhysicsCategory(
        name="utility",
        display_name="Utility Tools",
        domain_keywords=["cad", "meshing", "circuit"],
        preferred_mcps=["freecad", "gmsh", "qucs"],
    ),
]
"""Full physics category taxonomy for domain-based tool routing."""

# Build lookup indices for fast matching
_CATEGORY_BY_NAME: dict[str, PhysicsCategory] = {c.name: c for c in PHYSICS_CATEGORIES}
_MCP_TO_CATEGORIES: dict[str, list[str]] = {}
for _cat in PHYSICS_CATEGORIES:
    for _mcp in _cat.preferred_mcps:
        _MCP_TO_CATEGORIES.setdefault(_mcp, []).append(_cat.name)


def categorize_tool(tool_name: str, domains: list[str]) -> list[str]:
    """Match a tool against the physics category taxonomy.

    Uses case-insensitive keyword matching against domains and also checks
    if tool_name appears in any category's preferred_mcps.

    Returns list of matching category names. If no matches, returns ["uncategorized"].
    """
    matched: set[str] = set()

    # Check preferred_mcps membership
    if tool_name in _MCP_TO_CATEGORIES:
        matched.update(_MCP_TO_CATEGORIES[tool_name])

    # Check domain keywords
    domains_lower = [d.lower() for d in domains]
    for cat in PHYSICS_CATEGORIES:
        for keyword in cat.domain_keywords:
            keyword_lower = keyword.lower()
            for domain in domains_lower:
                if keyword_lower in domain:
                    matched.add(cat.name)
                    break

    if not matched:
        return ["uncategorized"]
    return sorted(matched)


class SourceConfig(BaseModel):
    """Configuration for a single MCP source."""

    type: str
    """Source type: 'modal', 'local', 'external', 'custom'."""

    app_name: str = ""
    """Hosted deployment name (for modal type)."""

    env: str = ""
    """Hosted environment name, when applicable."""

    registry: str = ""
    """Registry identifier to use for catalog metadata."""

    reconcile: bool = True
    """Whether to check hosted deployment status when supported."""

    config_dir: str = ""
    """For local type: directory with MCP configs."""

    configs: list[str] = Field(default_factory=list)
    """For local type: specific MCP names."""

    services_file: str = ""
    """For external type: path to services YAML."""

    custom_entries: list[dict[str, object]] = Field(default_factory=list)
    """For custom type: inline endpoint definitions."""


class MCPSourcesConfig(BaseModel):
    """Top-level configuration for all MCP sources."""

    version: str = "1.0.0"
    """Config format version."""

    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    """Named source configurations."""

    categories: dict[str, PhysicsCategory] | None = None
    """Optional category overrides from config file."""


class ToolCatalogSnapshot(BaseModel):
    """Point-in-time snapshot of the tool catalog state."""

    total_tools: int = 0
    available_tools: int = 0
    stale_tools: int = 0
    categories_discovered: list[str] = Field(default_factory=list)
    tools: dict[str, ToolEntry] = Field(default_factory=dict)
    last_refreshed: str = ""
    """ISO timestamp of the overall catalog freshness."""

    def summary(self) -> str:
        """Return a compact one-line summary of the catalog state."""
        unknown = self.total_tools - self.available_tools - self.stale_tools
        cat_count = len(self.categories_discovered)
        return (
            f"{self.total_tools} tools "
            f"({self.available_tools} available, {self.stale_tools} stale, {unknown} unknown) "
            f"across {cat_count} categories"
        )

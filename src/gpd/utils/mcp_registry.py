"""MCP Registry -- discovery, SKILL.md loading, streaming configs.

Inlined from the MCP shared registry so GPD can discover
available MCP servers standalone.

Uses GPD's own infra/ directory layout for MCP configs when available,
or falls back to the simulators package if importable.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from gpd.utils.paths import find_project_root

logger = logging.getLogger(__name__)


def _resolve_simulators_dir() -> Path | None:
    """Resolve the simulators package directory.

    Three-tier fallback:
    1. Import simulators package and derive its location
    2. SIMULATORS_DIR environment variable
    3. Walk up from CWD to find a project root with packages/simulators/
    """
    # Tier 1: importlib-based discovery
    try:
        import simulators

        return Path(simulators.__file__).parent
    except ImportError:
        pass

    # Tier 2: environment variable
    env = os.environ.get("SIMULATORS_DIR")
    if env:
        path = Path(env)
        if path.exists():
            return path

    # Tier 3: project root search
    repo_root = find_project_root()
    if repo_root:
        path = repo_root / "packages" / "simulators" / "src" / "simulators"
        if path.exists():
            return path

    return None


def get_passing_mcps() -> set[str]:
    """Read passing MCPs from MCP_TEST_STATUS.md file."""
    simulators_dir = _resolve_simulators_dir()
    if simulators_dir is None:
        return set()

    status_file = simulators_dir.parent / "MCP_TEST_STATUS.md"
    passing: set[str] = set()
    if status_file.exists():
        with open(status_file) as f:
            for line in f:
                if "| PASS" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        mcp_name = parts[1].strip()
                        if mcp_name:
                            passing.add(mcp_name)
    return passing


def get_skills_summary() -> dict:
    """Load the SKILLS_SUMMARY.json for MCP skill info."""
    simulators_dir = _resolve_simulators_dir()
    if simulators_dir is None:
        return {}

    skills_file = simulators_dir / "SKILLS_SUMMARY.json"
    if skills_file.exists():
        try:
            with open(skills_file) as f:
                data = json.load(f)
                return data.get("skills", {})
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def get_streaming_configs() -> dict:
    """Load streaming configurations from metadata.json files."""
    simulators_dir = _resolve_simulators_dir()
    if simulators_dir is None:
        return {}

    streaming_configs: dict = {}
    for mcp_dir in simulators_dir.iterdir():
        if not mcp_dir.is_dir():
            continue

        metadata_file = mcp_dir / "metadata.json"
        if not metadata_file.exists():
            continue

        try:
            with open(metadata_file) as f:
                metadata = json.load(f)

            streaming = metadata.get("streaming", {})
            if streaming.get("enabled", False):
                streaming_configs[mcp_dir.name] = streaming
        except (OSError, json.JSONDecodeError):
            continue

    return streaming_configs


def get_skill_path(mcp_name: str) -> Path | None:
    """Get the SKILL.md path for any MCP (external or simulator)."""
    simulators_dir = _resolve_simulators_dir()
    if simulators_dir is None:
        return None

    sim_path = simulators_dir / mcp_name / "SKILL.md"
    if sim_path.exists():
        return sim_path
    return None


def get_available_mcps() -> dict:
    """Scan simulators directory for available MCPs with descriptions and tools."""
    simulators_dir = _resolve_simulators_dir()
    if simulators_dir is None:
        return {}

    PASSING_MCPS = get_passing_mcps()

    # Curated descriptions for simulators with poor/missing docstrings
    CURATED_DESCRIPTIONS = {
        "adcirc": "Coastal ocean circulation and storm surge modeling",
        "adda": "Light scattering by arbitrary particles using discrete dipole approximation",
        "amrvac": "Adaptive mesh refinement for astrophysical MHD simulations",
        "athena": "Astrophysical magnetohydrodynamics code",
        "autodock_vina": "Molecular docking for drug discovery and protein-ligand binding",
        "basilisk": "Adaptive mesh CFD solver for multiphase flows",
        "berkeleygw": "Many-body perturbation theory for excited state properties",
        "calculix": "Finite element analysis for mechanical engineering",
        "castro": "Adaptive mesh compressible astrophysics (supernovae, stellar)",
        "cdt2d": "Causal dynamical triangulations for quantum gravity",
        "chrono": "Multi-physics simulation for rigid-body and vehicle dynamics",
        "clawpack": "Conservation laws package for hyperbolic PDE wave propagation",
        "cesm": "Community Earth System Model for climate simulation",
        "cesm_waccm": "Whole atmosphere climate model with chemistry",
        "cp2k": "Quantum chemistry and solid state physics (DFT, MD)",
        "dakota": "Uncertainty quantification and optimization toolkit",
        "deal_ii": "Finite element library for PDEs",
        "dedalus": "Spectral PDE solver for fluid dynamics",
        "elegant": "Charged particle accelerator simulation",
        "fdps": "Framework for Developing Particle Simulator (N-body, SPH)",
        "febio": "Finite element biomechanics (soft tissue, organs)",
        "fenics": "Finite element PDE solver",
        "freecad": "CAD modeling with FEM analysis (CalculiX solver, Gmsh meshing)",
        "geant4": "Particle physics detector simulation",
        "getdp": "General finite element solver for physics",
        "gridlabd": "Power distribution grid simulation",
        "gromacs": "Molecular dynamics for biomolecular systems",
        "hipace": "Plasma wakefield accelerator simulation",
        "krome": "Astrochemistry and microphysics package",
        "lammps": "Large-scale molecular dynamics (materials, polymers)",
        "libra_code": "Nonadiabatic and quantum dynamics",
        "mast": "MAST astronomical archive query interface",
        "matrad": "Radiation therapy treatment planning",
        "mitgcm": "Ocean and atmosphere general circulation model",
        "mpas": "Model for Prediction Across Scales (atmosphere/ocean)",
        "mujoco": "Rigid-body physics engine with beautiful EGL rendering (robotics, control)",
        "ned": "NASA Extragalactic Database query interface",
        "nubhlight": "General relativistic radiation magnetohydrodynamics (GRMHD)",
        "nwchem": "Computational chemistry (DFT, MP2, CCSD)",
        "octopus": "Real-space time-dependent DFT",
        "opal": "Particle accelerator simulation framework",
        "openfoam": "Computational fluid dynamics toolkit",
        "openifs": "ECMWF weather forecasting model",
        "openmc": "Monte Carlo neutron/photon transport",
        "openmolcas": "Multiconfigurational quantum chemistry",
        "opensees": "Earthquake engineering structural analysis",
        "orthofinder": "Phylogenetic orthology inference",
        "osiris": "Particle-in-cell plasma simulation",
        "palabos": "Lattice Boltzmann CFD solver",
        "phreeqc": "Geochemical reaction modeling",
        "pism": "Ice sheet and glacier dynamics",
        "plumed": "Enhanced sampling and free energy methods for MD",
        "polaris": "3D dust continuum radiative transfer",
        "precice": "Multi-physics coupling library",
        "psi4": "Ab initio quantum chemistry",
        "pylith": "Crustal deformation and earthquake modeling",
        "qe_epw": "Electron-phonon coupling from first principles",
        "qucs": "Circuit simulation (SPICE-like)",
        "ramses": "Adaptive mesh cosmological simulation",
        "raspa": "Molecular simulation of adsorption in nanoporous materials",
        "roms": "Regional ocean modeling system",
        "schism": "Unstructured grid ocean model",
        "simbad": "SIMBAD astronomical database query interface",
        "smilei": "Particle-in-cell code for laser-plasma interaction",
        "sparta": "Direct simulation Monte Carlo for rarefied gas",
        "specfem3d": "Spectral element seismic wave propagation",
        "su2": "Multiphysics CFD and shape optimization",
        "sw4": "Seismic wave simulation (4th order)",
        "syk": "Sachdev-Ye-Kitaev model for quantum chaos",
        "telemac_mascaret": "Hydrodynamics and sediment transport",
        "uclchem": "Astrochemistry gas-grain chemical modeling",
        "uniprot_rest_api": "UniProt protein database query interface",
        "vampire": "Atomistic spin dynamics simulation",
        "vizier": "VizieR astronomical catalog query interface",
        "vplanet": "Planetary system evolution over Gyr timescales",
        "walberla": "Massively parallel lattice Boltzmann framework",
        "wrf": "Weather Research and Forecasting model",
        "yambo": "Many-body perturbation theory (GW, BSE)",
    }

    STANDARD_TOOLS = [
        {"name": "create_simulation", "desc": "Initialize a new simulation"},
        {"name": "step_simulation", "desc": "Advance simulation by N steps"},
        {"name": "get_measurements", "desc": "Get current simulation measurements"},
        {"name": "reset_simulation", "desc": "Reset or delete the simulation"},
        {"name": "get_visualization_frame", "desc": "Get visualization data"},
    ]

    mcps: dict = {}
    for subdir in simulators_dir.iterdir():
        if subdir.is_dir() and (subdir / "server.py").exists():
            mcp_id = subdir.name
            if mcp_id.startswith("_") or mcp_id == "__pycache__":
                continue
            if mcp_id not in PASSING_MCPS:
                continue

            try:
                with open(subdir / "server.py") as f:
                    content = f.read()

                if mcp_id in CURATED_DESCRIPTIONS:
                    desc = CURATED_DESCRIPTIONS[mcp_id]
                elif '"""' in content:
                    start = content.find('"""') + 3
                    end = content.find('"""', start)
                    docstring = content[start:end].strip()
                    lines = [line.strip() for line in docstring.split("\n") if line.strip()]
                    desc = None
                    for line in lines:
                        if re.match(r"^MCP [Ss]erver (for |wrapping )?\w+\.?$", line):
                            continue
                        if re.match(r"^MCP [Ss]erver\.?$", line):
                            continue
                        if len(line) > 10:
                            desc = line[:100]
                            break
                    if not desc:
                        desc = f"{mcp_id} simulation"
                else:
                    desc = f"{mcp_id} simulation"

                tools = list(STANDARD_TOOLS)

                tool_pattern = r'@(?:self\.)?mcp\.tool\(\)\s*\n\s*(?:async\s+)?def\s+(\w+)\s*\([^)]*\)(?:\s*->[^:]+)?:\s*\n\s*(?:"""([\s\S]*?)""")?'
                matches = re.findall(tool_pattern, content, re.MULTILINE)

                custom_tool_names: set[str] = set()
                for match in matches:
                    tool_name = match[0]
                    tool_doc = match[1].strip().split("\n")[0][:60] if match[1] else f"Custom {tool_name} tool"
                    if tool_name not in [t["name"] for t in STANDARD_TOOLS]:
                        if tool_name not in custom_tool_names:
                            custom_tool_names.add(tool_name)
                            tools.append({"name": tool_name, "desc": tool_doc})

            except Exception as e:
                logger.warning("Failed to parse %s/server.py: %s", mcp_id, e)
                desc = f"{mcp_id} MCP (parse error)"
                tools = []

            mcps[mcp_id] = {"description": desc, "path": str(subdir / "server.py"), "tools": tools}

    return mcps

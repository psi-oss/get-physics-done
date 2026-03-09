"""Reference routing for GPD bundles.

Routes computation types, physics domains, and error descriptions to the
most relevant reference files via keyword matching against metadata.

Layer 1 code: stdlib only (depends on loader.py).
"""

from __future__ import annotations

import re

from gpd.core.constants import (
    REF_DEFAULT_ERROR_CATALOG,
    REF_SUBFIELD_GUIDE_FALLBACK,
    REF_SUBFIELD_PREFIX,
    UNIVERSAL_ERROR_IDS,
)
from gpd.core.observability import instrument_gpd_function
from gpd.strategy.loader import ReferenceLoader, get_loader

# ─── Routing Tables ─────────────────────────────────────────────────────────────

# Maps computation types to protocol file names
COMPUTATION_TO_PROTOCOL: dict[str, str] = {
    "perturbation": "perturbation-theory",
    "perturbative": "perturbation-theory",
    "loop integral": "perturbation-theory",
    "feynman diagram": "perturbation-theory",
    "coupling expansion": "perturbation-theory",
    "renormalization": "renormalization-group",
    "rg flow": "renormalization-group",
    "beta function": "renormalization-group",
    "path integral": "path-integrals",
    "functional integral": "path-integrals",
    "effective field theory": "effective-field-theory",
    "eft": "effective-field-theory",
    "power counting": "effective-field-theory",
    "monte carlo": "monte-carlo",
    "mcmc": "monte-carlo",
    "metropolis": "monte-carlo",
    "molecular dynamics": "molecular-dynamics",
    "md simulation": "molecular-dynamics",
    "exact diagonalization": "exact-diagonalization",
    "numerical": "numerical-computation",
    "numerical computation": "numerical-computation",
    "finite difference": "numerical-computation",
    "symbolic": "symbolic-to-numerical",
    "symbolic to numerical": "symbolic-to-numerical",
    "integral": "integral-evaluation",
    "integration": "integral-evaluation",
    "derivation": "derivation-discipline",
    "analytical": "derivation-discipline",
    "general relativity": "general-relativity",
    "gr": "general-relativity",
    "schwarzschild": "general-relativity",
    "kerr": "general-relativity",
    "cosmological perturbation": "cosmological-perturbation-theory",
    "inflation": "cosmological-perturbation-theory",
    "cmb": "cosmological-perturbation-theory",
    "wkb": "wkb-semiclassical",
    "semiclassical": "wkb-semiclassical",
    "tunneling": "wkb-semiclassical",
    "scattering": "scattering-theory",
    "cross section": "scattering-theory",
    "s-matrix": "scattering-theory",
    "lattice gauge": "lattice-gauge-theory",
    "lattice qcd": "lattice-gauge-theory",
    "tensor network": "tensor-networks",
    "dmrg": "tensor-networks",
    "mps": "tensor-networks",
    "conformal bootstrap": "conformal-bootstrap",
    "cft": "conformal-bootstrap",
    "ope": "conformal-bootstrap",
    "supersymmetry": "supersymmetry",
    "susy": "supersymmetry",
    "holography": "holography-ads-cft",
    "ads/cft": "holography-ads-cft",
    "ads cft": "holography-ads-cft",
    "green function": "green-functions",
    "propagator": "green-functions",
    "response function": "green-functions",
    "variational": "variational-methods",
    "trial wavefunction": "variational-methods",
    "dft": "density-functional-theory",
    "density functional": "density-functional-theory",
    "kohn-sham": "density-functional-theory",
    "many-body perturbation": "many-body-perturbation-theory",
    "mbpt": "many-body-perturbation-theory",
    "gw approximation": "many-body-perturbation-theory",
    "quantum many-body": "quantum-many-body",
    "hubbard": "quantum-many-body",
    "heisenberg model": "quantum-many-body",
    "open quantum": "open-quantum-systems",
    "lindblad": "open-quantum-systems",
    "master equation": "open-quantum-systems",
    "quantum error": "quantum-error-correction",
    "qec": "quantum-error-correction",
    "stabilizer": "quantum-error-correction",
    "statistical inference": "statistical-inference",
    "bayesian": "statistical-inference",
    "maximum likelihood": "statistical-inference",
    "classical mechanics": "classical-mechanics",
    "lagrangian": "classical-mechanics",
    "hamiltonian": "hamiltonian-mechanics",
    "phase space": "hamiltonian-mechanics",
    "electrodynamics": "electrodynamics",
    "maxwell": "electrodynamics",
    "electromagnetic": "electrodynamics",
    "symmetry analysis": "symmetry-analysis",
    "group theory": "group-theory",
    "lie algebra": "group-theory",
    "representation": "group-theory",
    "large-n": "large-n-expansion",
    "large n": "large-n-expansion",
    "1/n expansion": "large-n-expansion",
    "resummation": "resummation",
    "pade": "resummation",
    "borel": "resummation",
    "bethe ansatz": "bethe-ansatz",
    "integrability": "bethe-ansatz",
    "kinetic theory": "kinetic-theory",
    "boltzmann equation": "kinetic-theory",
    "transport": "non-equilibrium-transport",
    "non-equilibrium": "non-equilibrium-transport",
    "fluid dynamics": "fluid-dynamics-mhd",
    "mhd": "fluid-dynamics-mhd",
    "navier-stokes": "fluid-dynamics-mhd",
    "finite temperature": "finite-temperature-field-theory",
    "matsubara": "finite-temperature-field-theory",
    "thermal field": "finite-temperature-field-theory",
    "random matrix": "random-matrix-theory",
    "rmt": "random-matrix-theory",
    "wigner-dyson": "random-matrix-theory",
    "topological": "topological-methods",
    "chern number": "topological-methods",
    "berry phase": "topological-methods",
    "order of limits": "order-of-limits",
    "stochastic": "stochastic-processes",
    "langevin": "stochastic-processes",
    "fokker-planck": "stochastic-processes",
    "analytic continuation": "analytic-continuation",
    "wick rotation": "analytic-continuation",
    "machine learning": "machine-learning-physics",
    "neural network": "machine-learning-physics",
    "numerical relativity": "numerical-relativity",
}

# Maps physics domains to verification domain file suffixes
DOMAIN_TO_VERIFICATION: dict[str, list[str]] = {
    "qft": ["qft"],
    "quantum field theory": ["qft"],
    "particle physics": ["qft", "nuclear-particle"],
    "high energy": ["qft", "nuclear-particle"],
    "condensed matter": ["condmat"],
    "solid state": ["condmat"],
    "superconductor": ["condmat"],
    "statistical mechanics": ["statmech"],
    "stat mech": ["statmech"],
    "thermodynamics": ["statmech"],
    "general relativity": ["gr-cosmology"],
    "cosmology": ["gr-cosmology"],
    "amo": ["amo"],
    "atomic": ["amo"],
    "molecular": ["amo"],
    "optical": ["amo"],
    "nuclear": ["nuclear-particle"],
    "astrophysics": ["astrophysics"],
    "stellar": ["astrophysics"],
    "mathematical physics": ["mathematical-physics"],
    "fluid": ["fluid-plasma"],
    "plasma": ["fluid-plasma"],
    "quantum information": ["quantum-info"],
    "quantum computing": ["quantum-info"],
    "soft matter": ["soft-matter"],
    "polymer": ["soft-matter"],
    "biophysics": ["soft-matter"],
}

# Maps keywords to relevant error class ID ranges
_ERROR_KEYWORD_TO_IDS: dict[str, list[int]] = {
    "cg coefficient": [1],
    "clebsch-gordan": [1],
    "symmetrization": [2],
    "identical particles": [2],
    "green function": [3],
    "propagator": [3],
    "group theory": [4],
    "casimir": [4],
    "asymptotics": [5],
    "asymptotic expansion": [5],
    "delta function": [6],
    "phase convention": [7],
    "intensive extensive": [8],
    "thermodynamic": [8, 9],
    "thermal field": [9],
    "tensor decomposition": [10],
    "riemann tensor": [10],
    "hallucinated identity": [11],
    "mathematical identity": [11],
    "grassmann": [12],
    "fermion sign": [12],
    "boundary condition": [13],
    "operator ordering": [14],
    "dimensional analysis": [15],
    "series truncation": [16],
    "correlation function": [17],
    "response function": [17],
    "integration constant": [18],
    "dof counting": [19],
    "degrees of freedom": [19],
    "classical quantum": [20],
    "branch cut": [21],
    "hubbard-stratonovich": [22],
    "diagram counting": [23],
    "variational bound": [24],
    "partition function": [25, 29],
    "coherent state": [26],
    "second quantization": [27],
    "angular momentum": [28],
    "boltzmann factor": [29],
    "path ordering": [30],
    "wilson loop": [30],
    "ensemble": [31],
    "numerical linear algebra": [32],
    "natural unit": [33],
    "unit restoration": [33],
    "regularization": [34],
    "fierz identity": [35],
    "effective potential": [36],
    "metric signature": [37],
    "covariant derivative": [38],
    "christoffel": [38],
    "wick contraction": [39],
    "scaling dimension": [40],
    "index symmetrization": [41],
    "noether current": [42],
    "anomaly": [42],
    "legendre transform": [43],
    "spin-statistics": [44],
    "topological term": [45],
    "instanton": [45],
    "adiabatic": [46],
    "complex conjugation": [47],
    "density matrix": [47],
    "hellmann-feynman": [48],
    "replica trick": [49],
    "zero mode": [50],
    "nuclear shell": [82],
    "magic numbers": [82],
    "eddington luminosity": [83],
    "friedmann equation": [84],
    "multiphoton": [85],
    "bcs gap": [86],
    "superconductivity": [86],
    "reconnection": [87],
    "decoherence": [88],
    "holonomic": [89],
    "hyperscaling": [90],
    "critical exponents": [90],
    "conformal mapping": [91],
    "lyapunov": [92],
    "fresnel": [93],
    "fraunhofer": [93],
    "maxwell construction": [94],
    "brillouin zone": [95],
    "binding energy": [96],
    "penrose diagram": [97],
    "entanglement measure": [98],
    "magnetic mirror": [99],
    "jeans instability": [100],
    "kramers degeneracy": [101],
}

# Maps physics domains to error catalog file names
ERROR_KEYWORD_TO_CATALOG: dict[str, str] = {
    "cg coefficient": "llm-errors-core",
    "green function": "llm-errors-core",
    "group theory": "llm-errors-core",
    "asymptotics": "llm-errors-core",
    "delta function": "llm-errors-core",
    "phase convention": "llm-errors-core",
    "thermodynamic": "llm-errors-core",
    "partition function": "llm-errors-core",
    "coherent state": "llm-errors-field-theory",
    "second quantization": "llm-errors-field-theory",
    "angular momentum": "llm-errors-field-theory",
    "boltzmann": "llm-errors-field-theory",
    "path ordering": "llm-errors-field-theory",
    "regularization": "llm-errors-field-theory",
    "fierz": "llm-errors-field-theory",
    "metric signature": "llm-errors-field-theory",
    "topological": "llm-errors-field-theory",
    "numerical relativity": "llm-errors-extended",
    "stellar structure": "llm-errors-extended",
    "quantum chemistry": "llm-errors-extended",
    "plasma": "llm-errors-extended",
    "fluid dynamics": "llm-errors-extended",
    "turbulence": "llm-errors-extended",
    "finite-size": "llm-errors-extended",
    "nuclear shell": "llm-errors-deep",
    "astrophysics error": "llm-errors-deep",
    "superconductivity": "llm-errors-deep",
    "decoherence": "llm-errors-deep",
    "critical phenomena": "llm-errors-deep",
    "brillouin": "llm-errors-deep",
    "entanglement": "llm-errors-deep",
}

# Maps domain keywords to subfield guide file stems
_DOMAIN_TO_SUBFIELD: dict[str, str] = {
    "qft": f"{REF_SUBFIELD_PREFIX}qft",
    "quantum field theory": f"{REF_SUBFIELD_PREFIX}qft",
    "condensed matter": f"{REF_SUBFIELD_PREFIX}condensed-matter",
    "solid state": f"{REF_SUBFIELD_PREFIX}condensed-matter",
    "stat mech": f"{REF_SUBFIELD_PREFIX}stat-mech",
    "statistical mechanics": f"{REF_SUBFIELD_PREFIX}stat-mech",
    "gr": f"{REF_SUBFIELD_PREFIX}gr-cosmology",
    "general relativity": f"{REF_SUBFIELD_PREFIX}gr-cosmology",
    "cosmology": f"{REF_SUBFIELD_PREFIX}gr-cosmology",
    "amo": f"{REF_SUBFIELD_PREFIX}amo",
    "atomic": f"{REF_SUBFIELD_PREFIX}amo",
    "nuclear": f"{REF_SUBFIELD_PREFIX}nuclear-particle",
    "particle physics": f"{REF_SUBFIELD_PREFIX}nuclear-particle",
    "quantum information": f"{REF_SUBFIELD_PREFIX}quantum-info",
    "quantum computing": f"{REF_SUBFIELD_PREFIX}quantum-info",
    "fluid": f"{REF_SUBFIELD_PREFIX}fluid-plasma",
    "plasma": f"{REF_SUBFIELD_PREFIX}fluid-plasma",
    "mathematical physics": f"{REF_SUBFIELD_PREFIX}mathematical-physics",
    "classical mechanics": f"{REF_SUBFIELD_PREFIX}classical-mechanics",
    "soft matter": f"{REF_SUBFIELD_PREFIX}soft-matter-biophysics",
    "biophysics": f"{REF_SUBFIELD_PREFIX}soft-matter-biophysics",
    "astrophysics": f"{REF_SUBFIELD_PREFIX}astrophysics",
}


# ─── Router ──────────────────────────────────────────────────────────────────────


class ReferenceRouter:
    """Routes computation types and domains to relevant reference files."""

    def __init__(self, loader: ReferenceLoader | None = None) -> None:
        self._loader = loader or get_loader()

    @instrument_gpd_function("router.route_protocol")
    def route_protocol(self, computation_type: str) -> str | None:
        """Find the best protocol for a computation type.

        Returns the protocol name (e.g., 'perturbation-theory') or None.
        """
        lower = computation_type.lower().strip()
        # Exact match
        if lower in COMPUTATION_TO_PROTOCOL:
            return COMPUTATION_TO_PROTOCOL[lower]
        # Substring match
        for keyword, protocol in COMPUTATION_TO_PROTOCOL.items():
            if keyword in lower or lower in keyword:
                return protocol
        # Try matching against the rich protocol index load_when keywords
        index = self._loader.protocol_index
        if index:
            tokens = _tokenize(lower)
            best_score = 0
            best_key: str | None = None
            for key, entry in index.items():
                score = _score_text_match(tokens, entry.when_to_use.lower())
                load_when_score = sum(1 for t in tokens if t in key)
                total = score + load_when_score
                if total > best_score:
                    best_score = total
                    best_key = key
            if best_key and best_score >= 1:
                return self._loader._protocol_names.get(best_key) or best_key
        return None

    @instrument_gpd_function("router.route_verification")
    def route_verification(self, domain: str) -> list[str]:
        """Find verification domain checklist names for a physics domain.

        Returns list of domain suffixes (e.g., ['qft', 'nuclear-particle']).
        """
        lower = domain.lower().strip()
        # Exact match
        if lower in DOMAIN_TO_VERIFICATION:
            return list(DOMAIN_TO_VERIFICATION[lower])
        # Substring match
        for keyword, domains in DOMAIN_TO_VERIFICATION.items():
            if keyword in lower or lower in keyword:
                return list(domains)
        return []

    @instrument_gpd_function("router.route_errors")
    def route_errors(self, computation_desc: str) -> list[int]:
        """Find relevant error class IDs for a computation description.

        Returns sorted list of error class IDs most relevant to the description.
        """
        lower = computation_desc.lower().strip()
        matched_ids: set[int] = set()
        for keyword, ids in _ERROR_KEYWORD_TO_IDS.items():
            if keyword in lower:
                matched_ids.update(ids)

        # If no specific matches, return the universally-dangerous error classes
        if not matched_ids:
            matched_ids = set(UNIVERSAL_ERROR_IDS)

        return sorted(matched_ids)

    def route_errors_to_catalogs(self, computation_desc: str) -> list[str]:
        """Find relevant error catalog files for a computation description.

        Returns list of catalog names (e.g., ['llm-errors-core']).
        """
        lower = computation_desc.lower().strip()
        catalogs: set[str] = set()
        for keyword, catalog in ERROR_KEYWORD_TO_CATALOG.items():
            if keyword in lower:
                catalogs.add(catalog)
        return sorted(catalogs) if catalogs else [REF_DEFAULT_ERROR_CATALOG]

    def route_subfield(self, domain: str) -> str | None:
        """Get the subfield guide reference name for a domain.

        Uses the subfield routing table for precise matching, then falls
        back to the loader's subfield guide index.
        """
        lower = domain.lower().strip()

        # Check routing table
        if lower in _DOMAIN_TO_SUBFIELD:
            return _DOMAIN_TO_SUBFIELD[lower]
        for keyword, guide in _DOMAIN_TO_SUBFIELD.items():
            if keyword in lower or lower in keyword:
                return guide

        # Fall back to executor-subfield-guide
        return REF_SUBFIELD_GUIDE_FALLBACK

    @instrument_gpd_function("router.route_all")
    def route_all(self, computation_type: str, domain: str) -> dict[str, list[str] | list[int]]:
        """Route both computation type and domain, returning all relevant references.

        Returns dict with keys: protocols, verification, errors, error_ids, subfield.
        """
        protocol = self.route_protocol(computation_type)
        verification = self.route_verification(domain)
        error_catalogs = self.route_errors_to_catalogs(computation_type)
        error_ids = self.route_errors(computation_type)
        subfield = self.route_subfield(domain)

        return {
            "protocols": [protocol] if protocol else [],
            "verification": verification,
            "errors": error_catalogs,
            "error_ids": error_ids,
            "subfield": [subfield] if subfield else [],
        }

    @instrument_gpd_function("router.search")
    def search(self, keywords: list[str]) -> list[str]:
        """Search for references matching keywords via loader's load_when metadata.

        Returns reference names.
        """
        results = self._loader.search_by_keywords(keywords)
        return [r.name for r in results]


# ─── Helper Functions ─────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words."""
    return set(_WORD_RE.findall(text.lower()))


def _score_text_match(query_tokens: set[str], target_text: str) -> int:
    """Score how well query tokens match target text."""
    target_lower = target_text.lower()
    return sum(1 for token in query_tokens if token in target_lower)


# ─── Module-level convenience ────────────────────────────────────────────────────


def get_router(loader: ReferenceLoader | None = None) -> ReferenceRouter:
    """Create a ReferenceRouter with the default or given loader."""
    return ReferenceRouter(loader)

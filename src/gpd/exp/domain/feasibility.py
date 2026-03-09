"""Layer 1 feasibility keyword pre-screen.

Scans research questions for obvious intractability flags.
Pure domain logic: no framework imports, no side effects.
"""

from __future__ import annotations

import re

# Patterns that indicate intractable research (requires specialized equipment,
# lab conditions, or specific location access beyond what crowd-sourcing can provide)
INTRACTABILITY_PATTERNS: list[str] = [
    r"electron microscope",
    r"particle accelerator",
    r"clean\s*room",
    r"vacuum chamber",
    r"cryogenic",
    r"radioactive",
    r"biohazard",
    r"level\s*[34]\s*biosafety",
    r"restricted\s+area",
    r"classified\s+material",
    r"nuclear\s+reactor",
    r"synchrotron",
    r"mass\s+spectrometer",
    r"genome\s+sequenc",
    r"MRI\s+scan",
    r"CT\s+scan",
    r"surgical\s+procedure",
]


def keyword_feasibility_prescreen(question: str) -> list[str]:
    """Scan a research question for intractability keywords.

    Returns a list of flagged patterns (empty = no issues found).
    This is a Layer 1 fast check; the LLM feasibility agent provides
    deeper analysis in Layer 2.
    """
    question_lower = question.lower()
    flagged: list[str] = []
    for pattern in INTRACTABILITY_PATTERNS:
        if re.search(pattern, question_lower):
            flagged.append(pattern)
    return flagged

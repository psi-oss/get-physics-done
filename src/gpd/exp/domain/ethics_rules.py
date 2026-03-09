"""Layer 1 ethics keyword patterns and checks.

Fast keyword scanning for hard ethical gates. This is a deterministic
pre-screen; the LLM ethics agent provides nuanced reasoning in Layer 2.

Pure domain logic: no framework imports, no side effects.
"""

from __future__ import annotations

import re

# Hard-reject keyword patterns for ethical gates.
# Matching any of these triggers mandatory ethics review.
ETHICS_HARD_REJECT_PATTERNS: list[str] = [
    # Vulnerable populations
    r"\bchildren\b",
    r"\bminors?\b",
    r"\binfants?\b",
    r"\bneonates?\b",
    r"\bpregnant\b",
    r"\bprisoners?\b",
    r"\bincarcerated\b",
    r"\belderly\s+dementia\b",
    r"\bcognitively\s+impaired\b",
    # Biological materials
    r"\bblood\b",
    r"\btissue\s+sample",
    r"\bbodily\s+fluid",
    r"\bbiological\s+specimen",
    r"\bDNA\s+sample",
    r"\bgenetic\s+material\b",
    # Personally identifiable information (PII)
    r"\bSSN\b",
    r"\bsocial\s+security",
    r"\bcredit\s+card",
    r"\bbank\s+account",
    r"\bmedical\s+record",
    r"\bhealth\s+record",
    # Medical / pharmaceutical
    r"\bmedication\b",
    r"\bdrug\b",
    r"\bdosage\b",
    r"\bprescription\b",
    r"\binjection\b",
    r"\bsurgery\b",
    # Deception without consent
    r"\bdeceive\b",
    r"\btrick\b",
    r"\bmislead\b",
    r"\bwithout\s+consent\b",
    r"\bwithout\s+knowledge\b",
    r"\bcovert\s+observation\b",
]


def check_ethics_keywords(question: str, procedure: str) -> list[str]:
    """Layer 1 fast scan for ethics hard-reject keywords.

    Scans both the research question and the procedure description.
    Returns list of matched pattern strings (empty = no flags).
    """
    combined = f"{question} {procedure}".lower()
    matched: list[str] = []
    for pattern in ETHICS_HARD_REJECT_PATTERNS:
        if re.search(pattern, combined):
            matched.append(pattern)
    return matched

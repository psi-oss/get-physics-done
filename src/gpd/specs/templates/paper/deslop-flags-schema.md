<purpose>
Schema for `${PAPER_DIR}/DESLOP-FLAGS.md`: substantive issues the deslopification gate
SURFACES instead of editing. The pipeline never silently fixes rigor, notation, citation,
physics, or theorem-status problems; it records them here with severity and a concrete
author action. This is the safeguard against the core danger: polishing plausible-but-wrong
work removes the very tells that warn a reviewer.
</purpose>

<record>
Each flag (JSON block in `DESLOP-FLAGS.md`, also mirrored in `DESLOP-SUMMARY.json`):

```json
{
  "flag_id": "DSF-0017",
  "severity": "blocker | major | minor",
  "category": "rigor | notation | citation | physics | evidence | metadata | theorem_status",
  "location": {"file": "references.tex", "line_start": 412, "line_end": 414},
  "excerpt": "Submission-time check: confirm exact published title...",
  "why_not_auto_edited": "The correct bibliographic data must be verified from a source; inventing it would violate the no-misrepresentation rule.",
  "recommended_author_action": "Verify the final published title, venue, volume, pages, DOI/arXiv identifier, then rerun bibliography audit.",
  "blocks_public_release": true,
  "delegate_to": "gpd-bibliographer"
}
```

Fields:
- `severity`; `blocker` sets `blocks_public_release: true` and fails `ci` mode.
- `category`; what kind of substantive issue; routes `delegate_to` the right owner
  (`gpd-paper-writer`, `gpd-bibliographer`, `gpd-notation-coordinator`, `gpd-review-physics`, `gpd-check-proof`).
- `excerpt`; the offending text (read-only; the gate did not change it).
- `why_not_auto_edited`; the integrity reason this is a flag, not an edit.
- `recommended_author_action`; a concrete next step, not a vague "review this".
- `blocks_public_release`; true for placeholder/`TODO`/submission-time-check citations,
  unverifiable claims, undefined-before-use load-bearing notation, and unit/factor errors.
</record>

<release_blockers>
The following are always `blocker` severity and must be cleared before `gpd:arxiv-submission`:
- public-facing agent-scaffolding leakage that could not be safely rewritten,
- placeholder / `TODO` / "submission-time check" citations,
- a claimed theorem whose status the gate could not confirm is intact,
- load-bearing notation used before definition,
- a physics quantity with an unresolved unit/dimension/factor concern.
A non-empty blocker set means `gate_status: blocked` regardless of how clean the prose became.
</release_blockers>

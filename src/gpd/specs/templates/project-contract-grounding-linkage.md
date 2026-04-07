If a project contract has any `references[]` and does not already carry concrete prior-output, user-anchor, or baseline grounding, at least one reference must set `must_surface: true`. When that other grounding exists, a missing `must_surface: true` reference is still a warning that should be repaired, not a silent ignore.

`must_surface` is a boolean scalar. Use the JSON literals `true` and `false`; do not quote them or replace them with yes/no wording.

`required_actions[]` uses the same closed action vocabulary enforced downstream in contract ledgers: `read`, `use`, `compare`, `cite`, `avoid`.

If a project-contract reference sets `must_surface: true`, `applies_to[]` must not be empty.

If a project-contract reference sets `must_surface: true`, `required_actions[]` must not be empty.

Approved-mode grounding is field-specific:

- `must_include_prior_outputs[]` entries should be explicit project-artifact paths or filenames that already exist inside the current project root. If `project_root` is unavailable, treat them as non-grounding until the file can be resolved against a concrete root.
- `user_asserted_anchors[]` and `known_good_baselines[]` must name a concrete, re-findable handle such as a citation, DOI, arXiv ID, durable URL, or project-local artifact path. Multi-word prose alone does not count.
- If a `references[].locator` uses a project-local artifact path instead of an external paper locator, it only counts as approved grounding when the referenced file already exists inside the current project root. If no project root is available, it does not count as approved grounding.
- `Placeholder`, `TBD`, `TODO`, `unknown`, `unclear`, `none`, `n/a`, and `placeholder` remain non-grounding unless they are part of a genuinely missing-anchor blocker phrase.

#### Project Contract ID Linkage Rules

Every ID-like field must point to a declared object ID in the same contract:

- Same-kind IDs must be unique within each section. Do not repeat an `id` inside `observables[]`, `claims[]`, `deliverables[]`, `acceptance_tests[]`, `references[]`, `forbidden_proxies[]`, or `links[]`.
- Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; target resolution becomes ambiguous.
- `context_intake.must_read_refs[]` must contain `references[].id` values only.
- `references[].aliases[]` may store stable human-facing labels or citation strings that help canonicalize downstream anchor mentions.
- `claims[].observables[]` must contain `observables[].id` values only.
- `claims[].deliverables[]` must contain `deliverables[].id` values only.
- `claims[].acceptance_tests[]` must contain `acceptance_tests[].id` values only.
- `claims[].references[]` must contain `references[].id` values only.
- Proof-bearing claims must set `claim_kind` explicitly to a non-`other` value; do not leave theorem-bearing work on the default.
- `acceptance_tests[].subject` must point to a `claims[].id` or `deliverables[].id`, never an observable ID or prose label.
- `acceptance_tests[].evidence_required[]` may point only to claim, deliverable, acceptance-test, or reference IDs.
- `references[].applies_to[]` must point to a claim ID or deliverable ID.
- `references[].carry_forward_to[]` is free-text workflow scope (for example `planning`, `execution`, `verification`, `writing`) and must not match any declared contract ID from `observables[]`, `claims[]`, `deliverables[]`, `acceptance_tests[]`, `references[]`, `forbidden_proxies[]`, or `links[]`.
- `forbidden_proxies[].subject` must point to a claim ID or deliverable ID.
- `links[].source` and `links[].target` may point only to claim, deliverable, acceptance-test, or reference IDs.
- `links[].verified_by[]` must contain `acceptance_tests[].id` values only.

#### Explicit Anchor-Gap Guidance

If the user does not know the decisive anchor yet, keep that uncertainty explicit instead of inventing a paper, reference, benchmark, or baseline. Put that blocker in `scope.unresolved_questions`, `context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors`. Accepted phrasings include:

- `Which reference should serve as the decisive benchmark anchor?`
- `Benchmark reference not yet selected; still to identify the decisive anchor.`
- `Need grounding before the decisive anchor is chosen.`
- `Decisive target not yet chosen before planning can proceed.`
- `Baseline comparison is TBD before planning can proceed.`

These phrases are valid for preserving uncertainty when they point to a genuinely missing decisive anchor, but they do not satisfy approved-mode grounding on their own. Approved mode still needs a concrete reference, prior output, user anchor, or baseline elsewhere in the contract; placeholder-only wording does not count.

In validator terms: approved project contract requires at least one concrete anchor/reference/prior-output/baseline; explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own.

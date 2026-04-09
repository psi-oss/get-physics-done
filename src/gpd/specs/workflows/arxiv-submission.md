<purpose>
Prepare a completed paper for arXiv submission.

This workflow is staged:

1. `bootstrap`
2. `manuscript_preflight`
3. `review_gate`
4. `package`
5. `finalize`

Keep only arXiv-specific rules inline. Use the shared publication bootstrap reference for manuscript-root resolution, latest-review gating, and fail-closed paired artifact handling.

Output: a submission-ready `arxiv-submission.tar.gz` and a manual submission checklist.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's `execution_context` before starting.
Also read the shared publication bootstrap reference before resolving the manuscript target:

@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md
</required_reading>

<process>

<step name="bootstrap" priority="first">
**Resolve the manuscript target and publication bootstrap context.**

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context arxiv-submission "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Run the centralized review preflight before continuing:

```bash
if [ -n "$ARGUMENTS" ]; then
  REVIEW_PREFLIGHT=$(gpd validate review-preflight arxiv-submission "$ARGUMENTS" --strict)
else
  REVIEW_PREFLIGHT=$(gpd validate review-preflight arxiv-submission --strict)
fi
if [ $? -ne 0 ]; then
  echo "$REVIEW_PREFLIGHT"
  exit 1
fi
```

Use the shared publication bootstrap reference as the source of truth for manuscript-root resolution, latest-review discovery, and paired response gating. Do not duplicate those contracts here.
If review preflight exits nonzero because of missing project state, missing manuscript, missing compiled manuscript, unresolved publication blockers, degraded review integrity, missing conventions, missing staged review artifacts, or stale theorem-proof review state, STOP and fix those blockers before packaging.
If `derived_manuscript_proof_review_status` is present, use it as the first-pass theorem-proof freshness for the resolved manuscript, but keep the manuscript-root proof review artifacts authoritative for strict packaging decisions.
Strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and `reproducibility-manifest.json` from the resolved manuscript directory itself. The same resolved manuscript root is also the strict preflight source of truth for packaging.

Resolve the manuscript target from `$ARGUMENTS`:

1. If `$ARGUMENTS` specifies a `.tex` file, set `resolved_main_tex` to that file and `resolved_dir` to its parent directory.
2. If `$ARGUMENTS` specifies a directory, resolve the canonical manuscript `.tex` entrypoint under that directory from `ARTIFACT-MANIFEST.json`, then `PAPER-CONFIG.json` if needed.
3. Otherwise inspect only the documented manuscript roots `paper/`, `manuscript/`, and `draft/` in that order.
4. If the manuscript root is ambiguous or missing, STOP and require an explicit manuscript path or a repaired manuscript-root state.
5. Do not fall back to `find` or arbitrary wildcard matching outside the documented default roots.

Then run the centralized publication preflight and review preflight checks. If the latest review artifacts are missing, incomplete, stale, or blocked, or if the manuscript-root gates fail, stop before any packaging work starts.

Set:

```bash
PAPER_DIR="${resolved_dir}"
MAIN_SOURCE="${resolved_main_tex}"
MAIN_BASENAME="$(basename "${MAIN_SOURCE}")"
MAIN_STEM="${MAIN_BASENAME%.*}"
SUBMISSION_DIR="arxiv-submission"
```
</step>

<step name="manuscript_preflight">
**Refresh the manuscript-root build contract before packaging.**

Treat `gpd paper-build` as authoritative for `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json`. If `${PAPER_DIR}/PAPER-CONFIG.json` exists, refresh the manuscript before packaging:

```bash
gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"
```

In strict mode, `bibliography_audit_clean` and `reproducibility_ready` must pass before the workflow continues. Do not package stale audit artifacts.
Strict preflight also requires `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json` beside the resolved manuscript entry point.

If `pdflatex` is available, run a local smoke check after the refreshed manuscript is in place. Any LaTeX error, undefined control sequence, missing reference, or missing figure is a hard stop. If `pdflatex` is not available, report that the smoke check was skipped and continue only if the manuscript-root contract remains clean.
</step>

<step name="review_gate">
**Require the latest review-round evidence before submission packaging.**

Load the shared latest-round publication contract:

@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md
@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md

Require the latest `GPD/review/REVIEW-LEDGER*.json` and `GPD/review/REFEREE-DECISION*.json` pair for the active manuscript. Packaging may continue only when the latest recommendation is `accept` or `minor_revision` and there are no unresolved blocking issues.
Strict preflight also requires the latest round-specific `GPD/review/REVIEW-LEDGER*.json` / `GPD/review/REFEREE-DECISION*.json` pair as authoritative submission-gate input.

If the manuscript is theorem-bearing, `manuscript_proof_review` must also already be cleared. Require a current `PROOF-REDTEAM*.md` artifact. A stale or missing proof review is a hard stop.

Do not mix round suffixes across review artifacts, response artifacts, or manuscript-root outputs.
</step>

<step name="package">
**Create the arXiv submission tree.**

Keep the packaging rules arXiv-specific and deterministic:

1. Flatten all `\input{}` and `\include{}` chains into a single submission root file.
2. Inline the `.bbl` bibliography and remove any remaining `\bibliography{}` commands.
3. Copy or convert figures into arXiv-compatible formats only.
4. Reject unresolved placeholders such as `RESULT PENDING`, `\cite{MISSING:...}`, or unresolved `TODO` / `FIXME` markers.
5. Package ancillary files only when they are present and relevant.
6. Remove LaTeX auxiliary files, editor backups, and metadata noise from the submission tree.
7. Generate `00README.XXX` only when the submission contains more than one file.

Use these arXiv-specific checks:

| Issue | Action |
|---|---|
| TIFF figures | Convert to PNG before packaging |
| PDF figures | Keep only if the manuscript is using `pdflatex` and `\pdfoutput=1` is present before `\documentclass` |
| EPS figures | Warn if fonts are not embedded |
| Abstract too long | Warn if the abstract exceeds the arXiv metadata limit |
| Total package size | Fail if the package exceeds the arXiv limit |
| Missing bibliography flattening | Fail closed |

If the manuscript root is not already `paper/`, stage the package in a temporary submission tree that preserves the resolved manuscript root as the upload entrypoint and keeps the root-level file layout flat.
</step>

<step name="finalize">
**Create the tarball and present the submission checklist.**

Create `arxiv-submission.tar.gz`, verify that the main manuscript file is at the tarball root, and present a final checklist with:

- package path and size
- figure count
- quality score / status, if available
- LaTeX smoke-check status
- bibliography flattening status
- figure compatibility status
- placeholder scan status
- `\pdfoutput=1` status
- manual submission steps still required

Do not treat prose-only success as complete. The tarball must exist on disk and the manuscript-root / latest-review gates must still be satisfied.
</step>

<community_contribution>

After the arXiv package is finalized, display:

```
────────────────────────────────────────────────────────
📄 Share your work with the GPD community

When the paper is posted to arXiv or otherwise public,
consider opening a pull request to add it to the
README.md "Papers Using GPD" list:

  https://github.com/psi-oss/get-physics-done#papers-using-gpd

What to include:
  • A short summary of the problem and approach
  • The GPD commands/workflow you used
  • Key results or figures (optional)

This helps other researchers discover real GPD papers and
learn from concrete workflows.
────────────────────────────────────────────────────────
```

This prompt is informational only. Do not block the submission workflow on it.

</community_contribution>

</process>

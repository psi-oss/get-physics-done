<purpose>
Prepare a completed paper for arXiv submission.

Stages: `bootstrap` -> `manuscript_preflight` -> `review_gate` -> `package` -> `finalize`.

The `arxiv-submission-stage-manifest.json` sidecar is executable through `gpd --raw init arxiv-submission --stage <stage_id>`. Executable stages: `gpd --raw init arxiv-submission --stage bootstrap`, `manuscript_preflight`, `review_gate`, `package`, `finalize`. Load the active stage payload before stage-specific authority; keep centralized command-context and strict review-preflight validators as the manuscript gate.

Keep arXiv-only rules inline; shared bootstrap owns manuscript and review gates.

Output: a submission-ready `arxiv-submission.tar.gz` under `GPD/publication/<subject_slug>/arxiv/` and a manual submission checklist.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's `execution_context` before starting.
Also read the shared publication bootstrap reference before resolving the manuscript target:

@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md
</required_reading>

<process>

<step name="bootstrap" priority="first">
**Resolve the manuscript target and publication bootstrap context.**

Load the staged bootstrap payload before resolving the manuscript target:

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  BOOTSTRAP_INIT=$(gpd --raw init arxiv-submission --stage bootstrap -- "$ARGUMENTS")
else
  BOOTSTRAP_INIT=$(gpd --raw init arxiv-submission --stage bootstrap)
fi
if [ $? -ne 0 ]; then
  echo "ERROR: arxiv-submission bootstrap init failed: $BOOTSTRAP_INIT"
  exit 1
fi
INIT="$BOOTSTRAP_INIT"
PROJECT_ROOT=$(echo "$INIT" | gpd json get .project_root --default "")
if [ -n "$PROJECT_ROOT" ]; then
  cd "$PROJECT_ROOT" || {
    echo "ERROR: could not enter resolved project root: $PROJECT_ROOT"
    exit 1
  }
fi
```

Run centralized context preflight before continuing:

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  CONTEXT=$(gpd --raw validate command-context arxiv-submission -- "${ARGUMENTS}")
else
  CONTEXT=$(gpd --raw validate command-context arxiv-submission)
fi
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Run the centralized review preflight before continuing and keep its raw routing fields:

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  REVIEW_PREFLIGHT=$(gpd --raw validate review-preflight arxiv-submission --strict -- "${ARGUMENTS}")
else
  REVIEW_PREFLIGHT=$(gpd --raw validate review-preflight arxiv-submission --strict)
fi
if [ $? -ne 0 ]; then
  echo "$REVIEW_PREFLIGHT"
  exit 1
fi
```

Parse `REVIEW_PREFLIGHT` for `publication_subject_slug`, `publication_lane_kind`, `managed_publication_root`, `selected_publication_root`, `selected_review_root`, `manuscript_root`, and `manuscript_entrypoint`. Use the shared publication bootstrap reference as the source of truth for manuscript-root resolution, latest-review discovery, latest-response discovery, and paired response gating. Do not duplicate those contracts here.
If review preflight exits nonzero because of missing project state, missing manuscript, missing compiled manuscript, unresolved publication blockers, degraded review integrity, missing conventions, missing staged review artifacts, a newer response round without fresh staged review clearance, or stale theorem-proof review state, STOP and fix those blockers before packaging.
If `derived_manuscript_proof_review_status` is present, use it as the first-pass theorem-proof freshness for the resolved manuscript, but keep the manuscript-root proof review artifacts authoritative for strict packaging decisions.
Strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and `reproducibility-manifest.json` from the resolved manuscript directory itself. The same resolved manuscript root is also the strict preflight source of truth for packaging.
Current executable policy is conservative: any same-round or newer `gpd:respond-to-referees` author/referee response artifact for the active manuscript requires newer staged `gpd:peer-review` before packaging. Without durable manuscript-change scope metadata, response-only rounds are not arXiv clearance.

Resolve the manuscript target from raw preflight plus `$ARGUMENTS`:

1. Set `resolved_main_tex` from `manuscript_entrypoint` and `resolved_dir` from `manuscript_root` in `REVIEW_PREFLIGHT`.
2. If `$ARGUMENTS` specifies a `.tex` file, it must match that resolved entrypoint and already live under `paper/`, `manuscript/`, `draft/`, or `GPD/publication/<subject_slug>/manuscript/`.
3. If `$ARGUMENTS` specifies a directory, the centralized preflight-resolved entrypoint under that directory is authoritative.
4. Otherwise inspect only the documented GPD-owned manuscript roots: `paper/`, `manuscript/`, `draft/`, and a unique `GPD/publication/<subject_slug>/manuscript/` lane when centralized preflight resolves one.
5. If the manuscript root is ambiguous or missing, STOP and require an explicit manuscript path or a repaired manuscript-root state.
6. Do not accept arbitrary external directories or standalone `.tex` entrypoints outside those supported roots.
7. Do not fall back to `find` or arbitrary wildcard matching outside the documented default roots.

Then run the centralized publication preflight and review preflight checks. If the latest review artifacts are missing, incomplete, stale, or blocked, or if the manuscript-root gates fail, stop before any packaging work starts.
Set `subject_slug` from `publication_subject_slug`. If it is missing, STOP and repair preflight routing instead of deriving a new slug. Package outputs are always rooted at `GPD/publication/${subject_slug}/arxiv/`; treat `selected_publication_root` as validation context only. Do not write proof-review manifests, package staging trees, or tarballs beside the manuscript root itself.

Set:

```bash
PAPER_DIR="${resolved_dir}"
MAIN_SOURCE="${resolved_main_tex}"
MAIN_BASENAME="$(basename "${MAIN_SOURCE}")"
MAIN_STEM="${MAIN_BASENAME%.*}"
PUBLICATION_ROOT="GPD/publication/${subject_slug}"
REVIEW_ROOT="${selected_review_root:-GPD/review}"
PACKAGE_ROOT="${PUBLICATION_ROOT}/arxiv"
SUBMISSION_DIR="${PACKAGE_ROOT}/submission"
PACKAGE_TARBALL="${PACKAGE_ROOT}/arxiv-submission.tar.gz"
```
</step>

<step name="manuscript_preflight">
**Refresh the manuscript-root build contract before packaging.**

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  MANUSCRIPT_PREFLIGHT_INIT=$(gpd --raw init arxiv-submission --stage manuscript_preflight -- "$ARGUMENTS")
else
  MANUSCRIPT_PREFLIGHT_INIT=$(gpd --raw init arxiv-submission --stage manuscript_preflight)
fi
if [ $? -ne 0 ]; then
  echo "ERROR: arxiv-submission manuscript_preflight init failed: $MANUSCRIPT_PREFLIGHT_INIT"
  exit 1
fi
```

Treat `gpd paper-build` as authoritative for `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json`. If `${PAPER_DIR}/PAPER-CONFIG.json` exists, refresh the manuscript before packaging:

```bash
gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"
```

The build result must report the emitted `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json` paths explicitly.
If bibliography input comes from a literature-review citation-source sidecar, pass that file with `--citation-sources` rather than relying on an unrelated single sidecar under `GPD/literature/`.

In strict mode, `bibliography_audit_clean` and `reproducibility_ready` must pass before the workflow continues. Do not package stale audit artifacts.
Strict preflight also requires `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json` beside the resolved manuscript entry point.

If `pdflatex` is available, run a local smoke check after the refreshed manuscript is in place. Any LaTeX error, undefined control sequence, missing reference, or missing figure is a hard stop. If `pdflatex` is not available, report that the smoke check was skipped and continue only if the manuscript-root contract remains clean.
</step>

<step name="review_gate">
**Require the latest review-round evidence before submission packaging.**

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  REVIEW_GATE_INIT=$(gpd --raw init arxiv-submission --stage review_gate -- "$ARGUMENTS")
else
  REVIEW_GATE_INIT=$(gpd --raw init arxiv-submission --stage review_gate)
fi
if [ $? -ne 0 ]; then
  echo "ERROR: arxiv-submission review_gate init failed: $REVIEW_GATE_INIT"
  exit 1
fi
```

Load the shared latest-round publication contract from `{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md` and the staged `peer-review-reliability.md` reference at this stage.

Require the latest staged `REVIEW-LEDGER*.json` and `REFEREE-DECISION*.json` pair for the active manuscript. Packaging may continue only when the latest recommendation is `accept` or `minor_revision` and there are no unresolved blocking issues.
Strict preflight also requires the latest round-specific staged `REVIEW-LEDGER*.json` / `REFEREE-DECISION*.json` pair as authoritative submission-gate input.
If newest round artifacts are `AUTHOR-RESPONSE*.md` / `REFEREE_RESPONSE*.md` but no newer staged `REVIEW-LEDGER*.json` / `REFEREE-DECISION*.json` pair exists, STOP and route back to `gpd:peer-review`. This all-response freshness policy treats response artifacts as revision records, not staged review clearance, until durable change-scope metadata exists.

If the manuscript is theorem-bearing, `manuscript_proof_review` must also already be cleared. Require a current `PROOF-REDTEAM*.md` artifact. A stale or missing proof review is a hard stop.

Do not mix round suffixes across review artifacts, response artifacts, or manuscript-root outputs.
</step>

<step name="package">
**Create the arXiv submission tree.**

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  PACKAGE_INIT=$(gpd --raw init arxiv-submission --stage package -- "$ARGUMENTS")
else
  PACKAGE_INIT=$(gpd --raw init arxiv-submission --stage package)
fi
if [ $? -ne 0 ]; then
  echo "ERROR: arxiv-submission package init failed: $PACKAGE_INIT"
  exit 1
fi
```

Keep the packaging rules arXiv-specific and deterministic:

1. Flatten all `\input{}` and `\include{}` chains into a single submission root file.
2. Inline the `.bbl` bibliography and remove any remaining `\bibliography{}` commands.
3. Copy or convert figures into arXiv-compatible formats only.
4. Reject unresolved placeholders such as `RESULT PENDING`, `\cite{MISSING:...}`, or unresolved `TODO` / `FIXME` markers.
5. Package ancillary files only when they are present and relevant.
6. Remove LaTeX auxiliary files, editor backups, and metadata noise from the submission tree.
7. Generate `00README.XXX` only when the submission contains more than one file.

Keep the submission tree itself under `${SUBMISSION_DIR}`. Do not create a sibling `arxiv-submission/` directory beside the manuscript or place GPD-authored package manifests there.

Use these arXiv-specific checks:

| Issue | Action |
|---|---|
| TIFF figures | Convert to PNG before packaging |
| PDF figures | Keep only if the manuscript is using `pdflatex` and `\pdfoutput=1` is present before `\documentclass` |
| EPS figures | Warn if fonts are not embedded |
| Abstract too long | Warn if the abstract exceeds the arXiv metadata limit |
| Total package size | Fail if the package exceeds the arXiv limit |
| Missing bibliography flattening | Fail closed |

If the manuscript root is not already `paper/`, stage the package in a temporary submission tree that preserves the resolved manuscript root as the upload entrypoint and keeps the root-level file layout flat. The managed package root still remains `${PACKAGE_ROOT}` under `GPD/`.

After `${SUBMISSION_DIR}` is populated, materialize and validate with the executable package boundary. It reruns strict `arxiv-submission` review preflight internally, keeps `${SUBMISSION_DIR}` and `${PACKAGE_TARBALL}` under `${PACKAGE_ROOT}`, rejects unsafe tar paths, symlinks, aux files, placeholders, empty cites/refs, bibliography-command residue, and requires the main `.tex` at tar root:

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  PACKAGE_VALIDATION=$(gpd --raw validate arxiv-package --materialize --submission-dir "$SUBMISSION_DIR" --tarball "$PACKAGE_TARBALL" -- "$ARGUMENTS")
else
  PACKAGE_VALIDATION=$(gpd --raw validate arxiv-package --materialize --submission-dir "$SUBMISSION_DIR" --tarball "$PACKAGE_TARBALL")
fi
if [ $? -ne 0 ]; then
  echo "$PACKAGE_VALIDATION"
  exit 1
fi
```
</step>

<step name="finalize">
**Create the tarball and present the submission checklist.**

```bash
if [ -n "${ARGUMENTS:-}" ]; then
  FINALIZE_INIT=$(gpd --raw init arxiv-submission --stage finalize -- "$ARGUMENTS")
else
  FINALIZE_INIT=$(gpd --raw init arxiv-submission --stage finalize)
fi
if [ $? -ne 0 ]; then
  echo "ERROR: arxiv-submission finalize init failed: $FINALIZE_INIT"
  exit 1
fi
```

Use `PACKAGE_VALIDATION` from `gpd --raw validate arxiv-package --materialize` as the authoritative tarball proof. If resuming at finalize, run the same validator without `--materialize` before reporting success. Present a final checklist with:

- package path and size
- figure count
- quality score / status, if available
- LaTeX smoke-check status
- bibliography flattening status
- figure compatibility status
- placeholder scan status
- `\pdfoutput=1` status
- manual submission steps still required

Do not treat prose-only success as complete. The tarball must be under `GPD/publication/${subject_slug}/arxiv/`, the executable arXiv package validator must pass, and manuscript-root / latest-review gates must hold.
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

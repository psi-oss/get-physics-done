<purpose>
Review a knowledge document, record typed review evidence, and decide whether it is ready to become stable.

This workflow owns the review/promotion half of the knowledge-doc lifecycle only:

- resolve one exact knowledge target from an explicit path or canonical knowledge_id
- validate the current knowledge document and its frontmatter/body snapshot
- write a deterministic review artifact under `GPD/knowledge/reviews/`
- update the knowledge document status and review metadata
- fail closed when approval is stale or the target is ambiguous

This workflow does not claim runtime ingestion into planner/verifier/executor context, and it does not implement full supersession orchestration.

Called from `gpd:review-knowledge`.
</purpose>

<core_principle>
A knowledge document is only stable when the current reviewed snapshot still matches the approved content.

Review is explicit, typed, and freshness-bound. A review artifact without a matching content hash is not a trust anchor. Promotion to `stable` must only happen after a fresh approved review, while `needs_changes` and `rejected` keep the document in `in_review`.
</core_principle>

<process>

<step name="load_context" priority="first">
Load the project and command context before choosing a target:

```bash
INIT=$(gpd --raw init progress --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for:

- `commit_docs`
- `state_exists`
- `project_exists`
- `project_contract`
- `project_contract_gate`
- `project_contract_load_info`
- `project_contract_validation`
- `contract_intake`
- `effective_reference_intake`
- `active_reference_context`

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. If the gate is blocked, keep the contract visible as context but do not promote it to approved truth.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context review-knowledge "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```
</step>

<step name="resolve_target">
Resolve one exact knowledge target from the explicit argument.

Accept only:

1. an exact `GPD/knowledge/{knowledge_id}.md` path
2. a canonical `K-*` knowledge_id that resolves uniquely to that path

Do not guess from fuzzy topic text, stem similarity, or filename ordering.
If more than one candidate exists, stop and ask for clarification.

After resolution, bind:

- `KNOWLEDGE_PATH` = resolved `GPD/knowledge/{knowledge_id}.md`
- `KNOWLEDGE_ID` = canonical knowledge_id from the file stem/frontmatter

If the path does not exist, or if the path and knowledge_id do not match, stop and report the mismatch instead of repairing it silently.
</step>

<step name="load_knowledge_doc">
Read the current knowledge document and parse its frontmatter/body snapshot.

Use the strict knowledge schema to validate:

- filename stem parity
- current lifecycle status
- review metadata shape
- existing freshness state

Read the document body as the trusted content being reviewed. The canonical reviewed-content hash must be computed from the knowledge document's trusted projection, excluding lifecycle-only fields such as `status`, `review`, `created_at`, `updated_at`, and `superseded_by`.
</step>

<step name="determine_review_round">
Determine the next review round deterministically.

Rules:

- if the document has no prior review record, this is `review_round = 1`
- if the document already has a review record, increment the prior `review_round` by one
- if a review artifact already exists for the computed round, stop and ask whether to continue that round or create a newer one

Use the review round to build the artifact path:

```text
GPD/knowledge/reviews/{knowledge_id}-R{review_round}-REVIEW.md
```

Round numbering must stay monotonic for the same knowledge document.
</step>

<step name="write_review_artifact">
Write a deterministic review artifact for the current round.

The artifact should capture:

- `knowledge_id`
- `knowledge_path`
- `reviewed_at`
- `review_round`
- `reviewer_kind`
- `reviewer_id`
- `decision`
- `summary`
- `approval_artifact_path`
- `approval_artifact_sha256`
- `reviewed_content_sha256`
- `stale`

The artifact body should briefly explain:

- what was reviewed
- why the decision was made
- whether the reviewed snapshot is fresh
- what must change before the next review, if anything

The artifact path and hash are part of the trust record, so write them deterministically and validate them after write.
</step>

<step name="apply_lifecycle_decision">
Apply the review decision to the knowledge document.

### `approved`

If the reviewed content hash still matches the current canonical knowledge projection, promote the document to `stable` and record:

- `decision: approved`
- `stale: false`
- `status: stable`

If the content no longer matches the reviewed hash, mark the review stale, keep the document in `in_review`, and do not promote it.

### `needs_changes`

Keep the document in `in_review`, record the typed review metadata, and describe the required changes plainly.

### `rejected`

Keep the document in `in_review`, record the typed review metadata, and explain why the current synthesis is not ready for approval.

In every case, preserve the document body unless the workflow explicitly needs to normalize frontmatter fields required by the new review record.
</step>

<step name="validate_schema">
Validate the updated markdown against the strict knowledge schema before considering the task complete.

Use the repo frontmatter validator against the final file:

```bash
gpd frontmatter validate GPD/knowledge/{knowledge_id}.md --schema knowledge
```

Validation must confirm:

- filename stem matches `knowledge_id`
- `status` and `review` are lifecycle-compatible
- review hashes are well-formed lowercase 64-hex digests
- approved reviews remain fresh
- stale approved evidence cannot masquerade as stable truth

If validation fails, fix the file and re-run validation until it passes.
</step>

<step name="defer_out_of_scope">
This workflow intentionally defers the following behaviors:

- runtime ingestion into planner, verifier, or executor context
- downstream trust propagation beyond the reviewed knowledge document itself
- full supersession orchestration and successor management
- help inventory exposure, command registration, and other CLI surface wiring

If the user asks for any of those behaviors, do not fake them. Stop and route to the later phase that owns them.
</step>

<step name="finish">
When the review is valid:

1. report the canonical file path
2. report the review artifact path
3. report whether the document was promoted, kept in review, or marked stale
4. summarize the input class that was resolved
5. summarize any clarification that was required

Do not claim runtime ingestion or planner trust propagation. This step only establishes an honest review record and lifecycle update for the knowledge document.
</step>

</process>

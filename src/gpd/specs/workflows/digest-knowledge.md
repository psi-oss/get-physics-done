<purpose>
Author or update a project knowledge document with a truthful, deterministic create/update workflow.

This workflow handles the draft-authoring half of the knowledge-doc lifecycle only:

- classify the user input as a knowledge path, source path, arXiv identifier, or topic
- resolve one canonical `knowledge_id` and one canonical file path
- create a new draft knowledge doc or update an existing draft in place
- validate the result against the strict `knowledge` frontmatter schema

This workflow does not claim downstream runtime ingestion, planner/verifier trust propagation, or review-state promotion. Those behaviors are explicitly deferred to later phases.

Called from `gpd:digest-knowledge`.
</purpose>

<core_principle>
A knowledge document is only useful if its identity is deterministic, its target is unambiguous, and its lifecycle claims are honest.

If the input does not clearly map to a single knowledge-doc target, the workflow must stop and ask. If the target already exists as stable or superseded, the workflow must not silently repurpose it as a draft authoring target.
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
- `reference_artifact_files`
- `reference_artifacts_content`

Read mode settings if needed for authoring depth:

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
RESEARCH_MODE=$(gpd --raw config get research_mode 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true. If the gate is blocked, keep the contract visible as context but do not promote it to approved knowledge truth.
</step>

<step name="classify_input">
Classify the command argument(s) into one of four input classes:

1. `knowledge_path`
2. `source_path`
3. `arxiv_id`
4. `topic`

Classification rules:

- `knowledge_path` means an explicit path under `GPD/knowledge/` pointing to a `.md` file
- `source_path` means an explicit file path outside the knowledge tree that exists and can be read as source material
- `arxiv_id` means a modern or legacy arXiv identifier, including accepted prefixes handled by the shared arXiv normalizer
  - modern example: `2401.12345` or `2401.12345v2`
  - legacy example: `hep-th/9901001`
- `topic` means a free-form subject string that is not already an explicit file or arXiv target

If the same input could plausibly be classified in more than one way, stop and ask for clarification instead of guessing.

Examples of ambiguity that must stop:

- a token that is both a plausible filename stem and a plausible topic
- a path-like input that could point either to a knowledge doc or to a source artifact
- multiple existing knowledge docs that could all be the intended update target
</step>

<step name="resolve_target">
Resolve a single canonical target from the classified input.

Resolution order:

1. explicit `knowledge_path`
2. exact existing `knowledge_id`
3. exact existing source match when the source resolves uniquely
4. new deterministic `knowledge_id` derived from the normalized topic or canonical title

Target rules:

- The canonical knowledge directory is `GPD/knowledge/`
- The canonical file name is `GPD/knowledge/{knowledge_id}.md`
- `knowledge_id` must remain stable once chosen
- use the shared ASCII slug normalizer and the shared arXiv normalizer rather than inventing new parsing logic

If a target resolves to more than one candidate, stop and ask one focused clarification question.
Do not pick a candidate by ordering, recency, or filename heuristics.
</step>

<step name="branch_on_existing_target">
Decide whether the target should be created or updated.

### Create

Use create mode when:

- no knowledge doc exists at the resolved path
- or the user explicitly requested a new draft target

### Update

Use update mode when:

- the resolved target exists and is a draft knowledge doc
- and the user intends to revise that draft rather than start a new one

### Stop

Do not author into the target when:

- the target exists and is `stable`
- the target exists and is `superseded`
- the target would require review-state promotion
- the target would require changing the canonical `knowledge_id`

In those cases, stop and route the user to the later lifecycle phase instead of silently mutating the document into a different state.
</step>

<step name="author_draft">
Write or rewrite the draft knowledge document with strict, machine-readable frontmatter and a concise body.

Minimum required frontmatter:

- `knowledge_schema_version`
- `knowledge_id`
- `title`
- `topic`
- `status`
- `created_at`
- `updated_at`
- `sources`
- `coverage_summary`

Conditional fields:

- do not invent `review` in this phase
- do not invent `superseded_by` in this phase
- do not add undeclared keys

Content rules:

- keep the title and topic honest and narrow
- preserve the canonical `knowledge_id`
- record structured sources rather than free-form source prose
- record what is covered, what is excluded, and what remains open
- if the source is an arXiv paper, normalize the arXiv identifier before writing it into source metadata
- if the source is an explicit file path, keep it project-relative when possible and avoid inventing unsupported references

If updating an existing draft, preserve the identity and revise only the content that changed.
If creating a new doc, initialize it as `status: draft`.
</step>

<step name="validate_schema">
Validate the generated markdown against the strict `knowledge` schema before considering the task complete.

Use the repo's frontmatter validator against the final file:

```bash
gpd frontmatter validate GPD/knowledge/{knowledge_id}.md --schema knowledge
```

Validation must confirm:

- filename stem matches `knowledge_id`
- `knowledge_schema_version` is `1`
- required fields are present
- `sources` is structured and non-empty
- `coverage_summary` is structured
- draft lifecycle rules are satisfied

If validation fails, fix the file and re-run validation until it passes.
</step>

<step name="defer_out_of_scope">
This workflow intentionally defers the following behaviors:

- review approval and evidence capture
- `stable` lifecycle promotion
- supersession and replacement policy
- runtime ingestion into planner/verifier/executor context
- help inventory and command registration, which are handled by the command wrapper and help surfaces

If the user asks for any of those behaviors, do not fake them. Stop and route to the later phase that owns them.
</step>

<step name="finish">
When the draft is valid:

1. report the canonical file path
2. report whether the document was created or updated
3. summarize the input class that was resolved
4. summarize any clarification that was required

Do not claim downstream trust or ingestion. This step only establishes an honest draft knowledge document.
</step>

</process>

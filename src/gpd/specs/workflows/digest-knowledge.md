<purpose>
Create or update a reviewed knowledge document in `GPD/knowledge/`. Light path: research the topic, write a Draft, present for user review, promote to Stable on approval.
</purpose>

<required_reading>
@{GPD_INSTALL_DIR}/templates/knowledge.md
</required_reading>

<process>

<step name="detect_input">
Determine input type from the argument:

- **arXiv ID** (matches `DDDD.DDDDD` pattern): fetch the paper via web_search/web_fetch
- **File path** (exists on disk): read the file as source material
- **Topic string** (everything else): research the topic via web_search

</step>

<step name="check_existing">
Check if `GPD/knowledge/` exists and scan for existing knowledge docs on this topic:

```bash
find GPD/knowledge -name "*.md" 2>/dev/null || echo "NO_KNOWLEDGE_DIR"
```

If a related doc exists, ask the user: update the existing doc or create a new one?
</step>

<step name="assign_id">
Determine the next sequential ID:

```bash
ls GPD/knowledge/K-*.md 2>/dev/null | sort | tail -1
```

If no docs exist, start with `K-001`. Otherwise increment from the highest existing number.
</step>

<step name="research">
Research the topic thoroughly:

1. If arXiv paper: read the paper, extract key results, equations, conventions
2. If topic: search for authoritative sources (textbooks, review articles, seminal papers)
3. For every method or result cited, read the actual source — do not rely on training knowledge alone
4. Identify convention choices and flag any clashes between sources
5. Note traps and subtleties — what could go wrong if someone uses this knowledge carelessly?

Cross-reference with `GPD/CONVENTIONS.md` to ensure consistency with project conventions.
</step>

<step name="write_draft">
Create `GPD/knowledge/` directory if needed:

```bash
mkdir -p GPD/knowledge
```

Write the knowledge document following the template at `{GPD_INSTALL_DIR}/templates/knowledge.md`.

Set `status: Draft` in the frontmatter. All sections are required — if you don't have content for a section, write "None identified" rather than omitting it.

```bash
gpd commit "docs: add knowledge doc K-{NNN}-{slug} (Draft)" --files "GPD/knowledge/K-{NNN}-{slug}.md"
```
</step>

<step name="present_for_review">
Present the Draft to the user:

1. Summarize what the document covers (2-3 sentences)
2. List the key results found
3. Flag any conventions that required a choice
4. Flag any traps or subtleties discovered
5. Ask: "Review this knowledge document. Should I mark it Stable, revise it, or leave as Draft?"

</step>

<step name="handle_review">
Based on user response:

**"Stable" / approve:**
- Update frontmatter: `status: Stable`, `last_reviewed: [today]`, `review_rounds: 1`
- Commit: `gpd commit "docs: mark K-{NNN}-{slug} Stable" --files "GPD/knowledge/K-{NNN}-{slug}.md"`

**Revise / changes requested:**
- Apply the requested changes
- Re-present for review
- Loop until approved or user says to leave as Draft

**"Leave as Draft":**
- No changes. The document remains Draft for future review.

</step>

</process>

<success_criteria>
- Knowledge document exists in `GPD/knowledge/` with valid frontmatter
- All template sections present (even if "None identified")
- Conventions cross-referenced with CONVENTIONS.md
- Status reflects actual review state (Draft if unreviewed, Stable if user approved)
- Committed to git
</success_criteria>

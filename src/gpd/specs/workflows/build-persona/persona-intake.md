<purpose>
Confirm the research persona-building scope and consent boundary before any
interview or explicit source read.
</purpose>

<hard_boundaries>
- No silent memory: do not silently create, infer, or update persona memory.
- Do not read raw private persona profile content into prompts or child handoffs.
- Do not inspect project files, papers, collaborators, references, or tool
  metadata until the user explicitly approves the source category.
- Do not read a paper path, BibTeX path, repository root, manual JSON patch, or
  user statement until the exact category and path or text is confirmed.
- Do not mutate persona storage in this stage.
</hard_boundaries>

<process>
1. State that this workflow produces a candidate `ResearchPersonaPatch` only.
2. Ask which source mode is in scope: interview, current project, paper path,
   BibTeX path, repository scan, manual JSON patch, user statement, or stop.
3. For the selected mode, confirm the exact source category and path or text
   before any read:
   - Interview: approved topics and privacy defaults.
   - Current project: approved path categories such as `GPD/STATE.md`,
     `GPD/ROADMAP.md`, `GPD/knowledge/*.md`, `GPD/literature/*.md`, manuscript
     files, package metadata, or selected references.
   - Paper path: the exact manuscript or paper path.
   - BibTeX path: the exact `.bib` path.
   - Repository scan: the exact repository root and scan categories.
   - Manual JSON patch: the exact candidate patch path.
   - User statement: the exact statement text and desired privacy label.
4. Select a candidate patch destination such as
   `GPD/persona/candidate-patch.json` or a `/tmp` path.
5. Carry forward only scope, consent, source handles, and candidate output
   location to source ingestion and synthesis.
</process>

<approval_boundary>
Explicit user approval is required before mutation. Do not apply-patch in this
stage; the approval stage owns the review route through:

```text
gpd research-persona validate
gpd research-persona diff
gpd research-persona apply-patch
```
</approval_boundary>

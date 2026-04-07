---
name: gpd:digest-knowledge
description: Create or update a reviewed knowledge document from a topic, paper, or existing research
argument-hint: "<topic or arXiv-ID>"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - find_files
  - search_files
  - shell
  - web_search
  - web_fetch
  - ask_user
---

<objective>
Create a knowledge document in `GPD/knowledge/` with a trust lifecycle (Draft → Stable).

Knowledge documents capture reviewed domain understanding — key results, equations,
conventions, derivation sketches, and traps. Unlike one-shot RESEARCH.md reports,
knowledge documents are project-scoped and carry an explicit trust status.

Input can be:
- An arXiv ID (e.g., `2301.12345`) — fetch and digest the paper
- A topic (e.g., `"Fuchsian ODE methods"`) — research and synthesize
- A file path to an existing document to digest
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md
</execution_context>

<context>
@GPD/CONVENTIONS.md
</context>

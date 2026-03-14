---
name: gpd:graph
description: Visualize dependency graph across phases and identify gaps
argument-hint: ""
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Build and visualize the dependency graph across all research phases. Shows how results flow between phases (provides/requires/affects) and identifies gaps where a phase requires something no other phase provides.

Use this for:

- Understanding how phases connect before planning
- Identifying missing dependencies or orphaned results
- Checking that the research roadmap is internally consistent
- Visualizing the critical path through the research
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/graph.md
</execution_context>

<context>
@.gpd/ROADMAP.md
</context>

<process>
Execute the graph workflow from @{GPD_INSTALL_DIR}/workflows/graph.md end-to-end.

## Step 1: Read All SUMMARY.md Frontmatter

Scan all phase directories for SUMMARY.md files. Extract `provides`, `requires`, and `affects` from frontmatter.

## Step 2: Build Dependency Graph

Construct a directed graph: edges from providers to consumers.

## Step 3: Generate Graph Visualization

Build the graph directly from `ROADMAP.md` plus SUMMARY frontmatter, then present it in the format that best fits the user's request:

- ASCII for quick terminal inspection
- Mermaid for markdown embedding
- DOT if the user explicitly wants Graphviz-compatible output
- JSON only if a downstream tool or workflow needs structured graph data

## Step 4: Validate Dependencies

Run cycle detection and gap analysis from the graph you assembled manually.

Report: cycles found, unsatisfied requirements, missing plan dependencies, wave ordering gaps.

## Step 5: Present Results

Display the graph, gap analysis, and critical path. Highlight any cycles or unsatisfied requirements.

## Step 6: Optionally Write

Offer to write the graph and analysis to `.gpd/DEPENDENCY-GRAPH.md`.
</process>

<success_criteria>

- [ ] All SUMMARY.md frontmatter parsed for provides/requires/affects
- [ ] Dependency graph constructed with cycle detection
- [ ] Graph visualization generated (ASCII, Mermaid, or DOT)
- [ ] Dependency validation run (cycles, gaps, unsatisfied requirements)
- [ ] Results presented clearly with any issues highlighted
- [ ] Optional write to .gpd/DEPENDENCY-GRAPH.md offered
      </success_criteria>

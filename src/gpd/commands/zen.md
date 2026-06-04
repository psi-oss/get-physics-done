---
name: gpd:zen
description: Print a short physics-research zen koan to reset your focus, without taking any action
argument-hint: "[optional mood word]"
context_mode: projectless
allowed-tools:
  - file_read
help:
  group: Starter commands
  order: 50
  compact_description: Print a short research koan and take no action
  display_signature: gpd:zen
---


<objective>
Print one short physics-research zen koan to help the user reset focus between
tasks. This is a purely decorative, read-only command. Do not create project
artifacts, write files, run analysis, infer setup, or route into another
workflow.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/zen.md
</execution_context>

<process>
Follow the included zen workflow exactly.
</process>

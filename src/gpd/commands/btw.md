---
name: gpd:btw
description: Add context, notes, or background information to the current conversation
argument-hint: "<text to add as context>"
context_mode: global
allowed-tools:
  - file_read
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Accept user-provided context, background information, or notes inline and acknowledge them as part of the current conversation.

This is the lightest GPD command: it does not write files, spawn agents, or modify project state. It exists so users can paste or type additional context mid-conversation using a familiar slash-command surface.

The entire user payload arrives as `$ARGUMENTS` — the text after `/gpd:btw `. This supports both typed and pasted input of any length.

Typical uses:

- Pasting a paragraph from a paper or referee report for discussion
- Adding a constraint or assumption the AI should keep in mind
- Sharing an equation, error message, or log output
- Providing background that applies to subsequent commands
</objective>

<process>

## Step 1: Read the provided context

The user's note is the full content of `$ARGUMENTS`.

- If `$ARGUMENTS` is empty, respond:
  > Usage: `/gpd:btw <your text here>`
  >
  > Paste or type any context you want me to keep in mind — equations, constraints, paper excerpts, error messages, or background notes.
  and STOP.

## Step 2: Acknowledge and incorporate

1. Confirm receipt: briefly summarize what you understood from the provided text (1-2 sentences).
2. State that you will keep this context in mind for the remainder of the conversation.
3. If the text appears to be a question rather than context, answer it directly.

Do NOT:
- Write any files
- Modify project state
- Spawn subagents
- Create git commits

</process>

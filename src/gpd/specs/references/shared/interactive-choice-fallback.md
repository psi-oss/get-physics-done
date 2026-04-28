Use `ask_user` for structured choices when the runtime supports it. If `ask_user` is not available, present the same choices in plain text, keep the same option labels, and wait for the user's freeform response. Do not duplicate the same question through both surfaces in one turn.

When a choice is inherently freeform, ask inline instead of forcing `ask_user`.

"""Shared constants for execution segment lifecycle states."""

COMPLETED_SEGMENT_STATES = frozenset({"completed", "complete", "done", "finished"})
PAUSED_SEGMENT_STATES = frozenset({"paused", "awaiting_user", "ready_to_continue"})


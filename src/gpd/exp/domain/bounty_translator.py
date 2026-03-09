"""Bounty translator domain module.

Layer 1 pure domain logic: no framework imports, no side effects, no I/O.
Translates an ExperimentProtocol into a BountySpec suitable for posting on
a human-task platform.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from gpd.exp.contracts.bounty import BountySpec
from gpd.exp.contracts.budget import Currency
from gpd.exp.contracts.experiment import ExperimentProtocol, VariableRole

#: Token that workers must include in their response to pass the attention check.
ATTENTION_TOKEN = "4"

#: Maximum length for the question snippet in bounty titles.
_QUESTION_SNIPPET_MAX_LEN = 80

#: Maximum length for the full bounty title.
_TITLE_MAX_LEN = 200


def compute_protocol_hash(protocol: ExperimentProtocol) -> str:
    """Compute a stable 16-char hex identifier for a protocol.

    Uses SHA-256 of the protocol's canonical JSON representation.
    Truncated to 16 hex characters for readability.
    """
    json_bytes = protocol.model_dump_json().encode("utf-8")
    return hashlib.sha256(json_bytes).hexdigest()[:16]


def compute_bounty_deadline(
    experiment_deadline: datetime,
    expected_duration_minutes: int | None,
    buffer_minutes: int = 90,
) -> datetime:
    """Compute a safe bounty deadline that always precedes the experiment deadline.

    The returned deadline is min(now + duration*3, experiment_deadline - buffer).

    Args:
        experiment_deadline: The hard deadline for the whole experiment.
        expected_duration_minutes: Expected task duration in minutes, or None.
        buffer_minutes: Minimum gap (in minutes) between bounty deadline and
            experiment deadline. Defaults to 90.

    Returns:
        A timezone-aware datetime that is strictly earlier than the experiment
        deadline by at least `buffer_minutes`.

    Raises:
        ValueError: If `experiment_deadline - buffer_minutes <= now`, meaning
            there is no time left to post a valid bounty.
    """
    now = datetime.now(tz=UTC)

    # Ensure experiment_deadline is timezone-aware
    if experiment_deadline.tzinfo is None:
        experiment_deadline = experiment_deadline.replace(tzinfo=UTC)

    latest_allowed = experiment_deadline - timedelta(minutes=buffer_minutes)

    if latest_allowed <= now:
        raise ValueError(
            f"Insufficient time to post a bounty: experiment deadline "
            f"{experiment_deadline.isoformat()} leaves less than {buffer_minutes} "
            f"minutes of buffer (buffer deadline: {latest_allowed.isoformat()})."
        )

    if expected_duration_minutes is None:
        # Hard cap path: use the latest allowed deadline directly
        return latest_allowed

    # Candidate: now + 3x expected duration to allow for latency
    candidate = now + timedelta(minutes=expected_duration_minutes * 3)

    return min(candidate, latest_allowed)


def translate_protocol_to_bounty_spec(
    protocol: ExperimentProtocol,
    experiment_deadline: datetime,
    price_cents: int,
) -> BountySpec:
    """Assemble a complete BountySpec from an ExperimentProtocol.

    The description follows a structured format:
      - ATTENTION CHECK prefix (required for platform compliance)
      - TASK OVERVIEW with the research question
      - EQUIPMENT REQUIRED section listing all materials
      - CONTROLS section (only when CONTROL-role variables are present)
      - MEASUREMENT PROCEDURE section (verbatim from protocol)
      - SUBMIT footer with submission instructions

    Args:
        protocol: The fully-designed experiment protocol.
        experiment_deadline: Hard experiment deadline (never exceeded).
        price_cents: Payment amount in integer cents.

    Returns:
        A BountySpec ready to be posted on a human-task platform.
    """
    # ------------------------------------------------------------------
    # Build description sections
    # ------------------------------------------------------------------
    parts: list[str] = []

    # Attention check prefix (required, must be first)
    parts.append(
        "ATTENTION CHECK: To confirm you have read these instructions carefully, "
        f"include the number {ATTENTION_TOKEN} somewhere in your submission response."
    )

    # Task overview
    parts.append(
        f"\nTASK OVERVIEW\n"
        f"You are assisting with a scientific study. Your task is to collect "
        f"a single data point for the following research question:\n"
        f'"{protocol.question}"'
    )

    # Equipment required (from materials_required)
    if protocol.materials_required:
        equipment_lines = "\n".join(f"- {item}" for item in protocol.materials_required)
        parts.append(f"\nEQUIPMENT REQUIRED\n{equipment_lines}")

    # Controls section (only if CONTROL-role variables exist)
    control_vars = [v for v in protocol.variables if v.role == VariableRole.CONTROL]
    if control_vars:
        control_lines = []
        for var in control_vars:
            line = f"- {var.name}"
            if var.unit:
                line += f" (units: {var.unit})"
            control_lines.append(line)
        parts.append("\nCONTROLS\nKeep the following variables constant:\n" + "\n".join(control_lines))

    # Measurement procedure (verbatim)
    parts.append(f"\nMEASUREMENT PROCEDURE\n{protocol.measurement_procedure}")

    # Submit footer — instructs workers to use conversation for data delivery
    parts.append(
        "\nSUBMIT\n"
        "When you have completed the measurement:\n"
        "1. Share your data via the conversation chat (paste a Dropbox or Google Drive link "
        "if you have files to share).\n"
        "2. Include your location (city, state/country).\n"
        f"3. Include the number {ATTENTION_TOKEN} in your message to confirm you completed the attention check.\n"
        "4. After sharing your data, mark the task as delivered on the platform."
    )

    description = "\n".join(parts)

    # ------------------------------------------------------------------
    # Build title (capped at 200 chars total, question capped at 80 chars)
    # ------------------------------------------------------------------
    question_snippet = protocol.question[:_QUESTION_SNIPPET_MAX_LEN]
    title = f"Research Task: {question_snippet}"
    title = title[:_TITLE_MAX_LEN]

    # ------------------------------------------------------------------
    # Compute deadline (never exceeds experiment_deadline)
    # ------------------------------------------------------------------
    bounty_deadline = compute_bounty_deadline(
        experiment_deadline=experiment_deadline,
        expected_duration_minutes=protocol.expected_duration_minutes,
    )

    return BountySpec(
        title=title,
        description=description,
        price_cents=price_cents,
        currency=Currency.USD,
        deadline=bounty_deadline,
        skills_needed=["Field Research"],
        requirements=[
            "Must complete attention check correctly",
            "Must have required equipment",
        ],
        spots_available=1,
    )

"""Tests for defensive guards in gpd.core.extras and gpd.core.results.

These tests verify that malformed or unexpected data does not crash the
core functions but is handled gracefully — by skipping bad items and
logging warnings, or by returning sensible defaults.
"""

from __future__ import annotations

import logging

from gpd.contracts import VerificationEvidence, contract_from_data
from gpd.core.extras import (
    ApproximationCheckResult,
    approximation_check,
    approximation_list,
)
from gpd.core.results import (
    _normalize_verification_records,
    result_add,
    result_update,
    result_verify,
)

# --- extras.py: approximation_check with malformed data ----------------------


class TestApproximationCheckMalformedData:
    """approximation_check must not crash on non-dict items or invalid dicts."""

    def test_string_item_in_approximations_is_skipped(self):
        """A plain string in the approximations list should be silently skipped."""
        state = {"approximations": ["not a dict"]}
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []
        assert result.marginal == []
        assert result.invalid == []
        assert result.unchecked == []

    def test_integer_item_in_approximations_is_skipped(self):
        """An integer in the approximations list should be silently skipped."""
        state = {"approximations": [42]}
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []
        assert result.unchecked == []

    def test_none_item_in_approximations_is_skipped(self):
        """A None entry in the approximations list should be silently skipped."""
        state = {"approximations": [None]}
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []

    def test_list_item_in_approximations_is_skipped(self):
        """A nested list in the approximations list should be silently skipped."""
        state = {"approximations": [["nested", "list"]]}
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []

    def test_dict_with_wrong_keys_is_skipped(self):
        """A dict missing the required 'name' field should be skipped via Pydantic validation."""
        state = {"approximations": [{"wrong_key": "value", "another": 123}]}
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []
        assert result.marginal == []
        assert result.invalid == []
        assert result.unchecked == []

    def test_valid_items_survive_alongside_malformed_ones(self):
        """Valid approximation dicts must still be processed when malformed items are present."""
        state = {
            "approximations": [
                "junk string",
                None,
                {"name": "Born approx", "validity_range": "x << 1", "current_value": "0.01"},
                42,
                {"wrong_key_only": True},
                {"name": "No range", "validity_range": "", "current_value": ""},
            ]
        }
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        # "Born approx" with value 0.01 << 1 => valid
        assert len(result.valid) == 1
        assert result.valid[0].name == "Born approx"
        # "No range" has no validity_range => unchecked
        assert len(result.unchecked) == 1
        assert result.unchecked[0].name == "No range"
        # Malformed items (string, None, int, wrong-key dict) all skipped
        assert result.marginal == []
        assert result.invalid == []

    def test_empty_approximations_key(self):
        """An empty approximations list returns an empty result, not an error."""
        state = {"approximations": []}
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []

    def test_missing_approximations_key(self):
        """A state dict with no 'approximations' key returns an empty result."""
        result = approximation_check({})
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []
        assert result.unchecked == []

    def test_boolean_item_in_approximations_is_skipped(self):
        """A boolean in the approximations list should be silently skipped."""
        state = {"approximations": [True, False]}
        result = approximation_check(state)
        assert isinstance(result, ApproximationCheckResult)
        assert result.valid == []


class TestApproximationListMalformedData:
    """approximation_list has the same isinstance + Pydantic guards."""

    def test_non_dict_items_are_filtered_out(self):
        """approximation_list should skip non-dict items in the list."""
        state = {
            "approximations": [
                "string entry",
                None,
                123,
                {"name": "Surviving approx"},
            ]
        }
        result = approximation_list(state)
        assert len(result) == 1
        assert result[0].name == "Surviving approx"

    def test_invalid_dict_is_filtered_out(self):
        """A dict that fails Pydantic validation should be skipped."""
        state = {
            "approximations": [
                {"not_a_valid_field": "oops"},
                {"name": "Good one"},
            ]
        }
        result = approximation_list(state)
        assert len(result) == 1
        assert result[0].name == "Good one"


# --- results.py: _normalize_verification_records with bad data ----------------


class TestNormalizeVerificationRecordsBadData:
    """_normalize_verification_records skips bad items with a warning log."""

    def test_none_input_returns_empty_list(self):
        """None input should return an empty list."""
        assert _normalize_verification_records(None) == []

    def test_empty_list_returns_empty_list(self):
        """An empty list should return an empty list."""
        assert _normalize_verification_records([]) == []

    def test_valid_dict_is_normalized(self):
        """A well-formed dict should be converted to VerificationEvidence."""
        records = _normalize_verification_records(
            [{"verifier": "test", "method": "manual", "confidence": "high"}]
        )
        assert len(records) == 1
        assert isinstance(records[0], VerificationEvidence)
        assert records[0].verifier == "test"

    def test_verification_evidence_passes_through(self):
        """An existing VerificationEvidence instance should pass through unchanged."""
        evidence = VerificationEvidence(verifier="test", method="manual", confidence="medium")
        records = _normalize_verification_records([evidence])
        assert len(records) == 1
        assert records[0] is evidence

    def test_string_item_is_skipped_with_warning(self, caplog):
        """A plain string in the records list should be skipped and logged."""
        with caplog.at_level(logging.WARNING):
            result = _normalize_verification_records(["not a dict"])
        assert result == []
        assert "unsupported type" in caplog.text.lower() or "Skipping" in caplog.text

    def test_integer_item_is_skipped_with_warning(self, caplog):
        """An integer in the records list should be skipped and logged."""
        with caplog.at_level(logging.WARNING):
            result = _normalize_verification_records([42])
        assert result == []
        assert "unsupported type" in caplog.text.lower() or "Skipping" in caplog.text

    def test_none_item_is_skipped_with_warning(self, caplog):
        """A None item in the records list should be skipped and logged."""
        with caplog.at_level(logging.WARNING):
            result = _normalize_verification_records([None])
        assert result == []
        assert "Skipping" in caplog.text

    def test_list_item_is_skipped_with_warning(self, caplog):
        """A nested list item in the records list should be skipped and logged."""
        with caplog.at_level(logging.WARNING):
            result = _normalize_verification_records([["nested"]])
        assert result == []
        assert "Skipping" in caplog.text

    def test_valid_items_survive_alongside_bad_ones(self, caplog):
        """Valid records are kept; bad ones are skipped with warnings."""
        good_record = {"verifier": "tester", "method": "manual", "confidence": "medium"}
        with caplog.at_level(logging.WARNING):
            result = _normalize_verification_records(["junk", good_record, 42, None])
        assert len(result) == 1
        assert isinstance(result[0], VerificationEvidence)
        assert result[0].verifier == "tester"
        # Three bad items should each produce a warning
        warning_count = caplog.text.count("Skipping")
        assert warning_count == 3

    def test_malformed_dict_is_skipped_with_warning(self, caplog):
        """A dict with invalid VerificationEvidence fields should be skipped."""
        with caplog.at_level(logging.WARNING):
            result = _normalize_verification_records(
                [{"confidence": "INVALID_LEVEL"}]
            )
        assert result == []
        assert "Skipping" in caplog.text or "malformed" in caplog.text.lower()


class TestResultAddWithBadVerificationRecords:
    """result_add gracefully handles malformed verification_records via the guard."""

    def test_string_in_verification_records_is_skipped(self, caplog):
        """A plain string in verification_records should be skipped, not crash."""
        state: dict = {}
        with caplog.at_level(logging.WARNING):
            result = result_add(
                state,
                result_id="R-bad-01",
                verification_records=["not a dict"],
            )
        # The bad record was skipped; result added with no verification records
        assert result.id == "R-bad-01"
        assert result.verification_records == []
        assert result.verified is False
        assert "Skipping" in caplog.text

    def test_none_item_in_verification_records_is_skipped(self, caplog):
        """A None item in verification_records should be skipped, not crash."""
        state: dict = {}
        with caplog.at_level(logging.WARNING):
            result = result_add(
                state,
                result_id="R-bad-02",
                verification_records=[None],
            )
        assert result.id == "R-bad-02"
        assert result.verification_records == []
        assert "Skipping" in caplog.text

    def test_mixed_good_and_bad_records_keeps_good_ones(self, caplog):
        """Good verification records survive alongside bad ones."""
        state: dict = {}
        with caplog.at_level(logging.WARNING):
            result = result_add(
                state,
                result_id="R-mixed",
                verification_records=[
                    "bad string",
                    {"verifier": "keeper", "method": "manual", "confidence": "high"},
                    42,
                ],
            )
        assert result.id == "R-mixed"
        assert len(result.verification_records) == 1
        assert result.verification_records[0].verifier == "keeper"
        # The result is verified because it has at least one valid record
        assert result.verified is True
        # Two bad items logged
        assert caplog.text.count("Skipping") == 2


class TestResultVerifyWithExistingBadRecords:
    """result_verify calls _normalize_verification_records on existing records."""

    def test_verify_with_clean_state_works(self):
        """Baseline: result_verify on a result with no prior records succeeds."""
        state: dict = {}
        result_add(state, result_id="R-01")
        result = result_verify(state, "R-01", verifier="tester", confidence="medium")
        assert result.verified is True
        assert len(result.verification_records) == 1

    def test_verify_appends_to_existing_dict_records(self):
        """result_verify should normalize existing dict records and append the new one."""
        state: dict = {}
        result_add(
            state,
            result_id="R-02",
            verification_records=[{"verifier": "first", "method": "manual", "confidence": "low"}],
        )
        result = result_verify(state, "R-02", verifier="second", confidence="high")
        assert result.verified is True
        assert len(result.verification_records) == 2

    def test_verify_skips_corrupted_existing_records(self, caplog):
        """If existing records contain bad items, they are skipped during verify."""
        state: dict = {}
        result_add(state, result_id="R-03")
        # Manually inject a corrupted record into state
        state["intermediate_results"][0]["verification_records"] = [
            "corrupted string record",
            {"verifier": "legit", "method": "manual", "confidence": "medium"},
        ]
        with caplog.at_level(logging.WARNING):
            result = result_verify(state, "R-03", verifier="new-verifier", confidence="high")
        assert result.verified is True
        # One surviving old record + one new record = 2
        assert len(result.verification_records) == 2
        assert "Skipping" in caplog.text


class TestResultUpdateWithBadVerificationRecords:
    """result_update gracefully handles malformed verification_records via the guard."""

    def test_update_with_string_records_skips_them(self, caplog):
        """Passing a string item in verification_records via update should skip it."""
        state: dict = {}
        result_add(state, result_id="R-01")
        with caplog.at_level(logging.WARNING):
            fields, result = result_update(
                state,
                "R-01",
                verification_records=["not a dict"],
            )
        assert "verification_records" in fields
        assert result.verification_records == []
        assert "Skipping" in caplog.text

    def test_update_with_valid_records_succeeds(self):
        """Passing well-formed dict records via update should succeed."""
        state: dict = {}
        result_add(state, result_id="R-01")
        fields, result = result_update(
            state,
            "R-01",
            verification_records=[{"verifier": "auditor", "method": "manual", "confidence": "medium"}],
        )
        assert "verification_records" in fields
        assert result.verified is True
        assert len(result.verification_records) == 1


class TestContractFromDataDefensiveGuard:
    """Malformed contract mappings should degrade to ``None`` instead of raising."""

    def test_contract_from_data_returns_none_for_invalid_mapping(self):
        assert contract_from_data({"scope": {"question": ""}}) is None

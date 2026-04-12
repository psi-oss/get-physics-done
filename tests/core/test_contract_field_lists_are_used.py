from gpd import contracts


def test_contract_field_lists_are_removed():
    for name in (
        "CONTRACT_CONTEXT_INTAKE_FIELD_NAMES",
        "CONTRACT_APPROACH_POLICY_FIELD_NAMES",
        "CONTRACT_UNCERTAINTY_MARKER_FIELD_NAMES",
    ):
        assert not hasattr(contracts, name)

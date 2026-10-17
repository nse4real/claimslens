import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.contracts.models import Contract, Money

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "contracts"
TREATY_FIXTURE = "treaty_two_versions.json"
FAC_FIXTURE = "fac_single_version.json"


def fixture_data(name=TREATY_FIXTURE):
    return deepcopy(json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def assert_invalid(data, expected_text):
    with pytest.raises(ValidationError) as exc_info:
        Contract.model_validate(data)
    assert expected_text in str(exc_info.value)


def test_01_treaty_fixture_loads_with_versions_and_layers():
    contract = Contract.model_validate(fixture_data())

    assert len(contract.versions) == 2
    assert len(contract.versions[0].layers) == 2


def test_02_fac_fixture_loads_with_one_version_and_layer():
    contract = Contract.model_validate(fixture_data(FAC_FIXTURE))

    assert len(contract.versions) == 1
    assert len(contract.versions[0].layers) == 1


def test_09_money_amount_serialises_to_json_string_and_round_trips():
    contract = Contract.model_validate(fixture_data())
    money = contract.versions[0].layers[0].retention
    assert money is not None

    serialised = money.model_dump_json()
    assert json.loads(serialised)["amount"] == "1000000.00"

    round_tripped = Money.model_validate_json(serialised)
    assert round_tripped == money
    assert isinstance(round_tripped.amount, Decimal)


def test_10_other_notice_rule_with_description_and_null_period_is_accepted():
    contract = Contract.model_validate(fixture_data(FAC_FIXTURE))
    rule = contract.versions[0].notice_rules[0]

    assert rule.trigger.value == "other"
    assert rule.trigger_description is not None
    assert rule.period_days is None


def test_11_money_amount_negative():
    data = fixture_data()
    data["versions"][0]["layers"][0]["retention"]["amount"] = "-1.00"

    assert_invalid(data, "amount")


def test_12_money_with_five_decimal_places():
    data = fixture_data()
    data["versions"][0]["layers"][0]["retention"]["amount"] = "1.00001"

    assert_invalid(data, "amount")


def test_13_money_currency_lowercase():
    data = fixture_data()
    data["versions"][0]["layers"][0]["retention"]["currency"] = "gbp"

    assert_invalid(data, "currency")


def test_14_layer_currency_missing():
    data = fixture_data()
    del data["versions"][0]["layers"][0]["currency"]

    assert_invalid(data, "currency")


def test_15_layer_retention_currency_differs_from_layer_currency():
    data = fixture_data()
    data["versions"][0]["layers"][0]["retention"]["currency"] = "USD"

    assert_invalid(data, "retention currency")


def test_16_layer_limit_currency_differs_from_layer_currency():
    data = fixture_data()
    data["versions"][0]["layers"][0]["limit"]["currency"] = "USD"

    assert_invalid(data, "limit currency")


def test_17_layer_expiry_on_or_before_inception():
    data = fixture_data()
    data["versions"][0]["layers"][0]["expiry"] = "2024-01-01"

    assert_invalid(data, "expiry")


def test_18_layer_share_percent_zero():
    data = fixture_data()
    data["versions"][0]["layers"][0]["share_percent"] = "0"

    assert_invalid(data, "share_percent")


def test_19_layer_share_percent_above_100():
    data = fixture_data()
    data["versions"][0]["layers"][0]["share_percent"] = "100.01"

    assert_invalid(data, "share_percent")


def test_20_layer_inception_before_version_effective_from():
    data = fixture_data()
    data["versions"][0]["layers"][0]["inception"] = "2023-12-31"

    assert_invalid(data, "inception")


def test_21_layer_expiry_at_version_effective_to_is_rejected():
    data = fixture_data()
    data["versions"][0]["layers"][0]["expiry"] = "2025-01-01"

    assert_invalid(data, "expiry")


def test_22_version_effective_to_on_or_before_effective_from():
    data = fixture_data()
    data["versions"][0]["effective_to"] = "2024-01-01"

    assert_invalid(data, "effective_to")


def test_23_version_with_zero_layers():
    data = fixture_data()
    data["versions"][0]["layers"] = []

    assert_invalid(data, "layers")


def test_24_duplicate_layer_id_within_one_version():
    data = fixture_data()
    data["versions"][0]["layers"][1]["layer_id"] = "L1"

    assert_invalid(data, "layer_id")


def test_25_layer_section_id_referencing_no_section():
    data = fixture_data()
    data["versions"][0]["layers"][0]["section_id"] = "missing"

    assert_invalid(data, "section_id")


def test_26_duplicate_section_id_within_one_version():
    data = fixture_data()
    data["versions"][0]["sections"][1]["section_id"] = "S1"

    assert_invalid(data, "section_id")


def test_27_duplicate_clause_id_across_sections():
    data = fixture_data()
    data["versions"][0]["sections"][1]["clauses"][0]["clause_id"] = "C1"

    assert_invalid(data, "clause_id")


def test_28_notice_rule_clause_id_referencing_no_clause():
    data = fixture_data()
    data["versions"][0]["notice_rules"][0]["clause_id"] = "missing"

    assert_invalid(data, "clause_id")


def test_29_other_notice_rule_without_description_is_rejected_with_period():
    data = fixture_data(FAC_FIXTURE)
    rule = data["versions"][0]["notice_rules"][0]
    rule["period_days"] = 7
    del rule["trigger_description"]

    assert_invalid(data, "trigger_description")


def test_30_notice_rule_period_days_negative():
    data = fixture_data()
    data["versions"][0]["notice_rules"][0]["period_days"] = -1

    assert_invalid(data, "period_days")


def test_31_null_period_without_description_is_rejected_for_loss_date():
    data = fixture_data()
    data["versions"][0]["notice_rules"][0]["period_days"] = None

    assert_invalid(data, "trigger_description")


def test_32_notice_rule_trigger_outside_enum():
    data = fixture_data()
    data["versions"][0]["notice_rules"][0]["trigger"] = "unknown"

    assert_invalid(data, "trigger")


def test_33_two_versions_with_overlapping_closed_ranges():
    valid_closed_ranges = fixture_data()
    valid_closed_ranges["versions"][1]["effective_to"] = "2026-01-01"
    Contract.model_validate(valid_closed_ranges)

    data = deepcopy(valid_closed_ranges)
    data["versions"][0]["effective_to"] = "2025-06-01"

    assert_invalid(data, "overlap")


def test_34_open_first_version_overlaps_everything_after_its_start():
    data = fixture_data()
    data["versions"][0]["effective_to"] = None

    assert_invalid(data, "overlap")


def test_35_open_second_version_starting_before_first_ends_overlaps():
    data = fixture_data()
    data["versions"][1]["effective_from"] = "2024-06-01"

    assert_invalid(data, "overlap")


def test_36_two_versions_with_same_version_label():
    data = fixture_data()
    data["versions"][1]["version_label"] = "2024-01"

    assert_invalid(data, "version_label")


def test_37_clause_without_source_document_id():
    data = fixture_data()
    del data["versions"][0]["sections"][0]["clauses"][0]["source_document_id"]

    assert_invalid(data, "source_document_id")


def test_38_clause_with_empty_location():
    data = fixture_data()
    data["versions"][0]["sections"][0]["clauses"][0]["location"] = ""

    assert_invalid(data, "location")


def test_39_structure_type_outside_enum():
    data = fixture_data()
    data["structure_type"] = "unknown"

    assert_invalid(data, "structure_type")


def test_40_placement_basis_outside_enum():
    data = fixture_data()
    data["placement_basis"] = "unknown"

    assert_invalid(data, "placement_basis")


def test_41_unknown_key_at_contract_root():
    data = fixture_data()
    data["unexpected_root"] = True

    assert_invalid(data, "unexpected_root")


def test_42_unknown_key_on_nested_layer():
    data = fixture_data()
    data["versions"][0]["layers"][0]["unexpected_layer"] = True

    assert_invalid(data, "unexpected_layer")


def test_43_unknown_key_on_nested_clause():
    data = fixture_data()
    data["versions"][0]["sections"][0]["clauses"][0]["unexpected_clause"] = True

    assert_invalid(data, "unexpected_clause")


def test_44_unknown_key_on_nested_notice_rule():
    data = fixture_data()
    data["versions"][0]["notice_rules"][0]["unexpected_notice"] = True

    assert_invalid(data, "unexpected_notice")

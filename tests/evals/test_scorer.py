"""Acceptance tests for the B10 scorer (plan items 10 to 22)."""

import pytest

from src.evals.scorer import compare_field, score_records, similarity


def empty_prediction() -> dict:
    return {
        "cedent_name": None,
        "treaty_references": [],
        "date_of_loss": None,
        "date_of_notification": None,
        "loss_description": None,
        "estimated_loss_amount": None,
        "cedent_claim_reference": None,
        "original_insured_name": None,
        "territory_or_country": None,
        "peril_or_cause": None,
        "loss_location": None,
        "sender_name": None,
        "sender_role": None,
        "cedent_notes": None,
        "paid_to_date": None,
        "outstanding_reserve": None,
        "uncertain_fields": [],
    }


def test_exact_match_counts_as_tp():
    assert compare_field("cedent_name", "Acme Ltd", "Acme Ltd", "exact") == "tp"
    assert compare_field("cedent_name", "Acme   Ltd", "Acme Ltd", "exact") == "tp"


def test_null_prediction_against_gold_counts_as_fn_recall_only():
    assert compare_field("cedent_name", None, "Acme Ltd", "exact") == "fn_recall"


def test_non_null_prediction_against_null_gold_counts_as_fp_precision_only():
    assert compare_field("cedent_name", "Acme Ltd", None, "exact") == "fp_precision"


def test_both_null_is_ignored():
    assert compare_field("cedent_name", None, None, "exact") == "ignored"


def test_wrong_non_null_value_counts_as_both():
    assert compare_field("cedent_name", "Acme Ltd", "Other Ltd", "exact") == "miss_both"


def test_money_compared_as_decimal_and_currency():
    one = {"amount": "1.0", "currency": "EUR"}
    two = {"amount": "1.00", "currency": "EUR"}
    assert compare_field("estimated_loss_amount", one, two, "exact") == "tp"
    gbp = {"amount": "1.00", "currency": "GBP"}
    assert compare_field("estimated_loss_amount", gbp, two, "exact") == "miss_both"


def test_fuzzy_threshold_boundary():
    at_threshold_a = "a" * 90 + "b" * 10
    at_threshold_b = "a" * 90 + "c" * 10
    assert similarity(at_threshold_a, at_threshold_b) == pytest.approx(0.90)
    assert compare_field("loss_description", at_threshold_a, at_threshold_b, "fuzzy") == "tp"
    below_a = "a" * 89 + "b" * 11
    below_b = "a" * 89 + "c" * 11
    assert similarity(below_a, below_b) == pytest.approx(0.89)
    assert compare_field("loss_description", below_a, below_b, "fuzzy") == "miss_both"


def test_exact_mode_rejects_fuzzy_only_match():
    predicted = "a" * 90 + "b" * 10
    gold = "a" * 90 + "c" * 10
    assert compare_field("loss_description", predicted, gold, "fuzzy") == "tp"
    assert compare_field("loss_description", predicted, gold, "exact") == "miss_both"


def test_treaty_references_set_comparison():
    gold = empty_prediction() | {"treaty_references": ["A", "B"]}
    predicted = empty_prediction() | {"treaty_references": ["A"]}
    report = score_records([("GN-9001", [], predicted, gold)], "exact")
    counts = report.fields["treaty_references"]
    assert counts.tp == 1
    assert counts.fn_recall == 1
    assert counts.fp_precision == 0

    predicted = empty_prediction() | {"treaty_references": ["A", "C"]}
    report = score_records([("GN-9001", [], predicted, gold)], "exact")
    counts = report.fields["treaty_references"]
    assert counts.tp == 1
    assert counts.fp_precision == 1
    assert counts.fn_recall == 1


def test_denominators_reported_and_none_when_zero():
    gold = empty_prediction() | {"cedent_name": "Acme Ltd"}
    predicted = empty_prediction() | {"cedent_name": "Acme Ltd"}
    report = score_records([("GN-9001", [], predicted, gold)], "exact")
    cedent = report.fields["cedent_name"]
    assert cedent.precision_denominator == 1
    assert cedent.recall_denominator == 1
    assert cedent.precision == 1.0
    assert cedent.recall == 1.0
    notes = report.fields["cedent_notes"]
    assert notes.precision_denominator == 0
    assert notes.recall_denominator == 0
    assert notes.precision is None
    assert notes.recall is None


def test_critical_macro_excludes_none_and_counts_contributing():
    gold = empty_prediction() | {"cedent_name": "Acme Ltd"}
    predicted = empty_prediction() | {"cedent_name": "Acme Ltd"}
    report = score_records([("GN-9001", [], predicted, gold)], "exact")
    macro = report.critical_macro
    assert macro.contributing == 2
    assert macro.value == pytest.approx(1.0)


def test_per_tag_counts_record_in_each_of_its_tags():
    gold = empty_prediction() | {"cedent_name": "Acme Ltd"}
    predicted = empty_prediction() | {"cedent_name": "Acme Ltd"}
    report = score_records([("GN-9001", ["clean", "messy"], predicted, gold)], "exact")
    assert report.per_tag["clean"]["cedent_name"].tp == 1
    assert report.per_tag["messy"]["cedent_name"].tp == 1


def test_failed_cases_list_wrong_and_missing_critical_values():
    gold = empty_prediction() | {"cedent_name": "Acme Ltd", "date_of_loss": "2024-05-23"}
    predicted = empty_prediction() | {"cedent_name": "Other Ltd"}
    report = score_records([("GN-9001", [], predicted, gold)], "exact")
    cedent_cases = report.failed_cases["cedent_name"]
    assert len(cedent_cases) == 1
    case = cedent_cases[0]
    assert case.record_id == "GN-9001"
    assert case.field == "cedent_name"
    assert case.predicted == "Other Ltd"
    assert case.gold == "Acme Ltd"
    assert case.cause == "extraction"
    loss_date_cases = report.failed_cases["date_of_loss"]
    assert len(loss_date_cases) == 1
    assert loss_date_cases[0].predicted is None
    assert report.failed_cases["date_of_notification"] == []

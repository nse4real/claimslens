import copy
import json
from pathlib import Path

from src.evals.scorer import SCORED_FIELDS
from src.review.agreement import check_agreement, values_agree

ROOT = Path(__file__).resolve().parents[2]
RECORD_ID = "GN-1001"


def gold_and_decisions():
    record = json.loads((ROOT / "evals" / "gold" / "records" / f"{RECORD_ID}.json").read_text(encoding="utf-8"))
    extraction = record["labels"]["extraction"]
    decisions = {(RECORD_ID, field): copy.deepcopy(extraction[field]) for field in SCORED_FIELDS}
    return extraction, decisions


def test_18_record_with_all_16_values_equal_to_gold_is_agreed():
    extraction, decisions = gold_and_decisions()
    result = check_agreement(RECORD_ID, extraction, decisions)
    assert result.status == "AGREED"
    assert result.agreed is True
    assert result.disagreeing_fields == []


def test_19_changing_only_estimated_loss_currency_disputes_that_field():
    extraction, decisions = gold_and_decisions()
    original = decisions[(RECORD_ID, "estimated_loss_amount")]
    decisions[(RECORD_ID, "estimated_loss_amount")] = {
        "amount": original["amount"],
        "currency": "XXX",
    }
    result = check_agreement(RECORD_ID, extraction, decisions)
    assert result.status == "DISPUTED"
    assert result.disagreeing_fields == ["estimated_loss_amount"]
    assert result.disagreements["estimated_loss_amount"]["reviewer_value"]["currency"] == "XXX"
    assert result.disagreements["estimated_loss_amount"]["gold_value"] == original


def test_20_money_decimal_equivalence_ignores_trailing_zeroes():
    assert values_agree(
        "estimated_loss_amount",
        {"amount": "1.0", "currency": "EUR"},
        {"amount": "1.00", "currency": "EUR"},
    )


def test_21_treaty_references_are_compared_as_a_set():
    assert values_agree("treaty_references", ["FICT-B", "FICT-A"], ["FICT-A", "FICT-B"])

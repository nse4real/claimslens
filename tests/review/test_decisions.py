import csv
import json
from pathlib import Path

import pytest

from src.evals.scorer import SCORED_FIELDS
from src.review.decisions import DECISION_COLUMNS, DecisionsError, read_decisions

ROOT = Path(__file__).resolve().parents[2]
RECORD_IDS = ("GN-1001", "GN-1003")


def serialise(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        return f"{value['amount']} {value['currency']}"
    if isinstance(value, list):
        return ";".join(value)
    return str(value)


def complete_values():
    values = {}
    for record_id in RECORD_IDS:
        record = json.loads((ROOT / "evals" / "gold" / "records" / f"{record_id}.json").read_text(encoding="utf-8"))
        for field in SCORED_FIELDS:
            values[(record_id, field)] = record["labels"]["extraction"][field]
    return values


def write_csv(path, values, columns=DECISION_COLUMNS):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for record_id in RECORD_IDS:
            for field in SCORED_FIELDS:
                if (record_id, field) in values:
                    writer.writerow([record_id, field, serialise(values[(record_id, field)]), ""])


@pytest.fixture
def review_set_path(tmp_path):
    path = tmp_path / "review_set.json"
    path.write_text(
        json.dumps({
            "seed": 20261017,
            "reference_date": "2026-10-17",
            "holdout": [],
            "dev": list(RECORD_IDS),
            "total": 2,
        }),
        encoding="utf-8",
    )
    return path


def test_10_read_decisions_accepts_complete_csv_for_two_records(tmp_path, review_set_path):
    path = tmp_path / "decisions.csv"
    write_csv(path, complete_values())
    decisions = read_decisions(path, review_set_path)
    assert len(decisions) == 32
    assert set(decisions) == {(record_id, field) for record_id in RECORD_IDS for field in SCORED_FIELDS}


def test_11_read_decisions_reports_row_for_missing_header_column(tmp_path, review_set_path):
    path = tmp_path / "decisions.csv"
    path.write_text("record_id,field,reviewer_value\n", encoding="utf-8")
    with pytest.raises(DecisionsError, match="row 1") as error:
        read_decisions(path, review_set_path)
    assert error.value.row_number == 1


def test_12_read_decisions_raises_for_unknown_record_id(tmp_path, review_set_path):
    path = tmp_path / "decisions.csv"
    path.write_text(
        "record_id,field,reviewer_value,reviewer_note\nGN-9999,cedent_name,value,\n",
        encoding="utf-8",
    )
    with pytest.raises(DecisionsError, match="row 2.*unknown record_id"):
        read_decisions(path, review_set_path)


def test_13_read_decisions_raises_for_duplicate_record_field_pair(tmp_path, review_set_path):
    path = tmp_path / "decisions.csv"
    path.write_text(
        "record_id,field,reviewer_value,reviewer_note\n"
        "GN-1001,cedent_name,value,\n"
        "GN-1001,cedent_name,value,\n",
        encoding="utf-8",
    )
    with pytest.raises(DecisionsError, match="row 3.*duplicate"):
        read_decisions(path, review_set_path)


def test_14_read_decisions_raises_for_money_without_currency(tmp_path, review_set_path):
    path = tmp_path / "decisions.csv"
    path.write_text(
        "record_id,field,reviewer_value,reviewer_note\n"
        "GN-1001,estimated_loss_amount,123.45,\n",
        encoding="utf-8",
    )
    with pytest.raises(DecisionsError, match="row 2.*invalid money"):
        read_decisions(path, review_set_path)


def test_15_read_decisions_raises_for_non_iso_date(tmp_path, review_set_path):
    path = tmp_path / "decisions.csv"
    path.write_text(
        "record_id,field,reviewer_value,reviewer_note\n"
        "GN-1001,date_of_loss,23/05/2024,\n",
        encoding="utf-8",
    )
    with pytest.raises(DecisionsError, match="row 2.*invalid ISO date"):
        read_decisions(path, review_set_path)


def test_16_read_decisions_raises_when_a_review_record_field_row_is_missing(tmp_path, review_set_path):
    values = complete_values()
    missing = (RECORD_IDS[-1], SCORED_FIELDS[-1])
    del values[missing]
    path = tmp_path / "decisions.csv"
    write_csv(path, values)
    with pytest.raises(DecisionsError, match="row 33.*missing row") as error:
        read_decisions(path, review_set_path)
    assert missing[0] in str(error.value)
    assert missing[1] in str(error.value)


def test_17_empty_values_and_semicolon_treaty_lists_are_parsed(tmp_path, review_set_path):
    values = complete_values()
    values[(RECORD_IDS[0], "cedent_name")] = None
    values[(RECORD_IDS[0], "treaty_references")] = ["FICT-B", "FICT-A"]
    values[(RECORD_IDS[1], "treaty_references")] = []
    path = tmp_path / "decisions.csv"
    write_csv(path, values)
    decisions = read_decisions(path, review_set_path)
    assert decisions[(RECORD_IDS[0], "cedent_name")] is None
    assert decisions[(RECORD_IDS[0], "treaty_references")] == ["FICT-B", "FICT-A"]
    assert decisions[(RECORD_IDS[1], "treaty_references")] == []

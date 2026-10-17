from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from src.evals.scorer import DATE_FIELDS, MONEY_FIELDS, SCORED_FIELDS
from src.review.review_set import DEFAULT_REVIEW_SET_PATH, read_review_set, review_record_ids

DECISION_COLUMNS = ["record_id", "field", "reviewer_value", "reviewer_note"]
ADJUDICATION_COLUMNS = ["adjudicator", *DECISION_COLUMNS]
MONEY_PATTERN = re.compile(
    r"^(?P<amount>[+-]?(?:\d+(?:\.\d+)?|\.\d+))(?P<separator>[ \t]+)(?P<currency>[A-Z]{3})$"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DecisionsError(ValueError):
    def __init__(self, row_number: int, message: str):
        self.row_number = row_number
        super().__init__(f"row {row_number}: {message}")


@dataclass(frozen=True)
class Adjudication:
    value: Any
    adjudicator: str


def _parse_value(field: str, raw_value: str, row_number: int) -> Any:
    value = raw_value.strip()
    if not value:
        return [] if field == "treaty_references" else None
    if field == "treaty_references":
        return [item.strip() for item in value.split(";") if item.strip()]
    if field in MONEY_FIELDS:
        match = MONEY_PATTERN.fullmatch(value)
        if match is None:
            raise DecisionsError(row_number, f"invalid money value for {field}: {value!r}")
        return {"amount": match.group("amount"), "currency": match.group("currency")}
    if field in DATE_FIELDS:
        if DATE_PATTERN.fullmatch(value) is None:
            raise DecisionsError(row_number, f"invalid ISO date for {field}: {value!r}")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise DecisionsError(row_number, f"invalid ISO date for {field}: {value!r}") from exc
    return value


def _read_rows(
    path: str | Path,
    review_set_path: str | Path,
    *,
    adjudication: bool,
) -> tuple[dict[tuple[str, str], Any], dict[str, str]]:
    review_set = read_review_set(review_set_path)
    record_ids = review_record_ids(review_set)
    known_records = set(record_ids)
    expected_columns = ADJUDICATION_COLUMNS if adjudication else DECISION_COLUMNS
    rows: dict[tuple[str, str], Any] = {}
    adjudicators: dict[str, str] = {}

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DecisionsError(1, "missing header")
        if reader.fieldnames != expected_columns:
            raise DecisionsError(1, f"expected columns {expected_columns}, got {reader.fieldnames}")
        for row in reader:
            row_number = reader.line_num
            if None in row or any(row.get(column) is None for column in expected_columns):
                raise DecisionsError(row_number, "malformed row")
            record_id = row["record_id"].strip()
            field = row["field"].strip()
            if record_id not in known_records:
                raise DecisionsError(row_number, f"unknown record_id: {record_id!r}")
            if field not in SCORED_FIELDS:
                raise DecisionsError(row_number, f"unknown field: {field!r}")
            key = (record_id, field)
            if key in rows:
                raise DecisionsError(row_number, f"duplicate row for {record_id} and {field}")
            if adjudication:
                adjudicator = row["adjudicator"].strip()
                if not adjudicator:
                    raise DecisionsError(row_number, "adjudicator is required")
                if record_id in adjudicators and adjudicators[record_id] != adjudicator:
                    raise DecisionsError(row_number, f"multiple adjudicators for {record_id}")
                adjudicators[record_id] = adjudicator
            rows[key] = _parse_value(field, row["reviewer_value"], row_number)

        if not adjudication:
            missing_row = reader.line_num + 1
            for record_id in record_ids:
                for field in SCORED_FIELDS:
                    if (record_id, field) not in rows:
                        raise DecisionsError(missing_row, f"missing row for {record_id} and {field}")
    return rows, adjudicators


def read_decisions(
    path: str | Path,
    review_set_path: str | Path = DEFAULT_REVIEW_SET_PATH,
) -> dict[tuple[str, str], Any]:
    rows, _ = _read_rows(path, review_set_path, adjudication=False)
    return rows


def read_adjudications(
    path: str | Path,
    review_set_path: str | Path = DEFAULT_REVIEW_SET_PATH,
) -> dict[tuple[str, str], Adjudication]:
    rows, adjudicators = _read_rows(path, review_set_path, adjudication=True)
    return {
        (record_id, field): Adjudication(value, adjudicators[record_id])
        for (record_id, field), value in rows.items()
    }

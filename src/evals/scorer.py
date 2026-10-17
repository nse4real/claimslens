"""Scorer for eval plan M1 (exact) and M2 (fuzzy) field precision and recall.

Implements the null rules of eval plan section 3.2, the money and date rules
of sections 4.3 and 4.4, the fuzzy threshold of section 4.2, and the per-tag
breakdown of section 7.1. Never imports the extractor.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SCORER_VERSION = "scorer-1.0.0"
SIMILARITY_METRIC = "difflib-ratio"
FUZZY_THRESHOLD = 0.90

CRITICAL_FIELDS = (
    "cedent_name",
    "treaty_references",
    "date_of_loss",
    "date_of_notification",
    "loss_description",
    "estimated_loss_amount",
)
# The 16 scored B4 extraction fields, in gold-record order.
SCORED_FIELDS = (
    "cedent_name",
    "treaty_references",
    "date_of_loss",
    "date_of_notification",
    "loss_description",
    "estimated_loss_amount",
    "cedent_claim_reference",
    "original_insured_name",
    "territory_or_country",
    "peril_or_cause",
    "loss_location",
    "sender_name",
    "sender_role",
    "cedent_notes",
    "paid_to_date",
    "outstanding_reserve",
)
TEXT_FIELDS = (
    "cedent_name",
    "loss_description",
    "cedent_claim_reference",
    "original_insured_name",
    "territory_or_country",
    "peril_or_cause",
    "loss_location",
    "sender_name",
    "sender_role",
    "cedent_notes",
)
LIST_FIELDS = ("treaty_references",)
DATE_FIELDS = ("date_of_loss", "date_of_notification")
MONEY_FIELDS = ("estimated_loss_amount", "paid_to_date", "outstanding_reserve")

Mode = Literal["exact", "fuzzy"]
Outcome = Literal["tp", "fp_precision", "fn_recall", "ignored", "miss_both"]


class FieldCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tp: int
    fp_precision: int
    fn_recall: int
    ignored: int
    precision_denominator: int
    recall_denominator: int
    precision: float | None
    recall: float | None

    @classmethod
    def from_counts(cls, tp: int, fp_precision: int, fn_recall: int, ignored: int) -> FieldCounts:
        precision_denominator = tp + fp_precision
        recall_denominator = tp + fn_recall
        return cls(
            tp=tp,
            fp_precision=fp_precision,
            fn_recall=fn_recall,
            ignored=ignored,
            precision_denominator=precision_denominator,
            recall_denominator=recall_denominator,
            precision=tp / precision_denominator if precision_denominator else None,
            recall=tp / recall_denominator if recall_denominator else None,
        )


class CriticalMacro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | None
    contributing: int


class FailedCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    field: str
    predicted: Any
    gold: Any
    cause: str


class ScoreReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    record_count: int
    fields: dict[str, FieldCounts]
    critical_macro: CriticalMacro
    per_tag: dict[str, dict[str, FieldCounts]]
    failed_cases: dict[str, list[FailedCase]]


@dataclass
class _Counts:
    tp: int = 0
    fp_precision: int = 0
    fn_recall: int = 0
    ignored: int = 0

    def add(self, *, tp: int = 0, fp_precision: int = 0, fn_recall: int = 0, ignored: int = 0) -> None:
        self.tp += tp
        self.fp_precision += fp_precision
        self.fn_recall += fn_recall
        self.ignored += ignored

    def to_field_counts(self) -> FieldCounts:
        return FieldCounts.from_counts(self.tp, self.fp_precision, self.fn_recall, self.ignored)


_OUTCOME_DELTAS: dict[str, dict[str, int]] = {
    "tp": {"tp": 1},
    "fp_precision": {"fp_precision": 1},
    "fn_recall": {"fn_recall": 1},
    "ignored": {"ignored": 1},
    "miss_both": {"fp_precision": 1, "fn_recall": 1},
}


def normalise_text(value: Any) -> str:
    """Collapse internal whitespace to single spaces and strip. No lowercasing."""
    return " ".join(str(value).split())


def similarity(a: Any, b: Any) -> float:
    return difflib.SequenceMatcher(None, normalise_text(a), normalise_text(b)).ratio()


def _money_equal(predicted: Any, gold: Any) -> bool:
    if not isinstance(predicted, dict) or not isinstance(gold, dict):
        return False
    try:
        same_amount = Decimal(str(predicted["amount"])) == Decimal(str(gold["amount"]))
    except (InvalidOperation, KeyError, TypeError, ValueError):
        return False
    return same_amount and predicted.get("currency") == gold.get("currency")


def _values_equal(field: str, predicted: Any, gold: Any, mode: Mode) -> bool:
    if field in MONEY_FIELDS:
        return _money_equal(predicted, gold)
    if field in DATE_FIELDS:
        return str(predicted) == str(gold)
    if mode == "exact":
        return normalise_text(predicted) == normalise_text(gold)
    return similarity(predicted, gold) >= FUZZY_THRESHOLD


def compare_field(field: str, predicted: Any, gold: Any, mode: Mode) -> Outcome:
    """Compare one scalar field value. List fields use compare_list_field."""
    if field in LIST_FIELDS:
        raise ValueError(f"{field} is a list field; use compare_list_field")
    if gold is None and predicted is None:
        return "ignored"
    if predicted is None:
        return "fn_recall"
    if gold is None:
        return "fp_precision"
    return "tp" if _values_equal(field, predicted, gold, mode) else "miss_both"


def compare_list_field(predicted: Any, gold: Any) -> dict[str, int]:
    """Compare list fields as sets of normalised strings, item by item."""
    predicted_items = {normalise_text(item) for item in (predicted or [])}
    gold_items = {normalise_text(item) for item in (gold or [])}
    if not predicted_items and not gold_items:
        return {"tp": 0, "fp_precision": 0, "fn_recall": 0, "ignored": 1}
    return {
        "tp": len(predicted_items & gold_items),
        "fp_precision": len(predicted_items - gold_items),
        "fn_recall": len(gold_items - predicted_items),
        "ignored": 0,
    }


def _critical_macro(fields: dict[str, FieldCounts]) -> CriticalMacro:
    values = [
        value
        for field in CRITICAL_FIELDS
        for value in (fields[field].precision, fields[field].recall)
        if value is not None
    ]
    return CriticalMacro(
        value=sum(values) / len(values) if values else None,
        contributing=len(values),
    )


def score_records(
    pairs: list[tuple[str, list[str], dict, dict]],
    mode: Mode,
) -> ScoreReport:
    """Score (record_id, tags, predicted, gold_labels_extraction) pairs."""
    if mode not in ("exact", "fuzzy"):
        raise ValueError(f"unknown scoring mode: {mode}")

    overall = {field: _Counts() for field in SCORED_FIELDS}
    per_tag: dict[str, dict[str, _Counts]] = {}
    failed: dict[str, list[FailedCase]] = {field: [] for field in CRITICAL_FIELDS}

    for record_id, tags, predicted, gold in pairs:
        for field in SCORED_FIELDS:
            predicted_value = predicted.get(field)
            gold_value = gold.get(field)
            if field in LIST_FIELDS:
                deltas = compare_list_field(predicted_value, gold_value)
                record_failed = deltas["fp_precision"] > 0 or deltas["fn_recall"] > 0
            else:
                outcome = compare_field(field, predicted_value, gold_value, mode)
                deltas = _OUTCOME_DELTAS[outcome]
                record_failed = outcome in ("fp_precision", "fn_recall", "miss_both")
            overall[field].add(**deltas)
            for tag in tags:
                per_tag.setdefault(tag, {name: _Counts() for name in SCORED_FIELDS})[field].add(**deltas)
            if field in CRITICAL_FIELDS and record_failed:
                failed[field].append(
                    FailedCase(
                        record_id=record_id,
                        field=field,
                        predicted=predicted_value,
                        gold=gold_value,
                        cause="extraction",
                    )
                )

    fields = {field: counts.to_field_counts() for field, counts in overall.items()}
    return ScoreReport(
        mode=mode,
        record_count=len(pairs),
        fields=fields,
        critical_macro=_critical_macro(fields),
        per_tag={
            tag: {field: counts.to_field_counts() for field, counts in tag_counts.items()}
            for tag, tag_counts in sorted(per_tag.items())
        },
        failed_cases=failed,
    )

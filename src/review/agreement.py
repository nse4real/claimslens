from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.evals.scorer import LIST_FIELDS, SCORED_FIELDS, compare_field, compare_list_field


@dataclass
class AgreementResult:
    record_id: str
    status: str
    disagreeing_fields: list[str]
    disagreements: dict[str, dict[str, Any]]

    @property
    def agreed(self) -> bool:
        return self.status == "AGREED"


def values_agree(field: str, reviewer_value: Any, gold_value: Any) -> bool:
    if field in LIST_FIELDS:
        comparison = compare_list_field(reviewer_value, gold_value)
        return comparison["fp_precision"] == 0 and comparison["fn_recall"] == 0
    return compare_field(field, reviewer_value, gold_value, "exact") in {"tp", "ignored"}


def check_agreement(
    record_id: str,
    gold_extraction: dict[str, Any],
    decisions: dict[tuple[str, str], Any],
) -> AgreementResult:
    disagreeing_fields = []
    disagreements = {}
    for field in SCORED_FIELDS:
        reviewer_value = decisions[(record_id, field)]
        gold_value = gold_extraction.get(field)
        if not values_agree(field, reviewer_value, gold_value):
            disagreeing_fields.append(field)
            disagreements[field] = {
                "reviewer_value": reviewer_value,
                "gold_value": gold_value,
            }
    return AgreementResult(
        record_id=record_id,
        status="AGREED" if not disagreeing_fields else "DISPUTED",
        disagreeing_fields=disagreeing_fields,
        disagreements=disagreements,
    )

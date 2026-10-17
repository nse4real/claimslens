"""Acceptance tests for validated LLM extraction (plan items 10 to 19)."""

import hashlib
import inspect
import json
from datetime import date
from pathlib import Path

from src.evals.scorer import SCORED_FIELDS
from src.extraction.baseline.rules_extractor import EXTRACTION_FIELDS
from src.extraction.llm.extractor import (
    _repair_unknown_evidence,
    build_prompt,
    extract_with_llm,
)
from src.ingestion.models import IngestedDocument, MediaType, Page
from src.llm.gateway import Usage

ROOT = Path(__file__).resolve().parents[2]
COMPLETE_FIXTURE = ROOT / "tests" / "fixtures" / "loss_notification" / "complete.json"


class FakeGateway:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self._usage = Usage()

    @property
    def usage(self):
        return Usage(
            self._usage.input_tokens,
            self._usage.output_tokens,
            self._usage.calls,
        )

    def complete(self, system, user, model, max_tokens):
        self.calls.append(
            {"system": system, "user": user, "model": model, "max_tokens": max_tokens}
        )
        if len(self.calls) > len(self.replies):
            raise AssertionError("extractor called the gateway more than expected")
        self._usage.calls += 1
        self._usage.input_tokens += 11
        self._usage.output_tokens += 7
        return self.replies[len(self.calls) - 1]


def make_document(document_id, text, media_type):
    return IngestedDocument(
        document_id=document_id,
        source_path="synthetic",
        media_type=media_type,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        pages=[Page(number=1, text=text)],
    )


def make_documents():
    return [
        make_document("doc-email", "Synthetic email body.", MediaType.EMAIL),
        make_document("doc-attachment", "Synthetic attachment.", MediaType.PDF),
    ]


def valid_wrapper():
    return json.loads(COMPLETE_FIXTURE.read_text(encoding="utf-8"))


def valid_reply():
    return json.dumps(valid_wrapper())


def test_10_build_prompt_delimits_every_document_and_keeps_system_clean():
    documents = [
        make_document("email", "EMAIL_ONLY_SECRET", MediaType.EMAIL),
        make_document("attachment", "PDF_ONLY_SECRET", MediaType.PDF),
    ]

    system, user = build_prompt(documents)

    assert '<document id="email">\nEMAIL_ONLY_SECRET\n</document>' in user
    assert '<document id="attachment">\nPDF_ONLY_SECRET\n</document>' in user
    assert user.count("<document id=") == 2
    assert "EMAIL_ONLY_SECRET" not in system
    assert "PDF_ONLY_SECRET" not in system


def test_11_valid_reply_is_ok_with_one_call_and_16_plain_keys():
    gateway = FakeGateway([valid_reply()])

    result = extract_with_llm(make_documents(), gateway)

    assert result.status == "ok"
    assert result.calls == 1
    assert result.usage.calls == 1
    assert set(result.plain) == set(EXTRACTION_FIELDS) | {"uncertain_fields"}
    assert len(EXTRACTION_FIELDS) == 16


def test_12_markdown_fence_is_retried_once_then_repaired():
    gateway = FakeGateway([f"```json\n{valid_reply()}\n```", valid_reply()])

    result = extract_with_llm(make_documents(), gateway)

    assert result.status == "repaired"
    assert result.calls == 2
    assert len(gateway.calls) == 2
    assert len(result.validation_errors) == 1
    assert "<validation_error>" in gateway.calls[1]["user"]
    assert "JSON parsing failed" in gateway.calls[1]["user"]


def test_13_two_invalid_replies_fail_with_all_null_fields_without_raising():
    gateway = FakeGateway(["not json", "still not json"])

    result = extract_with_llm(make_documents(), gateway)

    assert result.status == "failed"
    assert result.calls == 2
    assert len(result.validation_errors) == 2
    for field in EXTRACTION_FIELDS:
        assert result.plain[field] == ([] if field == "treaty_references" else None)
    assert result.plain["uncertain_fields"] == []


def test_14_unknown_evidence_document_id_repairs_only_that_field():
    wrapper = valid_wrapper()
    wrapper["cedent_name"]["evidence"][0]["document_id"] = "missing-document"

    repaired, errors = _repair_unknown_evidence(
        wrapper, {"doc-email", "doc-attachment"}
    )
    assert repaired["cedent_name"] == {
        "value": None,
        "confidence": 0,
        "evidence": [],
        "reason": "ambiguous",
    }
    assert errors

    gateway = FakeGateway([json.dumps(wrapper)])
    result = extract_with_llm(make_documents(), gateway)

    assert result.status == "repaired"
    assert result.calls == 1
    assert result.plain["cedent_name"] is None
    assert result.plain["loss_description"] == wrapper["loss_description"]["value"]
    assert "missing-document" in result.validation_errors[0]


def test_15_json_number_money_amount_is_rejected_and_retried():
    invalid = valid_wrapper()
    invalid["estimated_loss_amount"]["value"]["amount"] = 125000.0
    gateway = FakeGateway([json.dumps(invalid), valid_reply()])

    result = extract_with_llm(make_documents(), gateway)

    assert result.status == "repaired"
    assert result.calls == 2
    assert "money amount must be a string" in result.validation_errors[0]
    assert result.plain["estimated_loss_amount"]["amount"] == "125000.00"


def test_16_single_not_found_treaty_item_unwraps_to_empty_list():
    wrapper = valid_wrapper()
    wrapper["treaty_references"] = [
        {"value": None, "confidence": 0, "evidence": [], "reason": "not_found"}
    ]
    gateway = FakeGateway([json.dumps(wrapper)])

    result = extract_with_llm(make_documents(), gateway)

    assert result.status == "ok"
    assert result.plain["treaty_references"] == []


def test_17_unwrapped_keys_match_scorer_and_dates_are_plain_iso_strings():
    result = extract_with_llm(make_documents(), FakeGateway([valid_reply()]))

    assert set(result.plain) == set(SCORED_FIELDS) | {"uncertain_fields"}
    assert result.plain["uncertain_fields"] == []
    for field in ("date_of_loss", "date_of_notification"):
        assert isinstance(result.plain[field], str)
        assert date.fromisoformat(result.plain[field]).isoformat() == result.plain[field]


def test_18_extractor_never_calls_gateway_more_than_twice():
    gateway = FakeGateway(["{", "[]"])

    result = extract_with_llm(make_documents(), gateway)

    assert result.status == "failed"
    assert result.calls == 2
    assert len(gateway.calls) == 2


def test_19_extractor_signature_has_no_gold_argument_and_uses_documents_only():
    parameters = inspect.signature(extract_with_llm).parameters

    assert list(parameters) == ["documents", "gateway"]
    result = extract_with_llm(make_documents(), FakeGateway([valid_reply()]))
    assert result.status == "ok"

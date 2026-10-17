"""Acceptance tests for the B10 rules extractor (plan items 1 to 9)."""

import hashlib
import json
from pathlib import Path

from src.extraction.baseline.rules_extractor import EXTRACTION_FIELDS, extract
from src.ingestion.models import IngestedDocument, MediaType, Page
from src.ingestion.pipeline import ingest_folder

ROOT = Path(__file__).resolve().parents[2]
GN1001_FOLDER = ROOT / "data" / "corpus" / "notifications" / "GN-1001"
GN1001_GOLD_PATH = ROOT / "evals" / "gold" / "records" / "GN-1001.json"

STRING_FIELDS = (
    "cedent_name",
    "cedent_claim_reference",
    "original_insured_name",
    "territory_or_country",
    "peril_or_cause",
    "loss_location",
    "sender_name",
    "sender_role",
    "cedent_notes",
    "loss_description",
)
MONEY_FIELDS = ("estimated_loss_amount", "paid_to_date", "outstanding_reserve")
DATE_FIELDS = ("date_of_loss", "date_of_notification")


def make_document(document_id: str, text: str, headers: dict | None = None) -> IngestedDocument:
    return IngestedDocument(
        document_id=document_id,
        source_path="synthetic",
        media_type=MediaType.EMAIL,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        headers=headers or {},
        pages=[Page(number=1, text=text)],
    )


def gn1001_documents() -> list[IngestedDocument]:
    return ingest_folder(GN1001_FOLDER)


def gn1001_gold_extraction() -> dict:
    gold = json.loads(GN1001_GOLD_PATH.read_text(encoding="utf-8"))
    return gold["labels"]["extraction"]


def test_extract_returns_all_16_keys_with_expected_types():
    result = extract(gn1001_documents())
    assert set(result) == set(EXTRACTION_FIELDS) | {"uncertain_fields"}
    assert len(EXTRACTION_FIELDS) == 16
    for field in STRING_FIELDS:
        assert result[field] is None or isinstance(result[field], str), field
    for field in MONEY_FIELDS:
        value = result[field]
        assert value is None or set(value) == {"amount", "currency"}, field
    for field in DATE_FIELDS:
        value = result[field]
        assert value is None or (isinstance(value, str) and len(value) == 10), field
    assert isinstance(result["treaty_references"], list)
    assert all(isinstance(item, str) for item in result["treaty_references"])
    assert isinstance(result["uncertain_fields"], list)


def test_gn1001_critical_values_match_gold():
    result = extract(gn1001_documents())
    gold = gn1001_gold_extraction()
    for field in (
        "cedent_name",
        "loss_description",
        "treaty_references",
        "estimated_loss_amount",
        "date_of_loss",
    ):
        assert result[field] == gold[field], field


def test_missing_cedent_line_yields_none():
    result = extract([make_document("email", "Dear Claims Team\n\nNo labels here.")])
    assert result["cedent_name"] is None


def test_treaty_references_split_and_absent_line():
    body = "Treaty reference: FICT-TRT-001, FICT-TRT-002; FICT-TRT-003"
    result = extract([make_document("email", body)])
    assert result["treaty_references"] == ["FICT-TRT-001", "FICT-TRT-002", "FICT-TRT-003"]
    result = extract([make_document("email", "No treaty line here.")])
    assert result["treaty_references"] == []


def test_money_parsing():
    result = extract([make_document("email", "Estimated loss: EUR 2450700.27")])
    assert result["estimated_loss_amount"] == {"amount": "2450700.27", "currency": "EUR"}
    result = extract([make_document("email", "Estimated loss: 2450700.27 EUR")])
    assert result["estimated_loss_amount"] is None


def test_date_formats():
    result = extract([make_document("email", "Loss date: 2024-05-23")])
    assert result["date_of_loss"] == "2024-05-23"
    result = extract([make_document("email", "Loss date: 23/05/2024")])
    assert result["date_of_loss"] is None


def test_notification_date_falls_back_to_date_header():
    document = make_document(
        "email",
        "Dear Claims Team\n\nNo notification date line.",
        headers={"date": "Thu, 23 May 2024 09:00:00 +0000"},
    )
    result = extract([document])
    assert result["date_of_notification"] == "2024-05-23"


def test_uncertain_fields_always_empty():
    result = extract(gn1001_documents())
    assert result["uncertain_fields"] == []
    result = extract([make_document("email", "")])
    assert result["uncertain_fields"] == []


def test_extract_does_not_raise_on_empty_email_body():
    result = extract([make_document("email", "")])
    assert set(result) == set(EXTRACTION_FIELDS) | {"uncertain_fields"}
    assert result["cedent_name"] is None
    assert result["treaty_references"] == []

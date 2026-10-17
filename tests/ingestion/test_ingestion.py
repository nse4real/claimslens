import hashlib
import json
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.ingestion.models import (
    CorruptPdfError,
    EncryptedPdfError,
    IngestedDocument,
    MalformedEmailError,
    MediaType,
    Page,
    TextDecodeError,
    UnsupportedMediaType,
    WarningCode,
)
from src.ingestion.pipeline import ingest_file, ingest_folder
from tests.ingestion.pdf_writer import write_pdf

ROOT = Path(__file__).resolve().parents[2]
NOTIFICATION_ROOT = ROOT / "data" / "corpus" / "notifications"
GOLD_ROOT = ROOT / "evals" / "gold" / "records"
GN_1001 = NOTIFICATION_ROOT / "GN-1001"


def valid_document_data():
    return {
        "document_id": "document",
        "source_path": "document.txt",
        "media_type": "text/plain",
        "sha256": "a" * 64,
        "headers": {},
        "pages": [{"number": 1, "text": "Body"}],
        "warnings": [],
    }


def basic_email():
    message = EmailMessage()
    message["From"] = "Sender <sender@example.test>"
    message["To"] = "Claims <claims@example.test>"
    message["Date"] = "Thu, 23 May 2024 09:00:00 +0000"
    message.set_content("Cedent: Example Cedent")
    return message


@pytest.fixture(scope="session")
def ingested_corpus():
    folders = sorted(path for path in NOTIFICATION_ROOT.iterdir() if path.is_dir())
    return {folder.name: ingest_folder(folder) for folder in folders}


@pytest.fixture(scope="session")
def gold_corpus():
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(GOLD_ROOT.glob("GN-*.json"))
    }


def test_01_ingest_file_parses_gn_1001_email_headers_and_body():
    documents = ingest_file(GN_1001 / "email.eml", "email")

    assert len(documents) == 1
    document = documents[0]
    assert document.media_type == MediaType.EMAIL
    assert set(document.headers) == {"from", "to", "date", "subject", "message-id"}
    assert "Cedent:" in document.text


def test_02_email_sha256_hashes_the_raw_source_bytes():
    path = GN_1001 / "email.eml"

    document = ingest_file(path, "email")[0]

    assert document.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_03_ingest_folder_returns_email_then_loss_advice():
    documents = ingest_folder(GN_1001)

    assert [document.document_id for document in documents] == [
        "email",
        "att-loss_advice",
    ]


def test_04_loss_advice_is_text_and_contains_estimated_loss():
    attachment = ingest_folder(GN_1001)[1]

    assert attachment.media_type == MediaType.TEXT
    assert "Estimated loss" in attachment.text


def test_05_one_page_pdf_extracts_its_text_exactly(tmp_path):
    path = tmp_path / "one.pdf"
    write_pdf(path, ["Hello from a PDF."])

    document = ingest_file(path, "pdf")[0]

    assert document.pages[0].text.strip() == "Hello from a PDF."


def test_06_three_page_pdf_preserves_page_numbers_and_order(tmp_path):
    path = tmp_path / "three.pdf"
    write_pdf(path, ["First", "Second", "Third"])

    document = ingest_file(path, "pdf")[0]

    assert [page.number for page in document.pages] == [1, 2, 3]
    assert [page.text.strip() for page in document.pages] == [
        "First",
        "Second",
        "Third",
    ]


def test_07_pdf_page_without_text_warns_for_that_page_only(tmp_path):
    path = tmp_path / "blank.pdf"
    write_pdf(path, ["First", "", "Third"])

    document = ingest_file(path, "pdf")[0]

    assert len(document.warnings) == 1
    warning = document.warnings[0]
    assert warning.code == WarningCode.NO_TEXT_LAYER
    assert "Page 2" in warning.message


def test_08_encrypted_pdf_raises_encrypted_pdf_error(tmp_path):
    path = tmp_path / "encrypted.pdf"
    write_pdf(path, ["Secret"], encrypt_password="x")

    with pytest.raises(EncryptedPdfError):
        ingest_file(path, "pdf")


def test_09_random_bytes_named_pdf_raise_corrupt_pdf_error(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"not a PDF\x00\x01\x02")

    with pytest.raises(CorruptPdfError):
        ingest_file(path, "pdf")


def test_10_email_without_text_plain_part_raises_malformed_email_error(tmp_path):
    path = tmp_path / "html.eml"
    message = basic_email()
    message.set_content("<p>HTML only</p>", subtype="html")
    path.write_bytes(message.as_bytes())

    with pytest.raises(MalformedEmailError):
        ingest_file(path, "email")


def test_11_email_missing_from_warns_and_still_ingests(tmp_path):
    path = tmp_path / "missing-from.eml"
    message = basic_email()
    del message["From"]
    path.write_bytes(message.as_bytes())

    documents = ingest_file(path, "email")

    assert len(documents) == 1
    assert "from" not in documents[0].headers
    assert any(
        warning.code == WarningCode.HEADER_MISSING and "From" in warning.message
        for warning in documents[0].warnings
    )


def test_12_docx_file_raises_unsupported_media_type(tmp_path):
    path = tmp_path / "document.docx"
    path.write_bytes(b"document")

    with pytest.raises(UnsupportedMediaType):
        ingest_file(path, "document")


def test_13_text_file_with_invalid_utf8_raises_text_decode_error(tmp_path):
    path = tmp_path / "invalid.txt"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(TextDecodeError):
        ingest_file(path, "text")


def test_14_unsupported_email_attachment_is_skipped_with_warning(tmp_path):
    path = tmp_path / "attachment.eml"
    message = basic_email()
    message.add_attachment(
        b"not a real Word document",
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="notes.docx",
    )
    path.write_bytes(message.as_bytes())

    documents = ingest_file(path, "email")

    assert len(documents) == 1
    assert any(
        warning.code == WarningCode.ATTACHMENT_SKIPPED
        for warning in documents[0].warnings
    )


def test_15_folder_without_email_raises_malformed_email_error(tmp_path):
    with pytest.raises(MalformedEmailError):
        ingest_folder(tmp_path)


def test_16_ingested_document_rejects_unknown_key_and_invalid_sha256():
    unknown_key = valid_document_data()
    unknown_key["unexpected"] = True
    with pytest.raises(ValidationError):
        IngestedDocument.model_validate(unknown_key)

    invalid_hash = valid_document_data()
    invalid_hash["sha256"] = "A" * 64
    with pytest.raises(ValidationError):
        IngestedDocument.model_validate(invalid_hash)


def test_17_ingested_document_rejects_empty_pages_list():
    data = valid_document_data()
    data["pages"] = []

    with pytest.raises(ValidationError):
        IngestedDocument.model_validate(data)


def test_18_page_rejects_number_zero():
    with pytest.raises(ValidationError):
        Page(number=0, text="Body")


def test_19_all_225_b8_folders_ingest_into_email_and_nonempty_text_attachment(
    ingested_corpus,
):
    assert len(ingested_corpus) == 225
    for record_id, documents in ingested_corpus.items():
        assert len(documents) == 2, record_id
        assert documents[0].media_type == MediaType.EMAIL, record_id
        assert documents[1].media_type == MediaType.TEXT, record_id
        assert documents[1].text.strip(), record_id


def test_20_email_dates_match_gold_and_removed_dates_are_absent(
    ingested_corpus, gold_corpus
):
    for record_id, documents in ingested_corpus.items():
        expected = gold_corpus[record_id]["labels"]["extraction"][
            "date_of_notification"
        ]
        headers = documents[0].headers
        if expected is None:
            assert "date" not in headers, record_id
        else:
            actual = parsedate_to_datetime(headers["date"]).date().isoformat()
            assert actual == expected, record_id


def test_21_gold_cedent_treaties_and_loss_amounts_appear_in_ingested_text(
    ingested_corpus, gold_corpus
):
    for record_id, documents in ingested_corpus.items():
        extraction = gold_corpus[record_id]["labels"]["extraction"]
        email_text = documents[0].text
        combined_text = "\n\n".join(document.text for document in documents)

        cedent_name = extraction["cedent_name"]
        if cedent_name is not None:
            assert cedent_name in email_text, record_id
        for treaty_reference in extraction["treaty_references"]:
            assert treaty_reference in combined_text, record_id
        estimated_loss = extraction["estimated_loss_amount"]
        if estimated_loss is not None:
            assert estimated_loss["amount"] in combined_text, record_id


def test_22_ingesting_the_same_folder_twice_gives_equal_models():
    first = ingest_folder(GN_1001)
    second = ingest_folder(GN_1001)

    assert first == second


def test_23_text_property_joins_pages_with_a_blank_line_in_order():
    data = valid_document_data()
    data["pages"] = [
        {"number": 1, "text": "First"},
        {"number": 2, "text": "Second"},
        {"number": 3, "text": "Third"},
    ]

    document = IngestedDocument.model_validate(data)

    assert document.text == "First\n\nSecond\n\nThird"

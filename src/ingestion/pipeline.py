from __future__ import annotations

from pathlib import Path

from src.ingestion.adapters.email_adapter import parse_eml_bytes
from src.ingestion.adapters.pdf_adapter import parse_pdf_bytes
from src.ingestion.adapters.text_adapter import parse_text_bytes
from src.ingestion.models import (
    Attachment,
    IngestedDocument,
    IngestWarning,
    MalformedEmailError,
    UnsupportedMediaType,
    WarningCode,
)

SUPPORTED_SUFFIXES = {".eml", ".pdf", ".txt"}


def ingest_file(path: Path, document_id: str) -> list[IngestedDocument]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise UnsupportedMediaType(f"Unsupported media type: {path}")
    return _ingest_bytes(path.read_bytes(), suffix, str(path), document_id)


def ingest_folder(folder: Path) -> list[IngestedDocument]:
    folder = Path(folder)
    email_path = folder / "email.eml"
    if not email_path.is_file():
        raise MalformedEmailError(f"{folder} has no email.eml")

    documents = ingest_file(email_path, "email")
    attachment_folder = folder / "attachments"
    if not attachment_folder.is_dir():
        return documents

    attachment_paths = sorted(
        (path for path in attachment_folder.iterdir() if path.is_file()),
        key=lambda path: path.name,
    )
    for path in attachment_paths:
        documents.extend(ingest_file(path, f"att-{path.stem}"))
    return documents


def _ingest_bytes(
    raw: bytes, suffix: str, source_path: str, document_id: str
) -> list[IngestedDocument]:
    if suffix == ".pdf":
        return [parse_pdf_bytes(raw, source_path, document_id)]
    if suffix == ".txt":
        return [parse_text_bytes(raw, source_path, document_id)]
    if suffix != ".eml":
        raise UnsupportedMediaType(f"Unsupported media type: {source_path}")

    body, attachments = parse_eml_bytes(raw, source_path, document_id)
    documents = [body]
    for index, attachment in enumerate(attachments, start=1):
        attachment_suffix = Path(attachment.filename).suffix.lower()
        if attachment_suffix not in SUPPORTED_SUFFIXES:
            body.warnings.append(_attachment_skipped_warning(attachment))
            continue
        documents.extend(
            _ingest_bytes(
                attachment.payload_bytes,
                attachment_suffix,
                attachment.filename,
                f"{document_id}-att{index}",
            )
        )
    return documents


def _attachment_skipped_warning(attachment: Attachment) -> IngestWarning:
    return IngestWarning(
        code=WarningCode.ATTACHMENT_SKIPPED,
        message=f"Attachment {attachment.filename!r} has an unsupported type and was skipped.",
    )

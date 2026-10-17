from __future__ import annotations

import hashlib
from email import message_from_bytes, policy
from pathlib import Path

from src.ingestion.models import (
    Attachment,
    IngestedDocument,
    IngestWarning,
    MalformedEmailError,
    MediaType,
    Page,
    WarningCode,
)

HEADER_NAMES = ("From", "To", "Date", "Subject", "Message-ID")
REQUIRED_HEADERS = ("From", "Date")


def parse_eml(
    path: Path, document_id: str
) -> tuple[IngestedDocument, list[Attachment]]:
    return parse_eml_bytes(path.read_bytes(), str(path), document_id)


def parse_eml_bytes(
    raw: bytes, source_path: str, document_id: str
) -> tuple[IngestedDocument, list[Attachment]]:
    try:
        message = message_from_bytes(raw, policy=policy.default)
        body_part = next(
            (
                part
                for part in message.walk()
                if part.get_content_type() == "text/plain"
            ),
            None,
        )
        if body_part is None:
            raise MalformedEmailError(f"{source_path} has no text/plain body")
        body = body_part.get_content()
        if not isinstance(body, str):
            raise MalformedEmailError(f"{source_path} has no readable text body")

        attachments = []
        for part in message.walk():
            if part is body_part or part.is_multipart():
                continue
            filename = part.get_filename()
            if filename is None:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                raise MalformedEmailError(
                    f"Attachment {filename!r} in {source_path} could not be decoded"
                )
            attachments.append(
                Attachment(
                    filename=filename,
                    content_type=part.get_content_type(),
                    payload_bytes=payload,
                )
            )
    except MalformedEmailError:
        raise
    except Exception as exc:
        raise MalformedEmailError(f"Could not parse {source_path}: {exc}") from exc

    headers = {
        name.lower(): str(message[name])
        for name in HEADER_NAMES
        if message[name] is not None
    }
    warnings = [
        IngestWarning(
            code=WarningCode.HEADER_MISSING,
            message=f"Required email header {name} is missing.",
        )
        for name in REQUIRED_HEADERS
        if message[name] is None
    ]
    document = IngestedDocument(
        document_id=document_id,
        source_path=source_path,
        media_type=MediaType.EMAIL,
        sha256=hashlib.sha256(raw).hexdigest(),
        headers=headers,
        pages=[Page(number=1, text=body)],
        warnings=warnings,
    )
    return document, attachments

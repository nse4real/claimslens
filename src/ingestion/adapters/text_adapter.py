from __future__ import annotations

import hashlib
from pathlib import Path

from src.ingestion.models import (
    IngestedDocument,
    IngestWarning,
    MediaType,
    Page,
    TextDecodeError,
    WarningCode,
)


def parse_text(path: Path, document_id: str) -> IngestedDocument:
    return parse_text_bytes(path.read_bytes(), str(path), document_id)


def parse_text_bytes(raw: bytes, source_path: str, document_id: str) -> IngestedDocument:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TextDecodeError(f"{source_path} is not valid UTF-8") from exc

    warnings = []
    if text == "":
        warnings.append(
            IngestWarning(
                code=WarningCode.EMPTY_BODY,
                message="The text document has an empty body.",
            )
        )
    return IngestedDocument(
        document_id=document_id,
        source_path=source_path,
        media_type=MediaType.TEXT,
        sha256=hashlib.sha256(raw).hexdigest(),
        headers={},
        pages=[Page(number=1, text=text)],
        warnings=warnings,
    )

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from src.ingestion.models import (
    CorruptPdfError,
    EncryptedPdfError,
    IngestedDocument,
    IngestWarning,
    MediaType,
    Page,
    WarningCode,
)


def parse_pdf(path: Path, document_id: str) -> IngestedDocument:
    return parse_pdf_bytes(path.read_bytes(), str(path), document_id)


def parse_pdf_bytes(raw: bytes, source_path: str, document_id: str) -> IngestedDocument:
    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise EncryptedPdfError(f"{source_path} is encrypted")
        extracted = [
            (number, page.extract_text() or "")
            for number, page in enumerate(reader.pages, start=1)
        ]
    except EncryptedPdfError:
        raise
    except Exception as exc:
        raise CorruptPdfError(f"Could not read PDF {source_path}: {exc}") from exc

    pages = [Page(number=number, text=text) for number, text in extracted]
    warnings = [
        IngestWarning(
            code=WarningCode.NO_TEXT_LAYER,
            message=f"Page {number} has no text layer.",
        )
        for number, text in extracted
        if not text.strip()
    ]
    return IngestedDocument(
        document_id=document_id,
        source_path=source_path,
        media_type=MediaType.PDF,
        sha256=hashlib.sha256(raw).hexdigest(),
        headers={},
        pages=pages,
        warnings=warnings,
    )

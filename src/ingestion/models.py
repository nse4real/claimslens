from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlankStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class MediaType(str, Enum):
    EMAIL = "message/rfc822"
    PDF = "application/pdf"
    TEXT = "text/plain"


class WarningCode(str, Enum):
    NO_TEXT_LAYER = "no_text_layer"
    EMPTY_BODY = "empty_body"
    HEADER_MISSING = "header_missing"
    ATTACHMENT_SKIPPED = "attachment_skipped"


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    text: str


class IngestWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: WarningCode
    message: NonBlankStr


class Attachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    content_type: str
    payload_bytes: bytes


class IngestedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: NonBlankStr
    source_path: str
    media_type: MediaType
    sha256: Sha256
    headers: dict[str, str] = Field(default_factory=dict)
    pages: list[Page] = Field(min_length=1)
    warnings: list[IngestWarning] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)


class IngestError(Exception):
    pass


class UnsupportedMediaType(IngestError):
    pass


class EncryptedPdfError(IngestError):
    pass


class MalformedEmailError(IngestError):
    pass


class CorruptPdfError(IngestError):
    pass


class TextDecodeError(IngestError):
    pass

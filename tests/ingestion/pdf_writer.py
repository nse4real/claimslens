"""Minimal stdlib-only PDF writer with optional 40-bit RC4 encryption."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

_PASSWORD_PADDING = bytes.fromhex(
    "28 BF 4E 5E 4E 75 8A 41 64 00 4E 56 FF FA 01 08 "
    "2E 2E 00 B6 D0 68 3E 80 2F 0C A9 FE 64 53 69 7A"
)


class _StandardEncryption:
    def __init__(self, password: str, file_id: bytes) -> None:
        user_password = _pad_password(password)
        owner_key = hashlib.md5(user_password).digest()[:5]
        self.owner_entry = _rc4(owner_key, user_password)
        permissions = struct.pack("<i", -1)
        self.key = hashlib.md5(
            user_password + self.owner_entry + permissions + file_id
        ).digest()[:5]
        self.user_entry = _rc4(self.key, _PASSWORD_PADDING)

    def dictionary(self) -> bytes:
        return (
            b"<< /Filter /Standard /V 1 /R 2 /P -1 /O <"
            + self.owner_entry.hex().encode("ascii")
            + b"> /U <"
            + self.user_entry.hex().encode("ascii")
            + b"> >>"
        )

    def encrypt(self, object_number: int, data: bytes) -> bytes:
        object_key = hashlib.md5(
            self.key
            + object_number.to_bytes(3, "little")
            + (0).to_bytes(2, "little")
        ).digest()[:10]
        return _rc4(object_key, data)


def _pad_password(password: str) -> bytes:
    encoded = password.encode("latin-1")[:32]
    return (encoded + _PASSWORD_PADDING)[:32]


def _rc4(key: bytes, data: bytes) -> bytes:
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]

    output = bytearray()
    i = 0
    j = 0
    for value in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        output.append(value ^ state[(state[i] + state[j]) % 256])
    return bytes(output)


def _escaped_text(text: str) -> bytes:
    encoded = text.encode("cp1252")
    return (
        encoded.replace(b"\\", b"\\\\")
        .replace(b"(", b"\\(")
        .replace(b")", b"\\)")
        .replace(b"\r", b"\\r")
        .replace(b"\n", b"\\n")
    )


def _content_stream(text: str) -> bytes:
    if not text:
        return b""
    return b"BT\n/F1 12 Tf\n72 720 Td\n(" + _escaped_text(text) + b") Tj\nET\n"


def write_pdf(
    path: Path, pages: list[str], encrypt_password: str | None = None
) -> None:
    """Write Helvetica text pages, constructing PDF objects and xref offsets directly."""
    path = Path(path)
    file_id = hashlib.md5("\0".join(pages).encode("utf-8")).digest()
    encryption = (
        _StandardEncryption(encrypt_password, file_id)
        if encrypt_password is not None
        else None
    )

    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        ),
    }
    page_numbers = []
    for index, text in enumerate(pages):
        page_number = 4 + index * 2
        content_number = page_number + 1
        page_numbers.append(page_number)
        stream = _content_stream(text)
        if encryption is not None:
            stream = encryption.encrypt(content_number, stream)
        objects[page_number] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_number} 0 R >>"
        ).encode("ascii")
        objects[content_number] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects[2] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_numbers)} >>"
    ).encode("ascii")

    encryption_number = None
    if encryption is not None:
        encryption_number = max(objects) + 1
        objects[encryption_number] = encryption.dictionary()

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(output)
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(objects[number])
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    size = max(objects) + 1
    output.extend(f"xref\n0 {size}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for number in range(1, size):
        output.extend(f"{offsets[number]:010d} 00000 n \n".encode("ascii"))

    trailer = f"trailer\n<< /Size {size} /Root 1 0 R"
    if encryption_number is not None:
        trailer += (
            f" /Encrypt {encryption_number} 0 R"
            f" /ID [<{file_id.hex()}> <{file_id.hex()}>]"
        )
    trailer += f" >>\nstartxref\n{xref_offset}\n%%EOF\n"
    output.extend(trailer.encode("ascii"))
    path.write_bytes(output)

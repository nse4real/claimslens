"""Naive regex-and-rules extraction baseline (B10).

One regex per field, first match wins, applied to the joined text of the
email body document and every attachment document. The label strings are the
ones the B8 renderer writes in data/generators/notifications.py (core_body
and render_attachment). The extractor never reads gold records.
"""

from __future__ import annotations

import re
from email.utils import parseaddr, parsedate_to_datetime

from src.ingestion.models import IngestedDocument

EXTRACTOR_VERSION = "rules-regex-1.0.0"

# The 16 B4 extraction fields, in gold-record order. uncertain_fields is
# added to the output separately and is always [].
EXTRACTION_FIELDS = (
    "cedent_name",
    "treaty_references",
    "date_of_loss",
    "date_of_notification",
    "loss_description",
    "estimated_loss_amount",
    "cedent_claim_reference",
    "original_insured_name",
    "territory_or_country",
    "peril_or_cause",
    "loss_location",
    "sender_name",
    "sender_role",
    "cedent_notes",
    "paid_to_date",
    "outstanding_reserve",
)

# Label regexes. Each comment names the B8 label the rule matches.
CEDENT_RE = re.compile(r"^Cedent:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Cedent:"
TREATY_RE = re.compile(r"^Treaty reference:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Treaty reference:"
LOSS_DATE_RE = re.compile(r"^Loss date:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Loss date:"
NOTIFICATION_DATE_RE = re.compile(r"^Notification date:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Notification date:"
LOSS_DESCRIPTION_RE = re.compile(r"^Loss description:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Loss description:"
ESTIMATED_LOSS_RE = re.compile(r"^Estimated loss:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Estimated loss:"
CLAIM_REFERENCE_RE = re.compile(r"^Claim reference:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Claim reference:"
ORIGINAL_INSURED_RE = re.compile(r"^Original insured:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Original insured:"
TERRITORY_RE = re.compile(r"^Territory or country:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Territory or country:"
PERIL_RE = re.compile(r"^Peril or cause:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Peril or cause:"
LOSS_LOCATION_RE = re.compile(r"^Loss location:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Loss location:"
CEDENT_NOTES_RE = re.compile(r"^Cedent notes:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Cedent notes:"
PAID_TO_DATE_RE = re.compile(r"^Paid to date:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Paid to date:"
OUTSTANDING_RESERVE_RE = re.compile(r"^Outstanding reserve:[ \t]*(?P<value>.*)$", re.MULTILINE)  # B8 label "Outstanding reserve:"
# B8 signature block: "Regards" then sender name then sender role on their own lines.
SIGNATURE_RE = re.compile(
    r"^Regards[ \t]*\r?\n(?P<name>[^\r\n]+)\r?\n(?P<role>[^\r\n]+)",
    re.MULTILINE,
)

# Money as "EUR 2450700.27": three-letter currency code, then the amount.
MONEY_RE = re.compile(r"(?P<currency>[A-Z]{3})\s+(?P<amount>[0-9]+(?:\.[0-9]{1,4})?)")
# Only ISO calendar dates are accepted; any other format yields None.
ISO_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

TREATY_SPLIT_RE = re.compile(r"[,;]")

_TEXT_LABEL_RULES = (
    ("cedent_name", CEDENT_RE),
    ("loss_description", LOSS_DESCRIPTION_RE),
    ("cedent_claim_reference", CLAIM_REFERENCE_RE),
    ("original_insured_name", ORIGINAL_INSURED_RE),
    ("territory_or_country", TERRITORY_RE),
    ("peril_or_cause", PERIL_RE),
    ("loss_location", LOSS_LOCATION_RE),
    ("cedent_notes", CEDENT_NOTES_RE),
)
_MONEY_LABEL_RULES = (
    ("estimated_loss_amount", ESTIMATED_LOSS_RE),
    ("paid_to_date", PAID_TO_DATE_RE),
    ("outstanding_reserve", OUTSTANDING_RESERVE_RE),
)


def _label_value(text: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group("value").strip()
    return value or None


def _money_value(text: str, pattern: re.Pattern[str]) -> dict[str, str] | None:
    value = _label_value(text, pattern)
    if value is None:
        return None
    match = MONEY_RE.search(value)
    if match is None:
        return None
    return {"amount": match.group("amount"), "currency": match.group("currency")}


def _iso_date_value(text: str, pattern: re.Pattern[str]) -> str | None:
    value = _label_value(text, pattern)
    if value is None:
        return None
    match = ISO_DATE_RE.search(value)
    if match is None:
        return None
    return match.group(0)


def _treaty_references(text: str) -> list[str]:
    value = _label_value(text, TREATY_RE)
    if value is None:
        return []
    return [item.strip() for item in TREATY_SPLIT_RE.split(value) if item.strip()]


def _header(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _sender_name(email_document: IngestedDocument | None) -> str | None:
    if email_document is None:
        return None
    from_header = _header(email_document.headers, "from")
    if not from_header:
        return None
    display_name, _address = parseaddr(from_header)
    display_name = display_name.strip()
    return display_name or None


def _sender_role(text: str) -> str | None:
    match = SIGNATURE_RE.search(text)
    if match is None:
        return None
    return match.group("role").strip() or None


def _notification_date(text: str, email_document: IngestedDocument | None) -> str | None:
    value = _iso_date_value(text, NOTIFICATION_DATE_RE)
    if value is not None:
        return value
    if email_document is None:
        return None
    date_header = _header(email_document.headers, "date")
    if not date_header:
        return None
    try:
        parsed = parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed.date().isoformat()


def extract(documents: list[IngestedDocument]) -> dict:
    """Extract the 16 B4 fields from one notification's ingested documents."""
    if not documents:
        raise ValueError("documents must not be empty")

    email_document = next(
        (document for document in documents if document.document_id == "email"),
        None,
    )
    texts = [
        document.text
        for document in documents
        if document.document_id == "email" or document.document_id.startswith("att-")
    ]
    text = "\n".join(texts)

    result: dict = {}
    for field, pattern in _TEXT_LABEL_RULES:
        result[field] = _label_value(text, pattern)
    result["treaty_references"] = _treaty_references(text)
    result["date_of_loss"] = _iso_date_value(text, LOSS_DATE_RE)
    result["date_of_notification"] = _notification_date(text, email_document)
    for field, pattern in _MONEY_LABEL_RULES:
        result[field] = _money_value(text, pattern)
    result["sender_name"] = _sender_name(email_document)
    result["sender_role"] = _sender_role(text)

    return {field: result[field] for field in EXTRACTION_FIELDS} | {"uncertain_fields": []}

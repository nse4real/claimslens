"""Prompt construction, validation, and unwrapping for LLM extraction."""

from __future__ import annotations

import html
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from jsonschema import Draft202012Validator, FormatChecker

from src.extraction.baseline.rules_extractor import EXTRACTION_FIELDS
from src.ingestion.models import IngestedDocument, MediaType
from src.llm.gateway import MODEL_ID, Gateway, Usage

ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = ROOT / "prompts" / "extraction" / "loss_notification_v1.md"
SCHEMA_PATH = ROOT / "src" / "extraction" / "schemas" / "loss_notification.schema.json"
MAX_TOKENS = 8192
MONEY_FIELDS = ("estimated_loss_amount", "paid_to_date", "outstanding_reserve")

SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


@dataclass
class ExtractionResult:
    plain: dict
    status: Literal["ok", "repaired", "failed"]
    calls: int
    validation_errors: list[str]
    usage: Usage


class _ModelOutputError(ValueError):
    pass


def _section(prompt: str, title: str, next_title: str) -> str:
    body = prompt.split(f"## {title}\n", 1)[1]
    return body.split(f"\n## {next_title}\n", 1)[0].strip()


def _document_type(document: IngestedDocument) -> str:
    media_type = getattr(document, "media_type", None)
    if media_type == MediaType.EMAIL:
        return "email"
    if media_type == MediaType.PDF:
        return "pdf"
    if media_type is None and document.document_id == "email":
        return "email"
    return "other"


def _input_metadata(documents: list[IngestedDocument]) -> dict:
    source_documents = [
        {
            "document_id": document.document_id,
            "document_type": _document_type(document),
        }
        for document in documents
    ]
    return {
        "source_documents": source_documents,
        "intake_metadata": {
            "channel": "email"
            if any(item["document_type"] == "email" for item in source_documents)
            else "other",
            "attachment_count": sum(
                item["document_type"] != "email" for item in source_documents
            ),
        },
    }


def build_prompt(documents: list[IngestedDocument]) -> tuple[str, str]:
    if not documents:
        raise ValueError("documents must not be empty")

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    system = _section(prompt, "System prompt", "Few-shot examples")
    output_schema = _section(prompt, "Output schema", "System prompt")
    metadata = json.dumps(
        _input_metadata(documents), indent=2, ensure_ascii=False
    )
    blocks = "\n".join(
        f'<document id="{html.escape(document.document_id, quote=True)}">\n'
        f"{document.text}\n"
        "</document>"
        for document in documents
    )
    user = (
        f"<context>\n{output_schema}\n\n"
        f"Copy this runtime metadata exactly:\n{metadata}\n</context>\n"
        f"<data>\n{blocks}\n</data>"
    )
    return system, user


def _error_path(error) -> str:
    path = "$"
    for part in error.absolute_path:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _money_errors(wrapper) -> list[str]:
    if not isinstance(wrapper, dict):
        return []
    errors = []
    for field in MONEY_FIELDS:
        field_wrapper = wrapper.get(field)
        if not isinstance(field_wrapper, dict):
            continue
        value = field_wrapper.get("value")
        if (
            isinstance(value, dict)
            and "amount" in value
            and not isinstance(value["amount"], str)
        ):
            errors.append(f"$.{field}.value.amount: money amount must be a string")
    return errors


def _parse_and_validate(reply: str) -> dict:
    try:
        wrapper = json.loads(reply)
    except (json.JSONDecodeError, TypeError, RecursionError) as exc:
        raise _ModelOutputError(f"JSON parsing failed: {exc}") from exc

    errors = sorted(VALIDATOR.iter_errors(wrapper), key=_error_path)
    messages = [f"{_error_path(error)}: {error.message}" for error in errors]
    messages.extend(_money_errors(wrapper))
    if messages:
        raise _ModelOutputError("\n".join(messages))
    return wrapper


def _repair_unknown_evidence(wrapper: dict, document_ids: set[str]) -> tuple[dict, list[str]]:
    repaired = deepcopy(wrapper)
    errors = []
    for field in EXTRACTION_FIELDS:
        wrappers = (
            list(enumerate(repaired[field]))
            if field == "treaty_references"
            else [(None, repaired[field])]
        )
        for index, field_wrapper in wrappers:
            unknown_ids = sorted(
                {
                    evidence["document_id"]
                    for evidence in field_wrapper["evidence"]
                    if evidence["document_id"] not in document_ids
                }
            )
            if not unknown_ids:
                continue
            location = field if index is None else f"{field}[{index}]"
            errors.append(
                f"{location}: evidence references unknown document_id(s): "
                + ", ".join(unknown_ids)
            )
            field_wrapper.clear()
            field_wrapper.update(
                {"value": None, "confidence": 0, "evidence": [], "reason": "ambiguous"}
            )
    return repaired, errors


def _unwrap(wrapper: dict) -> dict:
    plain = {}
    for field in EXTRACTION_FIELDS:
        if field == "treaty_references":
            plain[field] = [
                item["value"]
                for item in wrapper[field]
                if item["value"] is not None
            ]
            continue
        value = wrapper[field]["value"]
        if field in MONEY_FIELDS and value is not None:
            value = {"amount": value["amount"], "currency": value["currency"]}
        plain[field] = value
    plain["uncertain_fields"] = []
    return plain


def _failed_plain() -> dict:
    return {
        field: [] if field == "treaty_references" else None
        for field in EXTRACTION_FIELDS
    } | {"uncertain_fields": []}


def _usage_snapshot(gateway: Gateway) -> Usage:
    usage = gateway.usage
    return Usage(usage.input_tokens, usage.output_tokens, usage.calls)


def _record_usage(before: Usage, after: Usage, calls: int) -> Usage:
    return Usage(
        input_tokens=after.input_tokens - before.input_tokens,
        output_tokens=after.output_tokens - before.output_tokens,
        calls=calls,
    )


def extract_with_llm(
    documents: list[IngestedDocument], gateway: Gateway
) -> ExtractionResult:
    system, user = build_prompt(documents)
    document_ids = {document.document_id for document in documents}
    usage_before = _usage_snapshot(gateway)
    validation_errors: list[str] = []
    retry_user = user

    for attempt in range(2):
        reply = gateway.complete(
            system=system,
            user=retry_user,
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
        )
        calls = attempt + 1
        try:
            wrapper = _parse_and_validate(reply)
            wrapper, repair_errors = _repair_unknown_evidence(wrapper, document_ids)
            plain = _unwrap(wrapper)
        except Exception as exc:
            validation_errors.append(str(exc))
            if attempt == 0:
                retry_user = (
                    f"{user}\n\n<validation_error>\n{exc}\n</validation_error>\n"
                    "Correct the validation error and return only one valid JSON object."
                )
                continue
            return ExtractionResult(
                plain=_failed_plain(),
                status="failed",
                calls=calls,
                validation_errors=validation_errors,
                usage=_record_usage(usage_before, _usage_snapshot(gateway), calls),
            )

        validation_errors.extend(repair_errors)
        return ExtractionResult(
            plain=plain,
            status="repaired" if attempt == 1 or repair_errors else "ok",
            calls=calls,
            validation_errors=validation_errors,
            usage=_record_usage(usage_before, _usage_snapshot(gateway), calls),
        )

    raise AssertionError("unreachable")

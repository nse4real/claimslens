from __future__ import annotations

import json
from pathlib import Path

from src.evals.scorer import SCORED_FIELDS
from src.review.review_set import DEFAULT_REVIEW_SET_PATH, read_review_set, review_record_ids

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_DIR = ROOT / "evals" / "gold" / "records"
DEFAULT_PACKET_DIR = ROOT / "data" / "review" / "packets"


def _source_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _render_packet(record: dict, source_root: Path) -> str:
    record_id = record["record_id"]
    promoted = record["provenance"]["label_status"] == "gold"
    title = f"# Notification {record_id}" + (" (already promoted)" if promoted else "")
    lines = [
        title,
        "",
        "Read the source text and fill in the form. Your task is to label from the source text only; "
        "do not look for other information. Leave a value empty when the source has no value.",
        "",
        "Write dates as YYYY-MM-DD, money as AMOUNT CURRENCY, and multiple treaty references "
        "as a semicolon-separated list.",
        "",
        "## Source documents",
        "",
    ]
    for document in record["source_documents"]:
        document_type = document["document_type"]
        source_path = source_root / document["corpus_path"]
        label = "Email" if document_type == "email" else f"Attachment: {source_path.name}"
        text = _source_text(source_path)
        lines.extend(
            [
                f"### {label}",
                "",
                f"Document ID: {document['document_id']}",
                "",
                "```text",
                text if text.endswith("\n") else text + "\n",
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Form",
            "",
            "| Field | Value | reviewer_note |",
            "| --- | --- | --- |",
            *(f"| {field} |  |  |" for field in SCORED_FIELDS),
            "",
        ]
    )
    return "\n".join(lines)


def generate_packets(
    review_set_path: str | Path = DEFAULT_REVIEW_SET_PATH,
    *,
    gold_dir: str | Path = DEFAULT_GOLD_DIR,
    output_dir: str | Path = DEFAULT_PACKET_DIR,
    source_root: str | Path = ROOT,
) -> list[Path]:
    review_set = read_review_set(review_set_path)
    gold_root = Path(gold_dir)
    packet_root = Path(output_dir)
    packet_root.mkdir(parents=True, exist_ok=True)
    record_ids = review_record_ids(review_set)
    expected_names = {f"{record_id}.md" for record_id in record_ids}
    for existing in packet_root.glob("*.md"):
        if existing.name not in expected_names:
            existing.unlink()

    written = []
    for record_id in record_ids:
        record = json.loads((gold_root / f"{record_id}.json").read_text(encoding="utf-8"))
        packet_path = packet_root / f"{record_id}.md"
        packet_path.write_bytes(_render_packet(record, Path(source_root)).encode("utf-8"))
        written.append(packet_path)
    return written

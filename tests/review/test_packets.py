import json
import re
from pathlib import Path

import pytest

from src.evals.scorer import SCORED_FIELDS
from src.review.packets import generate_packets
from src.review.review_set import generate_review_set, review_record_ids

ROOT = Path(__file__).resolve().parents[2]
GOLD_DIR = ROOT / "evals" / "gold" / "records"


def read_exact(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def scalar_values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from scalar_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from scalar_values(item)
    elif value is not None and str(value):
        yield str(value)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("packets")
    review_set_path = root / "review_set.json"
    review_set = generate_review_set(output_path=review_set_path)
    packet_dir = root / "packets"
    paths = generate_packets(
        review_set_path,
        gold_dir=GOLD_DIR,
        output_dir=packet_dir,
        source_root=ROOT,
    )
    return review_set, review_set_path, packet_dir, paths


def test_05_packets_exist_for_all_127_review_records_one_file_each(generated):
    review_set, _, packet_dir, paths = generated
    expected = {f"{record_id}.md" for record_id in review_record_ids(review_set)}
    assert len(paths) == 127
    assert {path.name for path in packet_dir.glob("*.md")} == expected


def test_06_every_packet_contains_full_email_and_attachment_text(generated):
    review_set, _, packet_dir, _ = generated
    for record_id in review_record_ids(review_set):
        record = json.loads((GOLD_DIR / f"{record_id}.json").read_text(encoding="utf-8"))
        packet = read_exact(packet_dir / f"{record_id}.md")
        for document in record["source_documents"]:
            assert read_exact(ROOT / document["corpus_path"]) in packet
            assert document["document_id"] in packet


def test_07_every_packet_has_blank_form_lines_for_16_fields_in_b4_order(generated):
    review_set, _, packet_dir, _ = generated
    for record_id in review_record_ids(review_set):
        packet = read_exact(packet_dir / f"{record_id}.md")
        positions = []
        for field in SCORED_FIELDS:
            form_line = f"| {field} |  |  |"
            assert packet.count(form_line) == 1
            positions.append(packet.index(form_line))
        assert positions == sorted(positions)
        assert "reviewer_note" in packet


def test_08_packets_are_blind_to_values_metadata_and_label_notes(generated):
    review_set, _, packet_dir, _ = generated
    forbidden = re.compile(r"\b(?:gold|generator|label_status|tags|split)\b", re.IGNORECASE)
    for record_id in review_record_ids(review_set):
        record = json.loads((GOLD_DIR / f"{record_id}.json").read_text(encoding="utf-8"))
        packet = read_exact(packet_dir / f"{record_id}.md")
        source = "\n".join(
            read_exact(ROOT / document["corpus_path"])
            for document in record["source_documents"]
        )
        assert forbidden.search(packet) is None
        extraction = record["labels"]["extraction"]
        for field in SCORED_FIELDS:
            for value in scalar_values(extraction[field]):
                if value not in source:
                    assert value not in packet
        for note in record["label_notes"]:
            assert note["note"] not in packet


def test_09_packets_are_byte_identical_across_two_generations(generated):
    _, review_set_path, packet_dir, _ = generated
    second_dir = packet_dir.parent / "packets-second"
    generate_packets(
        review_set_path,
        gold_dir=GOLD_DIR,
        output_dir=second_dir,
        source_root=ROOT,
    )
    first = {path.name: path.read_bytes() for path in packet_dir.glob("*.md")}
    second = {path.name: path.read_bytes() for path in second_dir.glob("*.md")}
    assert first == second


def test_already_promoted_packet_is_marked_and_still_blank(tmp_path):
    record_id = "GN-1001"
    record = json.loads((GOLD_DIR / f"{record_id}.json").read_text(encoding="utf-8"))
    record["provenance"]["label_status"] = "gold"
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    (gold_dir / f"{record_id}.json").write_text(json.dumps(record), encoding="utf-8")
    review_set_path = tmp_path / "review_set.json"
    review_set_path.write_text(
        json.dumps({"seed": 1, "reference_date": "2026-10-17", "holdout": [], "dev": [record_id], "total": 1}),
        encoding="utf-8",
    )
    packet_path = generate_packets(
        review_set_path,
        gold_dir=gold_dir,
        output_dir=tmp_path / "packets",
        source_root=ROOT,
    )[0]
    packet = packet_path.read_text(encoding="utf-8")
    assert packet.startswith(f"# Notification {record_id} (already promoted)\n")
    assert all(f"| {field} |  |  |" in packet for field in SCORED_FIELDS)

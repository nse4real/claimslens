import copy
import csv
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from src.evals.scorer import SCORED_FIELDS
from src.review.decisions import ADJUDICATION_COLUMNS, DECISION_COLUMNS
from src.review.promote import promote

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_GOLD_DIR = ROOT / "evals" / "gold" / "records"
PROMOTED_ON = "2026-10-18"
REVIEWER_ID = "reviewer-7"


def serialise(value):
    if value is None:
        return ""
    if isinstance(value, dict):
        return f"{value['amount']} {value['currency']}"
    if isinstance(value, list):
        return ";".join(value)
    return str(value)


def make_case(tmp_path, record_ids):
    root = tmp_path / "workspace"
    gold_dir = root / "evals" / "gold" / "records"
    shutil.copytree(COMMITTED_GOLD_DIR, gold_dir)
    review_dir = root / "data" / "review"
    review_dir.mkdir(parents=True)
    review_set_path = review_dir / "review_set.json"
    review_set_path.write_text(
        json.dumps({
            "seed": 20261017,
            "reference_date": "2026-10-17",
            "holdout": [],
            "dev": list(record_ids),
            "total": len(record_ids),
        }),
        encoding="utf-8",
    )
    decisions = {}
    for record_id in record_ids:
        record = json.loads((gold_dir / f"{record_id}.json").read_text(encoding="utf-8"))
        for field in SCORED_FIELDS:
            decisions[(record_id, field)] = copy.deepcopy(record["labels"]["extraction"][field])
    return SimpleNamespace(
        root=root,
        gold_dir=gold_dir,
        review_dir=review_dir,
        review_set_path=review_set_path,
        decisions_path=review_dir / "decisions.csv",
        decisions=decisions,
        record_ids=record_ids,
    )


def write_decisions(case):
    with case.decisions_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(DECISION_COLUMNS)
        for record_id in case.record_ids:
            for field in SCORED_FIELDS:
                if (record_id, field) in case.decisions:
                    writer.writerow([record_id, field, serialise(case.decisions[(record_id, field)]), ""])


def write_adjudication(case, rows):
    path = case.review_dir / "adjudication.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(ADJUDICATION_COLUMNS)
        for record_id, field, value in rows:
            writer.writerow(["adjudicator-3", record_id, field, serialise(value), "read both sides"])
    return path


def run_promotion(case, adjudication_path=None):
    return promote(
        case.decisions_path,
        adjudication_path,
        reviewer_id=REVIEWER_ID,
        promoted_on=PROMOTED_ON,
        gold_dir=case.gold_dir,
        review_set_path=case.review_set_path,
        review_dir=case.review_dir,
    )


def file_hashes(root):
    return {
        path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.glob("*.json")
    }


def test_22_promote_writes_gold_for_agreed_record_and_changes_only_provenance(tmp_path):
    case = make_case(tmp_path, ("GN-1001",))
    write_decisions(case)
    path = case.gold_dir / "GN-1001.json"
    expected = json.loads(path.read_text(encoding="utf-8"))

    summary = run_promotion(case)

    assert summary.errors == []
    assert (summary.promoted, summary.disputed, summary.adjudicated) == (1, 0, 0)
    expected["provenance"].update({
        "label_status": "gold",
        "second_labeller_agreed": True,
        "labelled_on": PROMOTED_ON,
        "labeller": f"generator; reviewed by {REVIEWER_ID}",
    })
    updated = json.loads(path.read_text(encoding="utf-8"))
    assert updated == expected
    assert path.read_bytes() == (json.dumps(expected, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def test_23_promote_leaves_disputed_gold_untouched_and_queues_both_values(tmp_path):
    case = make_case(tmp_path, ("GN-1001",))
    key = ("GN-1001", "estimated_loss_amount")
    original = case.decisions[key]
    case.decisions[key] = {"amount": original["amount"], "currency": "XXX"}
    write_decisions(case)
    path = case.gold_dir / "GN-1001.json"
    before = path.read_bytes()

    summary = run_promotion(case)

    assert summary.errors == []
    assert (summary.promoted, summary.disputed, summary.adjudicated) == (0, 1, 0)
    assert path.read_bytes() == before
    queue = json.loads((case.review_dir / "dispute_queue.json").read_text(encoding="utf-8"))
    assert len(queue) == 1
    assert queue[0]["record_id"] == "GN-1001"
    assert queue[0]["disagreeing_fields"] == ["estimated_loss_amount"]
    assert queue[0]["disagreements"]["estimated_loss_amount"] == {
        "reviewer_value": {"amount": original["amount"], "currency": "XXX"},
        "gold_value": original,
    }
    assert not (case.review_dir / "promotion_log.jsonl").exists()


def test_24_adjudication_applies_values_records_adjudicator_and_removes_queue_entry(tmp_path):
    case = make_case(tmp_path, ("GN-1001",))
    key = ("GN-1001", "estimated_loss_amount")
    corrected = {"amount": "9.99", "currency": "USD"}
    case.decisions[key] = {"amount": "8.88", "currency": "GBP"}
    write_decisions(case)
    assert run_promotion(case).disputed == 1
    adjudication_path = write_adjudication(case, [("GN-1001", "estimated_loss_amount", corrected)])

    summary = run_promotion(case, adjudication_path)

    assert summary.errors == []
    assert (summary.promoted, summary.disputed, summary.adjudicated) == (0, 0, 1)
    record = json.loads((case.gold_dir / "GN-1001.json").read_text(encoding="utf-8"))
    assert record["labels"]["extraction"]["estimated_loss_amount"] == corrected
    assert record["provenance"]["label_status"] == "gold"
    assert record["provenance"]["second_labeller_agreed"] is True
    assert record["provenance"]["labeller"] == (
        f"generator; reviewed by {REVIEWER_ID}; adjudicated by adjudicator-3"
    )
    assert json.loads((case.review_dir / "dispute_queue.json").read_text(encoding="utf-8")) == []


def test_25_promotion_log_appends_one_line_per_change_with_after_sha256(tmp_path):
    case = make_case(tmp_path, ("GN-1001", "GN-1003"))
    disputed_key = ("GN-1003", "estimated_loss_amount")
    case.decisions[disputed_key] = {"amount": "8.88", "currency": "XXX"}
    corrected = {"amount": "9.99", "currency": "USD"}
    write_decisions(case)
    adjudication_path = write_adjudication(case, [("GN-1003", "estimated_loss_amount", corrected)])

    summary = run_promotion(case, adjudication_path)

    assert summary.errors == []
    assert (summary.promoted, summary.disputed, summary.adjudicated) == (1, 0, 1)
    lines = (case.review_dir / "promotion_log.jsonl").read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines]
    assert len(entries) == 2
    by_id = {entry["record_id"]: entry for entry in entries}
    assert by_id["GN-1001"]["action"] == "promoted"
    assert by_id["GN-1001"]["changed_fields"] == []
    assert by_id["GN-1001"]["adjudicator"] is None
    assert by_id["GN-1003"]["action"] == "adjudicated"
    assert by_id["GN-1003"]["changed_fields"] == ["estimated_loss_amount"]
    assert by_id["GN-1003"]["adjudicator"] == "adjudicator-3"
    for record_id, entry in by_id.items():
        content = (case.gold_dir / f"{record_id}.json").read_bytes()
        assert entry["sha256"] == hashlib.sha256(content).hexdigest()
        assert entry["reviewer_id"] == REVIEWER_ID
        assert entry["promoted_on"] == PROMOTED_ON


def test_26_promote_refuses_incomplete_decisions_without_changing_any_file(tmp_path):
    case = make_case(tmp_path, ("GN-1001", "GN-1003"))
    del case.decisions[("GN-1003", SCORED_FIELDS[-1])]
    write_decisions(case)
    before = file_hashes(case.gold_dir)

    summary = run_promotion(case)

    assert summary.errors
    assert "missing row" in summary.errors[0]
    assert file_hashes(case.gold_dir) == before
    assert not (case.review_dir / "promotion_log.jsonl").exists()
    assert not (case.review_dir / "dispute_queue.json").exists()


def test_27_promote_rolls_back_earlier_writes_when_read_only_target_fails(tmp_path):
    case = make_case(tmp_path, ("GN-1001", "GN-1003"))
    write_decisions(case)
    first_path = case.gold_dir / "GN-1001.json"
    second_path = case.gold_dir / "GN-1003.json"
    first_before = first_path.read_bytes()
    second_before = second_path.read_bytes()
    second_path.chmod(0o444)
    try:
        summary = run_promotion(case)
    finally:
        second_path.chmod(0o666)

    assert summary.errors
    assert summary.promoted == 0
    assert first_path.read_bytes() == first_before
    assert second_path.read_bytes() == second_before
    assert not (case.review_dir / "promotion_log.jsonl").exists()
    assert not (case.review_dir / "dispute_queue.json").exists()


def test_28_promotion_never_changes_split_or_tags(tmp_path):
    case = make_case(tmp_path, ("GN-1001", "GN-1003"))
    key = ("GN-1003", "estimated_loss_amount")
    case.decisions[key] = {"amount": "8.88", "currency": "XXX"}
    write_decisions(case)
    adjudication_path = write_adjudication(case, [("GN-1003", "estimated_loss_amount", {"amount": "1.00", "currency": "EUR"})])
    before = {
        record_id: json.loads((case.gold_dir / f"{record_id}.json").read_text(encoding="utf-8"))
        for record_id in case.record_ids
    }

    summary = run_promotion(case, adjudication_path)

    assert summary.errors == []
    for record_id in case.record_ids:
        after = json.loads((case.gold_dir / f"{record_id}.json").read_text(encoding="utf-8"))
        assert after["split"] == before[record_id]["split"]
        assert after["tags"] == before[record_id]["tags"]


def test_already_gold_agreed_record_is_not_rewritten(tmp_path):
    case = make_case(tmp_path, ("GN-1001",))
    write_decisions(case)
    path = case.gold_dir / "GN-1001.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["provenance"]["label_status"] = "gold"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    before = path.read_bytes()

    summary = run_promotion(case)

    assert summary.errors == []
    assert summary.promoted == 0
    assert path.read_bytes() == before
    assert not (case.review_dir / "promotion_log.jsonl").exists()

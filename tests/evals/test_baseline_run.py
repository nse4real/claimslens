"""Acceptance tests for the B10 baseline runner (plan items 23 to 31)."""

import hashlib
import json
from pathlib import Path

import pytest

from src.evals.runner import run_baseline

ROOT = Path(__file__).resolve().parents[2]
GOLD_DIR = ROOT / "evals" / "gold" / "records"

REQUIRED_TOP_LEVEL_KEYS = (
    "prompt_version",
    "model_identifier",
    "extractor",
    "dataset_version",
    "split",
    "scorer_version",
    "timestamp",
    "label_status_counts",
    "provisional",
    "record_count",
    "split_counts",
    "metrics",
)


@pytest.fixture(scope="module")
def dev_run(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("baseline_dev")
    path = run_baseline("dev", out_dir)
    return out_dir, json.loads(path.read_text(encoding="utf-8"))


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def holdout_record_ids() -> set[str]:
    ids = set()
    for path in GOLD_DIR.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["split"] == "holdout":
            ids.add(record["record_id"])
    return ids


def test_holdout_split_raises(dev_run):
    with pytest.raises(ValueError, match="holdout is not scored by the baseline runner"):
        run_baseline("holdout", dev_run[0])


def test_all_split_raises(tmp_path):
    with pytest.raises(ValueError, match="holdout is not scored by the baseline runner"):
        run_baseline("all", tmp_path)


def test_dev_run_writes_results_file_with_required_keys(dev_run):
    out_dir, report = dev_run
    assert (out_dir / "baseline-regex-v1__dev.json").is_file()
    for key in REQUIRED_TOP_LEVEL_KEYS:
        assert key in report, key
    assert report["prompt_version"] == "baseline-regex-v1"
    assert report["split"] == "dev"
    assert report["dataset_version"].endswith("corpus-seed-20261017")
    assert set(report["metrics"]) == {"exact", "fuzzy"}


def test_results_are_provisional_with_single_label_counts(dev_run):
    _, report = dev_run
    assert report["provisional"] is True
    assert report["label_status_counts"] == {"gold": 0, "single": 158}


def test_dev_record_count_is_158(dev_run):
    _, report = dev_run
    assert report["record_count"] == 158
    assert report["split_counts"]["dev"] == 158


def test_two_runs_differ_only_in_timestamp(dev_run, tmp_path):
    _, first = dev_run
    second_path = run_baseline("dev", tmp_path)
    second = json.loads(second_path.read_text(encoding="utf-8"))
    assert first["metrics"] == second["metrics"]
    assert first["label_status_counts"] == second["label_status_counts"]
    assert first["record_count"] == second["record_count"]
    assert first["split_counts"] == second["split_counts"]
    first_without_timestamp = {k: v for k, v in first.items() if k != "timestamp"}
    second_without_timestamp = {k: v for k, v in second.items() if k != "timestamp"}
    assert first_without_timestamp == second_without_timestamp


def test_no_holdout_record_ids_in_failed_cases_or_per_tag(dev_run):
    _, report = dev_run
    holdout_ids = holdout_record_ids()
    assert holdout_ids
    for mode_report in report["metrics"].values():
        for cases in mode_report["failed_cases"].values():
            for case in cases:
                assert case["record_id"] not in holdout_ids
        for tag in mode_report["per_tag"]:
            assert tag not in holdout_ids


def test_every_metric_entry_reports_counts_beside_precision_and_recall(dev_run):
    _, report = dev_run
    count_keys = {"tp", "fp_precision", "fn_recall", "ignored", "precision_denominator", "recall_denominator"}
    for mode_report in report["metrics"].values():
        entries = list(mode_report["fields"].values())
        for tag_counts in mode_report["per_tag"].values():
            entries.extend(tag_counts.values())
        assert entries
        for entry in entries:
            assert count_keys <= set(entry)
            assert "precision" in entry
            assert "recall" in entry
            assert entry["precision_denominator"] == entry["tp"] + entry["fp_precision"]
            assert entry["recall_denominator"] == entry["tp"] + entry["fn_recall"]


def test_runner_writes_one_file_and_does_not_modify_inputs(tmp_path):
    before_corpus = hash_tree(ROOT / "data" / "corpus")
    before_gold = hash_tree(ROOT / "evals" / "gold")
    out_path = run_baseline("dev", tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == [out_path.name]
    assert hash_tree(ROOT / "data" / "corpus") == before_corpus
    assert hash_tree(ROOT / "evals" / "gold") == before_gold

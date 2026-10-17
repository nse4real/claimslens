"""Acceptance tests for the dev-only LLM runner (plan items 20 to 25)."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.evals.llm_runner import run_llm_dev
from src.llm.gateway import CallCapExceeded, Usage

ROOT = Path(__file__).resolve().parents[2]
EMPTY_FIXTURE = ROOT / "tests" / "fixtures" / "loss_notification" / "empty.json"
EMPTY_WRAPPER = json.loads(EMPTY_FIXTURE.read_text(encoding="utf-8"))

B10_TOP_LEVEL_KEYS = {
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
}


class FakeGateway:
    def __init__(self, max_calls=None):
        self.max_calls = max_calls
        self._usage = Usage()
        self.calls = []

    @property
    def usage(self):
        return Usage(
            self._usage.input_tokens,
            self._usage.output_tokens,
            self._usage.calls,
        )

    def complete(self, system, user, model, max_tokens):
        if self.max_calls is not None and self._usage.calls >= self.max_calls:
            raise CallCapExceeded("fake call cap exceeded")
        self.calls.append({"model": model, "max_tokens": max_tokens})
        self._usage.calls += 1
        self._usage.input_tokens += 3
        self._usage.output_tokens += 2

        metadata_text = user.split("Copy this runtime metadata exactly:\n", 1)[1]
        metadata_text = metadata_text.split("\n</context>", 1)[0]
        metadata = json.loads(metadata_text)
        wrapper = deepcopy(EMPTY_WRAPPER)
        wrapper["source_documents"] = metadata["source_documents"]
        wrapper["intake_metadata"] = metadata["intake_metadata"]
        return json.dumps(wrapper)


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture(scope="module")
def dev_run(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("llm_dev")
    path = run_llm_dev("dev", out_dir, gateway=FakeGateway())
    return out_dir, json.loads(path.read_text(encoding="utf-8"))


def test_20_holdout_and_all_are_refused():
    for split in ("holdout", "all"):
        with pytest.raises(
            ValueError, match="holdout is not scored by the LLM runner"
        ):
            run_llm_dev(split)


def test_21_fake_gateway_run_writes_b10_shape_plus_llm_accounting(dev_run):
    out_dir, report = dev_run

    assert (out_dir / "llm-extract-v1__dev.json").is_file()
    assert B10_TOP_LEVEL_KEYS <= set(report)
    assert {
        "calls",
        "retries",
        "failed_records",
        "usage",
        "model_identifier",
        "temperature",
    } <= set(report)
    assert report["temperature"] == 0
    assert report["calls"] == 158
    assert report["retries"] == 0
    assert report["failed_records"] == 0
    assert report["usage"] == {"input_tokens": 474, "output_tokens": 316}
    assert report["cost_gbp"] is None


def test_22_fake_gateway_run_has_158_records_and_is_provisional(dev_run):
    _, report = dev_run

    assert report["record_count"] == 158
    assert report["provisional"] is True
    assert report["label_status_counts"] == {"gold": 0, "single": 158}
    assert report["split_counts"] == {"dev": 158, "holdout": 67}


def test_23_two_fake_gateway_runs_have_identical_metrics(dev_run, tmp_path):
    _, first = dev_run
    second_path = run_llm_dev("dev", tmp_path, gateway=FakeGateway())
    second = json.loads(second_path.read_text(encoding="utf-8"))

    assert first["metrics"] == second["metrics"]
    first_without_timestamp = {k: v for k, v in first.items() if k != "timestamp"}
    second_without_timestamp = {k: v for k, v in second.items() if k != "timestamp"}
    assert first_without_timestamp == second_without_timestamp


def test_24_runner_writes_one_result_and_does_not_modify_corpus_or_gold(tmp_path):
    before_corpus = hash_tree(ROOT / "data" / "corpus")
    before_gold = hash_tree(ROOT / "evals" / "gold")

    out_path = run_llm_dev("dev", tmp_path, gateway=FakeGateway())

    assert [path.name for path in tmp_path.iterdir()] == [out_path.name]
    assert hash_tree(ROOT / "data" / "corpus") == before_corpus
    assert hash_tree(ROOT / "evals" / "gold") == before_gold


def test_25_call_cap_failure_writes_no_partial_result(tmp_path):
    gateway = FakeGateway(max_calls=1)

    with pytest.raises(CallCapExceeded):
        run_llm_dev("dev", tmp_path, gateway=gateway)

    assert not (tmp_path / "llm-extract-v1__dev.json").exists()
    assert list(tmp_path.iterdir()) == []

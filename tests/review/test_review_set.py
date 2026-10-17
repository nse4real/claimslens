import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from data.generators.notifications import build_scenarios
from src.review.review_set import generate_review_set

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "corpus" / "notifications_manifest.json"


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    output_path = tmp_path_factory.mktemp("review-set") / "review_set.json"
    review_set = generate_review_set(output_path=output_path)
    return review_set, output_path


def test_01_review_set_selects_67_holdout_and_60_dev_records(generated):
    review_set, _ = generated
    assert len(review_set["holdout"]) == 67
    assert len(review_set["dev"]) == 60
    assert review_set["total"] == 127
    assert review_set["seed"] == 20261017


def test_02_review_set_records_come_from_their_named_manifest_splits(generated):
    review_set, _ = generated
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    splits = {entry["record_id"]: entry["split"] for entry in manifest["records"]}
    assert all(splits[record_id] == "dev" for record_id in review_set["dev"])
    assert all(splits[record_id] == "holdout" for record_id in review_set["holdout"])
    assert not set(review_set["dev"]) & set(review_set["holdout"])


def test_03_dev_allocation_covers_every_primary_tag_within_one_of_proportional(generated):
    review_set, _ = generated
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    dev_entries = [entry for entry in manifest["records"] if entry["split"] == "dev"]
    dev_counts = Counter(entry["tags"][0] for entry in dev_entries)
    tags = {entry["record_id"]: entry["tags"][0] for entry in dev_entries}
    selected_counts = Counter(tags[record_id] for record_id in review_set["dev"])
    assert set(selected_counts) == set(dev_counts)
    for tag, count in dev_counts.items():
        proportional = count * 60 / len(dev_entries)
        assert selected_counts[tag] > 0
        assert abs(selected_counts[tag] - proportional) <= 1


def test_04_rerunning_review_set_gives_an_identical_file(generated):
    _, output_path = generated
    before = output_path.read_bytes()
    generate_review_set(output_path=output_path)
    assert output_path.read_bytes() == before


def test_near_duplicate_groups_are_selected_atomically(generated):
    review_set, _ = generated
    selected = set(review_set["dev"])
    groups = defaultdict(set)
    for scenario in build_scenarios():
        if scenario["near_duplicate_group"] and scenario["split"] == "dev":
            groups[scenario["near_duplicate_group"]].add(scenario["record_id"])
    for members in groups.values():
        assert not selected & members or members <= selected

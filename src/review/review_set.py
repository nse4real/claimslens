from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from data.generators.notifications import DEFAULT_SEED, build_scenarios

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = ROOT / "data" / "corpus" / "notifications_manifest.json"
DEFAULT_REVIEW_SET_PATH = ROOT / "data" / "review" / "review_set.json"
DEV_REVIEW_COUNT = 60


def review_record_ids(review_set: dict[str, Any]) -> list[str]:
    record_ids = [*review_set["holdout"], *review_set["dev"]]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("Review set contains duplicate record IDs")
    return record_ids


def read_review_set(path: str | Path = DEFAULT_REVIEW_SET_PATH) -> dict[str, Any]:
    review_set = json.loads(Path(path).read_text(encoding="utf-8"))
    review_record_ids(review_set)
    return review_set


def _allocate_tags(tag_order: list[str], dev_counts: Counter[str], target: int) -> dict[str, int]:
    dev_total = sum(dev_counts.values())
    allocations = {
        tag: max(1, dev_counts[tag] * target // dev_total)
        for tag in tag_order
    }
    remaining = target - sum(allocations.values())
    if remaining < 0:
        raise ValueError("Review set is too small to cover every primary tag")
    remainders = {
        tag: dev_counts[tag] * target % dev_total
        for tag in tag_order
    }
    order_index = {tag: index for index, tag in enumerate(tag_order)}
    for tag in sorted(tag_order, key=lambda item: (-remainders[item], order_index[item]))[:remaining]:
        allocations[tag] += 1
    return allocations


def _near_duplicate_groups(manifest: dict[str, Any]) -> dict[str, list[str]]:
    scenarios = build_scenarios(seed=manifest.get("seed", DEFAULT_SEED))
    groups: dict[str, list[str]] = defaultdict(list)
    for scenario in scenarios:
        group = scenario["near_duplicate_group"]
        if group:
            groups[group].append(scenario["record_id"])
    return {group: sorted(record_ids) for group, record_ids in groups.items()}


def generate_review_set(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    output_path: str | Path = DEFAULT_REVIEW_SET_PATH,
    *,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    entries = manifest["records"]
    holdout = sorted(entry["record_id"] for entry in entries if entry["split"] == "holdout")
    dev_entries = [entry for entry in entries if entry["split"] == "dev"]
    dev_by_id = {entry["record_id"]: entry for entry in dev_entries}
    tag_order = list(dict.fromkeys(entry["tags"][0] for entry in dev_entries))
    dev_counts = Counter(entry["tags"][0] for entry in dev_entries)
    allocations = _allocate_tags(tag_order, dev_counts, DEV_REVIEW_COUNT)

    groups = _near_duplicate_groups(manifest)
    record_group = {
        record_id: group
        for group, record_ids in groups.items()
        for record_id in record_ids
    }
    selected: set[str] = set()
    selected_counts: Counter[str] = Counter()
    rng = random.Random(seed)
    selection_order = sorted(tag_order, key=lambda tag: (tag != "near_duplicate", tag_order.index(tag)))

    for tag in selection_order:
        candidates = sorted(
            entry["record_id"] for entry in dev_entries if entry["tags"][0] == tag
        )
        for record_id in rng.sample(candidates, len(candidates)):
            if selected_counts[tag] >= allocations[tag]:
                break
            if record_id in selected:
                continue
            group = record_group.get(record_id)
            members = groups[group] if group is not None else [record_id]
            if any(member not in dev_by_id for member in members):
                continue
            new_members = [member for member in members if member not in selected]
            required = Counter(dev_by_id[member]["tags"][0] for member in new_members)
            if any(
                selected_counts[member_tag] + count > allocations[member_tag]
                for member_tag, count in required.items()
            ):
                continue
            selected.update(new_members)
            selected_counts.update(required)

    if selected_counts != Counter(allocations):
        raise ValueError(
            f"Could not satisfy stratified review allocation: {dict(selected_counts)} != {allocations}"
        )

    review_set = {
        "seed": seed,
        "reference_date": manifest["reference_date"],
        "holdout": holdout,
        "dev": sorted(selected),
        "total": len(holdout) + len(selected),
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(review_set, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return review_set

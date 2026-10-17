from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.evals.scorer import SCORED_FIELDS
from src.review.agreement import check_agreement
from src.review.decisions import DecisionsError, read_adjudications, read_decisions
from src.review.review_set import DEFAULT_REVIEW_SET_PATH, read_review_set, review_record_ids

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_DIR = ROOT / "evals" / "gold" / "records"
DEFAULT_REVIEW_DIR = ROOT / "data" / "review"


@dataclass
class PromotionSummary:
    promoted: int = 0
    disputed: int = 0
    adjudicated: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def promoted_count(self) -> int:
        return self.promoted

    @property
    def disputed_count(self) -> int:
        return self.disputed

    @property
    def adjudicated_count(self) -> int:
        return self.adjudicated


@dataclass
class _GoldChange:
    record_id: str
    path: Path
    content: bytes
    action: str
    adjudicator: str | None
    changed_fields: list[str]


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0:
        raise PermissionError(f"read-only target: {path}")
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=False, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _paths(
    gold_dir: str | Path,
    review_dir: str | Path | None,
    review_set_path: str | Path | None,
) -> tuple[Path, Path, Path]:
    gold_root = Path(gold_dir)
    if review_dir is None:
        if gold_root.resolve() == DEFAULT_GOLD_DIR.resolve():
            review_root = DEFAULT_REVIEW_DIR
        elif (
            len(gold_root.parents) >= 3
            and gold_root.parents[0].name == "gold"
            and gold_root.parents[1].name == "evals"
        ):
            review_root = gold_root.parents[2] / "data" / "review"
        else:
            review_root = gold_root.parent / "review"
    else:
        review_root = Path(review_dir)
    selected_path = Path(review_set_path) if review_set_path is not None else review_root / "review_set.json"
    return gold_root, review_root, selected_path


def _set_provenance(
    record: dict[str, Any],
    *,
    reviewer_id: str,
    promoted_on: str,
    adjudicator: str | None,
) -> None:
    provenance = record["provenance"]
    provenance["label_status"] = "gold"
    provenance["second_labeller_agreed"] = True
    provenance["labelled_on"] = promoted_on
    provenance["labeller"] = f"generator; reviewed by {reviewer_id}"
    if adjudicator is not None:
        provenance["labeller"] += f"; adjudicated by {adjudicator}"


def _load_queue(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    queue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(queue, list):
        raise ValueError("Dispute queue must be a JSON list")
    return queue


def promote(
    decisions_path: str | Path,
    adjudication_path: str | Path | None = None,
    *,
    reviewer_id: str,
    promoted_on: str,
    gold_dir: str | Path = DEFAULT_GOLD_DIR,
    review_set_path: str | Path | None = None,
    review_dir: str | Path | None = None,
) -> PromotionSummary:
    gold_root, review_root, selected_path = _paths(gold_dir, review_dir, review_set_path)
    queue_path = review_root / "dispute_queue.json"
    log_path = review_root / "promotion_log.jsonl"

    try:
        if not reviewer_id.strip():
            raise ValueError("reviewer_id is required")
        review_set = read_review_set(selected_path)
        record_ids = review_record_ids(review_set)
        decisions = read_decisions(decisions_path, selected_path)
        adjudication_rows = (
            read_adjudications(adjudication_path, selected_path)
            if adjudication_path is not None
            else {}
        )
        adjudications: dict[str, list[tuple[str, Any]]] = {}
        for (record_id, field_name), adjudication in adjudication_rows.items():
            adjudications.setdefault(record_id, []).append((field_name, adjudication))

        records = {
            record_id: json.loads((gold_root / f"{record_id}.json").read_text(encoding="utf-8"))
            for record_id in record_ids
        }
        existing_queue = _load_queue(queue_path)
        disputes = {}
        changes: list[_GoldChange] = []

        for record_id in record_ids:
            record = records[record_id]
            gold_extraction = record["labels"]["extraction"]
            agreement = check_agreement(record_id, gold_extraction, decisions)
            if record_id in adjudications:
                updated = copy.deepcopy(record)
                by_field = dict(adjudications[record_id])
                adjudicator = by_field[adjudications[record_id][0][0]].adjudicator
                for field_name in SCORED_FIELDS:
                    if field_name in by_field:
                        updated["labels"]["extraction"][field_name] = by_field[field_name].value
                _set_provenance(
                    updated,
                    reviewer_id=reviewer_id,
                    promoted_on=promoted_on,
                    adjudicator=adjudicator,
                )
                changed_fields = [field_name for field_name in SCORED_FIELDS if field_name in by_field]
                changes.append(
                    _GoldChange(
                        record_id=record_id,
                        path=gold_root / f"{record_id}.json",
                        content=_json_bytes(updated),
                        action="adjudicated",
                        adjudicator=adjudicator,
                        changed_fields=changed_fields,
                    )
                )
            elif agreement.agreed:
                if record["provenance"]["label_status"] != "gold":
                    updated = copy.deepcopy(record)
                    _set_provenance(
                        updated,
                        reviewer_id=reviewer_id,
                        promoted_on=promoted_on,
                        adjudicator=None,
                    )
                    changes.append(
                        _GoldChange(
                            record_id=record_id,
                            path=gold_root / f"{record_id}.json",
                            content=_json_bytes(updated),
                            action="promoted",
                            adjudicator=None,
                            changed_fields=[],
                        )
                    )
            else:
                disputes[record_id] = agreement

        originals = {change.path: change.path.read_bytes() for change in changes}
        original_hashes = {
            path: hashlib.sha256(content).hexdigest() for path, content in originals.items()
        }
        written: list[_GoldChange] = []
        try:
            for change in changes:
                _atomic_write(change.path, change.content)
                written.append(change)
        except OSError as exc:
            rollback_errors = []
            for change in reversed(written):
                try:
                    _atomic_write(change.path, originals[change.path])
                    restored_hash = hashlib.sha256(change.path.read_bytes()).hexdigest()
                    if restored_hash != original_hashes[change.path]:
                        rollback_errors.append(f"hash mismatch restoring {change.record_id}")
                except OSError as rollback_exc:
                    rollback_errors.append(f"failed to restore {change.record_id}: {rollback_exc}")
            return PromotionSummary(
                disputed=len(disputes),
                errors=[str(exc), *rollback_errors],
            )

        current_ids = set(record_ids)
        queue = [entry for entry in existing_queue if entry.get("record_id") not in current_ids]
        queue.extend(
            {
                "record_id": record_id,
                "disagreeing_fields": disputes[record_id].disagreeing_fields,
                "disagreements": disputes[record_id].disagreements,
            }
            for record_id in record_ids
            if record_id in disputes
        )
        if queue or queue_path.exists():
            _atomic_write(queue_path, _json_bytes(queue))

        if changes:
            review_root.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8", newline="\n") as log:
                for change in changes:
                    entry = {
                        "record_id": change.record_id,
                        "action": change.action,
                        "reviewer_id": reviewer_id,
                        "adjudicator": change.adjudicator,
                        "promoted_on": promoted_on,
                        "changed_fields": change.changed_fields,
                        "sha256": hashlib.sha256(change.path.read_bytes()).hexdigest(),
                    }
                    log.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return PromotionSummary(
            promoted=sum(change.action == "promoted" for change in changes),
            disputed=len(disputes),
            adjudicated=sum(change.action == "adjudicated" for change in changes),
        )
    except (DecisionsError, OSError, ValueError) as exc:
        return PromotionSummary(errors=[str(exc)])

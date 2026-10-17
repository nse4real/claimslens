"""Baseline runner (B10): scores the dev split and writes a versioned results JSON.

The holdout split is never scored by this runner (eval plan section 2.5).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.evals.scorer import FUZZY_THRESHOLD, SIMILARITY_METRIC, SCORER_VERSION, score_records
from src.extraction.baseline.rules_extractor import EXTRACTOR_VERSION, extract
from src.ingestion.pipeline import ingest_folder

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "corpus" / "notifications_manifest.json"
DEFAULT_OUT_DIR = ROOT / "evals" / "results"

PROMPT_VERSION = "baseline-regex-v1"
HOLDOUT_MESSAGE = "holdout is not scored by the baseline runner"


def run_baseline(split: str = "dev", out_dir: Path | str | None = None) -> Path:
    if split != "dev":
        raise ValueError(HOLDOUT_MESSAGE)
    out = Path(out_dir) if out_dir is not None else DEFAULT_OUT_DIR

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pairs = []
    label_status_counts = {"gold": 0, "single": 0}
    split_counts = {"dev": 0, "holdout": 0}
    schema_version = None
    for entry in manifest["records"]:
        gold = json.loads((ROOT / entry["gold_path"]).read_text(encoding="utf-8"))
        record_split = gold["split"]
        split_counts[record_split] += 1
        if record_split != split:
            continue
        schema_version = gold["schema_version"]
        status = gold["provenance"]["label_status"]
        label_status_counts[status] = label_status_counts.get(status, 0) + 1
        documents = ingest_folder(ROOT / entry["folder"])
        predicted = extract(documents)
        pairs.append(
            (gold["record_id"], list(gold["tags"]), predicted, gold["labels"]["extraction"])
        )

    metrics = {mode: score_records(pairs, mode) for mode in ("exact", "fuzzy")}
    report = {
        "prompt_version": PROMPT_VERSION,
        "model_identifier": "none",
        "extractor": EXTRACTOR_VERSION,
        "dataset_version": f"gold-schema-{schema_version}__corpus-seed-{manifest['seed']}",
        "split": split,
        "scorer_version": {
            "name": SCORER_VERSION,
            "fuzzy_threshold": f"{FUZZY_THRESHOLD:.2f}",
            "similarity": SIMILARITY_METRIC,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label_status_counts": label_status_counts,
        "provisional": label_status_counts["gold"] == 0,
        "record_count": len(pairs),
        "split_counts": split_counts,
        "metrics": {mode: report_for_mode.model_dump(mode="json") for mode, report_for_mode in metrics.items()},
    }

    out.mkdir(parents=True, exist_ok=True)
    out_path = out / f"{PROMPT_VERSION}__{split}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path

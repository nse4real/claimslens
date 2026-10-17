"""Dev-only evaluation runner for validated LLM extraction."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.evals.scorer import FUZZY_THRESHOLD, SCORER_VERSION, SIMILARITY_METRIC, score_records
from src.extraction.llm.extractor import extract_with_llm
from src.ingestion.pipeline import ingest_folder
from src.llm.gateway import MODEL_ID, AnthropicGateway, Gateway

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "corpus" / "notifications_manifest.json"
DEFAULT_OUT_DIR = ROOT / "evals" / "results"

PROMPT_VERSION = "llm-extract-v1"
EXTRACTOR_VERSION = "llm-extract-v1"
HOLDOUT_MESSAGE = "holdout is not scored by the LLM runner"
DEFAULT_MAX_CALLS = 400
MODEL_LIST_PRICE_GBP_PER_TOKEN: dict[str, Decimal] | None = None


def _estimated_cost(input_tokens: int, output_tokens: int) -> str | None:
    if MODEL_LIST_PRICE_GBP_PER_TOKEN is None:
        return None
    cost = (
        input_tokens * MODEL_LIST_PRICE_GBP_PER_TOKEN["input"]
        + output_tokens * MODEL_LIST_PRICE_GBP_PER_TOKEN["output"]
    )
    return format(cost, "f")


def run_llm_dev(
    split: str = "dev",
    out_dir: Path | str | None = None,
    gateway: Gateway | None = None,
    max_calls: int = DEFAULT_MAX_CALLS,
) -> Path:
    if split != "dev":
        raise ValueError(HOLDOUT_MESSAGE)
    out = Path(out_dir) if out_dir is not None else DEFAULT_OUT_DIR
    active_gateway = gateway if gateway is not None else AnthropicGateway(max_calls=max_calls)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pairs = []
    label_status_counts = {"gold": 0, "single": 0}
    split_counts = {"dev": 0, "holdout": 0}
    schema_version = None
    calls = 0
    retries = 0
    input_tokens = 0
    output_tokens = 0
    failures = []

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
        result = extract_with_llm(documents, active_gateway)
        pairs.append(
            (
                gold["record_id"],
                list(gold["tags"]),
                result.plain,
                gold["labels"]["extraction"],
            )
        )
        calls += result.calls
        retries += result.calls - 1
        input_tokens += result.usage.input_tokens
        output_tokens += result.usage.output_tokens
        if result.status == "failed":
            failures.append(
                {
                    "record_id": gold["record_id"],
                    "validation_errors": result.validation_errors,
                }
            )

    metrics = {mode: score_records(pairs, mode) for mode in ("exact", "fuzzy")}
    report = {
        "prompt_version": PROMPT_VERSION,
        "model_identifier": MODEL_ID,
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
        "metrics": {
            mode: report_for_mode.model_dump(mode="json")
            for mode, report_for_mode in metrics.items()
        },
        "temperature": 0,
        "calls": calls,
        "retries": retries,
        "failed_records": len(failures),
        "failures": failures,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "cost_gbp": _estimated_cost(input_tokens, output_tokens),
    }

    out.mkdir(parents=True, exist_ok=True)
    out_path = out / f"{PROMPT_VERSION}__{split}.json"
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out_path

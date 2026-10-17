from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SEED = 20261017
GENERATOR_VERSION = "1.0.0"
SUPPORTED_CONTRACT_COUNT = 10
AMBIGUITY_TYPES = {
    "A1": "hours_clause_conflict",
    "A2": "notice_term_mismatch",
    "A3": "currency_mismatch",
    "A4": "endorsement_reversal",
}
CEDENT_NAMES = {
    "CED-A": "Example Cedent A Ltd (fictional)",
    "CED-B": "Example Cedent B Ltd (fictional)",
    "CED-C": "Example Cedent C Ltd (fictional)",
    "CED-D": "Example Cedent D Ltd (fictional)",
}
CONTRACT_SPECS = [
    {
        "contract_id": "FICT-TRT-001",
        "placement_basis": "treaty",
        "structure_type": "excess_of_loss",
        "cedent": "CED-A",
    },
    {
        "contract_id": "FICT-TRT-002",
        "placement_basis": "treaty",
        "structure_type": "excess_of_loss",
        "cedent": "CED-A",
    },
    {
        "contract_id": "FICT-TRT-003",
        "placement_basis": "treaty",
        "structure_type": "excess_of_loss",
        "cedent": "CED-B",
    },
    {
        "contract_id": "FICT-TRT-004",
        "placement_basis": "treaty",
        "structure_type": "cat_xol",
        "cedent": "CED-B",
    },
    {
        "contract_id": "FICT-TRT-005",
        "placement_basis": "treaty",
        "structure_type": "quota_share",
        "cedent": "CED-A",
    },
    {
        "contract_id": "FICT-TRT-006",
        "placement_basis": "treaty",
        "structure_type": "quota_share",
        "cedent": "CED-B",
    },
    {
        "contract_id": "FICT-TRT-007",
        "placement_basis": "treaty",
        "structure_type": "surplus",
        "cedent": "CED-C",
    },
    {
        "contract_id": "FICT-TRT-008",
        "placement_basis": "treaty",
        "structure_type": "stop_loss",
        "cedent": "CED-C",
    },
    {
        "contract_id": "FICT-FAC-001",
        "placement_basis": "facultative",
        "structure_type": "excess_of_loss",
        "cedent": "CED-D",
    },
    {
        "contract_id": "FICT-FAC-002",
        "placement_basis": "facultative",
        "structure_type": "quota_share",
        "cedent": "CED-D",
    },
]
TWO_VERSION_IDS = ("FICT-TRT-001", "FICT-TRT-002", "FICT-TRT-005")
FIRST_VERSION_NOTICE_PERIODS = {
    "FICT-TRT-001": 30,
    "FICT-TRT-002": 30,
    "FICT-TRT-003": 45,
    "FICT-TRT-004": 30,
    "FICT-TRT-005": 30,
    "FICT-TRT-006": 21,
    "FICT-TRT-007": 30,
    "FICT-TRT-008": 60,
    "FICT-FAC-001": None,
    "FICT-FAC-002": 30,
}
SECOND_VERSION_NOTICE_PERIODS = {
    "FICT-TRT-001": 14,
    "FICT-TRT-002": 21,
    "FICT-TRT-005": 10,
}
LAYER_PROFILES = {
    "FICT-TRT-001": (
        ("L1", "GBP", "1000000.00", "5000000.00", "100"),
        ("L2", "GBP", "6000000.00", "10000000.00", "100"),
    ),
    "FICT-TRT-002": (
        ("L1", "USD", "500000.00", "2000000.00", "100"),
    ),
    "FICT-TRT-003": (
        ("L1", "GBP", "250000.00", "1000000.00", "100"),
        ("L2", "GBP", "1250000.00", "2000000.00", "100"),
    ),
    "FICT-TRT-004": (
        ("L1", "USD", "1000000.00", "5000000.00", "100"),
        ("L2", "USD", None, "7500000.00", "100"),
    ),
    "FICT-TRT-005": (
        ("L1", "EUR", None, "10000000.00", "50"),
    ),
    "FICT-TRT-006": (
        ("L1", "USD", None, "8000000.00", "75"),
    ),
    "FICT-TRT-007": (
        ("L1", "GBP", "100000.00", "3000000.00", "100"),
    ),
    "FICT-TRT-008": (
        ("L1", "GBP", "500000.00", "5000000.00", "100"),
    ),
    "FICT-FAC-001": (
        ("L1", "USD", "250000.00", "1000000.00", "100"),
    ),
    "FICT-FAC-002": (
        ("L1", "EUR", None, "4000000.00", "50"),
    ),
}
SECTION_TITLES = {
    "S1": "General conditions",
    "S2": "Loss occurrence",
    "S3": "Claims cooperation",
    "S4": "Exclusions",
    "S5": "Endorsements",
    "S6": "Event aggregation",
}
SECTION_ORDER = ("S1", "S2", "S3", "S4", "S5", "S6")
CLAUSE_LOCATIONS = {
    "C1": "page 2, paragraph 1",
    "C3": "page 2, paragraph 1",
    "C10": "page 3, paragraph 1",
    "C11": "page 3, paragraph 2",
    "C20": "page 4, paragraph 1",
    "C30": "page 2, paragraph 2",
    "C40": "page 5, paragraph 1",
    "C41": "page 6, paragraph 1",
}


def assign_cedents(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(contract.get("cedent") for contract in contracts)
    unknown = [cedent for cedent in counts if cedent not in CEDENT_NAMES]
    if unknown:
        raise ValueError(f"Unknown cedent assignment: {unknown[0]}")
    for cedent in CEDENT_NAMES:
        if counts[cedent] < 2:
            raise ValueError(f"{cedent} must have at least 2 contracts")
    return contracts


def choose_ambiguities(seed: int) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(seed)
    ambiguity_ids = list(AMBIGUITY_TYPES)
    while True:
        selections = [
            rng.sample(ambiguity_ids, rng.choice((2, 3)))
            for _ in CONTRACT_SPECS
        ]
        counts = Counter(
            ambiguity_id
            for selection in selections
            for ambiguity_id in selection
        )
        if all(counts[ambiguity_id] >= 3 for ambiguity_id in ambiguity_ids):
            break

    assignments: dict[str, list[dict[str, Any]]] = {}
    for spec, selection in zip(CONTRACT_SPECS, selections, strict=True):
        version_count = 2 if spec["contract_id"] in TWO_VERSION_IDS else 1
        assignments[spec["contract_id"]] = [
            {
                "ambiguity_id": ambiguity_id,
                "version_index": rng.randrange(version_count),
            }
            for ambiguity_id in selection
        ]
    return assignments


def money(amount: str, currency: str) -> dict[str, str]:
    return {"amount": amount, "currency": currency}


def build_layers(contract_id: str, version_index: int) -> list[dict[str, Any]]:
    profiles = LAYER_PROFILES[contract_id]
    if contract_id == "FICT-TRT-001" and version_index == 1:
        profiles = profiles[:1]
    year = 2024 + version_index
    layers = []
    for layer_id, currency, retention, limit, share in profiles:
        layers.append(
            {
                "layer_id": layer_id,
                "section_id": "S1",
                "currency": currency,
                "retention": money(retention, currency) if retention else None,
                "limit": money(limit, currency) if limit else None,
                "share_percent": share,
                "inception": f"{year}-01-01",
                "expiry": f"{year}-12-31",
            }
        )
    return layers


def make_clause(contract_id: str, clause_id: str, title: str, text: str) -> dict[str, str]:
    return {
        "clause_id": clause_id,
        "title": title,
        "text": text,
        "source_document_id": f"{contract_id}-wording",
        "location": CLAUSE_LOCATIONS[clause_id],
    }


def build_version(spec: dict[str, str], version_index: int) -> dict[str, Any]:
    contract_id = spec["contract_id"]
    if version_index == 0:
        label = "2024-01"
        effective_from = "2024-01-01"
        effective_to = "2025-01-01" if contract_id in TWO_VERSION_IDS else None
        period = FIRST_VERSION_NOTICE_PERIODS[contract_id]
        clause_id = "C1"
    else:
        label = "2025-01"
        effective_from = "2025-01-01"
        effective_to = None
        period = SECOND_VERSION_NOTICE_PERIODS[contract_id]
        clause_id = "C3"

    if contract_id == "FICT-FAC-001":
        notice_text = (
            "Notice shall be given promptly after the cedent's claims committee "
            "receives a loss advice."
        )
        notice_rule = {
            "trigger": "other",
            "trigger_description": (
                "Receipt of a loss advice by the cedent's claims committee."
            ),
            "period_days": None,
            "clause_id": clause_id,
        }
    else:
        notice_text = f"Notice of loss shall be given within {period} days."
        notice_rule = {
            "trigger": "loss_date",
            "period_days": period,
            "clause_id": clause_id,
        }

    notice_clause = make_clause(
        contract_id, clause_id, "Notice of loss", notice_text
    )
    return {
        "version_label": label,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "sections": [
            {
                "section_id": "S1",
                "title": SECTION_TITLES["S1"],
                "clauses": [notice_clause],
            }
        ],
        "layers": build_layers(contract_id, version_index),
        "notice_rules": [notice_rule],
    }


def add_clause(
    version: dict[str, Any], section_id: str, clause: dict[str, str]
) -> None:
    for section in version["sections"]:
        if section["section_id"] == section_id:
            section["clauses"].append(clause)
            return
    version["sections"].append(
        {
            "section_id": section_id,
            "title": SECTION_TITLES[section_id],
            "clauses": [clause],
        }
    )


def plant_ambiguity(
    spec: dict[str, str], version: dict[str, Any], ambiguity_id: str
) -> tuple[dict[str, str], dict[str, str] | None]:
    contract_id = spec["contract_id"]
    label = version["version_label"]
    statement = None

    if ambiguity_id == "A1":
        add_clause(
            version,
            "S2",
            make_clause(
                contract_id,
                "C10",
                "Loss occurrence",
                "A loss occurrence comprises all losses arising from one event "
                "during a continuous period of 72 hours.",
            ),
        )
        add_clause(
            version,
            "S6",
            make_clause(
                contract_id,
                "C11",
                "Event aggregation",
                "The event clause defines one event as all losses within 48 "
                "consecutive hours.",
            ),
        )
        location = f"version {label}; section S2; clause C10"
        description = (
            "The occurrence clause uses 72 hours while the event clause uses 48 hours."
        )
        authoritative_value = "72 hours"
        expected_effect = (
            "Gold labels must flag the hours conflict instead of selecting a single "
            "occurrence period."
        )
    elif ambiguity_id == "A2":
        rule = version["notice_rules"][0]
        period = rule["period_days"]
        if period is None:
            conflict_text = (
                "Notwithstanding the general conditions, notice of loss shall be "
                "given within 14 days of the loss date."
            )
            description = (
                "The claims cooperation clause sets 14 days while the general "
                "conditions require prompt notice."
            )
            authoritative_value = "Prompt notice after receipt by the claims committee"
        else:
            alternate = period + 7
            conflict_text = (
                "Notwithstanding the general conditions, notice of loss shall be "
                f"given within {alternate} days."
            )
            description = (
                f"The claims cooperation clause allows {alternate} days while the "
                f"general conditions allow {period} days."
            )
            authoritative_value = f"{period} days"
        add_clause(
            version,
            "S3",
            make_clause(
                contract_id,
                "C20",
                "Conflicting notice term",
                conflict_text,
            ),
        )
        location = f"version {label}; section S3; clause C20"
        expected_effect = (
            "triage: notice_deadline_missed must be null when the notice period is "
            "ambiguous."
        )
    elif ambiguity_id == "A3":
        layer = version["layers"][0]
        limit = layer["limit"]
        currency = layer["currency"]
        amount = limit["amount"]
        alternate_currency = {"GBP": "USD", "USD": "EUR", "EUR": "GBP"}[currency]
        add_clause(
            version,
            "S1",
            make_clause(
                contract_id,
                "C30",
                "Authoritative layer limit",
                f"The limit for layer {layer['layer_id']} is {currency} {amount} "
                "and that currency governs payment.",
            ),
        )
        statement = {
            "section_id": "S1",
            "ambiguity_id": "A3",
            "text": (
                f"The schedule records the layer {layer['layer_id']} limit as "
                f"{alternate_currency} {amount}."
            ),
        }
        location = f"version {label}; section S1; schedule statement A3"
        description = (
            f"The schedule states the layer {layer['layer_id']} limit in "
            f"{alternate_currency} while the clause states it in {currency}."
        )
        authoritative_value = f"{currency} {amount}"
        expected_effect = (
            f"Gold labels must use {currency} {amount} as the limit and flag the "
            "schedule currency conflict."
        )
    elif ambiguity_id == "A4":
        add_clause(
            version,
            "S4",
            make_clause(
                contract_id,
                "C40",
                "Computer-system exclusion",
                "Losses directly caused by unauthorised access to a computer system "
                "are excluded.",
            ),
        )
        add_clause(
            version,
            "S5",
            make_clause(
                contract_id,
                "C41",
                "Partial reversal endorsement",
                "Endorsement E1 returns cover for losses from unauthorised access at "
                "named offices, but does not state whether associated business "
                "interruption is included.",
            ),
        )
        location = f"version {label}; section S5; clause C41"
        description = (
            "The endorsement reverses the computer-system exclusion for named offices "
            "but leaves business interruption scope unclear."
        )
        authoritative_value = (
            "Named-office unauthorised access is covered; associated business "
            "interruption is unresolved"
        )
        expected_effect = (
            "Gold labels must mark the endorsement scope as ambiguous rather than "
            "removing the whole exclusion."
        )
    else:
        raise ValueError(f"Unknown ambiguity: {ambiguity_id}")

    record = {
        "ambiguity_id": ambiguity_id,
        "type": AMBIGUITY_TYPES[ambiguity_id],
        "location": location,
        "description": description,
        "authoritative_value": authoritative_value,
        "expected_effect": expected_effect,
    }
    return record, statement


def order_sections(version: dict[str, Any]) -> None:
    by_id = {section["section_id"]: section for section in version["sections"]}
    version["sections"] = [
        by_id[section_id] for section_id in SECTION_ORDER if section_id in by_id
    ]


def render_body(
    contract: dict[str, Any],
    cedent: str,
    statements: dict[str, list[dict[str, str]]],
) -> str:
    lines = [
        f"# {contract['contract_id']}",
        "",
        f"Cedent: {cedent} - {contract['cedent_name']}",
        "",
    ]
    for version in contract["versions"]:
        lines.extend([f"## Version {version['version_label']}", ""])
        version_statements = statements[version["version_label"]]
        for section in version["sections"]:
            lines.extend(
                [f"### {section['section_id']} {section['title']}", ""]
            )
            for clause in section["clauses"]:
                lines.extend([f"{clause['clause_id']}. {clause['text']}", ""])
            for statement in version_statements:
                if statement["section_id"] == section["section_id"]:
                    lines.extend(
                        [
                            f"#### Schedule statement {statement['ambiguity_id']}",
                            "",
                            statement["text"],
                            "",
                        ]
                    )
    return "\n".join(lines).rstrip() + "\n"


def build_contract(
    spec: dict[str, str], assignments: list[dict[str, Any]]
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    version_count = 2 if spec["contract_id"] in TWO_VERSION_IDS else 1
    versions = [build_version(spec, index) for index in range(version_count)]
    statements = {version["version_label"]: [] for version in versions}
    ambiguity_records = []
    for assignment in assignments:
        version = versions[assignment["version_index"]]
        record, statement = plant_ambiguity(
            spec, version, assignment["ambiguity_id"]
        )
        ambiguity_records.append(record)
        if statement is not None:
            statements[version["version_label"]].append(statement)
    for version in versions:
        order_sections(version)

    contract = {
        "contract_id": spec["contract_id"],
        "placement_basis": spec["placement_basis"],
        "structure_type": spec["structure_type"],
        "cedent_name": CEDENT_NAMES[spec["cedent"]],
        "versions": versions,
    }
    body = render_body(contract, spec["cedent"], statements)
    return contract, body, ambiguity_records


def render_wording(contract: dict[str, Any], body: str) -> str:
    front_matter = yaml.safe_dump(
        contract,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    return f"---\n{front_matter}---\n\n{body}"


def generate_corpus(
    out: str | Path = "data/corpus",
    seed: int = DEFAULT_SEED,
    contracts: int = SUPPORTED_CONTRACT_COUNT,
) -> dict[str, Any]:
    if contracts != SUPPORTED_CONTRACT_COUNT:
        raise ValueError("--contracts must be exactly 10")
    assign_cedents(CONTRACT_SPECS)
    assignments = choose_ambiguities(seed)
    output_dir = Path(out)
    wording_dir = output_dir / "wordings"
    wording_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for spec in CONTRACT_SPECS:
        contract, body, ambiguity_records = build_contract(
            spec, assignments[spec["contract_id"]]
        )
        relative_path = f"wordings/{spec['contract_id']}.md"
        content = render_wording(contract, body)
        (output_dir / relative_path).write_text(
            content, encoding="utf-8", newline="\n"
        )
        entries.append(
            {
                "contract_id": spec["contract_id"],
                "cedent": spec["cedent"],
                "file": relative_path,
                "ambiguities": ambiguity_records,
            }
        )

    manifest = {
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "contracts": entries,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate fictional contract wordings.")
    parser.add_argument("--contracts", type=int, default=SUPPORTED_CONTRACT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default="data/corpus")
    args = parser.parse_args(argv)
    if args.contracts != SUPPORTED_CONTRACT_COUNT:
        parser.error("--contracts must be exactly 10")
    generate_corpus(out=args.out, seed=args.seed, contracts=args.contracts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

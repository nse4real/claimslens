import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from data.generators.notifications import (
    ADVERSARIAL_COUNTS,
    ADVERSARIAL_TAGS,
    ATTACHMENT_LAYOUTS,
    DEFAULT_SEED,
    DIFFERENCE_SEED,
    EXPECTED_SPLIT_COUNTS,
    EXTRACTION_FIELDS,
    GoldOverwriteError,
    INJECTION_TEXTS,
    LABEL_SYNONYMS,
    NON_ADVERSARIAL_COUNTS,
    REFERENCE_DATE,
    SUPPORTED_COUNT,
    TAG_COUNTS,
    build_scenarios,
    field_in_document,
    field_is_present,
    field_values,
    generate_corpus,
    load_contracts,
    render_attachment,
    rendering_plan,
)
from src.evals.runner import run_baseline

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "data" / "generators" / "notifications.py"
MANIFEST_PATH = ROOT / "data" / "corpus" / "notifications_manifest.json"
SCHEMA_PATH = ROOT / "evals" / "schemas" / "gold_record.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
DENIED_REAL_COMPANY_NAMES = ("Guy Carpenter", "Marsh", "Lloyd's")
NO_MATCH_TAGS = {"wrong_cedent", "out_of_scope"}


def run_generator(*arguments):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(GENERATOR), *map(str, arguments)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def load_gold(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def rendered_text(record):
    return "\n".join(
        (ROOT / document["corpus_path"]).read_text(encoding="utf-8")
        for document in record["source_documents"]
    )


def email_text(record_id):
    return (ROOT / "data" / "corpus" / "notifications" / record_id / "email.eml").read_text(
        encoding="utf-8"
    )


def attachment_text(record_id):
    return (
        ROOT
        / "data"
        / "corpus"
        / "notifications"
        / record_id
        / "attachments"
        / "loss_advice.txt"
    ).read_text(encoding="utf-8")


def expected_deadline(scenario):
    if scenario["primary_tag"] in NO_MATCH_TAGS:
        return None
    if any(item["ambiguity_id"] == "A2" for item in scenario["ambiguities"]):
        return None
    if {"date_of_loss", "date_of_notification"} & set(scenario["removed_fields"]):
        return None
    rule = scenario["version"].notice_rules[0]
    if rule.period_days is None:
        return None
    return scenario["sent_date"] > scenario["loss_date"] + timedelta(days=rule.period_days)


def ambiguity_note(record, ambiguity_id, block="matching"):
    matches = [
        note
        for note in record["label_notes"]
        if note["block"] == block and note["note"].startswith(f"{ambiguity_id} ")
    ]
    assert len(matches) == 1
    return matches[0]


@pytest.fixture(scope="session")
def contract_data():
    return load_contracts()


@pytest.fixture(scope="session")
def contracts_by_id(contract_data):
    return {item["contract"].contract_id: item for item in contract_data}


@pytest.fixture(scope="session")
def scenarios(contract_data):
    return build_scenarios(contract_data, seed=DEFAULT_SEED)


@pytest.fixture(scope="session")
def scenarios_by_id(scenarios):
    return {item["record_id"]: item for item in scenarios}


@pytest.fixture(scope="session")
def manifest():
    return load_gold(MANIFEST_PATH)


@pytest.fixture(scope="session")
def gold_records(manifest):
    return {
        entry["record_id"]: load_gold(ROOT / entry["gold_path"])
        for entry in manifest["records"]
    }


def test_01_default_generator_writes_225_folders_gold_records_and_manifest(tmp_path):
    result = generate_corpus(out=tmp_path)

    notification_root = tmp_path / "data" / "corpus" / "notifications"
    folders = sorted(path for path in notification_root.iterdir() if path.is_dir())
    assert len(folders) == SUPPORTED_COUNT
    assert [path.name for path in folders] == [f"GN-{1001 + index:04d}" for index in range(225)]
    assert all((path / "email.eml").is_file() for path in folders)
    assert all((path / "attachments" / "loss_advice.txt").is_file() for path in folders)
    gold_files = list((tmp_path / "evals" / "gold" / "records").glob("GN-*.json"))
    assert len(gold_files) == SUPPORTED_COUNT
    assert (tmp_path / "data" / "corpus" / "notifications_manifest.json").is_file()
    assert result["seed"] == DEFAULT_SEED
    assert result["counts"]["total"] == SUPPORTED_COUNT


def test_02_every_gold_record_validates_against_the_b6_schema(gold_records):
    assert len(gold_records) == SUPPORTED_COUNT
    for record_id, record in gold_records.items():
        errors = list(VALIDATOR.iter_errors(record))
        assert not errors, (record_id, [error.message for error in errors])


def test_03_split_counts_are_exactly_158_dev_and_67_holdout(gold_records):
    counts = Counter(record["split"] for record in gold_records.values())
    assert dict(counts) == EXPECTED_SPLIT_COUNTS


def test_04_every_tag_appears_in_both_splits(gold_records):
    for tag in TAG_COUNTS:
        splits = {
            record["split"]
            for record in gold_records.values()
            if tag in record["tags"]
        }
        assert splits == {"dev", "holdout"}


def test_05_adversarial_counts_are_exact_and_never_combined(gold_records):
    counts = Counter(
        tag
        for record in gold_records.values()
        for tag in record["tags"]
        if tag in ADVERSARIAL_TAGS
    )
    assert dict(counts) == ADVERSARIAL_COUNTS
    assert sum(counts.values()) == 30
    for record in gold_records.values():
        assert len(set(record["tags"]) & set(ADVERSARIAL_TAGS)) <= 1


def test_06_primary_non_adversarial_tag_counts_match_the_plan(gold_records):
    counts = Counter(
        tag
        for record in gold_records.values()
        for tag in record["tags"]
        if tag in NON_ADVERSARIAL_COUNTS
    )
    assert dict(counts) == NON_ADVERSARIAL_COUNTS
    assert sum(counts.values()) == 195


def test_07_every_correct_match_exists_in_the_b7_manifest_and_b5_model(
    gold_records, scenarios_by_id, contracts_by_id
):
    for record_id, record in gold_records.items():
        scenario = scenarios_by_id[record_id]
        matching = record["labels"]["matching"]
        if scenario["primary_tag"] in NO_MATCH_TAGS:
            continue
        assert matching["correct_contract_id"] == scenario["contract_id"]
        assert matching["correct_version_label"] == scenario["version_label"]
        assert matching["correct_layer_id"] == scenario["layer_id"]
        data = contracts_by_id[matching["correct_contract_id"]]
        version = next(
            item
            for item in data["contract"].versions
            if item.version_label == matching["correct_version_label"]
        )
        assert matching["correct_layer_id"] in {layer.layer_id for layer in version.layers}


def test_08_every_scenario_loss_date_is_inside_the_version_and_layer(scenarios):
    for scenario in scenarios:
        loss_date = scenario["loss_date"]
        version = scenario["version"]
        layer = scenario["layer"]
        assert version.effective_from <= loss_date
        if version.effective_to is not None:
            assert loss_date < version.effective_to
        assert layer.inception <= loss_date <= layer.expiry
        if scenario["secondary_choice"] is not None:
            secondary = scenario["secondary_choice"]
            assert secondary["version"].effective_from <= loss_date
            if secondary["version"].effective_to is not None:
                assert loss_date < secondary["version"].effective_to
            assert secondary["layer"].inception <= loss_date <= secondary["layer"].expiry


def test_09_every_qa_clause_id_exists_in_the_matched_version(gold_records, scenarios_by_id):
    for record_id, record in gold_records.items():
        qa = record["labels"]["qa"]
        if qa is None:
            continue
        clause_ids = {
            clause.clause_id
            for section in scenarios_by_id[record_id]["version"].sections
            for clause in section.clauses
        }
        for question in qa:
            assert question["required_clause_ids"]
            assert set(question["required_clause_ids"]) <= clause_ids


def test_10_notice_deadline_labels_follow_periods_and_precedence(
    gold_records, scenarios_by_id
):
    for record_id, record in gold_records.items():
        scenario = scenarios_by_id[record_id]
        triage = record["labels"]["triage"]
        expected = expected_deadline(scenario)
        if triage is None:
            assert scenario["primary_tag"] == "out_of_scope"
            continue
        assert triage["notice_deadline_missed"] == expected
        assert ("late_notice" in record["tags"]) == bool(expected)


def test_11_every_source_document_exists_and_document_ids_are_unique(gold_records):
    for record in gold_records.values():
        document_ids = [item["document_id"] for item in record["source_documents"]]
        assert len(document_ids) == len(set(document_ids))
        for document in record["source_documents"]:
            path = ROOT / document["corpus_path"]
            assert path.is_file(), path
            if document["document_type"] == "other":
                assert path.suffix == ".txt"
            else:
                assert document["document_type"] == "email"
                assert path.name == "email.eml"


def test_12_every_qa_label_note_references_an_existing_question(gold_records):
    for record in gold_records.values():
        question_ids = {item["question_id"] for item in record["labels"]["qa"] or []}
        for note in record["label_notes"]:
            if note["block"] == "qa":
                assert note["item_id"] in question_ids


def test_13_missing_fields_have_null_or_empty_labels_and_missing_information_notes(
    gold_records, scenarios_by_id
):
    for record_id, record in gold_records.items():
        scenario = scenarios_by_id[record_id]
        if scenario["primary_tag"] != "missing_fields":
            continue
        removed = scenario["removed_fields"]
        assert 1 <= len(removed) <= 2
        extraction = record["labels"]["extraction"]
        assert record["labels"]["triage"]["missing_information"] == list(removed)
        for field in removed:
            assert extraction[field] == ([] if field == "treaty_references" else None)
            note = next(
                item
                for item in record["label_notes"]
                if item["block"] == "extraction" and item["item_id"] == field
            )
            assert note["certain"] is True
            assert field not in extraction["uncertain_fields"]


def test_14_wrong_cedent_records_cannot_match_any_manifest_contract(
    gold_records, scenarios_by_id, contract_data
):
    known_cedents = {item["contract"].cedent_name for item in contract_data}
    for record_id, record in gold_records.items():
        scenario = scenarios_by_id[record_id]
        if scenario["primary_tag"] != "wrong_cedent":
            continue
        assert record["labels"]["matching"]["expected_no_match"] is True
        assert scenario["cedent"] not in known_cedents
        for data in contract_data:
            assert not (
                data["contract"].cedent_name == scenario["cedent"]
                and data["contract"].contract_id == scenario["contract_id"]
            )
        assert scenario["cedent"] in rendered_text(record)


def test_15_contradictory_documents_have_ambiguous_null_amounts(
    gold_records, scenarios_by_id
):
    for record_id, record in gold_records.items():
        if scenarios_by_id[record_id]["primary_tag"] != "contradictory_documents":
            continue
        extraction = record["labels"]["extraction"]
        assert extraction["estimated_loss_amount"] is None
        assert extraction["uncertain_fields"] == ["estimated_loss_amount"]
        note = next(
            item
            for item in record["label_notes"]
            if item["block"] == "extraction" and item["item_id"] == "estimated_loss_amount"
        )
        assert note["certain"] is False
        assert "ambiguous" in note["note"]
        assert email_text(record_id) != attachment_text(record_id)


def test_16_injection_text_is_rendered_without_changing_fact_based_labels(
    gold_records, scenarios_by_id
):
    for record_id, record in gold_records.items():
        scenario = scenarios_by_id[record_id]
        if scenario["primary_tag"] != "injection":
            continue
        rendered = rendered_text(record)
        for instruction in scenario["injection_texts"]:
            assert instruction in rendered
        triage = record["labels"]["triage"]
        if triage["priority"] == "urgent":
            assert expected_deadline(scenario) is True or scenario["injection_facts_urgent"]
        amount = record["labels"]["extraction"]["estimated_loss_amount"]
        assert amount == {
            "amount": format(scenario["estimated_amount"], ".2f"),
            "currency": scenario["stated_currency"],
        }


def test_17_near_duplicates_match_an_original_and_differ_by_under_one_percent(
    gold_records, scenarios_by_id
):
    near_duplicates = [
        scenario
        for scenario in scenarios_by_id.values()
        if scenario["primary_tag"] == "near_duplicate"
    ]
    assert len(near_duplicates) == ADVERSARIAL_COUNTS["near_duplicate"]
    for scenario in near_duplicates:
        original = scenarios_by_id[scenario["near_duplicate_of"]]
        assert scenario["record_id"] != original["record_id"]
        assert scenario["contract_id"] == original["contract_id"]
        assert scenario["loss_date"] == original["loss_date"]
        difference = abs(scenario["estimated_amount"] - original["estimated_amount"])
        assert difference / original["estimated_amount"] < Decimal("0.01")
        assert gold_records[scenario["record_id"]]["labels"]["extraction"]["estimated_loss_amount"]["amount"] == format(scenario["estimated_amount"], ".2f")


def test_18_two_runs_with_the_same_seed_produce_identical_file_hashes(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_corpus(out=first, seed=DEFAULT_SEED)
    generate_corpus(out=second, seed=DEFAULT_SEED)

    first_hashes = file_hashes(first)
    assert first_hashes == file_hashes(second)
    assert len(first_hashes) == 676


def test_19_a_different_seed_changes_at_least_one_notification_gold_label(tmp_path):
    default_dir = tmp_path / "default"
    alternate_dir = tmp_path / "alternate"
    generate_corpus(out=default_dir, seed=DEFAULT_SEED)
    generate_corpus(out=alternate_dir, seed=DIFFERENCE_SEED)

    changed = []
    for index in range(SUPPORTED_COUNT):
        record_id = f"GN-{1001 + index:04d}"
        default = load_gold(default_dir / "evals" / "gold" / "records" / f"{record_id}.json")
        alternate = load_gold(alternate_dir / "evals" / "gold" / "records" / f"{record_id}.json")
        if default["labels"] != alternate["labels"]:
            changed.append(record_id)
    assert changed


def test_20_count_cli_accepts_only_225(tmp_path):
    for count in (224, 226):
        out = tmp_path / f"invalid-{count}"
        result = run_generator("--count", count, "--out", out)
        assert result.returncode != 0
        assert "--count must be exactly 225" in result.stderr
        assert not out.exists()

    valid_out = tmp_path / "valid"
    result = run_generator("--count", 225, "--seed", DEFAULT_SEED, "--out", valid_out)
    assert result.returncode == 0, result.stderr
    assert len(list((valid_out / "data" / "corpus" / "notifications").iterdir())) == 225


def test_21_no_notification_text_contains_a_denied_real_company_name(gold_records):
    for record in gold_records.values():
        text = rendered_text(record).casefold()
        for denied_name in DENIED_REAL_COMPANY_NAMES:
            assert denied_name.casefold() not in text


def test_22_every_email_from_and_to_address_uses_example_test(gold_records):
    for record_id in gold_records:
        message = BytesParser(policy=policy.default).parsebytes(email_text(record_id).encode("utf-8"))
        addresses = getaddresses([str(message["From"]), str(message["To"])])
        assert len(addresses) == 2
        for _display_name, address in addresses:
            assert address.rsplit("@", 1)[1] == "example.test"


def test_23_manifest_counts_equal_counts_recomputed_from_records(manifest):
    split_counts = Counter(entry["split"] for entry in manifest["records"])
    tag_counts = Counter(tag for entry in manifest["records"] for tag in entry["tags"])
    expected = {
        "total": len(manifest["records"]),
        "splits": {split: split_counts[split] for split in ("dev", "holdout")},
        "tags": {tag: tag_counts[tag] for tag in TAG_COUNTS},
    }
    assert manifest["counts"] == expected
    assert set(manifest) == {"seed", "generator_version", "reference_date", "counts", "records"}


def test_24_all_records_are_single_labelled_by_the_generator(gold_records):
    for record in gold_records.values():
        provenance = record["provenance"]
        assert provenance["label_status"] == "single"
        assert provenance["labeller"] == "generator"
        assert provenance["second_labeller_agreed"] is None
        assert provenance["labelled_on"] == REFERENCE_DATE
        assert provenance["generator_seed"] == DEFAULT_SEED


def test_25_every_no_match_record_has_null_correct_fields_and_no_alternatives(
    gold_records, scenarios_by_id
):
    for record_id, record in gold_records.items():
        scenario = scenarios_by_id[record_id]
        matching = record["labels"]["matching"]
        if scenario["primary_tag"] in NO_MATCH_TAGS:
            assert matching["expected_no_match"] is True
            assert matching["correct_contract_id"] is None
            assert matching["correct_version_label"] is None
            assert matching["correct_layer_id"] is None
            assert matching["alternatives"] == []
            assert record["labels"]["qa"] is None
            assert record["labels"]["drafting"] is None
            if scenario["primary_tag"] == "out_of_scope":
                assert record["labels"]["triage"] is None
        else:
            assert matching["expected_no_match"] is False


def test_26_every_ambiguity_type_is_exercised_with_version_scoped_expected_effects(
    gold_records, scenarios_by_id
):
    exercised = set()
    isolation_checked = False
    for record_id, scenario in scenarios_by_id.items():
        record = gold_records[record_id]
        applicable_ids = {item["ambiguity_id"] for item in scenario["ambiguities"]}
        exercised |= applicable_ids
        for ambiguity in scenario["ambiguities"]:
            ambiguity_id = ambiguity["ambiguity_id"]
            if ambiguity_id == "A1":
                note = ambiguity_note(record, "A1")
                assert note["certain"] is False
                assert "C10" in note["note"] and "C11" in note["note"]
                assert "not resolved" in note["note"]
            elif ambiguity_id == "A2":
                note = ambiguity_note(record, "A2", block="qa")
                assert note["certain"] is True
                assert record["labels"]["triage"]["notice_deadline_missed"] is None
                question = record["labels"]["qa"][0]
                assert len(question["required_clause_ids"]) == 2
                assert "conflict" in question["expected_answer_summary"].casefold()
            elif ambiguity_id == "A3":
                note = ambiguity_note(record, "A3")
                assert note["certain"] is True
                assert ambiguity["authoritative_value"] in note["note"]
                assert len(record["labels"]["qa"]) == 1
            elif ambiguity_id == "A4":
                note = ambiguity_note(record, "A4")
                assert note["certain"] is False
                assert "business interruption" in note["note"]
                assert "unresolved" in note["note"]
        for ambiguity in scenario["contract_entry"]["ambiguities"]:
            if ambiguity["ambiguity_id"] not in applicable_ids:
                isolation_checked = True
                assert not any(
                    note["note"].startswith(f"{ambiguity['ambiguity_id']} ")
                    for note in record["label_notes"]
                )
        expected_uncertain = [
            note["item_id"]
            for note in record["label_notes"]
            if note["block"] == "extraction" and not note["certain"]
        ]
        assert record["labels"]["extraction"]["uncertain_fields"] == expected_uncertain
    assert exercised == {"A1", "A2", "A3", "A4"}
    assert isolation_checked


def test_27_every_qa_question_is_the_answerable_notice_question_with_required_clauses(
    gold_records, scenarios_by_id
):
    for record_id, record in gold_records.items():
        qa = record["labels"]["qa"]
        if qa is None:
            continue
        assert len(qa) == 1
        question = qa[0]
        scenario = scenarios_by_id[record_id]
        rule = scenario["version"].notice_rules[0]
        a2 = next(
            (item for item in scenario["ambiguities"] if item["ambiguity_id"] == "A2"),
            None,
        )
        expected_clauses = [rule.clause_id]
        if a2 is not None:
            expected_clauses.append("C20")
        assert question["question"] == "What is the notice requirement for this loss?"
        assert question["answerable"] is True
        assert question["required_clause_ids"] == expected_clauses
        if a2 is not None:
            assert a2["description"] in question["expected_answer_summary"]
        elif rule.period_days is not None:
            assert f"within {rule.period_days} days" in question["expected_answer_summary"]
        else:
            assert question["expected_answer_summary"] == rule.trigger_description


def test_28_per_tag_split_allocation_matches_rule_and_near_duplicate_groups_are_atomic(
    gold_records, scenarios_by_id
):
    for tag in TAG_COUNTS:
        tagged = [record for record in gold_records.values() if tag in record["tags"]]
        dev_count = sum(record["split"] == "dev" for record in tagged)
        assert dev_count == round(Decimal("0.7") * len(tagged))
    groups = defaultdict(list)
    for record_id, scenario in scenarios_by_id.items():
        if scenario["near_duplicate_group"]:
            groups[scenario["near_duplicate_group"]].append(record_id)
    assert len(groups) == ADVERSARIAL_COUNTS["near_duplicate"]
    for record_ids in groups.values():
        assert len(record_ids) == 2
        assert len({gold_records[record_id]["split"] for record_id in record_ids}) == 1


def test_29_injection_categories_a_to_e_have_required_coverage_and_locations(
    gold_records, scenarios_by_id
):
    category_records = defaultdict(set)
    for record_id, scenario in scenarios_by_id.items():
        if scenario["primary_tag"] != "injection":
            continue
        email = email_text(record_id)
        attachment = attachment_text(record_id)
        for category in scenario["injection_categories"]:
            category_records[category].add(record_id)
            instruction = INJECTION_TEXTS[category]
            if category == "b":
                assert instruction in attachment
            else:
                assert instruction in email
    for category in ("a", "b", "c", "d", "e"):
        assert len(category_records[category]) >= 2


def test_30_missing_treaties_are_empty_and_removed_notification_dates_are_absent(
    gold_records, scenarios_by_id
):
    for record_id, record in gold_records.items():
        scenario = scenarios_by_id[record_id]
        if scenario["primary_tag"] != "missing_fields":
            continue
        removed = set(scenario["removed_fields"])
        rendered = rendered_text(record)
        if "treaty_references" in removed:
            assert record["labels"]["extraction"]["treaty_references"] == []
            assert scenario["contract_id"] not in rendered
        if "date_of_notification" in removed:
            message = BytesParser(policy=policy.default).parsebytes(
                email_text(record_id).encode("utf-8")
            )
            assert "Date" not in message
            sent_date = scenario["sent_date"]
            rendered_dates = {
                sent_date.isoformat(),
                sent_date.strftime("%d/%m/%Y"),
                sent_date.strftime("%d %b %Y"),
                sent_date.strftime("%Y/%m/%d"),
            }
            assert not any(value in rendered for value in rendered_dates)


def head_file_bytes(relative_path):
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8")
    return result.stdout


def head_json(relative_path):
    return json.loads(head_file_bytes(relative_path))


def document_text(record_id, document):
    return email_text(record_id) if document == "email" else attachment_text(record_id)


def test_31_regeneration_leaves_every_single_labelled_gold_record_byte_identical_to_head(tmp_path):
    generate_corpus(out=tmp_path, seed=DEFAULT_SEED)
    for index in range(SUPPORTED_COUNT):
        record_id = f"GN-{1001 + index:04d}"
        relative = f"evals/gold/records/{record_id}.json"
        expected = head_file_bytes(relative)
        if json.loads(expected)["provenance"]["label_status"] != "single":
            continue
        assert (ROOT / relative).read_bytes() == expected
        assert (tmp_path / relative).read_bytes() == expected


def test_32_regeneration_leaves_manifest_and_per_tag_counts_unchanged(tmp_path):
    expected = {
        "total": 225,
        "splits": {"dev": 158, "holdout": 67},
        "tags": dict(TAG_COUNTS),
    }
    assert head_json("data/corpus/notifications_manifest.json")["counts"] == expected
    assert load_gold(MANIFEST_PATH)["counts"] == expected
    assert generate_corpus(out=tmp_path, seed=DEFAULT_SEED)["counts"] == expected


def test_33_every_label_synonym_appears_at_least_five_times(gold_records):
    corpus_text = "\n".join(
        email_text(record_id) + "\n" + attachment_text(record_id)
        for record_id in gold_records
    ).casefold()
    for synonyms in LABEL_SYNONYMS.values():
        for synonym in synonyms:
            assert corpus_text.count(synonym.casefold()) >= 5, synonym


def test_34_each_attachment_layout_appears_evenly_and_at_least_forty_times(scenarios):
    layouts = {scenario["record_id"]: rendering_plan(scenario)["layout"] for scenario in scenarios}
    counts = Counter(layouts.values())
    assert set(counts) == set(ATTACHMENT_LAYOUTS)
    assert all(count >= 40 for count in counts.values())
    assert max(counts.values()) - min(counts.values()) <= 1
    for scenario in scenarios:
        assert attachment_text(scenario["record_id"]) == render_attachment(scenario)


def test_35_at_least_twenty_records_have_a_field_in_only_one_document(scenarios):
    uneven_records = 0
    for scenario in scenarios:
        record_id = scenario["record_id"]
        plan = rendering_plan(scenario)
        values = {
            document: field_values(scenario, plan, document)
            for document in ("email", "attachment")
        }
        uneven = False
        for field in EXTRACTION_FIELDS:
            if not field_is_present(scenario, field):
                continue
            placement = plan["placements"][field]
            if placement == "both":
                continue
            uneven = True
            assert values[placement][field] in document_text(record_id, placement)
        uneven_records += uneven
    assert uneven_records >= 20


def test_36_cedent_and_treaty_are_present_unless_deliberately_removed(scenarios):
    for scenario in scenarios:
        record_id = scenario["record_id"]
        combined = (email_text(record_id) + "\n" + attachment_text(record_id)).casefold()
        removed = set(scenario["removed_fields"])
        if "cedent_name" not in removed:
            assert scenario["cedent"].casefold() in combined
        if "treaty_references" not in removed:
            assert scenario["contract_id"].casefold() in combined
            if scenario["secondary_choice"] is not None:
                secondary_id = scenario["secondary_choice"]["data"]["contract"].contract_id
                assert secondary_id.casefold() in combined


def test_37_at_least_twenty_percent_of_target_dates_are_non_iso(scenarios):
    date_values = []
    for scenario in scenarios:
        if scenario["primary_tag"] not in {"messy", "forwarded_chain", "scanned_style"}:
            continue
        plan = rendering_plan(scenario)
        for field in ("date_of_loss", "date_of_notification"):
            if not field_is_present(scenario, field):
                continue
            document = "email" if field_in_document(plan, field, "email") else "attachment"
            value = field_values(scenario, plan, document)[field]
            assert value in document_text(scenario["record_id"], document)
            expected = scenario["loss_date"] if field == "date_of_loss" else scenario["sent_date"]
            date_values.append((value, expected.isoformat()))
    assert date_values
    assert sum(value != iso_value for value, iso_value in date_values) / len(date_values) >= 0.20


def test_38_at_least_twenty_records_use_amount_separators_or_suffixes(scenarios):
    formatted_records = set()
    for scenario in scenarios:
        if scenario["primary_tag"] not in {"messy", "forwarded_chain"}:
            continue
        plan = rendering_plan(scenario)
        for field in ("estimated_loss_amount", "paid_to_date", "outstanding_reserve"):
            if not field_is_present(scenario, field) or plan["amount_styles"][field] == 3:
                continue
            document = "email" if field_in_document(plan, field, "email") else "attachment"
            value = field_values(scenario, plan, document)[field]
            assert value in document_text(scenario["record_id"], document)
            number = value.split(" ", 1)[1]
            assert re.search(r"\d[, ]\d{3}", number) or re.search(r"\d\.\d{2}m(?:\s|$)", number)
            formatted_records.add(scenario["record_id"])
    assert len(formatted_records) >= 20


def test_39_every_forwarded_chain_has_a_safe_quoted_trap_date(scenarios):
    for scenario in scenarios:
        if scenario["primary_tag"] != "forwarded_chain":
            continue
        match = re.search(
            r"^On (\d{1,2} [A-Za-z]{3} \d{4}) 09:00 \+0000, .+ wrote:$",
            email_text(scenario["record_id"]),
            re.MULTILINE,
        )
        assert match is not None
        quoted_date = datetime.strptime(match.group(1), "%d %b %Y").date()
        assert quoted_date < scenario["sent_date"]
        assert abs((quoted_date - scenario["sent_date"]).days) >= 3
        assert quoted_date != scenario["loss_date"]


def test_40_forwarded_top_message_date_equals_gold_notification_date(
    gold_records, scenarios_by_id
):
    for record_id, scenario in scenarios_by_id.items():
        if scenario["primary_tag"] != "forwarded_chain":
            continue
        message = BytesParser(policy=policy.default).parsebytes(
            email_text(record_id).encode("utf-8")
        )
        assert "Date" in message
        top_date = parsedate_to_datetime(str(message["Date"])).date().isoformat()
        assert top_date == scenario["sent_date"].isoformat()
        assert top_date == gold_records[record_id]["labels"]["extraction"]["date_of_notification"]


def test_41_two_regenerations_have_identical_email_and_attachment_hashes(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_corpus(out=first, seed=DEFAULT_SEED)
    generate_corpus(out=second, seed=DEFAULT_SEED)

    def rendered_hashes(root):
        notifications = root / "data" / "corpus" / "notifications"
        return {
            path.relative_to(notifications).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in notifications.rglob("*")
            if path.is_file()
        }

    assert rendered_hashes(first) == rendered_hashes(second)
    assert len(rendered_hashes(first)) == 450


def test_42_holdout_gold_files_remain_byte_identical(gold_records):
    holdout_ids = {
        record_id for record_id, record in gold_records.items() if record["split"] == "holdout"
    }
    assert len(holdout_ids) == 67
    for record_id in holdout_ids:
        relative = f"evals/gold/records/{record_id}.json"
        assert (ROOT / relative).read_bytes() == head_file_bytes(relative)


def test_43_all_adversarial_records_keep_tags_and_marker_text(
    gold_records, scenarios_by_id
):
    adversarial = []
    for record_id, record in gold_records.items():
        if not set(record["tags"]) & set(ADVERSARIAL_TAGS):
            continue
        adversarial.append(record_id)
        relative = f"evals/gold/records/{record_id}.json"
        assert record["tags"] == head_json(relative)["tags"]
        scenario = scenarios_by_id[record_id]
        if scenario["primary_tag"] == "injection":
            rendered = rendered_text(record)
            for instruction in scenario["injection_texts"]:
                assert instruction in rendered
        elif scenario["primary_tag"] == "contradictory_documents":
            plan = rendering_plan(scenario)
            email_amount = field_values(scenario, plan, "email")["estimated_loss_amount"]
            attachment_amount = field_values(scenario, plan, "attachment")["estimated_loss_amount"]
            assert email_amount != attachment_amount
            assert email_amount in email_text(record_id)
            assert attachment_amount in attachment_text(record_id)
        elif scenario["primary_tag"] == "out_of_scope":
            assert "outside claims handling" in email_text(record_id)
        elif scenario["primary_tag"] == "near_duplicate":
            assert scenario["near_duplicate_of"] in gold_records
    assert len(adversarial) == 30


def test_44_b10_runner_writes_provisional_v2_results_with_new_name(tmp_path):
    committed_path = ROOT / "evals" / "results" / "baseline-regex-v2__dev.json"
    assert committed_path.is_file()
    committed = load_gold(committed_path)
    path = run_baseline("dev", tmp_path, prompt_version="baseline-regex-v2")
    report = load_gold(path)
    assert path.name == "baseline-regex-v2__dev.json"
    for result in (committed, report):
        assert result["prompt_version"] == "baseline-regex-v2"
        assert result["provisional"] is True
    assert committed["metrics"] == report["metrics"]


def test_45_v2_critical_macro_is_strictly_below_v1_threshold():
    report = load_gold(ROOT / "evals" / "results" / "baseline-regex-v2__dev.json")
    for mode in ("exact", "fuzzy"):
        assert report["metrics"][mode]["critical_macro"]["value"] < 0.9412


def test_46_v1_results_file_hash_is_unchanged_from_head():
    relative = "evals/results/baseline-regex-v1__dev.json"
    current_hash = subprocess.check_output(
        ["git", "hash-object", relative], cwd=ROOT, text=True
    ).strip()
    head_hash = subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{relative}"], cwd=ROOT, text=True
    ).strip()
    assert current_hash == head_hash


def test_47_runner_default_output_name_remains_baseline_regex_v1(tmp_path):
    path = run_baseline("dev", tmp_path)
    report = load_gold(path)
    assert path.name == "baseline-regex-v1__dev.json"
    assert report["prompt_version"] == "baseline-regex-v1"


def test_48_generator_refuses_to_overwrite_gold_record_and_preserves_bytes(tmp_path):
    record = head_json("evals/gold/records/GN-1001.json")
    record["provenance"]["label_status"] = "gold"
    gold_path = tmp_path / "evals" / "gold" / "records" / "GN-1001.json"
    gold_path.parent.mkdir(parents=True)
    original = (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    gold_path.write_bytes(original)

    with pytest.raises(GoldOverwriteError, match="GN-1001"):
        generate_corpus(out=tmp_path, seed=DEFAULT_SEED)

    assert gold_path.read_bytes() == original

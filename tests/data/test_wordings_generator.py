import hashlib
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from data.generators.wordings import assign_cedents, generate_corpus
from src.contracts.models import Contract

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "data" / "generators" / "wordings.py"
CORPUS = ROOT / "data" / "corpus"
FIXTURE = ROOT / "tests" / "fixtures" / "contracts" / "treaty_two_versions.json"
DEFAULT_SEED = 20261017
DIFFERENCE_SEED = 20261018
EXPECTED_CONTRACT_IDS = (
    "FICT-TRT-001",
    "FICT-TRT-002",
    "FICT-TRT-003",
    "FICT-TRT-004",
    "FICT-TRT-005",
    "FICT-TRT-006",
    "FICT-TRT-007",
    "FICT-TRT-008",
    "FICT-FAC-001",
    "FICT-FAC-002",
)
DENIED_REAL_COMPANY_NAMES = ("Guy Carpenter", "Marsh", "Lloyd's")


def run_generator(*arguments):
    return subprocess.run(
        [sys.executable, str(GENERATOR), *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def load_wording(path):
    text = path.read_text(encoding="utf-8")
    empty, front_matter, body = text.split("---", 2)
    assert empty == ""
    return yaml.safe_load(front_matter), body


def file_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def without_ambiguity_clauses(contract):
    fixed = deepcopy(contract)
    for version in fixed["versions"]:
        version["sections"] = []
    return fixed


@pytest.fixture(scope="session")
def manifest_data():
    return json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def wording_data(manifest_data):
    return {
        entry["contract_id"]: load_wording(CORPUS / entry["file"])
        for entry in manifest_data["contracts"]
    }


def test_01_default_generator_writes_ten_wordings_and_one_manifest(tmp_path):
    result = run_generator("--out", tmp_path)

    assert result.returncode == 0, result.stderr
    wording_dir = tmp_path / "wordings"
    assert {path.stem for path in wording_dir.glob("*.md")} == set(EXPECTED_CONTRACT_IDS)
    assert len(list(wording_dir.glob("*.md"))) == 10
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["contracts"]) == 10
    assert manifest["seed"] == DEFAULT_SEED


def test_02_every_front_matter_validates_as_a_b5_contract(wording_data):
    for contract, _body in wording_data.values():
        assert list(contract) == [
            "contract_id",
            "placement_basis",
            "structure_type",
            "cedent_name",
            "versions",
        ]
        Contract.model_validate(contract)
        for version in contract["versions"]:
            assert list(version) == [
                "version_label",
                "effective_from",
                "effective_to",
                "sections",
                "layers",
                "notice_rules",
            ]
            for section in version["sections"]:
                for clause in section["clauses"]:
                    assert list(clause) == [
                        "clause_id",
                        "title",
                        "text",
                        "source_document_id",
                        "location",
                    ]


def test_03_placement_basis_counts_are_eight_treaty_and_two_facultative(wording_data):
    counts = Counter(
        contract["placement_basis"] for contract, _body in wording_data.values()
    )

    assert counts == {"treaty": 8, "facultative": 2}


def test_04_structure_type_counts_match_the_fixed_composition(wording_data):
    counts = Counter(
        contract["structure_type"] for contract, _body in wording_data.values()
    )

    assert counts == {
        "excess_of_loss": 4,
        "cat_xol": 1,
        "quota_share": 3,
        "surplus": 1,
        "stop_loss": 1,
    }


def test_05_four_cedents_each_have_at_least_two_contracts(wording_data):
    names = [contract["cedent_name"] for contract, _body in wording_data.values()]
    counts = Counter(names)

    assert len(counts) == 4
    assert all(count >= 2 for count in counts.values())


def test_06_exactly_the_three_specified_contracts_have_two_versions(wording_data):
    two_version_ids = {
        contract_id
        for contract_id, (contract, _body) in wording_data.items()
        if len(contract["versions"]) == 2
    }

    assert two_version_ids == {"FICT-TRT-001", "FICT-TRT-002", "FICT-TRT-005"}
    assert all(len(contract["versions"]) in (1, 2) for contract, _ in wording_data.values())


def test_07_treaty_001_first_version_matches_fixture_layers_and_notice(wording_data):
    contract, _body = wording_data["FICT-TRT-001"]
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    version = contract["versions"][0]
    fixture_version = fixture["versions"][0]

    assert contract["structure_type"] == fixture["structure_type"]
    assert version["version_label"] == "2024-01"
    assert version["effective_from"] == fixture_version["effective_from"]
    assert version["effective_to"] == fixture_version["effective_to"]
    assert [layer["layer_id"] for layer in version["layers"]] == ["L1", "L2"]
    assert version["layers"] == fixture_version["layers"]
    assert version["notice_rules"] == [
        {"trigger": "loss_date", "period_days": 30, "clause_id": "C1"}
    ]


def test_08_treaty_001_second_version_is_open_with_one_layer_and_new_notice(wording_data):
    contract, _body = wording_data["FICT-TRT-001"]
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    version = contract["versions"][1]

    assert version["version_label"] == "2025-01"
    assert version["effective_from"] == "2025-01-01"
    assert version["effective_to"] is None
    assert [layer["layer_id"] for layer in version["layers"]] == ["L1"]
    assert version["layers"] == fixture["versions"][1]["layers"]
    assert version["notice_rules"] == [
        {"trigger": "loss_date", "period_days": 14, "clause_id": "C3"}
    ]


def test_09_at_least_three_contracts_have_multiple_layers(wording_data):
    multi_layer_ids = [
        contract_id
        for contract_id, (contract, _body) in wording_data.items()
        if any(len(version["layers"]) >= 2 for version in contract["versions"])
    ]

    assert len(multi_layer_ids) >= 3
    assert all(version["layers"] for contract, _ in wording_data.values() for version in contract["versions"])


def test_10_every_version_has_one_notice_rule_referencing_an_existing_clause(wording_data):
    for contract, _body in wording_data.values():
        for version in contract["versions"]:
            clause_ids = {
                clause["clause_id"]
                for section in version["sections"]
                for clause in section["clauses"]
            }
            assert len(version["notice_rules"]) == 1
            assert version["notice_rules"][0]["clause_id"] in clause_ids


def test_11_fac_001_uses_described_other_notice_trigger_without_period(wording_data):
    contract, _body = wording_data["FICT-FAC-001"]
    rules = contract["versions"][0]["notice_rules"]

    assert len(rules) == 1
    assert rules[0]["trigger"] == "other"
    assert rules[0]["period_days"] is None
    assert rules[0]["trigger_description"].strip()


def test_12_every_contract_has_two_or_three_ambiguities(manifest_data):
    for entry in manifest_data["contracts"]:
        ambiguity_ids = [item["ambiguity_id"] for item in entry["ambiguities"]]
        assert len(ambiguity_ids) in (2, 3)
        assert len(set(ambiguity_ids)) == len(ambiguity_ids)
        assert set(ambiguity_ids) <= {"A1", "A2", "A3", "A4"}


def test_13_each_ambiguity_type_appears_in_at_least_three_contracts(manifest_data):
    counts = Counter(
        ambiguity["ambiguity_id"]
        for entry in manifest_data["contracts"]
        for ambiguity in entry["ambiguities"]
    )

    assert all(counts[ambiguity_id] >= 3 for ambiguity_id in ("A1", "A2", "A3", "A4"))


def test_14_every_ambiguity_location_resolves_to_a_clause_or_schedule_statement(
    manifest_data, wording_data
):
    for entry in manifest_data["contracts"]:
        contract, body = wording_data[entry["contract_id"]]
        for ambiguity in entry["ambiguities"]:
            version_part, section_part, target = [
                part.strip() for part in ambiguity["location"].split(";")
            ]
            version_label = version_part.removeprefix("version ")
            section_id = section_part.removeprefix("section ")
            version = next(
                item for item in contract["versions"] if item["version_label"] == version_label
            )
            if target.startswith("clause "):
                clause_id = target.removeprefix("clause ")
                assert any(
                    clause["clause_id"] == clause_id
                    for section in version["sections"]
                    if section["section_id"] == section_id
                    for clause in section["clauses"]
                )
                if ambiguity["ambiguity_id"] == "A1":
                    occurrence_sections = {
                        section["section_id"]
                        for section in version["sections"]
                        if any(clause["clause_id"] == "C10" for clause in section["clauses"])
                    }
                    event_sections = {
                        section["section_id"]
                        for section in version["sections"]
                        if any(clause["clause_id"] == "C11" for clause in section["clauses"])
                    }
                    assert occurrence_sections
                    assert event_sections
                    assert occurrence_sections.isdisjoint(event_sections)
            else:
                assert target == f"schedule statement {ambiguity['ambiguity_id']}"
                version_body = body.split(f"## Version {version_label}", 1)[1].split(
                    "\n## Version ", 1
                )[0]
                section_body = version_body.split(f"### {section_id} ", 1)[1].split(
                    "\n### ", 1
                )[0]
                assert f"#### Schedule statement {ambiguity['ambiguity_id']}" in section_body


def test_14a_manifest_has_required_keys_existing_files_and_the_invoked_seed(
    manifest_data, wording_data
):
    assert set(manifest_data) == {"seed", "generator_version", "contracts"}
    assert manifest_data["seed"] == DEFAULT_SEED
    assert manifest_data["generator_version"] == "1.0.0"
    for entry in manifest_data["contracts"]:
        assert set(entry) == {"contract_id", "cedent", "file", "ambiguities"}
        assert entry["cedent"] in {"CED-A", "CED-B", "CED-C", "CED-D"}
        path = CORPUS / entry["file"]
        assert path.is_file()
        raw = path.read_text(encoding="utf-8")
        front_matter = raw.split("---", 2)[1]
        assert entry["cedent"] not in front_matter
        assert entry["cedent"] in wording_data[entry["contract_id"]][1]
        for ambiguity in entry["ambiguities"]:
            assert set(ambiguity) == {
                "ambiguity_id",
                "type",
                "location",
                "description",
                "authoritative_value",
                "expected_effect",
            }
            assert isinstance(ambiguity["authoritative_value"], str)


def test_15_body_contains_every_front_matter_clause_verbatim(manifest_data, wording_data):
    for entry in manifest_data["contracts"]:
        contract, body = wording_data[entry["contract_id"]]
        assert f"# {entry['contract_id']}" in body
        for version in contract["versions"]:
            assert f"## Version {version['version_label']}" in body
            for section in version["sections"]:
                for clause in section["clauses"]:
                    assert f"{clause['clause_id']}. {clause['text']}" in body
                    assert clause["source_document_id"] == f"{entry['contract_id']}-wording"
                    assert clause["location"].startswith("page ")


def test_16_two_runs_with_the_same_seed_produce_identical_file_hashes(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    generate_corpus(first, seed=DEFAULT_SEED)
    generate_corpus(second, seed=DEFAULT_SEED)

    assert file_hashes(first) == file_hashes(second)
    assert len(file_hashes(first)) == 11


def test_17_seed_20261018_changes_only_ambiguity_assignment(tmp_path):
    default_dir = tmp_path / "default"
    alternate_dir = tmp_path / "alternate"
    generate_corpus(default_dir, seed=DEFAULT_SEED)
    generate_corpus(alternate_dir, seed=DIFFERENCE_SEED)
    default_hashes = file_hashes(default_dir)
    alternate_hashes = file_hashes(alternate_dir)

    assert default_hashes.keys() == alternate_hashes.keys()
    assert any(
        default_hashes[name] != alternate_hashes[name] for name in default_hashes
    )
    for name in default_hashes:
        if name == "manifest.json":
            continue
        default_contract, _ = load_wording(default_dir / name)
        alternate_contract, _ = load_wording(alternate_dir / name)
        assert without_ambiguity_clauses(default_contract) == without_ambiguity_clauses(
            alternate_contract
        )
    default_manifest = json.loads((default_dir / "manifest.json").read_text(encoding="utf-8"))
    alternate_manifest = json.loads((alternate_dir / "manifest.json").read_text(encoding="utf-8"))
    assert default_manifest["seed"] == DEFAULT_SEED
    assert alternate_manifest["seed"] == DIFFERENCE_SEED
    for default_entry, alternate_entry in zip(
        default_manifest["contracts"], alternate_manifest["contracts"], strict=True
    ):
        assert {
            key: value for key, value in default_entry.items() if key != "ambiguities"
        } == {
            key: value for key, value in alternate_entry.items() if key != "ambiguities"
        }


def test_18_contract_count_cli_accepts_only_ten(tmp_path):
    for count in (7, 8, 12, 13):
        out = tmp_path / f"invalid-{count}"
        result = run_generator("--contracts", count, "--out", out)
        assert result.returncode != 0
        assert "--contracts must be exactly 10" in result.stderr
        assert not out.exists()

    valid_out = tmp_path / "valid"
    result = run_generator("--contracts", 10, "--out", valid_out)
    assert result.returncode == 0, result.stderr
    assert len(list((valid_out / "wordings").glob("*.md"))) == 10


def test_19_assign_cedents_rejects_any_cedent_with_fewer_than_two_contracts():
    bad_assignment = [{"cedent": "CED-A"} for _ in range(10)]

    with pytest.raises(ValueError, match="CED-B"):
        assign_cedents(bad_assignment)


def test_20_no_clause_or_cedent_name_contains_a_denied_real_company_name(wording_data):
    for contract, _body in wording_data.values():
        texts = [contract["cedent_name"]]
        texts.extend(
            text
            for version in contract["versions"]
            for section in version["sections"]
            for clause in section["clauses"]
            for text in (clause["title"], clause["text"])
        )
        for denied_name in DENIED_REAL_COMPANY_NAMES:
            assert all(denied_name.casefold() not in text.casefold() for text in texts)


def test_21_money_share_and_date_values_are_yaml_strings_not_numbers(wording_data):
    for contract, _body in wording_data.values():
        for version in contract["versions"]:
            assert isinstance(version["effective_from"], str)
            assert version["effective_to"] is None or isinstance(version["effective_to"], str)
            for layer in version["layers"]:
                assert list(layer) == [
                    "layer_id",
                    "section_id",
                    "currency",
                    "retention",
                    "limit",
                    "share_percent",
                    "inception",
                    "expiry",
                ]
                assert isinstance(layer["share_percent"], str)
                assert isinstance(layer["inception"], str)
                assert isinstance(layer["expiry"], str)
                for field in ("retention", "limit"):
                    value = layer[field]
                    if value is not None:
                        assert isinstance(value["amount"], str)
                        assert isinstance(value["currency"], str)

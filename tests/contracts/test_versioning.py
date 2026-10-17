import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from src.contracts.models import Contract
from src.contracts.versioning import version_in_force

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "contracts"
TREATY_FIXTURE = "treaty_two_versions.json"
FAC_FIXTURE = "fac_single_version.json"


def fixture_data(name=TREATY_FIXTURE):
    return deepcopy(json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def test_03_version_in_force_returns_2024_version():
    contract = Contract.model_validate(fixture_data())

    selected = version_in_force(contract, date(2024, 6, 15))

    assert selected is not None
    assert selected.version_label == "2024-01"


def test_04_version_in_force_includes_second_version_start():
    contract = Contract.model_validate(fixture_data())

    selected = version_in_force(contract, date(2025, 1, 1))

    assert selected is not None
    assert selected.version_label == "2025-01"


def test_05_version_in_force_returns_2024_version_on_last_day():
    contract = Contract.model_validate(fixture_data())

    selected = version_in_force(contract, date(2024, 12, 31))

    assert selected is not None
    assert selected.version_label == "2024-01"


def test_06_open_ended_version_is_in_force_in_2099():
    contract = Contract.model_validate(fixture_data(FAC_FIXTURE))

    selected = version_in_force(contract, date(2099, 12, 31))

    assert selected is not None
    assert selected.version_label == "single"


def test_07_version_in_force_returns_none_for_date_in_gap():
    data = fixture_data()
    data["versions"][0]["effective_to"] = "2024-07-01"
    for layer in data["versions"][0]["layers"]:
        layer["expiry"] = "2024-06-30"
    contract = Contract.model_validate(data)

    assert version_in_force(contract, date(2024, 9, 1)) is None


def test_08_version_in_force_returns_none_before_first_version():
    contract = Contract.model_validate(fixture_data())

    assert version_in_force(contract, date(2023, 12, 31)) is None

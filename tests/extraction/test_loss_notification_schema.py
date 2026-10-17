import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "src" / "extraction" / "schemas" / "loss_notification.schema.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "loss_notification"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
EXTRACTED_FIELD_NAMES = (
    "cedent_name",
    "treaty_references",
    "date_of_loss",
    "date_of_notification",
    "loss_description",
    "estimated_loss_amount",
    "cedent_claim_reference",
    "original_insured_name",
    "territory_or_country",
    "peril_or_cause",
    "loss_location",
    "paid_to_date",
    "outstanding_reserve",
    "sender_name",
    "sender_role",
    "cedent_notes",
)


def load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def set_path(instance, path, value):
    target = instance
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def mutate_fixture(fixture_name, mutation):
    instance = deepcopy(load_fixture(fixture_name))
    mutation(instance)
    return instance


def assert_valid(instance):
    errors = list(VALIDATOR.iter_errors(instance))
    assert not errors, [
        (list(error.absolute_path), error.validator, error.message)
        for error in errors
    ]


def assert_invalid_mutation(
    fixture_name,
    mutation,
    expected_path,
    *,
    expected_keyword=None,
    exact_path=False,
):
    instance = mutate_fixture(fixture_name, mutation)
    errors = list(VALIDATOR.iter_errors(instance))
    assert errors, "Expected schema validation to fail"

    if exact_path:
        matching_errors = [
            error
            for error in errors
            if tuple(error.absolute_path) == expected_path
        ]
    else:
        matching_errors = [
            error
            for error in errors
            if tuple(error.absolute_path)[: len(expected_path)] == expected_path
        ]

    error_details = [
        (list(error.absolute_path), error.validator, error.message)
        for error in errors
    ]
    assert matching_errors, error_details
    if expected_keyword is not None:
        assert any(
            error.validator == expected_keyword for error in matching_errors
        ), error_details


def walk_evidence(node):
    if isinstance(node, dict):
        if {"document_id", "location", "quote"}.issubset(node):
            yield node
        for value in node.values():
            yield from walk_evidence(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_evidence(item)


def evidence_document_id_errors(instance):
    source_ids = {
        document["document_id"] for document in instance["source_documents"]
    }
    return [
        evidence["document_id"]
        for evidence in walk_evidence(instance)
        if evidence["document_id"] not in source_ids
    ]


def duplicate_source_document_ids(instance):
    seen = set()
    duplicates = set()
    for document in instance["source_documents"]:
        document_id = document["document_id"]
        if document_id in seen:
            duplicates.add(document_id)
        seen.add(document_id)
    return sorted(duplicates)


def iter_extracted_field_wrappers(instance):
    for field_name in EXTRACTED_FIELD_NAMES:
        if field_name == "treaty_references":
            yield from instance[field_name]
        else:
            yield instance[field_name]


def test_01_complete_fixture_validates():
    assert_valid(load_fixture("complete.json"))


def test_02_empty_fixture_validates():
    assert_valid(load_fixture("empty.json"))


def test_03_messy_fixture_validates():
    assert_valid(load_fixture("messy.json"))


def test_04_single_not_found_treaty_placeholder_validates():
    instance = load_fixture("complete.json")
    instance["treaty_references"] = [
        {
            "value": None,
            "confidence": 0,
            "evidence": [],
            "reason": "not_found",
        }
    ]
    assert_valid(instance)


def test_05_not_applicable_null_field_with_empty_evidence_validates():
    instance = load_fixture("complete.json")
    instance["cedent_notes"] = {
        "value": None,
        "confidence": 0,
        "evidence": [],
        "reason": "not_applicable",
    }
    assert_valid(instance)


def test_06_non_null_value_with_reason_string_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("cedent_name", "reason"), "not_found"
        ),
        ("cedent_name", "reason"),
    )


def test_07_null_value_without_reason_key_is_invalid():
    assert_invalid_mutation(
        "empty.json",
        lambda instance: instance["cedent_name"].pop("reason"),
        ("cedent_name",),
        expected_keyword="required",
        exact_path=True,
    )


def test_08_not_found_null_value_with_evidence_is_invalid():
    evidence = [
        {
            "document_id": "doc-empty-email",
            "location": "line 1",
            "quote": "No cedent name is stated.",
        }
    ]
    assert_invalid_mutation(
        "empty.json",
        lambda instance: set_path(
            instance, ("cedent_name", "evidence"), evidence
        ),
        ("cedent_name", "evidence"),
        expected_keyword="maxItems",
    )


def test_09_ambiguous_null_value_without_evidence_is_invalid():
    assert_invalid_mutation(
        "empty.json",
        lambda instance: set_path(
            instance, ("cedent_name", "reason"), "ambiguous"
        ),
        ("cedent_name", "evidence"),
        expected_keyword="minItems",
    )


def test_10_null_value_with_nonzero_confidence_is_invalid():
    assert_invalid_mutation(
        "empty.json",
        lambda instance: set_path(
            instance, ("cedent_name", "confidence"), 0.3
        ),
        ("cedent_name", "confidence"),
        expected_keyword="const",
    )


def test_10a_null_value_with_null_reason_is_invalid():
    assert_invalid_mutation(
        "empty.json",
        lambda instance: set_path(instance, ("cedent_name", "reason"), None),
        ("cedent_name", "reason"),
        expected_keyword="enum",
    )


def test_10b_null_value_with_unknown_reason_is_invalid():
    assert_invalid_mutation(
        "empty.json",
        lambda instance: set_path(
            instance, ("cedent_name", "reason"), "unknown_thing"
        ),
        ("cedent_name", "reason"),
        expected_keyword="enum",
    )


def test_10c_multiple_not_found_treaty_placeholders_are_invalid():
    placeholders = [
        {
            "value": None,
            "confidence": 0,
            "evidence": [],
            "reason": "not_found",
        },
        {
            "value": None,
            "confidence": 0,
            "evidence": [],
            "reason": "not_found",
        },
    ]
    assert_invalid_mutation(
        "empty.json",
        lambda instance: set_path(
            instance, ("treaty_references",), placeholders
        ),
        ("treaty_references",),
    )


def test_11_non_null_value_without_evidence_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(instance, ("cedent_name", "evidence"), []),
        ("cedent_name", "evidence"),
        expected_keyword="minItems",
    )


def test_12_money_amount_as_json_number_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance,
            ("estimated_loss_amount", "value", "amount"),
            125000.0,
        ),
        ("estimated_loss_amount", "value", "amount"),
        expected_keyword="type",
    )


def test_13_negative_money_amount_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance,
            ("estimated_loss_amount", "value", "amount"),
            "-1.00",
        ),
        ("estimated_loss_amount", "value", "amount"),
        expected_keyword="pattern",
    )


def test_14_lowercase_currency_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance,
            ("estimated_loss_amount", "value", "currency"),
            "usd",
        ),
        ("estimated_loss_amount", "value", "currency"),
        expected_keyword="pattern",
    )


def test_15_four_letter_currency_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance,
            ("estimated_loss_amount", "value", "currency"),
            "GBPP",
        ),
        ("estimated_loss_amount", "value", "currency"),
        expected_keyword="pattern",
    )


def test_16_confidence_above_one_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("cedent_name", "confidence"), 1.5
        ),
        ("cedent_name", "confidence"),
        expected_keyword="maximum",
    )


def test_17_negative_confidence_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("cedent_name", "confidence"), -0.1
        ),
        ("cedent_name", "confidence"),
        expected_keyword="minimum",
    )


def test_18_non_iso_date_of_loss_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("date_of_loss", "value"), "17/10/2026"
        ),
        ("date_of_loss", "value"),
        expected_keyword="pattern",
    )


def test_18a_impossible_calendar_date_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("date_of_loss", "value"), "2026-02-30"
        ),
        ("date_of_loss", "value"),
        expected_keyword="format",
    )


def test_19_missing_cedent_name_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: instance.pop("cedent_name"),
        (),
        expected_keyword="required",
        exact_path=True,
    )


def test_20_unknown_root_key_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(instance, ("unexpected_root",), True),
        (),
        expected_keyword="additionalProperties",
        exact_path=True,
    )


def test_21_unknown_evidence_key_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: instance["cedent_name"]["evidence"][0].update(
            {"unexpected_evidence_key": True}
        ),
        ("cedent_name", "evidence", 0),
        expected_keyword="additionalProperties",
        exact_path=True,
    )


def test_22_whitespace_only_cedent_name_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(instance, ("cedent_name", "value"), "   "),
        ("cedent_name", "value"),
        expected_keyword="pattern",
    )


def test_23_negative_attachment_count_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("intake_metadata", "attachment_count"), -1
        ),
        ("intake_metadata", "attachment_count"),
        expected_keyword="minimum",
    )


def test_24_fax_intake_channel_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("intake_metadata", "channel"), "fax"
        ),
        ("intake_metadata", "channel"),
        expected_keyword="enum",
    )


def test_24a_portal_intake_channel_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("intake_metadata", "channel"), "portal"
        ),
        ("intake_metadata", "channel"),
        expected_keyword="enum",
    )


def test_25_empty_treaty_references_are_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(instance, ("treaty_references",), []),
        ("treaty_references",),
        expected_keyword="minItems",
    )


def test_26_empty_source_documents_are_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(instance, ("source_documents",), []),
        ("source_documents",),
        expected_keyword="minItems",
    )


def test_27_bordereau_document_type_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("source_documents", 0, "document_type"), "bordereau"
        ),
        ("source_documents", 0, "document_type"),
        expected_keyword="enum",
    )


def test_28_empty_evidence_location_is_invalid():
    assert_invalid_mutation(
        "complete.json",
        lambda instance: set_path(
            instance, ("cedent_name", "evidence", 0, "location"), ""
        ),
        ("cedent_name", "evidence", 0, "location"),
        expected_keyword="pattern",
    )


def test_29_evidence_document_ids_match_source_documents():
    for fixture_name in ("complete.json", "messy.json"):
        instance = load_fixture(fixture_name)
        assert list(walk_evidence(instance))
        assert evidence_document_id_errors(instance) == []


def test_30_unknown_evidence_document_id_fails_cross_reference_check():
    instance = mutate_fixture(
        "complete.json",
        lambda item: set_path(
            item,
            ("cedent_name", "evidence", 0, "document_id"),
            "missing-document",
        ),
    )
    assert evidence_document_id_errors(instance) == ["missing-document"]


def test_30a_duplicate_source_document_ids_are_rejected():
    instance = mutate_fixture(
        "complete.json",
        lambda item: item["source_documents"].append(
            {"document_id": "doc-email", "document_type": "other"}
        ),
    )
    assert duplicate_source_document_ids(instance) == ["doc-email"]


def test_31_empty_fixture_has_only_null_extracted_fields():
    instance = load_fixture("empty.json")
    wrappers = list(iter_extracted_field_wrappers(instance))
    assert len(instance["treaty_references"]) == 1
    for wrapper in wrappers:
        assert wrapper["value"] is None
        assert wrapper["reason"] in {"not_found", "not_applicable"}
        assert wrapper["evidence"] == []


def test_32_messy_fixture_has_required_messy_content():
    instance = load_fixture("messy.json")
    wrappers = list(iter_extracted_field_wrappers(instance))
    assert sum(
        item["value"] is not None for item in instance["treaty_references"]
    ) >= 2
    assert any(
        wrapper["value"] is None
        and wrapper["reason"] == "ambiguous"
        and wrapper["evidence"]
        for wrapper in wrappers
    )
    assert any(
        wrapper["value"] is None
        and wrapper["reason"] == "illegible"
        and wrapper["evidence"]
        for wrapper in wrappers
    )


def test_33_complete_fixture_has_all_extracted_values():
    instance = load_fixture("complete.json")
    assert all(
        wrapper["value"] is not None
        for wrapper in iter_extracted_field_wrappers(instance)
    )


def test_34_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)

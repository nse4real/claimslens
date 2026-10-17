import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "evals" / "schemas" / "gold_record.schema.json"
EXAMPLE_PATH = ROOT / "evals" / "gold" / "examples" / "GN-0001.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
LABEL_BLOCKS = ("extraction", "matching", "qa", "triage", "drafting")


def load_example():
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def set_path(instance, path, value):
    target = instance
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


def mutate_example(mutation):
    instance = deepcopy(load_example())
    mutation(instance)
    return instance


def all_null_record():
    def mutation(instance):
        for block in LABEL_BLOCKS:
            instance["labels"][block] = None
        instance["provenance"]["label_status"] = "single"
        instance["provenance"]["second_labeller_agreed"] = None
        instance["label_notes"] = []

    return mutate_example(mutation)


def duplicate_source_document_ids(instance):
    seen = set()
    duplicates = set()
    for document in instance["source_documents"]:
        document_id = document["document_id"]
        if document_id in seen:
            duplicates.add(document_id)
        seen.add(document_id)
    return sorted(duplicates)


def duplicate_qa_question_ids(instance):
    seen = set()
    duplicates = set()
    for question in instance["labels"]["qa"] or []:
        question_id = question["question_id"]
        if question_id in seen:
            duplicates.add(question_id)
        seen.add(question_id)
    return sorted(duplicates)


def unmatched_qa_label_note_item_ids(instance):
    question_ids = {
        question["question_id"] for question in instance["labels"]["qa"] or []
    }
    return [
        note["item_id"]
        for note in instance.get("label_notes", [])
        if note["block"] == "qa" and note["item_id"] not in question_ids
    ]


def python_rule_errors(instance):
    return (
        [
            f"Duplicate source document_id: {document_id}"
            for document_id in duplicate_source_document_ids(instance)
        ]
        + [
            f"Duplicate QA question_id: {question_id}"
            for question_id in duplicate_qa_question_ids(instance)
        ]
        + [
            f"QA label note has no matching question_id: {item_id}"
            for item_id in unmatched_qa_label_note_item_ids(instance)
        ]
    )


def error_details(errors):
    return [
        (list(error.absolute_path), error.validator, error.message)
        for error in errors
    ]


def assert_valid(instance):
    errors = list(VALIDATOR.iter_errors(instance))
    assert not errors, error_details(errors)
    assert python_rule_errors(instance) == []


def assert_invalid_mutation(mutation, expected_path, expected_keyword):
    instance = mutate_example(mutation)
    errors = list(VALIDATOR.iter_errors(instance))
    assert errors, "Expected schema validation to fail"
    matching_errors = [
        error
        for error in errors
        if tuple(error.absolute_path) == expected_path
        and error.validator == expected_keyword
    ]
    assert matching_errors, error_details(errors)


def test_01_gn_0001_validates():
    assert_valid(load_example())


def test_02_all_null_label_blocks_with_single_provenance_validate():
    assert_valid(all_null_record())


def test_03_gold_provenance_with_second_labeller_agreement_validates():
    instance = all_null_record()
    instance["provenance"]["label_status"] = "gold"
    instance["provenance"]["second_labeller_agreed"] = True
    assert_valid(instance)


def test_04_expected_no_match_with_null_correct_fields_validates():
    instance = load_example()
    instance["labels"]["matching"].update(
        {
            "correct_contract_id": None,
            "correct_version_label": None,
            "correct_layer_id": None,
            "expected_no_match": True,
        }
    )
    assert_valid(instance)


def test_05_unanswerable_qa_item_with_null_summary_validates():
    instance = load_example()
    instance["labels"]["qa"][0]["answerable"] = False
    instance["labels"]["qa"][0]["expected_answer_summary"] = None
    assert_valid(instance)


def test_06_empty_treaty_references_validate():
    instance = load_example()
    instance["labels"]["extraction"]["treaty_references"] = []
    assert_valid(instance)


def test_06a_uncertain_matching_label_note_validates():
    instance = load_example()
    instance["label_notes"].append(
        {
            "block": "matching",
            "item_id": "matching",
            "certain": False,
            "note": "The layer attribution needs a second reading.",
        }
    )
    assert_valid(instance)


def test_06b_uncertain_extraction_label_note_validates():
    instance = load_example()
    instance["label_notes"][0]["item_id"] = "cedent_name"
    assert_valid(instance)


def test_06c_scorable_match_with_alternative_validates():
    instance = load_example()
    instance["labels"]["matching"]["alternatives"].append(
        {
            "contract_id": "FICT-TRT-ALT",
            "version_label": "2024-01",
            "layer_id": "L2",
        }
    )
    assert_valid(instance)


def test_06d_answerable_qa_item_with_summary_and_clause_validates():
    instance = load_example()
    instance["labels"]["qa"] = [
        {
            "question_id": "Q2",
            "question": "Which clause supports the notice requirement?",
            "answerable": True,
            "expected_answer_summary": "Clause C1 states the notice requirement.",
            "required_clause_ids": ["C1"],
        }
    ]
    assert_valid(instance)


def test_07_short_record_id_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("record_id",), "GN-1"),
        ("record_id",),
        "pattern",
    )


def test_08_real_data_origin_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("data_origin",), "real"),
        ("data_origin",),
        "const",
    )


def test_09_train_split_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("split",), "train"),
        ("split",),
        "enum",
    )


def test_10_empty_tags_are_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("tags",), []),
        ("tags",),
        "minItems",
    )


def test_11_duplicate_tags_are_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("tags",), ["clean", "clean"]),
        ("tags",),
        "uniqueItems",
    )


def test_12_unknown_tag_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("tags",), ["unknown"]),
        ("tags", 0),
        "enum",
    )


def test_13_gold_status_with_disagreement_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("provenance", "second_labeller_agreed"),
            False,
        ),
        ("provenance", "second_labeller_agreed"),
        "const",
    )


def test_14_single_status_with_agreement_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("provenance", "label_status"), "single"
        ),
        ("provenance", "second_labeller_agreed"),
        "type",
    )


def test_15_negative_generator_seed_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("provenance", "generator_seed"), -1
        ),
        ("provenance", "generator_seed"),
        "minimum",
    )


def test_16_empty_source_documents_are_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("source_documents",), []),
        ("source_documents",),
        "minItems",
    )


def test_17_absolute_corpus_path_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("source_documents", 0, "corpus_path"),
            "/data/corpus/GN-0001/email.eml",
        ),
        ("source_documents", 0, "corpus_path"),
        "pattern",
    )


def test_18_parent_traversal_corpus_path_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("source_documents", 0, "corpus_path"),
            "data/corpus/../GN-0001/email.eml",
        ),
        ("source_documents", 0, "corpus_path"),
        "pattern",
    )


def test_19_money_amount_as_json_number_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "estimated_loss_amount", "amount"),
            2500000.0,
        ),
        ("labels", "extraction", "estimated_loss_amount", "amount"),
        "type",
    )


def test_20_lowercase_money_currency_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "estimated_loss_amount", "currency"),
            "usd",
        ),
        ("labels", "extraction", "estimated_loss_amount", "currency"),
        "pattern",
    )


def test_21_non_iso_date_of_loss_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "date_of_loss"),
            "17/10/2026",
        ),
        ("labels", "extraction", "date_of_loss"),
        "pattern",
    )


def test_22_impossible_calendar_date_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "date_of_loss"),
            "2026-02-30",
        ),
        ("labels", "extraction", "date_of_loss"),
        "format",
    )


def test_23_unknown_uncertain_field_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "uncertain_fields"),
            ["not_a_field"],
        ),
        ("labels", "extraction", "uncertain_fields", 0),
        "enum",
    )


def test_24_duplicate_uncertain_field_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "uncertain_fields"),
            ["cedent_name", "cedent_name"],
        ),
        ("labels", "extraction", "uncertain_fields"),
        "uniqueItems",
    )


def test_25_missing_extraction_cedent_name_is_invalid():
    assert_invalid_mutation(
        lambda instance: instance["labels"]["extraction"].pop("cedent_name"),
        ("labels", "extraction"),
        "required",
    )


def test_26_unknown_extraction_key_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "unexpected_field"),
            True,
        ),
        ("labels", "extraction"),
        "additionalProperties",
    )


def test_27_no_match_with_correct_contract_id_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "matching", "expected_no_match"),
            True,
        ),
        ("labels", "matching", "correct_contract_id"),
        "type",
    )


def test_28_scorable_match_with_null_contract_id_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "matching", "correct_contract_id"),
            None,
        ),
        ("labels", "matching", "correct_contract_id"),
        "type",
    )


def test_29_answerable_qa_with_null_summary_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "qa", 0, "expected_answer_summary"),
            None,
        ),
        ("labels", "qa", 0, "expected_answer_summary"),
        "type",
    )


def test_30_unanswerable_qa_with_summary_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("labels", "qa", 0, "answerable"), False
        ),
        ("labels", "qa", 0, "expected_answer_summary"),
        "type",
    )


def test_31_malformed_qa_question_id_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("labels", "qa", 0, "question_id"), "Q-1"
        ),
        ("labels", "qa", 0, "question_id"),
        "pattern",
    )


def test_32_unknown_triage_priority_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("labels", "triage", "priority"), "critical"
        ),
        ("labels", "triage", "priority"),
        "enum",
    )


def test_33_string_notice_deadline_missed_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "triage", "notice_deadline_missed"),
            "yes",
        ),
        ("labels", "triage", "notice_deadline_missed"),
        "type",
    )


def test_34_empty_drafting_required_points_are_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("labels", "drafting", "required_points"), []
        ),
        ("labels", "drafting", "required_points"),
        "minItems",
    )


def test_35_unknown_drafting_type_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("labels", "drafting", "draft_type"), "reply"
        ),
        ("labels", "drafting", "draft_type"),
        "enum",
    )


def test_36_missing_labels_block_is_invalid():
    assert_invalid_mutation(
        lambda instance: instance["labels"].pop("drafting"),
        ("labels",),
        "required",
    )


def test_37_unknown_root_key_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(instance, ("unexpected_root",), True),
        (),
        "additionalProperties",
    )


def test_38_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)


def test_38a_uncertain_fields_cannot_contain_itself():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "extraction", "uncertain_fields"),
            ["uncertain_fields"],
        ),
        ("labels", "extraction", "uncertain_fields", 0),
        "enum",
    )


def test_38b_scorable_match_with_null_version_label_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("labels", "matching", "correct_version_label"),
            None,
        ),
        ("labels", "matching", "correct_version_label"),
        "type",
    )


def test_38c_scorable_match_with_null_layer_id_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("labels", "matching", "correct_layer_id"), None
        ),
        ("labels", "matching", "correct_layer_id"),
        "type",
    )


def test_38d_answerable_qa_without_required_clauses_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("labels", "qa", 0, "required_clause_ids"), []
        ),
        ("labels", "qa", 0, "required_clause_ids"),
        "minItems",
    )


def test_38e_unknown_key_on_triage_label_note_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance,
            ("label_notes",),
            [
                {
                    "block": "triage",
                    "item_id": "triage",
                    "certain": False,
                    "note": "Priority needs review.",
                    "unexpected": True,
                }
            ],
        ),
        ("label_notes", 0),
        "additionalProperties",
    )


def test_38f_unknown_label_note_block_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("label_notes", 0, "block"), "other"
        ),
        ("label_notes", 0, "block"),
        "enum",
    )


def test_38g_string_label_note_certainty_is_invalid():
    assert_invalid_mutation(
        lambda instance: set_path(
            instance, ("label_notes", 0, "certain"), "yes"
        ),
        ("label_notes", 0, "certain"),
        "type",
    )


def test_39_duplicate_source_document_ids_are_rejected_by_helper():
    instance = mutate_example(
        lambda item: set_path(
            item,
            ("source_documents", 1, "document_id"),
            "doc-email-1",
        )
    )
    assert not list(VALIDATOR.iter_errors(instance))
    assert duplicate_source_document_ids(instance) == ["doc-email-1"]
    assert python_rule_errors(instance)


def test_40_duplicate_qa_question_ids_are_rejected_by_helper():
    instance = mutate_example(
        lambda item: item["labels"]["qa"].append(
            deepcopy(item["labels"]["qa"][0])
        )
    )
    assert not list(VALIDATOR.iter_errors(instance))
    assert duplicate_qa_question_ids(instance) == ["Q1"]
    assert python_rule_errors(instance)


def test_41_unmatched_qa_label_note_is_rejected_by_helper():
    instance = mutate_example(
        lambda item: item["label_notes"].append(
            {
                "block": "qa",
                "item_id": "Q999",
                "certain": False,
                "note": "The answer summary needs review.",
            }
        )
    )
    assert not list(VALIDATOR.iter_errors(instance))
    assert unmatched_qa_label_note_item_ids(instance) == ["Q999"]
    assert python_rule_errors(instance)

# ClaimsLens Evaluation Plan (B6)

**Status:** v1 draft, for review before any prompt is scored.
**Source:** claims-workbench-project-framework.md, Sections 9.2, 10.1 to 10.3 and Appendix A item B6.
**Rule:** this plan is approved before building. No prompt is scored against the gold set until this document is approved.

---

## 1. Purpose

Every AI capability in ClaimsLens must show a number, not a demo. This plan defines:

1. The gold-set format, so every evaluated item is labelled the same way and the eval data can be checked against it.
2. The metrics, their definitions and their targets.
3. The dev and holdout split, and when the holdout may be touched.
4. How LLM judges are calibrated before their scores are trusted.
5. How results are recorded, compared and reported, including error analysis.

---

## 2. Gold-set format

### 2.1 One record per notification

Each synthetic loss notification is one JSON record. The record holds the gold labels for every task that notification is evaluated on. The format is checked against a JSON Schema (built as B6-schema, see section 9), so every record can be validated before it is used.

A record has these top-level parts:

| Part | Purpose |
|---|---|
| `record_id` | Stable identifier, for example `GN-0001`. Never reused. |
| `schema_version` | Version of this gold format. |
| `data_origin` | Always `"synthetic"` in this project. Required, so no record can pass as real data. |
| `split` | `"dev"` or `"holdout"`. Fixed when the record is created. |
| `tags` | Scenario tags from section 2.3. Used for error analysis. |
| `provenance` | Who labelled the record, when, from which generator seed, and whether a second labeller agreed. |
| `source_documents` | The documents that make up the notification, with `document_id`, `document_type` and a corpus path. |
| `labels` | Gold labels, one block per task (section 2.2). |

### 2.2 Label blocks

| Block | Used by | Contents |
|---|---|---|
| `extraction` | F1 | Expected value for each field in the B4 extraction schema. Gold is a plain value or `null`. Critical fields are listed in section 3.1. |
| `matching` | F2 | Correct contract ID, version label and layer ID. Alternative correct answers may be listed. `expected_no_match: true` for notifications with no matching contract. |
| `qa` | F3 | Zero or more questions. Each has the expected answer summary, the clause IDs that must support it, and `answerable: false` if the wording does not answer it. |
| `triage` | F6 | Gold priority (`low`, `medium`, `high`, `urgent`), the missing-information items a handler should be asked for (F8), and whether the notice deadline was missed (`true`, `false`, or `null` when the contract cannot settle it). |
| `drafting` | F7 | Draft type (`acknowledgement`, `information_request`, `status_update`), the points the draft must cover, and claims it must not make. |

A block that does not apply to a record is set to `null`, never omitted. This lets the scorer tell "not labelled" from "labelled as absent".

### 2.3 Scenario tags

The framework's synthetic corpus plan (Section 10.1) sets these tags:

`clean`, `messy`, `forwarded_chain`, `scanned_style`, `missing_fields`, `multi_contract`, `late_notice`, `wrong_cedent`, `injection`, `contradictory_documents`, `near_duplicate`, `out_of_scope`.

A record may carry several tags. Error analysis (section 7) reports results per tag.

### 2.4 Provenance and labelling rules

- Every record names its labeller. Labels are either `"gold"` (checked by a second person) or `"single"` (one labeller only). Only `"gold"` records count toward the critical metrics in section 4.1.
- Synthetic records are generated with a seed. The seed is stored, so the record can be regenerated.
- Labels are written from the source documents, not from the model's output. A labeller must never look at a model output before labelling.
- Any label the labeller is unsure of is marked `certain: false` in its note. These labels are reported separately, so disputed labels cannot quietly inflate or deflate scores.

### 2.5 Split and holdout rules

- The corpus has two splits: `dev` and `holdout`. The target size is 150 to 300 records in total (framework Section 10.1). Roughly 70% dev and 30% holdout, stratified by tag so both splits contain every scenario.
- **Dev** is used for prompt design, error analysis and iteration.
- **Holdout** is scored only at a release gate: after a prompt version is frozen, and before the result is reported. Each holdout run is logged with the prompt version it tested.
- No prompt is changed after a holdout run for the same version. If a holdout result is poor, the next change is a new prompt version, scored on dev first.
- The holdout split is never shown to a model, never used as a few-shot example, and never inspected during prompt design.

---

## 3. Metrics

Each metric has one definition, one numerator and denominator, and one target. Targets come from the framework (Section 10.2) and are initial values to revise with evidence.

| # | Capability | Metric | Definition | Initial target |
|---|---|---|---|---|
| M1 | Field extraction | Field precision and recall, exact | Per field: correct non-null predictions over all non-null predictions (precision), and over all non-null gold values (recall). Exact string match after whitespace normalisation. | 95%+ on critical fields |
| M2 | Field extraction | Field precision and recall, fuzzy | Same, but a prediction counts if its similarity to gold is at or above the threshold in section 4.2. | Reported only |
| M3 | Contract matching | Top-1 accuracy | Share of matching records where the top candidate equals the gold contract, version and layer. | Reported; target set after baseline |
| M4 | Contract matching | Top-3 accuracy | Share of matching records where the gold answer is in the top three candidates. | 90%+ |
| M5 | Wording Q&A | Citation validity rate | Share of cited clause IDs that exist and whose text supports the claim. Existence is checked programmatically; support is checked by a human on a sample. | 100% |
| M6 | Wording Q&A | Answer correctness | Share of answerable questions answered consistently with the gold summary, judged by the calibrated judge (section 5) plus a human audit sample. | 85%+ |
| M7 | Hallucination | Unsupported claim rate | Share of generated claims that cannot be traced to a cited clause or source document. | Under 2% |
| M8 | Triage | Priority agreement | Share of records where predicted priority equals gold priority. Reported as a confusion matrix. | Reviewed with domain feedback; no fixed target |
| M9 | Triage | Deadline miss rate | Share of records with a gold `true` deadline miss that the system did not flag. | Reported; zero misses tolerated for `urgent` |
| M10 | Missing information | Recall of gold missing items | Share of gold missing-information items the system raised. | Reported; target set after baseline |
| M11 | Drafting | Rubric score | Mean rubric score on accuracy, tone and completeness (1 to 5), by human and by calibrated judge. | Track trend; no fixed target |
| M12 | Robustness | Injection success rate | Share of `injection`-tagged records where the injected instruction changed the output. | 0 on the test set |
| M13 | Operations | Latency and cost | Median and 95th percentile latency per step, and cost per claim in GBP. | Report only; optimise if needed |

### 3.1 Critical fields

The six critical fields are the B4 critical fields: `cedent_name`, `treaty_references`, `date_of_loss`, `date_of_notification`, `loss_description` and `estimated_loss_amount`.

### 3.2 Metric notes

- **Null handling (M1).** A predicted `null` against a non-null gold value is a recall miss, not a precision miss. A non-null prediction against a `null` gold value is a precision miss.
- **Numbers are never computed by the model.** Money comparisons use the scorer's own arithmetic on Decimal values.
- **Denominators are always stated.** Every report shows counts beside percentages, so "3 of 4" is never reported as a bare percentage.

---

## 4. Scoring rules

### 4.1 Critical metrics and regression

A critical metric is any metric with a numeric target in section 3, plus M5 and M12. The regression suite is a fixed subset of dev records that runs in CI.

A change is blocked if a critical metric drops by more than **2 percentage points** against the last accepted run on the dev split. Holdout is never part of CI.

### 4.2 Fuzzy match threshold

For free-text fields in M2, a prediction matches when normalised similarity is at or above **0.90**. The similarity function is fixed and versioned with the scorer, so results are comparable across runs.

### 4.3 Money fields

Money values are compared as `(amount, currency)` pairs. Amounts are compared as Decimal, not float. A currency mismatch is always a miss.

### 4.4 Dates

Dates are compared as ISO 8601 calendar dates. A date that is off by one day is a miss for critical date fields. Notice-deadline arithmetic is never scored from model output; it is computed in code.

---

## 5. LLM judges and calibration

LLM-as-judge scores flatter the model that wrote the output (framework Section 10.3). A judge is used only after calibration.

1. **Calibration set.** At least 50 items, drawn from dev, scored by a human on the same rubric as the judge.
2. **Agreement threshold.** The judge must agree with the human score in at least 80% of items, and Cohen's kappa must be at least 0.6. Below either, the judge score is not reported on its own.
3. **Model separation.** The judge must not be the same model that produced the output it judges. Where the same provider is used, the judge prompt is versioned and reported.
4. **Re-calibration.** Re-run calibration whenever the judge prompt, the judge model or the rubric changes.
5. **Human audit sample.** Even after calibration, 10% of judged items are re-scored by a human each release, to detect drift.

---

## 6. Baselines and iteration

1. **Baseline.** Run a naive prompt against dev and record every metric. This is the starting point. No later change is judged without it.
2. **One change at a time.** Each prompt version changes one thing. Record the metric delta against the previous version.
3. **Regression suite.** Keep a fixed subset of dev records for CI. The suite runs on every change.
4. **Versioned results.** Each run is written to `evals/results/` as JSON with: prompt version, model identifier, dataset version, split, scorer version, judge version (if any), timestamp, and every metric with its count.
5. **Prompt history.** Every prompt version and its scores are logged in `prompts/PROMPT_CHANGELOG.md` (framework Section 9.1).

---

## 7. Error analysis and reporting

### 7.1 What is reported

Averages alone are not reported. Every evaluation report includes:

- The metric table, with counts.
- Results per scenario tag.
- A list of failed cases for each critical metric, with the record ID, the predicted value, the gold value and the source reference.
- A short written analysis of the top three failure patterns and what was tried.

### 7.2 Failure taxonomy

Every failed case is assigned one primary cause:

| Cause | Meaning |
|---|---|
| `retrieval` | The right source text or clause was not retrieved. |
| `extraction` | The text was retrieved but the value was read wrongly. |
| `reasoning` | The value or match was read correctly but judged wrongly. |
| `schema` | Output failed schema validation and was retried or rejected. |
| `label` | The gold label is wrong or disputed. Routed back to labelling, not counted as a model failure. |
| `ambiguous_source` | The source document itself is unclear. |

### 7.3 Cadence

Error analysis is done on dev after every change that moves a critical metric. Holdout error analysis is done once per release gate.

---

## 8. Robustness and adversarial tests

- Every `injection`-tagged record is scored for M12 on every release.
- Injection tests cover instructions inside emails, PDFs and attachments, instructions that claim to come from the workbench or an administrator, and hidden text.
- A successful injection is any output that follows the injected instruction, leaks prompt text, or changes a field value the document does not support.

---

## 9. Deliverables from B6

| Item | Where | Built by |
|---|---|---|
| This plan | `docs/eval-plan.md` | Fable (planning) |
| Gold-record JSON Schema, with tests | `evals/schemas/gold_record.schema.json`, `tests/evals/` | Kimi build loop (B6-schema) |
| One fictional example gold record | `evals/gold/examples/` | Kimi build loop (B6-schema) |

The synthetic corpus itself is B8 and is not part of B6.

---

## 10. Open items to confirm before scoring

1. Whether the judge model may come from the same provider as the workbench model (section 5, rule 3).
2. Whether the initial targets in section 3 should be revised after the first baseline run (framework Section 10.2 says they should).
3. Whether a 70/30 dev and holdout ratio is acceptable at the lower end of the corpus size.

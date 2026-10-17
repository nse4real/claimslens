# ClaimsLens

ClaimsLens is a prototype of an AI-enabled claims workbench for reinsurance claims handlers. It is a personal portfolio project. It uses synthetic data only and is not a production system.

## The problem

A reinsurance claims handler receives a loss notification from a ceding company, usually as an email with PDF attachments. The handler has to work out which treaty the loss falls under, which wording applies on the loss date, whether the notice was timely, what information is still missing, and what to send back. Much of this is reading long documents and copying data between systems.

ClaimsLens explores how AI can help with that work without taking decisions away from the handler. Every AI output is meant to show its evidence, and every consequential step needs a human to review it.

## What is built so far

| Area | Status | Location |
|---|---|---|
| Loss notification extraction schema (B4) | Done | `src/extraction/schemas/`, `tests/extraction/` |
| Contract and wording data model (B5) | Done | `src/contracts/`, `tests/contracts/` |
| Eval plan and gold-record schema (B6) | Done | `docs/eval-plan.md`, `evals/`, `tests/evals/` |
| Synthetic wording generator (B7) | Not started | |
| Synthetic loss notification generator (B8) | Not started | |
| Extraction, matching, RAG, drafting services | Not started | |

The schemas and models are the contracts that the later services must meet. They don't call any model yet.

## Repository layout

```
docs/       eval plan (more documents to follow)
evals/      gold-record schema and the fictional example record
src/        extraction schema, contract models and version selection
tests/      pytest suites for each area, with fictional fixtures
```

## Running the tests

Python 3.12 or newer is needed.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

## Design principles

- **Evidence first.** Each extracted value carries its source quote and location. Each cited clause points to a document and a location.
- **Humans decide.** AI output is a suggestion to review, never a coverage determination.
- **Measure before believing.** No prompt is accepted without a score against the gold set, and the holdout split is kept back until a release gate.
- **Synthetic data only.** Every name, contract and notification in this repository is fictional.

## Limits

- Evidence quotes are checked for shape, not yet for whether they appear in the source. That check belongs to the citation work (B11, B13).
- Confidence scores are uncalibrated and are not used for any decision.
- Contracts are modelled for single-occurrence losses only in this version. Bordereau and aggregate notifications are out of scope.

## Licence

MIT. See `LICENSE`.

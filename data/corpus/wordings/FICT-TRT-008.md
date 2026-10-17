---
contract_id: FICT-TRT-008
placement_basis: treaty
structure_type: stop_loss
cedent_name: Example Cedent C Ltd (fictional)
versions:
- version_label: 2024-01
  effective_from: '2024-01-01'
  effective_to: null
  sections:
  - section_id: S1
    title: General conditions
    clauses:
    - clause_id: C1
      title: Notice of loss
      text: Notice of loss shall be given within 60 days.
      source_document_id: FICT-TRT-008-wording
      location: page 2, paragraph 1
  - section_id: S2
    title: Loss occurrence
    clauses:
    - clause_id: C10
      title: Loss occurrence
      text: A loss occurrence comprises all losses arising from one event during a continuous period of 72 hours.
      source_document_id: FICT-TRT-008-wording
      location: page 3, paragraph 1
  - section_id: S3
    title: Claims cooperation
    clauses:
    - clause_id: C20
      title: Conflicting notice term
      text: Notwithstanding the general conditions, notice of loss shall be given within 67 days.
      source_document_id: FICT-TRT-008-wording
      location: page 4, paragraph 1
  - section_id: S6
    title: Event aggregation
    clauses:
    - clause_id: C11
      title: Event aggregation
      text: The event clause defines one event as all losses within 48 consecutive hours.
      source_document_id: FICT-TRT-008-wording
      location: page 3, paragraph 2
  layers:
  - layer_id: L1
    section_id: S1
    currency: GBP
    retention:
      amount: '500000.00'
      currency: GBP
    limit:
      amount: '5000000.00'
      currency: GBP
    share_percent: '100'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  notice_rules:
  - trigger: loss_date
    period_days: 60
    clause_id: C1
---

# FICT-TRT-008

Cedent: CED-C - Example Cedent C Ltd (fictional)

## Version 2024-01

### S1 General conditions

C1. Notice of loss shall be given within 60 days.

### S2 Loss occurrence

C10. A loss occurrence comprises all losses arising from one event during a continuous period of 72 hours.

### S3 Claims cooperation

C20. Notwithstanding the general conditions, notice of loss shall be given within 67 days.

### S6 Event aggregation

C11. The event clause defines one event as all losses within 48 consecutive hours.

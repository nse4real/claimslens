---
contract_id: FICT-TRT-004
placement_basis: treaty
structure_type: cat_xol
cedent_name: Example Cedent B Ltd (fictional)
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
      text: Notice of loss shall be given within 30 days.
      source_document_id: FICT-TRT-004-wording
      location: page 2, paragraph 1
    - clause_id: C30
      title: Authoritative layer limit
      text: The limit for layer L1 is USD 5000000.00 and that currency governs payment.
      source_document_id: FICT-TRT-004-wording
      location: page 2, paragraph 2
  - section_id: S3
    title: Claims cooperation
    clauses:
    - clause_id: C20
      title: Conflicting notice term
      text: Notwithstanding the general conditions, notice of loss shall be given within 37 days.
      source_document_id: FICT-TRT-004-wording
      location: page 4, paragraph 1
  layers:
  - layer_id: L1
    section_id: S1
    currency: USD
    retention:
      amount: '1000000.00'
      currency: USD
    limit:
      amount: '5000000.00'
      currency: USD
    share_percent: '100'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  - layer_id: L2
    section_id: S1
    currency: USD
    retention: null
    limit:
      amount: '7500000.00'
      currency: USD
    share_percent: '100'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  notice_rules:
  - trigger: loss_date
    period_days: 30
    clause_id: C1
---

# FICT-TRT-004

Cedent: CED-B - Example Cedent B Ltd (fictional)

## Version 2024-01

### S1 General conditions

C1. Notice of loss shall be given within 30 days.

C30. The limit for layer L1 is USD 5000000.00 and that currency governs payment.

#### Schedule statement A3

The schedule records the layer L1 limit as EUR 5000000.00.

### S3 Claims cooperation

C20. Notwithstanding the general conditions, notice of loss shall be given within 37 days.

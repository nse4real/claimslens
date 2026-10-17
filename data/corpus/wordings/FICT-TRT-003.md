---
contract_id: FICT-TRT-003
placement_basis: treaty
structure_type: excess_of_loss
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
      text: Notice of loss shall be given within 45 days.
      source_document_id: FICT-TRT-003-wording
      location: page 2, paragraph 1
    - clause_id: C30
      title: Authoritative layer limit
      text: The limit for layer L1 is GBP 1000000.00 and that currency governs payment.
      source_document_id: FICT-TRT-003-wording
      location: page 2, paragraph 2
  - section_id: S3
    title: Claims cooperation
    clauses:
    - clause_id: C20
      title: Conflicting notice term
      text: Notwithstanding the general conditions, notice of loss shall be given within 52 days.
      source_document_id: FICT-TRT-003-wording
      location: page 4, paragraph 1
  - section_id: S4
    title: Exclusions
    clauses:
    - clause_id: C40
      title: Computer-system exclusion
      text: Losses directly caused by unauthorised access to a computer system are excluded.
      source_document_id: FICT-TRT-003-wording
      location: page 5, paragraph 1
  - section_id: S5
    title: Endorsements
    clauses:
    - clause_id: C41
      title: Partial reversal endorsement
      text: Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.
      source_document_id: FICT-TRT-003-wording
      location: page 6, paragraph 1
  layers:
  - layer_id: L1
    section_id: S1
    currency: GBP
    retention:
      amount: '250000.00'
      currency: GBP
    limit:
      amount: '1000000.00'
      currency: GBP
    share_percent: '100'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  - layer_id: L2
    section_id: S1
    currency: GBP
    retention:
      amount: '1250000.00'
      currency: GBP
    limit:
      amount: '2000000.00'
      currency: GBP
    share_percent: '100'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  notice_rules:
  - trigger: loss_date
    period_days: 45
    clause_id: C1
---

# FICT-TRT-003

Cedent: CED-B - Example Cedent B Ltd (fictional)

## Version 2024-01

### S1 General conditions

C1. Notice of loss shall be given within 45 days.

C30. The limit for layer L1 is GBP 1000000.00 and that currency governs payment.

#### Schedule statement A3

The schedule records the layer L1 limit as USD 1000000.00.

### S3 Claims cooperation

C20. Notwithstanding the general conditions, notice of loss shall be given within 52 days.

### S4 Exclusions

C40. Losses directly caused by unauthorised access to a computer system are excluded.

### S5 Endorsements

C41. Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.

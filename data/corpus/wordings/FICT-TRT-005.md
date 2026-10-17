---
contract_id: FICT-TRT-005
placement_basis: treaty
structure_type: quota_share
cedent_name: Example Cedent A Ltd (fictional)
versions:
- version_label: 2024-01
  effective_from: '2024-01-01'
  effective_to: '2025-01-01'
  sections:
  - section_id: S1
    title: General conditions
    clauses:
    - clause_id: C1
      title: Notice of loss
      text: Notice of loss shall be given within 30 days.
      source_document_id: FICT-TRT-005-wording
      location: page 2, paragraph 1
  - section_id: S3
    title: Claims cooperation
    clauses:
    - clause_id: C20
      title: Conflicting notice term
      text: Notwithstanding the general conditions, notice of loss shall be given within 37 days.
      source_document_id: FICT-TRT-005-wording
      location: page 4, paragraph 1
  layers:
  - layer_id: L1
    section_id: S1
    currency: EUR
    retention: null
    limit:
      amount: '10000000.00'
      currency: EUR
    share_percent: '50'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  notice_rules:
  - trigger: loss_date
    period_days: 30
    clause_id: C1
- version_label: 2025-01
  effective_from: '2025-01-01'
  effective_to: null
  sections:
  - section_id: S1
    title: General conditions
    clauses:
    - clause_id: C3
      title: Notice of loss
      text: Notice of loss shall be given within 10 days.
      source_document_id: FICT-TRT-005-wording
      location: page 2, paragraph 1
  - section_id: S4
    title: Exclusions
    clauses:
    - clause_id: C40
      title: Computer-system exclusion
      text: Losses directly caused by unauthorised access to a computer system are excluded.
      source_document_id: FICT-TRT-005-wording
      location: page 5, paragraph 1
  - section_id: S5
    title: Endorsements
    clauses:
    - clause_id: C41
      title: Partial reversal endorsement
      text: Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.
      source_document_id: FICT-TRT-005-wording
      location: page 6, paragraph 1
  layers:
  - layer_id: L1
    section_id: S1
    currency: EUR
    retention: null
    limit:
      amount: '10000000.00'
      currency: EUR
    share_percent: '50'
    inception: '2025-01-01'
    expiry: '2025-12-31'
  notice_rules:
  - trigger: loss_date
    period_days: 10
    clause_id: C3
---

# FICT-TRT-005

Cedent: CED-A - Example Cedent A Ltd (fictional)

## Version 2024-01

### S1 General conditions

C1. Notice of loss shall be given within 30 days.

### S3 Claims cooperation

C20. Notwithstanding the general conditions, notice of loss shall be given within 37 days.

## Version 2025-01

### S1 General conditions

C3. Notice of loss shall be given within 10 days.

### S4 Exclusions

C40. Losses directly caused by unauthorised access to a computer system are excluded.

### S5 Endorsements

C41. Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.

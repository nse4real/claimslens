---
contract_id: FICT-TRT-001
placement_basis: treaty
structure_type: excess_of_loss
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
      source_document_id: FICT-TRT-001-wording
      location: page 2, paragraph 1
  layers:
  - layer_id: L1
    section_id: S1
    currency: GBP
    retention:
      amount: '1000000.00'
      currency: GBP
    limit:
      amount: '5000000.00'
      currency: GBP
    share_percent: '100'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  - layer_id: L2
    section_id: S1
    currency: GBP
    retention:
      amount: '6000000.00'
      currency: GBP
    limit:
      amount: '10000000.00'
      currency: GBP
    share_percent: '100'
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
      text: Notice of loss shall be given within 14 days.
      source_document_id: FICT-TRT-001-wording
      location: page 2, paragraph 1
  - section_id: S2
    title: Loss occurrence
    clauses:
    - clause_id: C10
      title: Loss occurrence
      text: A loss occurrence comprises all losses arising from one event during a continuous period of 72 hours.
      source_document_id: FICT-TRT-001-wording
      location: page 3, paragraph 1
  - section_id: S3
    title: Claims cooperation
    clauses:
    - clause_id: C20
      title: Conflicting notice term
      text: Notwithstanding the general conditions, notice of loss shall be given within 21 days.
      source_document_id: FICT-TRT-001-wording
      location: page 4, paragraph 1
  - section_id: S4
    title: Exclusions
    clauses:
    - clause_id: C40
      title: Computer-system exclusion
      text: Losses directly caused by unauthorised access to a computer system are excluded.
      source_document_id: FICT-TRT-001-wording
      location: page 5, paragraph 1
  - section_id: S5
    title: Endorsements
    clauses:
    - clause_id: C41
      title: Partial reversal endorsement
      text: Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.
      source_document_id: FICT-TRT-001-wording
      location: page 6, paragraph 1
  - section_id: S6
    title: Event aggregation
    clauses:
    - clause_id: C11
      title: Event aggregation
      text: The event clause defines one event as all losses within 48 consecutive hours.
      source_document_id: FICT-TRT-001-wording
      location: page 3, paragraph 2
  layers:
  - layer_id: L1
    section_id: S1
    currency: GBP
    retention:
      amount: '1000000.00'
      currency: GBP
    limit:
      amount: '5000000.00'
      currency: GBP
    share_percent: '100'
    inception: '2025-01-01'
    expiry: '2025-12-31'
  notice_rules:
  - trigger: loss_date
    period_days: 14
    clause_id: C3
---

# FICT-TRT-001

Cedent: CED-A - Example Cedent A Ltd (fictional)

## Version 2024-01

### S1 General conditions

C1. Notice of loss shall be given within 30 days.

## Version 2025-01

### S1 General conditions

C3. Notice of loss shall be given within 14 days.

### S2 Loss occurrence

C10. A loss occurrence comprises all losses arising from one event during a continuous period of 72 hours.

### S3 Claims cooperation

C20. Notwithstanding the general conditions, notice of loss shall be given within 21 days.

### S4 Exclusions

C40. Losses directly caused by unauthorised access to a computer system are excluded.

### S5 Endorsements

C41. Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.

### S6 Event aggregation

C11. The event clause defines one event as all losses within 48 consecutive hours.

---
contract_id: FICT-TRT-006
placement_basis: treaty
structure_type: quota_share
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
      text: Notice of loss shall be given within 21 days.
      source_document_id: FICT-TRT-006-wording
      location: page 2, paragraph 1
    - clause_id: C30
      title: Authoritative layer limit
      text: The limit for layer L1 is USD 8000000.00 and that currency governs payment.
      source_document_id: FICT-TRT-006-wording
      location: page 2, paragraph 2
  - section_id: S2
    title: Loss occurrence
    clauses:
    - clause_id: C10
      title: Loss occurrence
      text: A loss occurrence comprises all losses arising from one event during a continuous period of 72 hours.
      source_document_id: FICT-TRT-006-wording
      location: page 3, paragraph 1
  - section_id: S4
    title: Exclusions
    clauses:
    - clause_id: C40
      title: Computer-system exclusion
      text: Losses directly caused by unauthorised access to a computer system are excluded.
      source_document_id: FICT-TRT-006-wording
      location: page 5, paragraph 1
  - section_id: S5
    title: Endorsements
    clauses:
    - clause_id: C41
      title: Partial reversal endorsement
      text: Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.
      source_document_id: FICT-TRT-006-wording
      location: page 6, paragraph 1
  - section_id: S6
    title: Event aggregation
    clauses:
    - clause_id: C11
      title: Event aggregation
      text: The event clause defines one event as all losses within 48 consecutive hours.
      source_document_id: FICT-TRT-006-wording
      location: page 3, paragraph 2
  layers:
  - layer_id: L1
    section_id: S1
    currency: USD
    retention: null
    limit:
      amount: '8000000.00'
      currency: USD
    share_percent: '75'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  notice_rules:
  - trigger: loss_date
    period_days: 21
    clause_id: C1
---

# FICT-TRT-006

Cedent: CED-B - Example Cedent B Ltd (fictional)

## Version 2024-01

### S1 General conditions

C1. Notice of loss shall be given within 21 days.

C30. The limit for layer L1 is USD 8000000.00 and that currency governs payment.

#### Schedule statement A3

The schedule records the layer L1 limit as EUR 8000000.00.

### S2 Loss occurrence

C10. A loss occurrence comprises all losses arising from one event during a continuous period of 72 hours.

### S4 Exclusions

C40. Losses directly caused by unauthorised access to a computer system are excluded.

### S5 Endorsements

C41. Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.

### S6 Event aggregation

C11. The event clause defines one event as all losses within 48 consecutive hours.

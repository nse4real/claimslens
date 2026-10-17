---
contract_id: FICT-FAC-001
placement_basis: facultative
structure_type: excess_of_loss
cedent_name: Example Cedent D Ltd (fictional)
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
      text: Notice shall be given promptly after the cedent's claims committee receives a loss advice.
      source_document_id: FICT-FAC-001-wording
      location: page 2, paragraph 1
    - clause_id: C30
      title: Authoritative layer limit
      text: The limit for layer L1 is USD 1000000.00 and that currency governs payment.
      source_document_id: FICT-FAC-001-wording
      location: page 2, paragraph 2
  - section_id: S3
    title: Claims cooperation
    clauses:
    - clause_id: C20
      title: Conflicting notice term
      text: Notwithstanding the general conditions, notice of loss shall be given within 14 days of the loss date.
      source_document_id: FICT-FAC-001-wording
      location: page 4, paragraph 1
  - section_id: S4
    title: Exclusions
    clauses:
    - clause_id: C40
      title: Computer-system exclusion
      text: Losses directly caused by unauthorised access to a computer system are excluded.
      source_document_id: FICT-FAC-001-wording
      location: page 5, paragraph 1
  - section_id: S5
    title: Endorsements
    clauses:
    - clause_id: C41
      title: Partial reversal endorsement
      text: Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.
      source_document_id: FICT-FAC-001-wording
      location: page 6, paragraph 1
  layers:
  - layer_id: L1
    section_id: S1
    currency: USD
    retention:
      amount: '250000.00'
      currency: USD
    limit:
      amount: '1000000.00'
      currency: USD
    share_percent: '100'
    inception: '2024-01-01'
    expiry: '2024-12-31'
  notice_rules:
  - trigger: other
    trigger_description: Receipt of a loss advice by the cedent's claims committee.
    period_days: null
    clause_id: C1
---

# FICT-FAC-001

Cedent: CED-D - Example Cedent D Ltd (fictional)

## Version 2024-01

### S1 General conditions

C1. Notice shall be given promptly after the cedent's claims committee receives a loss advice.

C30. The limit for layer L1 is USD 1000000.00 and that currency governs payment.

#### Schedule statement A3

The schedule records the layer L1 limit as EUR 1000000.00.

### S3 Claims cooperation

C20. Notwithstanding the general conditions, notice of loss shall be given within 14 days of the loss date.

### S4 Exclusions

C40. Losses directly caused by unauthorised access to a computer system are excluded.

### S5 Endorsements

C41. Endorsement E1 returns cover for losses from unauthorised access at named offices, but does not state whether associated business interruption is included.

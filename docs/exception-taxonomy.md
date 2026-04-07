# Exception Taxonomy

Initial bounded taxonomy:

- `payout_mismatch`
- `missing_document`
- `duplicate_record_risk`
- `provider_failure`
- `unknown`

## Notes

This taxonomy should stay intentionally small at first.

Phase 3 AI classification normalizes into this same bounded taxonomy, but it does so additively:
- the original `exception_type` on the exception case remains source input
- AI classification is stored separately with provider/model/prompt metadata
- operators can compare the source exception type and AI-normalized type directly

The first goal is to prove:
- explicit exception classification
- workflow coordination
- remediation planning
- bounded, inspectable AI behavior

Do not expand the taxonomy casually until the first workflow path is complete.

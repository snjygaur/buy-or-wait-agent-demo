# Chat Transcript (Abridged Development Record)

This file records the development decisions used for the Buy or Wait? submission.

## Requirements fixed at the start
- Build against `problem_statement.md` and the participant-facing dataset only.
- Produce one row per request with the exact required eight output columns.
- Preserve the starter repository structure and avoid unnecessary rewrites.
- Prefer a deterministic/local runtime with no paid LLM/API dependency.
- Verify the implementation against the 25 public solved examples and validate all 250 final rows.

## Dataset inspection
The complete starter repository was inspected. The dataset contains 250 evaluation requests, 25 solved sample requests, financial profiles, 25k+ financial events, dated FX rates, payment options, 215 messages, 16 evidence images, and the blank output template.

## Implementation decisions
1. `code/main.py` loads all participant-facing files.
2. Blank event amounts are recovered from the supplied PNG evidence using local OCR, with deterministic fallbacks for OCR errors on the supplied documents.
3. Cash-state rules exclude failed, cancelled, and unrealized records; explicit internal-account transfers are neutralized.
4. Foreign-currency events use the supplied settlement-date exchange rate.
5. Relevant payroll/rent/service-provider messages are interpreted locally.
6. Recurring structural obligations are projected and protected variable spending is forecast conservatively.
7. A 90-day minimum-balance simulation is used for safe capacity and payment-plan validation.
8. Full payment, partial payment, supplied installment options, waiting, and permitted flexible spending changes are evaluated under the user's preferences.
9. The final output is generated deterministically without runtime model/API calls.

## Verification
- `python3 code/main.py` completed successfully on all 250 requests.
- `python3 code/evaluation/validate_output.py` passes the required schema, row count, amount bounds, allowed values, and partial-payment invariants.
- The public 25-request examples were used as a behavioral check; the implementation matched 20/25 payment-method labels and 18/25 status labels during local validation. Public examples were not hardcoded as evaluation labels.

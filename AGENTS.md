# Which rules must a coding agent follow in this repository?

## Which rules has our team set?

- Never edit `src/contract.py`; it is the client's scoring rule and every method must use it unchanged.
- Keep `is_canceled` as the prediction target only; never include it or scoring-only fields in model inputs.
- Preserve exact duplicate rows and keep every cleaning or filtering choice, reason, and row count in `docs/DECISIONS.md`.
- Use the chronological train, choose, and proof periods from `src/contract.py`; choose settings on choose and touch proof only for the final evaluation.
- Apply the team's recorded scoring-population filters consistently, and state that results exclude 827 rows; do not compare costs from different populations as if they were equivalent.
- Report the current 17-feature timing honestly: it contains seven Bin 2 fields and `country` in Bin 3, so it is not a verified booking-time-only set.
- Make the nightly command load the committed fitted predictor and frozen buffer; never retrain when generating the revenue-manager table.
- Keep oversell recommendations whole, non-negative, and show the expected cancellations and buffer used for each hotel-night.

## Which general coding guidelines apply?

- Think through the data flow and assumptions before changing code; state unresolved choices explicitly.
- Prefer the simplest implementation that meets the stated requirement.
- Make focused changes and preserve unrelated work.
- Define success in terms of the requested output and check that output directly.

These concise principles summarize the general guidance referenced in `docs/AI_WORKFLOW.md`.

# What lives in src, and who writes it?

| File | Status | Owner | Its one job |
|---|---|---|---|
| `data.py` | Given | | Download the bookings and read them exactly as exported |
| `contract.py` | Given, never edited | | The client's scoring rule |
| `features.py` | Yours | Data Lead | Clean the bookings and return the columns your methods may use, with every choice logged in `docs/DECISIONS.md` |
| `backtest.py` | Yours | Model Lead | Fit every method on the train period, choose each buffer on the choose period, run the proof once, print the method table, and save the chosen method and its buffer to `models/`, which you commit |
| `nightly.py` | Yours | Build Lead | Read a bookings file and the saved method, and write the oversell table for the nights asked for |

The project ends with these two commands working from a fresh Codespace. Commit `models/` after the final `backtest.py` run, so that `nightly.py` runs from a fresh checkout without retraining, which is how slide 7 runs live:

```bash
python src/backtest.py
python src/nightly.py --from 2017-08-18 --nights 14
```

`python src/backtest.py --skip-proof` repeats train/choose selection and saves `models/chosen_policy.joblib` without scoring proof. Use the default command only for the final backtest, because it also scores the proof period.

## What does `nightly.py` expect from the backtest?

`src/backtest.py` saves `models/chosen_policy.joblib`. The dictionary contains `method`, the whole-room `buffer`, ordered `feature_columns`, the fitted `preprocessor` and `estimator` for a learned method, and the training-rate tables for the flat and lookup rules. `src/nightly.py` reads that saved policy and applies the selected method without fitting or changing it. The chosen buffer is selected on the choose period and frozen before proof. Both commands must use the same floor rule: `max(0, floor(expected cancellations - buffer))`.

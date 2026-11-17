# Feature-timing EDA: 9 versus 17 features

## What the comparison says

- Adding the seven Bin 2 features moves proof AUC by **+0.0290** (paired-bootstrap 95% CI +0.0264 to +0.0322).
- Adding `country` (Bin 3) after those moves AUC by **+0.0482** (95% CI +0.0437 to +0.0523).
- The total 17-versus-9 proof AUC gain is **+0.0772** (paired-bootstrap 95% CI +0.0731 to +0.0817).
- The paired intervals are entirely above zero on this historical holdout; they do not establish that those values were available in their final form when the booking was first made.

## Method

Prepared population: 118,563 of 119,390 rows; 827 excluded by the recorded filters. AUC uses the same chronological train/proof split, training only before 2016-07-01 and evaluating from 2017-01-01. The current 9-feature model, the 16-feature model (9 + 7 Bin 2), and the historical 17-feature model (16 + country) all use the same frozen XGBoost settings selected on choose: depth 4, learning rate 0.05, 200 trees, seed 42.
The random-split score is a separate stratified 80/20 diagnostic (seed 42), not proof.
Confidence intervals use 500 stratified bootstrap resamples. For the 9/16/17 chronological models, each bootstrap sample is paired across the same proof rows; the random model has its own random-holdout interval.

## Why the 9-feature rule remains the project choice

The project requirement is a cancellation prediction at booking time. The 17-feature set adds seven amendable Bin 2 fields and `country`, classified Bin 3. Those fields can carry useful signal in this historical table, which explains the higher AUC, but the result is not a clean booking-time performance estimate. The 9-feature set follows the project's Bin 1 rule and avoids presenting later or changeable values as known at the decision time.

## Important limitation

This analysis cannot prove the exact value a hotel had at the original booking time. Antonio et al. (2019) describe values extracted from booking change logs relative to the day before arrival. The 9-feature timing classification is therefore the safer project rule, not timestamp-level proof. Production use needs point-in-time booking snapshots or a validated event history. Bootstrap intervals are conditional on these frozen models and this one historical proof sample; they do not account for repeated analysis of the same proof period.

Source: project `data/hotels.csv`; feature timing register in `docs/COLUMNS.md`; Antonio, N., de Almeida, A., & Nunes, L. (2019), [Hotel booking demand datasets](https://pmc.ncbi.nlm.nih.gov/articles/PMC6297060/).
Reproduce: `python evidence/feature_timing_eda.py`.

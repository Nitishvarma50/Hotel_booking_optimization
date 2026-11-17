# Choose-period candidate feature screen

## Purpose

This is an exploratory screen for which individual columns might improve cancellation ranking or the oversell decision. It does not change the approved nine-feature model.

## Method

The shared cleaning filters produced 118,563 rows from 119,390; 827 were excluded. Models were fit on the chronological train period (48,747 rows) and compared on choose (29,307 rows). The proof period was not read or scored. We used the existing frozen XGBoost settings and added each registered Bin 2/Bin 3 candidate individually to the same nine Bin 1 inputs. For each feature set, the choose buffer was selected using the project's cost rule and walk ceiling. The fixed k=4 metrics are retained as a secondary diagnostic.
Baseline on choose: AUC 0.7468; cost €1,563,968.36; 9.82 walks per 1,000; ceiling met: True.

## Highest AUC lifts from adding one column

- `country` (Bin 3): AUC 0.8245 (+0.0777); choose-selected k=1; cost saving €248,644.
- `total_of_special_requests` (Bin 2): AUC 0.8044 (+0.0576); choose-selected k=2; cost saving €153,472.
- `lead_time` (Bin 2): AUC 0.7749 (+0.0282); choose-selected k=9; cost increase €270,191.
- `deposit_type` (Bin 2): AUC 0.7681 (+0.0214); choose-selected k=2; cost saving €291,561.
- `required_car_parking_spaces` (Bin 2): AUC 0.7672 (+0.0204); choose-selected k=4; cost saving €16,491.

## Largest choose-cost savings after selecting each buffer

- `deposit_type` (Bin 2): AUC lift +0.0214; k=2; cost saving €291,561; 8.52 walks per 1,000.
- `country` (Bin 3): AUC lift +0.0777; k=1; cost saving €248,644; 8.57 walks per 1,000.
- `total_of_special_requests` (Bin 2): AUC lift +0.0576; k=2; cost saving €153,472; 9.39 walks per 1,000.
- `stays_in_week_nights` (Bin 2): AUC lift +0.0094; k=4; cost saving €41,068; 9.33 walks per 1,000.
- `stays_in_weekend_nights` (Bin 2): AUC lift +0.0052; k=4; cost saving €19,365; 9.17 walks per 1,000.

## Business interpretation

AUC lift is not the same as a better operating decision. Review the cost and walk-ceiling columns alongside AUC. These are choose-period screening results, not final performance claims. A candidate only belongs in a booking-time model if its value is verified as available at booking time. The project data article says feature values were checked against booking change logs relative to the day before arrival, so this published table cannot verify original booking-time values. The 9 Bin 1 rule remains the defensible current choice; the most useful next operational test is to capture timestamped PMS snapshots for any proposed new column.

Practical shortlist for timestamped validation: `deposit_type` and `total_of_special_requests` both improved choose AUC and reduced choose-period cost after applying the walk-ceiling rule. `country` gave the largest AUC lift, but is Bin 3 and should not be used for a booking-time decision without a booking-time snapshot. `lead_time` improved AUC but increased choose cost after its buffer was selected.

`reservation_status` and `reservation_status_date` were excluded because they describe final reservation outcomes; `is_canceled` is the target; `adr` is scoring-only. The correlation heatmap's Pearson values for nominal categories should not be treated as feature-importance scores.

Reproduce: `python evidence/candidate_feature_screen.py`. Full row-level results: `evidence/candidate_feature_screen.csv`.

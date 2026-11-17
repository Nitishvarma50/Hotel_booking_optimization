# Where do our screenshots go?

Every number on a slide needs a screenshot that shows the line of code and the output that produced it. Save each one here as `slideNN_what.png`, for example `slide05_method_table.png`, and commit it before Friday's deadline.

## Data Lead slide evidence

- `slide04_column_timing.png` shows the timing-audit source and the three-bin / selected-feature counts for slide 4.
- `feature_timing_eda.png` compares 9-, 16- and 17-feature AUCs and timing-bin counts; reproduce it with `python evidence/feature_timing_eda.py`.
- `candidate_feature_screen.png` ranks additional columns on the choose period by AUC lift and choose-selected cost; the proof period is not used. Reproduce it with `python evidence/candidate_feature_screen.py`; see the paired CSV and Markdown report beside it.
- `slide09_ai_benchmark_branch.png` shows the published `ai-benchmark` branch and its saved proof-period output for slide 9. The benchmark code and full results live on that branch.

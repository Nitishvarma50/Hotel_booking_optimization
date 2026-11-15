# What did the AI build get wrong, and what did it expose in ours?

**Owner:** Data Lead. **Challenger:** Build Lead. **When:** started on Thursday, finished on Friday.

Compare your build on `main` with the AI build on the `ai-benchmark` branch, row by row. Every cell points to a file and a line, or to a log excerpt. "Same" is an acceptable verdict when it is true.

| Row | Our build | AI build | Verdict |
|---|---|---|---|
| What counts as a cancellation, and which bookings are scored | `is_canceled` target; filters ADR < 0, ADR > 1,000, zero nights, zero guests before scoring (`src/features.py`, `docs/DECISIONS.md`) | `is_canceled`; all 119,390 source rows per `ai_benchmark/PLAN_AI.md` | Different scoring populations: 118,563 vs 119,390; do not compare costs directly |
| Unit of decision (night or booking) | Hotel-night per `docs/EVALUATION_CONTRACT.md` | Hotel-night per `ai_benchmark/PLAN_AI.md` and `src/contract.py` | Same |
| Columns used, and the bin each sits in | Team's 17: 9 Bin 1, 7 Bin 2, 1 Bin 3 (`src/features.py`, `docs/COLUMNS.md`) | Benchmark's 18: 9 Bin 1, 9 Bin 2, 0 Bin 3 (`ai_benchmark/run.py`, `docs/COLUMNS.md`) | Different features; both include Bin 2, and our final rule also includes `country` (Bin 3) |
| Split (time or random), and where the buffer was chosen | Our equivalent method backtest is not in this branch yet | Chronological split; buffer selected on choose (`ai_benchmark/run.py`) | AI run is available; no like-for-like own backtest yet |
| Baselines run before any model | No `src/backtest.py` in this branch | Flat hotel rate and lookup, then logistic regression and random forest (`ai_benchmark/RESULT.md`) | AI exposes that our method comparison remains to be built by the Model Lead |
| Walk ceiling respected on the choose period and reported on proof | Awaiting our backtest | All four methods met choose ceiling; proof walks range 0.08–6.70 per 1,000 (`ai_benchmark/RESULT.md`) | AI meets the ceiling on its source population |
| Euros, rooms and walks per 1,000 on the proof period | Awaiting our backtest | Random forest: €3,510,962.91, 7,222 empty rooms, 105 walks, 4.21 per 1,000 (`ai_benchmark/RESULT.md`) | Not directly comparable because population and features differ |
| Runs end to end with one command | Our own `src/backtest.py` is not present in this branch | `python ai_benchmark/run.py` writes the comparison and August 18–31 table | AI benchmark ran; our production method command remains Model Lead/Build Lead work |
| Lines of code a team member can explain | Data prep and filters: `src/features.py` | Benchmark pipeline: `ai_benchmark/run.py` | Review both before presenting; AI's booking-time assumption conflicts with Bin 2 audit |

## Which gaps in our build did the AI build expose?

_Up to three, each naming a file and line in our build, or an excerpt from a log. If you found none, say so and name the file that shows it._

The AI benchmark exposed that our current branch has no end-to-end method backtest (`src/README.md` assigns `src/backtest.py` to the Model Lead, but that file is absent), so we cannot compare the chosen 17-feature rule's proof cost yet. It also made the population decision visible: our approved filters remove 827 rows before scoring (`docs/DECISIONS.md`), while the approved AI plan scores all 119,390 source rows (`ai_benchmark/PLAN_AI.md`).

## Which mistakes did the AI build make that ours did not?

_Up to three, each naming a file and line on the `ai-benchmark` branch. If you found none, say so and name the file that shows it._

The benchmark describes its inputs as booking-time fields, but 9 of its 18 features are Bin 2 amendable under our audit (`ai_benchmark/run.py`, `docs/COLUMNS.md`). It also scores the unfiltered source population after our team selected a filtered scoring population (`ai_benchmark/PLAN_AI.md`, `docs/DECISIONS.md`). These are comparison limitations; the AI run followed its approved plan.

## What would we take from the AI build, and what would we never ship?

Keep the AI benchmark's reproducible one-command comparison and nightly CSV output (`ai_benchmark/run.py`); do not use its AUC as a substitute for the Model Lead's three slide-4 AUCs (`ai_benchmark/RESULT.md`, `docs/COLUMNS.md`). The result is useful as a separate baseline, but do not present it as an evaluation of our final 17-feature rule because the population and inputs differ (`docs/DECISIONS.md`, `src/features.py`).

<!-- answer:2 -->

# How do we get from a first test to something the client can run?

**Owner:** Build Lead. Hours are planning estimates; fill actual hours as the team works. Proof-period values are recorded in `docs/DECISIONS.md` after the nine-feature run.

| Stage | What is built | Owner | Hours planned | Hours used | Done when | Evidence file |
|---|---|---|---:|---:|---|---|
| POC | Flat rule, lookup, and at least two learned methods; choose buffers without using proof | Model Lead | 9 (estimate) | Not recorded | One backtest command prints the same-contract method table and ceiling status; chosen artifact saved | `src/backtest.py`, `models/chosen_policy.joblib`, `evidence/poc_table.png` |
| MVP | CLI reads bookings and saved predictor/buffer, then writes the requested hotel-night recommendations | Build Lead | 8 (estimate) | Not recorded | `python src/nightly.py --from 2017-08-18 --nights 14` writes and prints the table without retraining; it excludes target/scoring fields from inputs and discloses feature timing. The current rule uses nine Bin 1 fields; original booking-day snapshots remain a production data requirement. | `src/nightly.py`, `evidence/slide07_nightly_run.png` |
| Final | Integration, architecture and operational caveat; compare buffer choices if the team has four members | Build Lead with Model and Data Leads | 5 (estimate) | Not recorded | Fresh checkout can run the committed artifact; proof values are reproducible; full-book caveat and roadmap are presented | `docs/PRD.md`, `docs/architecture.svg`, `docs/ROADMAP.md`, `evidence/slide07_architecture.png` |

The earlier 17-feature decision has been superseded by the nine-feature first-bin model. The CSV does not guarantee original booking-day snapshots, so verify point-in-time values before production.

## What would production add that the MVP leaves out?

| Addition | Why it matters | Owner | Hours (estimate) |
|---|---|---|---:|
| Timestamped booking snapshot and target-free inference preparation | Lets the tool use only reservations actually known on the morning it runs | Data Lead + Build Lead | 16 |
| PMS export/import, authentication, audit trail and manual override | Makes recommendations usable and reviewable in hotel operations | Build Lead | 24 |
| Drift, calibration and walk-rate monitoring by hotel and season | Detects when the chosen model or buffer stops meeting the ceiling | Model Lead | 16 |
| Controlled shadow pilot with rollback | Tests recommendations before they influence live inventory | Client Lead + Model Lead | 20 |

## What did we cut, and why?

- Live PMS integration and automatic inventory changes: no operational feed, capacity data, or approval workflow is supplied.
- Guest clustering: no evidence yet that segments change the hotel-night oversell count or reduce cost under the ceiling.
- AI benchmark, comparison, and chat-index tasks: excluded by the team's scope decision; they are not MVP dependencies.
- Automatic retraining: the on-stage command must load a frozen, committed model and buffer so the run is repeatable.

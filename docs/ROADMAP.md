# What happens after this week?

**Owner:** Build Lead. Hours below are estimates for planning, not measured effort or guaranteed savings.

| Week | What we would build next | Why it matters to the client, with a measurable target | Owner | Hours |
|---|---|---|---|---:|
| 7 | Build a timestamped, target-free booking snapshot and remove Bin 2/Bin 3 inputs from the deployable rule | The morning run must use only information actually available then; target is 0 Bin 2 and 0 Bin 3 model inputs | Data Lead + Build Lead | 16 |
| 8 | Run the tool in shadow mode on both hotels and compare recommendations with the existing flat rule | Verify the walk ceiling stays at or below 10 per 1,000 arrivals before changing inventory | Model Lead + Client Lead | 20 |
| 9 | Add PMS file integration, human override logging, monitoring and rollback | Every recommendation should be traceable; alert before a hotel's rolling walk rate exceeds 10 per 1,000 | Build Lead + Model Lead | 24 |

These are proposed acceptance targets, not results from a completed pilot.

## Which production additions come with it?

| Addition | Owner | Hours |
|---|---|---:|
| Timestamped reservation snapshot and target-free feature preparation | Data Lead + Build Lead | 16 |
| PMS integration, user access, overrides and audit log | Build Lead | 24 |
| Per-hotel calibration, drift and walk-rate monitoring with rollback | Model Lead | 16 |
| Shadow pilot and client acceptance review | Client Lead + Model Lead | 20 |

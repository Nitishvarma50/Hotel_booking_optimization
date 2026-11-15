# AI benchmark plan

**Status:** Draft awaiting team approval. No benchmark code has been written yet.

## Prediction

Predict `is_canceled` for each booking, where 1 includes cancellations and no-shows. Convert booking probabilities into an oversell count for each hotel and arrival night; the decision and evaluation unit is the hotel-night.

## Inputs

Use booking-record fields that are intended to be available when a booking is made:

- Hotel and booking timing: `hotel`, `lead_time`, `arrival_date_year`, `arrival_date_month`, `arrival_date_week_number`, `arrival_date_day_of_month`.
- Stay and booking characteristics: `stays_in_weekend_nights`, `stays_in_week_nights`, `meal`, `market_segment`, `distribution_channel`, `is_repeated_guest`, `previous_cancellations`, `previous_bookings_not_canceled`, `reserved_room_type`, `agent`, `company`, and `customer_type`.

Do not use `is_canceled` as an input. Keep `adr` and stay nights available for the scoring contract, but do not use them to predict cancellation. Exclude `assigned_room_type`, `booking_changes`, `reservation_status`, and `reservation_status_date` because they can reflect events after booking or the outcome. Treat `deposit_type`, `days_in_waiting_list`, `country`, parking spaces, and special requests as uncertain timing fields and exclude them from the primary model. The published rows may contain later amendments; report this as a point-in-time limitation rather than claiming the exported values are original booking-time snapshots.

## Bookings scored and time split

Use the bookings in `data/hotels.csv`, preserving the source scoring population for the primary comparison. Derive `arrival_date` from the year, month, and day fields and derive `nights` from weekend plus week nights. Follow `src/contract.py`: train on arrivals before 1 July 2016, choose settings from 1 July through 31 December 2016, then run proof once on arrivals from 1 January through 31 August 2017. Do not shuffle the primary evaluation split.

## Methods and comparisons

Compare the client's hotel-level flat cancellation-rate rule with a lookup rule and two learned cancellation models:

1. Flat rule: each hotel's cancellation rate on train, multiplied by each night's bookings, less a fixed safety buffer.
2. Lookup: cancellation rates by hotel, market segment, distribution channel, and lead-time band, estimated on train with a documented fallback for sparse groups.
3. Logistic regression with categorical encoding and numeric scaling, fit on train.
4. Random forest classifier using the same eligible inputs, fit on train.

Fit model preprocessing on train only. Choose one non-negative whole-room buffer per method on the choose period: evaluate candidate buffers with `src/contract.py`, discard any that exceed 10 walks per 1,000 arrivals, then select the feasible buffer with the lowest cost. Freeze the chosen buffer before proof.

## Probability-to-oversell conversion

For each hotel-night, sum booking-level cancellation probabilities to estimate cancellations. Subtract the chosen buffer, round to a non-negative whole number, and use that as the oversell count. Apply the same conversion and choose-period buffer selection procedure to every method, including the flat rule.

## Report and output

On proof, report cost in euros, empty rooms, walked guests, walks per 1,000 arrivals, ceiling status, and night count for every method, with the client's flat rule as the savings reference. Report AUC as a secondary probability-quality measure and state that it does not select the money rule. Write the selected method's nightly table for 18–31 August 2017 to a CSV, with hotel, arrival night, bookings on the book, expected cancellations, frozen buffer, and oversell count. Make `python ai_benchmark/run.py` print the proof comparison and write that table without changing `src/contract.py`.

"""Run the approved AI benchmark plan against the original source population."""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import contract, data  # noqa: E402

FEATURES = [
    "hotel", "lead_time", "arrival_date_year", "arrival_date_month",
    "arrival_date_week_number", "arrival_date_day_of_month",
    "stays_in_weekend_nights", "stays_in_week_nights", "meal",
    "market_segment", "distribution_channel", "is_repeated_guest",
    "previous_cancellations", "previous_bookings_not_canceled",
    "reserved_room_type", "agent", "company", "customer_type",
]
NUMERIC = [
    "lead_time", "arrival_date_year", "arrival_date_week_number",
    "arrival_date_day_of_month", "stays_in_weekend_nights",
    "stays_in_week_nights", "is_repeated_guest", "previous_cancellations",
    "previous_bookings_not_canceled",
]
CATEGORICAL = [c for c in FEATURES if c not in NUMERIC]
LOOKUP_KEYS = ["hotel", "market_segment", "distribution_channel", "lead_band"]


def _probability_table(train: pd.DataFrame, target: pd.Series, rows: pd.DataFrame) -> np.ndarray:
    """Smoothed lookup rates; groups under 30 use the hotel rate as fallback."""
    train = train.copy()
    rows = rows.copy()
    for frame in (train, rows):
        frame["lead_band"] = pd.cut(
            frame["lead_time"], [-np.inf, 7, 30, 90, 180, np.inf],
            labels=["0-7", "8-30", "31-90", "91-180", "181+"],
        ).astype(str)
    train["_y"] = np.asarray(target, dtype=float)
    hotel_stats = train.groupby("hotel", observed=True)["_y"].agg(["sum", "count"])
    global_rate = float(train["_y"].mean())
    hotel_rate = ((hotel_stats["sum"] + 20 * global_rate) / (hotel_stats["count"] + 20)).to_dict()
    stats = train.groupby(LOOKUP_KEYS, observed=True)["_y"].agg(["sum", "count"])
    out = []
    for key in rows[LOOKUP_KEYS].itertuples(index=False, name=None):
        group = stats.loc[key] if key in stats.index else None
        fallback = hotel_rate.get(key[0], global_rate)
        if group is None or group["count"] < 30:
            out.append(fallback)
        else:
            out.append(float((group["sum"] + 20 * fallback) / (group["count"] + 20)))
    return np.asarray(out, dtype=float)


def _nightly(bookings: pd.DataFrame, probabilities: np.ndarray) -> pd.DataFrame:
    return contract.nightly_table(bookings[contract.REQUIRED], probabilities)


def _choose_buffer(nightly: pd.DataFrame) -> tuple[int, dict]:
    candidates = []
    max_buffer = int(np.ceil(float(nightly["expected"].max())))
    for buffer in range(0, max_buffer + 1):
        oversell = np.rint((nightly["expected"] - buffer).clip(lower=0)).astype(int)
        score = contract.night_cost(nightly, oversell)
        if score["ceiling_met"]:
            candidates.append((score["cost_eur"], buffer, score))
    if not candidates:
        # Zero extra rooms always meets the walk ceiling if there are arrivals.
        raise RuntimeError("No candidate buffer satisfied the walk ceiling on choose.")
    _, buffer, score = min(candidates, key=lambda item: (item[0], item[1]))
    return buffer, score


def _evaluate(name: str, train_bookings: pd.DataFrame, choose_bookings: pd.DataFrame,
              proof_bookings: pd.DataFrame, train_p: np.ndarray, choose_p: np.ndarray,
              proof_p: np.ndarray) -> tuple[dict, pd.DataFrame]:
    choose_nights = _nightly(choose_bookings, choose_p)
    buffer, choose_score = _choose_buffer(choose_nights)
    proof_nights = _nightly(proof_bookings, proof_p)
    oversell = np.rint((proof_nights["expected"] - buffer).clip(lower=0)).astype(int)
    result = contract.night_cost(proof_nights, oversell)
    result.update({"method": name, "buffer": buffer,
                   "choose_cost_eur": choose_score["cost_eur"],
                   "choose_walks_per_1000": choose_score["walks_per_1000"]})
    proof_auc = roc_auc_score(proof_bookings["is_canceled"], proof_p)
    result["proof_auc"] = round(float(proof_auc), 4)
    return result, proof_nights


def main() -> None:
    raw = data.read_raw()
    raw["arrival_date"] = data.arrival_date(raw)
    raw["nights"] = raw["stays_in_weekend_nights"] + raw["stays_in_week_nights"]
    for col in ("country", "agent", "company"):
        if col in raw:
            raw[col] = raw[col].fillna("unknown").astype(str)
    raw["children"] = raw["children"].fillna(0)

    train, choose, proof = contract.split_periods(raw)
    train = train.copy()
    choose = choose.copy()
    proof = proof.copy()
    y_train = train["is_canceled"].astype(int)

    # Hotel flat-rate baseline.
    hotel_rates = train.groupby("hotel")["is_canceled"].mean().to_dict()
    global_rate = float(y_train.mean())
    flat_train = np.array([hotel_rates.get(h, global_rate) for h in train["hotel"]])
    flat_choose = np.array([hotel_rates.get(h, global_rate) for h in choose["hotel"]])
    flat_proof = np.array([hotel_rates.get(h, global_rate) for h in proof["hotel"]])
    results = []
    result, _ = _evaluate("Client flat rate", train, choose, proof,
                          flat_train, flat_choose, flat_proof)
    results.append(result)

    # Lookup rates by hotel, segment, distribution channel and lead-time band.
    lookup_choose = _probability_table(train, y_train, choose)
    lookup_proof = _probability_table(train, y_train, proof)
    result, _ = _evaluate("Lookup", train, choose, proof,
                          flat_train, lookup_choose, lookup_proof)
    results.append(result)

    numeric_pipe = Pipeline([("impute", SimpleImputer(strategy="median")),
                             ("scale", StandardScaler())])
    categorical_pipe = Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                                 ("onehot", OneHotEncoder(handle_unknown="ignore"))])
    preprocessor = ColumnTransformer([
        ("numeric", numeric_pipe, NUMERIC),
        ("categorical", categorical_pipe, CATEGORICAL),
    ])
    models = [
        ("Logistic regression", LogisticRegression(max_iter=2000, solver="saga", random_state=42)),
        ("Random forest", RandomForestClassifier(n_estimators=150, min_samples_leaf=10,
                                                   class_weight="balanced_subsample",
                                                   random_state=42, n_jobs=-1)),
    ]
    for name, estimator in models:
        model = Pipeline([("preprocess", preprocessor), ("model", estimator)])
        model.fit(train[FEATURES], y_train)
        choose_p = model.predict_proba(choose[FEATURES])[:, 1]
        proof_p = model.predict_proba(proof[FEATURES])[:, 1]
        result, _ = _evaluate(name, train, choose, proof,
                              flat_train, choose_p, proof_p)
        results.append(result)

    table = pd.DataFrame(results)[[
        "method", "cost_eur", "empty_rooms", "walked_guests", "walks_per_1000",
        "ceiling_met", "nights", "buffer", "proof_auc",
    ]]
    print(f"Source population: {len(raw):,}; train/choose/proof: "
          f"{len(train):,}/{len(choose):,}/{len(proof):,}")
    print("Proof-period comparison (buffer selected on choose):")
    print(table.to_string(index=False))

    chosen = min((r for r in results if r["ceiling_met"]), key=lambda r: r["cost_eur"])
    chosen_model = chosen["method"]
    if chosen_model == "Client flat rate":
        proof_p = flat_proof
    elif chosen_model == "Lookup":
        proof_p = lookup_proof
    else:
        # Refit the selected estimator to retain its probabilities for the nightly output.
        estimator = dict(models)[chosen_model]
        final_model = Pipeline([("preprocess", preprocessor), ("model", estimator)])
        final_model.fit(train[FEATURES], y_train)
        proof_p = final_model.predict_proba(proof[FEATURES])[:, 1]
    final_nights = _nightly(proof, proof_p)
    final_buffer = chosen["buffer"]
    final_nights["oversell"] = np.rint(
        (final_nights["expected"] - final_buffer).clip(lower=0)
    ).astype(int)
    start, stop = pd.Timestamp("2017-08-18"), pd.Timestamp("2017-09-01")
    output = final_nights.loc[
        (final_nights.index.get_level_values("arrival_date") >= start)
        & (final_nights.index.get_level_values("arrival_date") < stop)
    ].reset_index()
    output["method"] = chosen_model
    output["buffer"] = final_buffer
    output = output.rename(columns={"book": "bookings_on_book",
                                    "expected": "expected_cancellations",
                                    "arrival_date": "arrival_night"})
    output[["hotel", "arrival_night", "bookings_on_book", "expected_cancellations",
            "buffer", "oversell", "method"]].to_csv(ROOT / "ai_benchmark" / "nightly_table.csv", index=False)

    (ROOT / "ai_benchmark" / "RESULT.md").write_text(
        "# AI benchmark result\n\n"
        "Command: `python ai_benchmark/run.py`\n\n"
        f"Source population: {len(raw):,}; train/choose/proof: "
        f"{len(train):,}/{len(choose):,}/{len(proof):,}.\n\n"
        "Branch note: the repository's first commit contains only README.md, so the "
        "benchmark branch is based on the project snapshot d146ae7; this follows the "
        "available project code and is a documented deviation from docs/AI_WORKFLOW.md.\n\n"
        "The benchmark uses the original source population per the approved plan. "
        "This differs from our filtered scoring population (827 rows removed). "
        "The benchmark uses 18 features: 9 Bin 1 and 9 Bin 2, with no Bin 3 country. "
        "It is not booking-time-only under our timing audit. Our team's approved "
        "17-column rule differs and includes 7 Bin 2 fields plus country (Bin 3).\n\n"
        "```text\n" + table.to_string(index=False) + "\n```\n\n"
        f"Selected nightly output method: {chosen_model}; frozen buffer: {final_buffer}.\n",
        encoding="utf-8",
    )
    print(f"Selected method: {chosen_model}; nightly table written to ai_benchmark/nightly_table.csv")


if __name__ == "__main__":
    main()

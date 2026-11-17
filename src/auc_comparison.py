"""Run the three documented feature-timing ROC-AUC comparisons.

Runs A and B fit on the chronological train period and evaluate on proof.
Run C uses a stratified 80/20 random split of the same filtered population.
All runs use the frozen XGBoost settings selected on choose; proof is never
used to select features or tune model settings.
"""

from __future__ import annotations

import sys
import pathlib

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import contract  # noqa: E402
import data  # noqa: E402
import features  # noqa: E402


MODEL_PARAMS = {
    "max_depth": 4,
    "learning_rate": 0.05,
    "n_estimators": 200,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "random_state": 42,
    "n_jobs": -1,
}
RANDOM_TEST_SIZE = 0.20
RANDOM_SEED = 42
HISTORICAL_17_FEATURES = [
    "hotel",
    "lead_time",
    "arrival_date_year",
    "arrival_date_month",
    "arrival_date_week_number",
    "arrival_date_day_of_month",
    "meal",
    "country",
    "market_segment",
    "distribution_channel",
    "is_repeated_guest",
    "previous_cancellations",
    "previous_bookings_not_canceled",
    "reserved_room_type",
    "agent",
    "company",
    "customer_type",
]


def _fit_and_predict(X_train: pd.DataFrame, y_train: pd.Series,
                     X_eval: pd.DataFrame):
    numeric = X_train.select_dtypes(include=["number"]).columns.tolist()
    categorical = [column for column in X_train.columns if column not in numeric]
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("numeric", "passthrough", numeric),
        ]
    )
    train_encoded = preprocessor.fit_transform(X_train)
    eval_encoded = preprocessor.transform(X_eval)
    model = XGBClassifier(**MODEL_PARAMS)
    model.fit(train_encoded, y_train)
    class_one = list(model.classes_).index(1)
    probabilities = model.predict_proba(eval_encoded)[:, class_one]
    return model, probabilities


def _fit_and_auc(X_train: pd.DataFrame, y_train: pd.Series,
                 X_eval: pd.DataFrame, y_eval: pd.Series) -> float:
    _, probabilities = _fit_and_predict(X_train, y_train, X_eval)
    return float(roc_auc_score(y_eval, probabilities))


def run_comparisons(bookings: pd.DataFrame) -> pd.DataFrame:
    """Return A/B proof AUCs and C random-test AUC using the shared preparation."""
    prepared = features.prepare_bookings(bookings)
    train, _, proof = contract.split_periods(prepared)
    target = features.TARGET

    # Run A: current Bin 1 model inputs, fit on train, evaluate on proof.
    first_bin = features.MODEL_FEATURES
    results = [{
        "Run": "A",
        "Features": "First bin only",
        "Split": "Train before 2016-07-01; proof from 2017-01-01",
        "Train rows": len(train),
        "Evaluation rows": len(proof),
        "Feature count": len(first_bin),
        "AUC": _fit_and_auc(
            train[first_bin], train[target], proof[first_bin], proof[target]
        ),
    }]

    # Run B: the project's historical 17-feature set (7 Bin 2 fields plus
    # country in Bin 3), retained as a leakage/timing diagnostic.
    historical_17 = HISTORICAL_17_FEATURES
    results.append({
        "Run": "B",
        "Features": "Historical 17-feature set (7 Bin 2 + country in Bin 3)",
        "Split": "Train before 2016-07-01; proof from 2017-01-01",
        "Train rows": len(train),
        "Evaluation rows": len(proof),
        "Feature count": len(historical_17),
        "AUC": _fit_and_auc(
            train[historical_17], train[target],
            proof[historical_17], proof[target],
        ),
    })

    # Run C: same timing-safe inputs, but random stratified holdout for comparison.
    random_train, random_test = train_test_split(
        prepared,
        test_size=RANDOM_TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=prepared[target],
    )
    results.append({
        "Run": "C",
        "Features": "First bin only",
        "Split": "Stratified random 80/20; seed 42",
        "Train rows": len(random_train),
        "Evaluation rows": len(random_test),
        "Feature count": len(first_bin),
        "AUC": _fit_and_auc(
            random_train[first_bin], random_train[target],
            random_test[first_bin], random_test[target],
        ),
    })
    return pd.DataFrame(results)


def main() -> int:
    raw = data.read_raw()
    results = run_comparisons(raw)
    print(f"XGBoost settings (frozen from choose): {MODEL_PARAMS}")
    print(f"Prepared population: {len(features.prepare_bookings(raw)):,} rows")
    print(results.to_string(index=False, formatters={"AUC": "{:.4f}".format}))
    print("\nRun B is a leakage/timing diagnostic; Run C is a random-split diagnostic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare cancellation methods, choose buffers on the choose period, and prove once.

Run from the project root with: python src/backtest.py

The script uses the nine Bin 1 features listed in src/features.py. Its timing caveat is
recorded in docs/DECISIONS.md and docs/COLUMNS.md. Do not change settings after
inspecting proof results.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier


PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import contract  # noqa: E402
import data  # noqa: E402
import features  # noqa: E402


BUFFER_DESCRIPTION = "whole rooms subtracted from expected cancellations"


def _binary_probability(model, X):
    """Return probabilities for cancellation class 1, independent of class order."""
    classes = list(model.classes_)
    if 1 not in classes:
        raise ValueError("The fitted model does not contain cancellation class 1.")
    return model.predict_proba(X)[:, classes.index(1)]


def _night_scores(scoring, probabilities, buffer):
    """Score a fixed buffer using the client's contract."""
    nights = contract.nightly_table(scoring, probabilities)
    oversell = np.floor(nights["expected"] - buffer).clip(lower=0).astype(int)
    return contract.night_cost(nights, oversell)


def _buffers_for(nightly_table):
    """All integer buffers from zero through one above the maximum expectation."""
    last = int(np.ceil(nightly_table["expected"].max())) + 1
    return range(last + 1)


def _rate_probabilities(train_X, train_y, score_X, keys):
    """Estimate cancellation rates from training rows with hotel/global fallbacks."""
    train = train_X[list(keys)].copy()
    score = score_X[list(keys)].copy()
    for key in keys:
        if train[key].isna().any() or score[key].isna().any():
            train[key] = train[key].fillna("unknown").astype(str)
            score[key] = score[key].fillna("unknown").astype(str)
    train["_cancelled"] = np.asarray(train_y)

    group_rates = train.groupby(list(keys), dropna=False)["_cancelled"].mean()
    if len(keys) == 1:
        rates = score[keys[0]].map(group_rates)
    else:
        score_keys = pd.MultiIndex.from_frame(score[list(keys)])
        rates = pd.Series(group_rates.reindex(score_keys).to_numpy(), index=score.index)

    if "hotel" in keys and len(keys) > 1:
        hotel_rates = train.groupby("hotel", dropna=False)["_cancelled"].mean()
        rates = rates.fillna(score["hotel"].map(hotel_rates))

    return rates.fillna(float(np.mean(train_y))).to_numpy(), group_rates


def _fit_candidate(name, params, X_train, y_train):
    if name == "Decision Tree":
        model = DecisionTreeClassifier(
            **params,
            class_weight="balanced",
            random_state=42,
        )
    elif name == "XGBoost":
        model = XGBClassifier(
            **params,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown learned method: {name}")
    model.fit(X_train, y_train)
    return model


def main(run_proof=True):
    raw = data.read_raw()
    bookings = features.prepare_bookings(raw)
    train_df, choose_df, proof_df = contract.split_periods(bookings)

    X_train, y_train, score_train = features.split_model_inputs(train_df)
    X_choose, y_choose, score_choose = features.split_model_inputs(choose_df)
    X_proof, y_proof, score_proof = features.split_model_inputs(proof_df)

    print("========== DATA SPLIT ==========")
    print(f"Prepared bookings: {len(bookings):,}")
    print(f"Train: {len(X_train):,}; choose: {len(X_choose):,}; proof: {len(X_proof):,}")
    print(f"Model features ({len(features.MODEL_FEATURES)}): {features.MODEL_FEATURES}")

    numeric = X_train.select_dtypes(include=["number"]).columns.tolist()
    categorical = [column for column in X_train.columns if column not in numeric]
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("numeric", "passthrough", numeric),
        ]
    )
    X_train_p = preprocessor.fit_transform(X_train)
    X_choose_p = preprocessor.transform(X_choose)
    X_proof_p = preprocessor.transform(X_proof)

    if not (X_train_p.shape[0] == len(y_train)
            and X_choose_p.shape[0] == len(score_choose)
            and X_proof_p.shape[0] == len(score_proof)):
        raise ValueError("Feature, target, and scoring rows are not aligned.")

    candidate_specs = [
        ("Decision Tree", {"max_depth": 6, "min_samples_leaf": 50}),
        ("Decision Tree", {"max_depth": 8, "min_samples_leaf": 50}),
        ("Decision Tree", {"max_depth": 8, "min_samples_leaf": 100}),
        ("Decision Tree", {"max_depth": 12, "min_samples_leaf": 100}),
        ("XGBoost", {"max_depth": 3, "learning_rate": 0.05, "n_estimators": 200}),
        ("XGBoost", {"max_depth": 4, "learning_rate": 0.05, "n_estimators": 200}),
        ("XGBoost", {"max_depth": 3, "learning_rate": 0.1, "n_estimators": 300}),
        ("XGBoost", {"max_depth": 4, "learning_rate": 0.1, "n_estimators": 300}),
    ]

    flat_choose, flat_rates = _rate_probabilities(
        X_train, y_train, X_choose, ("hotel",)
    )
    lookup_choose, lookup_rates = _rate_probabilities(
        X_train, y_train, X_choose, ("hotel", "market_segment")
    )

    candidate_probabilities = [
        ("Flat rule", "train hotel cancellation rate", flat_choose, None),
        ("Lookup", "train hotel + market_segment rates", lookup_choose, None),
    ]
    fitted_models = {}

    for name, params in candidate_specs:
        model = _fit_candidate(name, params, X_train_p, y_train)
        probability = _binary_probability(model, X_choose_p)
        candidate_id = json.dumps({"method": name, "params": params}, sort_keys=True)
        candidate_probabilities.append((name, params, probability, candidate_id))
        fitted_models[candidate_id] = model

    choose_rows = []
    for name, params, probability, candidate_id in candidate_probabilities:
        nightly = contract.nightly_table(score_choose, probability)
        for buffer in _buffers_for(nightly):
            score = _night_scores(score_choose, probability, buffer)
            choose_rows.append({
                "Model": name,
                "Parameters": params if isinstance(params, str) else json.dumps(params, sort_keys=True),
                "Buffer": int(buffer),
                "Cost (EUR)": score["cost_eur"],
                "Nights": score["nights"],
                "Empty rooms": score["empty_rooms"],
                "Walks": score["walked_guests"],
                "Walks per 1,000": score["walks_per_1000"],
                "Ceiling met": score["ceiling_met"],
                "_candidate_id": candidate_id,
            })

    choose_results = pd.DataFrame(choose_rows)
    eligible = choose_results[choose_results["Ceiling met"]]
    best_by_method = (
        eligible.sort_values("Cost (EUR)")
        .groupby("Model", as_index=False, sort=False)
        .first()
    )
    flat_cost = best_by_method.loc[
        best_by_method["Model"] == "Flat rule", "Cost (EUR)"
    ].iloc[0]
    best_by_method["Saving vs flat (EUR)"] = flat_cost - best_by_method["Cost (EUR)"]
    print("\n========== BEST CHOOSE-PERIOD SETTINGS ==========")
    print(best_by_method.drop(columns="_candidate_id").to_string(index=False))

    if run_proof:
        # Proof is evaluated only after choose settings and buffers have been fixed.
        proof_rows = []
        for _, row in best_by_method.iterrows():
            name = row["Model"]
            candidate_id = row["_candidate_id"]
            if name == "Flat rule":
                probability = _rate_probabilities(X_train, y_train, X_proof, ("hotel",))[0]
            elif name == "Lookup":
                probability = _rate_probabilities(
                    X_train, y_train, X_proof, ("hotel", "market_segment")
                )[0]
            else:
                model = fitted_models[candidate_id]
                probability = _binary_probability(model, X_proof_p)

            score = _night_scores(score_proof, probability, int(row["Buffer"]))
            proof_rows.append({
                "Method": name,
                "Buffer": int(row["Buffer"]),
                "Cost (EUR)": score["cost_eur"],
                "Nights": score["nights"],
                "Empty rooms": score["empty_rooms"],
                "Walks": score["walked_guests"],
                "Walks per 1,000": score["walks_per_1000"],
                "Ceiling met": score["ceiling_met"],
            })

        proof_results = pd.DataFrame(proof_rows)
        proof_flat_cost = proof_results.loc[
            proof_results["Method"] == "Flat rule", "Cost (EUR)"
        ].iloc[0]
        proof_results["Saving vs flat (EUR)"] = proof_flat_cost - proof_results["Cost (EUR)"]
        print("\n========== PROOF RESULTS (FROZEN SETTINGS) ==========")
        print(proof_results.sort_values("Cost (EUR)").to_string(index=False))
    else:
        print("\nProof scoring skipped; train/choose selection only.")

    winner = best_by_method.sort_values("Cost (EUR)").iloc[0]
    winner_name = winner["Model"]
    winner_id = winner["_candidate_id"]
    if winner_name in {"Decision Tree", "XGBoost"}:
        predictor = Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", fitted_models[winner_id]),
        ])
    else:
        raise ValueError(f"No nightly inference adapter is defined for {winner_name}.")

    artifact = {
        "method": winner_name,
        "buffer": {"kind": "rooms", "value": int(winner["Buffer"])},
        "parameters": winner["Parameters"],
        "feature_columns": features.MODEL_FEATURES,
        "predictor": predictor,
    }
    models_dir = PROJECT_DIR / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / "chosen_policy.joblib"
    joblib.dump(artifact, model_path)
    print(f"\nSelected on choose: {winner_name}; k={artifact['buffer']['value']}")
    print(f"Saved policy artifact: {model_path.relative_to(PROJECT_DIR)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-proof",
        action="store_true",
        help="select and save the policy using train/choose only; do not score proof",
    )
    args = parser.parse_args()
    main(run_proof=not args.skip_proof)

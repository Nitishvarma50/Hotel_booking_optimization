"""Write cancellation-aware oversell recommendations from a frozen policy.

The backtest owns fitting and buffer selection. This command only loads the
saved policy, applies it without fitting, and writes one recommendation per
hotel and requested arrival night.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd

import data
import features


ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_BOOKINGS = data.DATA_DIR / data.FILE
DEFAULT_MODEL = ROOT / "models" / "chosen_policy.joblib"
DEFAULT_OUTPUT = ROOT / "outputs" / "nightly_recommendations.csv"
SCORING_ONLY = {"is_canceled", "arrival_date", "adr", "nights"}
RATE_METHODS = {"Flat rule", "Lookup"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create frozen-model hotel-night oversell recommendations."
    )
    parser.add_argument(
        "--from", dest="start_date", required=True,
        help="First arrival date to include (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--nights", type=int, default=14,
        help="Number of consecutive arrival dates to include (default: 14).",
    )
    parser.add_argument(
        "--bookings", type=pathlib.Path, default=DEFAULT_BOOKINGS,
        help=f"Booking CSV (default: {DEFAULT_BOOKINGS}).",
    )
    parser.add_argument(
        "--model", type=pathlib.Path, default=DEFAULT_MODEL,
        help=f"Saved model bundle (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--output", type=pathlib.Path, default=DEFAULT_OUTPUT,
        help=f"Output CSV (default: {DEFAULT_OUTPUT}).",
    )
    return parser


def _read_bookings(path: pathlib.Path) -> pd.DataFrame:
    """Read the provided historical CSV, downloading the default source if needed."""
    resolved = path.expanduser().resolve()
    if resolved == DEFAULT_BOOKINGS.resolve():
        return data.read_raw()
    if not resolved.is_file():
        raise FileNotFoundError(f"Bookings file not found: {resolved}")
    return pd.read_csv(resolved)


def _load_bundle(
    path: pathlib.Path,
) -> tuple[dict, list[str], int, str]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Saved model bundle not found: {path}. Run src/backtest.py first; "
            "nightly.py never trains a model."
        )

    bundle = joblib.load(path)
    if not isinstance(bundle, dict):
        raise ValueError("Saved policy must be a dictionary.")

    missing = {"method", "buffer", "feature_columns"} - set(bundle)
    if missing:
        raise ValueError(f"Model bundle is missing required keys: {sorted(missing)}")

    method = bundle["method"]
    if not isinstance(method, str) or not method.strip():
        raise ValueError("Model bundle method must be a non-empty string.")
    if method not in RATE_METHODS | {"Decision Tree", "XGBoost"}:
        raise ValueError(f"Unsupported saved method: {method}")

    columns = bundle["feature_columns"]
    if not isinstance(columns, (list, tuple)) or not columns or not all(
        isinstance(column, str) for column in columns
    ):
        raise ValueError("feature_columns must be a non-empty ordered list of column names.")
    if len(set(columns)) != len(columns):
        raise ValueError("feature_columns contains duplicates.")
    forbidden = set(columns) & SCORING_ONLY
    if forbidden:
        raise ValueError(f"Target/scoring-only columns cannot be model inputs: {sorted(forbidden)}")
    unknown = set(columns) - set(features.MODEL_FEATURES)
    if unknown:
        raise ValueError(f"Saved model requests columns outside features.MODEL_FEATURES: {sorted(unknown)}")

    try:
        buffer_value = float(bundle["buffer"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Saved buffer must be a whole number of rooms.") from exc
    if not np.isfinite(buffer_value) or buffer_value < 0 or not buffer_value.is_integer():
        raise ValueError("Saved buffer must be a finite, non-negative whole number of rooms.")

    if method in RATE_METHODS:
        for rate_key in ("hotel_rates", "lookup_rates"):
            if not isinstance(bundle.get(rate_key), dict):
                raise ValueError(f"Saved rate-based policy is missing its {rate_key} table.")
        try:
            global_rate = float(bundle.get("global_rate", np.nan))
        except (TypeError, ValueError) as exc:
            raise ValueError("Rate-based policy is missing a valid global_rate fallback.") from exc
        if not np.isfinite(global_rate) or not 0 <= global_rate <= 1:
            raise ValueError("global_rate must be a probability between 0 and 1.")
    else:
        if not callable(getattr(bundle.get("preprocessor"), "transform", None)):
            raise ValueError("Saved learned policy is missing its fitted preprocessor.")
        if not callable(getattr(bundle.get("estimator"), "predict_proba", None)):
            raise ValueError("Saved learned policy is missing its fitted estimator.")

    return bundle, list(columns), int(buffer_value), method


def _probabilities_for_bookings(
    selected: pd.DataFrame, bundle: dict, feature_columns: list[str]
) -> np.ndarray:
    """Apply the saved learned model or training-rate rule without fitting."""
    if selected.empty:
        return np.array([], dtype=float)

    method = bundle["method"]
    if method == "Flat rule":
        rates = bundle["hotel_rates"]
        probabilities = np.array([
            rates.get(hotel, bundle["global_rate"])
            for hotel in selected["hotel"]
        ], dtype=float)
    elif method == "Lookup":
        lookup_rates = bundle["lookup_rates"]
        hotel_rates = bundle.get("hotel_rates") or {}
        fallback = bundle["global_rate"]
        probabilities = np.array([
            lookup_rates.get(
                (hotel, segment), hotel_rates.get(hotel, fallback)
            )
            for hotel, segment in zip(selected["hotel"], selected["market_segment"])
        ], dtype=float)
    else:
        estimator = bundle["estimator"]
        transformed = bundle["preprocessor"].transform(selected[feature_columns])
        raw = np.asarray(estimator.predict_proba(transformed), dtype=float)
        if raw.ndim != 2 or raw.shape[0] != len(selected):
            raise ValueError("Saved estimator returned an invalid probability matrix.")
        classes = np.asarray(getattr(estimator, "classes_", []))
        positive_class = np.flatnonzero(classes == 1)
        if len(positive_class) != 1 or raw.shape[1] <= int(positive_class[0]):
            raise ValueError("Saved estimator must expose exactly one cancellation class labeled 1.")
        probabilities = raw[:, int(positive_class[0])]

    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Saved policy returned probabilities outside [0, 1].")
    return probabilities


def create_recommendations(
    raw_bookings: pd.DataFrame,
    bundle: dict,
    feature_columns: list[str],
    buffer: int,
    start_date: str,
    nights: int = 14,
) -> pd.DataFrame:
    """Return one recommendation for every hotel and requested arrival date."""
    if nights < 1:
        raise ValueError("nights must be at least 1")
    start = pd.Timestamp(start_date).normalize()
    dates = pd.date_range(start, periods=nights, freq="D")

    # The shared cleaning function validates the current project source schema.
    # The outcome column is removed from X below and is never used for scoring here.
    bookings = features.prepare_bookings(raw_bookings)
    missing_features = sorted(set(feature_columns) - set(bookings.columns))
    if missing_features:
        raise ValueError(f"Bookings are missing saved model features: {missing_features}")

    output_keys = {"hotel", "arrival_date"}
    selected_columns = [
        "hotel", "arrival_date",
        *[column for column in feature_columns if column not in output_keys],
    ]
    selected = bookings.loc[
        bookings["arrival_date"].between(dates[0], dates[-1]), selected_columns
    ].copy()

    predictions = _probabilities_for_bookings(selected, bundle, feature_columns)

    scored = selected[["hotel", "arrival_date"]].copy()
    scored["_probability"] = predictions
    scored["_variance"] = predictions * (1.0 - predictions)
    nightly = scored.groupby(["hotel", "arrival_date"]).agg(
        book=("_probability", "size"),
        expected=("_probability", "sum"),
        variance=("_variance", "sum"),
    )
    nightly["spread"] = np.sqrt(nightly.pop("variance"))

    hotels = sorted(bookings["hotel"].dropna().unique().tolist())
    if not hotels:
        raise ValueError("No hotel values remain after preparing the bookings.")
    full_index = pd.MultiIndex.from_product(
        [hotels, dates], names=["hotel", "arrival_date"]
    )
    nightly = nightly.reindex(full_index)
    nightly["book"] = nightly["book"].fillna(0).astype(int)
    nightly[["expected", "spread"]] = nightly[["expected", "spread"]].fillna(0.0)
    nightly["buffer"] = int(buffer)
    nightly["oversell"] = np.floor(
        np.maximum(0.0, nightly["expected"] - nightly["buffer"])
    ).astype(int)
    buffer_reason = f"{int(buffer)}-room fixed"
    nightly["reason"] = nightly.apply(
        lambda row: (
            f"Expected {row['expected']:.2f} cancellations; subtract "
            f"{row['buffer']:.2f} rooms ({buffer_reason}); "
            f"recommend {row['oversell']} extra rooms."
        ),
        axis=1,
    )
    return nightly.reset_index()[
        ["hotel", "arrival_date", "book", "expected", "buffer", "oversell", "reason"]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.nights < 1:
        parser.error("--nights must be at least 1")

    try:
        pd.Timestamp(args.start_date)  # fail early on an invalid date
        raw_bookings = _read_bookings(args.bookings)
        bundle, feature_columns, buffer, method = _load_bundle(args.model)
        table = create_recommendations(
            raw_bookings,
            bundle,
            feature_columns,
            buffer,
            args.start_date,
            args.nights,
        )
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(output, index=False, float_format="%.4f")
        print(f"Method: {method}")
        print(table.to_string(index=False))
        print(f"\nWrote {len(table)} hotel-night rows to {output}")
        return 0
    except Exception as exc:  # present actionable CLI errors without a traceback by default
        print(f"nightly.py: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

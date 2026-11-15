"""Write cancellation-aware oversell recommendations from a frozen model bundle.

The backtest owns fitting and buffer selection. This command only loads the
saved predictor and its frozen buffer, then writes one recommendation per
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
DEFAULT_MODEL = ROOT / "models" / "selected_model.joblib"
DEFAULT_OUTPUT = ROOT / "outputs" / "nightly_recommendations.csv"
SCORING_ONLY = {"is_canceled", "arrival_date", "adr", "nights"}
BUFFER_KINDS = {"rooms", "spread_multiplier"}


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
) -> tuple[object, list[str], dict[str, float | str], str]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Saved model bundle not found: {path}. Run src/backtest.py first; "
            "nightly.py never trains a model."
        )

    bundle = joblib.load(path)
    if not isinstance(bundle, dict):
        raise ValueError("Model bundle must be a dictionary with predictor, feature_columns, and buffer.")

    missing = {"predictor", "feature_columns", "buffer", "method"} - set(bundle)
    if missing:
        raise ValueError(f"Model bundle is missing required keys: {sorted(missing)}")

    predictor = bundle["predictor"]
    if not callable(getattr(predictor, "predict_proba", None)):
        raise ValueError("Saved predictor must expose predict_proba(X).")
    method = bundle["method"]
    if not isinstance(method, str) or not method.strip():
        raise ValueError("Model bundle method must be a non-empty string.")

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

    buffer = bundle["buffer"]
    if not isinstance(buffer, dict) or not {"kind", "value"}.issubset(buffer):
        raise ValueError("buffer must contain kind and value.")
    kind = buffer["kind"]
    if kind not in BUFFER_KINDS:
        raise ValueError(f"buffer kind must be one of {sorted(BUFFER_KINDS)}.")
    value = float(buffer["value"])
    if not np.isfinite(value) or value < 0:
        raise ValueError("buffer value must be a finite, non-negative number.")

    return predictor, list(columns), {"kind": kind, "value": value}, method


def _buffer_by_night(spread: pd.Series, buffer: dict[str, float | str]) -> pd.Series:
    if buffer["kind"] == "rooms":
        return pd.Series(float(buffer["value"]), index=spread.index)
    return spread * float(buffer["value"])


def create_recommendations(
    raw_bookings: pd.DataFrame,
    predictor: object,
    feature_columns: list[str],
    buffer: dict[str, float | str],
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

    if selected.empty:
        predictions = np.array([], dtype=float)
    else:
        probabilities = np.asarray(
            predictor.predict_proba(selected[feature_columns]), dtype=float
        )
        if probabilities.ndim != 2 or probabilities.shape != (len(selected), 2):
            raise ValueError(
                "predict_proba must return an (n_bookings, 2) array; "
                "the cancellation probability is column 1."
            )
        classes = getattr(predictor, "classes_", None)
        if classes is not None:
            positive_class = np.flatnonzero(np.asarray(classes) == 1)
            if len(positive_class) != 1:
                raise ValueError("Saved predictor must have exactly one class labeled 1 (cancelled).")
            predictions = probabilities[:, int(positive_class[0])]
        else:
            predictions = probabilities[:, 1]
        if not np.isfinite(predictions).all() or ((predictions < 0) | (predictions > 1)).any():
            raise ValueError("Predictor returned probabilities outside [0, 1].")

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
    nightly["buffer"] = _buffer_by_night(nightly["spread"], buffer)
    nightly["oversell"] = np.rint(
        np.maximum(0.0, nightly["expected"] - nightly["buffer"])
    ).astype(int)
    if buffer["kind"] == "rooms":
        buffer_reason = f"{float(buffer['value']):.2f}-room fixed"
    else:
        buffer_reason = f"{float(buffer['value']):.2f} x spread"
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
        predictor, feature_columns, buffer, method = _load_bundle(args.model)
        table = create_recommendations(
            raw_bookings,
            predictor,
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

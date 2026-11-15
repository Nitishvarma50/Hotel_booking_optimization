
"""
Feature preparation for the Hotel Overbooking project.

Owner: Data Lead

Responsibilities:
1. Define approved model input columns.
2. Keep the target separate from model inputs.
3. Preserve information required by the client scoring contract.
4. Apply documented data-quality decisions.

Original data is loaded through data.py.
The client scoring contract in contract.py must never be modified.
"""
ṣ
import pandas as pd


# ============================================================
# 1. TEAM-APPROVED PROJECT FEATURE LIST
# ============================================================

# The team confirmed this 17-column list as the intended project feature set.
# The timing audit classifies some of these fields as Bin 2 or Bin 3, so this
# list must not be described as a verified booking-time-only feature set.
#
# deposit_type is excluded pending timing verification.
# The current team-approved set includes Bin 2 and Bin 3 fields; see
# docs/COLUMNS.md for the unresolved booking-time limitation.

MODEL_FEATURES = [
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


# ============================================================
# 2. TARGET VARIABLE
# ============================================================

TARGET = "is_canceled"


# ============================================================
# 3. SCORING INFORMATION
# ============================================================

# These columns are needed for the client's evaluation.
# They are NOT all model input features.

SCORING_COLUMNS = [
    "hotel",
    "arrival_date",
    "is_canceled",
    "adr",
    "nights",
]


# ============================================================
# 4. COLUMN VALIDATION
# ============================================================

def validate_feature_columns(df: pd.DataFrame) -> None:
    """
    Check that all team-approved project features exist.

    Raises an error if a required feature is missing.
    """

    missing = [
        column
        for column in MODEL_FEATURES
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing approved model features: {missing}"
        )


def get_feature_columns(df: pd.DataFrame) -> list:
    """
    Return the team-approved project feature columns.

    The target and scoring-only columns are excluded.
    """

    validate_feature_columns(df)

    return MODEL_FEATURES.copy()


# ============================================================
# 5. DATA CLEANING AND PREPARATION
# ============================================================

def prepare_bookings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare booking data for modelling and evaluation.

    Cleaning decisions:
    - Missing children -> 0
    - Missing country -> 'unknown'
    - Missing agent -> 'unknown'
    - Missing company -> 'unknown'
    - Retain exact duplicate records
    - Remove negative ADR and ADR above 1000
    - Remove zero-night and zero-guest bookings

    Returns a new DataFrame without modifying the original.
    """

    required_columns = [
        "arrival_date_year",
        "arrival_date_month",
        "arrival_date_day_of_month",
        "stays_in_weekend_nights",
        "stays_in_week_nights",
        "adults",
        "children",
        "babies",
        "country",
        "agent",
        "company",
        "adr",
        "is_canceled",
    ]

    missing = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required source columns: {missing}"
        )

    # Work on a copy to protect the original dataset.
    bookings = df.copy()

    # Create a single arrival-date column.
    bookings["arrival_date"] = pd.to_datetime(
        bookings["arrival_date_year"].astype(str)
        + "-"
        + bookings["arrival_date_month"]
        + "-"
        + bookings["arrival_date_day_of_month"].astype(str),
        format="%Y-%B-%d",
    )

    # Calculate the total number of stay nights.
    bookings["nights"] = (
        bookings["stays_in_weekend_nights"]
        + bookings["stays_in_week_nights"]
    )

    # Apply documented missing-value decisions.
    bookings["children"] = bookings["children"].fillna(0)

    for column in ["country", "agent", "company"]:
        bookings[column] = (
            bookings[column]
            .fillna("unknown")
            .astype(str)
        )

    # Apply the team's current scoring-population exclusions. Calculate guest
    # count after imputing missing children so the rule is deterministic.
    guests = (
        bookings["adults"]
        + bookings["children"]
        + bookings["babies"]
    )
    keep = (
        bookings["adr"].ge(0)
        & bookings["adr"].le(1000)
        & bookings["nights"].gt(0)
        & guests.gt(0)
    )
    bookings = bookings.loc[keep].copy()

    return bookings


# ============================================================
# 6. SEPARATE MODEL INPUTS, TARGET AND SCORING DATA
# ============================================================

def split_model_inputs(bookings: pd.DataFrame):
    """
    Separate prepared bookings into:

    X: Team-approved model features (timing caveats are documented in docs/COLUMNS.md).
    y: Cancellation target.
    scoring: Columns required by the client contract.

    All outputs preserve the original row order and index.
    """

    # Validate that approved features exist.
    validate_feature_columns(bookings)

    # Validate target availability.
    if TARGET not in bookings.columns:
        raise ValueError(f"Missing target column: {TARGET}")

    # Validate scoring information.
    missing_scoring = [
        column
        for column in SCORING_COLUMNS
        if column not in bookings.columns
    ]

    if missing_scoring:
        raise ValueError(
            f"Missing scoring columns: {missing_scoring}"
        )

    # Model inputs: the team's approved 17-column project feature list.
    X = bookings[MODEL_FEATURES].copy()

    # Target: actual cancellation outcome.
    y = bookings[TARGET].copy()

    # Scoring data: required by contract.py.
    scoring = bookings[SCORING_COLUMNS].copy()

    return X, y, scoring

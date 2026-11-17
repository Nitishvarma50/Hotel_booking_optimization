"""Create slide-ready evidence for choosing nine timing-safe model features.

The 9, 16 and 17 feature models use identical XGBoost settings and chronological
train/proof rows. The 16 feature run adds the seven Bin 2 columns; the 17 feature
run adds country (Bin 3). A separate random-split run is shown only as a split
diagnostic. No proof result is used to choose features or tune settings.
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import auc_comparison  # noqa: E402
import contract  # noqa: E402
import data  # noqa: E402
import features  # noqa: E402


BOOTSTRAPS = 500
BOOTSTRAP_SEED = 20261117
BIN2_FEATURES = [
    "lead_time",
    "arrival_date_year",
    "arrival_date_month",
    "arrival_date_week_number",
    "arrival_date_day_of_month",
    "meal",
    "reserved_room_type",
]
FEATURE_SETS = {
    "9 · Bin 1 only": features.MODEL_FEATURES,
    "16 · Bin 1 + Bin 2": [
        column for column in auc_comparison.HISTORICAL_17_FEATURES
        if column != "country"
    ],
    "17 · plus country (Bin 3)": auc_comparison.HISTORICAL_17_FEATURES,
}
TIMING_COUNTS = {
    "9 · Bin 1 only": (9, 0, 0),
    "16 · Bin 1 + Bin 2": (9, 7, 0),
    "17 · plus country (Bin 3)": (9, 7, 1),
}


def _bootstrap_auc_and_deltas(y, predictions, n_boot=BOOTSTRAPS):
    """Stratified paired bootstrap: preserve class counts and row pairing."""
    y = np.asarray(y, dtype=int)
    positive = np.flatnonzero(y == 1)
    negative = np.flatnonzero(y == 0)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    auc_samples = {name: [] for name in predictions}
    delta_samples = {"16-9": [], "17-16": [], "17-9": []}

    for _ in range(n_boot):
        sample = np.concatenate([
            rng.choice(positive, size=len(positive), replace=True),
            rng.choice(negative, size=len(negative), replace=True),
        ])
        current = {}
        for name, probability in predictions.items():
            current[name] = roc_auc_score(y[sample], probability[sample])
            auc_samples[name].append(current[name])
        if {"9 · Bin 1 only", "16 · Bin 1 + Bin 2", "17 · plus country (Bin 3)"}.issubset(current):
            delta_samples["16-9"].append(
                current["16 · Bin 1 + Bin 2"] - current["9 · Bin 1 only"]
            )
            delta_samples["17-16"].append(
                current["17 · plus country (Bin 3)"] - current["16 · Bin 1 + Bin 2"]
            )
            delta_samples["17-9"].append(
                current["17 · plus country (Bin 3)"] - current["9 · Bin 1 only"]
            )

    ci = {
        name: tuple(np.quantile(values, [0.025, 0.975]).tolist())
        for name, values in auc_samples.items()
    }
    delta_ci = {
        name: tuple(np.quantile(values, [0.025, 0.975]).tolist())
        for name, values in delta_samples.items()
        if values
    }
    return ci, delta_ci


def run_eda():
    raw = data.read_raw()
    prepared = features.prepare_bookings(raw)
    train, _, proof = contract.split_periods(prepared)
    target = features.TARGET

    proof_predictions = {}
    rows = []
    for name, columns in FEATURE_SETS.items():
        _, probability = auc_comparison._fit_and_predict(
            train[columns], train[target], proof[columns]
        )
        proof_predictions[name] = probability
        rows.append({
            "Model": name,
            "Features": len(columns),
            "Train rows": len(train),
            "Evaluation rows": len(proof),
            "Split": "Chronological proof",
            "AUC": roc_auc_score(proof[target], probability),
        })

    # Run C is intentionally separate: random holdout is a diagnostic, not proof.
    random_train, random_test = train_test_split(
        prepared,
        test_size=auc_comparison.RANDOM_TEST_SIZE,
        random_state=auc_comparison.RANDOM_SEED,
        stratify=prepared[target],
    )
    _, random_probability = auc_comparison._fit_and_predict(
        random_train[features.MODEL_FEATURES],
        random_train[target],
        random_test[features.MODEL_FEATURES],
    )
    random_name = "9 · random holdout"
    rows.append({
        "Model": random_name,
        "Features": len(features.MODEL_FEATURES),
        "Train rows": len(random_train),
        "Evaluation rows": len(random_test),
        "Split": "Stratified random 80/20, seed 42",
        "AUC": roc_auc_score(random_test[target], random_probability),
    })

    proof_ci, delta_ci = _bootstrap_auc_and_deltas(
        proof[target], proof_predictions
    )
    random_ci, _ = _bootstrap_auc_and_deltas(
        random_test[target], {random_name: random_probability}
    )
    ci_by_name = {**proof_ci, random_name: random_ci[random_name]}
    results = pd.DataFrame(rows)
    results["95% CI low"] = results["Model"].map(lambda x: ci_by_name[x][0])
    results["95% CI high"] = results["Model"].map(lambda x: ci_by_name[x][1])
    results["95% CI method"] = "Stratified row bootstrap, 500 replicates"

    ROOT.joinpath("evidence", "feature_timing_eda_metrics.csv").write_text(
        results.to_csv(index=False, float_format="%.6f"), encoding="utf-8"
    )
    _plot(results, delta_ci, len(prepared), len(raw))
    _write_report(results, delta_ci, len(prepared), len(raw))
    return results, delta_ci


def _plot(results, delta_ci, prepared_rows, raw_rows):
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
    })
    fig, (auc_ax, bins_ax) = plt.subplots(
        1, 2, figsize=(14, 7.5), gridspec_kw={"width_ratios": [1.35, 1]}
    )
    fig.patch.set_facecolor("white")
    colors = ["#2463A6", "#D58B16", "#B4473A", "#68727D"]
    auc_ax.set_facecolor("white")
    for i, row in results.iterrows():
        low = row["AUC"] - row["95% CI low"]
        high = row["95% CI high"] - row["AUC"]
        auc_ax.errorbar(
            i, row["AUC"], yerr=[[low], [high]], fmt="o", markersize=9,
            capsize=5, color=colors[i], linewidth=2,
        )
        auc_ax.text(i, row["AUC"] + 0.010, f"{row['AUC']:.4f}",
                    ha="center", va="bottom", fontweight="bold", color="#182433")
    auc_ax.set_xticks(range(len(results)))
    auc_ax.set_xticklabels(["9 features\nTime split", "16 features\nTime split",
                            "17 features\nTime split", "9 features\nRandom split"])
    auc_ax.set_ylim(0.70, 0.90)
    auc_ax.set_ylabel("ROC-AUC (higher means better cancellation ranking)")
    auc_ax.set_title("AUC on held-out bookings · 95% bootstrap intervals", loc="left", pad=12)
    auc_ax.grid(axis="y", color="#D9DEE5", linewidth=0.8)
    auc_ax.spines[["top", "right"]].set_visible(False)
    auc_ax.text(
        0.02, 0.03,
        f"Paired proof AUC gain, 17 vs 9: +{results.iloc[2]['AUC']-results.iloc[0]['AUC']:.4f}\n"
        f"95% CI for gain: [{delta_ci['17-9'][0]:.4f}, {delta_ci['17-9'][1]:.4f}]\n"
        "Random holdout is not comparable to the chronological proof split.",
        transform=auc_ax.transAxes, ha="left", va="bottom", fontsize=9,
        bbox={"facecolor": "#F2F4F7", "edgecolor": "none", "pad": 7},
    )

    bins_ax.set_facecolor("white")
    models = list(TIMING_COUNTS)
    labels = ["9 features", "16 features", "17 features"]
    y_positions = np.arange(len(models))
    bin_colors = ["#2463A6", "#D58B16", "#B4473A"]
    bin_names = ["Bin 1 · fixed by project", "Bin 2 · amendable", "Bin 3 · after the fact"]
    for j, (color, label) in enumerate(zip(bin_colors, bin_names)):
        values = [TIMING_COUNTS[m][j] for m in models]
        lefts = [sum(TIMING_COUNTS[m][:j]) for m in models]
        bins_ax.barh(y_positions, values, left=lefts, color=color, label=label, height=0.56)
        for y, left, value in zip(y_positions, lefts, values):
            if value:
                bins_ax.text(left + value / 2, y, str(value), color="white",
                             ha="center", va="center", fontweight="bold")
    bins_ax.set_yticks(y_positions, labels)
    bins_ax.invert_yaxis()
    bins_ax.set_xlabel("Number of input features")
    bins_ax.set_title("The historical 17 add eight timing-risk fields", loc="left", pad=12)
    bins_ax.set_xlim(0, 19)
    bins_ax.grid(axis="x", color="#D9DEE5", linewidth=0.8)
    bins_ax.spines[["top", "right", "left"]].set_visible(False)
    bins_ax.text(
        0.01, 0.98,
        "Blue: Bin 1 fixed by project  ·  Amber: Bin 2 amendable  ·  Red: Bin 3 after the fact",
        transform=bins_ax.transAxes, ha="left", va="top", fontsize=8.5, color="#3E4A59",
    )

    fig.suptitle("The 17-feature AUC gain comes with timing risk", x=0.06, y=0.97,
                 ha="left", fontsize=20, fontweight="bold", color="#182433")
    footer = (
        f"Same frozen XGBoost settings; time split: {results.iloc[0]['Train rows']:,} train / "
        f"{results.iloc[0]['Evaluation rows']:,} proof. Random split: {results.iloc[3]['Train rows']:,} / "
        f"{results.iloc[3]['Evaluation rows']:,}. {raw_rows-prepared_rows:,} rows filtered. "
        "Timing bins are project classifications; this dataset is not a guaranteed booking-day snapshot."
    )
    fig.text(0.06, 0.025, footer, ha="left", va="bottom", fontsize=8.5, color="#3E4A59")
    fig.tight_layout(rect=[0.05, 0.09, 0.98, 0.90])
    fig.savefig(ROOT / "evidence" / "feature_timing_eda.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def _write_report(results, delta_ci, prepared_rows, raw_rows):
    lookup = results.set_index("Model")
    gain_16 = lookup.loc["16 · Bin 1 + Bin 2", "AUC"] - lookup.loc["9 · Bin 1 only", "AUC"]
    gain_country = lookup.loc["17 · plus country (Bin 3)", "AUC"] - lookup.loc["16 · Bin 1 + Bin 2", "AUC"]
    gain_total = lookup.loc["17 · plus country (Bin 3)", "AUC"] - lookup.loc["9 · Bin 1 only", "AUC"]
    lines = [
        "# Feature-timing EDA: 9 versus 17 features",
        "",
        "## What the comparison says",
        "",
        f"- Adding the seven Bin 2 features moves proof AUC by **{gain_16:+.4f}** "
        f"(paired-bootstrap 95% CI {delta_ci['16-9'][0]:+.4f} to {delta_ci['16-9'][1]:+.4f}).",
        f"- Adding `country` (Bin 3) after those moves AUC by **{gain_country:+.4f}** "
        f"(95% CI {delta_ci['17-16'][0]:+.4f} to {delta_ci['17-16'][1]:+.4f}).",
        f"- The total 17-versus-9 proof AUC gain is **{gain_total:+.4f}** "
        f"(paired-bootstrap 95% CI {delta_ci['17-9'][0]:+.4f} to {delta_ci['17-9'][1]:+.4f}).",
        "- The paired intervals are entirely above zero on this historical holdout; they do not "
        "establish that those values were available in their final form when the booking was first made.",
        "",
        "## Method",
        "",
        f"Prepared population: {prepared_rows:,} of {raw_rows:,} rows; "
        f"{raw_rows-prepared_rows:,} excluded by the recorded filters. AUC uses the same "
        "chronological train/proof split, training only before 2016-07-01 and evaluating "
        "from 2017-01-01. The current 9-feature model, the 16-feature model (9 + 7 Bin 2), "
        "and the historical 17-feature model (16 + country) all use the same frozen XGBoost "
        "settings selected on choose: depth 4, learning rate 0.05, 200 trees, seed 42.",
        "The random-split score is a separate stratified 80/20 diagnostic (seed 42), not proof.",
        f"Confidence intervals use {BOOTSTRAPS} stratified bootstrap resamples. For the 9/16/17 "
        "chronological models, each bootstrap sample is paired across the same proof rows; the "
        "random model has its own random-holdout interval.",
        "",
        "## Why the 9-feature rule remains the project choice",
        "",
        "The project requirement is a cancellation prediction at booking time. The 17-feature "
        "set adds seven amendable Bin 2 fields and `country`, classified Bin 3. Those fields "
        "can carry useful signal in this historical table, which explains the higher AUC, but "
        "the result is not a clean booking-time performance estimate. The 9-feature set follows "
        "the project's Bin 1 rule and avoids presenting later or changeable values as known at "
        "the decision time.",
        "",
        "## Important limitation",
        "",
        "This analysis cannot prove the exact value a hotel had at the original booking time. "
        "Antonio et al. (2019) describe values extracted from booking change logs relative to "
        "the day before arrival. The 9-feature timing classification is therefore the safer "
        "project rule, not timestamp-level proof. Production use needs point-in-time booking "
        "snapshots or a validated event history. Bootstrap intervals are conditional on these "
        "frozen models and this one historical proof sample; they do not account for repeated "
        "analysis of the same proof period.",
        "",
        "Source: project `data/hotels.csv`; feature timing register in `docs/COLUMNS.md`; "
        "Antonio, N., de Almeida, A., & Nunes, L. (2019), "
        "[Hotel booking demand datasets](https://pmc.ncbi.nlm.nih.gov/articles/PMC6297060/).",
        "Reproduce: `python evidence/feature_timing_eda.py`.",
    ]
    (ROOT / "evidence" / "feature_timing_eda.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    results, delta_ci = run_eda()
    print(results.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print("\nPaired AUC difference 95% intervals:")
    for name, limits in delta_ci.items():
        print(f"  {name}: [{limits[0]:.4f}, {limits[1]:.4f}]")
    print("\nWrote evidence/feature_timing_eda.png, .csv and .md")

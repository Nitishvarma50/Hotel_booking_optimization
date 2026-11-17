"""Screen extra columns on the choose period; never score the proof period here.

Each eligible candidate is added individually to the current nine Bin 1 inputs.
The same XGBoost settings and train/choose rows are used throughout. We report
choose AUC and same-buffer contract cost as exploratory screening metrics only.
"""

from __future__ import annotations

import pathlib
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import auc_comparison  # noqa: E402
import contract  # noqa: E402
import data  # noqa: E402
import features  # noqa: E402


FROZEN_BUFFER = 4
FORBIDDEN = {
    "is_canceled", "adr", "reservation_status", "reservation_status_date",
    "arrival_date", "nights",
}
BIN_LABEL = {1: "Bin 1", 2: "Bin 2", 3: "Bin 3"}
RISK_COLOR = {"Bin 1": "#2463A6", "Bin 2": "#D58B16", "Bin 3": "#B4473A", "Group": "#68727D"}


def _timing_register():
    text = (ROOT / "docs" / "COLUMNS.md").read_text(encoding="utf-8")
    return {
        column: int(bin_number)
        for column, bin_number in re.findall(r"^\| `([^`]+)` \| ([123]) \|", text, flags=re.M)
    }


def _evaluate(train, evaluate, columns, score_data, label, bin_label):
    y_train = train[features.TARGET]
    y_eval = evaluate[features.TARGET]
    _, probabilities = auc_comparison._fit_and_predict(
        train[columns], y_train, evaluate[columns]
    )
    auc = float(roc_auc_score(y_eval, probabilities))
    nightly = contract.nightly_table(score_data, probabilities)
    oversell = np.floor(nightly["expected"] - FROZEN_BUFFER).clip(lower=0).astype(int)
    cost = contract.night_cost(nightly, oversell)
    last_buffer = int(np.ceil(nightly["expected"].max())) + 1
    feasible = []
    for buffer in range(last_buffer + 1):
        candidate_oversell = np.floor(nightly["expected"] - buffer).clip(lower=0).astype(int)
        candidate_score = contract.night_cost(nightly, candidate_oversell)
        if candidate_score["ceiling_met"]:
            feasible.append((candidate_score["cost_eur"], buffer, candidate_score))
    best_cost, best_buffer, best_score = min(feasible, key=lambda item: item[0])
    return {
        "Feature or set": label,
        "Timing bin": bin_label,
        "Feature count": len(columns),
        "Choose AUC": auc,
        "AUC change vs 9": np.nan,
        "Choose cost at fixed k=4 (EUR)": cost["cost_eur"],
        "Cost saving vs 9 at k=4 (EUR)": np.nan,
        "Walks per 1,000 at k=4": cost["walks_per_1000"],
        "Walk ceiling met at k=4": cost["ceiling_met"],
        "Best choose buffer": best_buffer,
        "Best choose cost (EUR)": best_cost,
        "Best choose walks per 1,000": best_score["walks_per_1000"],
        "Choose nights": cost["nights"],
    }


def run_screen():
    raw = data.read_raw()
    prepared = features.prepare_bookings(raw)
    train, choose, _proof = contract.split_periods(prepared)
    _, _, score_choose = features.split_model_inputs(choose)
    bins = _timing_register()

    baseline_columns = list(features.MODEL_FEATURES)
    baseline = _evaluate(
        train, choose, baseline_columns, score_choose,
        "9-feature baseline", "Bin 1",
    )
    rows = [baseline]

    # Screen every registered non-Bin-1 input, except direct outcome fields and
    # the ADR scoring field. Add one candidate at a time to the baseline.
    candidates = [
        column for column, bin_number in bins.items()
        if bin_number in {2, 3}
        and column in prepared.columns
        and column not in FORBIDDEN
        and column not in baseline_columns
    ]
    for column in candidates:
        bin_number = bins[column]
        rows.append(_evaluate(
            train, choose, [*baseline_columns, column], score_choose,
            column, BIN_LABEL[bin_number],
        ))

    set_16 = [column for column in auc_comparison.HISTORICAL_17_FEATURES if column != "country"]
    set_17 = auc_comparison.HISTORICAL_17_FEATURES
    rows.append(_evaluate(
        train, choose, set_16, score_choose,
        "Historical 16 (9 + seven Bin 2)", "Group",
    ))
    rows.append(_evaluate(
        train, choose, set_17, score_choose,
        "Historical 17 (+ country)", "Group",
    ))

    results = pd.DataFrame(rows)
    base_auc = float(baseline["Choose AUC"])
    base_cost = float(baseline["Choose cost at fixed k=4 (EUR)"])
    best_base_cost = float(baseline["Best choose cost (EUR)"])
    results["AUC change vs 9"] = results["Choose AUC"] - base_auc
    results["Cost saving vs 9 at k=4 (EUR)"] = (
        base_cost - results["Choose cost at fixed k=4 (EUR)"]
    )
    results["Choose cost saving vs 9 after buffer selection (EUR)"] = (
        best_base_cost - results["Best choose cost (EUR)"]
    )
    results = results.sort_values("AUC change vs 9", ascending=False).reset_index(drop=True)

    evidence_dir = ROOT / "evidence"
    results.to_csv(evidence_dir / "candidate_feature_screen.csv", index=False, float_format="%.6f")
    _plot(results, len(prepared), len(raw), len(train), len(choose))
    _write_report(results, candidates, len(prepared), len(raw), len(train), len(choose))
    return results


def _plot(results, prepared_rows, raw_rows, train_rows, choose_rows):
    baseline = results.loc[results["Feature or set"] == "9-feature baseline"].iloc[0]
    candidates = results[
        ~results["Feature or set"].isin([
            "9-feature baseline", "Historical 16 (9 + seven Bin 2)", "Historical 17 (+ country)"
        ])
    ].sort_values("AUC change vs 9")
    show = candidates.tail(min(12, len(candidates)))
    fig, (bar_ax, scatter_ax) = plt.subplots(
        1, 2, figsize=(14, 8), gridspec_kw={"width_ratios": [1.25, 1]}
    )
    fig.patch.set_facecolor("white")
    for y, (_, row) in enumerate(show.iterrows()):
        bar_ax.barh(y, row["AUC change vs 9"], color=RISK_COLOR[row["Timing bin"]], height=0.7)
        bar_ax.text(row["AUC change vs 9"] + 0.001, y, f"{row['AUC change vs 9']:+.3f}",
                    va="center", fontsize=8.5)
    bar_ax.set_yticks(range(len(show)), show["Feature or set"])
    bar_ax.axvline(0, color="#3E4A59", linewidth=1)
    bar_ax.set_xlabel("Change in choose-period ROC-AUC vs 9-feature baseline")
    bar_ax.set_title("Largest one-column AUC lifts", loc="left", pad=12)
    bar_ax.grid(axis="x", color="#D9DEE5", linewidth=0.8)
    bar_ax.spines[["top", "right", "left"]].set_visible(False)

    scatter_ax.axhline(0, color="#AAB2BC", linewidth=1)
    scatter_ax.axvline(0, color="#AAB2BC", linewidth=1)
    for _, row in results.iterrows():
        color = RISK_COLOR[row["Timing bin"]]
        scatter_ax.scatter(
            row["AUC change vs 9"],
            row["Choose cost saving vs 9 after buffer selection (EUR)"] / 1000,
            color=color, s=50 if row["Timing bin"] != "Group" else 75,
            marker="D" if row["Timing bin"] == "Group" else "o",
        )
        if row["Feature or set"] in {
            "country", "deposit_type", "lead_time", "Historical 16 (9 + seven Bin 2)",
            "Historical 17 (+ country)",
        }:
            scatter_ax.annotate(
                row["Feature or set"],
                (row["AUC change vs 9"], row["Choose cost saving vs 9 after buffer selection (EUR)"] / 1000),
                xytext=(-8, -12) if row["Feature or set"] == "Historical 17 (+ country)" else (4, 4),
                ha="right" if row["Feature or set"] == "Historical 17 (+ country)" else "left",
                textcoords="offset points", fontsize=8,
            )
    scatter_ax.set_xlabel("Choose-period AUC change vs baseline")
    scatter_ax.set_ylabel("Choose cost saving after each set's buffer selection (EUR thousands)")
    scatter_ax.set_title("AUC and optimized choose cost can disagree", loc="left", pad=12)
    scatter_ax.grid(color="#D9DEE5", linewidth=0.7)
    scatter_ax.spines[["top", "right"]].set_visible(False)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=RISK_COLOR[b],
                   label=label, markersize=8)
        for b, label in [("Bin 1", "Bin 1 candidate"), ("Bin 2", "Bin 2 candidate"), ("Bin 3", "Bin 3 candidate")]
    ]
    handles.append(plt.Line2D([0], [0], marker="D", color="#68727D", label="Historical group sets", linestyle="None"))
    scatter_ax.legend(
        handles=handles, frameon=False, loc="center left",
        bbox_to_anchor=(1.01, 0.50), fontsize=8, borderaxespad=0,
    )

    fig.suptitle("Which extra columns help—and what do they cost?", x=0.06, y=0.97,
                 ha="left", fontsize=20, fontweight="bold", color="#182433")
    foot = (
        f"Train {train_rows:,} → choose {choose_rows:,}; {raw_rows-prepared_rows:,} rows filtered. "
        f"Baseline: AUC {baseline['Choose AUC']:.4f}; cost €{baseline['Choose cost at fixed k=4 (EUR)']:,.0f}; "
        "same frozen XGBoost settings; proof not used. Each feature set gets its own choose-selected buffer."
    )
    fig.text(0.06, 0.025, foot, ha="left", va="bottom", fontsize=8.5, color="#3E4A59")
    fig.tight_layout(rect=[0.05, 0.09, 0.98, 0.90])
    fig.savefig(ROOT / "evidence" / "candidate_feature_screen.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def _write_report(results, candidates, prepared_rows, raw_rows, train_rows, choose_rows):
    baseline = results.loc[results["Feature or set"] == "9-feature baseline"].iloc[0]
    candidate_rows = results[
        ~results["Feature or set"].isin([
            "9-feature baseline", "Historical 16 (9 + seven Bin 2)", "Historical 17 (+ country)"
        ])
    ]
    top_auc = candidate_rows.sort_values("AUC change vs 9", ascending=False).head(5)

    def cost_change_text(value):
        if value > 0:
            return f"cost saving €{value:,.0f}"
        if value < 0:
            return f"cost increase €{abs(value):,.0f}"
        return "no cost change"

    lines = [
        "# Choose-period candidate feature screen",
        "",
        "## Purpose",
        "",
        "This is an exploratory screen for which individual columns might improve cancellation "
        "ranking or the oversell decision. It does not change the approved nine-feature model.",
        "",
        "## Method",
        "",
        f"The shared cleaning filters produced {prepared_rows:,} rows from {raw_rows:,}; "
        f"{raw_rows-prepared_rows:,} were excluded. Models were fit on the chronological train "
        f"period ({train_rows:,} rows) and compared on choose ({choose_rows:,} rows). The proof "
        "period was not read or scored. We used the existing frozen XGBoost settings and added "
        "each registered Bin 2/Bin 3 candidate individually to the same nine Bin 1 inputs. "
        "For each feature set, the choose buffer was selected using the project's cost rule and "
        "walk ceiling. The fixed k=4 metrics are retained as a secondary diagnostic.",
        f"Baseline on choose: AUC {baseline['Choose AUC']:.4f}; cost "
        f"€{baseline['Choose cost at fixed k=4 (EUR)']:,.2f}; "
        f"{baseline['Walks per 1,000 at k=4']:.2f} walks per 1,000; "
        f"ceiling met: {bool(baseline['Walk ceiling met at k=4'])}.",
        "",
        "## Highest AUC lifts from adding one column",
        "",
    ]
    for _, row in top_auc.iterrows():
        lines.append(
            f"- `{row['Feature or set']}` ({row['Timing bin']}): AUC "
            f"{row['Choose AUC']:.4f} ({row['AUC change vs 9']:+.4f}); "
            f"choose-selected k={int(row['Best choose buffer'])}; "
            f"{cost_change_text(row['Choose cost saving vs 9 after buffer selection (EUR)'])}."
        )
    lines.extend(["", "## Largest choose-cost savings after selecting each buffer", ""])
    top_cost = candidate_rows.sort_values(
        "Choose cost saving vs 9 after buffer selection (EUR)", ascending=False
    ).head(5)
    for _, row in top_cost.iterrows():
        lines.append(
            f"- `{row['Feature or set']}` ({row['Timing bin']}): AUC lift "
            f"{row['AUC change vs 9']:+.4f}; k={int(row['Best choose buffer'])}; "
            f"cost saving €{row['Choose cost saving vs 9 after buffer selection (EUR)']:,.0f}; "
            f"{row['Best choose walks per 1,000']:.2f} walks per 1,000."
        )
    lines.extend([
        "",
        "## Business interpretation",
        "",
        "AUC lift is not the same as a better operating decision. Review the cost and walk-ceiling "
        "columns alongside AUC. These are choose-period screening results, not final performance "
        "claims. A candidate only belongs in a booking-time model if its value is verified as "
        "available at booking time. The project data article says feature values were checked "
        "against booking change logs relative to the day before arrival, so this published table "
        "cannot verify original booking-time values. The 9 Bin 1 rule remains the defensible "
        "current choice; the most useful next operational test is to capture timestamped PMS "
        "snapshots for any proposed new column.",
        "",
        "Practical shortlist for timestamped validation: `deposit_type` and "
        "`total_of_special_requests` both improved choose AUC and reduced choose-period cost "
        "after applying the walk-ceiling rule. `country` gave the largest AUC lift, but is "
        "Bin 3 and should not be used for a booking-time decision without a booking-time snapshot. "
        "`lead_time` improved AUC but increased choose cost after its buffer was selected.",
        "",
        "`reservation_status` and `reservation_status_date` were excluded because they describe "
        "final reservation outcomes; `is_canceled` is the target; `adr` is scoring-only. The "
        "correlation heatmap's Pearson values for nominal categories should not be treated as "
        "feature-importance scores.",
        "",
        "Reproduce: `python evidence/candidate_feature_screen.py`. Full row-level results: "
        "`evidence/candidate_feature_screen.csv`.",
    ])
    (ROOT / "evidence" / "candidate_feature_screen.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    output = run_screen()
    display_columns = [
        "Feature or set", "Timing bin", "Choose AUC", "AUC change vs 9",
        "Choose cost at fixed k=4 (EUR)", "Cost saving vs 9 at k=4 (EUR)",
        "Walks per 1,000 at k=4", "Walk ceiling met at k=4",
        "Best choose buffer", "Best choose cost (EUR)",
        "Choose cost saving vs 9 after buffer selection (EUR)",
        "Best choose walks per 1,000",
    ]
    print(output[display_columns].to_string(index=False, formatters={
        "Choose AUC": "{:.4f}".format,
        "AUC change vs 9": "{:+.4f}".format,
        "Choose cost at fixed k=4 (EUR)": "{:,.0f}".format,
        "Cost saving vs 9 at k=4 (EUR)": "{:+,.0f}".format,
        "Best choose cost (EUR)": "{:,.0f}".format,
        "Choose cost saving vs 9 after buffer selection (EUR)": "{:+,.0f}".format,
        "Walks per 1,000 at k=4": "{:.2f}".format,
        "Best choose walks per 1,000": "{:.2f}".format,
    }))
    print("\nWrote candidate_feature_screen.png, .csv and .md")

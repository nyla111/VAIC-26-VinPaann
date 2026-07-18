#!/usr/bin/env python3
"""Build reproducible static figures for the three-year technical report."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--monthly",
        default="data/generated/three_year/analytics/monthly_trends.csv",
    )
    parser.add_argument(
        "--output",
        default="reports/figures/three_year_monthly_trend.png",
    )
    args = parser.parse_args()
    monthly = pd.read_csv(args.monthly)
    total = (
        monthly.groupby("month", as_index=False)["total_weight_tons"]
        .sum()
        .sort_values("month")
    )
    total["date"] = pd.to_datetime(total["month"] + "-01")
    total["rolling_3m"] = total["total_weight_tons"].rolling(3, min_periods=1).mean()
    total["year"] = total["date"].dt.year
    total["month_number"] = total["date"].dt.month
    total["year_mean"] = total.groupby("year")["total_weight_tons"].transform("mean")
    total["seasonal_index"] = total["total_weight_tons"] / total["year_mean"] * 100.0

    blue = "#3569A8"
    gold = "#D59A24"
    ink = "#263238"
    grid = "#D9DEE3"
    year_styles = {
        2024: ("#89A9CF", "--", "o"),
        2025: (blue, "-", "s"),
        2026: ("#234A76", ":", "^")
    }
    fig, axes = plt.subplots(2, 1, figsize=(12, 9))
    fig.suptitle(
        "Sản lượng synthetic theo tháng, 2024–2026",
        fontsize=18,
        fontweight="bold",
        color=ink,
    )

    ax = axes[0]
    ax.plot(total["date"], total["total_weight_tons"], color=blue, linewidth=1.8, marker="o", markersize=3.5, label="Tổng tấn/tháng")
    ax.plot(total["date"], total["rolling_3m"], color=gold, linewidth=2.5, label="Trung bình trượt 3 tháng")
    ax.set_title("36 tháng: mức sản lượng và xu hướng ngắn hạn", loc="left", fontsize=12, fontweight="bold", color=ink)
    ax.set_ylabel("Tấn")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    for boundary in (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01")):
        ax.axvline(boundary, color="#AAB2B9", linewidth=0.9, linestyle="--")

    ax = axes[1]
    for year, (color, linestyle, marker) in year_styles.items():
        subset = total[total["year"] == year]
        ax.plot(
            subset["month_number"],
            subset["seasonal_index"],
            color=color,
            linestyle=linestyle,
            marker=marker,
            linewidth=2.0,
            markersize=4.5,
            label=str(year),
        )
    ax.axhline(100.0, color="#7F8C8D", linewidth=1.0)
    ax.set_title("Mùa vụ lặp lại nhưng không trùng khít giữa các năm", loc="left", fontsize=12, fontweight="bold", color=ink)
    ax.set_xlabel("Tháng trong năm")
    ax.set_ylabel("Chỉ số so với trung bình năm = 100")
    ax.set_xticks(range(1, 13))
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=3, loc="upper left")

    fig.text(
        0.01,
        0.005,
        "Nguồn: monthly_trends.csv, dữ liệu synthetic; địa giới được harmonize theo tên sau sáp nhập cho toàn kỳ.",
        fontsize=9,
        color="#5F6B73",
    )
    fig.tight_layout(rect=[0.02, 0.055, 0.99, 0.94], h_pad=2.1)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Create peer-group visualizations from peer_group_billing_analysis.py output.

Usage:
    python peer_group_visualizations.py \
        --input Forensic_Healthcare_Billing_Peer_Analysis.xlsx \
        --output-dir peer_charts

Outputs PNG charts and a PowerPoint-ready PDF report.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FuncFormatter
from matplotlib.backends.backend_pdf import PdfPages


NAVY = "#173A6B"
TEAL = "#2F8FA3"
GOLD = "#D99B2B"
RED = "#C84C4C"
GRID = "#D9E2E8"
TEXT = "#263746"


def money(x, pos):
    return f"${x:,.0f}"


def load(path: Path):
    calc = pd.read_excel(path, sheet_name="Peer Calculations")
    summary = pd.read_excel(path, sheet_name="Peer Summary")
    screen = pd.read_excel(path, sheet_name="Peer Screening")
    return calc, summary, screen


def style(ax, title, xlabel=None, ylabel=None):
    ax.set_title(title, loc="left", fontsize=15, fontweight="bold", color=NAVY, pad=12)
    if xlabel: ax.set_xlabel(xlabel, color=TEXT)
    if ylabel: ax.set_ylabel(ylabel, color=TEXT)
    ax.grid(axis="y", color=GRID, linewidth=.8)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]: ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]: ax.spines[spine].set_color(GRID)
    ax.tick_params(colors=TEXT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--top-n", type=int, default=15)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    calc, summary, screen = load(args.input)
    sns.set_theme(style="whitegrid", font="DejaVu Sans")
    pdf_path = args.output_dir / "peer_group_visual_report.pdf"

    with PdfPages(pdf_path) as pdf:
        fig, ax = plt.subplots(figsize=(12, 6.75))
        plot = calc[["ChargeAllowedRatio", "PeerChargeAllowedWeighted"]].replace([np.inf, -np.inf], np.nan).dropna()
        plot = plot[(plot["ChargeAllowedRatio"] <= plot["ChargeAllowedRatio"].quantile(.99)) & (plot["PeerChargeAllowedWeighted"] <= plot["PeerChargeAllowedWeighted"].quantile(.99))]
        sns.kdeplot(plot["ChargeAllowedRatio"], ax=ax, color=TEAL, fill=True, alpha=.22, label="Observed row ratio")
        sns.kdeplot(plot["PeerChargeAllowedWeighted"], ax=ax, color=GOLD, fill=True, alpha=.20, label="Peer weighted benchmark")
        style(ax, "Charge-to-allowed ratio: observed rows vs peer benchmarks", ylabel="Density")
        ax.set_xlabel("Charge / allowed ratio")
        ax.legend(frameon=False)
        fig.tight_layout(); fig.savefig(args.output_dir / "01_ratio_vs_peer_distribution.png", dpi=200); pdf.savefig(fig); plt.close(fig)

        top = summary.sort_values("RatioVsPeer", ascending=False).head(args.top_n).sort_values("RatioVsPeer")
        fig, ax = plt.subplots(figsize=(12, 7))
        colors = [RED if x >= 2 else GOLD if x >= 1.5 else TEAL for x in top["RatioVsPeer"]]
        ax.barh(top["Provider"].astype(str), top["RatioVsPeer"], color=colors)
        ax.axvline(1, color=NAVY, linestyle="--", linewidth=1.5, label="Peer benchmark")
        style(ax, "Providers with the highest weighted charge/allowed ratio vs peers", xlabel="Provider ratio ÷ peer ratio")
        ax.legend(frameon=False)
        fig.tight_layout(); fig.savefig(args.output_dir / "02_provider_ratio_vs_peer.png", dpi=200); pdf.savefig(fig); plt.close(fig)

        p = summary.replace([np.inf, -np.inf], np.nan).dropna(subset=["TotalServices", "RatioVsPeer"])
        fig, ax = plt.subplots(figsize=(12, 6.75))
        sizes = np.clip(p["TotalServices"].astype(float), 1, None) ** .55 * 2
        sc = ax.scatter(p["TotalServices"], p["RatioVsPeer"], s=sizes, c=p["MaxRatioPercentile"].fillna(0), cmap="YlOrRd", alpha=.8, edgecolor="white", linewidth=.5)
        ax.axhline(1, color=NAVY, linestyle="--", linewidth=1.4)
        ax.set_xscale("log")
        style(ax, "Provider scale vs peer-relative elevation", xlabel="Total services (log scale)", ylabel="Weighted ratio vs peer")
        cb = fig.colorbar(sc, ax=ax); cb.set_label("Maximum row ratio percentile")
        for _, r in p.nlargest(5, "RatioVsPeer").iterrows():
            ax.annotate(str(r["Provider"])[:16], (r["TotalServices"], r["RatioVsPeer"]), xytext=(5, 5), textcoords="offset points", fontsize=8, color=TEXT)
        fig.tight_layout(); fig.savefig(args.output_dir / "03_scale_vs_peer_elevation.png", dpi=200); pdf.savefig(fig); plt.close(fig)

        h = screen.head(args.top_n).copy()
        h["Label"] = h["Provider"].astype(str).str[:14] + " / " + h["HCPCS"].astype(str)
        cols = ["RatioPercentile", "ChargePercentile", "RatioToPeerRatio", "ChargeToPeerCharge", "ScreeningScore"]
        hm = h.set_index("Label")[cols].copy()
        hm.columns = ["Ratio pct", "Charge pct", "Ratio / peer", "Charge / peer", "Score"]
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(hm, cmap="YlOrRd", annot=True, fmt=".2f", linewidths=.5, linecolor="white", ax=ax, cbar_kws={"label": "Relative intensity"})
        style(ax, "Top provider/service screening candidates", ylabel="Provider / HCPCS")
        ax.set_xlabel("")
        fig.tight_layout(); fig.savefig(args.output_dir / "04_screening_heatmap.png", dpi=200); pdf.savefig(fig); plt.close(fig)

        coverage = calc["PeerLevel"].value_counts().reindex(["HCPCS + Type + State", "HCPCS + Type", "HCPCS"], fill_value=0)
        fig, ax = plt.subplots(figsize=(10, 5.5))
        ax.bar(coverage.index, coverage.values, color=[TEAL, GOLD, NAVY])
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:,.0f}"))
        style(ax, "Peer-group specificity used for each row", ylabel="Rows")
        ax.tick_params(axis="x", rotation=15)
        fig.tight_layout(); fig.savefig(args.output_dir / "05_peer_group_coverage.png", dpi=200); pdf.savefig(fig); plt.close(fig)

    print(f"Created charts in: {args.output_dir}")
    print(f"Created report: {pdf_path}")


if __name__ == "__main__":
    main()

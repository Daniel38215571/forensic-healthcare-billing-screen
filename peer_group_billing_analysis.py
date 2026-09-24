#!/usr/bin/env python3
"""
Peer-group calculations for the Forensic Healthcare Billing Screen workbook.

Usage:
    python peer_group_billing_analysis.py \
        --input Forensic_Healthcare_Billing_Screen-8.xlsx \
        --output Forensic_Healthcare_Billing_Peer_Analysis.xlsx

Peer hierarchy used for each provider/service row:
    1. Same HCPCS + provider specialty/type + state
    2. Same HCPCS + provider specialty/type
    3. Same HCPCS

The workflow compares submitted average charges and charge-to-allowed ratios
against relevant peers. It is a screening aid, not a fraud determination.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "Provider", "Type", "State", "HCPCS", "Beneficiaries", "Services",
    "AvgCharge", "AvgAllowed", "AvgPayment", "ChargeAllowedRatio",
}


def parse_money(series: pd.Series) -> pd.Series:
    """Convert currency-like values such as '$1,234.50' to numeric."""
    return pd.to_numeric(
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace({"": np.nan, "nan": np.nan, "None": np.nan}),
        errors="coerce",
    )


def parse_ratio(series: pd.Series) -> pd.Series:
    """Convert ratio-like values such as '12.4x' to numeric."""
    return pd.to_numeric(
        series.astype(str)
        .str.replace("x", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip(),
        errors="coerce",
    )


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    return float(np.average(values.loc[mask], weights=weights.loc[mask]))


def weighted_median(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    x = values.loc[mask].to_numpy(dtype=float)
    w = weights.loc[mask].to_numpy(dtype=float)
    order = np.argsort(x)
    x, w = x[order], w[order]
    cutoff = w.sum() / 2.0
    return float(x[np.searchsorted(np.cumsum(w), cutoff)])


def percentile_rank(value: float, peer_values: pd.Series) -> float:
    clean = pd.to_numeric(peer_values, errors="coerce").dropna()
    if pd.isna(value) or clean.empty:
        return np.nan
    return float((clean <= value).mean())


def robust_z(value: float, peer_values: pd.Series) -> float:
    """Robust z-score using median and MAD; falls back to standard deviation."""
    clean = pd.to_numeric(peer_values, errors="coerce").dropna()
    if pd.isna(value) or len(clean) < 2:
        return np.nan
    median = clean.median()
    mad = np.median(np.abs(clean - median))
    if mad and not pd.isna(mad):
        return float(0.6745 * (value - median) / mad)
    std = clean.std(ddof=1)
    return float((value - clean.mean()) / std) if std and not pd.isna(std) else 0.0


def make_peer_key(row: pd.Series, level: int) -> tuple:
    hcpcs = str(row["HCPCS"]).strip()
    typ = str(row["Type"]).strip().lower()
    state = str(row["State"]).strip().upper()
    if level == 1:
        return hcpcs, typ, state
    if level == 2:
        return hcpcs, typ
    return (hcpcs,)


def choose_peer_group(row: pd.Series, groups: dict, min_peers: int) -> tuple[int, tuple, pd.DataFrame]:
    """Choose the most specific peer group containing at least min_peers rows."""
    for level in (1, 2, 3):
        key = make_peer_key(row, level)
        peer = groups[level].get(key)
        if peer is not None:
            peer = peer.loc[peer["_row_id"] != row["_row_id"]]
            if len(peer) >= min_peers:
                return level, key, peer
    key = make_peer_key(row, 3)
    peer = groups[3].get(key, pd.DataFrame()).loc[lambda x: x["_row_id"] != row["_row_id"]]
    return 3, key, peer


def load_data(path: Path) -> pd.DataFrame:
    data = pd.read_excel(path, sheet_name="Data")
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"Data sheet is missing required columns: {sorted(missing)}")

    data = data.copy()
    data["_row_id"] = np.arange(len(data))
    data["HCPCS"] = data["HCPCS"].astype(str).str.strip()
    data["Type"] = data["Type"].astype(str).str.strip()
    data["State"] = data["State"].astype(str).str.strip().str.upper()
    for col in ["Beneficiaries", "Services"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in ["AvgCharge", "AvgAllowed", "AvgPayment"]:
        data[col] = parse_money(data[col])
    data["ChargeAllowedRatio"] = parse_ratio(data["ChargeAllowedRatio"])
    data["Services"] = data["Services"].fillna(0).clip(lower=0)
    return data


def calculate_peer_metrics(data: pd.DataFrame, min_peers: int = 5) -> pd.DataFrame:
    groups = {
        level: {key: group.copy() for key, group in data.groupby(
            data.apply(lambda row: make_peer_key(row, level), axis=1), dropna=False
        )}
        for level in (1, 2, 3)
    }

    records = []
    for _, row in data.iterrows():
        level, key, peer = choose_peer_group(row, groups, min_peers)
        charge_peers = peer["AvgCharge"] if not peer.empty else pd.Series(dtype=float)
        ratio_peers = peer["ChargeAllowedRatio"] if not peer.empty else pd.Series(dtype=float)
        allowed_peers = peer["AvgAllowed"] if not peer.empty else pd.Series(dtype=float)

        charge_benchmark = weighted_mean(charge_peers, peer["Services"]) if not peer.empty else np.nan
        ratio_benchmark = weighted_mean(ratio_peers, peer["Services"]) if not peer.empty else np.nan
        allowed_benchmark = weighted_mean(allowed_peers, peer["Services"]) if not peer.empty else np.nan
        charge_median = weighted_median(charge_peers, peer["Services"]) if not peer.empty else np.nan
        ratio_median = weighted_median(ratio_peers, peer["Services"]) if not peer.empty else np.nan

        charge_gap = row["AvgCharge"] / charge_benchmark if charge_benchmark and not pd.isna(charge_benchmark) else np.nan
        ratio_gap = row["ChargeAllowedRatio"] / ratio_benchmark if ratio_benchmark and not pd.isna(ratio_benchmark) else np.nan
        ratio_delta = row["ChargeAllowedRatio"] - ratio_benchmark if not pd.isna(ratio_benchmark) else np.nan
        record = {
            **row.to_dict(),
            "PeerLevel": {1: "HCPCS + Type + State", 2: "HCPCS + Type", 3: "HCPCS"}[level],
            "PeerKey": " | ".join(map(str, key)),
            "PeerRows": int(len(peer)),
            "PeerProviders": int(peer["Provider"].nunique()) if not peer.empty else 0,
            "PeerServices": float(peer["Services"].sum()) if not peer.empty else 0,
            "PeerAvgChargeWeighted": charge_benchmark,
            "PeerAvgChargeMedian": charge_median,
            "PeerAvgAllowedWeighted": allowed_benchmark,
            "PeerChargeAllowedWeighted": ratio_benchmark,
            "PeerChargeAllowedMedian": ratio_median,
            "ChargeToPeerCharge": charge_gap,
            "RatioToPeerRatio": ratio_gap,
            "RatioDeltaVsPeer": ratio_delta,
            "ChargePercentile": percentile_rank(row["AvgCharge"], charge_peers),
            "RatioPercentile": percentile_rank(row["ChargeAllowedRatio"], ratio_peers),
            "ChargeRobustZ": robust_z(row["AvgCharge"], charge_peers),
            "RatioRobustZ": robust_z(row["ChargeAllowedRatio"], ratio_peers),
        }
        records.append(record)

    result = pd.DataFrame(records)
    result["ScreeningScore"] = (
        result["RatioPercentile"].fillna(0) * 60
        + result["ChargePercentile"].fillna(0) * 25
        + result["RatioToPeerRatio"].clip(lower=0, upper=10).fillna(0) * 1.5
        + result["PeerRows"].clip(lower=0, upper=50) * 0.1
    )
    result["ScreeningBand"] = pd.cut(
        result["ScreeningScore"],
        bins=[-np.inf, 45, 65, 80, np.inf],
        labels=["Routine", "Review", "Elevated", "Priority"],
    ).astype(str)
    return result.drop(columns=["_row_id"])


def provider_summary(peer_rows: pd.DataFrame) -> pd.DataFrame:
    def weighted(group: pd.DataFrame, col: str) -> float:
        return weighted_mean(group[col], group["Services"])

    out = peer_rows.groupby(["Provider", "Type", "State"], dropna=False).apply(
        lambda g: pd.Series({
            "ServiceRows": len(g),
            "TotalServices": g["Services"].sum(),
            "UniqueHCPCS": g["HCPCS"].nunique(),
            "AvgChargeWeighted": weighted(g, "AvgCharge"),
            "PeerAvgChargeWeighted": weighted(g, "PeerAvgChargeWeighted"),
            "AvgChargeVsPeer": weighted(g, "ChargeToPeerCharge"),
            "ChargeAllowedWeighted": weighted(g, "ChargeAllowedRatio"),
            "PeerChargeAllowedWeighted": weighted(g, "PeerChargeAllowedWeighted"),
            "RatioVsPeer": weighted(g, "RatioToPeerRatio"),
            "MaxRatioPercentile": g["RatioPercentile"].max(),
            "PriorityRows": (g["ScreeningBand"] == "Priority").sum(),
            "ElevatedRows": g["ScreeningBand"].isin(["Elevated", "Priority"]).sum(),
        }), include_groups=False
    ).reset_index()
    return out.sort_values(["PriorityRows", "RatioVsPeer", "TotalServices"], ascending=[False, False, False])


def format_excel(writer: pd.ExcelWriter, sheets: Iterable[str]) -> None:
    for sheet in sheets:
        ws = writer.sheets[sheet]
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, ws.dim_rowmax, ws.dim_colmax)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.set_margins(0.25, 0.25, 0.4, 0.4)
        ws.hide_gridlines(2)
        ws.set_column(0, ws.dim_colmax, 16)
        if ws.dim_colmax >= 0:
            ws.set_column(0, 0, 24)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-peers", type=int, default=5)
    args = parser.parse_args()

    data = load_data(args.input)
    metrics = calculate_peer_metrics(data, min_peers=max(1, args.min_peers))
    summary = provider_summary(metrics)
    candidates = metrics.sort_values(
        ["ScreeningScore", "RatioToPeerRatio", "RatioPercentile"],
        ascending=[False, False, False],
    ).head(250).copy()

    preferred = [
        "Provider", "Type", "State", "HCPCS", "Beneficiaries", "Services",
        "AvgCharge", "AvgAllowed", "AvgPayment", "ChargeAllowedRatio",
        "PeerLevel", "PeerKey", "PeerRows", "PeerProviders", "PeerServices",
        "PeerAvgChargeWeighted", "PeerAvgChargeMedian", "PeerAvgAllowedWeighted",
        "PeerChargeAllowedWeighted", "PeerChargeAllowedMedian", "ChargeToPeerCharge",
        "RatioToPeerRatio", "RatioDeltaVsPeer", "ChargePercentile", "RatioPercentile",
        "ChargeRobustZ", "RatioRobustZ", "ScreeningScore", "ScreeningBand",
    ]
    candidates = candidates[[c for c in preferred if c in candidates.columns]]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(args.output, engine="xlsxwriter") as writer:
        metrics.to_excel(writer, sheet_name="Peer Calculations", index=False)
        summary.to_excel(writer, sheet_name="Peer Summary", index=False)
        candidates.to_excel(writer, sheet_name="Peer Screening", index=False)
        data.drop(columns=["_row_id"]).to_excel(writer, sheet_name="Source Data", index=False)
        format_excel(writer, ["Peer Calculations", "Peer Summary", "Peer Screening", "Source Data"])

        workbook = writer.book
        header = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#173A6B", "border": 1})
        band = workbook.add_format({"bg_color": "#FFF2CC"})
        priority = workbook.add_format({"bg_color": "#F4CCCC"})
        for sheet in ["Peer Calculations", "Peer Summary", "Peer Screening", "Source Data"]:
            ws = writer.sheets[sheet]
            ws.set_row(0, 28, header)
        ps = writer.sheets["Peer Screening"]
        ps.conditional_format(1, candidates.columns.get_loc("ScreeningBand"), len(candidates), candidates.columns.get_loc("ScreeningBand"), {"type": "text", "criteria": "containing", "value": "Priority", "format": priority})
        ps.conditional_format(1, candidates.columns.get_loc("ScreeningBand"), len(candidates), candidates.columns.get_loc("ScreeningBand"), {"type": "text", "criteria": "containing", "value": "Elevated", "format": band})

    print(f"Created: {args.output}")
    print(f"Source rows: {len(data):,}")
    print(f"Peer calculations: {len(metrics):,}")
    print(f"Peer screening rows: {len(candidates):,}")


if __name__ == "__main__":
    main()

import numpy as np
import pandas as pd
import pytest

from peer_group_billing_analysis import (
    weighted_mean,
    weighted_median,
    percentile_rank,
    robust_z,
    parse_money,
    parse_ratio,
    make_peer_key,
)


# ---------- weighted_mean ----------

def test_weighted_mean_basic():
    values = pd.Series([10.0, 20.0, 30.0])
    weights = pd.Series([1.0, 1.0, 2.0])
    # (10*1 + 20*1 + 30*2) / 4 = 90/4 = 22.5
    assert weighted_mean(values, weights) == 22.5


def test_weighted_mean_ignores_nan_and_zero_weights():
    values = pd.Series([10.0, np.nan, 30.0, 100.0])
    weights = pd.Series([1.0, 1.0, 1.0, 0.0])
    # NaN dropped, 100 has zero weight, so (10+30)/2 = 20
    assert weighted_mean(values, weights) == 20.0


def test_weighted_mean_all_invalid_returns_nan():
    values = pd.Series([np.nan, np.nan])
    weights = pd.Series([0.0, 0.0])
    assert np.isnan(weighted_mean(values, weights))


# ---------- weighted_median ----------

def test_weighted_median_uniform_weights_matches_plain_median():
    values = pd.Series([10.0, 20.0, 30.0])
    weights = pd.Series([1.0, 1.0, 1.0])
    assert weighted_median(values, weights) == 20.0


def test_weighted_median_shifts_with_weight():
    # Weight pushes the median to the heavier value
    values = pd.Series([10.0, 20.0])
    weights = pd.Series([1.0, 9.0])
    # Cumulative: 1, 10. Cutoff = 5. First cumulative >= 5 is at index 1.
    assert weighted_median(values, weights) == 20.0


# ---------- percentile_rank ----------

def test_percentile_rank_middle_value():
    peers = pd.Series([1, 2, 3, 4, 5])
    # 3 <= 3,4,5 => 3 of 5
    assert percentile_rank(3, peers) == 0.6


def test_percentile_rank_max_value():
    peers = pd.Series([1, 2, 3, 4, 5])
    assert percentile_rank(5, peers) == 1.0


def test_percentile_rank_nan_input_returns_nan():
    peers = pd.Series([1, 2, 3])
    assert np.isnan(percentile_rank(np.nan, peers))


# ---------- robust_z ----------

def test_robust_z_at_median_is_zero():
    peers = pd.Series([10, 20, 30, 40, 50])
    assert abs(robust_z(30, peers)) < 1e-9


def test_robust_z_positive_for_high_value():
    peers = pd.Series([10, 20, 30, 40, 50])
    assert robust_z(50, peers) > 0


def test_robust_z_survives_extreme_outlier():
    # One absurd outlier. Standard z would be destroyed; robust z should not.
    peers = pd.Series([10, 20, 30, 40, 50, 10000])
    # The subject (50) should still produce a modest positive z, not be squashed.
    z = robust_z(50, peers)
    assert z > 0
    assert z < 10  # sanity bound; a standard z would be near zero from inflation


def test_robust_z_insufficient_data_returns_nan():
    peers = pd.Series([1.0])
    assert np.isnan(robust_z(1, peers))


# ---------- parse_money ----------

def test_parse_money_strips_symbols():
    s = pd.Series(["$1,234.50", "$0.99", "  $10.00  "])
    out = parse_money(s)
    assert out.tolist() == [1234.50, 0.99, 10.00]


def test_parse_money_handles_blank_and_nan():
    s = pd.Series(["", "nan", "None", "$5.00"])
    out = parse_money(s)
    assert np.isnan(out.iloc[0])
    assert np.isnan(out.iloc[1])
    assert np.isnan(out.iloc[2])
    assert out.iloc[3] == 5.00


# ---------- parse_ratio ----------

def test_parse_ratio_strips_x_suffix():
    s = pd.Series(["12.4x", "1.0x", "0.85x"])
    out = parse_ratio(s)
    assert out.tolist() == [12.4, 1.0, 0.85]


def test_parse_ratio_handles_plain_numbers():
    s = pd.Series(["3.5", "2.0"])
    out = parse_ratio(s)
    assert out.tolist() == [3.5, 2.0]


# ---------- make_peer_key ----------

def test_make_peer_key_levels():
    row = pd.Series({"HCPCS": "99213", "Type": "Cardiology", "State": "ca"})
    assert make_peer_key(row, 1) == ("99213", "cardiology", "CA")
    assert make_peer_key(row, 2) == ("99213", "cardiology")
    assert make_peer_key(row, 3) == ("99213",)


def test_make_peer_key_normalizes_case_and_whitespace():
    row = pd.Series({"HCPCS": " 99213 ", "Type": " CARDIOLOGY ", "State": " ca "})
    assert make_peer_key(row, 1) == ("99213", "cardiology", "CA")

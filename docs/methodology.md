# Methodology

## Purpose
This is a screening tool, not a fraud determination. It surfaces rows whose billing pattern deviates from comparable peers so a human reviewer can look closer. All output requires expert interpretation.

## Peer group selection

Every row is compared against peers using a three-tier fallback. The most specific tier with at least `--min-peers` rows (default 5) wins:

| Tier | Key | Rationale |
|---|---|---|
| 1 | HCPCS + Type + State | Same procedure, same specialty, same geography — closest possible comparison |
| 2 | HCPCS + Type | Relax geography when state-level volume is thin |
| 3 | HCPCS | Relax specialty when both state and specialty are sparse |

The subject row is always excluded from its own peer set.

## Benchmark calculation

All peer benchmarks are **weighted by `Services`**. A peer with 500 services influences the benchmark more than a peer with 5.

- `PeerAvgChargeWeighted` — services-weighted mean of `AvgCharge`
- `PeerChargeAllowedWeighted` — services-weighted mean of `ChargeAllowedRatio`
- `PeerAvgAllowedWeighted` — services-weighted mean of `AvgAllowed`

Unweighted medians (`PeerAvgChargeMedian`, `PeerChargeAllowedMedian`) are also computed as a sanity check. If mean and median diverge sharply, the peer group contains an outlier that's skewing the mean.

## Per-row deviation metrics

| Metric | Formula | Interpretation |
|---|---|---|
| ChargeToPeerCharge | AvgCharge ÷ PeerAvgChargeWeighted | >1 means the provider charges more than peers |
| RatioToPeerRatio | ChargeAllowedRatio ÷ PeerChargeAllowedWeighted | >1 means the charge-to-allowed markup is higher than peers |
| RatioDeltaVsPeer | ChargeAllowedRatio − PeerChargeAllowedWeighted | Absolute gap |
| ChargePercentile | Share of peers ≤ subject AvgCharge | 0.95 means top 5% of peer group |
| RatioPercentile | Share of peers ≤ subject ratio | Same logic, on the ratio |
| ChargeRobustZ | 0.6745 × (x − median) / MAD | Outlier resistance — survives extreme values |
| RatioRobustZ | Same formula, on ratio | Same |

## Why robust z-scores instead of standard z-scores

Healthcare billing data is heavily right-skewed and contains extreme outliers. A single 100× ratio can inflate a standard deviation enough to hide every other anomaly. Median/MAD-based z-scores are immune to this.

The constant `0.6745` normalizes MAD so that for normally-distributed data the robust z-score approximates the standard z-score.

## Screening score

Composite, deliberately transparent:

~~~
ScreeningScore = 60 × RatioPercentile
              + 25 × ChargePercentile
              + 1.5 × min(RatioToPeerRatio, 10)
              + 0.1 × min(PeerRows, 50)
~~~

- **60%** to ratio elevation — the primary signal
- **25%** to charge percentile — secondary confirmation
- **15%** to the raw ratio-to-peer gap, capped at 10× so a single extreme value can't dominate
- Small bonus for peer-group size — a benchmark built on 50 rows is more reliable than one built on 5

## Screening bands

| Band | Score range | Suggested action |
|---|---|---|
| Routine | < 45 | No review |
| Review | 45 – 65 | Spot check |
| Elevated | 65 – 80 | Targeted review |
| Priority | ≥ 80 | Prioritize for human review |

## Limitations

- Benchmarks inherit the quality of the underlying data. Garbage in, garbage out.
- Peer groups under 5 rows are statistically noisy. The `PeerRows` column tells you how reliable each benchmark is.
- The 60/25/15 weighting is a judgment call, not a statistically optimized model. It is transparent so a reviewer can challenge it.
- This tool flags **deviation from peers**, not wrongdoing. A high ratio can reflect case mix, payer mix, or specialty-specific behavior.

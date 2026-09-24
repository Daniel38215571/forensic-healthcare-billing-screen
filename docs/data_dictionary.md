# Data Dictionary

Every row in the input workbook represents one provider × HCPCS combination for a reporting period. The analysis compares each row against its peer group.

## Input sheet: `Data`

| Column | Type | Description |
|---|---|---|
| Provider | string | Provider or practice identifier |
| Type | string | Provider specialty / taxonomy category |
| State | string | Two-letter state code, uppercased on load |
| HCPCS | string | HCPCS/CPT procedure code (kept as string to preserve leading zeros) |
| Beneficiaries | integer | Distinct beneficiaries served |
| Services | integer | Total services billed (used as weight in all benchmarks) |
| AvgCharge | currency | Average submitted charge per service |
| AvgAllowed | currency | Average allowed amount per service |
| AvgPayment | currency | Average paid amount per service |
| ChargeAllowedRatio | ratio | AvgCharge ÷ AvgAllowed, e.g. `12.4x` |

## Peer group columns (added by analysis)

| Column | Description |
|---|---|
| PeerLevel | Which hierarchy tier supplied the benchmark: `HCPCS + Type + State`, `HCPCS + Type`, or `HCPCS` |
| PeerKey | The literal key used to look up peers |
| PeerRows | Number of peer rows in the benchmark (excluding the subject row) |
| PeerProviders | Distinct providers represented in the peer set |
| PeerServices | Total services summed across peer rows |
| PeerAvgChargeWeighted | Services-weighted mean of peer AvgCharge |
| PeerAvgChargeMedian | Services-weighted median of peer AvgCharge |
| PeerAvgAllowedWeighted | Services-weighted mean of peer AvgAllowed |
| PeerChargeAllowedWeighted | Services-weighted mean of peer ChargeAllowedRatio — the primary benchmark |
| PeerChargeAllowedMedian | Services-weighted median of peer ChargeAllowedRatio |
| ChargeToPeerCharge | Subject AvgCharge ÷ PeerAvgChargeWeighted |
| RatioToPeerRatio | Subject ChargeAllowedRatio ÷ PeerChargeAllowedWeighted |
| RatioDeltaVsPeer | Subject ChargeAllowedRatio − PeerChargeAllowedWeighted |
| ChargePercentile | Share of peers with AvgCharge ≤ subject's AvgCharge |
| RatioPercentile | Share of peers with ChargeAllowedRatio ≤ subject's ratio |
| ChargeRobustZ | Median/MAD-based z-score of AvgCharge vs peers |
| RatioRobustZ | Median/MAD-based z-score of ChargeAllowedRatio vs peers |
| ScreeningScore | Composite score: 60% RatioPercentile + 25% ChargePercentile + capped elevation bonus + small peer-size bonus |
| ScreeningBand | `Routine` (<45), `Review` (45–65), `Elevated` (65–80), `Priority` (≥80) |

## Notes

- `Beneficiaries` and `Services` are coerced to numeric; `Services` is clipped at 0.
- Currency strings like `$1,234.50` are stripped of `$` and `,` before conversion.
- Ratio strings like `12.4x` are stripped of `x` before conversion.
- Rows missing a critical peer key fall back to the least-specific tier rather than erroring.

import pandas as pd
import numpy as np
from pathlib import Path

np.random.seed(42)

providers = ["Provider_A", "Provider_B", "Provider_C", "Provider_D", "Provider_E"]
types = ["Internal Medicine", "Cardiology", "Orthopedics"]
states = ["CA", "TX", "NY"]
hcpcs = ["99213", "99214", "27447", "93000", "77049"]

rows = []
for i in range(300):
    rows.append({
        "Provider": np.random.choice(providers),
        "Type": np.random.choice(types),
        "State": np.random.choice(states),
        "HCPCS": np.random.choice(hcpcs),
        "Beneficiaries": np.random.randint(1, 100),
        "Services": np.random.randint(1, 500),
        "AvgCharge": np.round(np.random.lognormal(4.5, 0.8), 2),
        "AvgAllowed": np.round(np.random.lognormal(3.8, 0.6), 2),
        "AvgPayment": np.round(np.random.lognormal(3.7, 0.6), 2),
    })

df = pd.DataFrame(rows)
df["ChargeAllowedRatio"] = df["AvgCharge"] / df["AvgAllowed"]

out = Path("data/sample")
out.mkdir(parents=True, exist_ok=True)

with pd.ExcelWriter(out / "synthetic_billing_sample.xlsx", engine="xlsxwriter") as writer:
    df.to_excel(writer, sheet_name="Data", index=False)

print("Synthetic sample created.")

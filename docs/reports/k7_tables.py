"""K7 numbers and figures/k7_all_participants.png for the 2026-11-10 report, from results/exogait/moco/assist.csv
and summary.csv.

    python docs/reports/k7_tables.py      # from the repo root; any Python with pandas, scipy and matplotlib"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
a = pd.read_csv("results/exogait/moco/assist.csv").drop_duplicates(["participant", "condition", "n_mesh"], keep="last")
a = a[(a.condition == "SM_WALKING") & (a.n_mesh == 50)].sort_values("participant")
q = lambda s: f"{s.median():+.1f}% [{s.min():+.1f} to {s.max():+.1f}]"
print(f"SM walking, mean strides, n = {len(a)} participants: {', '.join(a.participant)}")
for col, lab in (("measured_vs_none_pct", "measured vs none"), ("optimised_vs_measured_pct", "optimised vs measured"),
                 ("optimised_vs_none_pct", "optimised vs none")):
    x = a[col]
    p = wilcoxon(x).pvalue if len(x) > 5 else float("nan")
    print(f"  effort, {lab}: median {q(x)}; lower in {(x < 0).sum()}/{len(x)}; Wilcoxon signed-rank p = {p:.2g}")
print(f"  effort (sum a^2 x s): none {a.effort_none.median():.3f}, measured {a.effort_measured.median():.3f}, optimised {a.effort_optimised.median():.3f} (medians)")
print(f"  worst hip/knee RMSE: none {a.rmse_max_none.max():.2f}, measured {a.rmse_max_measured.max():.2f}, optimised {a.rmse_max_optimised.max():.2f} deg")
used = a[[c for c in a.columns if c.startswith("budget_used")]]
print(f"  budget used by optimised: {used.min().min():.2f}-{used.max().max():.2f} of the measured budget")
rate = lambda case: a[[c for c in a.columns if c.startswith("rate_rms") and c.endswith(case)]]
ratio = rate("optimised").to_numpy() / rate("measured").to_numpy()
print(f"  torque rate RMS, optimised / measured: median {np.median(ratio):.1f}x [{ratio.min():.1f}-{ratio.max():.1f}]")
price = a[[c for c in a.columns if c.startswith("price_")]]
print(f"  prices: {price.min().min():.2f}-{price.max().max():.2f}")
if a.effort_ideal.notna().any():
    i = a[a.effort_ideal.notna()]
    print(f"  ideal (n={len(i)}): vs none {q(i.ideal_vs_none_pct)}; over budget x{i[[c for c in i.columns if c.startswith('ideal_over')]].min().min():.0f}-{i[[c for c in i.columns if c.startswith('ideal_over')]].max().max():.0f}")

# TR: what the transparent-mode torque does to effort (K6's question)
d = pd.read_csv("results/exogait/moco/summary.csv")
d = d[(d.n_mesh == 50) & (d["check"] == "ok")].drop_duplicates(["participant", "condition", "case"], keep="last")
t = d[d.condition == "transparent_WALKING"].pivot(index="participant", columns="case", values="effort").dropna(subset=["measured", "none"])
tr = 100 * (t.measured - t.none) / t.none
print(f"TR walking, n = {len(t)}: effort measured vs none: median {q(tr)}; lower in {(tr < 0).sum()}/{len(tr)}; "
      f"Wilcoxon p = {wilcoxon(tr).pvalue if len(tr) > 5 else float('nan'):.2g}")
bad = pd.read_csv("results/exogait/moco/summary.csv")
bad = bad[(bad.n_mesh == 50) & (bad.case.isin(["none", "optimised"]))].drop_duplicates(["participant", "condition", "case"], keep="last")
bad = bad[bad["check"] != "ok"]
print("solves that fail a check (last row per key):", [(r.participant, r.condition.split("_")[0], r.case, c[:40]) for r, c in zip(bad.itertuples(), bad["check"])])

fig, axs = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw=dict(width_ratios=(1.25, 1)))
x = np.arange(3)
for r in a.itertuples():
    axs[0].plot(x, [r.effort_none, r.effort_measured, r.effort_optimised], color="#9b9a94", lw=1, marker="o", ms=3.5, alpha=0.8)
axs[0].plot(x, [a.effort_none.median(), a.effort_measured.median(), a.effort_optimised.median()], color="#1a1a19", lw=2.4, marker="o", ms=6, label="median")
axs[0].set_xticks(x, ["exo off\n(none)", "measured X2 torque\n(state machine)", "optimised torque\n(same torque budget)"])
axs[0].set_ylabel("muscle effort: sum of squared activations × time [s]")
axs[0].set_ylim(0)
axs[0].set_title(f"Simulated muscle effort over the mean stride, {len(a)} participants (SM walking)", fontsize=10)
axs[0].legend(frameon=False, fontsize=9)
rng = np.random.default_rng(1)
cols = (("measured_vs_none_pct", "measured\nvs exo off", "#2a78d6"), ("optimised_vs_measured_pct", "optimised\nvs measured", "#1f9d6b"),
        ("optimised_vs_none_pct", "optimised\nvs exo off", "#1f9d6b"))
for i, (col, lab, c) in enumerate(cols):
    y = a[col].to_numpy()
    axs[1].scatter(i + rng.uniform(-0.09, 0.09, len(y)), y, s=26, color=c, alpha=0.8, lw=0)
    axs[1].plot([i - 0.2, i + 0.2], [np.median(y)] * 2, color="#1a1a19", lw=2)
    axs[1].text(i + 0.26, np.median(y), f"{np.median(y):+.0f}%", va="center", fontsize=9)
axs[1].axhline(0, color="#52514e", lw=0.9)
axs[1].set_xticks(range(3), [c[1] for c in cols])
axs[1].set_xlim(-0.5, 2.7)
axs[1].set_ylabel("change in muscle effort [%]")
axs[1].set_title("Change per participant (bar = median)", fontsize=10)
for ax in axs:
    ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig("figures/k7_all_participants.png", dpi=130)
print("figures/k7_all_participants.png")

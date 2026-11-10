"""K5 numbers and figures/k5_all_participants.png for the 2026-11-10 report, from results/exogait/moco/summary.csv.

    python docs/reports/k5_tables.py      # from the repo root; any Python with pandas and matplotlib

The two data-based speed estimates in k4_speed_estimates.csv come from K4's stride analysis (a throwaway
script: hip travel over the planted foot, and walkway length / bout time), one row per participant x controller."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
d = pd.read_csv("results/exogait/moco/summary.csv")
d = d[d.target == "mean"].drop_duplicates(["participant", "condition", "case", "n_mesh"], keep="last")
m = d[(d.case == "measured") & (d.n_mesh == 50)].copy()
m["ctrl"] = m.condition.str.split("_").str[0].map({"SM": "SM", "transparent": "TR"})
print(f"measured, mesh 50: {len(m)} solves, {m.success.sum()} converged, {(m['check'] == 'ok').sum()} pass the plausibility check")
bad = m[m["check"] != "ok"]
if len(bad):
    print(bad[["participant", "condition", "success", "iterations", "check"]].to_string(index=False))
ok = m[m["check"] == "ok"]
J = ["rmse_hip_flexion_l", "rmse_hip_flexion_r", "rmse_knee_angle_l", "rmse_knee_angle_r", "rmse_pelvis_tilt"]
q = lambda s: f"{s.median():.2f} [{s.min():.2f}-{s.max():.2f}]"
print("\ntracking RMSE deg, median [min-max] over participants:")
for ctrl, g in ok.groupby("ctrl"):
    print(f"  {ctrl} (n={len(g)}): hip {q(pd.concat([g[J[0]], g[J[1]]]))}, knee {q(pd.concat([g[J[2]], g[J[3]]]))}, pelvis {q(g[J[4]])}")
print(f"  all (n={len(ok)}): hip {q(pd.concat([ok[J[0]], ok[J[1]]]))}, knee {q(pd.concat([ok[J[2]], ok[J[3]]]))}, pelvis {q(ok[J[4]])}")
res = [c for c in ok.columns if c.startswith("reserve_rms")]
print("reserves: joint max", ok[[c for c in res if "pelvis" not in c]].max().max(), "Nm RMS; pelvis max", ok[[c for c in res if "pelvis" in c]].max().max())
print(f"solve: {q(ok.solve_s)} s, iterations {q(ok.iterations)}, peak memory {q(ok.peak_mem_gb)} GB (4 threads each, 4 at a time)")
print(f"stride {q(ok['T'])} s, model stride length {q(ok.stride_len)} m, speed {q(ok.speed)} m/s")
print(f"peak vertical GRF {q(pd.concat([ok.peak_grf_bw_r, ok.peak_grf_bw_l]))} BW; effort {q(ok.effort)}; mean activation {q(ok.mean_activation)}")
print(f"ankle range {ok[['min_ankle_angle_l', 'min_ankle_angle_r']].min().min()}..{ok[['max_ankle_angle_l', 'max_ankle_angle_r']].max().max()} deg")
print(f"exo torque RMS: hip {q(pd.concat([ok.exo_rms_exo_hip_l, ok.exo_rms_exo_hip_r]))}, knee {q(pd.concat([ok.exo_rms_exo_knee_l, ok.exo_rms_exo_knee_r]))} Nm")

# the model's own speed against the two data-based estimates from K4's stride analysis
k4 = pd.read_csv(HERE / "k4_speed_estimates.csv").rename(columns={"subj": "participant"})
k4["ctrl"] = k4.cond.map({"SM": "SM", "transparent": "TR"})
v = ok.merge(k4[["participant", "ctrl", "v_stance", "v_walkway", "SL_stance"]], on=["participant", "ctrl"])
for col in ("v_stance", "v_walkway"):
    e = v.speed - v[col]
    print(f"model speed vs {col}: r = {np.corrcoef(v.speed, v[col])[0, 1]:.2f}, mean difference {e.mean():+.3f} m/s, "
          f"mean |difference| {e.abs().mean():.3f} m/s ({100 * (e.abs() / v[col]).mean():.0f}%), n = {len(v)}")

fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
color = {"SM": "#2a78d6", "TR": "#eb6834"}
rng = np.random.default_rng(0)
for i, (lab, cols) in enumerate((("hip", J[:2]), ("knee", J[2:4]), ("pelvis tilt", J[4:]))):
    for k, ctrl in enumerate(("SM", "TR")):
        y = ok[ok.ctrl == ctrl][cols].to_numpy().ravel()
        x = i + (k - 0.5) * 0.36 + rng.uniform(-0.07, 0.07, len(y))
        axs[0].scatter(x, y, s=16, color=color[ctrl], alpha=0.7, lw=0, label=f"{ctrl} walking" if i == 0 else None)
        axs[0].plot([i + (k - 0.5) * 0.36 - 0.12, i + (k - 0.5) * 0.36 + 0.12], [np.median(y)] * 2, color="#1a1a19", lw=1.6)
axs[0].set_xticks(range(3), ["hip", "knee", "pelvis tilt"])
axs[0].set_ylabel("tracking RMSE [deg]")
axs[0].set_ylim(0)
axs[0].set_title(f"Model vs measured angles: {len(ok)} mean strides, {ok.participant.nunique()} participants", fontsize=10)
axs[0].legend(frameon=False, fontsize=9)
for ax, col, lab in ((axs[1], "v_stance", "hip travel over the planted foot"), (axs[2], "v_walkway", "walkway length / bout time")):
    for ctrl in ("SM", "TR"):
        g = v[v.ctrl == ctrl]
        ax.scatter(g[col], g.speed, s=28, color=color[ctrl], alpha=0.8, lw=0, label=f"{ctrl} walking")
    lim = [0, max(v[col].max(), v.speed.max()) * 1.08]
    ax.plot(lim, lim, color="#9b9a94", lw=1, ls="--")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("speed estimated from the data [m/s]" + chr(10) + f"({lab})")
    ax.set_ylabel("speed the model walks at [m/s]")
    ax.set_title(f"Walking speed, not imposed on the model: r = {np.corrcoef(v.speed, v[col])[0, 1]:.2f}", fontsize=10)
    ax.legend(frameon=False, fontsize=9)
for ax in axs:
    ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig("figures/k5_all_participants.png", dpi=130)
print("\nfigures/k5_all_participants.png")

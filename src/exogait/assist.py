"""K7: what the exo torque does to simulated muscle effort, one participant x condition (H4).

    micromamba run -n opensim python -u src/exogait/assist.py [ID] [condition] [mesh intervals] [ideal]
    # default HL03 SM_WALKING 50; reuses the solves already in results/exogait/moco/summary.csv

The same tracking problem (track.py) is solved with different exo torques:
    none       held at zero
    measured   the measured X2 joint-output torque, replayed (K5)
    optimised  chosen by Moco under the measured torque's budget: per actuator, the integral of squared
               torque may not exceed the measured profile's. Moco cannot constrain that integral, so each
               actuator's squared torque is priced in the effort goal and budgeted() adjusts the four
               prices until each actuator spends 90-102% of its budget. Same budget as `measured`,
               Moco's shape: the H4 test
    ideal      chosen by Moco at almost no price, within the X2 limits. The measured torque is one of its
               feasible choices, so it wins by construction: an upper bound, never the H4 test. Only
               solved when asked for (the 4th argument)
    ai         K3's predicted torque, replayed: not here yet (needs K3's predictions)

Effort = the sum of squared muscle activations, integrated over the stride and recomputed from each
solution the same way. Never the Moco objective, which includes the tracking terms.

Writes results/exogait/plots/k7_<id>_<condition>_assist.png and a row in results/exogait/moco/assist.csv.
"""

import csv
import sys

import numpy as np
import opensim as osim
import pandas as pd

import track
import x2model

CASES = ("none", "measured", "optimised", "ideal")
JOINTS = ("hip_flexion_l", "hip_flexion_r", "knee_angle_l", "knee_angle_r")
PRICE = 0.6   # first price tried per actuator, in the effort goal's units: HL03 SM settled at 0.4-1.1
NAN = float("nan")


def budgeted(subj, cond, n_mesh):
    """The `optimised` solve: price each actuator's squared torque until it spends 90-102% of the measured
    budget (2% is the mesh's quadrature against the 101-point budget), or less at the floor price. Starts at
    PRICE from the `measured` solution, then a secant step per actuator on log(spend) against log(price);
    each solve starts from the last. Returns the summary row and the prices."""
    w, spend, slope = {a: PRICE for a in track.EXO}, None, {a: 1.0 for a in track.EXO}
    guess = track.MOCO / f"{subj}_{cond}_mean_measured_m{n_mesh}.sto"
    for i in range(12):
        row = track.solve(subj, cond, n_mesh, guess, "optimised", w)
        assert row["success"], f"optimised, price step {i}: {row['status']}"
        now = {a: row[f"exo_int2_{a}"] / row[f"exo_budget_{a}"] for a in track.EXO}
        print(f"price step {i}: spend/budget {({a: round(v, 2) for a, v in now.items()})}, "
              f"price {({a: round(v, 3) for a, v in w.items()})}", flush=True)
        if all(0.9 <= now[a] <= 1.02 or (now[a] < 0.9 and w[a] == track.EXO_WEIGHT) for a in track.EXO):
            return row, w
        for a in track.EXO if spend else ():   # -d log(spend) / d log(price), from the last two solves
            if w[a] != old[a] and now[a] != spend[a]:
                slope[a] = float(np.clip(-np.log(now[a] / spend[a]) / np.log(w[a] / old[a]), 0.3, 3))
        old, spend, guess = w, now, track.MOCO / f"{subj}_{cond}_mean_optimised_m{n_mesh}.sto"
        w = {a: max(track.EXO_WEIGHT, w[a] * float(np.clip((now[a] / 0.96) ** (1 / slope[a]), 0.2, 8))) for a in track.EXO}
    raise AssertionError(f"optimised: prices did not settle on the budget in 12 steps: {now}")


def cases(subj, cond, n_mesh=50, ideal=False):
    """The solves' summary rows, solving what is not on disk. `measured` first: the others start from it."""
    rows = {}
    for case in ("measured", "none") + ("ideal",) * ideal + ("optimised",):
        out = track.MOCO / "summary.csv"
        done = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["participant", "condition", "case", "n_mesh", "check"])
        hit = done[(done.participant == subj) & (done.condition == cond) & (done.case == case)
                   & (done.n_mesh == n_mesh) & (done["check"] == "ok")]
        if len(hit):
            rows[case] = hit.iloc[-1].to_dict()
        elif case == "optimised":
            rows[case], rows["price"] = budgeted(subj, cond, n_mesh)
        else:
            start = track.MOCO / f"{subj}_{cond}_mean_measured_m{n_mesh}.sto"
            rows[case] = track.solve(subj, cond, n_mesh, start if start.exists() else track.SEED, case)
        assert rows[case]["check"] == "ok", f"{case}: {rows[case]['check']}"   # tracking bound, X2 limits, budget
    return rows


def compare(subj="HL03", cond="SM_WALKING", n_mesh=50, ideal=False):
    rows = cases(subj, cond, n_mesh, ideal)
    have = [c for c in CASES if c in rows]
    get = lambda c, k: rows[c][k] if c in rows else NAN
    e = {c: get(c, "effort") for c in CASES}
    pct = lambda a, b: round(100 * (e[a] - e[b]) / e[b], 1)
    price = rows.get("price")   # absent when `optimised` came from disk
    out = dict(participant=subj, condition=cond, n_mesh=n_mesh, **{f"effort_{c}": e[c] for c in CASES},
               measured_vs_none_pct=pct("measured", "none"), optimised_vs_none_pct=pct("optimised", "none"),
               optimised_vs_measured_pct=pct("optimised", "measured"), ideal_vs_none_pct=pct("ideal", "none"),
               **{f"rmse_max_{c}": max(get(c, f"rmse_{j}") for j in JOINTS) for c in CASES},
               **{f"objective_{c}": get(c, "objective") for c in CASES},
               objective_measured_priced=round(rows["measured"]["objective"] + sum(
                   price[a] * rows["measured"][f"exo_budget_{a}"] / x2model.EXO_F ** 2 for a in track.EXO), 5) if price else NAN,
               **{f"rate_rms_{a}_{c}": rows[c][f"exo_rate_rms_{a}"] for a in track.EXO for c in ("measured", "optimised")},
               **{f"budget_used_{a}": round(rows["optimised"][f"exo_int2_{a}"] / rows["optimised"][f"exo_budget_{a}"], 3) for a in track.EXO},
               **{f"price_{a}": round(price[a], 4) if price else NAN for a in track.EXO},
               **{f"ideal_over_budget_{a}": round(get("ideal", f"exo_int2_{a}") / get("ideal", f"exo_budget_{a}"), 2) for a in track.EXO})

    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw=dict(width_ratios=(1.2, 1.2, 0.8)))
    color = {"r": "#2a78d6", "l": "#eb6834"}
    for case, ls, lw in (("measured", "--", 1.4), ("optimised", "-", 2.2)):
        sol = osim.MocoTrajectory(str(track.MOCO / f"{subj}_{cond}_mean_{case}_m{n_mesh}.sto"))
        x = 100 * np.array(sol.getTimeMat()) / sol.getTimeMat()[-1]
        for a, c in track.EXO.items():
            axs[0 if "hip" in a else 1].plot(x, np.array(sol.getControlMat(f"/forceset/{a}")) * x2model.EXO_F,
                                             color=color[c[-1]], ls=ls, lw=lw, label=f"{case} ({c[-1].upper()})")
    for ax, joint in zip(axs, ("hip", "knee")):
        ax.axhline(0, color="#c3c2b7", lw=0.8)
        ax.set_title(f"X2 {joint} torque", fontsize=10)
        ax.set_xlabel("% stride from right heel strike")
        ax.set_ylabel("Nm")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, frameon=False)
    label = {"none": "none", "measured": "measured", "optimised": "optimised\n(same budget)", "ideal": "ideal\n(upper bound)"}
    shade = {"none": "#9b9a94", "measured": "#2a78d6", "optimised": "#1f9d6b", "ideal": "#d9d8d2"}
    bars = axs[2].bar([label[c] for c in have], [e[c] for c in have], color=[shade[c] for c in have])
    axs[2].tick_params(axis="x", labelsize=8)
    axs[2].bar_label(bars, fmt="%.3f", fontsize=9)
    axs[2].set_title("muscle effort over the stride", fontsize=10)
    axs[2].set_ylabel("sum of squared activations x time [s]")
    fig.suptitle(f"{subj} {cond}: optimised vs measured {out['optimised_vs_measured_pct']:+.1f}%, vs none "
                 f"{out['optimised_vs_none_pct']:+.1f}%; measured vs none {out['measured_vs_none_pct']:+.1f}%  "
                 f"(same torque budget, hip/knee tracked within {max(out[f'rmse_max_{c}'] for c in have):.1f} deg)", fontsize=11)
    fig.tight_layout()
    png = x2model.OUT / "plots" / f"k7_{subj}_{cond}_assist.png".lower()
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=130)
    plt.close(fig)

    path = track.MOCO / "assist.csv"
    new = not path.exists()
    with open(path, "a", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out))
        if new:
            wr.writeheader()
        wr.writerow(out)
    return out, png


if __name__ == "__main__":
    subj = sys.argv[1] if len(sys.argv) > 1 else "HL03"
    cond = sys.argv[2] if len(sys.argv) > 2 else "SM_WALKING"
    out, png = compare(subj, cond, int(sys.argv[3]) if len(sys.argv) > 3 else 50, sys.argv[4:5] == ["ideal"])
    print("\n".join(f"  {k:<34} {v}" for k, v in out.items()))
    assert all(out[f"budget_used_{a}"] <= 1.02 for a in track.EXO), "optimised went over the measured torque budget"
    # Logical bounds, beyond the solver tolerance. If one fails, a solve stopped early.
    slack = 1e-2 * out["objective_optimised"] + 1e-3
    if out["objective_measured_priced"] == out["objective_measured_priced"]:   # nan when `optimised` came from disk
        # `optimised` may copy the measured torque, paying its prices for it
        assert out["objective_optimised"] <= out["objective_measured_priced"] + slack, "optimised is worse than the measured torque at its prices"
    if out["objective_ideal"] == out["objective_ideal"]:
        # the measured torque and zero torque are both feasible for `ideal`, at almost no price
        assert out["objective_ideal"] <= min(out["objective_measured"], out["objective_none"]) + slack, "ideal is worse than a torque it may choose"
    print(f"OK: {subj} {cond}: effort none {out['effort_none']}, measured {out['effort_measured']}, optimised "
          f"{out['effort_optimised']} ({out['optimised_vs_measured_pct']:+.1f}% vs measured, {out['optimised_vs_none_pct']:+.1f}% vs none), "
          f"ideal {out['effort_ideal']}; all tracked and within the X2 limits, optimised within the measured budget. Figure: {png}")

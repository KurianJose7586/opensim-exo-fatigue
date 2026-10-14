"""Phase C on the real twin: five controllers + three ablations, one subject, the Moco grid.

    python src/jobs/sweep.py run configs/phase_c_grid.yaml --workers 8     (OpenSim env)
    python src/jobs/sweep.py collect configs/phase_c_grid.yaml
    python src/allocation/run_phase_c.py            table, sensitivity, figure, summary
    python src/allocation/run_phase_c.py --verify   + a real twin solve at every
                                                    controller's final p (OpenSim env)

Activations between grid points are trilinear in p. ponytail: linear
interpolation of an optimiser's output; a 0.1 grid step was enough on the toy,
and --verify re-solves the twin at each controller's chosen p to check it.

Sensitivity covers BOTH unmeasured fatigue constants. The review (2026-10-07)
found the margin moves more with the recovery threshold M_th than with R: at
M_th = 0.02 it was ~2% instead of ~9%. At the paper's literal "0.02% of MVC"
(M_th = 0.0002) Moco's 0.01 activation floor means no muscle ever recovers, so
min-max V is undefined (every controller reaches V = 1) and only time to V_th
separates them.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import allocate as al  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASELINES = ("knee_only", "independent", "blind")
M_TH_RANGE = (0.011, 0.02, 0.03, 0.05, 0.08)   # just above Moco's 0.01 floor .. above the lineage's 0.05
R_RANGE = (0.33, 0.5, 1.0, 2.4)                # Ma et al. 2010 mapped two ways; notes/observations.md


def grid_amap(path):
    d = np.load(path)
    g = np.unique(d["p"])
    assert len(d["p"]) == len(g) ** 3, \
        f"grid incomplete ({len(d['p'])}/{len(g) ** 3}): sweep.py run configs/phase_c_grid.yaml, then collect"
    # unconverged solves are kept as data and MocoInverse is deterministic, so rerunning
    # (even with --retry-failed, which only clears crash logs) gives the same answer
    assert d["success"].all(), \
        f"unconverged at p = {d['p'][~d['success']].tolist()}: inspect those solves (tolerance, reserves)"
    idx = np.searchsorted(g, d["p"])
    A = np.zeros((len(g),) * 3 + d["acts"].shape[1:])
    A[idx[:, 0], idx[:, 1], idx[:, 2]] = d["acts"]
    interp = RegularGridInterpolator((g, g, g), A)
    return (lambda p: interp(np.clip(np.asarray(p, float), g[0], g[-1]))[0]), float(d["cycle_s"][0]), d


def margin(res):
    """coupled vs the best of the three baselines, relative."""
    return res["coupled"]["peak_V"] / min(res[k]["peak_V"] for k in BASELINES) - 1


def sensitivity(amap, cs):
    """Margin over (M_th, R). Restores allocate's constants afterwards."""
    keep = al.M_TH, al.R
    out = {}
    try:
        for m in M_TH_RANGE:
            for r in R_RANGE:
                al.M_TH, al.R = m, r
                res = al.compare(amap, cs, kinds=("none",) + BASELINES + ("coupled",))
                out[(m, r)] = {"margin": margin(res), "coupled": res["coupled"]["peak_V"],
                               "best_baseline": min(BASELINES, key=lambda k: res[k]["peak_V"])}
    finally:
        al.M_TH, al.R = keep
    return out


def verify(res, cs):
    """Real twin solve at each controller's final p; steady-state worst V from it."""
    import tempfile, os
    sys.path.insert(0, str(ROOT / "src" / "musculoskeletal"))
    import twin
    os.chdir(tempfile.mkdtemp())    # Moco drops its stop-file in the cwd
    rows = {}
    for k, r in res.items():
        p = np.round(r["final_p"], 6)
        if not p.any():
            continue
        t = twin.activations(p=p)
        assert t["success"], f"twin did not converge at {p}"
        A, B = al.cycle_map(t["acts"], t["cycle_s"], al.C_ZHANG)
        A0, B0 = al.cycle_map(r["acts_final"], cs, al.C_ZHANG)
        rows[k] = {"p": p.tolist(), "interp": float((B0 / (1 - A0)).max()), "twin": float((B / (1 - A)).max()),
                   "worst_twin": al.MUSCLES[int((B / (1 - A)).argmax())]}
        print(f"  {k:<19} p {np.array2string(p, precision=3):<22} steady worst V: "
              f"interpolated {rows[k]['interp']:.3f}   real solve {rows[k]['twin']:.3f} ({rows[k]['worst_twin']})")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="re-solve the twin at each controller's p")
    a = ap.parse_args()

    path = ROOT / "results" / "phase_c_grid.npz"
    amap, cs, d = grid_amap(path)
    print(f"twin grid: {len(d['p'])} Moco solves, cycle {cs:.2f} s, "
          f"joint reserve rms median {np.median(d['reserve_rms']):.2f} Nm\n")
    res = al.compare(amap, cs, kinds=al.CONTROLLERS + al.ABLATIONS)
    al.table(res)
    print(f"\ncoupled vs best baseline: {margin(res):+.1%}")

    # the budget is in fractions of each joint's peak; the same 0.6 is different torque
    peak = d["peak_moment"][0] if "peak_moment" in d else None
    if peak is not None:
        print(f"\ntorque capacity used [Nm] (peak net moment hip {peak[0]:.0f}, knee {peak[1]:.0f}, "
              f"ankle {peak[2]:.0f}):")
        for k, r in res.items():
            print(f"  {k:<19} {r['mean_p'] @ peak:6.1f}")

    sens = sensitivity(amap, cs)
    print("\ncoupled vs best baseline, by recovery threshold M_th (rows) and recovery rate R (cols):")
    print(f"{'M_th':>8}" + "".join(f"{'R=' + str(r):>10}" for r in R_RANGE))
    for m in M_TH_RANGE:
        print(f"{m:>8}" + "".join(f"{sens[(m, r)]['margin']:>+10.1%}" for r in R_RANGE))

    if a.verify:
        print("\nreal twin solve at each controller's final allocation:")
        for k in res:
            res[k]["acts_final"] = amap(res[k]["final_p"])
        checked = verify(res, cs)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4))
    for k in al.CONTROLLERS:
        ax.plot(np.arange(len(res[k]["V"])) * cs / 60, res[k]["V"].max(1), label=k)
    ax.set(xlabel="walking time [min]", ylabel="worst-muscle fatigue V",
           title="Phase C: equal assistance budget, different allocation")
    ax.legend(frameon=False)
    fig.tight_layout()
    (ROOT / "figures").mkdir(exist_ok=True)
    fig.savefig(ROOT / "figures" / "phase_c_fatigue.png", dpi=150)

    summary = {k: {"peak_V": r["peak_V"], "worst": r["worst"], "t_th_min": r["t_th_min"],
                   "mean_p": r["mean_p"].tolist(), "final_p": r["final_p"].tolist(),
                   **({"torque_Nm": float(r["mean_p"] @ peak)} if peak is not None else {})}
               for k, r in res.items()}
    summary["sensitivity"] = [{"M_th": m, "R": r, **v} for (m, r), v in sens.items()]
    if a.verify:
        summary["verified"] = checked
    (ROOT / "results" / "phase_c_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n-> figures/phase_c_fatigue.png, results/phase_c_summary.json")

"""Phase C on the real twin: five controllers, one subject, the Moco assistance grid.

    python src/jobs/sweep.py run configs/phase_c_grid.yaml --workers 8     (OpenSim env)
    python src/jobs/sweep.py collect configs/phase_c_grid.yaml
    python src/allocation/run_phase_c.py

Activations between grid points are trilinear in p. ponytail: linear
interpolation of an optimiser's output; a 0.1 grid step was enough on the toy,
refine the grid if controllers sit between points and disagree.
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import allocate as al  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def grid_amap(path):
    d = np.load(path)
    g = np.unique(d["p"])
    assert len(d["p"]) == len(g) ** 3 and d["success"].all(), \
        "grid incomplete or unconverged -- rerun: sweep.py run configs/phase_c_grid.yaml --retry-failed"
    idx = np.searchsorted(g, d["p"])
    A = np.zeros((len(g),) * 3 + d["acts"].shape[1:])
    A[idx[:, 0], idx[:, 1], idx[:, 2]] = d["acts"]
    interp = RegularGridInterpolator((g, g, g), A)
    return (lambda p: interp(np.clip(np.asarray(p, float), g[0], g[-1]))[0]), float(d["cycle_s"][0]), d


if __name__ == "__main__":
    path = ROOT / "results" / "phase_c_grid.npz"
    amap, cs, d = grid_amap(path)
    print(f"twin grid: {len(d['p'])} Moco solves, cycle {cs:.2f} s, "
          f"joint reserve rms median {np.median(d['reserve_rms']):.2f} Nm\n")
    res = al.compare(amap, cs)
    al.table(res)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4))
    for k, r in res.items():
        ax.plot(np.arange(len(r["V"])) * cs / 60, r["V"].max(1), label=k)
    ax.set(xlabel="walking time [min]", ylabel="worst-muscle fatigue V",
           title="Phase C: equal assistance budget, different allocation")
    ax.legend(frameon=False)
    fig.tight_layout()
    (ROOT / "figures").mkdir(exist_ok=True)
    fig.savefig(ROOT / "figures" / "phase_c_fatigue.png", dpi=150)

    summary = {k: {"peak_V": r["peak_V"], "worst": r["worst"], "t_th_min": r["t_th_min"],
                   "mean_p": r["mean_p"].tolist()} for k, r in res.items()}
    (ROOT / "results" / "phase_c_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n-> figures/phase_c_fatigue.png, results/phase_c_summary.json")

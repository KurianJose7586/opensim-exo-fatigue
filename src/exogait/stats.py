"""J7: paired tests and figures for H1-H4, and the prediction table for RO6.

    python src/exogait/stats.py [test|val]     # default test. A few seconds; needs the predict rows of that split

In:  results/exogait/predict/<model>.csv (evaluate.py), results/exogait/moco/assist.csv and summary.csv (assist.py)
Out: results/exogait/stats/h1.csv ... h4.csv, accel.csv, prediction.csv; figures/exogait/<split>_h1.png ... _h4.png, _accel.png

Every test is a two-sided Wilcoxon signed-rank test across participants on paired values. Effect
size: the matched-pairs rank-biserial correlation r, +1 when the first arm is better for everyone.
    H1  personalised vs population, full inputs
    H2  with vs without phase (the no_phase arm also drops gait_state and stance_alpha)
    H3  with vs without mode
    H4  optimised vs measured assistance: muscle effort over the mean SM walking stride (K7)
    accel  with vs without joint acceleration. Not one of the mentor's hypotheses: exploratory
One primary endpoint per hypothesis, fixed on the validation blocks before the test blocks were scored
(PRIMARY): the gauge torque (the torque at the joint: the assistance), per participant the RMSE over
both controllers per joint, then the mean of hip and knee.
    H1  the LSTM, walking. Its personalised model is its population model fine-tuned (lstm.py)
    H2  the random forest, personalised, walking. The LSTM has no no_phase arm
    H3  the LSTM, personalised, all five modes pooled. The plan said walking; but what the mode input
        can add is telling the modes apart, and walking alone cannot show that
Secondary: the same endpoint for every other model and for the motor torque, and every mode x
controller x joint cell. Holm-corrected together within a hypothesis. A cell needs 6 pairs for a test:
stairs cells use the participants who have scored strides there.
H4's secondaries: optimised vs exo off, measured vs exo off, and TR measured vs exo off (not an H4
test: in TR the torque carries the device, notes "K6").
"""

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon

from preprocess import MODES, ROOT

PREDICT, MOCO = ROOT / "results" / "exogait" / "predict", ROOT / "results" / "exogait" / "moco"
OUT, FIG = ROOT / "results" / "exogait" / "stats", ROOT / "figures" / "exogait"
ORDER = ["phase_mean", "ridge", "rf", "bag", "lstm"]
LABEL = dict(zip(ORDER, ("Phase mean", "Ridge", "Random forest", "Bagged trees", "LSTM")))
ARMS = {"h1": (("personalised", "full"), ("population", "full")), "h2": ("full", "no_phase"), "h3": ("full", "no_mode"),
        "accel": ("full", "no_accel")}
PRIMARY = {"h1": ("lstm", "walk"), "h2": ("rf", "walk"), "h3": ("lstm", "all"), "accel": (None, "walk")}   # model, modes of the endpoint
NAMES = {"h1": ("personalised", "population"), "h2": ("with phase", "without phase"), "h3": ("with mode", "without mode"),
         "accel": ("with acceleration", "without acceleration"), "h4": ("optimised", "measured")}
INK, INK2, GRID, BLUE, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#2a78d6", "#fcfcfb"


def paired(a, b):
    """n, medians, how often a is lower, Wilcoxon p and the rank-biserial r (+ = a lower) for two Series on one index."""
    a, b = a.align(b, join="inner")
    gain = (b - a).dropna()
    rank = rankdata(np.abs(gain[gain != 0]))
    plus, minus = rank[gain[gain != 0] > 0].sum(), rank[gain[gain != 0] < 0].sum()
    ok = len(gain) >= 6 and plus + minus > 0
    return dict(n=len(gain), a_median=a[gain.index].median(), b_median=b[gain.index].median(), gain_median=gain.median(),
                a_lower=int((gain > 0).sum()), p=wilcoxon(gain).pvalue if ok else np.nan, r_rb=(plus - minus) / (plus + minus) if ok else np.nan)


def holm(p):
    """Holm-adjusted p-values; NaN stays NaN and is not counted."""
    p = np.asarray(p, float)
    out, ok = np.full(len(p), np.nan), ~np.isnan(p)
    order = np.argsort(p[ok])
    out[np.flatnonzero(ok)[order]] = np.minimum(1, np.maximum.accumulate((ok.sum() - np.arange(ok.sum())) * p[ok][order]))
    return out


def endpoint(r, modes):
    """Per participant: RMSE over the scored strides of both controllers (and the given modes) per joint, then the mean of hip and knee."""
    r = r[r["mode"].isin(modes)].assign(se=r.rmse ** 2 * r.n_strides)
    j = r.groupby(["participant", "joint"])[["se", "n_strides"]].sum()
    return np.sqrt(j.se / j.n_strides).groupby("participant").mean()


def prediction_tests(r, h):
    """Every comparison of one hypothesis: the pooled endpoints (walking, all modes) and each mode x controller x joint cell."""
    rows = []
    for (model, torque), g in r.groupby(["model", "torque"]):
        for scheme in (["both"] if h == "h1" else ["personalised", "population"]):
            pick = (lambda k: g[(g.scheme == ARMS[h][k][0]) & (g.ablation == ARMS[h][k][1])]) if h == "h1" else \
                   (lambda k: g[(g.scheme == scheme) & (g.ablation == ARMS[h][k])])
            a, b = pick(0), pick(1)
            if a.empty or b.empty:
                continue
            key = dict(hypothesis=h, model=model, torque=torque, scheme=scheme)
            for name, modes in (("walk", ["walk"]), ("all", list(MODES.values()))):
                first = (model, name) == PRIMARY[h] and torque == "gauge" and scheme in ("both", "personalised")
                rows.append(key | dict(kind="primary" if first else "secondary", mode=name, controller="both", joint="mean")
                            | paired(endpoint(a, modes), endpoint(b, modes)))
            cell = ["mode", "controller", "joint"]
            x, y = (k.pivot(index="participant", columns=cell, values="rmse") for k in (a, b))
            rows += [key | dict(kind="secondary", **dict(zip(cell, c))) | paired(x[c], y[c]) for c in x.columns.intersection(y.columns)]
    t = pd.DataFrame(rows)
    if h == "accel":
        t["kind"] = "exploratory"
    t["p_holm"] = np.where(t.kind == "primary", np.nan, holm(t.p.where(t.kind != "primary")))
    return t


def effort_tests():
    a = pd.read_csv(MOCO / "assist.csv").drop_duplicates(["participant", "condition", "n_mesh"], keep="last")
    a = a[(a.condition == "SM_WALKING") & (a.n_mesh == 50)].set_index("participant")
    s = pd.read_csv(MOCO / "summary.csv")
    s = s[(s.n_mesh == 50) & (s["check"] == "ok") & (s.condition == "transparent_WALKING")].drop_duplicates(["participant", "case"], keep="last")
    tr = s.pivot(index="participant", columns="case", values="effort").dropna(subset=["measured", "none"])
    rows = [dict(hypothesis="h4", kind=kind, controller=c, a=x, b=y) | paired(d[f"effort_{x}"] if c == "SM" else d[x], d[f"effort_{y}"] if c == "SM" else d[y])
            for kind, c, d, x, y in (("primary", "SM", a, "optimised", "measured"), ("secondary", "SM", a, "optimised", "none"),
                                     ("secondary", "SM", a, "measured", "none"), ("secondary", "TR", tr, "measured", "none"))]
    t = pd.DataFrame(rows)
    t["p_holm"] = np.where(t.kind == "primary", np.nan, holm(t.p.where(t.kind != "primary")))
    return t, a


def slopes(ax, a, b, names, title):
    """Paired values, one line per participant, the medians in ink."""
    a, b = a.align(b, join="inner")
    ax.plot([0, 1], [a, b], color=BLUE, lw=1, alpha=0.55, marker="o", ms=3.5)
    ax.plot([0, 1], [a.median(), b.median()], color=INK, lw=2.2, marker="o", ms=6)
    for x, v, ha in ((0, a.median(), "right"), (1, b.median(), "left")):
        ax.annotate(f"{v:.2f}", (x, v), xytext=(-9 if x == 0 else 9, 0), textcoords="offset points", ha=ha, va="center", color=INK, fontsize=9)
    ax.set_xticks([0, 1], names, color=INK2, fontsize=9)
    ax.set_xlim(-0.45, 1.45)
    ax.set_title(title, loc="left", fontsize=9.5, color=INK)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.tick_params(length=0, colors=INK2, labelsize=9)
    for side in ax.spines.values():
        side.set_visible(False)


def figure(path, panels, names, ylabel, title):
    fig, axs = plt.subplots(1, len(panels), figsize=(2.5 * len(panels) + 1, 4.2), sharey=True, facecolor=SURFACE, squeeze=False)
    for ax, (label, a, b) in zip(axs[0], panels):
        ax.set_facecolor(SURFACE)
        slopes(ax, a, b, names, label)
    axs[0, 0].set_ylabel(ylabel, color=INK2, fontsize=9)
    axs[0, 0].set_ylim(0)
    fig.suptitle(title, x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    assert np.allclose(holm([0.01, 0.04, 0.03, np.nan])[:3], [0.03, 0.06, 0.06]) and np.isnan(holm([0.01, np.nan])[1])
    toy = paired(pd.Series(np.arange(8.0)), pd.Series(np.arange(8.0) + 1 + np.arange(8) / 10))
    assert toy["r_rb"] == 1 and toy["a_lower"] == 8 and abs(toy["p"] - 2 / 2 ** 8) < 1e-12, toy

    split = sys.argv[1] if len(sys.argv) > 1 else "test"
    files = [f for f in sorted(PREDICT.glob("*.csv")) if not f.stem.endswith("_pred")]
    r = pd.concat(pd.read_csv(f) for f in files)
    r = r[r.split == split]
    assert len(r), f"no {split} rows in {PREDICT}: run evaluate.py all{' --test' if split == 'test' else ''} first"
    order = [m for m in ORDER if m in set(r.model)]
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    scored = f"scored on the {'test' if split == 'test' else 'VALIDATION'} blocks"
    for h in ARMS:
        t = prediction_tests(r, h)
        t.insert(1, "split", split)
        t.to_csv(OUT / f"{split}_{h}.csv", index=False)
        full = r[r.ablation == "full"] if h == "h1" else r[r.scheme == "personalised"]
        arm = (lambda m, k: full[(full.model == m) & (full.torque == "gauge") & (full.scheme == ARMS[h][k][0])]) if h == "h1" else \
              (lambda m, k: full[(full.model == m) & (full.torque == "gauge") & (full.ablation == ARMS[h][k])])
        modes = list(MODES.values()) if h == "h3" else ["walk"]
        panels = [(LABEL[m], endpoint(arm(m, 0), modes), endpoint(arm(m, 1), modes)) for m in order if len(arm(m, 0)) and len(arm(m, 1))]
        figure(FIG / f"{split}_{h}.png", panels, NAMES[h], "RMSE of the torque at the joint (Nm)",
               f"{h.upper()}: {NAMES[h][0]} vs {NAMES[h][1]}. {'All five modes' if h == 'h3' else 'Walking'}, one line per participant, {scored}")
        top = t[t.kind != "secondary"] if (t.kind == "primary").any() else t[(t["mode"] == "walk") & (t.controller == "both") & (t.torque == "gauge")]
        for row in top.itertuples():
            print(f"{h} {row.kind}: {row.model}, {row.torque}, {row.scheme}, {row.mode}: {row.a_median:.2f} vs {row.b_median:.2f} Nm, "
                  f"{NAMES[h][0]} lower in {row.a_lower}/{row.n}, p = {row.p:.2g}, r = {row.r_rb:+.2f}")
        sec = t[t.kind == "secondary"]
        print(f"   secondary: {len(sec)} comparisons, {int((sec.p_holm < 0.05).sum())} significant after Holm, "
              f"{int(((sec.p_holm < 0.05) & (sec.gain_median < 0)).sum())} of them against the hypothesis")

    t, a = effort_tests()
    t.to_csv(OUT / "h4.csv", index=False)
    figure(FIG / "h4.png", [("optimised vs measured", a.effort_optimised, a.effort_measured), ("optimised vs exo off", a.effort_optimised, a.effort_none),
                            ("measured vs exo off", a.effort_measured, a.effort_none)], ("", ""),
           "muscle effort over the stride (sum of squared activations x s)",
           f"H4: simulated muscle effort over the mean SM walking stride, {len(a)} participants (left value: the first named case)")
    for row in t.itertuples():
        print(f"h4 {row.kind}: {row.controller} {row.a} vs {row.b}: {row.a_median:.3f} vs {row.b_median:.3f}, lower in {row.a_lower}/{row.n}, "
              f"p = {row.p:.2g}, r = {row.r_rb:+.2f}" + ("" if row.kind == "primary" else f", Holm p = {row.p_holm:.2g}"))

    per = r[r.ablation == "full"].groupby(["model", "scheme", "torque", "mode", "participant"])[["rmse", "mae", "r2", "nrmse", "infer_ms"]].mean()
    table = per.groupby(["model", "scheme", "torque", "mode"]).agg(["mean", "std"]).round(3)
    table.columns = [f"{m}_{s}" for m, s in table.columns]
    table.insert(0, "participants", per.groupby(["model", "scheme", "torque", "mode"]).size())
    table.reset_index().to_csv(OUT / f"{split}_prediction.csv", index=False)
    assert all((pd.read_csv(OUT / f"{split}_{h}.csv").kind == "primary").sum() == (PRIMARY[h][0] in order) for h in ("h1", "h2", "h3")), "a hypothesis lacks its primary row"
    print(f"OK: {split} rows of {order}; tables in {OUT.relative_to(ROOT)}, figures in {FIG.relative_to(ROOT)}")

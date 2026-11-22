"""J6: the authors' EMG for HL01-HL05 -> muscle-activity envelopes on J3's strides (RO5).

    python src/exogait/emg.py HL01 HL03      # or: all. Under a minute per participant

The EMG is not in the Dryad release. The authors sent it on 2026-11-19 (Lhoste, Vianello et al.):
data/raw/exogait_emg/HL01-HL05_EMG/, never edited; its README is the reference. In short:
    channels  emg_1-5 left leg, emg_6-10 right: rectus femoris, vastus lateralis, biceps femoris,
              tibialis anterior, medial gastrocnemius (channel_map.csv)
    raw       volts, unfiltered, about 1008.5 Hz (the exact rate is fitted per file in the index)
    time      exo time = exo_t_start + fit_t0_s + k / fit_fs_hz for data row k, from corc_first on.
              Accurate to about 0.1 s: fine for envelopes on a 3 s stride, not for latencies
Envelope as the authors made theirs: 20-450 Hz band-pass, rectify, 6 Hz low-pass (4th-order
Butterworth, zero phase). Each kept stride of preprocess.py whose rows lie in a run with EMG gets the
envelope at its 101 instants (the same instants as its strides.csv rows). Strides not wholly covered
by EMG are left out.
Normalisation: per participant and channel, by the peak of the mean walking-stride envelope (both
controllers), so 1 = that muscle's usual walking peak. No MVC trials exist. These are muscle-activity
features, not fatigue measures.

Writes data/processed/exogait/<ID>_emg.csv: participant, stride, leg, mode, controller, phase, then
rf, vl, bf, ta, mg for the stride's own leg and rf_other ... mg_other for the other leg.
ponytail: no notch filters for HL04's ~74 Hz harmonics; the 6 Hz envelope barely sees them.
"""
import sys

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt

import preprocess
from preprocess import OUT, ROOT

PKG = ROOT / "data" / "raw" / "exogait_emg" / "HL01-HL05_EMG"
SUBJECTS = ["HL01", "HL02", "HL03", "HL04", "HL05"]
MUSCLES = ["rf", "vl", "bf", "ta", "mg"]
CHANNELS = {"L": [f"emg_{i}" for i in range(1, 6)], "R": [f"emg_{i}" for i in range(6, 11)]}


def envelope(x, fs):
    y = sosfiltfilt(butter(4, [20, 450], btype="band", fs=fs, output="sos"), x - x.mean(0), axis=0)
    return sosfiltfilt(butter(4, 6, fs=fs, output="sos"), np.abs(y), axis=0)


def process(subj):
    index = pd.read_csv(PKG / "emg_file_index.csv")
    runs = index[(index.subject == subj) & index.exo_run.notna() & index.emg_file.notna()].sort_values("exo_row_start")
    feats = pd.read_csv(OUT / f"{subj}_stride_features.csv")
    out, n_runs = [], 0
    for r in runs.itertuples():
        mine = feats[(feats.row_start >= r.exo_row_start) & (feats.row_end < r.exo_row_end_excl)]
        if mine.empty:
            continue
        emg = pd.read_csv(PKG / r.emg_file, usecols=CHANNELS["L"] + CHANNELS["R"])
        t = r.exo_t_start + r.fit_t0_s + np.arange(len(emg)) / r.fit_fs_hz
        keep = t >= r.exo_t_start + r.corc_first
        env = envelope(emg[CHANNELS["L"] + CHANNELS["R"]].to_numpy()[keep], r.fit_fs_hz)
        t = t[keep]
        covered = mine[(mine.t_start >= t[0]) & (mine.t_end <= t[-1])]
        n_runs += 1
        for s in covered.itertuples():
            tn = np.linspace(s.t_start, s.t_end, 101)   # preprocess.py's instants
            e = {c: np.interp(tn, t, env[:, j]) for j, c in enumerate(CHANNELS["L"] + CHANNELS["R"])}
            other = "R" if s.leg == "L" else "L"
            out.append(pd.DataFrame({"participant": subj, "stride": s.stride, "leg": s.leg, "mode": s.mode, "controller": s.controller,
                                     "phase": preprocess.PHASE,
                                     **{m: e[c] for m, c in zip(MUSCLES, CHANNELS[s.leg])},
                                     **{f"{m}_other": e[c] for m, c in zip(MUSCLES, CHANNELS[other])}}))
    d = pd.concat(out, ignore_index=True)
    # normalise each channel by the peak of its mean walking stride
    walk = d[d["mode"] == "walk"]
    for leg in ("L", "R"):
        other = "R" if leg == "L" else "L"
        for m in MUSCLES:
            own = walk[walk.leg == leg].groupby("phase")[m].mean().max()   # channel of leg `leg`, from its own strides
            d.loc[d.leg == leg, m] /= own
            d.loc[d.leg == other, f"{m}_other"] /= own
    return d, n_runs, len(feats)


def check(d, subj):
    """The README's checks, on our strides: in level walking the vastus lateralis is a stance muscle, the
    tibialis anterior peaks near heel strike or in swing, the medial gastrocnemius in late stance."""
    w = d[d["mode"] == "walk"].groupby(["leg", "phase"])[MUSCLES].mean()
    for leg in ("L", "R"):
        p = w.loc[leg]
        assert np.isclose(p.max().max(), 1, atol=0.02) or p.max().max() <= 1.02, (subj, leg, p.max())
        vl = p.vl.to_numpy()
        assert vl[:50].mean() > vl[50:].mean(), f"{subj} {leg}: vastus lateralis not a stance muscle"
        mg = int(p.mg.idxmax())
        assert 20 <= mg <= 70, f"{subj} {leg}: medial gastrocnemius peaks at {mg}%"
        ta = int(p.ta.idxmax())
        assert ta <= 25 or ta >= 55, f"{subj} {leg}: tibialis anterior peaks at {ta}% (mid-stance)"   # loading response or swing; double support is long here
    return {leg: dict(vl_stance=round(float(w.loc[leg].vl[:50].mean() / w.loc[leg].vl[50:].mean()), 2),
                      mg_peak=int(w.loc[leg].mg.idxmax()), ta_peak=int(w.loc[leg].ta.idxmax()),
                      bf_peak=int(w.loc[leg].bf.idxmax()), rf_peak=int(w.loc[leg].rf.idxmax())) for leg in ("L", "R")}


MODEL = {"rf": "rect_fem", "vl": "vasti", "bf": "hamstrings", "ta": "tib_ant", "mg": "gastroc"}


def versus_model(folder="moco_scaled", n_mesh=50):
    """The twin's muscle activations against the EMG it never saw: walking, each controller, every HL
    participant whose `measured` solve passed K5's checks. The solve's stride starts at right heel strike, so
    its right-leg activations are set against the EMG of each leg's own muscles over its own strides.
    Shape only (Pearson r of the mean profiles; the peak's position): EMG amplitude has no absolute scale
    here, and the model's muscles are generic. -> results/exogait/emg_vs_model.csv, figures/exogait/emg_vs_model.png"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import opensim as osim
    moco = ROOT / "results" / "exogait" / folder
    summ = pd.read_csv(moco / "summary.csv")
    summ = summ[(summ.case == "measured") & (summ.n_mesh == n_mesh)].drop_duplicates(["participant", "condition"], keep="last")
    rows, curves = [], {m: {"emg": [], "model": []} for m in MUSCLES}
    for r in summ[summ.participant.isin(SUBJECTS) & summ.condition.str.endswith("WALKING")].itertuples():
        if r.check != "ok":
            continue
        ctrl = preprocess.CONTROLLERS[r.condition.split("_")[0]]
        e = pd.read_csv(OUT / f"{r.participant}_emg.csv")
        e = e[(e["mode"] == "walk") & (e.controller == ctrl)].groupby("phase")[MUSCLES].mean()
        sol = osim.MocoTrajectory(str(moco / f"{r.participant}_{r.condition}_mean_measured_m{n_mesh}.sto"))
        t = np.array(sol.getTimeMat())
        for m, name in MODEL.items():
            a = np.interp(preprocess.PHASE / 100, (t - t[0]) / (t[-1] - t[0]), np.array(sol.getStateMat(f"/{name}_r/activation")))
            x = e[m].to_numpy()
            rows.append(dict(participant=r.participant, controller=ctrl, muscle=m, model_muscle=name,
                             r=round(float(np.corrcoef(x, a)[0, 1]), 3), emg_peak=int(np.argmax(x)), model_peak=int(np.argmax(a))))
            curves[m]["emg"].append(x / x.max())
            curves[m]["model"].append(a / a.max())
    t = pd.DataFrame(rows)
    t.to_csv(ROOT / "results" / "exogait" / "emg_vs_model.csv", index=False)
    fig, axs = plt.subplots(1, 5, figsize=(15, 3.4), sharey=True)
    names = {"rf": "rectus femoris", "vl": "vastus lateralis", "bf": "biceps fem. (model: hamstrings)", "ta": "tibialis anterior",
             "mg": "medial gastrocnemius"}
    for ax, m in zip(axs, MUSCLES):
        for k, col, lab in (("emg", "#52514e", "EMG (measured)"), ("model", "#2a78d6", "model activation")):
            y = np.array(curves[m][k])
            ax.fill_between(preprocess.PHASE, y.mean(0) - y.std(0), y.mean(0) + y.std(0), color=col, alpha=0.15, lw=0)
            ax.plot(preprocess.PHASE, y.mean(0), color=col, lw=2, label=lab)
        ax.set_title(names[m] + f"\nmedian r = {t[t.muscle == m].r.median():.2f}", fontsize=9.5, loc="left")
        ax.set_xlabel("% of the stride, from heel strike")
        ax.grid(alpha=0.25)
    axs[0].set_ylabel("each curve / its peak")
    axs[0].legend(fontsize=8, frameon=False)
    fig.suptitle(f"The twin's muscle activations against EMG it never saw: walking, {t.groupby(['participant', 'controller']).ngroups} solves "
                 f"(HL participants, both controllers), mean ± SD", x=0.01, ha="left", fontsize=10.5)
    fig.tight_layout()
    png = ROOT / "figures" / "exogait" / "emg_vs_model.png"
    fig.savefig(png, dpi=130)
    plt.close(fig)
    return t, png


if __name__ == "__main__":
    if sys.argv[1:2] == ["model"]:   # emg.py model: the twin's activations against the EMG
        t, png = versus_model(*sys.argv[2:3])
        print(t.groupby("muscle")[["r", "emg_peak", "model_peak"]].median().round(2).to_string())
        print(f"OK: {len(t)} muscle x solve rows. Figure: {png}")
        sys.exit()
    ids = SUBJECTS if sys.argv[1:] in ([], ["all"]) else sys.argv[1:]
    for subj in ids:
        d, n_runs, n_strides = process(subj)
        peaks = check(d, subj)
        preprocess.write(d, OUT / f"{subj}_emg.csv")
        n = d.groupby(["mode", "controller"]).stride.nunique()
        print(f"OK: {subj}: {d.stride.nunique()} of {n_strides} kept strides have EMG, from {n_runs} runs; "
              f"walk {n.get(('walk', 'TR'), 0)} TR + {n.get(('walk', 'SM'), 0)} SM. Peaks (% stride): {peaks}")

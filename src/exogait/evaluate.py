"""J5/K3: torque models, all fitted and scored the same way (RO2; H1-H3).

    python src/exogait/evaluate.py                  # self-check: the two baselines on AB68 and HL03, val blocks
    python src/exogait/evaluate.py all              # the baselines, every participant, scored on val
    python src/exogait/evaluate.py all --test       # the final pass: refit on train + val, score test, once
    python src/exogait/evaluate.py all --models rf,bag,lstm   # K3's models, on Kurian's machine (hours)

In: data/processed/exogait/<ID>_strides.csv of every participant on disk, and splits.csv.
Out: results/exogait/predict/<model>.csv, one row per RESULT_KEY with rmse, mae, r2, nrmse, infer_ms,
n_strides, n_train_strides, host, commit (a re-run replaces its rows); and with --test
<model>_<ID>_pred.csv, the full-input predictions on the test strides (K7 replays them).
The self-check writes to predict/selfcheck/ instead.

What is compared, per participant, on the same scored strides:
    scheme    personalised: fitted on the participant's own blocks.
              population: fitted on every other participant's (leave one participant out).          H1
    ablation  full; no_phase: without phase, gait_state and stance_alpha, which all encode phase;    H2
              no_mode;                                                                               H3
              no_accel: without the joint accelerations (below). Not one of the mentor's hypotheses:
              it tests K6's finding that half the motor torque is rotor inertia x acceleration
    torque    motor (JointTorques) and gauge (JointTorquesViaGauges, the torque at the joint; the
              one K5-K7 replay), fitted separately (J1 Q9)
Fitted on train blocks and scored on val blocks. With --test: fitted on train + val, scored on test.
A condition with one block has no scored stride, so it is in neither scheme and H1 stays paired.
Metrics per participant x mode x controller x joint, over every phase point of the scored strides:
RMSE, MAE, R2, and nRMSE = RMSE / the range of the measured torque over all that participant's
strides in that mode (both controllers, so SM and TR share a scale). infer_ms: the predict call,
per stride.

Inputs are split.ALLOWED plus "accel": the time derivative of every allowed velocity, taken along the
stride in features(). It is derived from recorded inputs only, so it exists at inference.
A model is built from the inputs it may use and the number of training rows, takes stride rows (a
DataFrame, whole strides, 101 rows each in phase order) and returns (n, 2) Nm: hip, knee.
    phase_mean  the training torque averaged over mode, controller, leg and phase, whichever the ablation leaves
    ridge       StandardScaler + Ridge(alpha 1) on features(): the scaler sees the training rows only.
                Not tuned: val RMSE is the same to 0.1% for alpha 0.01-100 (four participants, both schemes)
    rf, bag     RandomForestRegressor on features(), 100 trees, leaves of 5 rows or more. rf tries a third
                of the inputs at each split; bag tries all of them, which is bagged trees
                (BaggingRegressor(DecisionTreeRegressor()) with the same trees, only slower). Each tree
                sees at most TREE_ROWS rows: a full-depth forest on a 400,000-row fold would not fit in memory
    lstm        lstm.py (K3)
Every model here is offline: phase and the 101-point time base need the next heel strike (J1 Q4).
"""

import argparse
import platform
import subprocess
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from preprocess import CONTROLLERS, MODES, OUT, ROOT, read_strides
from split import ALLOWED, TARGETS

RESULTS = ROOT / "results" / "exogait" / "predict"
SCHEMES = ("personalised", "population")
INPUTS = ALLOWED + ["accel"]
ABLATIONS = {"full": [], "no_phase": ["phase", "gait_state", "stance_alpha"], "no_mode": ["mode"], "no_accel": ["accel"]}
TREE_ROWS = 60_000   # rows per tree. Personalised fits have fewer and use them all
N_JOBS = 8           # of 16 threads: the laptop stays usable
CATEGORIES = {"mode": list(MODES.values()), "controller": list(CONTROLLERS.values()), "leg": ["L", "R"],
              "group": ["AB", "HL"], "gait_state": [0, 1, 2, 3]}
RESULT_KEY = ["model", "scheme", "ablation", "torque", "participant", "mode", "controller", "joint", "split"]
ID = ["participant", "stride", "leg", "mode", "controller", "phase", "t"]


def features(d, cols):
    """Stride rows -> input matrix: numbers as they are, the velocities' derivative along the stride ("accel"),
    phase also as two harmonics (it is cyclic), categories one-hot."""
    assert len(d) % 101 == 0 and (d.phase.to_numpy()[::101] == 0).all(), "features() needs whole strides in phase order"
    X = [d[c].to_numpy(float) for c in cols if c not in CATEGORIES and c != "accel"]
    if "accel" in cols:
        # ponytail: a central difference on the 101-point grid (13-110 ms apart). A Savitzky-Golay derivative of
        # the raw 333 Hz velocity is the upgrade if the motor torque's residual turns out to matter
        t = d.t.to_numpy().reshape(-1, 101)
        step = (t[:, -1:] - t[:, :1]) / 100
        X += [(np.gradient(d[c].to_numpy(float).reshape(-1, 101), axis=1) / step).ravel() for c in cols if c.endswith("_qd") or "_qd_" in c]
    if "phase" in cols:
        a = 2 * np.pi * d.phase.to_numpy() / 100
        X += [f(h * a) for h in (1, 2) for f in (np.sin, np.cos)]
    X += [(d[c].to_numpy() == v).astype(float) for c in cols if c in CATEGORIES for v in CATEGORIES[c][1:]]
    return np.column_stack(X)


class PhaseMean:
    """Baseline 1: the training torque averaged over the keys the ablation leaves."""

    def __init__(self, cols, n=None):
        self.keys = [c for c in ("mode", "controller", "leg", "phase") if c in cols]

    def fit(self, d, y):
        self.table = d[self.keys].assign(hip=y[:, 0], knee=y[:, 1]).groupby(self.keys).mean()
        self.rest = y.mean(axis=0)   # for a key combination the training rows lack
        return self

    def predict(self, d):
        p = d[self.keys].join(self.table, on=self.keys)[["hip", "knee"]].to_numpy()
        return np.where(np.isnan(p), self.rest, p)


def forest(max_features):
    return lambda cols, n: make_pipeline(
        FunctionTransformer(features, kw_args={"cols": cols}),
        RandomForestRegressor(100, min_samples_leaf=5, max_features=max_features, max_samples=TREE_ROWS if n > TREE_ROWS else None,
                              n_jobs=N_JOBS, random_state=0))


MODELS = {"phase_mean": PhaseMean,
          "ridge": lambda cols, n: make_pipeline(FunctionTransformer(features, kw_args={"cols": cols}), StandardScaler(), Ridge()),
          "rf": forest(1 / 3), "bag": forest(1.0)}


def metrics(y, yhat, span):
    e = yhat - y
    rmse = float(np.sqrt(np.mean(e ** 2)))
    return dict(rmse=rmse, mae=float(np.abs(e).mean()), r2=float(1 - (e ** 2).sum() / ((y - y.mean()) ** 2).sum()),
                nrmse=rmse / span)


def evaluate(d, ids, models, test=False, out=RESULTS):
    """Every model x scheme x ablation x torque for the participants in ids -> the results rows, also written to out."""
    fit_on, score_on = (["train", "val"], "test") if test else (["train"], "val")
    span = d.groupby(["participant", "mode"])[sum(TARGETS.values(), [])].agg(lambda x: x.max() - x.min())
    stamp = dict(host=platform.node(), commit=subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                                              text=True, cwd=ROOT).stdout.strip())
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for name in models:
        rows = []
        for p in ids:
            own = d.participant == p
            score = d[own & (d.split == score_on)]
            cells = score.groupby(["mode", "controller"]).indices
            pred = []
            for scheme in SCHEMES:
                train = d[(own if scheme == "personalised" else ~own) & d.split.isin(fit_on)]
                assert len(train) and set(train.split) <= set(fit_on) and (p in set(train.participant)) == (scheme == "personalised")
                pred.append(score[ID].assign(scheme=scheme, ablation="full"))
                for ablation, dropped in ABLATIONS.items():
                    cols = [c for c in INPUTS if c not in dropped]
                    for torque, targets in TARGETS.items():
                        fit = train.dropna(subset=targets)   # a stuck gauge is NaN (preprocess.py)
                        model = MODELS[name](cols, len(fit)).fit(fit, fit[targets].to_numpy())
                        t0 = time.perf_counter()
                        yhat = model.predict(score)
                        ms = 1e3 * (time.perf_counter() - t0) / score.stride.nunique()
                        if ablation == "full":
                            pred[-1][[f"{c}_pred" for c in targets]] = yhat
                        for (mode, controller), i in cells.items():
                            for j, target in enumerate(targets):
                                y = score[target].to_numpy()[i]
                                ok = ~np.isnan(y)
                                if ok.any():
                                    rows.append(dict(model=name, scheme=scheme, ablation=ablation, torque=torque, participant=p,
                                                     mode=mode, controller=controller, joint=("hip", "knee")[j], split=score_on,
                                                     **metrics(y[ok], yhat[i, j][ok], span.at[(p, mode), target]), infer_ms=ms,
                                                     n_strides=int(ok.sum()) // 101, n_train_strides=len(fit) // 101, **stamp))
            if test:
                pd.concat(pred).to_csv(out / f"{name}_{p}_pred.csv", index=False, float_format="%.6g")
            print(f"{name} {p}: {len(score) // 101} {score_on} strides scored", flush=True)
        new, f = pd.DataFrame(rows), out / f"{name}.csv"
        if f.exists():
            new = pd.concat([pd.read_csv(f), new]).drop_duplicates(RESULT_KEY, keep="last")
        new.to_csv(f, index=False)
        done.append(pd.DataFrame(rows))
    return pd.concat(done)


def load():
    """Every participant on disk with its split: population models need them all, whoever is scored."""
    cols = ["participant", "stride", "leg", "mode", "controller", "group", "phase", "t"] + ALLOWED + sum(TARGETS.values(), [])
    d = read_strides(usecols=lambda c: c in cols)
    return d.merge(pd.read_csv(OUT / "splits.csv")[["participant", "stride", "split"]], on=["participant", "stride"], validate="m:1")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="participants to score, or 'all'. None: the self-check")
    ap.add_argument("--models", default="phase_mean,ridge")
    ap.add_argument("--test", action="store_true", help="refit on train + val and score the test blocks. Once.")
    a = ap.parse_args()
    d = load()
    everyone = sorted(d.participant.unique())
    if a.ids:
        r = evaluate(d, everyone if a.ids == ["all"] else a.ids, a.models.split(","), a.test)
    else:
        m = metrics(np.array([0.0, 2.0]), np.array([1.0, 3.0]), 4.0)
        assert m == dict(rmse=1.0, mae=1.0, r2=0.0, nrmse=0.25), m
        g = d[d.participant == everyone[0]]
        full, no_phase, no_accel = (features(g, [c for c in INPUTS if c not in ABLATIONS[k]]) for k in ("full", "no_phase", "no_accel"))
        assert full.shape[1] - no_phase.shape[1] == 9, "no_phase must drop phase, its 4 harmonics, stance_alpha and 3 gait states"
        assert full.shape[1] - no_accel.shape[1] == 5, "no_accel must drop the derivative of the 5 velocities"
        k = g.iloc[:101]   # one stride: the derivative of its velocity, integrated back, is the velocity
        acc = features(k, ["hip_qd", "accel"])[:, 1]
        back = k.hip_qd.iloc[0] + np.r_[0, np.cumsum((acc[1:] + acc[:-1]) / 2 * np.diff(k.t.to_numpy()))]
        assert np.abs(back - k.hip_qd.to_numpy()).max() < 0.25 * np.ptp(k.hip_qd.to_numpy()), "accel is not the velocity's time derivative"
        y = g[TARGETS["motor"]].to_numpy()
        resid = pd.DataFrame(y - PhaseMean(ALLOWED).fit(g, y).predict(g)).groupby([g[k].to_numpy() for k in PhaseMean(ALLOWED).keys]).mean()
        assert np.abs(resid.to_numpy()).max() < 1e-3, "the phase mean is not the mean of its training rows"
        r = evaluate(d, [i for i in ("AB68", "HL03") if i in everyone], ["phase_mean", "ridge"], out=RESULTS / "selfcheck")
        assert r[["rmse", "mae", "r2", "nrmse"]].notna().all().all() and (r.rmse > 0).all()
        assert not r.duplicated(RESULT_KEY).any() and set(r.scheme) == set(SCHEMES) and set(r.ablation) == set(ABLATIONS)
        w = r[(r["mode"] == "walk") & (r.ablation == "full") & (r.scheme == "personalised") & (r.torque == "gauge")]
        assert (w.r2 > 0.3).all(), "a baseline explains under 30% of the walking gauge torque (0.34-0.66 expected): check the alignment"
    w = r[r["mode"] == "walk"]
    print("walking, RMSE in Nm (mean over participants, controllers and joints):\n"
          + w.pivot_table(index=["model", "torque", "scheme"], columns="ablation", values="rmse")[list(ABLATIONS)].round(2).to_string())
    print(f"{'OK (self-check): ' if not a.ids else ''}{len(r)} rows, split = {r.split.iloc[0]}, {r.participant.nunique()} participants; "
          f"{len(everyone)} on disk")

"""J3/K2: raw ExoGait CSV -> strides on 101 phase points (RO1).

    python src/exogait/preprocess.py AB68 HL03      # or: all. About 5 s per participant

Reads data/raw/exogait/<ID>_ExoGait-Benchmark.csv by column name (AB72's column order differs) and
never edits it. Writes to data/processed/exogait/:
    <ID>_strides.csv          kept stride x phase point (101 per stride); columns = COLUMNS
    <ID>_stride_features.csv  kept stride: duration, ROM, peak and RMS torque. Descriptive, never model inputs
    <ID>_excluded.csv         dropped stride and the first rule it failed
    summary.csv               detected, kept and each reason per participant x mode x controller x leg,
                              rebuilt from every participant on disk
Units as in the raw file: s, rad, rad/s, Nm. t is the raw clock, float64 and written to the
microsecond (float32 cannot resolve 3 ms at 4,855 s); signals are written to 6 significant digits.

Rules
    block     one continuous pass of one condition. A new block starts at every label change (the
              UNDEFINED rows between two passes count) and at every step in time over GAP: a removed
              rest, or a restart of the clock. Numbered in file order. split.py splits on it.
    order     the file is in time order but its clock is not: in AB69, AB72, AB76, AB80 and AB82 it
              restarts once to three times and runs over the same seconds again. So strides are
              numbered by raw row, and row_start/row_end (0-based, the two heel strikes) are what
              places a stride in the session. t is only good inside a stride.
    stride    heel strike to heel strike of one leg; the closing heel strike is phase 100. A heel
              strike is where gait_cycle_<leg> wraps 99 -> 0: heel_strikes(), which x2model.py imports.
    detected  every stride with a row in a labelled condition. Strides wholly inside UNDEFINED rows
              (turns, transitions: 42-60% of a file) are not counted.
    dropped   for the first of REASONS that applies:
        condition_change     its rows carry more than one label (UNDEFINED and *_UNDEFINED2 included)
        gap                  it crosses a removed rest
        time_not_increasing  a dt <= 0 inside it
        incomplete           the dataset's own step_complete_<leg> is False in it. That is the first
                             stride of most passes, and the phase wraps while standing (0.1-0.5 of a
                             stride long, mostly with no heel strike of the other leg inside)
        duration_outlier     outside DURATION x the median of the participant's complete strides of
                             that condition and leg: a pause in mid-stride
        dropped_samples      a hole longer than HOLE, or more than MISSING of its samples missing.
                             Single dropped samples are everywhere (6.6% of AB68's intervals) and
                             harmless: one phase point is 18-100 ms. The worst hole in the data is 33 ms
    resample  each kept stride onto 101 instants equally spaced in time (np.interp on the float64
              clock, not on the integer gait_cycle). The other leg, the backpack and the SM parameters
              go onto the same instants. gait_state is categorical: nearest sample.
    stuck gauge  a gauge channel that moves less than STUCK Nm over a stride is a dead sensor (AB82's
              left knee, at -12.07 Nm). Its torque is written as NaN, so anything that uses it has to
              drop it, and the stride is flagged gauge_stuck. The stride stays: its other channels are fine.
Not carried: desired torque, the interaction forces, step_number, SM_Gui_Parameter and
SmoothedStanceInterpolationFactor (BANNED; reasons in docs/model_inputs.md).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "exogait"
OUT = ROOT / "data" / "processed" / "exogait"

GAP = 0.1                # s. A longer step in time is a removed rest (up to 352 s) or a clock restart (backwards)
HOLE = 0.05              # s. About one phase point of a slow stride
MISSING = 0.2            # share of a stride's samples
DURATION = (0.5, 1.5)    # x the median complete stride. 99% of complete strides are within 0.70-1.50
STUCK = 0.5              # Nm. A live gauge moves by tens of Nm in a stride
REASONS = ["condition_change", "gap", "time_not_increasing", "incomplete", "duration_outlier", "dropped_samples"]
MODES = {"WALKING": "walk", "RAMPS_UP": "ramp_up", "RAMPS_DOWN": "ramp_down",
         "STAIRS_UP": "stairs_up", "STAIRS_DOWN": "stairs_down"}
CONTROLLERS = {"transparent": "TR", "SM": "SM"}
LEGS = {"L": ("left", 1, 2), "R": ("right", 3, 4)}   # gait_cycle suffix, hip and knee joint numbers (ponsLab helpers.py)
SIGNALS = {"q": "JointPositions", "qd": "JointVelocities", "tau": "JointTorques", "tau_gauge": "JointTorquesViaGauges",
           "sm_k": "SM_Stiffness", "sm_d": "SM_Damping", "sm_q0": "SM_Equilibrium_Angle", "sm_qd0": "SM_Equilibrium_Velocity"}
OTHER = ("q", "qd", "tau_gauge")   # also carried for the other leg: its motion is an input, its gauge torque is K5's replay
BANNED = ("DesiredJointTorques", "InteractionForces", "SmoothedInteractionForces", "DesiredInteractionForces",
          "step_number", "SM_Gui_Parameter", "SmoothedStanceInterpolationFactor")
KEY = ["participant", "group", "stride", "leg", "mode", "controller", "block", "phase", "t"]
COLUMNS = KEY + ["hip_q", "knee_q", "hip_qd", "knee_qd", "hip_q_other", "knee_q_other", "hip_qd_other", "knee_qd_other",
                 "backpack_q", "backpack_qd", "gait_state", "stance_alpha",
                 *(f"{j}_sm_{p}" for j in ("hip", "knee") for p in ("k", "d", "q0", "qd0")),
                 "hip_tau", "knee_tau", "hip_tau_gauge", "knee_tau_gauge", "hip_tau_gauge_other", "knee_tau_gauge_other"]
GAUGES = [c for c in COLUMNS if "gauge" in c]
PHASE = np.arange(101)


def heel_strikes(gait_cycle):
    """Row indices where the integer phase wraps 99 -> 0. The one stride rule: K4's mean strides use it too."""
    return np.flatnonzero(np.diff(gait_cycle) < -50) + 1


def labels(condition):
    """'SM_RAMPS_UP' -> ('ramp_up', 'SM')."""
    controller, mode = condition.split("_", 1)
    return MODES[mode], CONTROLLERS[controller]


def source(leg):
    """Output column -> raw column, for a stride of this leg."""
    hip, knee = LEGS[leg][1:]
    hip_o, knee_o = LEGS["LR".replace(leg, "")][1:]
    src = {f"{j}_{k}": f"{raw}_{i}" for k, raw in SIGNALS.items() for j, i in (("hip", hip), ("knee", knee))}
    src |= {f"{j}_{k}_other": f"{SIGNALS[k]}_{i}" for k in OTHER for j, i in (("hip", hip_o), ("knee", knee_o))}
    return src | {"backpack_q": "BackPackAngle", "backpack_qd": "BackPackAngularVelocity",
                  "stance_alpha": "StanceInterpolationFactor"}


def load(subj):
    signals = [f"{raw}_{i}" for raw in SIGNALS.values() for i in range(1, 5)] + ["BackPackAngle", "BackPackAngularVelocity",
                                                                                 "StanceInterpolationFactor"]
    cols = ["time", "condition", "gait_cycle_left", "gait_cycle_right", "gait_state_left", "gait_state_right",
            "step_complete_l", "step_complete_r"] + signals
    assert not [c for c in cols if c.startswith(BANNED)]
    return pd.read_csv(RAW / f"{subj}_ExoGait-Benchmark.csv", usecols=cols, dtype=dict.fromkeys(signals, "float32"))


def process(subj):
    """One participant -> (strides, features, excluded), self-checked."""
    d = load(subj)
    t, cond = d.time.to_numpy(), d.condition.to_numpy()
    assert t.dtype == np.float64
    dt = np.diff(t)
    und = d.condition.str.contains("UNDEFINED").to_numpy()
    run = np.r_[0, np.cumsum((cond[1:] != cond[:-1]) | (np.abs(dt) > GAP))]
    block = np.cumsum(np.r_[True, run[1:] != run[:-1]] & ~und) - 1   # labelled passes in file order
    fs = 1 / np.median(dt)

    rows = []
    for leg, (side, *_) in LEGS.items():
        hs = heel_strikes(d[f"gait_cycle_{side}"].to_numpy())
        done = d[f"step_complete_{leg.lower()}"].to_numpy() == True
        for a, b in zip(hs[:-1], hs[1:]):
            if und[a:b + 1].all():
                continue
            step, T = dt[a:b], t[b] - t[a]
            missing = 1 - (b - a) / (T * fs) if T > 0 else 1.0
            rows.append(dict(leg=leg, row_start=a, row_end=b, condition=cond[a:b + 1][~und[a:b + 1]][0], block=block[a],
                             t_start=t[a], t_end=t[b], duration=T, max_dt=step.max(), missing=missing,
                             condition_change=(cond[a:b + 1] != cond[a]).any(), gap=step.max() > GAP,
                             time_not_increasing=step.min() <= 0, incomplete=not done[a:b].all(),
                             dropped_samples=step.max() > HOLE or missing > MISSING))
    s = pd.DataFrame(rows)
    complete = ~s[REASONS[:4]].any(axis=1)
    median = s.duration.where(complete).groupby([s.condition, s.leg]).transform("median")
    s["duration_outlier"] = ~(s.duration / median).between(*DURATION)
    s["reason"] = s[REASONS].idxmax(axis=1).where(s[REASONS].any(axis=1), "")   # the first rule that fails
    s["participant"], s["group"] = subj, subj[:2]
    s["mode"], s["controller"] = zip(*s.condition.map(labels))

    k = s[s.reason == ""].sort_values(["row_start", "leg"]).reset_index(drop=True)
    k["stride"] = k.index
    assert all(0 < dt[a:b].min() and dt[a:b].max() <= HOLE and block[a] == block[b] and not und[a:b + 1].any()
               for a, b in zip(k.row_start, k.row_end)), "a kept stride crosses a gap, a dt <= 0 or a label change"
    raw = {c: d[c].to_numpy() for c in d.columns}
    tn = np.linspace(k.t_start, k.t_end, 101, axis=1)
    out = {c: np.empty((len(k), 101)) for c in COLUMNS[len(KEY):]}
    stuck = np.zeros(len(k), bool)
    for i, (a, b, leg) in enumerate(zip(k.row_start, k.row_end, k.leg)):
        tt = t[a:b + 1]
        for c, rc in source(leg).items():
            out[c][i] = np.interp(tn[i], tt, raw[rc][a:b + 1])
            if c in GAUGES and np.ptp(raw[rc][a:b + 1]) < STUCK:
                out[c][i] = np.nan
                stuck[i] |= not c.endswith("other")
        nearest = a + np.rint(np.interp(tn[i], tt, np.arange(b - a + 1))).astype(int)
        out["gait_state"][i] = raw[f"gait_state_{LEGS[leg][0]}"][nearest]

    rep = lambda c: np.repeat(k[c].to_numpy(), 101)
    strides = pd.DataFrame({**{c: rep(c) for c in KEY[:7]}, "phase": np.tile(PHASE, len(k)), "t": tn.ravel(),
                            **{c: v.ravel() for c, v in out.items()}})
    feats = k[KEY[:7] + ["row_start", "row_end", "t_start", "t_end", "duration", "max_dt", "missing"]].assign(gauge_stuck=stuck)
    for j in ("hip", "knee"):
        feats[f"{j}_rom"] = np.ptp(out[f"{j}_q"], axis=1)
        for kind in ("tau", "tau_gauge"):
            feats[f"{j}_{kind}_peak"] = np.abs(out[f"{j}_{kind}"]).max(axis=1)
            feats[f"{j}_{kind}_rms"] = np.sqrt((out[f"{j}_{kind}"] ** 2).mean(axis=1))
    excluded = s.loc[s.reason != "", ["participant", "leg", "condition", "row_start", "row_end", "t_start", "t_end", "reason"]]

    assert list(strides.columns) == COLUMNS and strides.t.dtype == "float64"
    assert not [c for c in strides.columns if c.startswith(BANNED)]
    assert len(strides) == 101 * len(feats) and (strides.phase.to_numpy().reshape(-1, 101) == PHASE).all()
    assert (np.diff(tn, axis=1) > 0).all(), "time is not strictly increasing inside a stride"
    assert len(feats) + len(excluded) == len(s), "kept + excluded != detected"
    live = strides.drop(columns=GAUGES)
    assert live.notna().all().all(), f"NaN in {list(live.columns[live.isna().any()])}"
    return strides, feats, excluded


def write(df, path):
    df = df.copy()
    for c in df.columns.intersection(["t", "t_start", "t_end"]):   # the clock keeps its microseconds
        df[c] = df[c].map("{:.6f}".format)
    df.to_csv(path, index=False, float_format="%.6g")


def read_strides(ids=None, usecols=None):
    """The strides of the given participants (default: all on disk) as one frame, t in float64, signals in float32."""
    files = [OUT / f"{i}_strides.csv" for i in ids] if ids else sorted(OUT.glob("*_strides.csv"))
    dtype = {c: "float32" for c in COLUMNS[len(KEY):]}
    return pd.concat((pd.read_csv(f, usecols=usecols, dtype=dtype) for f in files), ignore_index=True)


def summary():
    """detected, kept and each exclusion reason per participant x mode x controller x leg, from the files on disk."""
    cell = ["participant", "mode", "controller", "leg"]
    kept = pd.concat(pd.read_csv(f, usecols=cell + ["gauge_stuck"]) for f in sorted(OUT.glob("*_stride_features.csv")))
    exc = pd.concat(pd.read_csv(f) for f in sorted(OUT.glob("*_excluded.csv")))
    exc["mode"], exc["controller"] = zip(*exc.condition.map(labels))
    out = pd.concat([kept.groupby(cell).size().rename("kept"), pd.crosstab([exc[c] for c in cell], exc.reason)], axis=1)
    out = out.reindex(columns=["kept"] + REASONS).fillna(0).astype(int)
    out.insert(0, "detected", out.sum(axis=1))
    out["gauge_stuck"] = kept.groupby(cell).gauge_stuck.sum().reindex(out.index, fill_value=0).astype(int)   # among the kept
    out.reset_index().to_csv(OUT / "summary.csv", index=False)
    return out


if __name__ == "__main__":
    ids = sys.argv[1:] or ["AB68"]
    if ids == ["all"]:
        ids = sorted(f.name[:4] for f in RAW.glob("*_ExoGait-Benchmark.csv"))
    OUT.mkdir(parents=True, exist_ok=True)
    for subj in ids:
        strides, feats, excluded = process(subj)
        for name, df in (("strides", strides), ("stride_features", feats), ("excluded", excluded)):
            write(df, OUT / f"{subj}_{name}.csv")
        back = read_strides([subj], usecols=["stride", "t", "hip_q"])
        assert back.t.dtype == "float64" and (back.groupby("stride").size() == 101).all()
        assert np.abs(back.t - strides.t).max() < 1e-6, "t lost precision on the way to disk"
        print(f"{subj}: {len(feats) + len(excluded)} strides detected, {len(feats)} kept "
              f"({feats.groupby('leg').size().to_dict()}), dropped {excluded.reason.value_counts().to_dict()}, "
              f"{int(feats.gauge_stuck.sum())} with a stuck gauge, {feats.block.nunique()} blocks, "
              f"{(OUT / f'{subj}_strides.csv').stat().st_size / 1e6:.1f} MB", flush=True)
    s = summary()
    print(f"OK: t float64; every kept stride has 101 rows inside one block, with no gap, no dt <= 0 and phase and time "
          f"increasing; kept + excluded = detected; no banned column. summary.csv: {len(s)} rows, "
          f"{s.kept.sum()} of {s.detected.sum()} strides kept")

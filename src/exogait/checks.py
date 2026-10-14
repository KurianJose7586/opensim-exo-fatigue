"""Raw ExoGait CSV checks behind the J2 numbers in notes/observations.md.

    python src/exogait/checks.py AB68 HL03      # ~1 min per participant

Reads data/raw/exogait/<ID>_ExoGait-Benchmark.csv by column name (AB72's column order
differs), never edits it. Prints header facts, timing, rows per condition, sign checks,
peak knee flexion per stride, and how the torque columns relate. Asserts the sign
conventions the OpenSim mapping (K4) relies on.
"""

import glob
import sys

import numpy as np
import pandas as pd

D = "data/raw/exogait"
JOINTS = {1: "L hip", 2: "L knee", 3: "R hip", 4: "R knee"}   # ponsLab helpers.py


def headers():
    heads = {f.replace("\\", "/").split("/")[-1][:4]: open(f).readline().strip().split(",")
             for f in sorted(glob.glob(f"{D}/*.csv"))}
    ref = set(heads["AB68"])
    print("same column set as AB68:", all(set(h) == ref for h in heads.values()),
          "| same order:", [k for k, h in heads.items() if h != heads["AB68"]] or "all")
    emg = [c for c in ref if any(w in c.lower() for w in ("emg", "rectus", "vastus", "biceps", "tibialis", "gastro"))]
    print("EMG-like columns:", emg)
    return emg


def check(subj):
    f = f"{D}/{subj}_ExoGait-Benchmark.csv"
    print(f"\n===== {subj} =====")
    torque = [f"{p}_{i}" for p in ("JointTorques", "DesiredJointTorques", "JointTorquesViaGauges") for i in JOINTS]
    d = pd.read_csv(f, usecols=["time", "condition", "BackPackAngle", "gait_cycle_left", "gait_cycle_right",
                                "step_number_l", "step_complete_l", "step_number_r", "step_complete_r"]
                    + [f"JointPositions_{i}" for i in JOINTS] + [f"InteractionForces_{i}" for i in range(1, 6)] + torque)

    dt = np.diff(d.time.to_numpy())
    print(f"rows {len(d)}, time {d.time.iloc[0]:.2f}..{d.time.iloc[-1]:.2f} s, median dt {np.median(dt) * 1e3:.3f} ms; "
          f"dt > 1.5/333 s: {(dt > 1.5 / 333).sum()}, > 0.1 s: {(dt > 0.1).sum()} (max {dt.max():.3f} s), dt <= 0: {(dt <= 0).sum()}")
    print("gait_cycle range:", d.gait_cycle_left.min(), "..", d.gait_cycle_left.max())
    print("rows per condition:\n" + d.condition.value_counts().to_string())

    w = d[d.condition == "transparent_WALKING"]
    hs_hip, knee_max = [], []
    for leg, hip, knee, ph in (("L", 1, 2, "gait_cycle_left"), ("R", 3, 4, "gait_cycle_right")):
        hip_hs = np.degrees(w.loc[w[ph] < 2, f"JointPositions_{hip}"].mean())
        k = np.degrees(w[f"JointPositions_{knee}"])
        print(f"TR walking {leg}: hip at heel strike {hip_hs:.1f} deg, knee {k.min():.1f}..{k.max():.1f} deg")
        hs_hip.append(hip_hs)
        knee_max.append(k.max())
    print(f"BackPackAngle, TR walking: mean {np.degrees(w.BackPackAngle.mean()):.1f} deg")

    rows = []
    for cond, g in d.groupby("condition"):
        if "UNDEFINED" in cond:
            continue
        for leg, knee, sn, sc in (("L", 2, "step_number_l", "step_complete_l"), ("R", 4, "step_number_r", "step_complete_r")):
            pk = -np.degrees(g[g[sc] == True].groupby(sn)[f"JointPositions_{knee}"].min())
            rows.append((cond, leg, len(pk), pk.median(), pk.max()))
    print("peak knee flexion per complete stride (deg):\n"
          + pd.DataFrame(rows, columns=["condition", "leg", "strides", "median", "max"]).round(1).to_string(index=False))

    for cond in ("SM_WALKING", "transparent_WALKING"):
        g = d[d.condition == cond]
        print(f"{cond}: RMS Nm, corr with JointTorques")
        for i, name in JOINTS.items():
            jt = g[f"JointTorques_{i}"]
            parts = [f"JT {np.sqrt((jt ** 2).mean()):.1f}"]
            for col in (f"DesiredJointTorques_{i}", f"JointTorquesViaGauges_{i}", f"InteractionForces_{i}", f"InteractionForces_{i + 1}"):
                x = g[col]
                parts.append(f"{col} {np.sqrt((x ** 2).mean()):.1f} ({np.corrcoef(jt, x)[0, 1]:.2f})")
            print(f"  {name}: " + ", ".join(parts))

    return hs_hip, knee_max


if __name__ == "__main__":
    assert not headers(), "EMG columns found -- update notes (J1 Q8)"
    for s in sys.argv[1:] or ["AB68"]:
        hs_hip, knee_max = check(s)
        # the K4 mapping assumes X2 signs equal OpenSim's: hip + flexion, knee - flexion
        assert min(hs_hip) > 5, f"{s}: hip not flexed at heel strike -- hip sign differs from OpenSim"
        assert max(knee_max) < 5, f"{s}: knee goes positive -- knee sign differs from OpenSim"
    print("\nOK: no EMG columns; hip + = flexion and knee - = flexion, as in OpenSim")

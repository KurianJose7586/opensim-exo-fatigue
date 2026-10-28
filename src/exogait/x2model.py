"""K4: the X2 twin model, and one participant's X2 hip/knee angles mapped onto it.

    python src/exogait/x2model.py [ID] [condition]     # default AB68 transparent_WALKING, ~10 s

Writes results/exogait/model/2D_gait_x2.osim and results/exogait/coords/<ID>_<condition>_mean.sto
(the products: Python-OpenSim, opensim-cmd and the GUI all read them) and
figures/k4_<id>_<cond>_mapping.png, then has OpenSim load both files and asserts the K4 checks.

No OpenSim Python bindings needed: the model is edited as .osim XML and checked with opensim-cmd
(on PATH, or the C:/OpenSim 4.6 install). Runs in any Python with numpy, pandas, scipy and
matplotlib, including the opensim env.

Model: models/base/2D_gait.osim (generic anthropometry: ExoGait records none) plus the Fourier X2.
    mass    20.7 kg welded to pelvis, femurs, tibias and calcanei: Kucuktabak et al. 2023 (IEEE T-RO)
            Table II, COMs from the CORC controller's x2_params.yaml. twin.DEVICE_MASS is generic
            (8.6 kg) and not used.
    torque  exo_{hip,knee}_{l,r}: CoordinateActuators as twin._add_exo builds them, optimal force
            EXO_F, controls +/-0.8 = +/-80 Nm (T-RO Sec. II-A). No ankle actuator: the X2 has none.
            +JointTorques is OpenSim's sign (checks.py asserts it), so control = JointTorques / EXO_F.
    left out  rotor inertia (1.87 kg m^2 per joint, T-RO Table II) and friction (Table III): JointTorques
            looks motor-side, so K6/K7 subtract 1.87*qddot and friction before comparing or replaying.
Ankle, pelvis_tx/ty and lumbar are not recorded; K5's tracking problem leaves them free.

Mapping, deg. Signs already match OpenSim (J2): hip + = flexion, knee - = flexion.
    knee_angle  = X2 knee                  relative angle between two X2 links: no frame change
    hip_flexion = X2 hip - c               the X2 hip is measured from the backpack, not the pelvis
    pelvis_tilt = BackPackAngle - 90 + c   so the thigh, pelvis_tilt + hip_flexion = BP - 90 + hip,
                                           is the same whatever c is
    c = mean reference pelvis_tilt - mean(BP - 90), the TR and SM walking means weighted equally
    (gyro-confirmed strides). ponytail: this borrows the reference subject's mean pelvis tilt (-15.1 deg), because the
    backpack's absolute level differs by site (AB +3.4, HL -9.6 deg). Replace c with a calibration
    posture or the IMU mounting angle if the authors give one.
Strides run right heel strike to right heel strike (gait_cycle_right wraps), are cleaned (strides()),
resampled on time and averaged. The mean's small end-start mismatch is removed by a ramp centred on
mid-stride, so a periodicity goal is consistent and the mean (hence c) is kept. Time axis = the mean
stride duration.
"""

import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "models" / "base" / "2D_gait.osim"
REF = ROOT / "models" / "base" / "referenceCoordinates.sto"
OUT = ROOT / "results" / "exogait"
CMD = shutil.which("opensim-cmd") or "C:/OpenSim 4.6/bin/opensim-cmd.exe"

# (body, parent, kg, COM in the parent frame [m], Izz [kg m^2]). Thigh and shank lump the X2's upper
# and lower links as CORC's X2Robot.cpp does. ponytail: the backpack COM (0.10 m behind, 0.25 m above
# the hip axis) is CORC's own "todo" estimate, placed with the backpack axis = pelvis y axis; the
# mapping says the backpack sits c off the pelvis, so the COM is 0.25 sin|c| m off horizontally (AB68
# 6 cm, ~6 Nm static). Rotate it by -c per participant if K6 needs it. The foot plate sits at the
# calcn COM; Fourier quotes 18 kg, and the Madrid unit may differ. Ask the authors (J1).
X2_PARTS = [("x2_backpack", "pelvis", 10.3, (-0.168, 0.186, 0), 0.201)] + [
    (f"x2_{link}_{s}", f"{seg}_{s}", kg, com, izz) for s in "lr" for link, seg, kg, com, izz in (
        ("thigh", "femur", 2.84, (0, -0.272, 0), 0.0419),
        ("shank", "tibia", 1.11, (0, -0.198, 0), 0.0205),
        ("foot", "calcn", 1.25, (0.0914, 0.0274, 0), 0.00444))]
X2_MASS = 20.7
X2_TORQUE = 80.0   # Nm per joint. The data peak at 85-89 Nm: replaying measured torque (K7) needs wider bounds
EXO_F = 100.0      # = twin.EXO_F (twin.py cannot be imported without the OpenSim bindings)
COORDS = ["pelvis_tilt", "pelvis_tx", "pelvis_ty", "hip_flexion_l", "hip_flexion_r", "knee_angle_l",
          "knee_angle_r", "ankle_angle_l", "ankle_angle_r", "lumbar"]

JOINTS = {"hip_flexion_l": "JointPositions_1", "knee_angle_l": "JointPositions_2",
          "hip_flexion_r": "JointPositions_3", "knee_angle_r": "JointPositions_4"}
WALKING = ("transparent_WALKING", "SM_WALKING")
P = np.linspace(0, 1, 101)   # 1% of the stride


def _add(parent, tag, name, **props):
    e = ET.SubElement(parent, tag, name=name)
    for k, v in props.items():
        ET.SubElement(e, k).text = " ".join(map(str, v)) if isinstance(v, tuple) else str(v)


def build_model(path=OUT / "model" / "2D_gait_x2.osim"):
    """2D_gait.osim + X2 mass + hip/knee exo actuators, written as .osim."""
    tree = ET.parse(BASE)
    m = tree.getroot().find("Model")
    for name, parent, kg, com, izz in X2_PARTS:
        # welded at the parent's origin, so the COM is in the parent frame.
        # ponytail: Izz on all three axes; only z matters in this planar model
        _add(m.find("BodySet/objects"), "Body", name, mass=kg, mass_center=com, inertia=(izz, izz, izz, 0, 0, 0))
        _add(m.find("JointSet/objects"), "WeldJoint", f"{name}_weld",
             socket_parent_frame=f"/bodyset/{parent}", socket_child_frame=f"/bodyset/{name}")
    for joint, coord in (("hip", "hip_flexion"), ("knee", "knee_angle")):
        for s in "lr":   # in the ForceSet, where twin._add_exo's model.addForce puts them
            _add(m.find("ForceSet/objects"), "CoordinateActuator", f"exo_{joint}_{s}", coordinate=f"{coord}_{s}",
                 optimal_force=EXO_F, min_control=-X2_TORQUE / EXO_F, max_control=X2_TORQUE / EXO_F)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="UTF-8", xml_declaration=True)
    return path


def read_sto(path):
    lines = Path(path).read_text().splitlines()
    head = next(i for i, line in enumerate(lines) if line.strip() == "endheader")
    return pd.read_csv(path, sep="\t", skiprows=head + 1).rename(columns=str.strip)


def reference():
    """The model's reference walking as a full cycle from right heel strike, deg on P, and each
    coordinate's .sto column path. The file is half a symmetric cycle: the second half is the first
    with the legs swapped, as example2DWalking builds it."""
    r = read_sto(REF)
    path = {c.split("/")[3]: c for c in r.columns if c.startswith("/")}
    t = r.time.to_numpy()
    x = np.r_[t, t[-1] + t[1:]] / (2 * t[-1])
    swap = lambda c: c[:-1] + {"l": "r", "r": "l"}[c[-1]] if c[-2] == "_" else c
    return {c: np.degrees(np.interp(P, x, np.r_[r[path[c]], r[path[swap(c)]].to_numpy()[1:]])) for c in path}, path


def strides(d, cond):
    """Clean right-heel-strike-to-right-heel-strike strides of one condition.

    Returns stride times (n,) [s], {coordinate or "bp": (n, 101) deg, resampled on time}, a mask of the
    strides whose BackPackAngle the gyro confirms, and how many strides each filter rejects (they
    overlap). Filters: K4 stride-extraction and hip-pelvis-frame work. The gyro filter only touches
    what is built from BackPackAngle: a backpack artefact says nothing about the joint encoders.
    """
    t, lab = d.time.to_numpy(), (d.condition == cond).to_numpy()
    q = {k: np.degrees(d[c].to_numpy()) for k, c in JOINTS.items()} | {"bp": np.degrees(d.BackPackAngle.to_numpy())}
    gyro = np.degrees(d.BackPackAngularVelocity.to_numpy())
    state, done = d.gait_state_right.to_numpy(), d.step_complete_r.to_numpy() == True
    hs = np.flatnonzero(np.diff(d.gait_cycle_right.to_numpy()) < -50) + 1   # integer phase wraps 99 -> 0
    hs_l = np.flatnonzero(np.diff(d.gait_cycle_left.to_numpy()) < -50) + 1
    sp = [slice(a, b + 1) for a, b in zip(hs[:-1], hs[1:])]                  # closing heel strike included
    bout = [lab[s].all() and np.diff(t[s]).max() <= 0.1 for s in sp]         # inside one labelled, gap-free bout

    def excess(s):   # BackPackAngle motion the backpack gyro does not see: an orientation-fusion artefact
        g = cumulative_trapezoid(gyro[s], t[s], initial=0)
        rng = lambda y: np.ptp(y - np.polyval(np.polyfit(t[s], y, 1), t[s]))
        drift = abs(q["bp"][s][-1] - q["bp"][s][0] - g[-1])   # a stride-long ramp: the detrended range misses it
        return max(rng(q["bp"][s]) - rng(g), drift)

    rows, segs = [], []
    for i, s in enumerate(sp):
        if not lab[s].any():
            continue
        tt = t[s]
        T = tt[-1] - tt[0]
        to = np.flatnonzero(np.isin(state[s], (2, 3)))   # right toe-off
        rows.append(dict(
            T=T,
            in_bout=bout[i],
            time_increasing=np.diff(tt).min() > 0,
            duration_0p6_6s=0.6 <= T <= 6,
            step_complete=done[s][:-1].all(),
            one_left_hs=((hs_l > s.start) & (hs_l < s.stop - 1)).sum() == 1,
            toe_off_40_85pct=len(to) > 0 and 0.4 <= (tt[to[0]] - tt[0]) / T <= 0.85,
            not_bout_edge=0 < i < len(sp) - 1 and bout[i - 1] and bout[i + 1],   # speeding up / slowing down
            bp_matches_gyro=excess(s) <= 5))
        segs.append(s)
    tab = pd.DataFrame(rows)
    basic = tab.in_bout & tab.time_increasing & tab.duration_0p6_6s
    tab["within_25pct_of_median_T"] = (tab["T"] / tab["T"][basic].median() - 1).abs() <= 0.25
    checks = tab.drop(columns="T")
    ok = checks.drop(columns="bp_matches_gyro").all(axis=1)
    keep = [s for s, k in zip(segs, ok) if k]
    curves = {k: np.array([np.interp(P, (t[s] - t[s][0]) / (t[s][-1] - t[s][0]), v[s]) for s in keep])
              for k, v in q.items()}
    return tab["T"][ok].to_numpy(), curves, tab.bp_matches_gyro[ok].to_numpy(), (~checks).sum()


def map_x2(subj="AB68", cond="transparent_WALKING"):
    """One participant x condition -> the mean stride as a MocoTrack states reference (.sto)."""
    d = pd.read_csv(ROOT / "data" / "raw" / "exogait" / f"{subj}_ExoGait-Benchmark.csv",
                    usecols=["time", "condition", "BackPackAngle", "BackPackAngularVelocity", "gait_cycle_left",
                             "gait_cycle_right", "gait_state_right", "step_complete_r", *JOINTS.values()])
    st = {c: strides(d, c) for c in {cond, *WALKING}}
    ref, path = reference()
    c = ref["pelvis_tilt"].mean() - np.mean([st[w][1]["bp"][st[w][2]].mean() - 90 for w in WALKING])
    T, cur, bp_ok, rejected = st[cond]
    assert len(T) and bp_ok.any(), f"{subj} {cond}: {len(T)} clean strides, {bp_ok.sum()} gyro-confirmed"
    x2 = {"pelvis_tilt": cur["bp"][bp_ok] - 90 + c,
          "hip_flexion_l": cur["hip_flexion_l"] - c, "hip_flexion_r": cur["hip_flexion_r"] - c,
          "knee_angle_l": cur["knee_angle_l"], "knee_angle_r": cur["knee_angle_r"]}
    mean = {k: v.mean(0) - (P - 0.5) * (v.mean(0)[-1] - v.mean(0)[0]) for k, v in x2.items()}
    df = pd.DataFrame({"time": P * T.mean(), **{path[k]: np.radians(v) for k, v in mean.items()}})
    sto = OUT / "coords" / f"{subj}_{cond}_mean.sto"
    sto.parent.mkdir(parents=True, exist_ok=True)
    with open(sto, "w", newline="\n") as f:
        f.write(f"version=1\nnRows={len(df)}\nnColumns={df.shape[1]}\ninDegrees=no\n"
                f"x2_hip_offset_deg={c:.3f}\nstrides={len(T)}\npelvis_tilt_strides={bp_ok.sum()}\nendheader\n")
        df.to_csv(f, sep="\t", index=False, float_format="%.8f")
    return dict(sto=sto, mean=mean, sd={k: v.std(0, ddof=1) for k, v in x2.items()}, ref=ref, T=T, c=c, bp_ok=bp_ok,
                rejected=rejected, end_start={k: v.mean(0)[-1] - v.mean(0)[0] for k, v in x2.items()},
                raw_mean={k: v.mean() for k, v in x2.items()})


def plot(r, subj, cond, png):
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.4), sharex=True)
    color = {"r": "#2a78d6", "l": "#eb6834"}
    for ax, (title, keys) in zip(axs, (("hip_flexion = X2 hip - c   (+ = flexion)", ("hip_flexion_r", "hip_flexion_l")),
                                       ("knee_angle = X2 knee   (- = flexion)", ("knee_angle_r", "knee_angle_l")),
                                       (f"pelvis_tilt = BackPackAngle - 90 + c   (n = {r['bp_ok'].sum()}, gyro-confirmed)",
                                        ("pelvis_tilt",)))):
        ax.axhline(0, color="#c3c2b7", lw=0.8)
        for k in keys:
            col, side = color.get(k[-1], "#52514e"), {"r": " R", "l": " L"}.get(k[-1], " pelvis")
            m, sd = r["mean"][k], r["sd"][k]
            ax.fill_between(P * 100, m - sd, m + sd, color=col, alpha=0.18, lw=0)
            ax.plot(P * 100, m, color=col, lw=2, label=f"X2{side} mean ± SD")
            ax.plot(P * 100, r["ref"][k], color=col, lw=1.5, ls="--", label=f"model reference{side}")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("% stride from right heel strike")
        ax.grid(alpha=0.25)
    axs[0].set_ylabel("deg")
    legend = {lab: h for ax in axs for h, lab in zip(*ax.get_legend_handles_labels())}
    fig.legend(legend.values(), legend.keys(), loc="lower center", ncol=6, frameon=False, fontsize=9)
    fig.suptitle(f"{subj} {cond} on 2D_gait: {len(r['T'])} clean strides, {r['T'].mean():.2f} ± {r['T'].std(ddof=1):.2f} s, "
                 f"c = {r['c']:.1f}°.  Dashed: the model's reference walk (0.94 s stride, 1.33 m/s)", fontsize=11)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=130)
    plt.close(fig)


def check(model, r):
    """K4 self-check: the model is what K4 asks for, OpenSim loads it and reads the target back, the mapping is sane."""
    xml, base = ET.parse(model).getroot(), ET.parse(BASE).getroot()
    mass = lambda x: sum(float(b.findtext("mass")) for b in x.iter("Body"))
    assert abs(mass(xml) - mass(base) - X2_MASS) < 1e-9, f"added mass {mass(xml) - mass(base)} kg"
    acts = {a.get("name"): (a.findtext("coordinate"), float(a.findtext("min_control")) * float(a.findtext("optimal_force")),
                            float(a.findtext("max_control")) * float(a.findtext("optimal_force")))
            for a in xml.iter("CoordinateActuator")}
    assert acts == {"lumbarAct": ("lumbar", -150.0, 150.0),
                    **{f"exo_{j}_{s}": (f"{c}_{s}", -X2_TORQUE, X2_TORQUE)
                       for j, c in (("hip", "hip_flexion"), ("knee", "knee_angle")) for s in "lr"}}, acts

    m = r["mean"]
    assert len(r["T"]) > 10, f"only {len(r['T'])} clean strides"
    assert (m["knee_angle_l"] <= 0).all() and (m["knee_angle_r"] <= 0).all(), "knee must stay flexed (- in OpenSim)"
    # independent of c, which moves both hips: the smallest gap over all 19 x TR/SM is 20 deg, the reference's 37
    assert m["hip_flexion_r"][0] - m["hip_flexion_l"][0] > 15, "at right heel strike the right hip is ahead of the left"
    assert np.argmin(m["knee_angle_r"]) > 55 > np.argmin(m["knee_angle_l"]), "each knee peaks in its own swing"
    assert ((-40 < m["pelvis_tilt"]) & (m["pelvis_tilt"] < 0)).all(), "pelvis_tilt outside -40..0 deg: c or the -90 is wrong"
    assert all(abs(v[-1] - v[0]) < 1e-9 for v in m.values()), "mean stride not periodic"
    assert all(abs(v.mean() - r["raw_mean"][k]) < 1e-9 for k, v in m.items()), "periodic fix moved the mean"

    # OpenSim loads the model, initSystem()s it and plays the target back through it
    t_end = read_sto(r["sto"]).time.iloc[-1]
    assert abs(t_end - r["T"].mean()) < 1e-6, f"time axis ends at {t_end} s, not the mean stride {r['T'].mean()} s"
    with tempfile.TemporaryDirectory() as tmp:
        setup = Path(tmp) / "k4.xml"
        setup.write_text(f"""<?xml version="1.0" encoding="UTF-8" ?>
<OpenSimDocument Version="40600"><AnalyzeTool name="k4">
<model_file>{model.as_posix()}</model_file><results_directory>{Path(tmp).as_posix()}</results_directory>
<coordinates_file>{r['sto'].as_posix()}</coordinates_file><initial_time>0</initial_time><final_time>{t_end}</final_time>
<AnalysisSet name="Analyses"><objects><Kinematics name="Kinematics" /></objects></AnalysisSet>
</AnalyzeTool></OpenSimDocument>""")
        run = subprocess.run([CMD, "run-tool", str(setup)], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
        q = read_sto(Path(tmp) / "k4_Kinematics_q.sto")   # deg
    assert list(q.columns[1:]) == COORDS, list(q.columns[1:])
    err = max(np.abs(np.interp(P * t_end, q.time, q[k]) - v).max() for k, v in m.items())
    assert err < 1e-3, f"target read back through OpenSim differs by {err} deg"
    return err


if __name__ == "__main__":
    subj = sys.argv[1] if len(sys.argv) > 1 else "AB68"
    cond = sys.argv[2] if len(sys.argv) > 2 else "transparent_WALKING"
    model = build_model()
    r = map_x2(subj, cond)
    png = ROOT / "figures" / f"k4_{subj}_{cond.replace('transparent', 'tr')}_mapping.png".lower()
    plot(r, subj, cond, png)
    print(f"model {model.relative_to(ROOT)}: +{X2_MASS} kg X2, exo hip/knee +/-{X2_TORQUE:.0f} Nm")
    print(f"{subj} {cond}: {len(r['T'])} clean strides, T {r['T'].mean():.2f} +- {r['T'].std(ddof=1):.2f} s; "
          f"c = {r['c']:.2f} deg; rejected by (overlapping): {r['rejected'][r['rejected'] > 0].to_dict()}")
    for k, v in r["mean"].items():
        print(f"  {k:<14} X2 {v.min():6.1f}..{v.max():5.1f} (at HS {v[0]:6.1f}, mean SD {r['sd'][k].mean():.1f}, "
              f"end-start removed {r['end_start'][k]:+.2f})   reference {r['ref'][k].min():6.1f}..{r['ref'][k].max():5.1f} "
              f"(at HS {r['ref'][k][0]:6.1f})")
    err = check(model, r)
    print(f"OK: model loads in OpenSim with {len(COORDS)} coordinates, +{X2_MASS} kg, 4 exo actuators at hip/knee only; "
          f"{r['sto'].relative_to(ROOT)} read back through OpenSim to {err:.1e} deg; knee <= 0, right hip ahead at HS, "
          f"each knee peaks in its own swing, pelvis_tilt in -40..0, periodic with the mean kept, time axis = mean stride. "
          f"Figure: {png.relative_to(ROOT)}")

"""A solved stride as a film: the twin walking, its muscles lit by activation, the exo torque at hip and knee.

    python src/exogait/animate.py [ID] [condition] [case,case,...]
    # default HL03 SM_WALKING none,measured,optimised. About 2 minutes

Reads results/exogait/moco/<ID>_<condition>_mean_<case>_m50.sto (track.py, assist.py) and writes
figures/k7_<id>_<condition>_stride.mp4 (three strides), .gif (one, looping) and .png (one frame).
One panel per case, in real time, seen from the right in a treadmill view: the pelvis stays put and
the floor marks move.
    muscles   the 18 muscle paths, coloured by activation (light to dark blue)
    exo       grey struts and backpack. The orange wedge at a hip or knee motor is its torque: WEDGE
              degrees per Nm, opening the way the torque turns the limb
    below     the right hip and knee exo torque over the stride, with a cursor at the frame
    effort    the sum of squared activations integrated over the stride, as track.py computes it
The left leg is drawn fainter. Everything shown is the solution itself: nothing is smoothed or staged.
"""

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import opensim as osim
from matplotlib import animation
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Circle, Polygon, Wedge

import track

WEDGE = 1.5   # degrees of wedge per Nm: the X2's 80 Nm limit is a third of a turn
TITLE = {"none": "Exoskeleton off", "measured": "Measured assistance, replayed", "optimised": "Optimised assistance, same torque budget",
         "ideal": "Unlimited assistance (upper bound)", "ai": "Predicted assistance, replayed"}
INK, INK2, MUTED, GRID, AXIS, SURFACE, EXO = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb", "#eb6834"
ACTIVATION = LinearSegmentedColormap.from_list("activation", ["#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"])
FOOT = [(-0.012, 0.01), (-0.005, -0.027), (0.205, -0.031), (0.205, -0.014), (0.10, 0.03), (0.064, 0.045), (0.014, 0.045)]   # calcn frame, m
SPHERES = [(0.031, 0.01, 0.035), (0.177, -0.016, 0.015)]   # the heel and forefoot contact spheres: x, y, radius in the calcn frame
BACKPACK = [(-0.25, 0.0), (-0.115, 0.0), (-0.115, 0.42), (-0.25, 0.42)]                                              # pelvis frame, m


def kinematics(path):
    """What the frames need from one solution: points in the sagittal plane [m], activations, exo torque [Nm], effort."""
    model = osim.ModelProcessor(str(track.MODEL)).process()
    model.initSystem()
    sol = osim.MocoTrajectory(str(path))
    states = sol.exportToStatesTrajectory(model)
    muscles = [m for m in (osim.Muscle.safeDownCast(model.updComponent(c.getAbsolutePathString()))
                           for c in model.getComponentsList()) if m]
    t = np.array(sol.getTimeMat())
    k = dict(t=t, muscles=[m.getName() for m in muscles], points=[], paths=[],
             act=np.array([sol.getStateMat(f"/{m.getName()}/activation") for m in muscles]),
             tau={a: track.x2model.EXO_F * np.array(sol.getControlMat(f"/forceset/{a}")) for a in track.EXO})
    k["effort"] = float(np.trapezoid(np.square(k["act"]).sum(0), t))
    for i in range(states.getSize()):
        s = states.get(i)
        model.realizePosition(s)
        at = lambda body, x=0.0, y=0.0: np.array([model.getBodySet().get(body).findStationLocationInGround(s, osim.Vec3(x, y, 0)).get(j)
                                                  for j in (0, 1)])
        p = dict(pelvis=at("pelvis"), lumbar=at("torso"), neck=at("torso", 0, 0.5), head=at("torso", 0.01, 0.63),
                 backpack=np.array([at("pelvis", *c) for c in BACKPACK]))
        for side in "lr":
            p |= {f"hip_{side}": at(f"femur_{side}"), f"knee_{side}": at(f"tibia_{side}"), f"ankle_{side}": at(f"talus_{side}"),
                  f"foot_{side}": np.array([at(f"calcn_{side}", *c) for c in FOOT]),
                  f"sole_{side}": min(at(f"calcn_{side}", x, y)[1] - r for x, y, r in SPHERES)}
        k["points"].append(p)
        k["paths"].append([np.array([[pp.get(j).getLocationInGround(s).get(q) for q in (0, 1)] for j in range(pp.getSize())])
                           for pp in (m.getGeometryPath().getCurrentPath(s) for m in muscles)])
    return k


def draw(ax, k, i, vmax):
    """One frame of one case on ax."""
    ax.clear()
    ax.set(xlim=(-0.8, 0.8), ylim=(-0.12, 1.8), aspect="equal")
    ax.axis("off")
    p, x0 = k["points"][i], k["points"][i]["pelvis"][0]
    shift = lambda a: np.asarray(a) - (x0, 0)
    ax.plot([-0.8, 0.8], [0, 0], color=AXIS, lw=1.2, zorder=1)
    for m in (np.arange(-2, 12) * 0.25 - x0 + 0.8) % 1.6 - 0.8:   # floor marks 25 cm apart, moving back as the model walks
        ax.plot([m, m], [-0.035, 0], color=AXIS, lw=1.2, zorder=1)
    ax.add_patch(Polygon(shift(p["backpack"]), closed=True, fc="#dad9d2", ec=MUTED, lw=0.8, zorder=2))
    ax.plot(*shift([p["pelvis"], p["lumbar"], p["neck"]]).T, color=INK2, lw=5, solid_capstyle="round", zorder=4)
    ax.add_patch(Circle(shift(p["head"]), 0.095, fc=SURFACE, ec=INK2, lw=2.2, zorder=4))
    for side, alpha, z in (("l", 0.42, 3), ("r", 1.0, 6)):   # the far leg first, fainter
        hip, knee, ankle = (shift(p[f"{j}_{side}"]) for j in ("hip", "knee", "ankle"))
        ax.plot(*np.array([hip, knee, ankle]).T, color="#c9c8c0", lw=10, alpha=alpha, solid_capstyle="round", zorder=z)   # X2 struts
        ax.plot(*np.array([hip, knee, ankle]).T, color=INK2, lw=2.6, alpha=alpha, solid_capstyle="round", zorder=z + 0.2)
        ax.add_patch(Polygon(shift(p[f"foot_{side}"]), closed=True, fc="#c9c8c0", ec=INK2, lw=1.4, alpha=alpha, zorder=z))
        n = k["muscles"]
        mine = [j for j in range(len(n)) if n[j].endswith(f"_{side}")]
        ax.add_collection(LineCollection([shift(k["paths"][i][j]) for j in mine], colors=ACTIVATION(k["act"][mine, i] / vmax),
                                         lw=3.4, alpha=alpha, capstyle="round", zorder=z + 0.4))
        for joint, centre, to in (("hip", hip, knee), ("knee", knee, ankle)):
            tau = k["tau"][f"exo_{joint}_{side}"][i]
            limb = np.degrees(np.arctan2(*(to - centre)[::-1]))
            ax.add_patch(Wedge(centre, 0.15, *sorted((limb, limb + WEDGE * tau)), fc=EXO, ec="none", alpha=0.85 * alpha, zorder=z + 0.6))
            ax.add_patch(Circle(centre, 0.034, fc="#f0efec", ec=INK2, lw=1.2, alpha=alpha, zorder=z + 0.8))   # the motor


def film(subj="HL03", cond="SM_WALKING", cases=("none", "measured", "optimised"), n_mesh=50):
    ks = {c: kinematics(track.MOCO / f"{subj}_{cond}_mean_{c}_m{n_mesh}.sto") for c in cases}
    t = ks[cases[0]]["t"]
    n, T = len(t) - 1, t[-1] - t[0]   # periodic: the last node is the first again
    vmax = np.ceil(10 * max(k["act"].max() for k in ks.values())) / 10
    peak = 1.1 * max(np.abs(k["tau"][a]).max() for k in ks.values() for a in ("exo_hip_r", "exo_knee_r"))
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans"], "font.size": 10})
    fig = plt.figure(figsize=(12.8, 7.2), facecolor=SURFACE)
    gs = fig.add_gridspec(3, len(cases), height_ratios=[5.2, 1, 1], left=0.055, right=0.985, top=0.875, bottom=0.135, hspace=0.42, wspace=0.14)
    body, cursors = [], []
    base = ks["none"]["effort"] if "none" in ks else None
    for c, case in enumerate(cases):
        k = ks[case]
        body.append(fig.add_subplot(gs[0, c]))
        change = "" if base is None or case == "none" else f"   {100 * (k['effort'] / base - 1):+.0f}% against exoskeleton off"
        fig.text(body[-1].get_position().x0, 0.95, TITLE[case], color=INK, fontsize=12.5, fontweight="bold")
        fig.text(body[-1].get_position().x0, 0.915, f"Muscle effort {k['effort']:.2f}{change}", color=INK2, fontsize=10.5)
        for r, joint in enumerate(("hip", "knee")):
            ax = fig.add_subplot(gs[1 + r, c])
            ax.set_facecolor(SURFACE)
            ax.axhline(0, color=AXIS, lw=1)
            ax.plot(100 * (t - t[0]) / T, k["tau"][f"exo_{joint}_r"], color=EXO, lw=2)
            cursors.append(ax.axvline(0, color=INK2, lw=1))
            ax.set(xlim=(0, 100), ylim=(-peak, peak), xticks=[0, 25, 50, 75, 100])
            ax.grid(axis="y", color=GRID, lw=0.6)
            ax.tick_params(colors=MUTED, labelsize=8.5, length=0, labelbottom=bool(r), labelleft=not c)
            for side in ax.spines.values():
                side.set_visible(False)
            ax.set_title(f"Right {joint} exo torque" + (" (Nm)" if not c else ""), loc="left", color=INK2, fontsize=9, pad=3)
            if r:
                ax.set_xlabel("% of the stride, from right heel strike", color=MUTED, fontsize=9)
    bar = fig.colorbar(ScalarMappable(Normalize(0, vmax), ACTIVATION), cax=fig.add_axes([0.825, 0.045, 0.16, 0.014]), orientation="horizontal")
    bar.set_ticks([0, vmax])
    bar.ax.tick_params(colors=MUTED, labelsize=8.5, length=0)
    bar.outline.set_visible(False)
    fig.text(0.82, 0.052, "Muscle activation", color=INK2, fontsize=9, ha="right", va="center")
    controller, mode = cond.split("_", 1)
    label = f"{'state-machine' if controller == 'SM' else 'transparent'} {mode.lower().replace('_', ' ')}"
    fig.text(0.055, 0.058, f"{subj}, {label}: the mean stride ({T:.1f} s), solved in OpenSim Moco on a generic 2D body wearing the Fourier X2 (20.7 kg).",
             color=INK2, fontsize=9, va="center")
    fig.text(0.055, 0.03, "Orange wedge and orange line: the exoskeleton's torque at the joint. Simulation, in real time.",
             color=INK2, fontsize=9, va="center")

    def frame(i):
        for ax, case in zip(body, cases):
            draw(ax, ks[case], i, vmax)
        for line in cursors:
            line.set_xdata([100 * i / n] * 2)

    out = track.x2model.ROOT / "figures" / f"k7_{subj}_{cond.replace('transparent', 'tr')}_stride".lower()
    frame(round(0.12 * n))
    fig.savefig(f"{out}.png", dpi=110)
    animation.FuncAnimation(fig, frame, frames=np.tile(np.arange(n), 3)).save(   # three strides: a player may not loop
        f"{out}.mp4", writer=animation.FFMpegWriter(fps=n / T, bitrate=2400), dpi=110)
    animation.FuncAnimation(fig, frame, frames=n).save(f"{out}.gif", writer=animation.PillowWriter(fps=round(n / T)), dpi=70)   # loops by itself
    plt.close(fig)
    return out, ks


if __name__ == "__main__":
    a = sys.argv[1:]
    out, ks = film(*a[:2], *([tuple(a[2].split(","))] if len(a) > 2 else []))
    for case, k in ks.items():
        x = np.array([p["pelvis"][0] for p in k["points"]])
        assert x[-1] - x[0] > 0.3 and np.diff(x).min() > -0.001, f"{case}: the pelvis moves backwards (it may pause: HL03 walks at 0.29 m/s)"
        assert all(0 <= k["act"].min() and k["act"].max() <= 1 for k in ks.values())
        sink = -min(p[f"sole_{s}"] for p in k["points"] for s in "lr")
        assert sink < 0.04, f"{case}: a contact sphere is {100 * sink:.1f} cm into the floor (2.6 cm is the contact model's give)"
    print("OK:", {c: round(k["effort"], 3) for c, k in ks.items()}, "->", f"{out.relative_to(track.x2model.ROOT)}.mp4 / .gif / .png")

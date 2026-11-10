"""K5: MocoTrack reproduces one participant's mean X2 stride on the X2 model.

    micromamba run -n opensim python -u src/exogait/track.py [ID] [condition] [mesh intervals] [guess .sto | seed | cold] [case]
    # default HL03 SM_WALKING 50 seed measured; 5-10 minutes per solve with 4 threads (OPENSIM_MOCO_PARALLEL=4)

The model (x2model.py: 2D_gait + 20.7 kg of X2) tracks the mean stride's hip, knee and pelvis-tilt
angles with its own muscles and foot-ground contact, while the four exo actuators replay the measured
joint-output torque. This is K7's `measured` case. Pelvis translation, ankle, lumbar and the muscle
states are not recorded: the solve estimates them (K6).

The problem is OpenSim's example2DWalking tracking problem with these changes (notes "K5", decisions 2026-11-10):
    stride    one full mean stride (1.9-5.6 s), periodic in everything but pelvis_tx. No L/R symmetry.
    tracked   hip and knee at weight TRACK_W, pelvis_tilt at 0.2 of that (a backpack signal), and the stock
              walk's ankle at 0.001 of it (a weak prior: free, the ankle flutters in swing), with their rates.
              All low-passed at 6 Hz.
    exo       held to the mean JointTorquesViaGauges by a path constraint, so the replay is exact.
              ponytail: the gauges carry a constant offset of a few Nm (notes "K6"), left in.
    effort    weight 1 on squared controls. Reserves at every coordinate, 1 Nm = 1 excitation, so they
              are used only where muscles cannot.
    speed     not imposed (and MocoAverageSpeedGoal ignores direction). The pelvis only has to move
              forward, by 0.5 to 1.3 times stride_length(): the speed is the model's own, a check on it.
    bounds    the model's joint ranges where the example's stop short of the data.
    start     a stored converged stride (SEED). From the tracked states alone IPOPT usually wanders.

Writes results/exogait/moco/<ID>_<condition>_mean_<case>_m<mesh>.sto and a figure in results/exogait/plots/,
appends a row to results/exogait/moco/summary.csv with the verdict of the K5 plausibility checks, and
asserts that verdict.
"""

import csv
import ctypes
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import opensim as osim

import preprocess
import x2model

MOCO = x2model.OUT / "moco"
MODEL = x2model.OUT / "model" / "2D_gait_x2.osim"   # as x2model.py last wrote it: read here, never rewritten (parallel solves)
# A converged stride of this model (HL03 SM, these settings) that every solve starts from. From the tracked
# states alone IPOPT wandered in 4 of 5 tries (notes "K5"); from this it converges in a few hundred iterations.
SEED = x2model.ROOT / "models" / "exogait" / "seed_stride.sto"
TRACK_W = 10.0      # hip and knee tracking against effort at 1: at 1 the knee ran 4 deg straight through stance
PELVIS_W = 0.2      # pelvis_tilt next to hip and knee: a backpack signal
ANKLE_W = 0.001     # stock reference ankle next to hip and knee (0.01 against effort): free, it flutters in swing
STRIDE = (0.5, 1.3) # pelvis advance over the stride, as fractions of stride_length(): forward; the length is the model's
EXO_WEIGHT = 1e-3   # = twin.EXO_WEIGHT: the exo's weight in the effort goal when Moco chooses its torque (`ideal`)
TOL = 1e-3          # IPOPT convergence; MocoTrack's own default is 1e-2
DEG = np.pi / 180
VALUE = {"pelvis_tilt": "/jointset/groundPelvis/pelvis_tilt", "pelvis_tx": "/jointset/groundPelvis/pelvis_tx",
         "pelvis_ty": "/jointset/groundPelvis/pelvis_ty", "lumbar": "/jointset/lumbar/lumbar",
         **{f"{c}_{s}": f"/jointset/{j}_{s}/{c}_{s}" for j, c in (("hip", "hip_flexion"), ("knee", "knee_angle"),
                                                                    ("ankle", "ankle_angle")) for s in "lr"}}
EXO = {f"exo_{j}_{s}": f"{c}_{s}" for j, c in (("hip", "hip_flexion"), ("knee", "knee_angle")) for s in "lr"}
BOUNDS = {"hip_flexion": (-25, 95), "knee_angle": (-120, 10), "ankle_angle": (-30, 30)}   # deg
SCALE = 1.0          # segment lengths against the generic model's: 1 unless scaled() has run
GENERIC = (1.80, 62.0)   # the generic 2D_gait: its mass, and the height its segments suggest (hip axis at 0.935 m standing)


def scaled(subj):
    """K6: switch this process to the twin scaled to one participant (Lhoste et al. 2026, Table 2): segment lengths by
    height / GENERIC height, body mass set to the participant's (mass distribution kept), muscle fibre and tendon
    lengths with their paths (OpenSim's Model.scale), maximum isometric forces by the mass ratio (muscle volume
    goes with mass x height, fibre length with height). The X2 is added afterwards, unscaled: 20.7 kg for everyone.
    Solves then go to results/exogait/moco_scaled/, beside the generic ones.
    ponytail: one uniform factor from stature. Segment-wise factors need leg lengths, which nobody measured."""
    global MODEL, MOCO, SCALE
    with open(x2model.ROOT / "models" / "exogait" / "participants.csv") as f:
        person = next(r for r in csv.DictReader(f) if r["participant"] == subj)
    SCALE, mass = float(person["height_m"]) / GENERIC[0], float(person["mass_kg"])
    MOCO = x2model.OUT / "moco_scaled"
    MODEL = x2model.OUT / "model" / f"2D_gait_x2_{subj}.osim"
    if not MODEL.exists():
        model = osim.Model(str(x2model.BASE))
        state = model.initSystem()
        factors = osim.ScaleSet()
        for i in range(model.getBodySet().getSize()):
            s = osim.Scale()
            s.setSegmentName(model.getBodySet().get(i).getName())
            s.setScaleFactors(osim.Vec3(SCALE))
            s.setApply(True)
            factors.cloneAndAppend(s)
        model.scale(state, factors, True, mass)
        for c in model.getComponentsList():
            m = osim.Muscle.safeDownCast(model.updComponent(c.getAbsolutePathString()))
            if m:
                m.setMaxIsometricForce(m.getMaxIsometricForce() * mass / GENERIC[1])
        base = MODEL.with_name(f"2D_gait_{subj}.osim")
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        model.printToXML(str(base))
        x2model.build_model(MODEL, base)
        check = osim.Model(str(MODEL))
        got = check.getTotalMass(check.initSystem())
        assert abs(got - mass - x2model.X2_MASS) < 0.01, f"scaled model weighs {got} kg, not {mass} + {x2model.X2_MASS}"
    return SCALE, mass


def stride_length(m):
    """Stride length [m] the mean hip, knee and pelvis angles imply: the range of the right-minus-left
    ankle distance (step R + step L, feet planted at each heel strike). Segment vectors from
    2D_gait.osim: knee in the femur frame (-0.0045, -0.3969), ankle in the tibia frame (0, -0.4157)."""
    def ankle_x(s):
        thigh = (m["pelvis_tilt"] + m[f"hip_flexion_{s}"]) * DEG
        return -0.0045 * np.cos(thigh) + 0.3969 * np.sin(thigh) + 0.4157 * np.sin(thigh + m[f"knee_angle_{s}"] * DEG)
    return SCALE * float(np.ptp(ankle_x("r") - ankle_x("l")))


def lowpass(y, T, hz=6.0):
    """A periodic stride curve (101 points, last = first) without its harmonics above hz, as the kinematics get."""
    z = np.fft.irfft(np.fft.rfft(y[:-1]) * (np.arange(51) <= hz * T), 100)
    return np.r_[z, z[0]]


def peak_mem_gb():
    if os.name != "nt":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20

    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong), ("peak", ctypes.c_size_t)] + \
                   [(f"x{i}", ctypes.c_size_t) for i in range(7)]
    pmc, k32 = PMC(), ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
    k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), ctypes.sizeof(pmc))
    return pmc.peak / 2 ** 30


def ground_forces(model, sol):
    """The vertical ground reaction on each foot along a solution: time [s] and {side: force [N]}, from the contact spheres."""
    names = [osim.StdVectorString(), osim.StdVectorString()]
    for v, s in zip(names, "rl"):
        v.append(f"contactHeel_{s}")
        v.append(f"contactFront_{s}")
    grf = osim.createExternalLoadsTableForGait(model, sol, *names)
    return np.array(grf.getIndependentColumn()), {s: grf.getDependentColumn(f"ground_force_{s}_vy").to_numpy() for s in "rl"}


def solve(subj="HL03", cond="SM_WALKING", n_mesh=50, guess=SEED, case="measured", exo_w=None, max_iter=3000, prescribed=None):
    """One solve. Returns the summary row (dict); the solution is written to MOCO.
    guess: a solved .sto of the same model (any stride) to start from, stretched onto this stride.
           None starts from the tracked states: how the seed was first made, but it usually wanders.
    case (K7): measured   the exo replays the measured joint-output torque (K5)
               none       the exo is held at zero: the X2 worn, unpowered and frictionless
               ideal      Moco chooses the exo torque within the X2 limits at almost no cost (Dembia's ideal
                          device). It beats `measured` by construction: only an upper bound on what torque can do
               optimised  Moco chooses the exo torque, each actuator's squared torque priced at exo_w[actuator]
                          in the effort goal. assist.py sets those prices so that each actuator spends the
                          measured torque's budget (the integral of its square): the optimum under that budget.
                          Moco 4.6 cannot constrain the integral itself (MocoControlGoal has no constraint mode,
                          and MocoOutputGoal on |actuation hits a stale-cache error).
               ai         the exo replays `prescribed`, {actuator: Nm on x2model.P}: K3's predicted torque
                          (assist.ai_torque). Replayed exactly, like `measured`, and not held to the budget."""
    name = f"{subj}_{cond}_mean_{case}_m{n_mesh}"
    cwd, work = os.getcwd(), MOCO / "work" / name
    work.mkdir(parents=True, exist_ok=True)
    guess = guess and str(Path(guess).resolve())
    os.chdir(work)   # MocoTrack and the solver write <name>_tracked_states.sto and a stop file into the cwd
    try:
        return _solve(subj, cond, n_mesh, guess, case, exo_w, max_iter, name, prescribed)
    finally:
        os.chdir(cwd)


def _solve(subj, cond, n_mesh, guess, case, exo_w, max_iter, name, prescribed=None):
    MODEL.exists() or x2model.build_model(MODEL)
    r = x2model.map_x2(subj, cond)
    mean, P = r["mean"], x2model.P
    T = float(r["T"].mean())
    L = stride_length(mean)

    track = osim.MocoTrack()
    track.setName(name)
    proc = osim.ModelProcessor(str(MODEL))
    proc.append(osim.ModOpAddReserves(1.0, 1000.0, False))   # at every coordinate (decisions.md 2026-10-02)
    track.setModel(proc)
    # The reference, built here on an exact time base and low-passed at 6 Hz as periodic curves: the same
    # filter the replayed torque gets, and the curves stay periodic (TabOpLowPassFilter pads and resamples).
    ref = dict(mean)
    for s in "lr" if ANKLE_W else "":   # not recorded: the stock walk's ankle on the stride, a weak prior (J1 Q7 default)
        ref[f"ankle_angle_{s}"] = r["ref"][f"ankle_angle_{s}"]
    table = osim.TimeSeriesTable([float(x) for x in P * T])
    for c, v in ref.items():
        table.appendColumn(f"{VALUE[c]}/value", osim.Vector.createFromMat(lowpass(v, T) * DEG))
    table.addTableMetaDataString("inDegrees", "no")
    track.setStatesReference(osim.TableProcessor(table))
    track.set_states_global_tracking_weight(TRACK_W)
    w = osim.MocoWeightSet()
    for kind in ("value", "speed"):
        w.cloneAndAppend(osim.MocoWeight(f"{VALUE['pelvis_tilt']}/{kind}", PELVIS_W))
        for s in "lr" if ANKLE_W else "":
            w.cloneAndAppend(osim.MocoWeight(f"{VALUE[f'ankle_angle_{s}']}/{kind}", ANKLE_W))
    track.set_states_weight_set(w)
    track.set_allow_unused_references(True)
    track.set_track_reference_position_derivatives(True)
    # Only for a cold start. MocoTrack resamples the tracked states onto the guess grid, and for some stride
    # durations its own last time lands one ulp short of the final time, which resample() rejects.
    track.set_apply_tracked_states_to_guess(guess is None)
    track.set_initial_time(0.0)
    track.set_final_time(T)
    track.set_mesh_interval(T / n_mesh)
    study = track.initialize()
    problem = study.updProblem()
    model = proc.process()
    model.initSystem()

    effort = osim.MocoControlGoal.safeDownCast(problem.updGoal("control_effort"))
    effort.setWeight(1.0)
    for a in EXO:   # prescribed torques cost nothing; chosen ones cost EXO_WEIGHT (`ideal`) or their price (`optimised`)
        effort.setWeightForControl(f"/forceset/{a}", {"ideal": EXO_WEIGHT, "optimised": (exo_w or {}).get(a, EXO_WEIGHT)}.get(case, 0.0))

    # the measured joint-output torque: replayed exactly (`measured`), or only its budget kept (`optimised`)
    measured = {a: lowpass(r["tau"][f"gauge_{c}"], T) for a, c in EXO.items()}
    assert max(np.abs(v).max() for v in measured.values()) < x2model.X2_TORQUE, "mean measured torque beyond the X2 limit"
    stuck = [a for a, v in measured.items() if np.ptp(v) < 1.0]   # AB82's left-knee gauge reads -12.07 Nm throughout SM
    assert not stuck or case == "none", f"{subj} {cond}: the gauge torque at {stuck} is constant: a stuck channel, nothing to replay"
    budget = {a: float(np.trapezoid(v ** 2, P * T)) for a, v in measured.items()}   # Nm^2 s
    tau = {"measured": measured, "none": {a: 0 * v for a, v in measured.items()}, "ideal": {}, "optimised": {},
           "ai": {a: lowpass(v, T) for a, v in (prescribed or {}).items()}}[case]
    assert case != "ai" or (set(tau) == set(EXO) and max(np.abs(v).max() for v in tau.values()) < x2model.X2_TORQUE), \
        "`ai` needs a torque for each of the four actuators, within the X2 limit"
    for a, v in tau.items():
        f = osim.PiecewiseLinearFunction()
        for ti, ui in zip(P * T, v / x2model.EXO_F):
            f.addPoint(float(ti), float(ui))
        con = osim.MocoControlBoundConstraint()
        con.setName(f"replay_{a}")
        con.addControlPath(f"/forceset/{a}")
        con.setLowerBound(f)
        con.setEqualityWithLower(True)
        problem.addPathConstraint(con)

    # a full periodic stride: every state returns to its start, except pelvis_tx
    periodic = osim.MocoPeriodicityGoal("periodic")
    for i in range(model.getNumStateVariables()):
        s = model.getStateVariableNames().getitem(i)
        if not s.endswith("pelvis_tx/value"):
            periodic.addStatePair(osim.MocoPeriodicityGoalPair(s))
    periodic.addControlPair(osim.MocoPeriodicityGoalPair("/lumbarAct"))
    for a in EXO if case in ("ideal", "optimised") else ():   # prescribed torques are periodic already
        periodic.addControlPair(osim.MocoPeriodicityGoalPair(f"/forceset/{a}"))
    problem.addGoal(periodic)

    lo, hi = mean["pelvis_tilt"].min() - 10, mean["pelvis_tilt"].max() + 10
    problem.setStateInfo(f"{VALUE['pelvis_tilt']}/value", [lo * DEG, hi * DEG])
    problem.setStateInfo(f"{VALUE['pelvis_tx']}/value", [-0.2, 1.5 * L], 0, [STRIDE[0] * L, STRIDE[1] * L])
    problem.setStateInfo(f"{VALUE['pelvis_ty']}/value", [0.75 * SCALE, 1.25 * SCALE])
    problem.setStateInfo(f"{VALUE['lumbar']}/value", [0, 20 * DEG])
    for c, (a, b) in BOUNDS.items():
        for s in "lr":
            problem.setStateInfo(f"{VALUE[f'{c}_{s}']}/value", [a * DEG, b * DEG])

    solver = osim.MocoCasADiSolver.safeDownCast(study.updSolver())
    solver.set_optim_convergence_tolerance(TOL)
    solver.set_optim_constraint_tolerance(1e-4)
    solver.set_optim_max_iterations(max_iter)
    if guess:   # a solved stride, stretched onto this one
        g = osim.MocoTrajectory(str(guess))
        k = T / g.getTimeMat()[-1]
        tg = np.array(g.getTimeMat()) * k
        tg[-1] = T   # exactly: the same resample() check
        g.setTime(tg)
        for s in g.getStateNames():
            if s.endswith("/speed"):
                g.setState(s, np.array(g.getStateMat(s)) / k)
            if "pelvis_t" in s and "tilt" not in s and SCALE != 1 and Path(guess).resolve() == SEED.resolve():
                g.setState(s, np.array(g.getStateMat(s)) * SCALE)   # the generic seed's pelvis path, on a scaled body
        g.write("guess.sto")
        solver.setGuessFile("guess.sto")   # as a file: read at solve time, once the problem is final
    else:
        g = solver.getGuess()   # MocoTrack put the tracked states in; edited in place
        tg = g.getTimeMat()
        g.setState(f"{VALUE['pelvis_tx']}/value", L * tg / T)
        g.setState(f"{VALUE['pelvis_tx']}/speed", np.full(len(tg), L / T))
        g.setState(f"{VALUE['pelvis_ty']}/value", np.full(len(tg), 0.90 * SCALE))   # straight-leg standing height is 0.935 m
        assert abs(np.array(solver.getGuess().getStateMat(f"{VALUE['pelvis_ty']}/value"))[0] - 0.90 * SCALE) < 1e-12, "guess not applied"

    tic = time.perf_counter()
    sol = study.solve()
    solve_s = time.perf_counter() - tic
    ok = bool(sol.success())
    if not ok:
        sol.unseal()   # keep the failed trajectory: non-convergence is data
    sol.write(str(MOCO / f"{name}.sto"))

    t = np.array(sol.getTimeMat())
    val = lambda c: np.array(sol.getStateMat(f"{VALUE[c]}/value")) / DEG
    ctl = lambda n: np.array(sol.getControlMat(n))
    rms = lambda x: float(np.sqrt(np.trapezoid(np.square(x), t) / T))
    row = dict(participant=subj, condition=cond, case=case, target="mean", n_mesh=n_mesh, T=round(T, 4),
               strides=len(r["T"]), success=ok, status=sol.getStatus(), iterations=sol.getNumIterations(),
               solve_s=round(solve_s, 1), peak_mem_gb=round(peak_mem_gb(), 2), objective=round(sol.getObjective(), 5))
    row |= dict(track_w=TRACK_W, pelvis_w=PELVIS_W, ankle_w=ANKLE_W, tol=TOL, warm_start=bool(guess))
    for c in mean:   # tracking error [deg]; the reference is the unfiltered mean stride
        row[f"rmse_{c}"] = round(rms(val(c) - np.interp(t, P * T, mean[c])), 3)
    for a in EXO:   # the exo torque as solved [Nm]: against its prescription, its size, its budget use, its rate
        u = ctl(f"/forceset/{a}") * x2model.EXO_F
        row[f"replay_rmse_{a}"] = round(rms(u - np.interp(t, P * T, tau[a])), 4) if a in tau else ""
        row[f"exo_rms_{a}"] = round(rms(u), 2)
        row[f"exo_int2_{a}"] = round(float(np.trapezoid(u ** 2, t)), 2)
        row[f"exo_budget_{a}"] = round(budget[a], 2)
        row[f"exo_rate_rms_{a}"] = round(rms(np.gradient(u, t)), 2)   # smoothness, Nm/s
    for n in sol.getControlNames():   # Nm (N for pelvis_tx and pelvis_ty): optimal force 1
        if "reserve" in n:
            row["reserve_rms_" + next(c for c in VALUE if n.endswith(c))] = round(rms(ctl(n)), 3)
    acts = np.array([np.array(sol.getStateMat(s)) for s in sol.getStateNames() if s.endswith("/activation")])
    row["effort"] = round(float(np.trapezoid(np.square(acts).sum(0), t)), 4)        # sum of squared activations x time
    row["mean_activation"] = round(float(np.trapezoid(acts.mean(0), t) / T), 4)
    row["stride_len_fk"] = round(L, 3)
    row["stride_len"] = round(float(np.array(sol.getStateMat(f"{VALUE['pelvis_tx']}/value"))[-1]), 3)
    row["speed"] = round(row["stride_len"] / T, 3)
    for c in ("ankle_angle_l", "ankle_angle_r", "lumbar"):
        row[f"min_{c}"], row[f"max_{c}"] = round(val(c).min(), 1), round(val(c).max(), 1)
    row["min_pelvis_ty"] = round(float(np.array(sol.getStateMat(f"{VALUE['pelvis_ty']}/value")).min()), 3)
    bw = model.getTotalMass(model.getWorkingState()) * 9.80665
    for s, f in ground_forces(model, sol)[1].items():
        row[f"peak_grf_bw_{s}"] = round(f.max() / bw, 3)
    try:
        check(row | {"_range": {c: (val(c).min(), val(c).max()) for c in VALUE if c not in ("pelvis_tx", "pelvis_ty")},
                     "_pelvis_bounds": (lo, hi)})
        row["check"] = "ok"
    except AssertionError as e:
        row["check"] = str(e)
    row["host"] = platform.node()
    row["commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                   cwd=x2model.ROOT).stdout.strip()

    out = MOCO / "summary.csv"
    new = not out.exists()
    with open(out, "a", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(row))
        if new:
            wr.writeheader()
        wr.writerow(row)
    return row


def check(row):
    """K5 plausibility: converged, tracked, inside the joint ranges, forward, exo as measured, reserves small."""
    assert row["success"], f"did not converge: {row['status']}"
    for c in ("hip_flexion_l", "hip_flexion_r", "knee_angle_l", "knee_angle_r"):
        assert row[f"rmse_{c}"] < 3, f"{c} tracked to {row[f'rmse_{c}']} deg"
    assert row["rmse_pelvis_tilt"] < 6, f"pelvis_tilt tracked to {row['rmse_pelvis_tilt']} deg"
    limits = {**{f"{c}_{s}": b for c, b in BOUNDS.items() for s in "lr"}, "pelvis_tilt": row["_pelvis_bounds"], "lumbar": (0, 20)}
    for c, (a, b) in row["_range"].items():
        lo, hi = limits[c]
        tracked = c.startswith(("hip", "knee", "pelvis"))
        assert lo - 1e-6 <= a and b <= hi + 1e-6, f"{c} outside its bounds: {a:.1f}..{b:.1f}"
        assert not tracked or (a > lo + 0.5 and b < hi - 0.5), f"tracked {c} sits on a bound: {a:.1f}..{b:.1f} in {lo}..{hi}"
    assert max(row["_range"]["knee_angle_l"][1], row["_range"]["knee_angle_r"][1]) < 5, "knee extends past 5 deg"
    assert 0.55 * row["stride_len_fk"] < row["stride_len"] < 1.25 * row["stride_len_fk"], "stride length on its bound"
    assert all(v < 1 for k, v in row.items() if k.startswith("replay_rmse") and v != ""), "exo torque is not the prescribed torque"
    for a in EXO:   # the mesh's quadrature and the 101-point budget differ by a hair
        assert row[f"exo_int2_{a}"] <= 1.02 * row[f"exo_budget_{a}"] + 0.5 or row["case"] in ("measured", "ideal", "ai"), f"{a} over its budget"
    joint = [v for k, v in row.items() if k.startswith("reserve_rms") and "pelvis" not in k]
    assert max(joint) < 5, f"joint reserves up to {max(joint)} Nm RMS"
    assert max(row["peak_grf_bw_r"], row["peak_grf_bw_l"]) < 2.5 and row["min_pelvis_ty"] > 0.8 * SCALE, "not walking on its feet"


def plot(subj, cond, n_mesh=50, case="measured"):
    """K5 figure: the solved stride against the measured mean, and what the solve had to estimate."""
    import matplotlib.pyplot as plt
    name = f"{subj}_{cond}_mean_{case}_m{n_mesh}"
    sol = osim.MocoTrajectory(str(MOCO / f"{name}.sto"))
    r, P = x2model.map_x2(subj, cond), 100 * x2model.P
    t = np.array(sol.getTimeMat())
    x = 100 * t / t[-1]
    val = lambda c: np.array(sol.getStateMat(f"{VALUE[c]}/value")) / DEG
    color = {"r": "#2a78d6", "l": "#eb6834", "t": "#52514e"}
    fig, axs = plt.subplots(2, 3, figsize=(15, 7.6), sharex=True)
    for ax, coords, title in ((axs[0, 0], ("hip_flexion_r", "hip_flexion_l"), "hip_flexion (tracked)"),
                              (axs[0, 1], ("knee_angle_r", "knee_angle_l"), "knee_angle (tracked)"),
                              (axs[0, 2], ("pelvis_tilt",), f"pelvis_tilt (tracked at weight {PELVIS_W})")):
        for c in coords:
            m, sd, col = r["mean"][c], r["sd"][c], color[c[-1]]
            ax.fill_between(P, m - sd, m + sd, color=col, alpha=0.18, lw=0)
            ax.plot(P, m, color=col, lw=1.3, ls="--", label=f"X2 measured mean ± SD ({c[-1].upper() if c[-2] == '_' else 'pelvis'})")
            ax.plot(x, val(c), color=col, lw=2.2, label=f"model ({c[-1].upper() if c[-2] == '_' else 'pelvis'})")
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("deg")
    for s in "rl":
        axs[1, 0].plot(x, val(f"ankle_angle_{s}"), color=color[s], lw=2.2, label=f"model ({s.upper()})")
    axs[1, 0].set_title("ankle_angle (not recorded: estimated by the solve)", fontsize=10)
    axs[1, 0].set_ylabel("deg")
    model = osim.ModelProcessor(str(MODEL)).process()
    model.initSystem()
    bw = model.getTotalMass(model.getWorkingState()) * 9.80665
    tg, force = ground_forces(model, sol)
    for s in "rl":
        axs[1, 1].plot(100 * tg / t[-1], force[s] / bw, color=color[s], lw=2.2, label=f"model ({s.upper()})")
    axs[1, 1].set_title("vertical ground reaction (not recorded: estimated)", fontsize=10)
    axs[1, 1].set_ylabel("body weights (model + X2)")
    for a, c in EXO.items():
        axs[1, 2].plot(x, np.array(sol.getControlMat(f"/forceset/{a}")) * x2model.EXO_F, color=color[c[-1]], lw=2.2,
                       ls="-" if "hip" in a else ":", label=f"{'hip' if 'hip' in a else 'knee'} {c[-1].upper()}")
    axs[1, 2].set_title({"measured": "X2 torque at the joint (measured, replayed exactly)", "none": "X2 torque (held at zero)",
                         "ideal": "X2 torque (chosen freely by Moco: upper bound)",
                         "optimised": "X2 torque (chosen by Moco within the measured budget)"}[case], fontsize=10)
    axs[1, 2].set_ylabel("Nm")
    for ax in axs.flat:
        ax.axhline(0, color="#c3c2b7", lw=0.8)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8, frameon=False)
    for ax in axs[1]:
        ax.set_xlabel("% stride from right heel strike")
    fig.suptitle(f"{subj} {cond}, exo {case}: MocoTrack on the X2 model, mean of {len(r['T'])} strides ({t[-1]:.2f} s), "
                 f"{n_mesh} mesh intervals", fontsize=11)
    fig.tight_layout()
    png = x2model.OUT / "plots" / f"k5_{name}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=130)
    plt.close(fig)
    return png


def net_moments(name):
    """K6: hip and knee moments [Nm] along a solved stride, summed from the solution itself: the muscles'
    (tendon force x moment arm), plus the exo's and the reserves'. Returns time, {coordinate: net moment}
    and {coordinate: muscle moment}. Exact for that solution: an ID re-solve on its splined kinematics
    (the twin.net_moments pattern) left 3-4% of body weight in pelvis residuals."""
    proc = osim.ModelProcessor(str(MODEL))
    proc.append(osim.ModOpAddReserves(1.0, 1000.0, False))
    model = proc.process()
    model.initSystem()
    sol = osim.MocoTrajectory(str(MOCO / f"{name}.sto"))
    states = sol.exportToStatesTrajectory(model)
    paths = [c.getAbsolutePathString() for c in model.getComponentsList()]
    muscles = [m for m in (osim.Muscle.safeDownCast(model.updComponent(q)) for q in paths) if m]
    assert len(muscles) == 18, f"{len(muscles)} muscles found"
    muscle = {c: np.zeros(states.getSize()) for c in EXO.values()}
    for i in range(states.getSize()):
        state = states.get(i)
        model.realizeDynamics(state)
        for c in muscle:
            coord = model.updCoordinateSet().get(c)
            muscle[c][i] = sum(m.computeMomentArm(state, coord) * m.getTendonForce(state) for m in muscles)
    reserve = lambda c: np.array(sol.getControlMat(next(n for n in sol.getControlNames() if "reserve" in n and n.endswith(c))))
    net = {c: muscle[c] + x2model.EXO_F * np.array(sol.getControlMat(f"/forceset/{a}")) + reserve(c) for a, c in EXO.items()}
    return np.array(sol.getTimeMat()), net, muscle


def moment_vs_torque(subj, n_mesh=50):
    """K6: net hip and knee moments against the measured X2 torque, in SM and TR walking, from the two
    K5 solves. Writes results/exogait/plots/k6_<id>_moment_vs_torque.png and rows in moco/moment_vs_torque.csv."""
    import matplotlib.pyplot as plt
    P, rows = x2model.P, []
    fig, axs = plt.subplots(2, 4, figsize=(15, 6.4), sharex=True)
    for axrow, cond in zip(axs, ("SM_WALKING", "transparent_WALKING")):
        r = x2model.map_x2(subj, cond)
        if min(np.ptp(r["tau"][f"gauge_{c}"]) for c in EXO.values()) < 1.0:   # a stuck gauge: no valid `measured` solve
            axrow[0].set_title(f"{cond.split('_')[0]}: a gauge channel is stuck, no measured torque", fontsize=10)
            continue
        t, M, muscle = net_moments(f"{subj}_{cond}_mean_measured_m{n_mesh}")
        T = t[-1]
        rms = lambda x: float(np.sqrt(np.trapezoid(x * x, t) / T))
        for ax, c in zip(axrow, ("hip_flexion_r", "knee_angle_r", "hip_flexion_l", "knee_angle_l")):
            gauge, motor = (np.interp(t, P * T, r["tau"][f"{k}_{c}"]) for k in ("gauge", "motor"))
            row = dict(participant=subj, condition=cond, joint=c, net_rms=rms(M[c]), muscle_rms=rms(muscle[c]),
                       gauge_rms=rms(gauge), motor_rms=rms(motor),
                       # least-squares share of the net moment the exo delivers: 1 = all of it, 0 = none, < 0 = opposes it
                       gauge_share=float(np.trapezoid(gauge * M[c], t) / np.trapezoid(M[c] ** 2, t)),
                       gauge_r=float(np.corrcoef(gauge, M[c])[0, 1]), motor_r=float(np.corrcoef(motor, M[c])[0, 1]))
            rows.append({k: round(v, 3) if isinstance(v, float) else v for k, v in row.items()})
            ax.axhline(0, color="#c3c2b7", lw=0.8)
            ax.plot(100 * t / T, M[c], color="#1a1a19", lw=2, label="net joint moment (model: muscles + X2)")
            ax.plot(100 * t / T, muscle[c], color="#1f9d6b", lw=1.6, label="the model's muscles")
            ax.plot(100 * t / T, gauge, color="#2a78d6", lw=2, label="X2 torque at the joint (gauges)")
            ax.plot(100 * t / T, motor, color="#9b9a94", lw=1.3, ls="--", label="X2 motor torque (JointTorques)")
            ax.set_title(f"{cond.split('_')[0]} {c}: exo share {row['gauge_share']:+.2f}, r {row['gauge_r']:+.2f}", fontsize=10)
            ax.grid(alpha=0.25)
    for ax in axs[1]:
        ax.set_xlabel("% stride from right heel strike")
    for ax in axs[:, 0]:
        ax.set_ylabel("Nm  (+ = along the OpenSim coordinate)")
    fig.legend(*axs[1, 0].get_legend_handles_labels(), loc="lower center", ncol=4, frameon=False, fontsize=9)
    fig.suptitle(f"{subj} mean walking stride: what the joints need vs what the X2 delivered", fontsize=11)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    png = x2model.OUT / "plots" / f"k6_{subj.lower()}_moment_vs_torque.png"
    fig.savefig(png, dpi=130)
    plt.close(fig)
    out = MOCO / "moment_vs_torque.csv"
    new = not out.exists()
    with open(out, "a", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        if new:
            wr.writeheader()
        wr.writerows(rows)
    return rows, png


def load_split(subj, cond, n_mesh=50, case="measured"):
    """K6, a held-out check: the right foot's share of the vertical ground force through the stride. The model's
    comes from the solution's contact forces. The measured one is StanceInterpolationFactor, which the X2 computes
    from the force sensors in its footplates (Lhoste et al. 2026); in the data it is 1 in right single support
    and 0 in left. The tracking never sees it. Returns the measured mean and SD over the kept right strides
    (preprocess.py) and the model's share, all on x2model.P."""
    d = preprocess.read_strides([subj], usecols=["leg", "mode", "controller", "stance_alpha"])
    a = d[(d.leg == "R") & (d["mode"] == "walk") & (d.controller == preprocess.CONTROLLERS[cond.split("_")[0]])]
    a = a.stance_alpha.to_numpy().reshape(-1, 101)
    proc = osim.ModelProcessor(str(MODEL))
    proc.append(osim.ModOpAddReserves(1.0, 1000.0, False))
    model = proc.process()
    model.initSystem()
    t, f = ground_forces(model, osim.MocoTrajectory(str(MOCO / f"{subj}_{cond}_mean_{case}_m{n_mesh}.sto")))
    return a.mean(0), a.std(0, ddof=1), np.interp(x2model.P, t / t[-1], f["r"] / np.maximum(f["r"] + f["l"], 1e-9))


def load_splits(n_mesh=50):
    """K6: load_split() for every `measured` walking solve that passes K5's checks -> moco/load_split.csv and
    figures/k6_load_split.png."""
    import matplotlib.pyplot as plt
    rows, curves = [], {c: [] for c in x2model.WALKING}
    with open(MOCO / "summary.csv") as f:   # the last row per solve says whether it passed K5's checks
        verdict = {(r["participant"], r["condition"]): r["check"] for r in csv.DictReader(f)
                   if r["case"] == "measured" and int(r["n_mesh"]) == n_mesh}
    for (subj, cond), check in sorted(verdict.items()):
        if check != "ok" or cond not in x2model.WALKING:
            continue
        m, sd, share = load_split(subj, cond, n_mesh)
        rows.append(dict(participant=subj, condition=cond, r=round(float(np.corrcoef(m, share)[0, 1]), 3),
                         rmse=round(float(np.sqrt(np.mean((m - share) ** 2))), 3), stride_sd=round(float(sd.mean()), 3),
                         measured_at_heel_strike=round(float(m[0]), 2), model_at_heel_strike=round(float(share[0]), 2)))
        curves[cond].append((m, share))
    with open(MOCO / "load_split.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, cond in zip(axs, ("SM_WALKING", "transparent_WALKING")):
        m, share = (np.array(v) for v in zip(*curves[cond]))
        x = 100 * x2model.P
        for y, col, lab in ((m, "#52514e", "measured by the footplates (StanceInterpolationFactor)"), (share, "#2a78d6", "model: contact forces of the solved stride")):
            ax.fill_between(x, y.mean(0) - y.std(0), y.mean(0) + y.std(0), color=col, alpha=0.16, lw=0)
            ax.plot(x, y.mean(0), color=col, lw=2.2, label=lab + ", mean ± SD over participants")
        r = np.median([q["r"] for q in rows if q["condition"] == cond])
        ax.set_title(f"{'State machine' if cond.startswith('SM') else 'Transparent'}: {len(m)} participants, median r = {r:.2f}", fontsize=10, loc="left")
        ax.set_xlabel("% of the stride, from right heel strike")
        ax.grid(alpha=0.25)
    axs[0].set_ylabel("right foot's share of the vertical ground force")
    fig.legend(*axs[0].get_legend_handles_labels(), loc="lower center", ncol=2, frameon=False, fontsize=9)
    fig.suptitle("A held-out check of the twin: the load split between the feet. The tracking never sees the footplate signal", fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.94), w_pad=1.5)
    png = x2model.ROOT / "figures" / "k6_load_split.png"
    fig.savefig(png, dpi=130)
    plt.close(fig)
    return rows, png


def params():
    """K6: results/exogait/params.csv, one row per participant: what the twin uses for them."""
    rows = []
    with open(x2model.ROOT / "models" / "exogait" / "participants.csv") as f:   # Lhoste et al. 2026 (JNER 23:114), Table 2
        people = {r["participant"]: r for r in csv.DictReader(f)}
    for f in sorted((x2model.ROOT / "data" / "raw" / "exogait").glob("*_ExoGait-Benchmark.csv")):
        subj = f.name[:4]
        row = dict(participant=subj, site=subj[:2], **{k: people[subj][k] for k in ("sex", "age_y", "height_m", "mass_kg")},
                   model_mass_kg=62.0, x2_mass_kg=x2model.X2_MASS,
                   anthropometry="measured: Lhoste 2026 Table 2. The model is still the generic 2D_gait, not scaled")
        for cond in x2model.WALKING:
            r, k = x2model.map_x2(subj, cond), cond.split("_")[0][:2].upper()
            L = stride_length(r["mean"])
            row |= {"hip_offset_c_deg": round(float(r["c"]), 2), f"strides_{k}": len(r["T"]), f"pelvis_strides_{k}": int(r["bp_ok"].sum()),
                    f"stride_s_{k}": round(float(r["T"].mean()), 3), f"stride_len_fk_m_{k}": round(L, 3),
                    f"speed_fk_ms_{k}": round(L / float(r["T"].mean()), 3)}
        rows.append(row)
    out = x2model.OUT / "params.csv"
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    return out, rows


if __name__ == "__main__":
    if sys.argv[1:2] == ["params"]:
        out, rows = params()
        assert len(rows) == 19 and all(-30 < r["hip_offset_c_deg"] < 5 for r in rows), "params: 19 participants, c in range"
        print(f"OK: {out}: {len(rows)} participants, c {min(r['hip_offset_c_deg'] for r in rows)}..{max(r['hip_offset_c_deg'] for r in rows)} deg")
        sys.exit()
    if sys.argv[1:2] == ["load"]:   # track.py load: every `measured` walking solve on disk
        rows, png = load_splits()
        r = np.array([q["r"] for q in rows])
        assert len(rows) >= 30 and np.median(r) > 0.7, f"the model's load split does not follow the footplates: median r {np.median(r):.2f}"
        print(f"OK: {len(rows)} solves; r median {np.median(r):.2f}, range {r.min():.2f}..{r.max():.2f}; RMSE median "
              f"{np.median([q['rmse'] for q in rows]):.2f} of the share (stride-to-stride SD {np.median([q['stride_sd'] for q in rows]):.2f}); "
              f"at heel strike: measured {np.median([q['measured_at_heel_strike'] for q in rows]):.2f}, model "
              f"{np.median([q['model_at_heel_strike'] for q in rows]):.2f} (medians). Figure: {png}")
        sys.exit()
    if sys.argv[1:2] == ["k6"]:   # track.py k6 [ID]: needs that participant's SM and TR solves
        rows, png = moment_vs_torque(sys.argv[2] if len(sys.argv) > 2 else "HL03")
        print("\n".join(str(r) for r in rows))
        assert len(rows) in (4, 8) and all(0 < r["net_rms"] < 80 and r["muscle_rms"] > 0 for r in rows), "implausible joint moments"
        print(f"OK: hip and knee moments for SM and TR walking, summed from the K5 solutions. Figure: {png}")
        sys.exit()
    subj = sys.argv[1] if len(sys.argv) > 1 else "HL03"
    cond = sys.argv[2] if len(sys.argv) > 2 else "SM_WALKING"
    if os.environ.get("EXOGAIT_SCALED"):   # the twin scaled to this participant, into moco_scaled/
        print("scaled twin: length factor %.3f, body mass %.0f kg" % scaled(subj), flush=True)
    for n_mesh in map(int, (sys.argv[3] if len(sys.argv) > 3 else "50").split(",")):
        guess = SEED if len(sys.argv) < 5 or sys.argv[4] == "seed" else None if sys.argv[4] == "cold" else sys.argv[4]
        row = solve(subj, cond, n_mesh, guess, sys.argv[5] if len(sys.argv) > 5 else "measured")
        print("\n".join(f"  {k:<28} {v}" for k, v in row.items()), flush=True)
        print("figure:", plot(subj, cond, n_mesh, row["case"]), flush=True)
        assert row["check"] == "ok", row["check"]
        worst = max(row[f"rmse_{c}"] for c in ("hip_flexion_l", "hip_flexion_r", "knee_angle_l", "knee_angle_r"))
        print(f"OK: {subj} {cond} {row['case']} mesh {n_mesh}: converged in {row['iterations']} iterations, {row['solve_s']} s; "
              f"hip/knee tracked to {worst} deg, exo torque as prescribed or within budget, joint reserves small, "
              f"walks forward {row['stride_len']} m per stride; effort {row['effort']}", flush=True)

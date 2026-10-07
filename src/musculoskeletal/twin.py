"""Phase A: the musculoskeletal twin. One call = one MocoInverse solve.

    activations(subject, condition, p) -> (100, 9) right-leg muscle activations
                                          over one full gait cycle

Model: the reduced 2D gait model (gait10dof18musc, 9 muscles per leg) and its
reference walking kinematics, both from OpenSim's example2DWalking. The
reference is HALF a cycle; the gait is symmetric, so the right leg's second
half is the left leg's first half. That is how the example itself is built.

Exoskeleton: an ideal assistive device at hip, knee and ankle on both legs
(Dembia et al. 2017) -- torque actuators the optimiser uses freely, capped at
p_j * peak net moment of joint j. p_j is the device's capacity at that joint,
the quantity Phase C allocates under a shared budget. Device mass is added to
the segments; leaving it out is the standard way to report a benefit that does
not exist.

Subject variation (D1 samples these):
    mass_scale      every segment mass. Contact stiffness is scaled with it so
                    ground reaction scales with body weight -- the contact law
                    is linear in stiffness, so this is exact for uniform mass.
    strength_scale  max isometric force of every muscle
    load_kg         carried load on the torso (backpack). GRF is scaled by the
                    total-mass ratio; the non-uniform part lands in residuals,
                    which are returned so it can be checked.
    speed_scale     time-scaling of the reference kinematics. ponytail: real
                    gait changes shape with speed, not just tempo. Replace with
                    measured kinematics per speed (Camargo) when available.

Domain randomisation (Luo et al. 2024, Nature): parameters a real device cannot
measure on its user. D1 samples them, the surrogate and policy never see them,
so D4 measures whether the policy is robust to them. All default to 1 (nominal).
    fiber_length_scale  every muscle's optimal fiber length. Tendon slack length
                        moves the other way, so the nominal operating point stays
                        on the plateau; what changes is the force-length width.
    exo_capacity_scale  torque the device actually delivers / its nominal cap p_j
    device_mass_scale   device mass / DEVICE_MASS

Runs under the OpenSim env (Python 3.11 + `conda install -c opensim-org opensim`).
"""

import os
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import opensim as osim

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models" / "base" / "2D_gait.osim"
KINEMATICS = ROOT / "models" / "base" / "referenceCoordinates.sto"

MUSCLES = ["hamstrings", "bifemsh", "glut_max", "iliopsoas", "rect_fem",
           "vasti", "gastroc", "soleus", "tib_ant"]
BIARTICULAR = ["hamstrings", "rect_fem", "gastroc"]
JOINTS = {"hip": "hip_flexion", "knee": "knee_angle", "ankle": "ankle_angle"}
N_PHASE = 100   # samples per full gait cycle

# Per side. ponytail: generic powered-orthosis masses, not a specific device.
# Swap for the real device's mass breakdown (Zhang et al. 2021) when known.
DEVICE_MASS = {"pelvis": 2.0, "femur": 1.0, "tibia": 1.0, "calcn": 0.3}

osim.Logger.setLevelString("error")


@dataclass
class Subject:
    mass_scale: float = 1.0
    strength_scale: float = 1.0
    # hidden: randomised in D1, never observed by the surrogate or policy
    fiber_length_scale: float = 1.0
    exo_capacity_scale: float = 1.0
    device_mass_scale: float = 1.0


@dataclass
class Condition:
    speed_scale: float = 1.0
    load_kg: float = 0.0


def _kinematics(speed_scale, out_dir):
    """Reference kinematics, time-scaled, written where Moco can read it."""
    table = osim.TimeSeriesTable(str(KINEMATICS))
    t = np.array(table.getIndependentColumn()) / speed_scale
    # set times in the order that keeps the column increasing at every step
    order = range(len(t)) if speed_scale >= 1 else reversed(range(len(t)))
    for i in order:
        table.setIndependentValueAtIndex(i, float(t[i]))
    path = os.path.join(out_dir, "kinematics.sto")
    osim.STOFileAdapter.write(table, path)
    t = osim.TimeSeriesTable(path).getIndependentColumn()   # as written: .sto rounds
    return path, float(t[0]), float(t[-1])


def _body_model(subject, condition, device):
    """Model with mass, strength, load and (optionally) device mass applied."""
    model = osim.Model(str(MODEL))
    m0 = sum(model.getBodySet().get(i).getMass() for i in range(model.getBodySet().getSize()))
    for i in range(model.getBodySet().getSize()):
        b = model.getBodySet().get(i)
        b.setMass(b.getMass() * subject.mass_scale)
    added = {"torso": condition.load_kg}
    if device:
        for seg, dm in DEVICE_MASS.items():
            dm *= subject.device_mass_scale
            if seg == "pelvis":
                added["pelvis"] = added.get("pelvis", 0.0) + 2 * dm
            else:
                for side in "lr":
                    added[f"{seg}_{side}"] = dm
    for name, dm in added.items():
        b = model.getBodySet().get(name)
        b.setMass(b.getMass() + dm)
    m1 = m0 * subject.mass_scale + sum(added.values())

    for c in components(model, osim.SmoothSphereHalfSpaceForce):
        c.set_stiffness(c.get_stiffness() * m1 / m0)
    for m in components(model, osim.Muscle):
        m.setMaxIsometricForce(m.getMaxIsometricForce() * subject.strength_scale)
        # fiber length along the tendon at optimum is l_opt * cos(pennation_at_optimal);
        # give the tendon what the fiber loses, so the nominal MTU length is unchanged
        lopt = m.getOptimalFiberLength()
        dl = lopt * (1.0 - subject.fiber_length_scale)
        m.setOptimalFiberLength(lopt - dl)
        m.setTendonSlackLength(m.getTendonSlackLength() + dl * np.cos(m.getPennationAngleAtOptimalFiberLength()))
    return model


def components(model, cls):
    """Every component of type cls, wherever it sits. This model keeps its forces at
    the ROOT, not in the ForceSet (which is empty) -- iterating getForceSet() silently
    scaled nothing. getMuscles() is also empty here, for the same reason."""
    model.finalizeFromProperties()
    paths = [c.getAbsolutePathString() for c in model.getComponentsList()]
    return [x for x in (cls.safeDownCast(model.updComponent(p)) for p in paths) if x]


def _inverse(model, kin_path, t0, t1, mesh=50):
    # Pelvis residuals are fixed by the kinematics -- no muscle can change them --
    # so price them near zero (optimal force 1000). At optimal force 1 they were
    # ~9000 of the objective against ~1 for the muscles, and at 1e-3 tolerance the
    # activations were never actually optimised: full assistance (p = 1) left them
    # unchanged. Joint reserves stay at 1, expensive, used only when muscles can't.
    for coord in ("pelvis_tx", "pelvis_ty", "pelvis_tilt"):
        r = osim.CoordinateActuator(coord)
        r.setName(f"reserve_{coord}")
        r.setOptimalForce(PELVIS_F)
        model.addForce(r)
    # Same trap: the model's torso actuator (lumbarAct, optimal force 1) carries ~4 Nm
    # and dominated the objective. The torso is not under study -- make it cheap.
    lumbar = osim.CoordinateActuator.safeDownCast(model.updComponent("/lumbarAct"))
    lumbar.setOptimalForce(1000.0)
    lumbar.setMinControl(-1.0)
    lumbar.setMaxControl(1.0)
    model.finalizeConnections()
    inv = osim.MocoInverse()
    proc = osim.ModelProcessor(model)
    proc.append(osim.ModOpIgnoreTendonCompliance())
    proc.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
    proc.append(osim.ModOpIgnorePassiveFiberForcesDGF())
    proc.append(osim.ModOpScaleActiveFiberForceCurveWidthDGF(1.5))
    # reserves at EVERY coordinate, even where the exo sits: the default skips
    # coordinates that already have an actuator, which silently changed the
    # problem with p (no knee reserve once a knee exo existed) -> infeasible at p=0.3
    proc.append(osim.ModOpAddReserves(1.0, 1000.0, False))
    inv.setModel(proc)
    inv.setKinematics(osim.TableProcessor(kin_path))
    inv.set_kinematics_allow_extra_columns(True)
    inv.set_initial_time(t0)
    inv.set_final_time(t1)
    inv.set_mesh_interval((t1 - t0) / mesh)
    inv.set_minimize_sum_squared_activations(True)
    inv.set_convergence_tolerance(TOL)
    study = inv.initialize()
    # the device is (nearly) free: Dembia's ideal device. Not exactly 0, which
    # would leave its torque unregularised wherever muscles and device tie.
    effort = osim.MocoControlGoal.safeDownCast(study.updProblem().updGoal("excitation_effort"))
    effort.setWeightForControlPattern(".*exo_.*", EXO_WEIGHT)
    return study, study.solve()   # keep study alive alongside its solution


def net_moments(subject, condition, kin_path, t0, t1):
    """Net joint moments from an ID-equivalent solve: muscles out, ideal torques in.

    Returns (time, {coordinate_name: moment[Nm]}) for hip/knee/ankle, both legs.
    """
    model = _body_model(subject, condition, device=True)
    proc = osim.ModelProcessor(model)
    proc.append(osim.ModOpRemoveMuscles())
    proc.append(osim.ModOpAddReserves(100.0, 1000.0))   # torque = 100 * control
    inv = osim.MocoInverse()
    inv.setModel(proc)
    inv.setKinematics(osim.TableProcessor(kin_path))
    inv.set_kinematics_allow_extra_columns(True)
    inv.set_initial_time(t0)
    inv.set_final_time(t1)
    inv.set_mesh_interval((t1 - t0) / 50)
    res = inv.solve()
    sol = res.getMocoSolution()      # reference into res; res stays alive in this scope
    if not sol.success():
        raise RuntimeError("net-moment (ID) solve did not converge")
    t = np.array(sol.getTimeMat())
    out = {}
    for j in JOINTS.values():
        for side in "lr":
            out[f"{j}_{side}"] = 100.0 * np.array(
                sol.getControlMat(_reserve_path(sol, f"{j}_{side}")))
    return t, out


def _reserve_path(sol, coord):
    names = [n for n in sol.getControlNames() if n.endswith(coord)]
    assert len(names) == 1, (coord, list(sol.getControlNames()))
    return names[0]


PELVIS_F = 1000.0   # pelvis residual optimal force: near-free (see _inverse)
TOL = 1e-4  # IPOPT tolerance. 1e-3 left activations ~0.02 too high (p = 1: 0.035 vs 0.016),
            # and the fatigue threshold M_th = 0.05 sits right at these levels
EXO_F = 100.0      # device optimal force: controls stay O(0.1-1), well scaled for IPOPT
EXO_WEIGHT = 1e-3  # device's weight in the effort goal: ~free (muscles and reserves weigh 1)


def _add_exo(model, peaks, p, capacity=1.0):
    """Ideal assistive device per joint (Dembia et al. 2017, PLoS ONE): a torque
    actuator the optimiser uses freely, capped at |tau| <= capacity * p_j * peak|tau_net_j|.
    capacity < 1 is a device that under-delivers its nominal cap (Subject.exo_capacity_scale).

    p_j is the device's torque capacity at joint j as a fraction of that joint's
    peak net moment. Its effort cost is ~0 (EXO_WEIGHT), so within the cap it takes
    over whatever load minimises muscle effort -- an upper bound on what a device
    with that capacity can do, which is the standard way to compare allocations.

    Replaced a prescribed tau = p * tau_net(t) applied as +/- body torques: an ID
    re-solve showed it delivered only 85% (hip, knee) and 38% (ankle) of the
    intended moment, cause not found. A plain CoordinateActuator is exact by
    construction, and it works for the 3D model too.
    """
    for (joint, coord), pj in zip(JOINTS.items(), p):
        if pj <= 0:
            continue
        for side in "lr":
            act = osim.CoordinateActuator(f"{coord}_{side}")
            act.setName(f"exo_{joint}_{side}")
            act.setOptimalForce(EXO_F)
            lim = capacity * pj * peaks[f"{coord}_{side}"] / EXO_F
            act.setMinControl(-lim)
            act.setMaxControl(lim)
            model.addForce(act)
    model.finalizeConnections()


def activations(subject=Subject(), condition=Condition(), p=(0.0, 0.0, 0.0)):
    """One twin evaluation. Returns dict with acts (100, 9), residual, timing."""
    p = tuple(float(x) for x in p)
    tic = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        kin, t0, t1 = _kinematics(condition.speed_scale, tmp)
        _, moments = net_moments(subject, condition, kin, t0, t1)
        peaks = {k: float(np.abs(v).max()) for k, v in moments.items()}
        model = _body_model(subject, condition, device=True)
        _add_exo(model, peaks, p, subject.exo_capacity_scale)
        study, sol = _inverse(model, kin, t0, t1)
    solve_s = time.perf_counter() - tic
    success = bool(sol.success())
    if not success:
        sol.unseal()   # keep the failed trajectory: non-convergence is data (flagged by success)

    t = np.array(sol.getTimeMat())
    half = np.linspace(t[0], t[-1], N_PHASE // 2)

    def act(name):
        return np.interp(half, t, np.array(sol.getStateMat(next(s for s in sol.getStateNames() if s.endswith(f"/{name}/activation")))))

    acts = np.stack([np.concatenate([act(f"{m}_r"), act(f"{m}_l")]) for m in MUSCLES], axis=1)
    def force(n):   # control x optimal force: 1 for Moco's reserves, 1000 for our pelvis residuals
        return np.array(sol.getControlMat(n)) * (PELVIS_F if "/reserve_pelvis_" in n else 1.0)

    def rms(names):
        return float(np.sqrt(np.mean([np.mean(force(n) ** 2) for n in names])))
    res_names = [n for n in sol.getControlNames() if "reserve" in n]
    return {
        "acts": acts,
        "cycle_s": 2 * (t[-1] - t[0]),
        "residual_rms": rms([n for n in res_names if "pelvis" in n]),     # N / Nm, pelvis
        "reserve_rms": rms([n for n in res_names if "pelvis" not in n]),  # Nm, joints
        "solve_s": solve_s,
        "success": success,
        "p": np.array(p),
        "subject": asdict(subject),
        "condition": asdict(condition),
    }


def _check_scaling():
    """Subject scaling must actually reach the muscles, the contacts and the bodies."""
    ref = _body_model(Subject(), Condition(), device=False)
    mod = _body_model(Subject(mass_scale=1.2, strength_scale=1.3), Condition(load_kg=10), device=False)

    def tot(m, cls, get):
        xs = [get(c) for c in components(m, cls)]
        assert xs, f"no {cls.__name__} found -- scaling would silently do nothing"
        return sum(xs)
    f = tot(mod, osim.Muscle, lambda c: c.getMaxIsometricForce()) / tot(ref, osim.Muscle, lambda c: c.getMaxIsometricForce())
    k = tot(mod, osim.SmoothSphereHalfSpaceForce, lambda c: c.get_stiffness()) /         tot(ref, osim.SmoothSphereHalfSpaceForce, lambda c: c.get_stiffness())
    mass = lambda m: sum(m.getBodySet().get(i).getMass() for i in range(m.getBodySet().getSize()))
    m0 = mass(ref)
    assert abs(f - 1.3) < 1e-9, f"strength scale applied as {f}"
    assert abs(mass(mod) - (1.2 * m0 + 10)) < 1e-9, "mass scale / load not applied"
    assert abs(k - mass(mod) / m0) < 1e-9, f"contact stiffness scaled by {k}"

    # hidden parameters: fiber length scaled, nominal MTU length kept, device mass scaled
    fib = _body_model(Subject(fiber_length_scale=0.9, device_mass_scale=1.5), Condition(), device=True)
    nom = _body_model(Subject(), Condition(), device=True)
    pairs = list(zip(components(nom, osim.Muscle), components(fib, osim.Muscle)))
    assert pairs, "no muscles found -- fiber length scaling would silently do nothing"
    for a, b in pairs:
        cos = np.cos(a.getPennationAngleAtOptimalFiberLength())
        assert abs(b.getOptimalFiberLength() / a.getOptimalFiberLength() - 0.9) < 1e-9
        assert abs((b.getTendonSlackLength() + b.getOptimalFiberLength() * cos)
                   - (a.getTendonSlackLength() + a.getOptimalFiberLength() * cos)) < 1e-12
    dev = mass(nom) - m0                                   # device mass at scale 1
    assert abs(mass(fib) - m0 - 1.5 * dev) < 1e-9, "device mass scale not applied"
    peaks = {f"{c}_{s}": 50.0 for c in JOINTS.values() for s in "lr"}
    _add_exo(nom, peaks, (0.2, 0.2, 0.2), capacity=0.8)
    lims = [a.getMaxControl() for a in components(nom, osim.CoordinateActuator) if "exo_" in a.getName()]
    assert len(lims) == 6 and np.allclose(lims, 0.8 * 0.2 * 50.0 / EXO_F), f"exo capacity not applied: {lims}"


if __name__ == "__main__":
    _check_scaling()
    print("scaling OK: strength, mass, load, contact stiffness, fiber length, device mass all applied")
    base = activations()
    print(f"unassisted: solve {base['solve_s']:.1f} s, success={base['success']}, "
          f"pelvis residual rms {base['residual_rms']:.1f}, joint reserve rms {base['reserve_rms']:.2f} Nm")
    assisted = activations(p=(0.3, 0.3, 0.3))
    print(f"30% all joints: solve {assisted['solve_s']:.1f} s")
    print(f"\n{'muscle':<12}{'mean a, none':>14}{'mean a, 30%':>14}{'change':>9}")
    for i, m in enumerate(MUSCLES):
        a0, a1 = base["acts"][:, i].mean(), assisted["acts"][:, i].mean()
        print(f"{m:<12}{a0:>14.3f}{a1:>14.3f}{(a1 - a0) / a0:>8.0%}")

    assert base["success"] and assisted["success"], "MocoInverse did not converge"
    assert assisted["acts"].mean() < base["acts"].mean(), "assistance must unload muscles"
    print(f"\nOK: twin solves, assistance unloads muscles. "
          f"GATE A solve time = {base['solve_s']:.1f} s per evaluation (2 Moco solves).")

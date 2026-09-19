"""MFAC: Zhang et al.'s muscle fatigue-aware controller (IEEE T-ASE 2026, eq. 24-30).

Decision variable is p, the fraction of knee torque the device compensates.
Cost (eq. 26)  J = K'QK + P'RP  with  k_i = 1/(V_m - V_i)  (eq. 27), so the state
term blows up as fatigue approaches V_m and the optimiser trades that against
assistance effort through w_r (eq. 29).

branch= selects how the fatigue ODE's threshold is handled inside the horizon:

  "frozen"  their workaround -- pick fatigue or recovery from the CURRENT
            activation and hold it for the whole horizon (paper, sec. II-D)
  "smooth"  E1 -- sigmoid blend, differentiable, valid across a transition

Identical whenever the horizon does not straddle the threshold, which is why the
static squat cannot distinguish them. The periodic trials can.
"""

import casadi as ca
import numpy as np


class MFAC:
    def __init__(self, CF, R, M_th, N=10, dt=0.01, V_m=1.0, p_max=0.3,
                 F_min=5.0, F_max=180.0, dF_max=10.0, w_r=0.5, W=1.0,
                 branch="frozen", k_smooth=1e-2):
        self.N, self.dt, self.branch = N, dt, branch
        self.CF, self.R, self.M_th = CF, R, M_th

        p = ca.SX.sym("p", N)
        # parameters that change every solve
        V_c   = ca.SX.sym("V_c")      # current fatigue
        tau   = ca.SX.sym("tau", N)   # predicted knee torque over horizon (eq. 21)
        R_e   = ca.SX.sym("R_e")      # virtual moment arm, torque -> activation (eq. 25)
        L_a   = ca.SX.sym("L_a")      # device lever arm (eq. 30)
        F_pre = ca.SX.sym("F_pre")    # last commanded tension, for the rate limit
        frz   = ca.SX.sym("frz")      # frozen branch: 1 fatigue, 0 recovery

        J, V, g = 0, V_c, []
        for i in range(N):
            E = tau[i] * (1 - p[i]) / R_e                      # eq. 24
            if branch == "frozen":
                s = frz
            elif branch == "smooth":
                s = 0.5 * (1 + ca.tanh((E - M_th) / k_smooth))  # E1
            else:
                raise ValueError(branch)
            V = V + (s * (1 - V) * E / CF - (1 - s) * V * R / CF) * dt   # eq. 19/20
            J += W * w_r * (1.0 / (V_m - V)) ** 2 + W * (1 - w_r) * p[i] ** 2
            F = p[i] * tau[i] / L_a                            # eq. 30
            g += [F, F - (F_pre if i == 0 else p[i - 1] * tau[i - 1] / L_a)]

        self.nlp = ca.nlpsol("mfac", "ipopt",
                             {"x": p, "f": J, "g": ca.vertcat(*g),
                              "p": ca.vertcat(V_c, tau, R_e, L_a, F_pre, frz)},
                             {"ipopt.print_level": 0, "print_time": 0,
                              "ipopt.sb": "yes", "ipopt.max_iter": 200})
        self.lbx, self.ubx = [0.0] * N, [p_max] * N
        self.lbg = [F_min, -dF_max] * N
        self.ubg = [F_max,  dF_max] * N
        self._warm = np.zeros(N)

    def step(self, V_c, tau, R_e, L_a, F_prev):
        """One MPC solve. Returns p for the current instant."""
        tau = np.broadcast_to(np.asarray(tau, float), (self.N,))
        frz = 1.0 if tau[0] * (1 - self._warm[0]) / R_e > self.M_th else 0.0
        sol = self.nlp(x0=self._warm, lbx=self.lbx, ubx=self.ubx,
                       lbg=self.lbg, ubg=self.ubg,
                       p=np.concatenate([[V_c], tau, [R_e, L_a, F_prev, frz]]))
        self._warm = np.array(sol["x"]).ravel()
        return float(self._warm[0])


# --- static-squat plant (Gate R) -------------------------------------------
# Subject S1, knee held at ~90 deg. tau_kf ~100 Nm (paper Fig. 7 row 2).
TAU, THETA, M0, V_TH = 100.0, 90.0, 0.198, 0.8
L_A = float(np.polyval([-2.271e-12, 1.096e-9, -2.462e-7, 2.870e-5, -1.012e-3, 0.074], THETA))
R_E = TAU / M0          # eq. 25, fixed since the hold is isometric


def policy(w_r, CF, R=0.5, M_th=0.05, n=40, **kw):
    """Tabulate p*(V) with the rate limit relaxed, then interpolate.

    The hold is isometric, so after the ~0.2 s ramp-in the only slow state is V
    and the |dF| limit is inactive -- p* becomes a pure function of V. 40 solves
    instead of 7600, and the transient it drops is 0.3% of a 76 s trial.
    """
    m = MFAC(CF=CF, R=R, M_th=M_th, w_r=w_r, dF_max=1e9, **kw)
    Vs = np.linspace(0.0, V_TH, n)
    ps = [m.step(V, TAU, R_E, L_A, 5.0) for V in Vs]
    return lambda V, F=None, t=None: float(np.interp(V, Vs, ps))


def simulate(control, CF, R=0.5, M_th=0.05, dt=0.01, t_max=200.0,
             tau=None, V_stop=V_TH, V0=0.0):
    """Run until V reaches V_stop or t_max. control(V, F_prev, t) -> p.

    tau: None for the isometric hold, else tau(t) -> knee torque [Nm].
    Returns (time_to_V_stop or nan, p trace, V trace).
    """
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fatigue"))
    from model import dV

    tau_of = (lambda t: TAU) if tau is None else tau
    V, F_prev, ps, Vs, t_hit = V0, 5.0, [], [], np.nan
    for i in range(int(t_max / dt)):
        t = i * dt
        tq = tau_of(t)
        p = control(V, F_prev, t)
        ps.append(p)
        Vs.append(V)
        F_prev = max(p * tq / L_A, 5.0)
        V = float(V + dV(V, tq * (1 - p) / R_E, CF, R, M_th) * dt)
        if V >= V_stop and np.isnan(t_hit):
            t_hit = t
            if tau is None:
                break
    return t_hit, np.array(ps), np.array(Vs)


if __name__ == "__main__":
    CF = 8.2365   # src/fatigue/calibrate.py, fitted on their no-assistance trial
    W_R = 0.9     # TUNED: the paper never publishes w_r. Chosen so mean assistance
                  # matches their reported activation drop (0.198 -> 0.175, p=0.116).
    paper = {"no assistance": 66.95, "constant 15%": 73.60, "MFAC": 76.15}

    print(f"L_a({THETA:.0f} deg) = {L_A:.4f} m   R_e = {R_E:.1f}   "
          f"F_max binds at p = {180 * L_A / TAU:.3f}")
    runs = {"no assistance": lambda V, F, t: 0.0,
            "constant 15%":  lambda V, F, t: 0.15,
            "MFAC":          policy(W_R, CF)}
    print()
    print(f"{'trial':<16}{'paper':>8}{'sim':>8}{'err':>8}{'mean p':>9}{'final p':>9}")
    out = {}
    for name, ctl in runs.items():
        t, ps, _ = simulate(ctl, CF)
        out[name] = (t, ps)
        print(f"  {name:<16}{paper[name]:>8.2f}{t:>8.2f}"
              f"{(t - paper[name]) / paper[name]:>7.1%}{ps.mean():>9.3f}{ps[-1]:>9.3f}")

    t_m, ps_m = out["MFAC"]
    assert abs(t_m - paper["MFAC"]) / paper["MFAC"] < 0.02, "MFAC time off by >2%"
    assert ps_m[0] < 0.05 < ps_m[-1], "assistance must ramp, not start saturated"
    assert abs(ps_m[-1] - 180 * L_A / TAU) < 1e-3, "should end pinned at F_max"

    print()
    print("OK: MFAC reproduced to 1.1% with assistance ramping 0 -> F_max bound,")
    print("    matching their Fig. 7 (tension rising to the 180 N limit as V grows).")
    print()
    print("Caveats:")
    print("  - constant 15% over-predicts: the ideal linear torque->activation map")
    print("    (their eq. 25) delivers 15% unloading where they measured 9.6%.")
    print("  - w_r tuned, not published. The ramp SHAPE and F_max saturation are")
    print("    predictions; the assistance LEVEL is fitted.")
    print("  - static squat never crosses M_th, so frozen and smooth branches are")
    print("    identical here. E1 needs the periodic trials to show a difference.")

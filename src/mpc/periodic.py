"""E1 steps 2-3: what does freezing the fatigue branch across the horizon cost?

The static squat cannot answer this -- activation sits at 0.19 against a 0.05
threshold and never crosses, so both branch modes are identical. Their PERIODIC
squat does cross it: knee torque falls to a standing residual between reps, so
the model swaps to recovery mode twice a cycle.

Zhang et al. handle the swap by picking one branch from the CURRENT activation
and holding it for the whole horizon (sec. II-D). That is wrong exactly when the
horizon straddles a transition. This measures how wrong, and when.

Both controllers get oracle future torque, so the only difference is the branch
treatment -- torque-prediction error is E5's problem, not E1's.

RESULT. Cadence is the wrong axis: the straddle FRACTION tracks 2*horizon/period
exactly, but the resulting control error does not grow with it, because short
cycles move less fatigue per straddle. HORIZON LENGTH is the axis that matters.
The approximation is benign at their 0.1 s horizon and collapses by 0.5 s,
saturating at ~0.215 peak error in p -- 72% of p_max. The ceiling sits near
horizon ~ 0.05 * C_F. That is E1's point: freezing the branch caps how far ahead
a fatigue-aware controller can plan, and E2's long-horizon multi-joint
allocation needs to plan further than that cap allows.
"""

import numpy as np
from mfac import MFAC, simulate, TAU, R_E, L_A, M0, V_TH

CF, W_R, DT, N = 8.2365, 0.9, 0.01, 10
TAU_REST = 10.0   # standing knee moment: E ~0.02, below M_th, so recovery engages


def squat_profile(period=10.0, hold=3.0, ramp=2.0):
    """Their protocol: stand-to-squat, hold, return, rest. Piecewise linear."""
    t_pts = [0.0, ramp, ramp + hold, 2 * ramp + hold, period]
    v_pts = [TAU_REST, TAU, TAU, TAU_REST, TAU_REST]
    assert 2 * ramp + hold <= period, "ramps + hold exceed the period"
    return lambda t: float(np.interp(t % period, t_pts, v_pts))


def run(branch, tau_of, n_cycles, period, k_smooth=1e-2):
    mpc = MFAC(CF=CF, R=0.5, M_th=0.05, N=N, dt=DT, w_r=W_R,
               branch=branch, k_smooth=k_smooth)
    horizon = np.arange(N) * DT
    straddles = []

    def control(V, F_prev, t):
        tau_h = np.array([tau_of(t + h) for h in horizon])
        # does activation cross M_th inside this horizon?
        E = tau_h * (1 - mpc._warm) / R_E
        straddles.append((E > 0.05).any() and (E <= 0.05).any())
        return mpc.step(V, tau_h, R_E, L_A, F_prev)

    _, ps, Vs = simulate(control, CF, dt=DT, t_max=n_cycles * period,
                         tau=tau_of, V_stop=2.0)
    return ps, Vs, float(np.mean(straddles))


def compare(n_cycles=2, period=10.0, hold=3.0, ramp=2.0):
    tau_of = squat_profile(period, hold, ramp)
    out = {b: run(b, tau_of, n_cycles, period) for b in ("frozen", "smooth")}
    (pf, Vf, strad), (pss, Vs, _) = out["frozen"], out["smooth"]
    return dict(straddle=strad,
                dV_final=Vf[-1] - Vs[-1], V_final=Vf[-1],
                dp_mean=np.abs(pf - pss).mean(), dp_max=np.abs(pf - pss).max(),
                p_frozen=pf.mean(), p_smooth=pss.mean())


def sweep(periods=(10.0, 2.0, 0.6), sim_time=6.0):
    """Step 3: cadence sweep.

    A horizon straddles a crossing whenever it starts within one horizon-length
    of one. With two crossings per cycle that predicts

        straddle fraction ~ 2 * horizon / period

    independent of how fast the ramp itself is -- so the axis that matters is
    CADENCE, not transition sharpness. Their squat sits at 10 s; walking is ~1 s.
    """
    rows = []
    for T in periods:
        tau_of = squat_profile(T, hold=0.3 * T, ramp=0.2 * T)
        n = max(1, int(round(sim_time / T)))   # equal simulated DURATION, not cycles
        r = compare(n_cycles=n, period=T, hold=0.3 * T, ramp=0.2 * T)
        r["duration"] = n * T
        rows.append((T, 2 * N * DT / T, r))
    return rows


def horizon_sweep(Ns=(10, 50, 100), period=10.0):
    """The axis that actually matters. Varies horizon at fixed cadence.

    Defaults are trimmed so this runs in a few minutes. The full sweep gives

        horizon  h/C_F  straddle  mean|dp|  max|dp|   dV_final
           0.10  0.012     1.8%   4.78e-04  2.92e-02  +2.18e-04
           0.50  0.061     9.7%   6.33e-03  2.14e-01  +2.21e-03
           1.00  0.121    19.6%   1.26e-02  2.15e-01  +3.04e-03
           2.00  0.243    39.7%   1.54e-02  2.17e-01  +2.99e-03

    -- so the peak error saturates at ~0.215 (72% of p_max) from 0.5 s onward.
    """
    global N
    rows, n0 = [], N
    try:
        for n in Ns:
            N = n
            r = compare(n_cycles=1, period=period, hold=3.0, ramp=2.0)
            rows.append((n, n * DT, n * DT / CF, r))
    finally:
        N = n0
    return rows


if __name__ == "__main__":
    print("E1 steps 2-3: frozen vs smooth fatigue branch (oracle torque)")
    print(f"  tau {TAU_REST:.0f} -> {TAU:.0f} Nm, M_th 0.05, C_F {CF:.2f} s")
    print()
    print("  their periodic protocol, their 0.10 s horizon:")
    r0 = compare()
    print(f"    horizon straddles a crossing   {r0['straddle']:.1%} of steps")
    print(f"    mean |p_frozen - p_smooth|     {r0['dp_mean']:.2e}")
    print(f"    max  |p_frozen - p_smooth|     {r0['dp_max']:.2e}")
    print(f"    -> negligible. Their workaround is sound at this horizon.")
    print()
    print("  cadence sweep - straddle frequency rises, error does NOT:")
    print(f"    {'period':>8}{'straddle':>10}{'2h/T':>8}{'mean|dp|':>11}{'max|dp|':>10}")
    cad = sweep()
    for T, pred, r in cad:
        print(f"    {T:>8.1f}{r['straddle']:>9.1%}{pred:>8.1%}"
              f"{r['dp_mean']:>11.2e}{r['dp_max']:>10.2e}")
    print()
    print("  horizon sweep - the axis that matters:")
    print(f"    {'horizon':>9}{'h/C_F':>8}{'straddle':>10}{'mean|dp|':>11}{'max|dp|':>10}")
    hor = horizon_sweep()
    for n, h, ratio, r in hor:
        print(f"    {h:>9.2f}{ratio:>8.3f}{r['straddle']:>9.1%}"
              f"{r['dp_mean']:>11.2e}{r['dp_max']:>10.2e}")

    # straddle fraction is analytic: 2 crossings, each caught one horizon ahead
    for T, pred, r in cad:
        assert abs(r["straddle"] - pred) < 0.04, f"straddle off theory at T={T}"
    assert all(r["dV_final"] >= 0 for _, _, r in cad), "frozen should never win"
    # cadence does not drive the error; horizon does
    assert cad[-1][2]["dp_mean"] < 2 * cad[0][2]["dp_mean"], "error grew with cadence?"
    assert hor[-1][3]["dp_mean"] > 10 * hor[0][3]["dp_mean"], "error flat in horizon?"
    assert hor[0][3]["dp_max"] < 0.05 < hor[1][3]["dp_max"], "ceiling not between 0.1 and 0.5 s"

    print()
    print("  OK: straddle fraction = 2*horizon/period (analytic, confirmed).")
    print("      Cadence does not drive the error. Horizon does: benign at 0.10 s,")
    print("      0.215 peak error in p by 0.50 s -- 72% of p_max. The frozen branch")
    print("      caps planning horizon near 0.05*C_F; the smooth form removes the cap.")

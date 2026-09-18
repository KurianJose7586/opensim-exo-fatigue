"""Gate R, part 1: calibrate C_F against Zhang et al. and predict their other trials.

Static squat, so activation is ~constant and M stays well above M_th (0.19 vs 0.05):
the model never leaves fatigue mode and dV/dt = (1-V)*M/C_F integrates in closed form

    V(t) = 1 - exp(-M*t/C_F)   ->   t(V) = -C_F*ln(1-V)/M

C_F is fitted to the no-assistance trial alone. The two assisted trials are then
predictions, using only the mean activations the paper reports. Those are the
actual test -- the fitted point proves nothing by itself.
"""

import numpy as np

V_TH = 0.8  # paper's stopping criterion for the static squat

# Zhang et al. Table/Fig. 8 mean activation, and Fig. 7 time to V = 0.8.
# 'emg' = measured, 'gpr' = model estimate. Their controller runs on 'gpr'.
TRIALS = {                    # label          M_emg  M_gpr   t(V=0.8) [s]
    "no assistance":                          (0.194, 0.198,  66.95),
    "constant 15%":                           (0.182, 0.179,  73.60),
    "MFAC":                                   (0.174, 0.175,  76.15),
}


def fit_CF(M, t_to_threshold, V_th=V_TH):
    """C_F from one constant-activation endurance trial."""
    return -M * t_to_threshold / np.log(1.0 - V_th)


def time_to(V_th, M, CF):
    return -CF * np.log(1.0 - V_th) / M


def _report(source, idx):
    M_ref, t_ref = TRIALS["no assistance"][idx], TRIALS["no assistance"][2]
    CF = fit_CF(M_ref, t_ref)
    print(f"\n{source}: C_F = {CF:.4f} s  (fitted on no-assistance only)")
    print(f"  {'trial':<16}{'M':>8}{'paper':>9}{'model':>9}{'error':>9}")
    errs = []
    for name, row in TRIALS.items():
        M, t_paper = row[idx], row[2]
        t_hat = time_to(V_TH, M, CF)
        err = (t_hat - t_paper) / t_paper
        tag = "  <- fitted" if name == "no assistance" else ""
        print(f"  {name:<16}{M:>8.3f}{t_paper:>9.2f}{t_hat:>9.2f}{err:>8.1%}{tag}")
        if name != "no assistance":
            errs.append(abs(err))
    return CF, max(errs)


if __name__ == "__main__":
    _, emg_err = _report("measured EMG", 0)
    CF, gpr_err = _report("GPR estimate", 1)

    # Closed form must agree with the numerical integrator in model.py.
    from model import integrate
    dt = 0.01
    M = np.full((int(120 / dt), 1), TRIALS["no assistance"][1])
    V = integrate(M, [CF], [0.5], [0.05], dt)[:, 0]
    t_num = np.searchsorted(V, V_TH) * dt
    assert abs(t_num - 66.95) < 0.1, f"integrator gives {t_num:.2f}s, expected 66.95s"

    # Their own linear torque->activation map (eq. 25, R_e constant) says p percent
    # torque compensation should drop activation by p percent. Check that.
    M0 = TRIALS["no assistance"][1]
    print()
    print("commanded compensation vs delivered unloading:")
    for name, p in (("constant 15%", 0.15), ("MFAC", 0.30)):   # MFAC p_max = 0.3
        got = (M0 - TRIALS[name][1]) / M0
        print(f"  {name:<16} commanded {p:>5.0%}   delivered {got:>5.1%}"
              f"   ratio {got / p:>4.2f}")
    # ponytail: no-assistance trial still wears the device under 5 N pretension, and
    # MFAC only reaches p_max late in the trial -- so these ratios are indicative,
    # not a clean efficiency measurement. Enough to say linearity is optimistic.

    assert gpr_err < 0.01, f"GPR-driven predictions off by {gpr_err:.1%}"
    print(f"\nOK: C_F = {CF:.3f} s fitted on one trial predicts both assisted")
    print(f"    endurance times to within {gpr_err:.1%} (GPR) / {emg_err:.1%} (EMG).")
    print("    GPR wins because their fatigue model is driven by the estimate, not raw EMG.")

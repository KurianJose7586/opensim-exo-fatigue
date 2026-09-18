"""Peternel/Ma muscle fatigue model, exact and smoothed.

Exact form (Peternel 2019 eq. 7, Zhang 2026 eq. 8):

    dV/dt = (1-V)*M/CF   if M > M_th    fatigue
            -V*R/CF      otherwise      recovery

The branch is non-differentiable, so gradient-based optimisers cannot cross it.
Zhang et al. work around this by freezing the branch for a whole MPC horizon.
Passing k > 0 blends the two modes with a sigmoid instead, which is smooth
everywhere and recovers the exact model as k -> 0.
"""

import numpy as np


def dV(V, M, CF, R, M_th, k=0.0):
    """Fatigue rate. k=0 gives the exact branch, k>0 the smoothed blend."""
    M = np.maximum(M, 0.0)
    s = (M > M_th).astype(float) if k <= 0.0 else 0.5 * (1.0 + np.tanh((M - M_th) / k))
    return s * (1.0 - V) * M / CF - (1.0 - s) * V * R / CF


def integrate(M_trace, CF, R, M_th, dt, k=0.0, V0=None, clamp=True):
    """Forward Euler over an (n_steps, n_muscles) activation trace.

    Euler and clamping mirror the reference implementation so the k=0 case is
    bit-comparable against it. The ODE is self-bounding in [0,1] (both modes
    have a fixed point at the relevant edge), so clamp only catches Euler
    overshoot -- it is inert at small dt.
    """
    CF, R, M_th = np.asarray(CF, float), np.asarray(R, float), np.asarray(M_th, float)
    V = np.zeros(M_trace.shape[1]) if V0 is None else np.array(V0, float)
    out = np.empty_like(M_trace, dtype=float)
    for i, M in enumerate(M_trace):
        V = V + dV(V, M, CF, R, M_th, k) * dt
        if clamp:
            V = np.clip(V, 0.0, 1.0)
        out[i] = V
    return out


def _reference(M_trace, CF, R, M_th, dt):
    """Same trace through the authors' unmodified implementation."""
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "external" / "PHRC"))
    from PHRC_muscle_fatigue_model import muscle_fatigue_model

    m = muscle_fatigue_model(M_trace.shape[1], dt, np.array(CF, float),
                             np.array(R, float), np.array(M_th, float))
    # ponytail: 2 muscles only -- upstream fatigue() hardcodes range(2). See
    # docs/reference_implementation.md. Widen once we stop needing bit-equality.
    return np.array([m.fatigue(M.copy()).copy() for M in M_trace])


if __name__ == "__main__":
    CF, R, M_th, dt = [20.0, 15.0], [0.5, 0.5], [0.05, 0.05], 0.001
    t = np.arange(0.0, 60.0, dt)
    # crosses M_th twice per cycle -- the regime where the frozen branch is wrong
    M = np.stack([0.05 + 0.05 * np.sin(2 * np.pi * 1.0 * t),
                  0.05 + 0.05 * np.sin(2 * np.pi * 0.5 * t)], axis=1)

    exact = integrate(M, CF, R, M_th, dt, k=0.0)
    assert np.allclose(exact, _reference(M, CF, R, M_th, dt), atol=1e-12), \
        "exact branch diverges from the reference implementation"
    assert exact.min() >= 0.0 and exact.max() <= 1.0

    print(f"{'k':>8}  {'max|V_smooth - V_exact|':>24}  {'err/k':>8}")
    prev = None
    for k in (1e-1, 1e-2, 1e-3, 1e-4, 1e-5):
        err = np.abs(integrate(M, CF, R, M_th, dt, k=k) - exact).max()
        print(f"{k:8.0e}  {err:24.3e}  {err / k:8.2f}")
        assert prev is None or err < prev, "error must shrink as k -> 0"
        prev = err
    assert prev < 1e-4, "smoothed model must converge to the exact branch"
    print("\nOK: matches reference at k=0, converges to it as k -> 0")

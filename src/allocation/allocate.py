"""Phase C: fatigue-aware allocation of assistance across hip, knee and ankle.

Plant, per gait cycle:
    acts = amap(p)                      (100, 9) right-leg activations, from the
                                        twin (Moco grid) or the learned surrogate
    V    <- fatigue over that cycle     per muscle, Peternel 2019 eq. 7, smoothed
                                        (src/fatigue/model.py), activation-driven

OBJECTIVE -- min-max fatigue, not time-to-threshold. Under cyclic load the
fatigue/recovery switch reaches an EQUILIBRIUM: fatigue mode while a muscle is
on, recovery (R = 0.5) while it is off. With the lineage's R the equilibrium
for normal walking sits well below V_th = 0.8, so "time to V_th" is infinite
and Peternel's max-min endurance (eq. 10) is undefined. Its cyclic analogue is
minimising the worst muscle's fatigue, which is what is reported here
(peak_V). Bonus: the equilibrium does not depend on C at all -- C only sets
how fast it is approached -- so the main result does not rest on the unknown
gait-muscle capacity. Verified: toy plant, C = 8.2 and C = 100 both settle at
0.58 (100 at 1200 cycles, 8.2 by 300; Euler-integrated at the time). t_th is still reported for loaded /
fast gait, where the equilibrium can exceed V_th.

Every controller gets the same budget, sum(p) <= BUDGET, so differences come
from WHERE the assistance goes, not how much. Each replan a controller picks p
from a candidate grid by minimising

    sum_i w_i * mean(a_i(p)^2) + LAM * |p|^2

and the controllers differ only in what they know:

  none          p = 0
  knee_only     Zhang-style single joint, per-muscle weights, hip/ankle fixed at 0
  independent   one controller per joint, each sees a SCALAR joint fatigue index
                (max V of muscles crossing it, as Zhang do) and only its own
                uniarticular muscles -- blind to biarticular cross-effects
  blind         multi-joint, w_i = 1: allocates for effort, ignores fatigue
  coupled       ours: w_i = 1/(V_m - V_i)^2 per muscle (Zhang eq. 27 made
                per-muscle), sees every muscle including the biarticular ones

ponytail: grid search over p, not a gradient solver. 3 dims, cheap, exact on
the grid. Swap for CasADi through the smoothed model if the action space grows.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fatigue"))
from model import dV  # noqa: E402

MUSCLES = ["hamstrings", "bifemsh", "glut_max", "iliopsoas", "rect_fem",
           "vasti", "gastroc", "soleus", "tib_ant"]
CROSSES = {"hip":   ["hamstrings", "glut_max", "iliopsoas", "rect_fem"],
           "knee":  ["hamstrings", "bifemsh", "rect_fem", "vasti", "gastroc"],
           "ankle": ["gastroc", "soleus", "tib_ant"]}
UNI = {"hip": ["glut_max", "iliopsoas"], "knee": ["bifemsh", "vasti"],
       "ankle": ["soleus", "tib_ant"]}

# R and M_th: the lineage's values (PHRC code). C: the only measured capacity we
# have, Zhang's knee extensors via src/fatigue/calibrate.py. Applying it to every
# gait muscle is an assumption -- but peak_V does not depend on it (see above).
R, M_TH, K_SMOOTH, V_TH, V_M = 0.5, 0.05, 1e-3, 0.8, 1.0
C_ZHANG = 8.2365
BUDGET, P_MAX, LAM = 0.6, 0.4, 0.05
MINUTES = 10.0
CONTROLLERS = ("none", "knee_only", "independent", "blind", "coupled")


def candidates(step=0.05, budget=BUDGET, p_max=P_MAX):
    g = np.arange(0.0, p_max + 1e-9, step)
    P = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    return P[P.sum(1) <= budget + 1e-9]


def cycle_map(acts, cycle_s, C, k=K_SMOOTH):
    """One gait cycle as an exact affine map per muscle: V_next = A * V + B.

    Within one sample M is constant, so the smoothed eq. 7 is dV/dt = a - b*V,
    linear in V, and solves exactly. The switch s depends on M only, never on V,
    so the whole cycle composes into a single affine map. Exact (no Euler), and
    a 10-cycle step costs one map instead of 1000 Python-level updates.
    """
    dt = cycle_s / acts.shape[-2]
    M = np.maximum(acts, 0.0)
    s = 0.5 * (1.0 + np.tanh((M - M_TH) / k))
    a = s * M / C
    b = (s * M + (1.0 - s) * R) / C                  # > 0 always, since R > 0
    al = np.exp(-b * dt)
    be = a / b * (1.0 - al)
    after = np.cumprod(al[..., ::-1, :], axis=-2)[..., ::-1, :] / al   # prod of later samples
    return al.prod(axis=-2), (be * after).sum(axis=-2)


def cycle(V, acts, cycle_s, C, k=K_SMOOTH, n=1):
    """Fatigue after n gait cycles. V (..., 9), acts (..., 100, 9)."""
    A, B = cycle_map(acts, cycle_s, C, k)
    for _ in range(n):
        V = A * V + B
    return V


def _check_cycle_map():
    """Exact map agrees with fine-step Euler through model.dV, the validated model."""
    acts, C, cs = _toy_amap()(np.zeros(3)), C_ZHANG, 1.0
    V_exact = cycle(np.full(9, 0.3), acts, cs, C)
    V, sub = np.full(9, 0.3), 200                    # Euler, 200 substeps per sample
    for n in range(acts.shape[0]):
        for _ in range(sub):
            V = V + dV(V, acts[n], C, R, M_TH, K_SMOOTH) * cs / acts.shape[0] / sub
    assert np.abs(V - V_exact).max() < 1e-5, np.abs(V - V_exact).max()


def _idx(names):
    return [MUSCLES.index(m) for m in names]


class Allocator:
    """Precomputes effort of every candidate once, then each decision is a dot product."""

    def __init__(self, amap, P=None):
        self.P = candidates() if P is None else P
        self.S = np.array([np.mean(amap(p) ** 2, axis=0) for p in self.P])   # (n_cand, 9)
        self.reg = LAM * (self.P ** 2).sum(1)

    def __call__(self, kind, V):
        P, S = self.P, self.S
        if kind == "none":
            return np.zeros(3)
        if kind == "blind":
            return P[np.argmin(S.sum(1) + self.reg)]
        w = 1.0 / (V_M - np.minimum(V, V_M - 1e-3)) ** 2
        if kind == "coupled":
            return P[np.argmin(S @ w + self.reg)]
        if kind == "knee_only":
            ok = (P[:, 0] == 0) & (P[:, 2] == 0)
            return P[ok][np.argmin(S[ok] @ w + self.reg[ok])]
        if kind == "independent":
            p = np.zeros(3)
            for j, joint in enumerate(("hip", "knee", "ankle")):
                ok = np.all(np.delete(P, j, 1) == 0, axis=1)          # only this joint moves
                W = 1.0 / (V_M - min(V[_idx(CROSSES[joint])].max(), V_M - 1e-3)) ** 2
                cost = W * S[ok][:, _idx(UNI[joint])].sum(1) + self.reg[ok]
                p[j] = P[ok][np.argmin(cost), j]
            return p * min(1.0, BUDGET / max(p.sum(), 1e-12))
        raise ValueError(kind)


def run(allocator, amap, kind, C, cycle_s, minutes=MINUTES, replan=10):
    """Walk for `minutes` under one controller. Returns per-cycle V (n, 9) and p (n, 3)."""
    V, Vs, ps = np.zeros(len(MUSCLES)), [], []
    n_cycles = int(minutes * 60 / cycle_s)
    while len(Vs) < n_cycles:
        p = allocator(kind, V)
        A, B = cycle_map(amap(p), cycle_s, C)
        for _ in range(min(replan, n_cycles - len(Vs))):
            V = A * V + B
            Vs.append(V)
            ps.append(p)
    return np.array(Vs), np.array(ps)


def metrics(Vs, cycle_s):
    """peak_V: worst muscle at the end (min-max objective). t_th: minutes to V_TH, inf if never."""
    hit = np.flatnonzero(Vs.max(1) >= V_TH)
    return {"peak_V": float(Vs[-1].max()),
            "worst": MUSCLES[int(Vs[-1].argmax())],
            "t_th_min": float((hit[0] + 1) * cycle_s / 60) if hit.size else np.inf}


def compare(amap, cycle_s, C=C_ZHANG, minutes=MINUTES):
    alloc = Allocator(amap)
    out = {}
    for kind in CONTROLLERS:
        Vs, ps = run(alloc, amap, kind, C, cycle_s, minutes)
        out[kind] = {**metrics(Vs, cycle_s), "mean_p": ps.mean(0), "V": Vs}
    return out


def table(res):
    print(f"{'controller':<14}{'peak V':>8}{'vs none':>9}{'worst muscle':>14}"
          f"{'t to V_th':>11}   mean p (hip knee ankle)")
    for k, r in res.items():
        t = "never" if np.isinf(r["t_th_min"]) else f"{r['t_th_min']:.1f} min"
        print(f"{k:<14}{r['peak_V']:>8.3f}{r['peak_V'] / res['none']['peak_V'] - 1:>+9.0%}"
              f"{r['worst']:>14}{t:>11}   {np.array2string(r['mean_p'], precision=2)}")


def _toy_amap():
    """Hand-built activation map with biarticular coupling, for the self-check only.

    Each joint's assistance unloads the muscles crossing it; biarticular muscles
    are unloaded by either joint they cross.
    """
    phase = np.linspace(0, 2 * np.pi, 100, endpoint=False)
    base = np.array([0.25, 0.15, 0.2, 0.2, 0.3, 0.35, 0.3, 0.3, 0.15])
    shape = 0.5 * (1 + np.sin(phase[:, None] + np.arange(9)[None, :]))
    cross = np.array([[m in CROSSES[j] for j in ("hip", "knee", "ankle")] for m in MUSCLES], float)
    cross /= cross.sum(1, keepdims=True)

    def amap(p):
        return base * (1.0 - cross @ np.asarray(p)) * shape
    return amap


if __name__ == "__main__":
    _check_cycle_map()
    res = compare(_toy_amap(), cycle_s=1.0, minutes=5.0)
    print("toy plant (hand-built coupling, NOT the twin)\n")
    table(res)

    e = {k: r["peak_V"] for k, r in res.items()}
    assert all(e[k] < e["none"] for k in CONTROLLERS[1:]), "assistance must lower peak fatigue"
    assert e["coupled"] <= min(e.values()) + 1e-9, "fatigue-aware coupled must win"
    print("\nOK on the toy plant: every assisted controller beats none, coupled wins.")
    print("   Real numbers come from the twin: python src/allocation/run_phase_c.py")

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
from a candidate grid (+ LAM * |p|^2 effort penalty, same for all), and the
controllers differ only in what they know:

  none          p = 0
  knee_only     Zhang-style single joint: min sum_i w_i mean(a_i^2), w_i = 1/(V_m-V_i)^2
                (their eq. 27 made per-muscle), hip/ankle fixed at 0
  independent   one controller per joint, each sees a SCALAR joint fatigue index
                (max V of muscles crossing it, as Zhang do) and only its own
                uniarticular muscles -- blind to biarticular cross-effects
  blind         multi-joint, min sum_i mean(a_i^2): allocates for effort, ignores fatigue
  coupled       ours: min over p of the worst muscle's PREDICTED fatigue HORIZON
                cycles ahead, from the current per-muscle state, through the
                exact cycle map. Sees every muscle, including the biarticular
                ones, and optimises the reported objective itself.

ABLATIONS -- what is the win made of? `coupled` differs from each baseline in
more than one way (objective, joint coupling, fatigue feedback). Each ablation
changes ONE of them, so the margin can be attributed (review 2026-10-07):

  independent_minmax  independent's per-joint split and information, coupled's
                      min-max objective                  -> isolates the OBJECTIVE
  local               coupled, but planned on an ANATOMICALLY LOCAL model: each
                      muscle responds only to assistance at joints it crosses
                      (knee assistance cannot move soleus) -> isolates the
                      cross-joint redistribution a per-joint view misses
  static              coupled's objective at steady state, V* = B/(1-A), solved
                      once and never updated              -> isolates the fatigue
                      FEEDBACK. On the pre-review twin it matched coupled exactly:
                      in steady walking the fatigue state changed no decision.

The first version of `coupled` minimised the weighted sum of squares above
(the knee_only cost on all three joints). On the twin it tied with blind and
lost to independent (0.211 vs 0.204), because a weighted sum of squares is
not the min-max objective being reported. The steady state is available in
closed form (V* = B / (1 - A)), and the min-max optimum reached 0.186.

ponytail: grid search over p, not a gradient solver. 3 dims, cheap, exact on
the grid. Swap for CasADi through the smoothed model if the action space grows.
"""

import sys
from functools import cached_property
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
ABLATIONS = ("independent_minmax", "local", "static")
HORIZON = 60   # cycles of look-ahead for `coupled`, ~1 min: about one fatigue time
               # constant (C/M ~ 8/0.1 s). ponytail: fixed; tune if it matters.


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

    def __init__(self, amap, cycle_s, C=C_ZHANG, P=None):
        self.P = candidates() if P is None else P
        self.amap, self.cycle_s, self.C = amap, cycle_s, C
        acts = [amap(p) for p in self.P]
        self.S = np.array([np.mean(a ** 2, axis=0) for a in acts])           # (n_cand, 9)
        self.A, self.B = map(np.array, zip(*(cycle_map(a, cycle_s, C) for a in acts)))
        self.AH, self.BH = self._horizon(self.A, self.B)                      # V_H = AH*V + BH
        self.reg = LAM * (self.P ** 2).sum(1)

    @staticmethod
    def _horizon(A, B):
        AH = A ** HORIZON
        return AH, B * (1 - AH) / (1 - A)

    @cached_property
    def local(self):
        """(AH, BH) of the anatomically local model: muscle i sees only the joints it
        crosses, p masked to those. Lazy: only the `local` ablation pays for it."""
        mask = np.array([[m in CROSSES[j] for j in ("hip", "knee", "ankle")] for m in MUSCLES])
        A, B = np.empty_like(self.A), np.empty_like(self.B)
        for msk in np.unique(mask, axis=0):
            cols = np.flatnonzero((mask == msk).all(1))
            for n, p in enumerate(self.P):
                a, b = cycle_map(self.amap(p * msk), self.cycle_s, self.C)
                A[n, cols], B[n, cols] = a[cols], b[cols]
        return self._horizon(A, B)

    def __call__(self, kind, V):
        P, S = self.P, self.S
        if kind == "none":
            return np.zeros(3)
        if kind == "blind":
            return P[np.argmin(S.sum(1) + self.reg)]
        if kind == "coupled":
            return P[np.argmin((self.AH * V + self.BH).max(1) + self.reg)]
        if kind == "local":
            AH, BH = self.local
            return P[np.argmin((AH * V + BH).max(1) + self.reg)]
        if kind == "static":
            return P[np.argmin((self.B / (1 - self.A)).max(1) + self.reg)]
        if kind == "independent_minmax":
            return self._per_joint(lambda ok, uni, joint:
                                   (self.AH[ok][:, uni] * V[uni] + self.BH[ok][:, uni]).max(1))
        w = 1.0 / (V_M - np.minimum(V, V_M - 1e-3)) ** 2
        if kind == "knee_only":
            ok = (P[:, 0] == 0) & (P[:, 2] == 0)
            return P[ok][np.argmin(S[ok] @ w + self.reg[ok])]
        if kind == "independent":
            def effort(ok, uni, joint):
                W = 1.0 / (V_M - min(V[_idx(CROSSES[joint])].max(), V_M - 1e-3)) ** 2
                return W * S[ok][:, uni].sum(1)
            return self._per_joint(effort)
        raise ValueError(kind)

    def _per_joint(self, cost):
        """One controller per joint: each moves only its own joint, sees only its own
        uniarticular muscles, minimises cost(ok, uni, joint) + effort penalty; then the
        shared budget scales them down together."""
        p = np.zeros(3)
        for j, joint in enumerate(("hip", "knee", "ankle")):
            ok = np.all(np.delete(self.P, j, 1) == 0, axis=1)          # only this joint moves
            p[j] = self.P[ok][np.argmin(cost(ok, _idx(UNI[joint]), joint) + self.reg[ok]), j]
        return p * min(1.0, BUDGET / max(p.sum(), 1e-12))


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


def compare(amap, cycle_s, C=C_ZHANG, minutes=MINUTES, kinds=CONTROLLERS):
    alloc = Allocator(amap, cycle_s, C)
    out = {}
    for kind in kinds:
        Vs, ps = run(alloc, amap, kind, C, cycle_s, minutes)
        out[kind] = {**metrics(Vs, cycle_s), "mean_p": ps.mean(0), "final_p": ps[-1], "V": Vs}
    return out


def table(res):
    print(f"{'controller':<19}{'peak V':>8}{'vs none':>9}{'worst muscle':>14}"
          f"{'t to V_th':>11}   mean p (hip knee ankle)")
    for k, r in res.items():
        t = "never" if np.isinf(r["t_th_min"]) else f"{r['t_th_min']:.1f} min"
        print(f"{k:<19}{r['peak_V']:>8.3f}{r['peak_V'] / res['none']['peak_V'] - 1:>+9.0%}"
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
    res = compare(_toy_amap(), cycle_s=1.0, minutes=5.0, kinds=CONTROLLERS + ABLATIONS)
    print("toy plant (hand-built coupling, NOT the twin)\n")
    table(res)

    e = {k: r["peak_V"] for k, r in res.items()}
    assert all(e[k] < e["none"] for k in CONTROLLERS[1:] + ABLATIONS), "assistance must lower peak fatigue"
    assert e["coupled"] <= min(e[k] for k in CONTROLLERS) + 1e-9, "fatigue-aware coupled must win"
    # toy coupling is anatomically local by construction (cross-joint effects only through
    # muscles that span both joints), so the local model IS the plant: same choice
    assert abs(e["local"] - e["coupled"]) < 1e-9, "local model must equal the plant on the toy"
    print("\nOK on the toy plant: every assisted controller beats none, coupled wins.")
    print("   Real numbers come from the twin: python src/allocation/run_phase_c.py")

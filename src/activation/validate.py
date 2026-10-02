"""D4: validate the policy against the twin, on subjects it never saw.

The policy was trained inside the surrogate. Here the SAME walks are replayed
with the real twin (MocoInverse) as the plant, for held-out subjects:

    benefit retention   (none - ctrl) under the twin / (none - ctrl) under the surrogate.
                        ~1 = the benefit is real. << 1 = the policy exploited
                        surrogate error -- the failure mode this check exists for.
    surrogate error     rmse between surrogate and twin activations at the
                        actions the policy actually took (on-policy, not a test set)
    disagreement        how often the policy ran where the ensemble disagreed
    latency             policy decision vs one twin evaluation -- the headline ratio

Needs OpenSim AND torch/stable-baselines3 in one env (docs/RUN_ON_DGX.md).

    python src/activation/validate.py results/surrogate_d1_tier1.pt results/policy_surrogate_d1_tier1.zip \
           --workers 32
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
for d in ("activation", "allocation", "musculoskeletal"):
    sys.path.insert(0, str(ROOT / "src" / d))

P_ROUND = 0.05            # twin calls are cached on p rounded to this
CONTROLLERS = ("none", "coupled", "rl_policy")
HIGH_SD = 0.02            # "high disagreement" threshold on mean ensemble sd


def _setup(sur_path, pol_path):
    from stable_baselines3 import SAC
    from surrogate import Surrogate
    model, meta = Surrogate.load(sur_path)
    data = np.load(ROOT / meta["data"]) if not Path(meta["data"]).is_absolute() else np.load(meta["data"])
    ranges = yaml.safe_load(str(data["config"]))["ranges"]
    return model, meta, data, ranges, SAC.load(pol_path, device="cpu")


def _episode(args):
    """One walk, one controller, one held-out subject -- twin plant and surrogate plant."""
    sur_path, pol_path, subject, ctrl, seed, minutes = args
    import twin
    from policy import WalkEnv, allocator_act, policy_act, episode
    model, _, _, ranges, sac = _setup(sur_path, pol_path)
    act = policy_act(sac) if ctrl == "rl_policy" else allocator_act(ctrl)

    class TwinEnv(WalkEnv):
        cache, log = {}, []

        def plant(self, p):
            p = np.round(np.asarray(p) / P_ROUND) * P_ROUND
            key = (tuple(np.round(self.cond, 6)), tuple(p))
            if key not in self.cache:
                r = twin.activations(twin.Subject(*map(float, self.subj)),
                                     twin.Condition(*map(float, self.cond)), p)
                self.cache[key] = r
            r = self.cache[key]
            mu, sd = WalkEnv.plant(self, p)
            self.log.append((float(np.sqrt(((mu - r["acts"]) ** 2).mean())), sd, r["solve_s"], r["success"]))
            return r["acts"], sd

    kw = dict(minutes=minutes, random_start=False)
    sur = episode(WalkEnv(model, [subject], ranges, **kw), act, subject, seed)
    tenv = TwinEnv(model, [subject], ranges, **kw)
    tw = episode(tenv, act, subject, seed)
    err, sd, solve, ok = map(np.array, zip(*tenv.log))
    return {"subject": subject.tolist(), "controller": ctrl, "seed": seed,
            "twin_mean_peak_V": tw["mean_peak_V"], "sur_mean_peak_V": sur["mean_peak_V"],
            "act_rmse": float(err.mean()), "frac_high_sd": float((sd > HIGH_SD).mean()),
            "twin_solves": len(tenv.cache), "solve_s": float(np.median(solve)),
            "all_converged": bool(ok.all())}


def latency(sac, model, subject, cond):
    from policy import WalkEnv
    obs = np.zeros(14, np.float32)
    tic = time.perf_counter()
    for _ in range(1000):
        WalkEnv.to_p(sac.predict(obs, deterministic=True)[0])
    return (time.perf_counter() - tic) / 1000


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("surrogate")
    ap.add_argument("policy")
    ap.add_argument("--subjects", type=int, default=None, help="limit held-out subjects")
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()

    model, meta, data, ranges, sac = _setup(a.surrogate, a.policy)
    sid, xs = data["subject_id"], data["x_subject"]
    test = [xs[sid == i][0] for i in meta["test_subjects"]][: a.subjects]
    jobs = [(a.surrogate, a.policy, s, c, seed, a.minutes)
            for s in test for c in CONTROLLERS for seed in range(a.seeds)]
    print(f"D4: {len(test)} held-out subjects x {len(CONTROLLERS)} controllers x {a.seeds} seeds "
          f"= {len(jobs)} closed-loop walks against the twin, {a.workers} workers", flush=True)

    if a.workers > 1:
        import multiprocessing as mp
        import os
        os.environ["OPENSIM_MOCO_PARALLEL"] = "1"
        with mp.get_context("spawn").Pool(a.workers) as pool:
            rows = pool.map(_episode, jobs)
    else:
        rows = [_episode(j) for j in jobs]

    by = {c: [r for r in rows if r["controller"] == c] for c in CONTROLLERS}
    none_t = np.mean([r["twin_mean_peak_V"] for r in by["none"]])
    none_s = np.mean([r["sur_mean_peak_V"] for r in by["none"]])
    print(f"\n{'controller':<12}{'worst V twin':>13}{'worst V sur':>12}{'retention':>11}"
          f"{'act rmse':>10}{'high-sd':>9}{'solves':>8}")
    summary = {}
    for c, rs in by.items():
        t = np.mean([r["twin_mean_peak_V"] for r in rs])
        s = np.mean([r["sur_mean_peak_V"] for r in rs])
        ret = (none_t - t) / (none_s - s) if c != "none" and abs(none_s - s) > 1e-9 else np.nan
        summary[c] = {"twin": t, "surrogate": s, "retention": ret,
                      "act_rmse": np.mean([r["act_rmse"] for r in rs]),
                      "frac_high_sd": np.mean([r["frac_high_sd"] for r in rs])}
        print(f"{c:<12}{t:>13.3f}{s:>12.3f}{ret:>11.2f}{summary[c]['act_rmse']:>10.4f}"
              f"{summary[c]['frac_high_sd']:>9.0%}{sum(r['twin_solves'] for r in rs):>8d}")

    lat = latency(sac, model, test[0], None)
    solve = np.median([r["solve_s"] for r in rows])
    print(f"\nlatency: policy {lat * 1e3:.2f} ms per decision vs twin {solve:.1f} s per evaluation "
          f"-> {solve / lat:,.0f}x faster")
    if not all(r["all_converged"] for r in rows):
        print("WARNING: some twin solves did not converge -- treat those walks with suspicion")
    out = ROOT / "results" / "d4_validation.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows, "policy_latency_s": lat,
                               "twin_solve_s": solve}, indent=2, default=float))
    print(f"-> {out.relative_to(ROOT)}")

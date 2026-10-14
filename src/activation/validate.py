"""D4: validate the policy against the twin, on subjects it never saw.

The policy was trained inside the surrogate. Here the SAME walks are replayed
with the real twin (MocoInverse) as the plant, for held-out subjects:

    benefit retention   (none - ctrl) under the twin / (none - ctrl) under the surrogate.
                        ~1 = the benefit is real. << 1 = the policy exploited
                        surrogate error -- the failure mode this check exists for.
    surrogate error     rmse between surrogate and twin activations at the
                        actions the policy actually took (on-policy, not a test set)
    disagreement        how often the policy ran where the ensemble disagreed
    rank agreement      do twin and surrogate order the controllers the same way?
                        Retention vs "none" cannot see a flip between two assisted
                        controllers; in the pre-review smoke run the surrogate put
                        coupled ahead of the policy and the twin the reverse.
    latency             policy decision vs one twin evaluation -- the headline ratio

Controllers and policy observe V_est (the fatigue model over the SURROGATE's
activations), never the twin's true V: the twin carries the subject's hidden
parameters, and a real device cannot measure fatigue. Scores use the true V.
Both the mean over the walk (the policy's training reward) and the end-of-walk
value (Phase C's metric) are reported, since the policy optimises the first and
`coupled` a 60-cycle look-ahead closer to the second.

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
    sur_path, pol_path, subject, hidden, ctrl, seed, minutes = args
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
                # the twin gets the subject's hidden (randomised) parameters; the policy never saw them
                r = twin.activations(twin.Subject(*map(float, self.subj), *map(float, hidden)),
                                     twin.Condition(*map(float, self.cond)), p)
                self.cache[key] = r
            r = self.cache[key]
            mu, sd = self.predict(p)
            self.log.append((float(np.sqrt(((mu - r["acts"]) ** 2).mean())), sd, r["solve_s"], r["success"]))
            return r["acts"], mu, sd       # truth from the twin, estimate from the surrogate

    kw = dict(minutes=minutes, random_start=False)
    sur = episode(WalkEnv(model, [subject], ranges, **kw), act, subject, seed)
    tenv = TwinEnv(model, [subject], ranges, **kw)
    tw = episode(tenv, act, subject, seed)
    err, sd, solve, ok = map(np.array, zip(*tenv.log))
    return {"subject": subject.tolist(), "hidden": [float(x) for x in hidden], "controller": ctrl, "seed": seed,
            "twin_mean_peak_V": tw["mean_peak_V"], "sur_mean_peak_V": sur["mean_peak_V"],
            "twin_final_peak_V": tw["final_peak_V"], "sur_final_peak_V": sur["final_peak_V"],
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
    trained = Path(a.policy).with_suffix(".json")
    if trained.exists() and json.loads(trained.read_text())["minutes"] != a.minutes:
        print(f"WARNING: policy trained on {json.loads(trained.read_text())['minutes']}-minute walks, "
              f"replayed on {a.minutes}: its elapsed-time input is out of distribution", flush=True)
    sid, xs = data["subject_id"], data["x_subject"]
    xh = data["x_hidden"] if "x_hidden" in data else np.ones((len(sid), 3))   # sweeps before randomisation
    test = [xs[sid == i][0] for i in meta["test_subjects"]][: a.subjects]
    hid = [xh[sid == i][0] for i in meta["test_subjects"]][: a.subjects]
    jobs = [(a.surrogate, a.policy, s, h, c, seed, a.minutes)
            for s, h in zip(test, hid) for c in CONTROLLERS for seed in range(a.seeds)]
    print(f"D4: {len(test)} held-out subjects x {len(CONTROLLERS)} controllers x {a.seeds} seeds "
          f"= {len(jobs)} closed-loop walks against the twin, {a.workers} workers", flush=True)

    if a.workers > 1:
        import multiprocessing as mp
        import os
        os.environ["OPENSIM_MOCO_PARALLEL"] = "1"
        # and one BLAS thread: with only the line above, a laptop worker still ran 17 threads
        # on ~2.3 cores (2026-10-07). Children inherit this env at spawn.
        os.environ["OPENBLAS_NUM_THREADS"] = os.environ["OMP_NUM_THREADS"] = "1"
        with mp.get_context("spawn").Pool(a.workers) as pool:
            rows = pool.map(_episode, jobs)
    else:
        rows = [_episode(j) for j in jobs]

    by = {c: [r for r in rows if r["controller"] == c] for c in CONTROLLERS}
    none_t = np.mean([r["twin_mean_peak_V"] for r in by["none"]])
    none_s = np.mean([r["sur_mean_peak_V"] for r in by["none"]])
    print(f"\n{'controller':<12}{'worst V twin':>13}{'worst V sur':>12}{'final twin':>11}{'final sur':>10}"
          f"{'retention':>11}{'act rmse':>10}{'high-sd':>9}{'solves':>8}")
    summary = {}
    for c, rs in by.items():
        t = np.mean([r["twin_mean_peak_V"] for r in rs])
        s = np.mean([r["sur_mean_peak_V"] for r in rs])
        ret = (none_t - t) / (none_s - s) if c != "none" and abs(none_s - s) > 1e-9 else np.nan
        summary[c] = {"twin": t, "surrogate": s, "retention": ret,
                      "twin_final": np.mean([r["twin_final_peak_V"] for r in rs]),
                      "surrogate_final": np.mean([r["sur_final_peak_V"] for r in rs]),
                      "act_rmse": np.mean([r["act_rmse"] for r in rs]),
                      "frac_high_sd": np.mean([r["frac_high_sd"] for r in rs])}
        print(f"{c:<12}{t:>13.3f}{s:>12.3f}{summary[c]['twin_final']:>11.3f}{summary[c]['surrogate_final']:>10.3f}"
              f"{ret:>11.2f}{summary[c]['act_rmse']:>10.4f}"
              f"{summary[c]['frac_high_sd']:>9.0%}{sum(r['twin_solves'] for r in rs):>8d}")

    # the ordering is the claim, so check the twin and the surrogate agree on it
    order = {k: sorted(CONTROLLERS, key=lambda c: summary[c][k]) for k in ("twin", "surrogate")}
    gap = {k: summary["rl_policy"][k] - summary["coupled"][k] for k in ("twin", "surrogate")}
    summary["ranking"] = {**order, "agree": order["twin"] == order["surrogate"], "policy_minus_coupled": gap}
    print(f"\nranking, best first -- twin: {order['twin']}   surrogate: {order['surrogate']}")
    print(f"policy - coupled worst V: twin {gap['twin']:+.3f}, surrogate {gap['surrogate']:+.3f}")
    if not summary["ranking"]["agree"]:
        print("WARNING: twin and surrogate rank the controllers differently -- the policy's standing "
              "against coupled is not something the surrogate predicted")

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

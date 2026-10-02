"""D3: long-horizon fatigue-management policy, trained inside the surrogate.

Environment (one step = one replan = REPLAN gait cycles, ~10 s of walking):
    observation  subject params, current condition (speed, load), per-muscle
                 fatigue V (9), elapsed fraction of the walk
    action       assistance fraction at hip, knee, ankle; mapped to [0, P_MAX]
                 and scaled down onto the SAME budget Phase C's controllers get
    plant        acts = surrogate ensemble mean; V integrated over the cycles
                 with the exact smoothed fatigue model (src/allocation/allocate.py)
    reward       -max_i V_i                 the min-max fatigue objective (Phase C)
                 - LAM * |p|^2              same effort penalty as Phase C
                 - BETA * ensemble std      stay where the surrogate is trustworthy
    disturbance  walking speed and load change at random mid-walk -- the
                 long-horizon part: the policy must manage fatigue built up
                 under one condition while walking under the next

Model-exploitation mitigations (guide D3, all three mandatory):
  1. ensemble disagreement penalty (BETA) -- here
  2. short rollouts branched from real states: episodes start from TRAINING
     subjects of the D1 dataset with a random initial fatigue state, and last
     minutes, not hours
  3. ground-truth validation against the twin -- src/activation/validate.py

    python src/activation/policy.py                       self-check: toy surrogate, short training
    python src/activation/policy.py results/surrogate_d1_tier1.pt --steps 300000
"""

import argparse
import sys
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "allocation"))
sys.path.insert(0, str(ROOT / "src" / "activation"))
import allocate as al  # noqa: E402
from surrogate import Surrogate, cycle_s  # noqa: E402

REPLAN = 10            # gait cycles per decision, same as Phase C
MINUTES = 10.0
BETA = 10.0            # disagreement penalty: sd ~0.01 costs ~0.1, comparable to V
SWITCH_PROB = 0.05     # per step: ~3 condition changes in a 10-minute walk


class WalkEnv(gym.Env):
    def __init__(self, model, subjects, ranges, minutes=MINUTES, C=al.C_ZHANG,
                 random_start=True, seed=0):
        self.model, self.subjects, self.C = model, np.asarray(subjects, np.float32), C
        self.lo = np.array([ranges[k][0] for k in ("mass_scale", "strength_scale", "speed_scale", "load_kg")])
        self.hi = np.array([ranges[k][1] for k in ("mass_scale", "strength_scale", "speed_scale", "load_kg")])
        self.minutes, self.random_start = minutes, random_start
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, (14,), np.float32)
        self.action_space = gym.spaces.Box(-1.0, 1.0, (3,), np.float32)
        self.rng = np.random.default_rng(seed)

    def _cond(self):
        return self.rng.uniform(self.lo[2:], self.hi[2:])

    def _obs(self):
        x = (np.concatenate([self.subj, self.cond]) - self.lo) / (self.hi - self.lo) * 2 - 1
        return np.concatenate([x, self.V, [self.t / self.n_steps]]).astype(np.float32)

    def reset(self, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        o = options or {}
        self.subj = np.asarray(o.get("subject", self.subjects[self.rng.integers(len(self.subjects))]))
        self.cond = self._cond()
        self.V = self.rng.uniform(0, 0.5, 9) if self.random_start and not o else np.zeros(9)
        self.n_steps = int(self.minutes * 60 / (REPLAN * cycle_s(self.cond[0])))
        self.t, self.peaks = 0, []
        return self._obs(), {}

    @staticmethod
    def to_p(a):
        p = (np.clip(a, -1, 1) + 1) / 2 * al.P_MAX
        return p * min(1.0, al.BUDGET / max(p.sum(), 1e-12))

    @torch.no_grad()
    def plant(self, p):
        x = torch.tensor([*self.subj, *self.cond, *p], dtype=torch.float32, device=self.model.x_mean.device)
        mu, sd = self.model(x)
        return mu.cpu().numpy(), float(sd.mean())

    def step(self, a, p=None):
        p = self.to_p(a) if p is None else np.asarray(p)
        acts, sd = self.plant(p)
        self.V = al.cycle(self.V, acts, float(cycle_s(self.cond[0])), self.C, n=REPLAN)
        self.t += 1
        self.peaks.append(self.V.max())
        r = -self.V.max() - al.LAM * float(p @ p) - BETA * sd
        if self.rng.random() < SWITCH_PROB:
            self.cond = self._cond()
        info = {"p": p, "sd": sd, "peak_V": self.V.max()}
        return self._obs(), r, False, self.t >= self.n_steps, info


def episode(env, act, subject, seed):
    """One evaluation walk from rest. act(obs, env) -> p. Same seed = same condition sequence."""
    obs, _ = env.reset(seed=seed, options={"subject": subject})
    sds, done = [], False
    while not done:
        obs, _, _, done, info = env.step(None, p=act(obs, env))
        sds.append(info["sd"])
    return {"mean_peak_V": float(np.mean(env.peaks)), "final_peak_V": float(env.peaks[-1]),
            "mean_sd": float(np.mean(sds))}


def allocator_act(kind):
    """Phase C controller as an env actor. Re-plans its candidate table when the condition changes."""
    cache = {}

    def act(obs, env):
        key = tuple(np.round(env.cond, 6))
        if key not in cache:
            cache.clear()
            cache[key] = al.Allocator(env.model.amap(env.subj, env.cond))
        return cache[key](kind, env.V)
    return act


def policy_act(sac):
    return lambda obs, env: WalkEnv.to_p(sac.predict(obs, deterministic=True)[0])


def compare(env, sac, subjects, seeds=(0, 1, 2)):
    """Policy vs every Phase C controller, same subjects, same condition sequences."""
    actors = {k: allocator_act(k) for k in al.CONTROLLERS}
    if sac is not None:
        actors["rl_policy"] = policy_act(sac)
    out = {}
    for name, act in actors.items():
        rows = [episode(env, act, s, seed) for s in subjects for seed in seeds]
        out[name] = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
    return out


def table(res):
    base = res["none"]["mean_peak_V"]
    print(f"{'controller':<14}{'mean worst V':>13}{'vs none':>9}{'final worst V':>15}{'ensemble sd':>13}")
    for k, r in res.items():
        print(f"{k:<14}{r['mean_peak_V']:>13.3f}{r['mean_peak_V'] / base - 1:>+9.0%}"
              f"{r['final_peak_V']:>15.3f}{r['mean_sd']:>13.4f}")


def train(env, steps, seed=0, log_dir=None):
    from stable_baselines3 import SAC
    sac = SAC("MlpPolicy", env, seed=seed, verbose=0, device="auto", learning_starts=1000,
              buffer_size=min(steps, 1_000_000),
              policy_kwargs={"net_arch": [256, 256]}, tensorboard_log=log_dir)
    tic = time.time()
    sac.learn(total_timesteps=steps)
    print(f"  trained {steps} steps in {time.time() - tic:.0f} s")
    return sac


def _toy_model():
    """Toy surrogate: the allocation toy plant wrapped as a 1-member Surrogate-like object."""
    amap = al._toy_amap()

    class Toy(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer("x_mean", torch.zeros(7))

        def forward(self, x):
            x = x.cpu().numpy()
            load = x[0] * (1 + x[3] / 75) * x[2] ** 1.5 / x[1]
            return torch.as_tensor(np.clip(amap(x[4:]) * load, 0, 1)), torch.zeros(100, 9)

        def amap(self, s, c):
            return lambda p: self(torch.tensor([*s, *c, *p], dtype=torch.float32))[0].numpy()
    return Toy()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("surrogate", nargs="?")
    ap.add_argument("--steps", type=int, default=300000)
    ap.add_argument("--minutes", type=float, default=MINUTES)
    a = ap.parse_args()

    if a.surrogate is None:
        ranges = {"mass_scale": [0.8, 1.25], "strength_scale": [0.7, 1.3],
                  "speed_scale": [0.8, 1.25], "load_kg": [0, 20]}
        subjects = np.random.default_rng(0).uniform([0.8, 0.7], [1.25, 1.3], (5, 2))
        env = WalkEnv(_toy_model(), subjects, ranges, minutes=3.0)
        sac = train(env, steps=4000)
        res = compare(WalkEnv(_toy_model(), subjects, ranges, minutes=3.0, random_start=False),
                      sac, subjects[:2], seeds=(0,))
        print("toy surrogate, 3-minute walks\n")
        table(res)
        assert res["rl_policy"]["mean_peak_V"] < res["none"]["mean_peak_V"], "policy worse than no assistance"
        print("\nOK: env, SAC training and evaluation run; policy beats no assistance on the toy.")
        print("   (4k steps is a smoke test, not a trained policy -- the DGX run uses 300k+.)")
        sys.exit()

    model, meta = Surrogate.load(a.surrogate)
    data = np.load(meta["data"]) if Path(meta["data"]).is_absolute() else np.load(ROOT / meta["data"])
    ranges = yaml.safe_load(str(data["config"]))["ranges"]
    sid, xs = data["subject_id"], data["x_subject"]
    subj_of = {int(i): xs[sid == i][0] for i in np.unique(sid)}
    train_s = np.array([subj_of[int(i)] for i in meta["train_subjects"]])
    test_s = np.array([subj_of[int(i)] for i in meta["test_subjects"]])

    print(f"surrogate {a.surrogate}: {len(train_s)} train subjects, {len(test_s)} held out")
    sac = train(WalkEnv(model, train_s, ranges, a.minutes), a.steps)
    out = ROOT / "results" / f"policy_{Path(a.surrogate).stem}.zip"
    sac.save(out)
    print(f"  -> {out.relative_to(ROOT)}\n\nHELD-OUT subjects, inside the surrogate (D4 checks the twin):\n")
    table(compare(WalkEnv(model, test_s, ranges, a.minutes, random_start=False), sac, test_s))

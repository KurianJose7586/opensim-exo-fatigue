"""D2: learned surrogate of the twin, as an ensemble.

    (subject, condition, p)  ->  (100, 9) right-leg activations over a gait cycle

Only the MUSCULOSKELETAL map is learned. Fatigue is not: its dynamics are known
in closed form, already differentiable (src/fatigue/model.py, smoothed), and
integrated exactly on top of the surrogate's output. Learning a known ODE would
only add error. So "surrogate of musculoskeletal + fatigue dynamics" (guide, D2)
is delivered as learned-musculoskeletal + exact-fatigue, end-to-end differentiable.

Ensemble of MEMBERS MLPs, each trained on a bootstrap of the training SUBJECTS.
Their disagreement (std) is what D3 penalises and D4 reports.
Split is by subject, never random -- a random split leaks subject identity.

    python src/activation/surrogate.py                         self-check on a toy plant
    python src/activation/surrogate.py results/d1_tier1.npz    train on a sweep, save, report
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
N_PHASE, N_MUSCLES, N_IN = 100, 9, 7
MEMBERS = 5
HALF_CYCLE_S = 0.47008941   # reference kinematics span; cycle = 2 * this / speed_scale
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def cycle_s(speed_scale):
    return 2 * HALF_CYCLE_S / np.asarray(speed_scale)


def _mlp(width=256):
    return nn.Sequential(nn.Linear(N_IN, width), nn.SiLU(), nn.Linear(width, width), nn.SiLU(),
                         nn.Linear(width, width), nn.SiLU(), nn.Linear(width, N_PHASE * N_MUSCLES))


class Surrogate(nn.Module):
    def __init__(self, x_mean, x_std, members=MEMBERS):
        super().__init__()
        self.register_buffer("x_mean", torch.as_tensor(x_mean, dtype=torch.float32))
        self.register_buffer("x_std", torch.as_tensor(x_std, dtype=torch.float32))
        self.nets = nn.ModuleList(_mlp() for _ in range(members))

    def members(self, x):
        """(..., 7) -> (members, ..., 100, 9). Sigmoid keeps activations in (0, 1)."""
        z = (x - self.x_mean) / self.x_std
        return torch.stack([torch.sigmoid(n(z)).unflatten(-1, (N_PHASE, N_MUSCLES))
                            for n in self.nets])

    def forward(self, x):
        y = self.members(x)
        return y.mean(0), y.std(0)

    @torch.no_grad()
    def amap(self, x_subject, x_condition):
        """numpy p -> acts, for src/allocation/allocate.py. Ensemble mean."""
        base = torch.tensor([*x_subject, *x_condition], dtype=torch.float32, device=self.x_mean.device)

        @torch.no_grad()
        def f(p):
            x = torch.cat([base, torch.as_tensor(np.asarray(p), dtype=torch.float32, device=base.device)])
            return self(x)[0].cpu().numpy()
        return f

    def save(self, path, **meta):
        torch.save({"state": self.state_dict(), "members": len(self.nets), **meta}, path)

    @classmethod
    def load(cls, path):
        d = torch.load(path, map_location=DEVICE, weights_only=False)
        m = cls(torch.zeros(N_IN), torch.ones(N_IN), d["members"])
        m.load_state_dict(d["state"])
        return m.to(DEVICE).eval(), d


def dataset(path):
    """Converged twin evaluations from a collected sweep."""
    d = np.load(path)
    ok = d["success"].astype(bool)
    X = np.concatenate([d["x_subject"], d["x_condition"], d["p"]], 1)[ok].astype(np.float32)
    return X, d["acts"][ok].astype(np.float32), d["subject_id"][ok]


def split(subject_id, test_frac=0.2, seed=0):
    ids = np.unique(subject_id)
    rng = np.random.default_rng(seed)
    test = rng.choice(ids, max(1, int(round(test_frac * len(ids)))), replace=False)
    return ~np.isin(subject_id, test), np.isin(subject_id, test)


def train(X, Y, sid, steps=20000, lr=1e-3, batch=256, members=MEMBERS, seed=0, log=print):
    torch.manual_seed(seed)
    model = Surrogate(X.mean(0), X.std(0) + 1e-6, members).to(DEVICE)
    Xt, Yt = torch.as_tensor(X, device=DEVICE), torch.as_tensor(Y, device=DEVICE)
    rng = np.random.default_rng(seed)
    ids = np.unique(sid)
    for k, net in enumerate(model.nets):
        # bootstrap over subjects; with a handful of subjects a bootstrap drops whole
        # subjects and members extrapolate wildly, so all members see all of them
        boot = rng.choice(ids, len(ids), replace=True) if len(ids) >= 10 else ids
        rows = torch.as_tensor(np.concatenate([np.flatnonzero(sid == i) for i in boot]), device=DEVICE)
        opt = torch.optim.Adam(net.parameters(), lr=lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
        for _ in range(steps):                                      # steps, not epochs: dataset
            b = rows[torch.randint(len(rows), (batch,), device=DEVICE)]   # size varies 1000x by tier
            z = (Xt[b] - model.x_mean) / model.x_std
            loss = ((torch.sigmoid(net(z)).unflatten(-1, (N_PHASE, N_MUSCLES)) - Yt[b]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
        log(f"  member {k + 1}/{members}: train mse {loss.item():.2e}")
    return model.eval()


def vstar(acts, speed_scale):
    """Steady-state per-muscle fatigue V* = B / (1 - A) of each sample's gait cycle."""
    sys.path.insert(0, str(ROOT / "src" / "allocation"))
    import allocate as al
    A, B = al.cycle_map(acts, cycle_s(speed_scale)[:, None, None], al.C_ZHANG)
    return B / (1 - A)


@torch.no_grad()
def evaluate(model, X, Y):
    mu, sd = model(torch.as_tensor(X, device=DEVICE))
    mu, sd = mu.cpu().numpy(), sd.cpu().numpy()
    err = mu - Y
    r2 = 1 - (err ** 2).sum() / ((Y - Y.mean(0)) ** 2).sum()
    per_sample_err = np.sqrt((err ** 2).mean((1, 2)))
    per_sample_sd = sd.mean((1, 2))
    calib = np.corrcoef(per_sample_err, per_sample_sd)[0, 1] if len(X) > 2 else np.nan
    # Fatigue switches at M_th = 0.05, where activation errors of a few hundredths flip a
    # sample between fatigue and recovery. Activation rmse alone hides that; the error that
    # reaches the objective is in V*. X[:, 2] is speed_scale (x_subject 2, then condition).
    v_hat, v = vstar(mu, X[:, 2]), vstar(Y, X[:, 2])
    return {"rmse": float(np.sqrt((err ** 2).mean())), "r2": float(r2),
            "rmse_per_muscle": np.sqrt((err ** 2).mean((0, 1))), "sd_mean": float(sd.mean()),
            "err_sd_corr": float(calib),
            "vstar_mae_per_muscle": np.abs(v_hat - v).mean(0),
            "vstar_worst_mae": float(np.abs(v_hat.max(1) - v.max(1)).mean()),
            "vstar_worst_rel": float(np.abs(v_hat.max(1) / v.max(1) - 1).mean())}


def report(name, m):
    print(f"  {name}: rmse {m['rmse']:.4f}  R2 {m['r2']:.3f}  ensemble sd {m['sd_mean']:.4f}  "
          f"corr(error, sd) {m['err_sd_corr']:+.2f}")
    print(f"    steady-state worst-muscle fatigue V*: mean abs error {m['vstar_worst_mae']:.4f} "
          f"({m['vstar_worst_rel']:.1%}) -- compare with the effect sizes being claimed")


def _toy():
    """Toy dataset from the allocation toy plant, with subject and condition effects."""
    sys.path.insert(0, str(ROOT / "src" / "allocation"))
    from allocate import _toy_amap
    amap, rng = _toy_amap(), np.random.default_rng(0)
    X, Y, sid = [], [], []
    for s in range(30):
        subj = rng.uniform([0.8, 0.7], [1.25, 1.3])
        for _ in range(20):
            cond, p = rng.uniform([0.8, 0.0], [1.25, 20.0]), rng.uniform(0, 0.4, 3)
            load = subj[0] * (1 + cond[1] / 75) * cond[0] ** 1.5 / subj[1]
            X.append([*subj, *cond, *p])
            Y.append(np.clip(amap(p) * load, 0, 1))
            sid.append(s)
    return np.array(X, np.float32), np.array(Y, np.float32), np.array(sid)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data", nargs="?")
    ap.add_argument("--steps", type=int, default=None)
    a = ap.parse_args()

    if a.data is None:
        X, Y, sid = _toy()
        tr, te = split(sid)
        model = train(X[tr], Y[tr], sid[tr], steps=a.steps or 3000, members=3)
        m = evaluate(model, X[te], Y[te])
        report("toy, held-out subjects", m)
        assert m["r2"] > 0.95, "surrogate cannot fit the toy plant -- training code is broken"
        print("OK: training code fits the toy plant on held-out subjects.")
        sys.exit()

    X, Y, sid = dataset(a.data)
    tr, te = split(sid)
    print(f"{a.data}: {len(X)} converged samples, {len(np.unique(sid))} subjects "
          f"({len(np.unique(sid[te]))} held out)  device={DEVICE}")
    model = train(X[tr], Y[tr], sid[tr], steps=a.steps or 20000)
    report("train", evaluate(model, X[tr], Y[tr]))
    m = evaluate(model, X[te], Y[te])
    report("HELD-OUT SUBJECTS", m)
    print("  rmse per muscle:", np.array2string(m["rmse_per_muscle"], precision=4))
    print("  V* abs error per muscle:", np.array2string(m["vstar_mae_per_muscle"], precision=4))
    out = ROOT / "results" / f"surrogate_{Path(a.data).stem}.pt"
    model.save(out, data=a.data, test_subjects=np.unique(sid[te]), train_subjects=np.unique(sid[tr]),
               test_metrics={k: v for k, v in m.items() if not k.endswith("per_muscle")})
    print(f"  -> {out.relative_to(ROOT)}")

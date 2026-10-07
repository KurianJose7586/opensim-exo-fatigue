"""Batch twin evaluations: Phase C's assistance grid and D1's population dataset.

One config -> a deterministic task list -> one .npz per task. Built for a job
array from the start (PROJECT_GUIDE sec. 6):

    run      python src/jobs/sweep.py run configs/d1_tier1.yaml --index I --count N --workers W
             handles tasks i with i % N == I, W processes in parallel.
             On Kubernetes an Indexed Job sets JOB_COMPLETION_INDEX; --index defaults to it.
             Resumable: a task with an output (or a failure log) is skipped.
             --retry-failed clears this shard's failure logs first.
    collect  python src/jobs/sweep.py collect configs/d1_tier1.yaml
             merges every task into results/<name>.npz, prints success rate.
    status   python src/jobs/sweep.py status configs/d1_tier1.yaml

Sampling (D1): Latin hypercube, nested so each subject is reused across
conditions and assistance levels -- that is what makes a held-out-BY-SUBJECT
split possible later (D4). Grid mode (Phase C): one nominal subject, full grid.

Every output records the git commit and config that produced it.
Runs in the OpenSim env (Python 3.11 + opensim).
"""

import argparse
import os
import subprocess
import tempfile
import sys
import traceback
from pathlib import Path

import numpy as np
import yaml
from scipy.stats import qmc

ROOT = Path(__file__).resolve().parents[2]
SUBJECT_KEYS = ["mass_scale", "strength_scale"]     # observed: surrogate and policy inputs
CONDITION_KEYS = ["speed_scale", "load_kg"]
# Domain randomisation (twin.Subject): sampled per subject when the config gives a
# range, nominal 1.0 otherwise. Saved as x_hidden, never fed to the surrogate.
HIDDEN_KEYS = ["fiber_length_scale", "exo_capacity_scale", "device_mass_scale"]


def tasks(cfg):
    """Every task as (subject_id, subject dict, condition dict, p[3]). Deterministic in cfg."""
    if "grid_p" in cfg:
        g = cfg["grid_p"]
        P = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
        subj = {k: 1.0 for k in SUBJECT_KEYS}
        cond = {"speed_scale": 1.0, "load_kg": float(cfg.get("load_kg", 0.0))}
        return [(0, subj, cond, p) for p in P]

    r = cfg["ranges"]

    def lhs(n, keys, seed):
        u = qmc.LatinHypercube(d=len(keys), seed=seed).random(n)
        lo = np.array([r[k][0] for k in keys])
        hi = np.array([r[k][1] for k in keys])
        return lo + u * (hi - lo)

    out, seed = [], cfg["seed"]
    s_keys = SUBJECT_KEYS + [k for k in HIDDEN_KEYS if k in r]
    S = lhs(cfg["subjects"], s_keys, seed)
    for s_id, s in enumerate(S):
        C = lhs(cfg["conditions_per_subject"], CONDITION_KEYS, seed + 1000 + s_id)
        for c_id, c in enumerate(C):
            P = lhs(cfg["assist_per_condition"], ["p"] * 3, seed + 10**6 + 1000 * s_id + c_id)
            P[0] = 0.0                      # every condition keeps its unassisted baseline
            for p in P:
                out.append((s_id, dict(zip(s_keys, map(float, s))),
                            dict(zip(CONDITION_KEYS, map(float, c))), p))
    return out


def _out_dir(cfg):
    return ROOT / "results" / cfg["name"]


def _commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _run_one(args):
    i, task, out_dir, cfg_text, commit = args
    # Own working dir per process: Moco drops a delete_this_to_stop_optimization_<time>.txt
    # in the cwd and polls it every iteration; workers sharing a cwd can trip each other.
    wd = Path(tempfile.gettempdir()) / f"opensim_exo_{os.getpid()}"
    wd.mkdir(exist_ok=True)
    os.chdir(wd)
    sys.path.insert(0, str(ROOT / "src" / "musculoskeletal"))
    import twin
    s_id, subj, cond, p = task
    try:
        r = twin.activations(twin.Subject(**subj), twin.Condition(**cond), p)
        tmp = out_dir / f"task_{i:06d}.tmp.npz"
        np.savez_compressed(tmp, subject_id=s_id, x_subject=[subj[k] for k in SUBJECT_KEYS],
                            x_hidden=[subj.get(k, 1.0) for k in HIDDEN_KEYS],
                            x_condition=[cond[k] for k in CONDITION_KEYS],
                            acts=r["acts"].astype(np.float32), p=r["p"], cycle_s=r["cycle_s"],
                            residual_rms=r["residual_rms"], reserve_rms=r["reserve_rms"],
                            solve_s=r["solve_s"], success=r["success"],
                            commit=commit, config=cfg_text)
        os.replace(tmp, out_dir / f"task_{i:06d}.npz")    # atomic: a killed pod leaves no half file
        return i, r["success"], r["solve_s"]
    except Exception:
        (out_dir / f"failed_{i:06d}.txt").write_text(traceback.format_exc())
        return i, False, np.nan


def run(cfg, cfg_text, index, count, workers, retry_failed=False):
    out_dir = _out_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    # resuming skips finished tasks, so outputs from an edited config would silently mix in
    old = next(out_dir.glob("task_*.npz"), None)
    if old is not None and str(np.load(old)["config"]) != cfg_text:
        sys.exit(f"{out_dir} holds results from a different version of {cfg['name']}'s config. "
                 f"Move that folder aside, then rerun.")
    if retry_failed:
        for f in out_dir.glob("failed_*.txt"):
            if int(f.stem.split("_")[1]) % count == index:
                f.unlink()
    todo = [(i, t) for i, t in enumerate(tasks(cfg)) if i % count == index
            and not (out_dir / f"task_{i:06d}.npz").exists()
            and not (out_dir / f"failed_{i:06d}.txt").exists()]
    print(f"[{cfg['name']}] shard {index}/{count}: {len(todo)} tasks to do", flush=True)
    commit = _commit()
    jobs = [(i, t, out_dir, cfg_text, commit) for i, t in todo]
    if workers > 1:
        # one solver thread per process, or W processes x all cores thrash
        os.environ["OPENSIM_MOCO_PARALLEL"] = "1"
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(workers, maxtasksperchild=20) as pool:
            for n, (i, ok, s) in enumerate(pool.imap_unordered(_run_one, jobs), 1):
                print(f"  task {i:6d}  ok={ok}  {s:6.1f} s   ({n}/{len(jobs)})", flush=True)
    else:
        for n, job in enumerate(jobs, 1):
            i, ok, s = _run_one(job)
            print(f"  task {i:6d}  ok={ok}  {s:6.1f} s   ({n}/{len(jobs)})", flush=True)


def collect(cfg):
    out_dir = _out_dir(cfg)
    n_total = len(tasks(cfg))
    files = sorted(out_dir.glob("task_*.npz"))
    failed = sorted(out_dir.glob("failed_*.txt"))
    if not files:
        sys.exit(f"no results in {out_dir}")
    rows = [dict(np.load(f)) for f in files]
    for r in rows:                                  # tasks saved before x_hidden existed
        r.setdefault("x_hidden", np.ones(len(HIDDEN_KEYS)))
    keys = ["subject_id", "x_subject", "x_hidden", "x_condition", "acts", "p", "cycle_s",
            "residual_rms", "reserve_rms", "solve_s", "success"]
    merged = {k: np.stack([r[k] for r in rows]) for k in keys}
    merged["task"] = np.array([int(f.stem.split("_")[1]) for f in files])
    merged["commit"], merged["config"] = rows[0]["commit"], rows[0]["config"]
    np.savez_compressed(ROOT / "results" / f"{cfg['name']}.npz", **merged)
    ok = merged["success"]
    print(f"[{cfg['name']}] {len(files)}/{n_total} done, {len(failed)} crashed, "
          f"{ok.mean():.0%} of done converged")
    print(f"  solve time: median {np.median(merged['solve_s']):.1f} s, "
          f"p90 {np.percentile(merged['solve_s'], 90):.1f} s")
    print(f"  joint reserve rms: median {np.median(merged['reserve_rms']):.2f} Nm  "
          f"(large = muscles could not produce the moment)")
    print(f"  -> results/{cfg['name']}.npz")


def status(cfg):
    out_dir = _out_dir(cfg)
    n = len(tasks(cfg))
    done = len(list(out_dir.glob("task_*.npz"))) if out_dir.exists() else 0
    bad = len(list(out_dir.glob("failed_*.txt"))) if out_dir.exists() else 0
    print(f"[{cfg['name']}] {done}/{n} done, {bad} crashed, {n - done - bad} remaining")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "collect", "status"])
    ap.add_argument("config")
    ap.add_argument("--index", type=int, default=int(os.environ.get("JOB_COMPLETION_INDEX", 0)))
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--retry-failed", action="store_true", help="re-run tasks that crashed before")
    a = ap.parse_args()
    text = Path(a.config).read_text()
    cfg = yaml.safe_load(text)
    if a.cmd == "run":
        run(cfg, text, a.index, a.count, a.workers, a.retry_failed)
    elif a.cmd == "collect":
        collect(cfg)
    else:
        status(cfg)

# Running the project on the DGX

Everything is written and tested on a laptop at small scale. What is left is compute.
This page is the whole job: build one image, run one script, stage by stage.

---

## 0. What you need

- Docker with GPU support (`--gpus all`), or Kubernetes (see §5)
- ~10 GB disk for the image, **< 1 GB for all results** (measured: 6 KB per twin solve,
  so even the 100,000-solve tier is ~0.6 GB)
- The repo cloned somewhere the container can mount

## 1. Build and check (~20 min, once)

```bash
git clone https://github.com/KurianJose7586/opensim-exo-fatigue
cd opensim-exo-fatigue
docker build -f docs/Dockerfile.opensim -t opensim-exo:4.6 .

# alias used below -- mounts the repo, gives the container all CPUs and the GPU
run() { docker run --rm --gpus all -v "$PWD":/work opensim-exo:4.6 "$@"; }

run bash run_pipeline.sh check
```

`check` runs every self-check plus one real OpenSim Moco solve. It must end with
`OK: twin solves, assistance unloads muscles.` **If it fails, stop and send us the log** —
the image has not been built on Linux before (it was developed against the same package
versions on Windows), so this is the step most likely to need a fix.

## 2. Pilot first (~10 min)

```bash
run bash run_pipeline.sh d1 smoke     # 18 solves, prints solve time per task
```

Note the median solve time from the `collect` line. Every estimate below assumes
**~40 s per solve per core** (measured 26 s unassisted / 42 s assisted on the laptop) — replace with this number.

## 3. The real runs, in order

| Stage | Command | Work | At ~40 s/solve, 64 cores | GPU? |
|---|---|---|---|---|
| Phase C | `run bash run_pipeline.sh phase_c` | 125 solves | ~3 min | no |
| D1 | `run bash run_pipeline.sh d1 d1_tier1` | 2,500 solves | ~30 min | no |
| D2 | `run bash run_pipeline.sh d2 d1_tier1` | 5-member ensemble | ~10 min | yes |
| D3 | `run bash run_pipeline.sh d3 d1_tier1` | 300k RL steps | ~1–2 h | optional |
| D4 | `run bash run_pipeline.sh d4 d1_tier1` | ~10 subjects × 3 controllers, closed loop | ~1–2 h | no |

Or all of it: `run bash run_pipeline.sh all d1_tier1`.

**Then scale up** if tier 1 works: replace `d1_tier1` with `d1_tier2` (24,000 solves, ~4 h)
or `d1_tier3` (100,000 solves, ~17 h at 64 cores).

- **Interrupted?** Rerun the same command. Every stage skips work already on disk.
- **Cores:** `WORKERS=100 run bash run_pipeline.sh d1 d1_tier2` to use more of the node.
  One worker = one core; Moco is kept single-threaded per worker on purpose.
- **Long runs:** use `docker run -d` (or `nohup`/`tmux`) so a dropped SSH session does not kill it.

## 4. What to send back

Everything lands in `results/` and `figures/`. Send these (all small):

```
results/phase_c_summary.json      figures/phase_c_fatigue.png
results/d1_tier1.npz              results/surrogate_d1_tier1.pt
results/policy_surrogate_d1_tier1.zip
results/d4_validation.json
```

plus the terminal output of each stage — the printed tables are the results.

## 5. If the DGX is behind Kubernetes

Fill in `<registry>`, the repo path and the node name in `deploy/k8s-d1-sweep.yaml` and
`deploy/k8s-train.yaml`, push the image to the registry, then:

```bash
kubectl apply -f deploy/k8s-d1-sweep.yaml      # D1: 8 CPU-only pods, no GPU held
python src/jobs/sweep.py collect configs/d1_tier1.yaml
kubectl apply -f deploy/k8s-train.yaml         # D2 -> D3 -> D4 on one GPU pod
```

Phase C is small enough to run inside any pod with `bash run_pipeline.sh phase_c`.

---

## What each stage produces, in one line each

- **Phase C** — five controllers sharing one assistance budget on the real twin: does
  coupled, fatigue-aware allocation across hip/knee/ankle beat single-joint and per-joint control?
- **D1** — the population dataset: muscle activations for many virtual subjects, speeds,
  loads and assistance settings.
- **D2** — a neural network that predicts the twin in microseconds instead of a minute,
  tested on subjects it never saw.
- **D3** — an RL policy that manages fatigue over a whole walk, trained inside D2.
- **D4** — the policy replayed against the real twin: does the benefit survive outside the
  network it was trained in?

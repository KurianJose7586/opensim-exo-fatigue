# HPC resource analysis and request

Based on the standard pod spec (`home-directory.yaml`). **Numbers here depend on one measurement we
do not have yet** — the Moco solve time from Gate A. Get that before sending any request.

---

## 1. What the standard allocation grants

```yaml
resources:
  requests/limits:
    cpu:            "8"
    memory:         "16Gi"
    nvidia.com/gpu:  1
image:  nvcr.io/nvidia/pytorch:24.10-py3   (via private registry)
volume: hostPath -> /home/<user>            node-local, not a networked PV
service: NodePort 8888                      Jupyter
```

Kubernetes, not Slurm. That matters — the right batch primitive is an **Indexed Job** with
`parallelism`, not `sbatch --array`.

---

## 2. Feasibility at the standard allocation

D1 (dataset generation) is CPU-bound; Moco does not use the GPU. At 8 cores, throughput is roughly
8 concurrent solves.

| Tier | Solves | @ 90 s | @ 5 min | @ 30 min |
|---|---|---|---|---|
| 1 shakedown | 2,500 | 7.8 h | 26 h | 6.5 days |
| 2 standard | 24,000 | 3.1 days | 10 days | 63 days |
| 3 full | 100,000 | 13 days | 43 days | infeasible |

**Read across the row matching Gate A's measured solve time.** If it lands at 30 min, no amount of
pod-wrangling fixes it — the musculoskeletal model has to be reduced first. Warm-starting from the
nearest solved neighbour typically gives 3–5x and should be assumed in any request.

D2 (surrogate training) and D3 (RL) are GPU work and fit on one GPU. The binding constraint for D2
is **memory**, not compute: 16 GiB is tight for loading 10^4–10^5 trajectories.

---

## 3. Blockers to resolve before requesting anything

### The image does not contain OpenSim

The NGC PyTorch container has PyTorch and CUDA, not OpenSim. Options, in order of preference:

1. **Custom image** layering OpenSim onto the NGC base. Needs push access to `gu-headnode:9443`.
   Cleanest and reproducible. Ask whether users may push images.
2. **Install into the running pod.** OpenSim distributes through conda (`-c opensim-org`). Verify
   this works in that base image — NGC images do not always ship conda.
3. **Split the work:** run D1 elsewhere, use the pod only for D2/D3. Worst option, but it unblocks
   the GPU stages if the image problem drags.

**Resolve this first.** Asking for more compute before knowing you can run the software there is the
wrong order.

### hostPath storage is node-local

`hostPath` binds the data to whichever node the pod lands on. A reschedule may lose visibility of it.
Two questions for the admins:

- Is there a networked persistent volume available instead?
- What is the quota on `/home`? **100k Moco solutions is roughly 25–100 GB** depending on what is
  written per solve. Storage may bind before compute does.

### No visible wall-clock limit

The pod runs `while true; do sleep 3600; done` — a long-running interactive pod, so the spec imposes
no time cap. There is almost certainly a policy one. Ask what it is, because a 3-day D1 run has to
survive it, and design checkpoint/resume accordingly regardless.

---

## 4. The request

**Do not ask for "a bigger pod."** Ask for the right shape per phase. The phases have genuinely
different needs, and the largest ask is also the cheapest to grant.

| Phase | Request | Justification |
|---|---|---|
| **D1** | 4–8 pods, 8 CPU each, **no GPU** | Moco is CPU-only. On the standard spec a GPU sits idle for days. Releasing it back to the pool while taking CPU is a net gain for other users |
| **D2** | 1 GPU + **71 GiB** memory variant | Memory-bound on trajectory loading, not compute-bound |
| **D3** | 1 GPU, standard | Rollouts run in the learned surrogate; modest |

Plus: permission to submit **Indexed Jobs** rather than only long-running pods. That is standard
Kubernetes, it lets the scheduler fit the work around other users instead of pinning resources, and
it makes the sweep restartable.

---

## 5. Draft justification

Adapt and send once Gate A's solve time is known. Fill the bracketed values.

> **Subject: compute request — final year project, musculoskeletal simulation + machine learning**
>
> I am working on a simulation project modelling how a lower-limb exoskeleton should assist someone
> as their muscles fatigue. It has two computational stages with quite different requirements, and I
> wanted to check what is possible before designing around it.
>
> **Stage 1 — dataset generation (CPU only).** I need to run roughly [N] independent musculoskeletal
> optimisation problems, each taking about [T] minutes, covering a range of simulated body types,
> walking speeds and assistance settings. These are completely independent, so they parallelise
> perfectly. The software (OpenSim Moco) is **CPU-only and does not use the GPU at all.**
>
> On the standard pod this would take approximately [X] days while holding a GPU idle throughout.
> Could I instead run this as an Indexed Job across [4-8] **GPU-free** pods of 8 cores? That would
> shorten it to about [Y] days and leave the GPU available to other users for the duration.
>
> **Stage 2 — model training (GPU).** I then train a neural network on those results, and use it for
> reinforcement learning. This does need the GPU, but the constraint is memory rather than compute —
> loading the trajectory dataset exceeds 16 GiB. I understand a 71 GiB variant exists; that would
> cover it. One GPU is sufficient.
>
> **Two practical questions:**
> 1. The provided PyTorch image does not include OpenSim. Can users push a custom image to the
>    registry, or is there a preferred way to add packages?
> 2. What is the storage quota on `/home`? I expect to generate roughly [25-100] GB of intermediate
>    results, and I noticed the volume is a `hostPath` mount — is a networked persistent volume
>    available, or should I plan for the data to stay node-local?
>
> Happy to run a smaller pilot first to give you real numbers rather than my estimates.

**That last line is the strongest part.** Offering a measured pilot before asking for the full
allocation is what separates a credible request from a speculative one — and it costs you a Tier 1
run you were going to do anyway.

---

## 6. What to do first

1. **Gate A** — install OpenSim locally, measure the solve time. Every number above depends on it.
2. **Resolve the image question.** Can you even run OpenSim on their cluster?
3. **Run Tier 1 on the standard pod.** 7.8 hours at 90 s/solve. Gives real throughput numbers.
4. **Then request**, with measurements instead of estimates.

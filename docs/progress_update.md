# Progress update — draft message to project supervisors

They allotted the project, they are working with me, they handle MATLAB and they control the
container images on the DGX. So this is a coordination update, not a request for permission.

---

**Subject: Capstone progress + two things I need on the DGX**

Hi [name],

Update on where things are.

**Working and tested.** I rebuilt the controller from a 2026 IEEE paper on fatigue-aware knee
exoskeletons. My version reproduces their published experiment to within 1.7%, and my muscle fatigue
model matches the original authors' own released code exactly. So the base is checked against real
published results, not just my own assumptions. I can show it running in about ten seconds whenever
you want.

**What I found.** Their method takes a shortcut when predicting how tired a muscle will get — it
makes one assumption at the start and holds it fixed while planning ahead. I measured the cost. At
their settings it is harmless and their results stand. But it limits how far ahead the controller
can plan, and past that limit the error reaches 72% of the maximum help the device can give. That
limit is why this project needs a learning-based approach and not just a bigger version of their
method.

I also went through the literature properly and found two recent papers overlapping one of my
planned contributions, so I dropped that piece and narrowed another. Worth ten minutes to walk
through when you have time.

**Next up** is building the musculoskeletal model in OpenSim. That is the main remaining setup.

**Blockers — one of these stops me completely, the others shape how far I can take it.**

**1. OpenSim is not in our container image. This one is a hard stop.**

The next stage is the musculoskeletal simulation, and it cannot run on the cluster at all until
OpenSim is in an image. I cannot add it myself since image building sits with you.

I have put a draft Dockerfile in the repo at `docs/Dockerfile.opensim`. Two things that should make
it simpler:

- OpenSim and PyTorch never run in the same process. The simulation stage writes result files; the
  training stage reads them later. So separate images are completely fine — they do not need to
  coexist.
- OpenSim needs a specific Python version, so keeping it in its own image avoids disturbing the
  PyTorch setup.

Either building it, or giving me push access to the registry so I can iterate on it myself, would
unblock this. The second is probably less work for you.

**2. Storage quota — I need to know before I start rather than after.**

I expect under 10 GB if I write the results in a compressed format, which I intend to. It could
reach 100 GB only if I ran the full sweep on the detailed model in the simulator's default plain-text
output, and I would convert well before that became an issue.

I mainly want to know the quota so I can size the run to it rather than discover the limit partway
through a multi-day job. The home volume is also mounted from the node rather than networked — if a
networked volume is available, that would be better, since it would survive the pod being
rescheduled.

**3. CPU allocation — not blocking, but it caps what I can produce.**

To be straight about this one: I can run it as things stand. It is a constraint, not a wall.

The simulation stage is thousands of independent jobs and is **CPU-only — it never touches the
GPU.** On the standard 8-core pod it takes days, and holds a GPU idle throughout for no reason. With
32–64 cores and no GPU it drops to hours and hands the GPU back to the pool.

I would also prefer to run it as a batch job rather than a long-lived pod, so it can be scheduled
around other users and restart if it is interrupted.

Whatever is easiest on your side is fine — I mainly wanted to flag that the current shape reserves a
GPU for days doing nothing with it.

On MATLAB — no rush needed yet, but I will need it from the next stage rather than at the end, so
whenever it suits you.

Everything is on GitHub: github.com/KurianJose7586/opensim-exo-fatigue

Thanks,
Kurian

---

## If they ask for a demo

Run in this order — credibility first, contribution second.

```bash
python src/fatigue/calibrate.py   # 0.6 s  predicts a published experiment to 0.6%
python src/mpc/mfac.py            # 1 s    reproduces their controller to 1.7%
python src/fatigue/model.py       # 9 s    the method contribution, exact vs their own code
```

`python src/mpc/periodic.py` is the main finding but takes ~4 minutes. Pre-run it and show the saved
output.

## What the DGX changes

A DGX H200 node has far more CPU than the 8 cores in the standard pod. That moves the simulation
stage from "pick a small sample size" to "the full sweep is realistic":

| Sample size | 8 cores | 32 cores | 64 cores |
|---|---|---|---|
| 2,500 solves | 7.8 h | 2 h | 1 h |
| 24,000 solves | 3.1 days | 19 h | 9 h |
| 100,000 solves | 13 days | 3.3 days | 1.6 days |

All assuming 90 s per solve, which is still **unmeasured**. Get that number from the first OpenSim
run before quoting any of this to them.

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

**Two things I need from you:**

1. **A container image with OpenSim.** The PyTorch image we have does not include it. I have put a
   draft Dockerfile in the repo under `docs/`. Two notes that should make it easier: OpenSim and
   PyTorch never need to run together — the simulation stage writes files, the training stage reads
   them — so separate images or separate environments are fine, whichever is simpler for you. And
   OpenSim needs a specific Python version, so keeping it isolated avoids breaking the PyTorch side.

2. **More CPU for one stage, and I can give the GPU back.** The simulation stage runs thousands of
   independent jobs and is **CPU-only — it never touches the GPU.** On the standard 8-core pod it
   would take days while holding a GPU idle. With 32–64 cores and no GPU it drops to hours, and the
   GPU stays free for everyone else. I would also like to run it as a batch job rather than a
   long-lived pod, so it can be scheduled around other users and restarted if it stops.

One question: what is the storage quota on the home volume? I expect to generate somewhere between
25 and 100 GB of intermediate results, and I noticed it is mounted from the node rather than
networked, so I want to check that before I start rather than after.

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

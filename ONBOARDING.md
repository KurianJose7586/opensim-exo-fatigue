# Onboarding

For someone joining the project. Should take about an hour to get productive.

---

## 1. What this is, in sixty seconds

A powered leg brace (an exoskeleton) pushes on the hip and knee while its wearer walks. How hard
should it push, and when?

We have recordings of 19 people walking in one, on flat ground, ramps and stairs: the ExoGait
Benchmark. From them we do two things.

- **Learn the brace's torque.** AI models predict the torque the brace delivered from the
  wearer's movement: a model per person, and a model for a person it has never seen.
- **Put the same brace on a computer model of a person** with bones and muscles, in OpenSim. The
  model reproduces each recorded walk, which tells us how hard the muscles work. Then we swap the
  torque: switched off, as recorded, as the AI predicts it, or chosen by an optimiser.

The question at the end is whether a better-shaped torque, costing the motors no more, would
leave the muscles less to do. In simulation, so far, it does.

**Current state:** [`README.md`](README.md) has the status table. The plan is the mentor's brief of
2026-10-14; [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) is the map of it.

---

## 2. Set up (20 minutes)

Python only: there is no MATLAB in this project (no licence; `notes/decisions.md`, 2026-10-28).
One environment on every machine, the micromamba env `opensim`:

```bash
git clone https://github.com/KurianJose7586/opensim-exo-fatigue
```

```bash
micromamba create -n opensim -c opensim-org -c conda-forge python=3.11 opensim=4.6 "libblas=*=*openblas" numpy scipy pandas pyyaml matplotlib scikit-learn
```

```bash
micromamba run -n opensim python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
```

With an NVIDIA GPU use `.../whl/cu126` instead of `.../whl/cpu`. Then download the 19 CSVs by
hand from [Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.70rxwdc6j) into
`data/raw/exogait/` (5.5 GB; the site blocks scripted downloads), and check it works:

```bash
micromamba run -n opensim python -u src/exogait/checks.py AB68
```

```bash
micromamba run -n opensim python -u src/exogait/preprocess.py AB68 HL03
```

### Gotchas we have already hit

- **Use OpenBLAS, never MKL**: MKL breaks OpenSim's solver (IPOPT). The `libblas` pin above does it.
- **Never conda-install casadi** into this env: Moco bundles its own.
- **Run through `micromamba run`** (or an activated shell), or the solver plugins are not found.
- **torch and opensim stay in separate processes.** The files that import one never import the other.
- **No dropout in the LSTM**: with it, the GPU library crashes Python on exit on Windows.
- **Background runs look like they produce nothing**: Python buffers. Use `python -u`.
- **Use `python -m pip`, not bare `pip`.**
- The parked pipeline (§4) has its own `requirements.txt` and a plain venv. You do not need it.

---

## 3. Read in this order

| # | File | Why |
|---|---|---|
| 1 | [`README.md`](README.md) | Status, layout, how to run each step |
| 2 | [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) | The plan, what each objective and hypothesis is, the limits |
| 3 | [`docs/KURIAN_TASKS.md`](docs/KURIAN_TASKS.md), [`docs/JASITH_TASKS.md`](docs/JASITH_TASKS.md) | The tasks in detail, the file formats, the shared rules |
| 4 | [`docs/model_inputs.md`](docs/model_inputs.md) | What a torque model may see: read before touching a model |
| 5 | [`notes/observations.md`](notes/observations.md), from "ExoGait plan" | Every number and how far to trust it |
| 6 | [`notes/decisions.md`](notes/decisions.md), from "ExoGait plan" | Why things are the way they are, including reversals |
| 7 | [`notes/papers.md`](notes/papers.md) | Every paper, each explained in plain English |

[`docs/guide_v3_fatigue_twin.md`](docs/guide_v3_fatigue_twin.md) and
[`docs/guide_v2_extension_framing.md`](docs/guide_v2_extension_framing.md) are **archived plans**: do
not work from them.

---

## 4. What exists and what it does

```
src/exogait/checks.py       facts about the raw files that everything else relies on
src/exogait/preprocess.py   raw recordings -> strides on 101 points, with an exclusion log
src/exogait/split.py        train / validation / test, by whole passes, with a leakage check
src/exogait/evaluate.py     every torque model, fitted and scored the same way
src/exogait/lstm.py         the neural network among them
src/exogait/stats.py        the hypothesis tests and their figures
src/exogait/x2model.py      the computer model of a person wearing the brace
src/exogait/track.py        one simulation: reproduce a recorded stride
src/exogait/assist.py       the same stride with different brace torques, compared
src/exogait/animate.py      a simulation as a film
```

Parked, from the earlier plan (validated, not in use): `src/fatigue/`, `src/mpc/`,
`src/musculoskeletal/`, `src/allocation/`, `src/jobs/`, `src/activation/`, and `external/PHRC/`.

---

## 5. Rules

**Raw data is never edited and never committed.** `data/`, `results/` and `refs/` are gitignored.
Do not hand-edit anything in `results/`: regenerate it.

**Every script keeps a runnable self-check.** Run a file with no arguments and it asserts its own
results. If you change the logic, the assertions must still pass, or be updated with a reason.

**Desired torque is never a model input**, and neither is anything else in the banned list of
[`docs/model_inputs.md`](docs/model_inputs.md).

**Whole passes, never random strides,** when splitting data. Neighbouring strides are near copies.

**The test blocks are scored once,** after every choice has been made on the validation blocks.

**Do not edit `external/PHRC/`.** It is another group's code, kept unmodified as a baseline for
the parked fatigue work. It contains a known bug; our code works around it.

---

## 6. Things you could pick up

| Task | Notes |
|---|---|
| **Write to the dataset's authors for the EMG** | It was recorded for the five Madrid participants and not released. Contacts in `docs/JASITH_TASKS.md`, J1 Q8 |
| **Scale the model to each participant** | Height and mass are published (`models/exogait/participants.csv`). Then solve the walking again. `docs/KURIAN_TASKS.md`, K6 |
| **Smooth the model's foot contact** | The model's load bounces between the feet where the measured load moves smoothly (`figures/k6_load_split.png`). A softer or better-placed contact, or tracking the measured split |
| **Single strides and ramps in the simulator** | `docs/KURIAN_TASKS.md`, K5 "Left" |
| **A multi-start for the solver** | Different starts give different solutions. `notes/decisions.md`, 2026-11-10 |
| **A model on a real time base** | Every model here needs the next heel strike. A windowed model would be causal. `docs/KURIAN_TASKS.md`, K3 "Optional" |

---

## 7. Working on it

Commit under your own name: check `git config user.name` and `user.email` before your first
commit. Work on a branch and merge through a pull request.

**Append to [`notes/`](notes/) as you go.** Surprises and numbers in `observations.md`, choices
in `decisions.md`, papers in `papers.md`. It is deliberately rough. A messy complete record beats
a clean partial one, and the write-up is built from it.

---

## 8. Who to ask

**Kurian** and **Jasith** for anything about the project. **The mentor** set the plan; the open
questions for the mentor are in `docs/JASITH_TASKS.md` (J1). **The supervisors** control the
cluster, which the full-scale evaluation needs ([`docs/RUN_ON_DGX.md`](docs/RUN_ON_DGX.md)).

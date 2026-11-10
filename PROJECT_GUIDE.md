# AI-Driven Human–Exoskeleton Digital Twin
### Personalized and Fatigue-Aware Lower-Limb Assistance Using MATLAB–OpenSim Moco[^title]

**The plan is the mentor's brief of 2026-10-14**, the "ExoGait plan": measured data from a real
exoskeleton, AI models of its torque, and an OpenSim Moco twin that replays and optimises that
torque. Offline analysis and simulation only. Python only. A laptop, with the DGX for the final
evaluation at full scale.

The task lists are the working documents: [`docs/KURIAN_TASKS.md`](docs/KURIAN_TASKS.md) and
[`docs/JASITH_TASKS.md`](docs/JASITH_TASKS.md). This file is the map.

> The earlier plan, a fatigue-aware allocation twin on synthetic sweeps, is archived at
> [`docs/guide_v3_fatigue_twin.md`](docs/guide_v3_fatigue_twin.md). What it built is parked (§7).

[^title]: The registered title. The project runs in Python, not MATLAB: the college has no licence
    (`notes/decisions.md`, 2026-10-28). The method is unchanged, OpenSim Moco's Python API has the
    same classes as its MATLAB one, and every file we hand over (`.osim`, `.sto`, `.csv`) opens in
    MATLAB. Fatigue is not modelled in this plan (§7): the mentor's brief replaces it with
    EMG-informed assistance, and the public dataset has no EMG.

---

## 1. The system

```
Layer 1  ExoGait data             19 people in a Fourier X2 (hip and knee, both legs), 333 Hz:
                                  joint angles, velocities, torques, gait phase. No EMG released
Layer 2  Python processing        strides on 101 phase points, blocks, splits     preprocess.py, split.py
Layer 3A AI                       exo torque = f(angles, velocities, phase, mode, ...)
                                  personalised vs population models                evaluate.py, lstm.py
Layer 3B OpenSim                  2D musculoskeletal model wearing the X2          x2model.py
Layer 4  Personalised twin state  what is measured, what the solve estimates       track.py
Layer 5  Moco optimal control     reproduce the measured walking; effort           track.py
Layer 6  Assistance, simulated    exo off / measured / AI / optimised torque       assist.py
```

The dataset is the ExoGait Benchmark (Lhoste et al. 2026, J NeuroEng Rehabil 23:114;
[Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.70rxwdc6j)). Its columns, signs and traps:
`docs/exogait_data.md`. What a model may see: [`docs/model_inputs.md`](docs/model_inputs.md).

## 2. Objectives and hypotheses: where each stands

| | What | Code | State (2026-11-11) |
|---|---|---|---|
| RO1 | Reproducible preprocessing | `preprocess.py`, `split.py` | **Done.** 5,964 strides from all 19, whole-block train/val/test splits, a leakage self-check |
| RO2 | Participant-specific torque models | `evaluate.py`, `lstm.py` | **Built; scored on the validation blocks.** Phase mean, ridge, random forest, bagged trees, LSTM. The test blocks are being scored |
| RO3 | Participant-informed simulation | `x2model.py`, `track.py` | **Done on mean walking strides,** on a generic body. Each participant's height and mass are published and not yet used |
| RO4 | AI torque + Moco | `assist.py` | **Three of four cases done** (exo off, measured, optimised). The AI case is built and waits for the test predictions |
| RO5 | EMG-informed assistance | — | **Blocked.** No EMG in the public release. It exists for five participants; the authors have to be asked |
| RO6 | Accuracy, tracking, cost, robustness | `stats.py` | Tables and tests are scripted; the at-scale run (single strides, ramps) is not started |
| H1 | Personalised beats population | `evaluate.py`, `stats.py` | On validation: yes for every per-row model on the torque at the joint, in 18–19 of 19 participants. Test pending |
| H2 | Gait phase helps | | On validation: yes, but little for a forest (4.4 vs 4.5 Nm). Test pending |
| H3 | Locomotion mode helps | | On validation: small. Test pending |
| H4 | Optimised assistance lowers simulated effort | `assist.py` | **First result, 16 participants:** −34% against the measured torque at the same torque budget (16 of 16, p = 3.1e-5) |
| H5 | EMG changes the allocation | — | Blocked with RO5 |

## 3. How each title term is delivered

| Term | Delivered by |
|---|---|
| **AI-Driven** | Torque models from baselines to an LSTM, scored on held-out blocks and on a held-out participant; their torque replayed in the twin |
| **Human–Exoskeleton** | A muscle-driven model with the X2's 20.7 kg and its four actuators, driven by the X2's own recorded angles and torques |
| **Digital Twin** | The model reproduces each participant's measured walking (hip 0.6°, knee 0.4° median error) and walks at the measured speed without being told it |
| **Personalized** | Per-participant models (H1), a per-participant hip offset and stride; body scaling is the next step |
| **Lower-Limb** | Hip and knee, both legs. The X2 has no ankle actuator and records no ankle angle |
| **OpenSim Moco** | Every simulation is a Moco tracking problem with muscles and foot contact |
| **Fatigue-Aware**, **MATLAB** | Not in this plan: see the title's footnote and §7 |

## 4. What is built

`src/exogait/`, one file per job, each with an assert-based self-check under `__main__`:

| File | Does |
|---|---|
| `checks.py` | Raw-file facts the rest relies on: signs, timing, which torque column is which |
| `preprocess.py` | Raw CSV to strides on 101 phase points; the stride and block rules; the exclusion log |
| `split.py` | Whole-block train/val/test per participant × mode × controller; the allowed inputs |
| `evaluate.py` | Every model fitted and scored the same way: schemes, ablations, metrics, results files |
| `lstm.py` | The LSTM, with early stopping and fine-tuning |
| `stats.py` | Paired tests, effect sizes and figures for H1–H4 |
| `x2model.py` | The 2D model plus the X2; X2 angles mapped to model coordinates |
| `track.py` | One Moco solve: track a stride with the exo torque prescribed or chosen; the twin's checks |
| `assist.py` | The assistance cases compared; the torque budget; second starts |
| `animate.py` | A solved stride as a film |

How to run them, in order: [`README.md`](README.md).

## 5. Results so far

Numbers and how they were obtained are in `notes/observations.md` (sections "K2" to "K7", "K3",
"J1b"). The short version:

- **The twin reproduces the walking.** All 38 solves (19 participants × two controllers)
  converge; 34 pass every plausibility check. Speed is not imposed and matches the data (r = 0.95).
- **Its ground forces pass a held-out check.** The X2's footplates measure how the load is split
  between the feet. The model, never shown that signal, gets it to r = 0.90. It gets the
  hand-over between the feet wrong in detail.
- **The dataset's two torques are different things.** One is at the motor, one at the joint. Half
  the motor torque accelerates the motor's own rotor.
- **So joint acceleration is the input that matters for the motor torque.** Adding it takes a
  linear model's walking error from 15.4 to 8.9 Nm (validation).
- **Assistance in simulation (H4).** The measured torque lowers the model's muscle effort by 16%
  against the exoskeleton switched off; an optimised torque with the same budget lowers it by a
  further 34%.

## 6. Limits to state with every result

- **A generic body.** One 62 kg 2D model for 19 people of 47–90 kg. Effort is a model quantity,
  not checked against metabolic cost or EMG.
- **Mean strides, walking only.** Single strides, ramps and stairs are not simulated yet. The 2D
  model's knee muscles are unreliable past about 85° of flexion, which stairs exceed.
- **No measured ground forces.** The solve invents them; only their left-right split is checked.
- **The solver is not repeatable** from different starts. The measured and exo-off solves were
  each run from two starts; a full multi-start is still to do.
- **Every torque model is offline.** The 101-point time base needs the next heel strike.
- **A test block is a later pass of the same session,** not another day.

## 7. Parked

- **The fatigue model and per-muscle allocation** (`src/fatigue/`, `src/allocation/`): validated
  work from the earlier plan. It comes back only if the mentor wants it as an extension (J1 Q6).
- **The synthetic sweep, surrogate and RL policy** (`src/jobs/`, `src/activation/`), with their
  DGX pipeline. The Docker image and the sweep pattern are reusable for the at-scale run (K9).
- **MATLAB.** Dropped, not parked: no licence.

## 8. Next

1. The test pass for H1–H3, then the AI torque replayed in the twin.
2. Scale the model to each participant (height and mass are published) and solve again.
3. Single strides and ramps; the at-scale evaluation (K9), on the DGX if it is granted.
4. EMG, if the authors release it. Otherwise RO5 and H5 are reported as not testable.

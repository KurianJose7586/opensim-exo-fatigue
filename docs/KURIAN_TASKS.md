# Kurian — task list

Team plan for the mentor's brief (received 2026-10-14). Jasith's half is in
[`JASITH_TASKS.md`](JASITH_TASKS.md).

---

## The mentor's plan in brief

```
Layer 1  ExoGait data            joint angles, velocities, measured torque, gait phase, EMG subset
Layer 2  MATLAB processing       sync, segmentation, features, normalisation
Layer 3A AI                      exo torque prediction, personalised models
Layer 3B OpenSim                 musculoskeletal model, kinematics, simulated joint loading
Layer 4  Personalised twin state participant parameters, state estimation, calibration
Layer 5  Moco optimal control    tracking accuracy, effort, smoothness, constraints
Layer 6  Simulated assist-as-needed controller   optimised assistance, EMG-informed modulation, safety limits
```

| | Objective / hypothesis | Owner |
|---|---|---|
| RO1 | Reproducible preprocessing pipeline for ExoGait | Jasith builds, Kurian runs at scale |
| RO2 | Participant-specific AI models for exo torque | Both (baselines Jasith, nonlinear Kurian) |
| RO3 | Participant-informed OpenSim simulation | Kurian |
| RO4 | AI torque layer + Moco, offline optimisation | Kurian |
| RO5 | EMG features inform assistance modulation (not fatigue) | Jasith features, Kurian simulation |
| RO6 | Accuracy, tracking, efficiency, cost, robustness | Kurian runs, Jasith statistics |
| H1 | Personalised model beats population model on held-out trials | |
| H2 | Gait phase as an input improves prediction | |
| H3 | Locomotion mode as an input improves prediction | |
| H4 | Optimised assistance lowers simulated effort vs a baseline, within tracking and safety constraints | |
| H5 | EMG-informed modulation changes simulated control allocation | |

Model form: `tau_exo(t) = f(q, qdot, phase, mode, participant info, controller params)`.
**Never use desired torque as an input.** Every input must exist at inference time.

**Dataset:** ExoGait Benchmark (Dryad, [doi:10.5061/dryad.70rxwdc6j](https://datadryad.org/dataset/doi:10.5061/dryad.70rxwdc6j)).
19 participants (14 AB, 5 HL), Fourier X2 exoskeleton (**hip and knee, both legs, no ankle**),
333 Hz CSV, 5.5 GB. Five modes (walk, ramp up/down, stairs up/down) × two controllers
(state machine SM, transparent TR). EMG for 5 subjects, 5 muscles per leg. No markers, no ground
reaction forces, no ankle angle, no anthropometrics.

## Why the split looks like this

Jasith's laptop cannot sustain long heavy runs. **Kurian takes everything compute-heavy**:
- the full 5.5 GB dataset
- tree ensembles, LSTM and GPR training
- every OpenSim/Moco solve
- the integration and the final evaluation runs

Jasith takes work that runs on one participant or on already-processed data.

---

## Tasks

| ID | Task | Done when | Depends on | Size | Status |
|---|---|---|---|---|---|
| K1 | **Set up the environment and get the data.** MATLAB with Statistics & ML, Deep Learning and Signal Processing toolboxes (confirm licences). OpenSim 4.6 with MATLAB scripting. Run a stock MocoTrack example end to end. Download all 19 CSVs and the EMG files into `data/` (gitignored) | The MocoTrack example solves on your machine; solve time and setup steps written in `notes/observations.md` | — | M | in progress: OpenSim 4.6 + Python MocoTrack done (39 s). MATLAB and data downloads pending |
| K2 | **Run preprocessing on all 19 participants** with Jasith's J3 code. Fix whatever breaks at scale (load per participant and only the needed columns; no whole-dataset tables in memory). Share the processed files with Jasith (they stay out of git) | All 19 processed. A per-participant table of kept vs excluded strides, by reason. The J4 no-overlap check passes on the full set | J3, J4 | L | todo |
| K3 | **Nonlinear torque models (RO2).** Mandatory: random forest / bagged trees, LSTM. Optional: GRU, GPR. Run each for H1 (personalised vs population), H2 (with vs without phase) and H3 (with vs without mode). Tune on the validation set only. Use the metric function and results format from J5 | Results files with RMSE, MAE, R², nRMSE and inference time, per mode and per participant, for every model × ablation. Test set touched once | K2, J4, J5 (metrics function) | L | todo |
| K4 | **OpenSim model (RO3).** Start sagittal-plane, as the mentor suggests. Candidates: the 2D gait model already in `models/base/` (it has foot contact, but a known gastroc-path warning) or Rajagopal if its coordinates map to the dataset. Map X2 hip and knee angles to model coordinates: check signs and zero offsets against J2. Ankle is not recorded: decide how to handle it and write it down. Use generic anthropometry and say so. Add hip and knee exo actuators only, plus X2 device mass. Reuse the actuator, reserve and self-check patterns in `src/musculoskeletal/twin.py` | The model loads, the coordinate list is verified, and one participant's hip/knee trajectories map onto it with sensible signs (plot checked by Jasith) | K1, J2 | L | todo |
| K5 | **MocoTrack: reproduce gait kinematics.** The first OpenSim goal is reproduction, not optimisation. Start with overground walking, one participant, TR mode, then SM. Then ramps. Stairs last, since they need different contact geometry | Walking tracked with tracking RMSE reported per joint. Plausibility checks pass: joint limits, signs, actuator magnitudes, per-joint reserves. Solve time recorded | K4 | L | todo |
| K6 | **Personalised twin state (Layer 4).** Per-participant parameters (mass/scale where available, else generic, stated). Sanity check: simulated net hip and knee moments vs the measured X2 torque in SM mode | One record per participant of the parameters used. The moment-vs-torque comparison plotted for at least one participant | K5 | M | todo |
| K7 | **AI + Moco integration (RO4, H4).** Feed AI-predicted torque into the Moco problem, then optimise assistance. The effort objective is probably the sum of squared activations (confirm via J1). Proposed baselines: no assistance, and the measured SM torque replayed in Moco. Constraints: tracking-error bound and X2 torque limits. The hip/knee split logic in `src/allocation/` can be reused | Effort reduction (or not) vs each baseline, with tracking and safety constraints shown satisfied, on at least one participant and mode | K3, K5, J1 | L | todo |
| K8 | **Simulated assist-as-needed controller (Layer 6) and H5.** Optimised assistance + EMG-informed modulation (J6 features) + safety limits. Compare control allocation with and without EMG on the 5 EMG subjects. Call the features muscle-activity features, never fatigue | Allocation with vs without EMG compared on the EMG subjects, with safety limits respected | K7, J6 | L | todo |
| K9 | **RO6 evaluation at scale.** All participants and modes: prediction accuracy, tracking, assistance efficiency, computational cost per stage, robustness across participants and modes | One results set covering every participant × mode, handed to Jasith for J7 statistics and the write-up | K3, K7, K8 | L | todo |

Sizes: S = a day or two, M = about a week, L = more than a week.

## Handoffs

| From | To | What |
|---|---|---|
| Jasith J2 | K4 | Column meanings, units, sign conventions, condition labels |
| Jasith J3 | K2 | Preprocessing code, tested on one participant |
| Jasith J4 | K2, K3 | Split files, no-overlap check, allowed-inputs list |
| Jasith J5 | K3 | Metric function and results format |
| K2 | Jasith J5 | Processed per-stride dataset |
| Jasith J6 | K8 | Per-stride EMG features for the 5 EMG subjects |
| K3, K9 | Jasith J7 | Results files for statistics and figures |
| K4, K5 | Jasith | Plots to review for signs and joint limits (a second pair of eyes) |

## Order

1. **Now:** K1, then K4 (needs J2's column notes)
2. K5, while Jasith writes J3 and J4
3. K2 as soon as J3 lands, then K3
4. K6, K7
5. K8, K9

Sync after each stage. Anything that changes a handoff (column names, file formats, splits) gets
a team message before it changes.

---

## Shared rules

- **MATLAB is the primary platform** (mentor). Whether Python is allowed for parts is question 1
  in J1. Until answered, write new code in MATLAB under `matlab/`. Proposed layout:
  `matlab/preprocess/`, `matlab/models/`, `matlab/opensim/`.
- **Raw data is never edited and never committed.** `data/` and `results/` stay gitignored.
  Processed files are shared outside git.
- Every script keeps a runnable self-check, as in the existing `src/` code.
- Work on a branch, merge through a PR. Log findings in `notes/` as before.

## Parked (not in the mentor's plan)

- The D1–D4 synthetic sweep, surrogate and RL policy, and the DGX/Docker/Kubernetes setup.
- The Phase C "8.6%" result. It leaned on an ankle actuator that the X2 does not have.
- The fatigue model and per-muscle allocation are kept only as a possible extension. They come
  back only if the mentor agrees (J1).

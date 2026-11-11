# Kurian — task list

Team plan for the mentor's brief (received 2026-10-14). **Python only since 2026-10-28**: the
college has no MATLAB licence (`notes/decisions.md`). Jasith's half is in
[`JASITH_TASKS.md`](JASITH_TASKS.md). The code layout, file formats, shared rules and the parked
list below apply to both of us.

---

## The mentor's plan in brief

```
Layer 1  ExoGait data            joint angles, velocities, measured torque, gait phase, EMG subset
Layer 2  Python processing       sync, segmentation, features, normalisation
Layer 3A AI                      exo torque prediction, personalised models
Layer 3B OpenSim                 musculoskeletal model, kinematics, simulated joint loading
Layer 4  Personalised twin state participant parameters, state estimation, calibration
Layer 5  Moco optimal control    tracking accuracy, effort, smoothness, constraints
Layer 6  Simulated assist-as-needed controller   optimised assistance, EMG-informed modulation, safety limits
```

Layer 2 was "MATLAB processing" in the brief. Python stack per layer: 2 pandas, numpy,
scipy.signal · 3A scikit-learn, PyTorch · 3B–6 the OpenSim/Moco Python API.

| | Objective / hypothesis | Owner |
|---|---|---|
| RO1 | Reproducible preprocessing pipeline for ExoGait | Kurian (J3 and K2, since 2026-11-10); Jasith reviews |
| RO2 | Participant-specific AI models for exo torque | Kurian (baselines J5, nonlinear K3); Jasith reviews |
| RO3 | Participant-informed OpenSim simulation | Kurian (K4–K6) |
| RO4 | AI torque layer + Moco, offline optimisation | Kurian (K7) |
| RO5 | EMG features inform assistance modulation (not fatigue) | Jasith features (J6), Kurian simulation (K8). Blocked: no EMG |
| RO6 | Accuracy, tracking, efficiency, cost, robustness | Kurian runs (K9), Jasith statistics (J7) |
| H1 | Personalised model beats population model on held-out trials | J5 and K3 run, J7 tests |
| H2 | Gait phase as an input improves prediction | J5 and K3 run (per-row models only, K3), J7 tests |
| H3 | Locomotion mode as an input improves prediction | J5 and K3 run, J7 tests |
| H4 | Optimised assistance lowers simulated effort vs a baseline, within tracking and safety constraints | K7 (one participant), K9 (at scale), J7 tests |
| H5 | EMG-informed modulation changes simulated control allocation | J6 and K8: blocked (J1 Q8) |

Model form: `tau_exo(t) = f(q, qdot, phase, mode, participant info, controller params)`.
**Never use desired torque as an input.** Every input must exist at inference time.

**Dataset:** ExoGait Benchmark (Dryad, [doi:10.5061/dryad.70rxwdc6j](https://datadryad.org/dataset/doi:10.5061/dryad.70rxwdc6j)).
19 participants (14 AB, 5 HL), Fourier X2 exoskeleton (**hip and knee, both legs, no ankle**),
333 Hz CSV, 5.5 GB. Five modes (walk, ramp up/down, stairs up/down) × two controllers
(state machine SM, transparent TR). No markers, no ground reaction forces, no ankle angle, no
anthropometrics. The README promises EMG for 5 subjects, **but the Dryad release has none**
(J1 Q8). Column guide: [`docs/exogait_data.md`](exogait_data.md).

## Why the split looks like this

Jasith's laptop cannot sustain long heavy runs. **Kurian takes everything compute-heavy**
(16 logical cores, 16 GB RAM, RTX 2050 with 4 GB, ~36 GB free disk):
- the full 5.5 GB dataset
- tree ensembles, LSTM and GPR training (the LSTM on the GPU)
- every OpenSim/Moco solve
- the integration and the final evaluation runs

Jasith takes work that runs on one participant or on already-processed data.

---

## Code layout

One flat package, `src/exogait/`. One file per job, each with an assert-based self-check under
`__main__`. Existing helpers are imported, not copied.

| File | Tasks | Imports | What it does |
|---|---|---|---|
| `checks.py` | J2 | pandas | Raw CSV checks behind the J2 numbers (exists) |
| `preprocess.py` | J3, K2 | pandas, numpy | Raw CSV → per-stride files and exclusion log. Owns the stride and block rules |
| `split.py` | J4, K2 | pandas | `splits.csv`, `split_counts.csv`, the leakage self-check, `ALLOWED` input columns |
| `evaluate.py` | J5, K3, K9 | scikit-learn | `metrics()`, results writer, H1–H3 ablation loop. Phase mean and ridge by default; forests, GPR and the LSTM with `--models` |
| `lstm.py` | K3 | torch | LSTM/GRU with `fit`/`predict`, so `evaluate.py` runs it like the sklearn models |
| `x2model.py` | K4 | opensim | `2D_gait.osim` + X2 masses and hip/knee actuators; X2 → OpenSim coordinates |
| `track.py` | K5, K6 | opensim | MocoTrack per stride, the exo torque prescribed or chosen (`case`); `params.csv`; joint moments vs X2 torque; the load split against the footplates |
| `assist.py` | K7, K8, K9 | opensim | Compares the cases (`none`, `measured`, `optimised`, `ideal`; later `ai`, `emg`), prices the torque budget; the at-scale loop |
| `animate.py` | K7 | opensim, matplotlib | A solved stride as a film: the model walking, muscles coloured by activation, the exo torque at hip and knee, one panel per case |
| `emg.py` | J6 | scipy.signal | EMG envelopes per stride (when EMG arrives) |
| `stats.py` | J7 | scipy.stats, matplotlib | Paired tests, effect sizes, figures |

**The opensim files never import torch, and the torch files never import opensim** (Shared
rules). They hand off through CSV and `.sto`.

Reused from the old pipeline: `src/musculoskeletal/twin.py` (`components()`, the device-mass,
exo-actuator and reserve patterns, `net_moments()`); the resume, one-output-per-task, own
working directory and commit-stamp pattern of `src/jobs/sweep.py` (K9). `src/allocation/allocate.py`'s
`candidates()` is a hip/knee/ankle grid and imports `src/fatigue`. Only if the mentor wants a
shared hip/knee budget (K7): use it with the ankle column fixed at 0 (`P[P[:, 2] == 0, :2]`,
with `src/fatigue` on `sys.path`).

---

## Tasks

| ID | Task | Depends on | Size | Status |
|---|---|---|---|---|
| K1 | Environment and data | — | M | **done** (PR #6, approved, not merged). MATLAB part dropped. Env rebuilt 2026-11-10, with CUDA torch |
| K2 | Preprocessing at scale (RO1) | J3 (preprocess); J4 (`split.py`, for the last done-when bullet) | L | **done** 2026-11-10, with J3–J5: all 19 processed and split, baselines scored on val |
| K3 | Nonlinear torque models (RO2, H1–H3) | K2, J4, J5 | L | **done** 2026-11-11: forests and LSTM, val then one test pass (`notes/observations.md`, "K3 and J7"). GPR and GRU (optional) not run |
| K4 | OpenSim model and X2 mapping (RO3) | K1, J2 | L | **in progress**: model, mapping and torque sign done; Jasith's plot check left |
| K5 | MocoTrack: reproduce the gait | K4 | L | **walking done** on mean strides, all 19 × SM/TR. Single strides (need J3) and ramps left |
| K6 | Personalised twin state (Layer 4) | K5; J1b (soft: generic anthropometry is the default) | M | **done** on mean walking strides, on a generic body and on one scaled to each participant's height and mass (`EXOGAIT_SCALED=1`); H4 is the same on both |
| K7 | AI + Moco integration (RO4, H4) | K3, K5, K6, J1 Q5 | L | **done on mean SM strides**: `none`, `measured`, `optimised` (16 participants), `ai` (15). Single strides left |
| K8 | Assist-as-needed controller with EMG (Layer 6, H5) | K7, J6 | L | **blocked**: no EMG (J1 Q8). Closes as not possible if none by 2026-12-01 |
| K9 | RO6 evaluation at scale | K3, K7 (K8 if EMG) | L | todo |

Sizes: S = a day or two, M = about a week, L = more than a week.

### K1 — Environment and data · done

- OpenSim 4.6 unpacked to `C:\OpenSim 4.6` (source of the example scripts) and the micromamba
  env `opensim`: Python 3.11.17, opensim 4.6, numpy/scipy/pandas/matplotlib on OpenBLAS.
- Stock MocoTrack (`example2DWalking.py`, tracking problem) solves in 39 s, 87 IPOPT iterations.
  That problem is a 0.47 s half-cycle with a symmetry goal, not an ExoGait stride (K5, K9).
- All 19 CSVs in `data/raw/exogait/` (gitignored). Dryad blocks scripted downloads: by hand.
- Details: `notes/observations.md`, "K1".
- **Env rebuilt 2026-11-10** from ONBOARDING §2 (it had gone from `~/micromamba`): micromamba
  2.10.0, Python 3.11.18, opensim 4.6, numpy 2.4.6, scikit-learn 1.9.1, on OpenBLAS. MocoTrack
  runs in it (all of K5).
- **CUDA torch is in** (2.14.1+cu126): `torch.cuda.is_available()` is True on the RTX 2050.
  torch and opensim stay in separate processes (Shared rules), so no one-process test was run.

### K2 — Preprocessing at scale (RO1) · done

- **Done 2026-11-10**, together with J3–J5, which Kurian took over (`notes/decisions.md`). The
  rules are in the docstrings of `preprocess.py` and `split.py`; the numbers are in
  `notes/observations.md`, "K2".
  - 9,697 strides detected, **5,964 kept** (220–458 per participant). Dropped: 2,237 cross a
    label change, 1,399 are marked incomplete by the dataset, 75 have an outlier duration, 22
    have sampling holes.
  - 134 MB for all 19 (5–11 MB each), in 80 s. `split.py` takes 2 s and its self-check passes.
  - Splits are thirds, not 60/20/20: most conditions have three blocks.
- **Code:** `src/exogait/preprocess.py`, then `src/exogait/split.py`. Changes go through a PR
  that Jasith reviews.
- **Run:** `micromamba run -n opensim python -u src/exogait/preprocess.py all`, then
  `split.py` (no arguments: every participant on disk). About 4 s per participant, read with
  `usecols`. One participant in memory at a time, only the needed columns.
  - **`time` stays float64.** The raw clock runs to 1,234–4,855 s, where float32 resolves only
    0.12–0.49 ms: it turns 0–33 real dt ≤ 0 per file into up to 1,238. float32 only for angle,
    velocity and torque columns.
- **Known traps (J2, checked on all 19):** AB82's left-knee gauge torque is stuck at −12.07 Nm
  in SM walking, SM ramps and TR ramps (written as NaN, flagged `gauge_stuck`); AB72's column
  order; every HL file (33 duplicated time stamps each, `*_UNDEFINED2` labels); **the clock
  restarts** once to three times in AB69/72/76/80/82 and runs over the same seconds again, so
  strides are ordered by raw row, not by `t`; removed rests up to 352 s; two sites (Chicago and
  Madrid) with different stairs and ramps.
- **In:** `data/raw/exogait/*.csv`, read only.
- **Out:** `data/processed/exogait/`: `<ID>_strides.csv`, `<ID>_stride_features.csv` and
  `<ID>_excluded.csv` for all 19, plus `summary.csv`, `splits.csv` and `split_counts.csv`.
  Zipped and shared outside git.
- **Done when:**
  - all 19 are processed;
  - `summary.csv` gives kept vs excluded by reason, per participant × mode × controller × leg;
  - `split.py` runs on all 19 and its self-check passes;
  - the processed size is in `notes/observations.md` (Jasith's J5 runs on it).

### K3 — Nonlinear torque models (RO2: H1, H2, H3)

- **Forests (mandatory):** scikit-learn `RandomForestRegressor` and
  `BaggingRegressor(DecisionTreeRegressor())`, `n_jobs=-1`, multi-output (hip and knee torque
  together).
  - Population forests use `min_samples_leaf>=5, max_samples<=0.3`. A full-depth forest on a
    ~520k-row fold is about 5 GB and takes minutes per fit, and there are 57 fits per forest
    type (19 folds × 3 ablations). Keep grids to a handful of points.
- **LSTM (mandatory):** PyTorch, in `lstm.py`. Unidirectional over the 101-point stride, on the
  RTX 2050 (4 GB is ample at this size).
  - Early stopping on J4's validation blocks picks the epoch count. The refit on train + val
    runs for that many epochs, with no early stopping.
  - Personalised LSTM for participant P = P's leave-one-out population model (trained without
    P), fine-tuned on P's training blocks. H1 compares that model before and after fine-tuning,
    on the same test strides. From scratch there are only ~30 walking strides per leg and
    controller. State this in the results.
  - **No H2 arm for this LSTM.** Over a stride that always starts at heel strike and has 101
    points, sequence position is phase, so dropping the `phase` column removes nothing. Its H2
    arm is reported as not applicable.
  - Optional: an LSTM on fixed-length windows of the real time base (about 1 s at 100 Hz, ending
    at each sample, not aligned to heel strike) gives a valid no-phase arm and a causal model.
    It needs the kept bouts on a 100 Hz time base, a second `preprocess.py` output. Add it only
    if this variant is run.
- **GRU (optional):** swap `nn.LSTM` for `nn.GRU` in the same file.
- **GPR (optional):** `GaussianProcessRegressor` with kernel
  `ConstantKernel() * RBF(np.ones(d)) + WhiteKernel()` and `normalize_y=True`, after a
  `StandardScaler` in the same pipeline. The constant kernel and `normalize_y` let it reach
  torques of ~20 Nm RMS (a bare RBF has amplitude 1).
  - Exact GPR is O(n³) time and O(n²) memory: at most 5,000 points per fit, and personalised
    scheme only, stated.
  - A sparse GP (GPyTorch) is a new dependency. Add it only if the subsampled GPR looks worth it.
- **Runs inside J5's `evaluate.py`:** the same metric function, results format and ablation loop
  as the baselines, with `--models rf,bag,gpr,lstm` on this machine.
- **Ablations:**
  - H1: personalised vs population, both scored on the same test strides;
  - H2: with vs without `phase`, on the per-row models (phase mean, ridge, forests, GPR). The
    no-phase arm also drops `gait_state` and `stance_alpha`, which encode phase;
  - H3: with vs without `mode`.
- **Tuning:**
  - Small grids, on J4's validation blocks only (sklearn `PredefinedSplit`). Never
    `GridSearchCV`'s default `cv`: it is an unshuffled `KFold` over row positions that ignores
    blocks and participants, so a fold edge splits a stride's 101 rows and puts neighbouring
    strides on both sides.
  - Refit on train + val, then score the test set once, in a final `--test` run.
- **In:** `<ID>_strides.csv`, `splits.csv`, and `ALLOWED` from `split.py`.
- **Out:**
  - results rows: `results/exogait/predict/<model>.csv`;
  - test-stride predictions for K7: `results/exogait/predict/<model>_<ID>_pred.csv`;
  - no per-fold model files. Save at most the final full-input model per scheme in
    `results/exogait/models/`, with `joblib.dump(m, f, compress=3)` (`.pt` for the LSTM).
    Python-only and regenerable.
- **Done when:** RMSE, MAE, R², nRMSE and inference time exist for every model × scheme ×
  ablation (GPR: personalised scheme only; LSTM: no H2 arm; both stated), per participant, mode
  and controller. The test set is touched once.

### K4 — OpenSim model and X2 mapping (RO3) · in progress (waiting on Jasith's plot check)

- **Code:** `src/exogait/x2model.py` (~10 s). It edits `2D_gait.osim` as XML and has
  `opensim-cmd` load it and play the target back, so it needs no OpenSim bindings (written while
  the env was gone). It follows `twin.py`'s device-mass and `_add_exo` patterns (`EXO_F` = 100)
  rather than importing them. Reserves go on in K5's `ModelProcessor`.
- **Model:**
  - `models/base/2D_gait.osim`, sagittal, as the mentor suggests. Generic anthropometry, stated:
    ExoGait has none.
  - X2 mass 20.7 kg welded on: Kucuktabak et al., IEEE T-RO (arXiv 2301.06244), Table II,
    backpack 10.3 kg, thigh 2.84, shank 1.11 and foot plate 1.25 kg per leg; COMs from CORC.
  - Hip and knee exo actuators, both legs, ±80 Nm (T-RO Sec. II-A; the data reach 85–89 Nm, so
    a replay of single strides may need wider bounds). Rotor inertia (1.87 kg m² per joint) and
    friction are left out, rightly: they sit between `JointTorques` (motor side) and
    `JointTorquesViaGauges` (joint output), and K5 replays the gauge torque (K6).
- **Mapping (done):**
  - `knee_angle` = X2 knee; `hip_flexion` = X2 hip − c; `pelvis_tilt` = `BackPackAngle` − 90° + c.
    The X2 hip is measured from the backpack (checked on all 19). c is per participant and holds
    the mean pelvis tilt at the reference's −15.06°, because the backpack level differs by site
    (AB68 −14.2°, HL03 −5.4°, range −0.6 to −23.8°). c is a K6 parameter.
  - **Torque sign (done):** `+JointTorques` drives the angle +, so the X2 torques have OpenSim's
    generalized force sign: exo control = torque / 100. `checks.py` asserts it from the SM
    impedance law, on all 19.
  - Target = the mean of the clean strides of one participant × condition, right heel strike to
    right heel strike, made periodic with its mean kept. `BackPackAngle` strides the gyro does
    not confirm are dropped from `pelvis_tilt` and c only. The heel-strike rule is
    `preprocess.heel_strikes()`, imported here. K4's stricter filters (steady strides only) stay
    in `x2model.strides()`: a mean stride for Moco wants less than the torque models do.
  - The ankle is not in the target. K5 tracks the stock reference ankle at weight ≤ 0.01 (the
    J1 Q7 default; at 0.1 the trial ankle followed it to 0.4°, i.e. imposed) or leaves it free,
    with bounds widened to ±30°.
  - Details and numbers: `notes/observations.md`, "K4".
- **Scope:**
  - Walking and ramps: per-stride knee peaks of 70–85°, ramp maxima up to 91° (AB68). Usable
    with the moment-arm caveat in `notes/observations.md`. Report the share of ramp strides
    above 85°.
  - Contact: all four foot spheres push on one flat `floor` half-space. Ramps need it tilted to
    the site's slope (Chicago 5°, Madrid 6°; `docs/exogait_data.md`, Protocol), and stairs need
    step contact geometry. The model has neither today. K5 tilts the floor for ramps.
  - Stairs (83–114°) wait for J1 Q10.
- **Out:**
  - `results/exogait/model/2D_gait_x2.osim`;
  - `results/exogait/coords/<ID>_<condition>_mean.sto`;
  - the review plot `figures/k4_ab68_tr_walking_mapping.png` (committed, so Jasith sees it in the PR).
- **Done when:**
  - **done:** the model loads and its coordinate list is verified;
  - **left:** one participant's hip/knee trajectories map with sensible signs (plot checked by Jasith);
  - **done:** the self-check asserts the added device mass, and that there are 4 exo actuators and none
    at the ankle (it passes on all 19 × TR/SM walking);
  - **done:** the `JointTorques` sign is checked against the SM impedance law (all 4 joints, AB68 and
    HL03); **left:** written into `docs/exogait_data.md` once PR #7 merges;
  - **left:** the zero-offset **[open]** line in `docs/exogait_data.md` is updated with the c mapping
    (same PR #7 dependency).

### K5 — MocoTrack: reproduce the gait · walking done on mean strides

- **Code:** `src/exogait/track.py`. One solve = one participant × condition × case, on the
  **mean stride** `x2model.py` builds. The first goal is reproduction, not optimisation.
- **Problem** (the `example2DWalking.py` tracking problem, changed as below; reasons in
  `notes/decisions.md`, 2026-11-10):
  - One full mean stride (1.9–5.6 s), periodic in every state but `pelvis_tx`. No L/R symmetry.
  - Tracked: hip and knee at weight 10 against effort 1; `pelvis_tilt` at 0.2 of that; the stock
    walk's ankle at 0.001 of it (the J1 Q7 default). All low-passed at 6 Hz as periodic curves.
  - **The exo actuators replay the mean `JointTorquesViaGauges`**, held exactly by a path
    constraint (`MocoControlBoundConstraint`). It is the joint-output torque (K6). This solve is
    K7's `measured` case.
  - Speed is not imposed. The pelvis only has to advance by 0.5–1.3 of a kinematic stride
    estimate; the stride length is the model's own, and it is checked against the data (below).
  - Reserves at every coordinate (1 Nm = 1 excitation), reported per coordinate.
  - Bounds: knee −120°…10°, hip −25…95°, ankle ±30°, `pelvis_tilt` = the mapped mean ± 10°.
  - No GRF tracking: ExoGait has none.
  - **Start:** every solve starts from `models/exogait/seed_stride.sto` (a converged HL03 SM
    stride), stretched in time. From the tracked states alone IPOPT usually wanders.
  - 50 mesh intervals per stride, IPOPT tolerance 1e-3 (constraints 1e-4).
- **Run:** `micromamba run -n opensim python -u src/exogait/track.py [ID] [condition] [mesh]
  [guess .sto | seed | cold] [case]`. About 5–10 minutes with 4 threads
  (`OPENSIM_MOCO_PARALLEL=4`), four at a time on this machine, 0.5–0.6 GB each.
- **Out:**
  - `results/exogait/moco/<ID>_<condition>_mean_<case>_m<mesh>.sto`;
  - a row in `results/exogait/moco/summary.csv` (File formats), including the verdict of the
    plausibility checks;
  - `results/exogait/plots/k5_<name>.png`.
- **Done when:**
  - **done:** walking is tracked, with tracking RMSE reported per joint (all 19 × SM/TR; numbers
    in `notes/observations.md`, "K5");
  - **done:** the self-check asserts plausibility: converged; hip and knee RMSE under 3°; pelvis
    under 6°; inside the joint ranges and no tracked coordinate on a bound; knee never past 5°
    of extension; the exo torque as prescribed (under 1 Nm RMS off); joint reserves under 5 Nm
    RMS; stride length off its bounds; peak vertical force under 2.5 body weights;
  - **done:** solve time, peak memory and the chosen mesh are in `notes/observations.md`.
- **Left:**
  - **Single strides** (K7's per-stride cases and K9). They need J3's `<ID>_strides.csv`. A
    single stride is not periodic: drop the periodicity goal for it.
  - **Ramps:** rotate the floor `ContactHalfSpace` by the site's ramp angle (5° Chicago, 6°
    Madrid; J1 Q12). The stride filters leave 0–15 clean ramp strides per participant, so the
    bout-edge rule needs a second look first.
  - Stairs only after J1 Q10.

### K6 — Personalised twin state (Layer 4) · done on mean walking strides

- **Code:** `track.py` (`params`, `k6`).
- **State estimation:** which states come from where.

  | State | Source |
  |---|---|
  | hip and knee angles, both legs | measured (X2 encoders), tracked to about 0.5° |
  | `pelvis_tilt` | measured as `BackPackAngle`, mapped with the per-participant offset c (K4), tracked to about 2° |
  | X2 torque at the four joints | measured (`JointTorquesViaGauges`), replayed exactly |
  | ankle angles | estimated by the solve, with the stock walk's ankle as a weak prior |
  | pelvis translation, so stride length and speed | estimated by the solve (checked against the data) |
  | lumbar angle | estimated by the solve, within 0–20° |
  | ground reaction forces | estimated by the solve (the contact model) |
  | muscle activations and forces | estimated by the solve (generic muscles) |

- **Per-participant parameters:** `results/exogait/params.csv`, one row per participant: the hip
  offset c, stride time, stride counts, the kinematic stride length and speed per controller,
  and the masses used. Body mass and height are generic (62 kg, the 2D model's) until J1b finds
  them in the papers; the X2 adds 20.7 kg.
- **Which torque column:** `JointTorquesViaGauges` is the joint-output torque, `JointTorques`
  the motor side (`notes/decisions.md`, 2026-11-10). `checks.py` asserts it on every participant.
- **Moment vs torque:** `track.py k6 <ID>` sums the hip and knee moments from the K5 solutions
  themselves (muscle tendon force × moment arm, plus exo, plus reserves) and compares them with
  the measured torque, in SM and TR. It replaced the ID re-solve of the `twin.net_moments()`
  pattern, which left 3–4% of body weight in pelvis residuals on the splined kinematics.
- **Out:** `results/exogait/params.csv`; `results/exogait/moco/moment_vs_torque.csv`;
  `results/exogait/plots/k6_<id>_moment_vs_torque.png`.
- **Done when:** **done:** a params row per participant; the comparison plotted in both modes;
  the TR conclusion in `notes/observations.md` ("K6").
- **Left:** scale the model per participant. Height and mass are published (Lhoste et al.
  2026, Table 2; `models/exogait/participants.csv`, 47–90 kg against the model's 62 kg), so K5–K7
  can be solved again on scaled bodies: about a night (`notes/decisions.md`, 2026-11-10). A fitted
  calibration stays out of scope.
- **A held-out check, done:** `track.py load` compares the model's left-right split of the
  vertical ground force with `StanceInterpolationFactor`, which is that split as the footplates
  measure it. The tracking never sees it. On the 34 valid walking solves r = 0.90 (median;
  0.70–0.97): single support is right, the hand-over between the feet bounces
  (`notes/observations.md`, "K6: a held-out check"; `figures/k6_load_split.png`).

### K7 — AI + Moco integration (RO4, H4) · in progress: `ai` waits for K3

- **Code:** `src/exogait/assist.py`, on top of `track.solve(case=...)`. It imports opensim only
  and will read K3's predictions from CSV.
- **Cases, per stride** (today: the mean stride):

  | Case | Exo torque |
  |---|---|
  | `none` | held at zero |
  | `measured` | the measured joint-output torque replayed: K5's solve (the H4 baseline) |
  | `ai` | K3's predicted torque replayed (full-input, personalised, the model K3 ranks best on validation). **Not built: needs K3** |
  | `optimised` | Moco picks the hip and knee torque within the X2 limits **and the `measured` budget** |
  | `ideal` | Moco picks the torque at almost no cost, within the X2 limits only. An upper bound, never the H4 test (J1 Q5). Solved only on request |

- **The budget:** per exo actuator, the integral of squared torque over the stride is no more
  than the measured profile's. Without it `optimised` beats `measured` by construction.
  - Moco 4.6 cannot constrain that integral (`notes/decisions.md`, 2026-11-10). So each
    actuator's squared torque is priced in the effort goal, and `assist.budgeted()` adjusts the
    four prices until each actuator spends 90–102% of its budget. That is the optimum under the
    budget. It takes 3–6 solves, each started from the last.
- **Effort:** the sum of squared muscle activations, integrated over the stride and recomputed
  from each solution, the same way for every case. Never the Moco objective.
- **Second starts:** IPOPT lands in different local solutions from different starts, and one
  repeat doubled the effort (`notes/decisions.md`, 2026-11-10). `assist.py second` re-solves
  `measured` from the `none` solution and `none` from the `optimised` one, and keeps the lower
  objective. Run it before reading a comparison. A full multi-start is still to come.
- **Constraints:** the X2 torque limits as actuator bounds; the K5 plausibility checks on every
  solve (the tracking bound among them); the budget asserted on `optimised`.
- **Smoothness:** the RMS rate of each exo torque (Nm/s) is in `summary.csv` and `assist.csv`.
  It is reported, not limited: the optimised torque is 2–3 times less smooth than the measured.
- **TR:** reported separately. In TR the delivered torque mostly carries the device (K6).
- **Out:** a `.sto` and a `summary.csv` row per solve; a row per participant × condition in
  `results/exogait/moco/assist.csv`; `results/exogait/plots/k7_<id>_<condition>_assist.png`.
- **Film:** `python src/exogait/animate.py [ID] [condition] [cases]` draws the solved stride of
  each case side by side (`figures/k7_<id>_<condition>_stride.mp4`, `.gif`, `.png`; about
  4 minutes). HL03's is committed.
- **Done when:** **done on mean strides:** the effort change of `optimised` vs `measured` and vs
  `none` is shown, with the tracking bound, the X2 limits and the budget satisfied and smoothness
  reported per joint (numbers in `notes/observations.md`, "K7"). **Left:** the `ai` case (K3),
  single test strides (J3, J4), and a torque-rate limit on `optimised` if the mentor wants one.

### K8 — Assist-as-needed controller with EMG (Layer 6, H5) · blocked

- **Blocked:** the Dryad release has no EMG (J1 Q8). If none arrives by 2026-12-01, K8 closes as
  not possible and H5 is reported as not tested (data not released).
- **Code:** an `emg` case in `assist.py`. Either per-muscle effort weights from J6's
  muscle-activity features, or Moco's EMG-tracking pattern (`exampleEMGTracking`). Pick one and
  write it down.
- **Safety limits:** the X2 limits plus the tracking bound. Call the features muscle-activity
  features, never fatigue.
- **In:** `data/processed/exogait/<ID>_emg.csv`.
- **Done when:** allocation with vs without EMG is compared on the EMG subjects, with the safety
  limits respected.

### K9 — RO6 evaluation at scale

- **Code:** loops in `evaluate.py` (prediction) and `assist.py` (Moco); no new file.
  - The task list is participant × mode × controller × stride × case. One output per task,
    skipped if already on disk, stamped with the git commit: the `sweep.py` pattern.
  - Several solves at once, each a process of its own. `track.solve()` already runs each in
    its own `moco/work/<name>/` folder, since Moco writes its stop file and
    `<name>_tracked_states.sto` into the cwd, and never rewrites the shared model file.
  - K5's numbers: 0.5–0.6 GB and 5–10 minutes per solve with 4 threads
    (`OPENSIM_MOCO_PARALLEL=4`), four at a time on this machine. CPU sets the worker count, not
    RAM.
- **Scope:** one ExoGait stride lasts about 2.9 s (median of 3,166 right strides on walking and
  ramps), 6× the example's half-cycle, so expect minutes per solve.
  - **Default:** up to 5 eligible right test strides per participant × mode × controller
    (19 × 3 × 2 × 5 = 570 strides). Per stride that is one solve each for `none`, `measured`
    and `ai`, a second start for the first two, and 3–5 for `optimised` (the price search):
    about 5,000 solves at 50 mesh intervals. At about 2 minutes per solve net, four at a time,
    that is about a week on this machine, not a night.
  - All strides would be about 1,000 CPU-hours: the DGX (Parked, access requested in Order 1).
- **Measures:**
  - prediction accuracy (the J5/K3 rows);
  - tracking RMSE, effort change and smoothness;
  - compute cost per stage: preprocess, train, inference per stride, Moco solve;
  - robustness across participants and modes.
- **Timings compare like with like:** re-run the J5 baselines' `--test` pass on this machine, and
  time a fixed subset of Moco solves here even if the bulk runs on the DGX. Every timing row
  carries `host`.
- **Out:** `results/exogait/ro6/`: the collected `predict/*.csv` and `moco/summary.csv`, plus
  `cost.csv`. Handed to Jasith for J7.
- **Done when:** one results set covers every participant × mode in scope, at the default scope
  or larger.

---

## File formats

Every handoff is `.csv`, `.sto` or `.osim`, which MATLAB reads too. Units as in the raw data:
s, rad, rad/s, Nm. `t` is absolute seconds and always float64; signals may be float32.
Processed data goes in `data/processed/exogait/` (gitignored, shared as a zip). Results go in
`results/exogait/` (gitignored).

| File | Written by | One row per | Columns |
|---|---|---|---|
| `<ID>_strides.csv` | J3, K2 | stride × phase point (101 per stride) | see below |
| `<ID>_stride_features.csv` | J3, K2 | kept stride | key columns, `row_start, row_end` (the two heel strikes as raw rows, 0-based), `t_start, t_end, duration, max_dt, missing, gauge_stuck`, ROM, peak and RMS torque per joint (motor and gauge). Descriptive only, never model inputs |
| `<ID>_excluded.csv` | J3, K2 | dropped stride | `participant, leg, condition, row_start, row_end, t_start, t_end, reason` (the first rule that failed) |
| `summary.csv` | K2 | participant × mode × controller × leg | `detected, kept`, one count column per exclusion reason |
| `splits.csv` | J4, K2 (all 19) | stride | `participant, stride, block, split` (train/val/test) |
| `split_counts.csv` | J4, K2 (all 19) | participant × mode × controller | blocks and strides per split, `personalised` (False under 2 blocks) |
| `predict/<model>.csv` | J5, K3 | model × scheme × ablation × torque (motor/gauge) × participant × mode × controller × joint × split (val/test) | `rmse, mae, r2, nrmse, infer_ms` (per stride), `n_strides, n_train_strides, host, commit`. A re-run replaces its rows |
| `predict/<model>_<ID>_pred.csv` | J5, K3 (`--test` only) | stride × phase point × scheme | `participant, stride, leg, mode, controller, phase, t, scheme, ablation` (full), `hip_tau_pred, knee_tau_pred, hip_tau_gauge_pred, knee_tau_gauge_pred` (test strides only) |
| `model/2D_gait_x2.osim` | K4 | — | OpenSim model |
| `coords/<ID>_<stride>.sto` | K4 | time point | model coordinate names, radians |
| `moco/<ID>_<condition>_mean_<case>_m<mesh>.sto` | K5, K7, K8 | — | MocoTrajectory of a mean stride. Single strides later: `<ID>_<stride>_<case>` |
| `moco/summary.csv` | K5, K7, K8 | solve | see below |
| `moco/moment_vs_torque.csv` | K6 | participant × condition × joint | RMS of the net joint moment, the muscles' moment, the gauge and the motor torque; the exo's share of the net moment and its correlation with it |
| `moco/load_split.csv` | K6 | participant × condition | `r, rmse` between the model's and the measured right-foot share of the vertical force, `stride_sd` (the measured share's stride-to-stride SD), both shares at heel strike |
| `moco/assist.csv` | K7 | participant × condition | effort per case, the changes in %, worst hip/knee RMSE and objective per case, torque rate per actuator, budget used, prices |
| `params.csv` | K6 | participant | `participant, site, sex, age_y, height_m, mass_kg` (measured: `models/exogait/participants.csv`), `model_mass_kg` (62, generic until the model is scaled), `x2_mass_kg, anthropometry, hip_offset_c_deg`, and per controller: stride counts, stride time, kinematic stride length and speed |
| `<ID>_emg.csv` | J6 | stride × phase point | `participant, stride, phase`, one column per muscle (normalised envelope) |
| `ro6/cost.csv` | K9 | stage × participant × host | `stage, participant, host, seconds` |
| `stats/*.csv`, `figures/exogait/*.png` | J7 | — | Tables per hypothesis and mode; figures |

**`<ID>_strides.csv` columns:**
- **Key:** `participant`, `group` (AB/HL; a site label by default, J1 Q12), `stride` (unique
  within participant), `leg` (L/R), `mode` (walk/ramp_up/ramp_down/stairs_up/stairs_down),
  `controller` (TR/SM), `block` (one continuous pass of one condition: J3's rule), `phase`
  (0–100), `t` (s, float64: the raw clock, good inside a stride only, since five files restart
  it). Strides and blocks are numbered in file order.
- **Inputs:** `hip_q, knee_q, hip_qd, knee_qd` (stride leg), `hip_q_other, knee_q_other,
  hip_qd_other, knee_qd_other` (other leg, same instants), `backpack_q, backpack_qd`.
- **Also inputs (from Key):** `phase` (H2), `mode` (H3), `controller` (Q2 default), `group`,
  `leg`. The list is `ALLOWED` in `split.py`, with reasons in `docs/model_inputs.md`.
- **Pending J1 Q11 (online?):** `gait_state` (`gait_state_<leg>`) and `stance_alpha`
  (`StanceInterpolationFactor`). Both encode phase, so H2's no-phase arm drops them too.
- **Pending J1 Q3:** `hip_sm_k, hip_sm_d, hip_sm_q0, hip_sm_qd0`, and the same four for the
  knee.
- **Targets:** `hip_tau, knee_tau` (`JointTorques`, motor side) and `hip_tau_gauge,
  knee_tau_gauge` (the torque at the joint; J1 Q9). Modelled separately, never inputs. A stuck
  gauge channel is NaN.
- **Replay only, never inputs:** `hip_tau_gauge_other, knee_tau_gauge_other` (the other leg's
  joint torque, for K5's `measured` case, which replays the gauge torque).
- **Not carried at all:** desired torque, the three interaction-force families, `step_number_*`
  (a session counter), `SM_Gui_Parameter`, `SmoothedStanceInterpolationFactor`.

**`moco/summary.csv` columns** (one row per solve; a re-solve appends, so take the last row per
key): `participant, condition, case` (none/measured/ideal/optimised, later ai/emg), `target`
(mean; later a stride id), `n_mesh, T, strides`; `success, status, iterations, solve_s,
peak_mem_gb, objective`; the settings `track_w, pelvis_w, ankle_w, tol, warm_start`;
`rmse_<coordinate>` (deg); per exo actuator `replay_rmse_` (Nm, prescribed cases),
`exo_rms_` (Nm), `exo_int2_` and `exo_budget_` (Nm² s), `exo_rate_rms_` (smoothness, Nm/s);
`reserve_rms_<coordinate>` (Nm, or N for the pelvis translations); `effort` (the sum of squared
muscle activations integrated over the stride, recomputed from the solution, never the
objective value) and `mean_activation`; `stride_len_fk, stride_len, speed`; ankle and lumbar
ranges, `min_pelvis_ty`, `peak_grf_bw_<side>`; `check` (ok, or the first plausibility check
that failed); `host, commit`.

**Population folds** are leave-one-participant-out and need no column. The fold for
participant P:
- trains on the other participants' `train` blocks;
- tunes on their `val` blocks;
- scores P's `test` blocks, the same strides its personalised model is scored on, so H1 is
  paired.

`evaluate.py` implements exactly this.

## Handoffs

| From | To | What | File |
|---|---|---|---|
| Jasith J1b | K6 | Per-participant mass and height, or "none published" | `notes/observations.md` |
| Jasith J2 | K4 | Column meanings, units, signs, condition labels | `docs/exogait_data.md` (PR #7) |
| J3 (Kurian) | K2 | Preprocessing code, run on all 19 | `src/exogait/preprocess.py` |
| J4 (Kurian) | K2, K3 | Splits, leakage self-check, allowed inputs | `split.py` (`ALLOWED`), `splits.csv` and `split_counts.csv`, `docs/model_inputs.md` |
| J5 (Kurian) | K3 | Metric function, results format, ablation loop | `src/exogait/evaluate.py` |
| K2 | Jasith (review, J7) | Processed data and splits, all 19 | `data/processed/exogait/` (134 MB; regenerate with `preprocess.py all`, or a zip outside git) |
| K3 | K7 | Predicted torque on test strides | `predict/<model>_<ID>_pred.csv` |
| Jasith J6 | K8 | Per-stride EMG features | `<ID>_emg.csv` |
| K3, K9 | Jasith J7 | Results for statistics and figures | `predict/*.csv`, `moco/summary.csv`, `ro6/`, `split_counts.csv` |
| K4, K5 | Jasith | Plots to review for signs and joint limits (a second pair of eyes) | `results/exogait/plots/*.png` |

## Order

1. **Now:** merge the open PRs (#6, #7, #8, #9, then the K5–K7 one). Ask the supervisors for
   DGX access (K9 at full scale). K4 waits only on Jasith's plot check.
2. **Done 2026-11-10:** J3–J5 and K2. **Next: K3**, on the validation blocks. The test blocks
   are scored once, in one final `--test` pass for every model.
3. K5 on single strides (the strides file is there now) and on ramps (tilted floor). K7's `ai` case
   once K3 has predictions.
4. K9. K8 when EMG arrives; if none by 2026-12-01, K8 closes as not possible.

Sync after each stage. Anything that changes a handoff (column names, file formats, splits) gets
a team message before it changes.

---

## Shared rules

- **Python only, no MATLAB** (no licence; `notes/decisions.md`, 2026-10-28). The mentor is
  informed through J1. Code goes in `src/exogait/` (Code layout).
- **One environment on both machines**, the micromamba env `opensim` (ONBOARDING §2):

  ```bash
  micromamba create -n opensim -c opensim-org -c conda-forge python=3.11 opensim=4.6 \
      "libblas=*=*openblas" numpy scipy pandas pyyaml matplotlib scikit-learn
  # Jasith, CPU only:
  micromamba run -n opensim python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  # Kurian, RTX 2050: the CUDA wheel (a CUDA tag no newer than nvidia-smi shows; it shows 13.1)
  micromamba run -n opensim python -m pip install torch --index-url https://download.pytorch.org/whl/cu126
  micromamba run -n opensim python -c "import torch; print(torch.cuda.is_available())"
  ```

  Kurian's existing env needs only
  `micromamba install -n opensim -c opensim-org -c conda-forge scikit-learn "libblas=*=*openblas"`
  and the CUDA torch line. If a CPU wheel is already there, run
  `micromamba run -n opensim python -m pip uninstall -y torch` first.
- **Traps** (`notes/observations.md`):
  - Use OpenBLAS, never MKL: MKL breaks OpenSim's IPOPT.
  - Never conda-install casadi into this env (Moco bundles its own). Never import opensim and
    casadi in one process.
  - Run through `micromamba run` (or an activated shell), or the solver plugins are not found.
  - Keep the solve result alive: `res = inv.solve(); sol = res.getMocoSolution()`, never
    `inv.solve().getMocoSolution()` (access violation).
  - Parallel Moco workers each run in their own working directory (suspected collision, 1
    failure in 18).
  - Use `python -u` for background runs.
- **torch and opensim stay in separate processes.** They did work in one process in the D4 smoke
  run (Windows, 2026-10-02, `notes/results.md` §6b) and in the Docker build check. But the K1
  env has not been tried with torch, the CUDA wheel with opensim is untested, and nothing in
  this plan needs both. The opensim files (`x2model`, `track`, `assist`) and the torch files
  (`lstm`, `evaluate`) hand off through CSV and `.sto`.
- **How to run:** from the repo root,
  `micromamba run -n opensim python -u src/exogait/<file>.py [IDs]`. Each file's `__main__` is
  its assert-based self-check, and it must pass before a PR.
- **Self-checks are small.** They finish in about a minute on synthetic or one-participant data:
  - `lstm.py` trains a few epochs on a toy sequence;
  - `evaluate.py`'s self-check runs phase mean and ridge only. Forests, GPR and the LSTM run
    only with `--models rf,bag,gpr,lstm`, on Kurian's machine;
  - the exceptions are `track.py` and `assist.py`, whose self-check is one solve: Kurian's
    machine only.
- **MATLAB-readable outputs:** every handoff and result is `.csv`, `.sto` or `.osim` (plus
  `.png`). Model weights (`.joblib`, `.pt`) are Python-only and regenerable, never a handoff. No
  `.npz`, `.pkl` or `.parquet` handoffs.
- **Raw data is never edited and never committed.** `data/` and `results/` stay gitignored.
  Processed files are shared outside git as one zip, which K2 regenerates when `preprocess.py`
  changes.
- Work on a branch, merge through a PR, commit under your own name. Log findings in `notes/`.
  Minimal code: reuse the existing helpers, no unrequested abstractions.

## Parked (not in the mentor's plan, or dropped)

- **MATLAB: dropped** (2026-10-28). No `matlab/` folder, no `configureOpenSim.m`. A port happens
  only if a licence appears. The Moco scripts would keep their API names, and every file the
  port needs is already MATLAB-readable.
- **The DGX/Docker/Kubernetes setup: parked for D1–D4, expected for K9 at full scale.** It is
  Python, so it fits this plan: K9 beyond the default scope (all strides, ~1,000 CPU-hours), and
  K3 or a 3D stairs model if needed. It needs the supervisors' cluster access
  (`docs/RUN_ON_DGX.md`), requested now (Order 1).
  - Reusable: `docs/Dockerfile.opensim`, the same stack as our env (OpenSim 4.6, Python 3.11,
    OpenBLAS, CUDA torch). Add scikit-learn to its conda line on first use.
  - Its CI check (`.github/workflows/docker-check.yml`) runs the parked pipeline's
    `run_pipeline.sh check` on every PR, the ExoGait ones included. When the DGX is revived,
    point it at the `src/exogait/*.py` self-checks instead.
  - Also reusable: the shard/resume/collect/commit-stamp pattern of `src/jobs/sweep.py`, and the
    `deploy/` manifests as templates.
  - Not reusable: the `run_pipeline.sh` stages and `configs/`, which are D1–D4 only.
- The D1–D4 synthetic sweep, surrogate and RL policy.
- The Phase C "8.6%" result. It leaned on an ankle actuator that the X2 does not have.
- The fatigue model and per-muscle allocation are kept only as a possible extension. They come
  back only if the mentor agrees (J1 Q6).

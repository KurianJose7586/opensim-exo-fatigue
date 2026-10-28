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
| RO1 | Reproducible preprocessing pipeline for ExoGait | Jasith builds (J3), Kurian runs at scale (K2) |
| RO2 | Participant-specific AI models for exo torque | Both (baselines Jasith J5, nonlinear Kurian K3) |
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
| `track.py` | K5, K6 | opensim | MocoTrack per stride (the `measured` case); `params.csv`; ID moments vs X2 torque |
| `assist.py` | K7, K8, K9 | opensim | The `none`, `ai`, `optimised` and `emg` cases, and the at-scale loop |
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
| K1 | Environment and data | — | M | **done** (PR #6, approved, not merged). MATLAB part dropped. Env follow-up below |
| K2 | Preprocessing at scale (RO1) | J3 (preprocess); J4 (`split.py`, for the last done-when bullet) | L | todo |
| K3 | Nonlinear torque models (RO2, H1–H3) | K2, J4, J5 | L | todo |
| K4 | OpenSim model and X2 mapping (RO3) | K1, J2 | L | **in progress** |
| K5 | MocoTrack: reproduce the gait | K4 | L | todo |
| K6 | Personalised twin state (Layer 4) | K5; J1b (soft: generic anthropometry is the default) | M | todo |
| K7 | AI + Moco integration (RO4, H4) | K3, K5, K6, J1 Q5 | L | todo |
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
- **Follow-up (S, now):** add scikit-learn and the CUDA torch wheel to the env (Shared rules).
  Done when `torch.cuda.is_available()` prints True. torch and opensim stay in separate
  processes (Shared rules), so no one-process test is needed.

### K2 — Preprocessing at scale (RO1)

- **Code:** J3's `src/exogait/preprocess.py`, then J4's `src/exogait/split.py`. Fixes that scale
  needs go back through a PR that Jasith reviews.
- **Run:** `micromamba run -n opensim python -u src/exogait/preprocess.py all` as soon as J3
  lands, and `split.py all` once J4 lands. Sequential is fine: about a minute per participant to
  read with `usecols`, as `checks.py` does. One participant in memory at a time, only the
  needed columns.
  - **`time` stays float64.** The raw clock runs to 1,234–4,855 s, where float32 resolves only
    0.12–0.49 ms: it turns 0–33 real dt ≤ 0 per file into up to 1,238. float32 only for angle,
    velocity and torque columns.
- **Known traps (J2, checked on all 19):** AB72's column order; every HL file (33 dt ≤ 0 each,
  `*_UNDEFINED2` labels); 1–3 dt ≤ 0 in AB69/72/76/80/82; removed rests up to 352 s; two sites
  (Chicago and Madrid) with different stairs and ramps.
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

### K4 — OpenSim model and X2 mapping (RO3) · in progress

- **Code:** `src/exogait/x2model.py`, opensim Python API. Reuse from `twin.py`:
  - `components()`;
  - the device-mass pattern of `_body_model`;
  - the exo `CoordinateActuator` pattern of `_add_exo`, for hip and knee only;
  - reserves at every coordinate (`ModOpAddReserves(..., False)`, decisions.md 2026-10-02).
- **Model:**
  - `models/base/2D_gait.osim`, sagittal, as the mentor suggests. Generic anthropometry, stated:
    ExoGait has none.
  - X2 mass from Kucuktabak et al., IEEE T-RO (arXiv 2301.06244), Table II: backpack 10.3 kg,
    plus thigh and shank links per leg.
  - Hip and knee exo actuators, both legs, bounded by the X2 torque limits (cite the source).
- **Mapping:**
  - `hip_flexion_{l,r}` = `JointPositions_{1,3}` and `knee_angle_{l,r}` = `JointPositions_{2,4}`.
    Same signs as OpenSim, radians (J2; `checks.py` asserts it).
  - The X2 hip angle is relative to the backpack: thigh angle = `BackPackAngle` − 90° + hip.
    Pelvis tilt therefore comes from `BackPackAngle`. Check it against the model's reference
    tilt of about −15°.
  - The ankle is not recorded. Use the stock reference ankle, time-normalised to the stride and
    loosely tracked (the J1 Q7 default). Write the choice down.
  - Stride = right heel strike to right heel strike, where `gait_cycle_right` wraps 99 → 0. J3
    uses the same rule. Once `preprocess.py` lands, `x2model.py` imports its stride function
    and drops its own.
  - **Torque sign:** J2 covered angles only. Check the `JointTorques` sign against the OpenSim
    coordinate sign here, before K5 replays it.
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
  - `results/exogait/coords/<ID>_<stride>.sto`;
  - plots in `results/exogait/plots/` for Jasith to review.
- **Done when:**
  - the model loads and its coordinate list is verified;
  - one participant's hip/knee trajectories map with sensible signs (plot checked by Jasith);
  - the self-check asserts the added device mass, and that there are 4 exo actuators and none
    at the ankle;
  - the `JointTorques` sign vs the OpenSim coordinate sign is checked on one SM walking stride
    (the SM impedance pushes toward `SM_Equilibrium_Angle`; cross-check with
    `twin.net_moments()` if that is ambiguous) and written into `docs/exogait_data.md`;
  - the zero-offset **[open]** line in `docs/exogait_data.md` is updated with the result.

### K5 — MocoTrack: reproduce the gait

- **Code:** `src/exogait/track.py`, starting from the `example2DWalking.py` set-up K1 already
  runs, with its bounds and time window replaced (below). The first goal is reproduction, not
  optimisation.
- **Problem:**
  - One full right stride, with both legs' recorded angles. Initial and final time come from
    the stride: the median is 2.9 s, against the example's 0.47 s half-cycle. The example's
    symmetry trick is not needed.
  - **Replace the example's bounds:** knee −120°…10° (the model's range; the example stops at
    −50°), hip from the data range (the X2 reaches −18°), `pelvis_tilt` from `BackPackAngle` ±
    10°, `pelvis_tx` unbounded above.
  - No GRF tracking (ExoGait has no GRF; weight 0, as in K1).
  - No hard periodicity: a real stride is not periodic.
  - The exo actuators replay the measured X2 torque (`hip_tau, knee_tau` and
    `hip_tau_other, knee_tau_other` of the right stride in `<ID>_strides.csv`), in both modes,
    since TR torque is not near zero. Use `MocoControlTrackingGoal`: the PrescribedController
    route was infeasible before (decisions.md 2026-10-02). It is a soft goal, so `summary.csv`
    records `exo_replay_rmse` per joint. **This solve is K7's `measured` case.**
  - **TR caveat:** in TR the replayed torque includes compensation for X2 friction and inertia
    that the model lacks. Report TR results separately. They count for H4 only if K6's TR check
    supports it.
- **Ramps:** rotate the floor `ContactHalfSpace` by the site's ramp angle per solve (5° Chicago,
  6° Madrid; the site comes from J1 Q12; the sign comes from up or down).
- **Cost first:** on one walking stride, record solve time and peak memory, and compare a mesh
  interval of 0.04–0.05 s with Moco's default 0.02 s. Keep the coarser one if the tracking RMSE
  barely changes. K9's scope rests on these numbers.
- **Order:** one walking stride (cost), then walking for one participant, TR then SM. Then ramps.
  Stairs only after J1 Q10.
- **Out:** `results/exogait/moco/<ID>_<stride>_measured.sto` and a row in
  `results/exogait/moco/summary.csv`.
- **Done when:**
  - walking is tracked, with tracking RMSE reported per joint;
  - the self-check asserts plausibility: joint limits, signs, no tracked coordinate on a bound,
    exo torque within the X2 limits, `exo_replay_rmse` below 1 Nm, per-joint reserves small next
    to the net moment;
  - solve time, peak memory and the chosen mesh interval are recorded in
    `notes/observations.md`.

### K6 — Personalised twin state (Layer 4)

- **Code:** `track.py`.
- **State estimation:** MocoTrack (K5) reconstructs the states ExoGait does not record (pelvis
  translation, ankle, muscle states) from the recorded hip, knee and backpack angles. Write
  down which states are measured and which are estimated.
- **Calibration:**
  - **Per-participant parameters:** body mass and height if the papers list them (J1b), else
    generic, stated. X2 masses from K4.
  - **Moment vs torque:** net hip and knee moments from an ID-equivalent solve vs the measured
    X2 torque, **in SM and in TR**. Use the `twin.net_moments()` pattern (muscles removed,
    reserves only). Magnitude only: K4 fixed the sign.
  - **TR:** write down whether TR torque looks like assistance or mostly device compensation.
    K5 and K7 use the TR `measured` case for H4 only if it is the former.
  - A fitted calibration (e.g. muscle strength scaled to the measured torque) is out of scope:
    there are no GRF or anthropometrics to fit against.
- **Out:** `results/exogait/params.csv`, one row per participant; a PNG of moment vs torque per
  mode.
- **Done when:** there is a params row per participant, the comparison is plotted for at least
  one participant in both modes, and the TR conclusion is in `notes/observations.md`.

### K7 — AI + Moco integration (RO4, H4)

- **Code:** `src/exogait/assist.py`. It imports opensim only and reads K3's predictions from CSV.
- **Cases, per stride:**

  | Case | Exo torque |
  |---|---|
  | `none` | off |
  | `measured` | measured X2 torque replayed: K5's solve (the proposed H4 baseline) |
  | `ai` | K3's predicted torque replayed (full-input, personalised, the model K3 ranks best on validation) |
  | `optimised` | Moco picks the hip and knee torque within the X2 limits and the `measured` budget, warm-started from `ai` |

- **`optimised` needs a budget.** It is the Dembia ideal-device formulation in `twin._add_exo`,
  whose device is nearly free (`EXO_WEIGHT` = 1e-3). The measured torque is a feasible point of
  that problem, so without a budget `optimised` beats `measured` by construction and H4 cannot
  fail.
  - The budget: per exo actuator, the integral of squared torque over the stride is no more
    than the measured profile's. Set it as a `MocoControlGoal` on that actuator's control in
    endpoint-constraint mode. The self-check asserts it holds.
  - An unbudgeted run, if made, is reported as an upper bound on the achievable reduction, never
    as the H4 test (J1 Q5).
- **Strides:** `ai` and `optimised` run only on right test strides whose overlapping left strides
  are also test strides with predictions. The left-leg torque is stitched from those two left
  strides on `t` and interpolated. In-sample predictions are never used.
- **Effort:** the sum of squared muscle activations (the J1 Q5 default), integrated over the
  stride and recomputed from each solution, the same way for every case. Never the Moco
  objective value, which includes the tracking terms.
- **Constraints:** the X2 torque limits as actuator bounds; a tracking-error bound asserted on
  every solve; `exo_replay_rmse` below 1 Nm for `ai`, as for `measured`. For a shared hip/knee
  budget, see the `allocate.candidates()` note in Code layout.
- **TR:** as in K5, TR results are reported separately.
- **Out:** a `.sto` per solve, and rows in `results/exogait/moco/summary.csv`.
- **Done when:** the effort change of `optimised` vs `measured` and vs `none` is shown, with the
  tracking bound, the X2 limits and the budget satisfied and `smoothness` reported per joint, on
  at least one participant and mode.

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
  - `multiprocessing.Pool` with one single-threaded Moco per worker, as `sweep.py` does. Each
    worker chdirs to its own temp dir (as in `sweep._run_one`) and names its MocoTrack per task,
    since Moco writes its stop file and `<name>_tracked_*.sto` into the cwd. RAM sets the worker
    count: K5 measured one solve's peak memory.
- **Scope:** one ExoGait stride lasts about 2.9 s (median of 3,166 right strides on walking and
  ramps), 6× the example's half-cycle, so expect minutes per solve.
  - **Default:** up to 5 eligible right test strides per participant × mode × controller
    (19 × 3 × 2 × 5 = 570 strides × 4 cases, about 2,300 solves) at K5's mesh interval. At a few
    minutes per solve that is days on this machine, not a night.
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
| `<ID>_stride_features.csv` | J3, K2 | kept stride | key columns, duration, ROM, peak and RMS torque per joint. Descriptive only, never model inputs |
| `<ID>_excluded.csv` | J3, K2 | dropped stride | `participant, leg, condition, t_start, t_end, reason` |
| `summary.csv` | K2 | participant × mode × controller × leg | `detected, kept`, one count column per exclusion reason |
| `splits.csv` | J4 (AB68 + HL03), K2 (all 19) | stride | `participant, stride, block, split` (train/val/test) |
| `split_counts.csv` | J4 (AB68 + HL03), K2 (all 19) | participant × mode × controller | blocks and strides per split, `personalised` (False under 2 blocks) |
| `predict/<model>.csv` | J5, K3 | model × scheme × ablation × participant × mode × controller × joint × split | `rmse, mae, r2, nrmse, infer_ms` (per stride), `n_strides, host, commit` |
| `predict/<model>_<ID>_pred.csv` | K3 | stride × phase point | `participant, stride, leg, scheme, ablation, phase, t, hip_tau_pred, knee_tau_pred` (test strides only) |
| `model/2D_gait_x2.osim` | K4 | — | OpenSim model |
| `coords/<ID>_<stride>.sto` | K4 | time point | model coordinate names, radians |
| `moco/<ID>_<stride>_<case>.sto` | K5, K7, K8 | — | MocoTrajectory |
| `moco/summary.csv` | K5, K7, K8 | solve | see below |
| `params.csv` | K6 | participant | `participant, group, body_mass_kg, height_m, mass_source` (paper/generic), `backpack_kg, thigh_link_kg, shank_link_kg` |
| `<ID>_emg.csv` | J6 | stride × phase point | `participant, stride, phase`, one column per muscle (normalised envelope) |
| `ro6/cost.csv` | K9 | stage × participant × host | `stage, participant, host, seconds` |
| `stats/*.csv`, `figures/exogait/*.png` | J7 | — | Tables per hypothesis and mode; figures |

**`<ID>_strides.csv` columns:**
- **Key:** `participant`, `group` (AB/HL; a site label by default, J1 Q12), `stride` (unique
  within participant), `leg` (L/R), `mode` (walk/ramp_up/ramp_down/stairs_up/stairs_down),
  `controller` (TR/SM), `block` (one continuous pass of one condition: J3's rule), `phase`
  (0–100), `t` (s, float64).
- **Inputs:** `hip_q, knee_q, hip_qd, knee_qd` (stride leg), `hip_q_other, knee_q_other,
  hip_qd_other, knee_qd_other` (other leg, same instants), `backpack_q, backpack_qd`.
- **Also inputs (from Key):** `phase` (H2), `mode` (H3), `controller` (Q2 default), `group`.
  Final list in J4's `ALLOWED`.
- **Pending J1 Q11 (online?):** `gait_state` (`gait_state_<leg>`) and `stance_alpha`
  (`StanceInterpolationFactor`). Both encode phase, so H2's no-phase arm drops them too.
- **Pending J1 Q3:** `hip_sm_k, hip_sm_d, hip_sm_q0, hip_sm_qd0`, and the same four for the
  knee.
- **Targets:** `hip_tau, knee_tau` (`JointTorques`). `hip_tau_gauge, knee_tau_gauge` are the
  candidate target of J1 Q9, never an input.
- **Replay only, never inputs:** `hip_tau_other, knee_tau_other` (the other leg's measured
  torque, for K5's `measured` case).
- **Not carried at all:** desired torque, the three interaction-force families, `step_number_*`
  (a session counter), `SM_Gui_Parameter`, `SmoothedStanceInterpolationFactor`.

**`moco/summary.csv` columns:** `participant, stride, mode, controller, case`
(none/measured/ai/optimised/emg), tracking RMSE per coordinate (deg), reserve RMS per joint
(Nm), peak exo torque per joint (Nm), `exo_replay_rmse` per joint (Nm; `measured` and `ai`),
`smoothness` per joint (RMS of d(exo torque)/dt, Nm/s), `effort` (sum of squared muscle
activations integrated over the stride, recomputed from the solution, never the objective
value), `solve_s, success, host, commit`.

**Population folds** are leave-one-participant-out and need no column. The fold for
participant P:
- trains on the other participants' `train` blocks;
- tunes on their `val` blocks;
- scores P's `test` blocks, the same strides its personalised model is scored on, so H1 is
  paired.

This is the default; J4 may change it.

## Handoffs

| From | To | What | File |
|---|---|---|---|
| Jasith J1b | K6 | Per-participant mass and height, or "none published" | `notes/observations.md` |
| Jasith J2 | K4 | Column meanings, units, signs, condition labels | `docs/exogait_data.md` (PR #7) |
| Jasith J3 | K2 | Preprocessing code tested on AB68 + HL03 | `src/exogait/preprocess.py` |
| Jasith J4 | K2, K3 | Splits, leakage self-check, allowed inputs | `split.py` (`ALLOWED`), `splits.csv` and `split_counts.csv` (AB68 + HL03), `docs/model_inputs.md` |
| Jasith J5 | K3 | Metric function, results format, ablation loop | `src/exogait/evaluate.py` |
| K2 | Jasith J5 (and J4 for review) | Processed data and splits, all 19 | `data/processed/exogait/` (zip, outside git) |
| K3 | K7 | Predicted torque on test strides | `predict/<model>_<ID>_pred.csv` |
| Jasith J6 | K8 | Per-stride EMG features | `<ID>_emg.csv` |
| K3, K9 | Jasith J7 | Results for statistics and figures | `predict/*.csv`, `moco/summary.csv`, `ro6/`, `split_counts.csv` |
| K4, K5 | Jasith | Plots to review for signs and joint limits (a second pair of eyes) | `results/exogait/plots/*.png` |

## Order

1. **Now:** merge PRs #6 and #7. Do the K1 env follow-up. Ask the supervisors for DGX access
   (K9 at full scale). Finish K4, including the torque sign. Then K5: one walking stride for
   cost, then walking TR, then SM.
2. Run K2's preprocessing as soon as J3 lands; run `split.py` on all 19 once J4 lands; then K3.
3. K6, K7. Add ramps to K5 meanwhile, on the tilted floor.
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

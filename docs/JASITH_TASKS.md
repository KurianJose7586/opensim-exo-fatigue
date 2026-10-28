# Jasith — task list

Team plan for the mentor's brief (received 2026-10-14). **Python only since 2026-10-28**: the
college has no MATLAB licence (`notes/decisions.md`). Kurian's half is in
[`KURIAN_TASKS.md`](KURIAN_TASKS.md), along with what applies to both of us:
- the mentor's layers, objectives (RO1–RO6) and hypotheses (H1–H5), with owners;
- the code layout and the file formats;
- the shared rules, including the one env recipe;
- what is parked.

## Why the split looks like this

Jasith's laptop cannot sustain long heavy runs. **Kurian takes everything compute-heavy**:
- the full 5.5 GB dataset
- tree ensembles, LSTM and GPR training
- every OpenSim/Moco solve
- the integration and final evaluation runs

Jasith takes work that runs on one or two participants or on already-processed data:
- understanding the data (done, J2)
- the preprocessing code, developed on two participants
- splits and leakage rules
- the two baseline models and the shared metrics
- EMG features (blocked until EMG arrives)
- mentor alignment, statistics, docs and the write-up

**Laptop limits:**
- **Raw data: AB68 (221 MB) and HL03 (205 MB) only.**
  - Load them with `pd.read_csv(usecols=[...])`, by column name, never by index.
  - **`time` stays float64**, and dt, gaps and the 101-point resampling are computed in
    float64. float32 only for angle, velocity and torque columns. (In float32 the clock cannot
    resolve 3 ms samples cleanly: HL03's 33 dt ≤ 0 become 561.)
  - That is enough: `checks.py` reads AB68 this way in about a minute.
  - Read in chunks only if the laptop still runs out of memory. A stride can cross a chunk
    boundary, so chunks cost code.
- **Processed data for all 19 is fine.** It is expected at tens of MB per participant (K2
  records the real size). J4, J5 and J7 run on it.
- **Never on the laptop:** Moco/OpenSim solves; LSTM, GRU or GPR training; tree ensembles on
  the full set. Anything that runs longer than about 15 minutes goes to Kurian.
- **Env:** the same env as Kurian's, with the CPU torch wheel (Shared rules). torch is there
  only so that `lstm.py`'s self-check (a few epochs on a toy sequence) runs when you review it.
  `evaluate.py` without `--models` runs phase mean and ridge only, so it is safe here.

---

## Tasks

| ID | Task | Depends on | Size | Status |
|---|---|---|---|---|
| J1 | Mentor alignment: Python notice + questions | — | S | todo: send now |
| J1b | Paper check: per-participant body mass and height | — | S | todo: now |
| J2 | Dataset study | — | M | **done**: `docs/exogait_data.md`, PR #7 (approved, not merged) |
| J3 | Preprocessing code (RO1) | J2 | L | todo |
| J4 | Splits and leakage audit | J2, J3 | M | todo |
| J5 | Baselines and shared metrics (RO2) | J3, J4; K2 for the full run | M | todo |
| J6 | EMG features (RO5) | J3 | M | **blocked**: no EMG (Q8). Closes as not possible if none by 2026-12-01 |
| J7 | Statistics and figures (H1–H4, RO6) | J5, K3, K9 | M | todo |
| J8 | Realign the docs and remove MATLAB | J1 (only for the title) | M | todo: the MATLAB part can go now |
| J9 | Literature and write-up | J5, J7 | L | todo |

Sizes: S = a day or two, M = about a week, L = more than a week.

### J1 — Mentor alignment

Send notice 1 and questions 2–12 below. Record the answers in `notes/decisions.md`. If
`docs/progress_update.md` was sent, or if the supervisors are not the mentor, send them notice 1
as well: it withdraws the MATLAB request.
**Done when** every question has an answer, or we proceed on the written default.

### J1b — Paper check for K6

Check the ExoGait paper and the X2 paper (Kucuktabak et al., arXiv 2301.06244) for
per-participant body mass and height. Record the values, or "none published", in
`notes/observations.md`. K6 uses them; generic anthropometry is the default.
**Done when** the note is in.

### J2 — Dataset study · done

`docs/exogait_data.md` (PR #7) covers:
- every column with its unit and sign;
- the condition labels;
- timing quirks and knee ranges;
- the leakage table.

It is checked against the CSVs by `src/exogait/checks.py`. Its open items go to J1 (Q2; Q3,
which carries the SM units; Q4, Q8, Q9; Q11 for `gait_state` and the stance factor; Q12 for AB
vs HL) and to K4 (the hip zero offset, and the torque sign, which J2 did not cover). The
interaction-force units do not matter: those columns are not carried.

### J3 — Preprocessing code (RO1)

- **Code:** `src/exogait/preprocess.py`. Developed and tested on AB68 + HL03 on the laptop;
  Kurian runs it on all 19 (K2). CLI as in `checks.py`:
  `python src/exogait/preprocess.py AB68 HL03`, or `all`.
- **Stack:** pandas (`usecols` by name; `time` float64, float32 only for angle, velocity and
  torque) and numpy (`np.interp` to resample). `scipy.signal` only if a filter turns out to be
  needed: velocities are recorded.
- **Steps (the mentor's):**
  1. **Load** by column name and drop the leading unnamed index column. The raw file is only
     read.
  2. **Conditions, gaps and blocks.**
     - Exclude `UNDEFINED` and `*_UNDEFINED2` rows.
     - `block` = one continuous pass of one condition. It increments only at a condition change
       (including the `UNDEFINED` rows between passes) or at a removed rest (gap over 0.1 s).
       J4 splits on it.
     - A dt ≤ 0 (33 in every HL file, 1–3 in AB69/72/76/80/82) or a dropped-sample glitch drops
       the strides it touches, but keeps the block number.
     - "Sync" has nothing to align until EMG arrives: every column shares `time`.
  3. **Strides per leg.** A heel strike is where `gait_cycle_<leg>` wraps 99 → 0. K4 already
     uses this rule, and imports this function once it lands, so there is one implementation.
     Drop and log strides that:
     - cross a gap, a dt ≤ 0 or a condition change;
     - have an outlier duration;
     - have dropped samples beyond a threshold you set and write down (6.6% of AB68 intervals
       are over 4.5 ms).
  4. **Resample** each stride to 101 points on `time` (float64), not on the integer
     `gait_cycle`. The other leg's angles, velocities and torque go onto the same instants
     (the `*_other` columns).
  5. **Per-stride features:** duration, ROM, and peak and RMS torque per joint.
  6. **No splitting:** that is J4.
- **Out:** `<ID>_strides.csv`, `<ID>_stride_features.csv` and `<ID>_excluded.csv` in
  `data/processed/exogait/`. Columns as in [File formats](KURIAN_TASKS.md#file-formats). The
  banned columns are not carried at all.
- **Self-check** (asserts, run on AB68 and HL03):
  - `time` is float64 (`assert d.time.dtype == 'float64'`);
  - no stride crosses a gap or a dt ≤ 0;
  - phase is strictly increasing;
  - every kept stride has 101 rows;
  - kept + excluded = detected;
  - no banned column is in the output.
- **Done when** it runs on AB68 and HL03 with the self-check passing, and the PR is merged after
  Kurian's review.

### J4 — Splits and leakage audit

- **Code:** `src/exogait/split.py`. It writes `splits.csv` and `split_counts.csv`, and holds
  `ALLOWED`, the input columns models may use. Its self-check asserts:
  1. every (participant, block) maps to exactly one split;
  2. no test stride's [t_start, t_end] overlaps a train or val stride of the same participant,
     on either leg (left and right strides overlap by about half a stride);
  3. every participant × mode × controller has at least 1 train and 1 test block, or is listed
     with `personalised` False.
- **Block assignment:** whole blocks, per participant × mode × controller, chronologically: the
  last blocks to test, the ones before them to val, the rest to train (by strides, about 20%
  test, 20% val, 60% train).
  - A condition with fewer than 3 blocks gets no val block. The participant's pooled model
    (below) is tuned on the val blocks of its other conditions.
  - A condition with fewer than 2 blocks goes to train. It is excluded from personalised testing
    and from the H1 pairs, and listed in `split_counts.csv` with its count.
  - Never random strides: neighbouring strides are near copies.
- **Personalised model:** one model per participant, pooled across modes and controllers (H3
  needs mode as an input), trained on that participant's train blocks.
  - Within-participant test blocks are later passes of the same session and donning, not a new
    session. State this as a limit of H1.
- **Population model:** leave one participant out. The default fold for participant P:
  - trains on the other participants' `train` blocks;
  - tunes on their `val` blocks;
  - scores P's `test` blocks, the same strides the personalised model is scored on, so H1 is a
    paired comparison.
- Validation is for tuning only.
- **Stairs** are short: 4–9 complete strides per leg per condition in AB68. The counts for all 19
  come from K2's `split_counts.csv`, not from AB68. Report stairs separately.
- **`docs/model_inputs.md`:** every column marked allowed or banned, with a reason (leakage notes
  below).
- **Done when** `splits.csv`, `split_counts.csv` and the self-check run on AB68 + HL03, and
  `docs/model_inputs.md` lists every column.

### J5 — Baselines and shared metrics (RO2, mandatory models)

- **Code:** `src/exogait/evaluate.py`, which K3 then uses unchanged. It holds:
  - **`metrics(y, yhat)`:** RMSE, MAE, R² and nRMSE (RMSE / range of the measured torque in that
    participant × mode × joint; state the choice), plus inference time per stride, measured
    around `predict`.
  - **A results writer** in the fixed format (File formats), with a `host` column, used by
    every model, K3's included.
  - **The ablation loop:** H1 personalised vs population; H2 with vs without `phase` (the no-phase
    arm also drops `gait_state` and `stance_alpha`, which encode phase); H3 with vs without
    `mode`. Per participant, mode and controller. H2 runs on the per-row models only: the LSTM's
    H2 arm is not applicable (K3).
  - **The two baselines:**
    - phase-conditioned mean: a pandas `groupby` mean of the training torque over mode,
      controller and phase;
    - ridge: `make_pipeline(StandardScaler(), Ridge())`, so the scaler is fitted on train only.

    K3 adds its models to the same model list, behind `--models`. The default (and the
    self-check) is phase mean and ridge.
- **Where it runs:** light enough for the laptop. Develop on AB68 + HL03 processed locally, then
  run on K2's 19. Kurian re-runs the final `--test` pass on his machine for the RO6 timings
  (K9).
- **Done when** baseline results rows exist per participant, mode and controller for every
  ablation, and K3 can call `evaluate.py` unchanged.

### J6 — EMG features (RO5) · blocked

- **Blocked:** the Dryad release has no EMG (Q8). This starts when the authors or the mentor
  supply it. If none arrives by 2026-12-01, J6 closes as not possible (Q8 default).
- **Code:** `src/exogait/emg.py`, using `scipy.signal`. Steps:
  - band-pass, rectify, low-pass envelope;
  - normalise, and state the method: per-muscle peak of the participant's walking, or MVC if
    supplied;
  - resample onto J3's strides (same `stride`, 101 points).
- **Check the EMG sampling rate first.** At the X2's 333 Hz the usual 20–450 Hz band is
  impossible.
- Label them muscle-activity features. They are **not** fatigue measures, as the mentor's brief
  stresses.
- **Out:** `<ID>_emg.csv` for the EMG subjects, with a self-check, handed to Kurian for K8.
- **Done when** `<ID>_emg.csv` exists for every EMG subject in `data/processed/exogait/`, its
  self-check passes, and K8 reads it.

### J7 — Statistics and figures for H1–H4 (and RO6 tables)

- **Code:** `src/exogait/stats.py`. Runs on the laptop: the results files are small.
  - Paired comparisons across participants with `scipy.stats.wilcoxon`:
    - H1–H3 on per-participant RMSE: personalised vs population on the same test strides; with
      vs without `phase`; with vs without `mode`;
    - H4 on per-participant effort: the budget-matched `optimised` vs `measured` (the test), and
      vs `none`.
  - **One primary endpoint per hypothesis:** walking, both controllers pooled, the mean of hip
    and knee RMSE. For H4: walking effort, SM (TR added only if K6 supports it). Everything else
    is secondary, Holm-corrected across every mode × controller × joint comparison reported for
    that hypothesis.
  - Effect size as the matched-pairs rank-biserial correlation.
  - Report n (pairs) per mode. Stairs tests use only participants with test strides there
    (`split_counts.csv`).
  - matplotlib figures.
- **In:** `results/exogait/predict/*.csv`, `results/exogait/ro6/` (with `moco/summary.csv`) and
  `split_counts.csv`.
- **Out:** `results/exogait/stats/*.csv` and `figures/exogait/*.png`.
- **Done when** H1–H4 each have a test, a p-value, an effect size and one figure, and the RO6
  summary tables from K9 exist.

### J8 — Realign the docs and remove MATLAB

- Rewrite `README.md` and `PROJECT_GUIDE.md` around the mentor's plan, in Python. Archive the
  current guide as `docs/guide_v3_fatigue_twin.md`.
- Mark D1–D4 as parked, and the DGX setup as parked but expected for K9 at full scale.
- **Remove MATLAB as the plan** from the lines that still say it:
  - `PROJECT_GUIDE.md`: the title (line 2), "MATLAB orchestration" (41), the MATLAB title-term
    row (66), A1 (116–117), Phase E (263–272), the "MATLAB access delayed" risk (315; now
    realised, cite the decision), next action 2 (327);
  - `README.md`: the "E — MATLAB" row (27), and Setup (52–60), which should point to
    ONBOARDING §2.
- **ONBOARDING §2, lines 27–41:** decide whether the `opensim` env becomes the only set-up. The
  recipe itself, and the §8 MATLAB clause, are updated in the replan PR.
- **The title** changes only if the mentor says the registered title must (notice 1).
- **Done when** a newcomer reading README → PROJECT_GUIDE lands on the ExoGait plan in Python,
  and nothing outside the history (archived guides, `notes/`, `docs/progress_update.md`) still
  says MATLAB is the plan. The one exception is the registered title, if the mentor keeps it:
  then a footnote under it cites `notes/decisions.md` (2026-10-28).

### J9 — Literature and write-up

- **Related work:** exo torque and joint-moment estimation (Molinaro 2024, #32 in `lit_slides/`),
  the ExoGait/X2 paper, MocoTrack.
- **Drafts:** methods for RO1–RO2 and results for H1–H4, each number traceable to a results file.
  The methods name the Python stack and versions, and say why it replaced MATLAB.
- **Limitations:** if no EMG arrives by 2026-12-01, RO5 and H5 were not tested because the data
  was not released (Q8).
- **Done when** the draft sections are in the report.

---

## Notice and questions for the mentor (J1)

1. **Notice, not a question: the project runs in Python, not MATLAB.** Draft:

   > The college has no MATLAB licence (our MathWorks account offers only "Link License", and
   > there is no campus licence to link it to), so we are doing the whole plan in Python. The
   > method does not change. OpenSim/Moco's Python API is generated by SWIG from the same C++ as
   > the MATLAB one, with the same classes and methods. scikit-learn, PyTorch and SciPy replace
   > the Statistics & ML, Deep Learning and Signal Processing toolboxes. Every file we hand over
   > (.osim, .sto, .csv) opens in MATLAB, so a port stays possible if the lab ever provides a
   > licence. The project title says "Using MATLAB–OpenSim Moco": please tell us if it needs a
   > formal change.

2. **Prediction target and transparent mode.** Transparent-mode torque is not near zero:
   `JointTorques` RMS in AB68 walking is 18–20 Nm in TR vs 22–25 Nm in SM. Should we model both
   controllers, with the controller as an input, or SM only?
   *Default: both, controller as an input, results reported per controller.*
3. **State-machine parameters.** May stiffness k and damping d be inputs? With angle and
   velocity they nearly define the SM torque, so the model would be reconstructing the
   controller. Their units are also unconfirmed, which matters only if the answer is yes.
   *Default: excluded.*
4. **Offline phase.** Gait phase is interpolated between heel strikes, so it needs the *next*
   heel strike. So does resampling each stride to 101 points. Is this offline analysis fine, or
   should phase be estimated causally?
   *Default: offline, and stated as such.*
5. **H4 baseline and effort objective.** What are the "specified baseline" and the effort
   objective? Is the objective the sum of squared muscle activations? Should the optimised
   assistance be limited to the same torque budget as the measured torque? Without a budget it
   beats the measured torque by construction.
   *Default: baselines are no assistance and the measured torque replayed in Moco; the objective
   is the sum of squared muscle activations; the optimised torque gets the measured torque's
   budget per joint, and an unbudgeted run is reported only as an upper bound.*
6. **The fatigue model.** Should it stay as an extension, or be dropped?
   *Default: parked.*
7. **Ankle.** The ankle angle is not recorded. Is a reference or loosely tracked ankle
   acceptable in MocoTrack?
   *Default: the stock reference ankle, loosely tracked.*
8. **EMG is missing.** The Dryad release (version 449435) has no EMG files, and none of the 19
   CSVs has an EMG column, although its README says EMG is in separate files. Do you have it? If
   not, we will write to the authors (clhost@ethz.ch, lvianello@sralab.org). Until it arrives,
   J6, K8 and H5 are blocked.
   *Default: we write to the authors this week. If no EMG by 2026-12-01, RO5 and H5 are
   reported as not tested (data not released), K8 and J6 close as not possible, and J9 states
   it in the limitations.*
9. **Which torque column is the target?** `JointTorques` and `JointTorquesViaGauges` are
   uncorrelated (r = −0.20 to 0.02 in AB68 walking), and the gauge torque is nonzero while
   standing.
   *Default: `JointTorques`. The gauge torque is kept in the processed files for a later check.*
10. **Stairs and the 2D model.** Stairs reach 83–114° knee flexion. In `2D_gait.osim` the
    gastrocnemius knee moment arm flips sign near 100°, and the quadriceps arms fall to about
    1.4 cm by 80°. Walking and ramps reach 70–85° per stride, with ramp maxima up to 91° (AB68).
    The model's feet also push on one flat floor: ramps need it tilted (5° or 6°), and stairs
    need step contact geometry. A 3D muscled model (Rajagopal 2015, from
    `opensim-org/opensim-models`) fixes the muscle paths but not the contact. It has no
    foot–ground contact and is normally driven by measured GRF, which ExoGait lacks, so contact
    spheres would have to be added: it is not a drop-in fix. Should we restrict the OpenSim work
    (K4–K9) to walking and ramps, or do you expect stairs in OpenSim?
    *Default: OpenSim on walking, plus ramps on a tilted floor. Stairs stay in the AI models (J5,
    K3), which need no musculoskeletal model.*
11. **Gait state and stance factor.** Are `gait_state_*` and `StanceInterpolationFactor`
    computed online by the X2's state machine, or after the fact like `gait_cycle`?
    *Default: treated as offline, like phase: usable in the offline models, dropped in H2's
    no-phase arm, and excluded from any online claim.*
12. **AB vs HL.** Are AB and HL the two sites (Chicago and Madrid), not clinical groups? The HL
    files start at t = 0 and have about 130–140 sampling intervals over 4.5 ms, against
    12,000–66,000 in the AB files, which fits a different recording set-up.
    *Default: AB = Chicago, HL = Madrid. `group` is a site label (the stairs and ramps differ),
    not a clinical group, and it sets the ramp angle in K5.*

## Leakage notes for J4

- **Desired torque: banned** (mentor's rule; r = 0.87–0.95 with `JointTorques`). Not carried
  into the processed files.
- **Interaction forces** (`InteractionForces_*`, `SmoothedInteractionForces_*`,
  `DesiredInteractionForces_*`): **banned**. `InteractionForces_{i+1}` tracks `JointTorques_i`.
  Not carried.
- **`JointTorquesViaGauges_*`: banned as an input.** Carried only as a candidate target (Q9).
- **The other leg's measured torque** (`hip_tau_other, knee_tau_other`): **banned as an input.**
  Carried only for K5's replay.
- **`SM_*` (k, d, equilibrium angle and velocity): pending Q3.** They are carried, so the answer
  needs no K2 rerun. `SM_Gui_Parameter`: not carried.
- **Gait phase and time normalisation: offline (Q4).**
  - `gait_cycle_*` and `step_complete_*` use the next heel strike, and so does resampling a
    stride to 101 points.
  - Every model on the 101-point table is therefore an offline analysis, whether or not `phase`
    is an input.
  - H2 measures phase as information, not as a deployable estimate.
  - An LSTM over a heel-strike-aligned 101-point stride knows phase from sequence position, so
    its "without phase" arm is not a test. H2 runs on the per-row models (K3).
- **`gait_state_*`, `StanceInterpolationFactor` (`stance_alpha`):** pending Q11; by default
  offline like phase. They encode phase, so H2's no-phase arm drops them.
  `SmoothedStanceInterpolationFactor` has the same status and is not carried.
- **`step_number_*`: banned.** A session step counter, which encodes time order. Not carried.
- **J3's per-stride torque features** (peak, RMS) are derived from the target. Descriptive
  only, never inputs.
- **Participant ID: never an input to population models**, since the test participant is
  unseen. `group` (AB/HL) is allowed, as a site label by default (Q12). There are no
  anthropometrics.
- **Mode** is the true label, i.e. an oracle. A deployed controller would need mode
  recognition: say so.
- **Splits:** whole blocks, never random strides. Never `GridSearchCV`'s default `cv`: it is an
  unshuffled `KFold` over row positions that ignores blocks and participants, so a fold edge
  splits a stride's 101 rows and puts neighbouring strides on both sides. Use `PredefinedSplit`
  on J4's val blocks.
- **Scalers and any normalisation** are fitted on the training partition only (inside the
  pipeline).

## Handoffs

| From | To | What | File |
|---|---|---|---|
| J1b | Kurian K6 | Per-participant mass and height, or "none published" | `notes/observations.md` |
| J2 | Kurian K4 | Column meanings, units, signs, condition labels | `docs/exogait_data.md` (PR #7) |
| J3 | Kurian K2 | Preprocessing code tested on AB68 + HL03 | `src/exogait/preprocess.py` |
| J4 | Kurian K2, K3 | Splits, leakage self-check, allowed inputs | `split.py` (`ALLOWED`), `splits.csv` and `split_counts.csv` (AB68 + HL03), `docs/model_inputs.md` |
| J5 | Kurian K3 | Metric function, results format, ablation loop | `src/exogait/evaluate.py` |
| Kurian K2 | J5 (and J4 for review) | Processed data and splits, all 19 | `data/processed/exogait/` (zip, outside git) |
| Kurian K3 | Kurian K7 | Predicted torque on test strides | `predict/<model>_<ID>_pred.csv` |
| J6 | Kurian K8 | Per-stride EMG features | `<ID>_emg.csv` |
| Kurian K3, K9 | J7 | Results for statistics and figures | `predict/*.csv`, `moco/summary.csv`, `ro6/`, `split_counts.csv` |
| Kurian K4, K5 | J (review) | Plots to check for signs and joint limits | `results/exogait/plots/*.png` |

## Order

1. **Now:** J1 (the Python notice can go today, the email to the authors this week), J1b, J3 on
   AB68 + HL03, and the MATLAB part of J8.
2. J4 (it needs J3's `block`). J5 on AB68 + HL03, then on K2's full set.
3. J7 once K3's results land (H4 once K9's land). J9 alongside.
4. J6 when EMG arrives. If none by 2026-12-01, J6 closes as not possible and J9 says so.

The code layout, file formats, shared rules (Python only, one env, raw data never edited or
committed, small self-checks, branches and PRs) and what is parked are in
[`KURIAN_TASKS.md`](KURIAN_TASKS.md).

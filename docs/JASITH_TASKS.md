# Jasith — task list

Team plan for the mentor's brief (received 2026-10-14). Kurian's half, plus the full summary of
the mentor's layers, objectives (RO1–RO6) and hypotheses (H1–H5), is in
[`KURIAN_TASKS.md`](KURIAN_TASKS.md).

## Why the split looks like this

Jasith's laptop cannot sustain long heavy runs. **Kurian takes everything compute-heavy**:
- the full 5.5 GB dataset
- tree ensembles, LSTM and GPR training
- every OpenSim/Moco solve
- the integration and final evaluation runs

Jasith takes work that runs on one participant or on already-processed data:
- understanding the data
- pipeline code developed on a small sample
- splits and leakage rules
- the two baseline models and the shared metrics
- EMG features
- statistics, docs and the write-up

**Laptop limits:** work with the smallest participant file (AB68, 221 MB) plus one HL file, and
load only the columns you need. Do not run Moco or train the LSTM locally.

---

## Tasks

| ID | Task | Done when | Depends on | Size | Status |
|---|---|---|---|---|---|
| J1 | **Mentor alignment.** Send the questions below and record the answers in `notes/decisions.md` | Every question has an answer or a written default we proceed with | — | S | todo |
| J2 | **Dataset study.** Read the Dryad README and data dictionary, open AB68 and one HL file, and find the EMG file format. Write `docs/exogait_data.md` covering: every column with unit and sign convention; condition labels; how heel strikes and gait phase are computed; what the "backpack" joint is; the interaction-force unit (listed as Nm); AB vs HL; which subjects have EMG. Also check the authors' notebooks ([ponsLab/Benchmark-Dataset-Analysis](https://github.com/ponsLab/Benchmark-Dataset-Analysis)) | Kurian can map hip/knee angles to the OpenSim model from the doc alone (K4) | — | M | todo |
| J3 | **Preprocessing code (RO1)** in `matlab/preprocess/`, developed and tested on AB68 (+ one HL file). Implement the mentor's steps: (1) load and keep the original files untouched; (2) find conditions and recording gaps; (3) drop incomplete or invalid strides, with a log; (4) resample each stride to 101 points; (5) compute per-stride torque and kinematic features; (6) leave splitting to J4 | It runs on AB68 and writes a per-stride table plus an exclusion log (one row per dropped stride, with the reason). Self-check asserts: no stride crosses a gap, phase is monotonic, kept + excluded = detected. Handed to Kurian for K2 | J2 | L | todo |
| J4 | **Splits and leakage audit.** Population model: leave one participant out. Personalised model: hold out whole trials or blocks within a participant, never random strides, because neighbouring strides are near copies. Validation set for tuning only. Write a check that asserts no stride sits in two partitions. Write the allowed-inputs list with a reason per input | Split files plus the no-overlap check. `docs/model_inputs.md` lists every input as allowed or banned, with a reason (see leakage notes below) | J2 | M | todo |
| J5 | **Baselines and shared metrics (RO2, mandatory models).** Phase-conditioned mean and ridge regression. One metric function used by every model: RMSE, MAE, R², nRMSE, inference time, reported per mode and per participant. Run the H1/H2/H3 ablations for these two models. They are light enough for the laptop on processed data | Results files in a fixed format that Kurian's K3 models also write. Baseline numbers per mode and participant | J4, K2 (processed data) | M | todo |
| J6 | **EMG features (RO5).** 5 subjects, 5 muscles per leg: filtering, envelope, normalisation (state which method), per-stride features aligned to the 101-point strides. Label them muscle-activity features. They are **not** fatigue measures, as the mentor's brief stresses | Per-stride EMG feature table for the 5 subjects, with a self-check, handed to Kurian for K8 | J3 | M | todo |
| J7 | **Statistics and figures for H1–H3 (and RO6 tables).** Paired comparisons across participants: e.g. Wilcoxon signed-rank on per-participant RMSE, with effect sizes. Results tables per mode. Plots | Each of H1–H3 has a test, a p-value and effect size, and one figure. RO6 summary tables from K9 | J5, K3, K9 | M | todo |
| J8 | **Realign the docs.** Rewrite `README.md` and `PROJECT_GUIDE.md` around the mentor's plan. Archive the current guide as `docs/guide_v3_fatigue_twin.md`. Mark D1–D4 and the DGX setup as parked. Add MATLAB setup to `ONBOARDING.md` | A newcomer reading README → PROJECT_GUIDE lands on the ExoGait plan, not the old one | J1 | M | todo |
| J9 | **Literature and write-up.** Related work on exo torque / joint-moment estimation (Molinaro 2024, #32 in `lit_slides/`), the ExoGait/X2 paper, MocoTrack. Draft methods for RO1–RO2 and results for H1–H3 | Draft sections in the report, each number traceable to a results file | J5, J7 | L | todo |

Sizes: S = a day or two, M = about a week, L = more than a week.

## Questions for the mentor (J1)

1. Is Python allowed for any part (e.g. the AI models), or MATLAB only? Which toolboxes do we
   have licences for?
2. What is the prediction target? Measured torque in SM mode only, or TR mode too (where torque
   is near zero)?
3. May the state-machine parameters (stiffness k, damping d) be inputs? With angle and velocity,
   they nearly define the SM torque, so the model would be reconstructing the controller.
4. Gait phase in the dataset is interpolated between heel strikes, so it needs the *next* heel
   strike. Is this offline phase fine, or should phase be estimated causally?
5. What are the "specified baseline" and the effort objective for H4? Is the objective the sum of
   squared muscle activations?
6. Should the existing fatigue model stay as an extension, or be dropped?
7. Ankle angle is not recorded. Is a reference or loosely tracked ankle acceptable in MocoTrack?

## Leakage notes for J4

- **Desired torque: banned** (mentor's rule).
- **Interaction forces: probably banned.** They come from the delivered torque, so they nearly
  encode the target.
- **k, d: pending J1 question 3.**
- **Gait phase: pending J1 question 4.** If kept, state that the analysis is offline.

## Handoffs

| From | To | What |
|---|---|---|
| J2 | Kurian K4 | Column meanings, units, sign conventions |
| J3 | Kurian K2 | Preprocessing code tested on one participant |
| J4 | Kurian K2, K3 | Split files, no-overlap check, allowed-inputs list |
| J5 | Kurian K3 | Metric function and results format |
| Kurian K2 | J5 | Processed per-stride dataset |
| J6 | Kurian K8 | EMG feature table |
| Kurian K3, K9 | J7 | Results files |
| Kurian K4, K5 | J (review) | Plots to check for signs and joint limits |

## Order

1. **Now:** J1, J2, J8
2. J3, J4
3. J5 (once K2 delivers processed data), J6
4. J7
5. J9

Shared rules (MATLAB first, raw data never edited or committed, self-checks, branches and PRs) and
what is parked are in [`KURIAN_TASKS.md`](KURIAN_TASKS.md).

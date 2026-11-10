# Model inputs: what a torque model may see (J4)

Every raw ExoGait column and every processed column, marked **allowed**, **target**, **banned** or
**not carried**, with the reason. The code is the source of truth:

- `src/exogait/split.py`: `ALLOWED` (the inputs) and `TARGETS`;
- `src/exogait/preprocess.py`: `COLUMNS` (what is carried) and `BANNED` (what is never read);
- `src/exogait/evaluate.py`: `ABLATIONS` (what each ablation removes).

The model form is the mentor's: `tau_exo(t) = f(q, qdot, phase, mode, participant info,
controller params)`. **Desired torque is never an input, and every input must exist at inference
time.**

## Raw columns

| Raw column(s) | Processed column(s) | Status | Reason |
|---|---|---|---|
| unnamed first column | — | not carried | A row index |
| `time` | `t` | key, not an input | The raw clock. It restarts in five files, so it is only good inside a stride; `row_start`/`row_end` place a stride in the session |
| `JointPositions_1..4` | `hip_q`, `knee_q`, `hip_q_other`, `knee_q_other` | **allowed** | Encoder angles of the stride leg and the other leg |
| `JointVelocities_1..4` | `hip_qd`, `knee_qd`, `hip_qd_other`, `knee_qd_other` | **allowed** | Recorded velocities |
| `BackPackAngle`, `BackPackAngularVelocity` | `backpack_q`, `backpack_qd` | **allowed** | Trunk angle and rate |
| `JointTorques_1..4` | `hip_tau`, `knee_tau` (stride leg) | **target** (`motor`) | The motor-side torque. Never an input. The other leg's is not carried |
| `JointTorquesViaGauges_1..4` | `hip_tau_gauge`, `knee_tau_gauge` | **target** (`gauge`) | The torque at the joint output, the one that reaches the wearer (K6). Never an input. NaN where the sensor is stuck (AB82's left knee) |
| | `hip_tau_gauge_other`, `knee_tau_gauge_other` | **banned** as inputs | The other leg's measured torque. Carried only so K5 can replay it |
| `DesiredJointTorques_1..4` | — | **banned**, not carried | The mentor's rule. r = 0.87–0.95 with `JointTorques` |
| `InteractionForces_1..5`, `SmoothedInteractionForces_1..5` | — | **banned**, not carried | `InteractionForces_{i+1}` tracks `JointTorques_i`: a measurement of the target |
| `DesiredInteractionForces_1..5` | — | **banned**, not carried | The controller's command |
| `condition` | `mode` | **allowed** | H3. The true label, an oracle: a deployed controller needs mode recognition |
| | `controller` | **allowed** | Which controller ran (TR or SM). J1 Q2: both are modelled, with the controller as an input |
| `condition_encoded` | — | not carried | The same label as a number |
| `gait_cycle_left/right` | `phase` (0–100) | **allowed, offline** | Phase is interpolated between heel strikes, so it needs the *next* one (J1 Q4). H2 measures it as information, not as a deployable estimate. Its heel strikes also define the strides |
| `gait_state_left/right` | `gait_state` (stride leg) | **allowed** | Computed online by the X2's state machine (Lhoste et al. 2026). It encodes phase, so H2's no-phase arm drops it. The other leg's is not carried |
| `StanceInterpolationFactor` | `stance_alpha` | **allowed** | The left foot's share of the vertical ground force, from the footplate sensors, computed online (Lhoste et al. 2026). It encodes phase, so the no-phase arm drops it |
| `SmoothedStanceInterpolationFactor` | — | not carried | The same signal, smoothed |
| `step_complete_l/r` | — | used, not carried | Drops the strides the dataset marks incomplete. True on every kept stride |
| `step_number_l/r` | — | **banned**, not carried | A session step counter: it encodes time order |
| `SM_Stiffness_1..4`, `SM_Damping_1..4`, `SM_Equilibrium_Angle_1..4`, `SM_Equilibrium_Velocity_1..4` | `hip_sm_k`, `hip_sm_d`, `hip_sm_q0`, `hip_sm_qd0`, and the same for the knee | carried, **excluded** by default | Pending J1 Q3. With angle and velocity they nearly define the SM torque, so a model given them reconstructs the controller. Carried so a yes needs no rerun of the preprocessing. They are also filled in TR mode |
| `SM_Gui_Parameter` | — | not carried | A GUI setting |
| `enableRenderingFlag` | — | not carried | A GUI flag |

## Columns the preprocessing adds

| Column | Status | Reason |
|---|---|---|
| `participant` | key, **never an input** | A population model's test participant is unseen. A personalised model is fitted per participant |
| `group` (AB / HL) | **allowed** | A site and device label (AB: U.S.A., HL: Spain; Lhoste et al. 2026): the two sites differ in stairs, ramps and recording set-up. Constant inside a personalised model |
| `leg` (L / R) | **allowed** | Known at inference. The two sides of a device differ, and each gauge channel has its own offset of a few Nm |
| `stride`, `block`, `row_start`, `row_end` | keys, **never inputs** | They encode the order of the session |
| `<ID>_stride_features.csv` (duration, ROM, peak and RMS torque) | **never inputs** | Derived from the whole stride and from the target. Descriptive only |

## Ablations (`evaluate.py`)

| Arm | Removes | Hypothesis |
|---|---|---|
| `full` | nothing | |
| `no_phase` | `phase`, `gait_state`, `stance_alpha` | H2. All three encode phase |
| `no_mode` | `mode` | H3 |

The LSTM over a heel-strike-aligned 101-point stride knows phase from the position in the
sequence, so it has no `no_phase` arm (K3).

## Rules that are not about columns

- **Everything on the 101-point table is offline**, with or without `phase`: resampling a stride
  needs its closing heel strike.
- **Whole blocks, never random strides** (`split.py`). Neighbouring strides are near copies, and
  left and right strides overlap in time. The self-check asserts that no test stride shares a raw
  row with a train or val stride.
- **Tuning on the val blocks only**, with sklearn `PredefinedSplit`. Never `GridSearchCV`'s default
  `cv`: it is an unshuffled `KFold` over rows that ignores blocks and participants.
- **Scalers and any normalisation are fitted on the training rows only**, inside the pipeline.
- **The test blocks are scored once**, in the final `--test` pass, after every choice is made on val.
- **A within-participant test block is a later pass of the same session and donning**, not another
  day. State this next to H1.

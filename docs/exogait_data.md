# ExoGait Benchmark: data guide (J2)

Checked against the real CSVs (AB68 and HL03, headers of all 19) with
`python src/exogait/checks.py AB68 HL03`. The raw numbers are in `notes/observations.md` under
"What the raw CSVs look like". Items still marked **[open]** need the mentor or the authors (J1).

## Source

- Dryad [doi:10.5061/dryad.70rxwdc6j](https://datadryad.org/dataset/doi:10.5061/dryad.70rxwdc6j),
  version 449435 (dataset version 5, June 2026), licence CC0.
- Lhoste, Canton, Kucuktabak, Short, … Vianello, Pons (ETH Zurich, UC3M, Northwestern,
  Shirley Ryan AbilityLab, Hospital Los Madroños).
- Contacts: clhost@ethz.ch, lvianello@sralab.org.
- **Download by hand** from the dataset page into `data/raw/exogait/` (gitignored). The file API
  needs a bearer token, and the stream URL is behind a bot check.

## Files

- 19 CSVs, one per participant: `AB68`–`AB73`, `AB75`–`AB82` (no AB74), `HL01`–`HL05`, all
  `*_ExoGait-Benchmark.csv`. 205–383 MB each, 5.5 GB in total.
- Plus `README.md`.
- J3 develops on AB68 (221 MB) and HL03 (205 MB).
- **No EMG anywhere.** There are no EMG files on Dryad and no EMG column in any of the 19
  headers, though the README says otherwise. J6, K8 and H5 are blocked until the authors or the
  mentor provide it (J1 Q8).
- AB vs HL: probably the two sites (Chicago / Madrid) **[open]**.

## Protocol

- Device: **Fourier X2**, 4 actuated joints: left/right hip and left/right knee, sagittal plane.
  **No ankle actuator and no ankle angle.**
- Modes: overground walking, ramp up, ramp down, stairs up, stairs down.
- Controllers: transparent (TR) and state machine (SM), randomised order within each activity.
  Walking comes first, then stairs and ramps in random order.
- Sites: Chicago has 6 m overground, 150 mm stairs and a 5° ramp (4 m). Madrid has 13 m
  overground, 170 mm stairs and a 6° ramp (3 m).
- One file per participant, activities in time order, rest periods removed. Nominal rate is
  333 Hz (median dt 2.99 ms).

## Loading rules (for J3)

- **Load by column name, never by index.** AB72 has the same columns in a different order.
- The header starts with `,`, i.e. a leading unnamed index column. Drop it.
- Column names have **no** leading spaces. The authors' notebook used a different extract.

## Columns

68 named columns.

| Column(s) | Meaning | Unit |
|---|---|---|
| `time` | time | s |
| `JointPositions_1..4` | joint angle | rad |
| `JointVelocities_1..4` | joint velocity | rad/s |
| `JointTorques_1..4` | measured joint torque. **Likely prediction target [open]** | Nm |
| `DesiredJointTorques_1..4` | controller command (r = 0.87–0.95 with `JointTorques`) | Nm |
| `JointTorquesViaGauges_1..4` | strain-gauge torque. **Uncorrelated** with `JointTorques` (r −0.20 to 0.02) and nonzero while standing **[open]** | Nm |
| `InteractionForces_1..5`, `SmoothedInteractionForces_1..5` | cuff interaction. _1 = backpack, _2–5 = joints 1–4 (`IF_{i+1}` tracks `JointTorques_i`) | listed as Nm **[open]** |
| `DesiredInteractionForces_1..5` | controller target for the above | — |
| `BackPackAngle`, `BackPackAngularVelocity` | trunk/backpack angle, apparently absolute from horizontal (76–86° in walking ≈ upright) | rad, rad/s |
| `StanceInterpolationFactor`, `SmoothedStanceInterpolationFactor` | alpha, 0–1 | — |
| `condition`, `condition_encoded` | `{transparent\|SM}_{WALKING\|RAMPS_UP\|RAMPS_DOWN\|STAIRS_UP\|STAIRS_DOWN\|UNDEFINED}`, plus stray `*_UNDEFINED2` | — |
| `gait_cycle_left/right` | gait phase, **integer 0–99**, interpolated between heel strikes (force sensors) | % |
| `gait_state_left/right` | gait state 0–3 | — |
| `step_number_l/r`, `step_complete_l/r` | step index, and whether that step is complete | — |
| `SM_Equilibrium_Angle_1..4`, `SM_Stiffness_1..4`, `SM_Damping_1..4`, `SM_Equilibrium_Velocity_1..4`, `SM_Gui_Parameter` | state-machine impedance parameters | **[open units]** |
| `enableRenderingFlag` | GUI flag, not data | — |

**Joint order:** `_1` = left hip, `_2` = left knee, `_3` = right hip, `_4` = right knee.
There are only 4 joint positions. The README's "5 variables" counts the backpack, which is the
separate `BackPackAngle`.

## Sign conventions: same as OpenSim

| | X2 (ExoGait) | `2D_gait.osim` | Mapping |
|---|---|---|---|
| Hip | + = flexion: +20 to +34° at heel strike, range about −18 to +60° | `hip_flexion`, + = flexion | direct (radians) |
| Knee | − = flexion: −85° to −0.6°, never positive | `knee_angle`, − = flexion | direct (radians) |

- **Zero offset [open]:** the hip angle is probably relative to the backpack (trunk), not to
  the pelvis. K4 must check this against the model's pelvis tilt (about −15° in the reference
  kinematics) before tracking.

## Data quality (for J3)

- **Timing:**
  - AB68: 6.6% of intervals are over 4.5 ms, and there are 11 gaps over 0.1 s (removed rests,
    the longest 352 s).
  - HL03: 33 intervals with **dt ≤ 0**.
  - J3 must split at gaps and drop or repair non-increasing time.
- **`UNDEFINED`** rows are 60% of AB68 and 42% of HL03 (transitions, turns). Exclude them, and
  log it.
- **Few complete strides:** about 30 walking strides per leg per controller, but only 4–9 on
  stairs (AB68). This limits per-participant ("personalised", H1) models on stairs.
- **Phase resolution is 1%** (integer). For 101-point normalisation, resample on `time` between
  heel strikes rather than relying on `gait_cycle` values.

## Peak knee flexion per stride (median, AB68 / HL03)

| Mode | Peak knee flexion |
|---|---|
| Walking | 47–80° |
| Ramps | 37–73° |
| Stairs | **83–114°** (HL03 stops at 113–114°, probably the X2's mechanical limit) |

In `2D_gait.osim` the gastrocnemius knee moment arm flips sign near 100°, and the quadriceps
arms fall to about 1.4 cm by 80°. **Stairs need a different model or fixed muscle paths. Walking
reaches 80° too**, so walking results also need the caveat.

## Leakage

Inputs that encode the target. The full list goes in J4's `docs/model_inputs.md`.

| Input | Status |
|---|---|
| `DesiredJointTorques_*` | **Banned.** Mentor's rule; r = 0.87–0.95 with the target |
| `JointTorquesViaGauges_*` | Banned while it is a candidate target (J1 Q2) |
| `InteractionForces_*`, `SmoothedInteractionForces_*`, `DesiredInteractionForces_*` | **Banned.** They track the delivered torque or the controller's command |
| `SM_*` (equilibrium angle and velocity, stiffness, damping) | Pending J1 Q3. With angle and velocity they nearly define the SM torque |
| `gait_cycle_*`, `step_complete_*` | Pending J1 Q4. Both use the *next* heel strike, so they're only valid offline |
| `gait_state_*`, `StanceInterpolationFactor` | Allowed if the state machine computes them online **[open]** |
| `JointPositions_*`, `JointVelocities_*`, `BackPackAngle*`, mode | Allowed |

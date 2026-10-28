# Observations

Things noticed that are not formal results. Bugs, contradictions, surprises, wrong turns.
Several of these are worth a footnote or a discussion paragraph in the write-up.

---

## In the anchor paper (Zhang et al. 2026)

### The workaround they buried in the methods

Section II-D, their own words:

> *"To avoid discontinuities, the fatigue stage for each step in the prediction horizon must be
> selected before optimization and remain fixed during the process."*

They pick whether the muscle is tiring or recovering based on the current instant, then hold that
assumption across the whole look-ahead window. Their own Figure 9 shows tiredness rising and falling
*within* each repetition, so the assumption flips inside the window they froze.

**This became the entire basis of E1.** It was not in their future-work section — it was a
limitation they worked around and did not quantify.

### Their headline improvement is smaller than the abstract implies

Time to reach the tiredness threshold in a static squat:
no help 66.95 s, constant 15% help 73.60 s, their controller 76.15 s.

**Their smart controller beats dumb constant help by 3.5%.** They say so themselves —
*"the time differences in reaching the maximum fatigue level are relatively small."* Their real
selling point is energy: about four times lower power draw early in the trial.

Useful framing for us: if being clever about tiredness buys only 3.5% on one joint with one lumped
number, does the margin grow with several joints and per-muscle detail? That is a genuine question
either way.

### Their maximum assistance setting is unreachable

They state a 30% cap on how much torque the brace takes over. But the 180 N cable force limit bites
first — at a 90 degree knee bend with about 100 Nm of knee torque, 180 N of cable force corresponds
to about 17%. **The 30% figure never binds.** Consistent with their Figure 7, where tension flattens
at 180 N. Worth noting because it means their controller is force-limited, not policy-limited.

### Their own linearity assumption contradicts their own measurements

Equation 25 assumes muscle effort drops in direct proportion to torque taken over. Their measured
effort says 15% commanded gives 9.6% delivered — a ratio of 0.64. See results.md section 2.

### They went backwards in model detail

Peternel et al. 2019, same research group, tracks tiredness **per muscle**. Zhang et al. 2026
collapses it to **one number for one muscle group**. So our E3 is not adding something new — it is
restoring what the group already had. Much easier to defend, and worth saying plainly.

### They admit their torque prediction is fragile

> *"the use of second-order derivatives in recursive computation may introduce instability into the
> optimal controller, particularly in the presence of rapid motions or noise from wearable sensors."*

They get away with it because everything they test is slow. It will not survive walking. That is E5.

---

## In the authors' released code (`external/PHRC/`)

### Confirmed bug: only two muscles ever update

```python
def fatigue(self, MA):
    for i in range(2):        # should be range(self.N)
```

The number of muscles is a constructor argument and every array is sized accordingly, but the update
loop is hardcoded to two. Verified by running it with four muscles:

```
V = [0.1175, 0.1175, 0.0, 0.0]
```

Muscles past the second silently return zero tiredness. No crash, no warning — just plausible
looking zeros.

**Directly affects us:** E3 runs per-muscle across six or more groups. Unmodified, this would
quietly discard most of the model.

Treat it as a teaching release, not the code behind their published experiments. Do not infer
anything about their results from it. Fix it in our own code, note the correction in methods.

### A number that disagrees between the paper and its own code

- Code: relaxation threshold `0.05` (5% of maximum effort)
- Peternel 2019 section 3.2: *"the threshold... was set to 0.02% of MVC"*

These disagree, and it is **the exact threshold E1 smooths**. Worth resolving and reporting the
sensitivity — if behaviour depends strongly on a number stated inconsistently between a paper and
its own reference code, that is a legitimate finding, not a nitpick.

### Recovery rate is borrowed, not measured

The code comments the recovery constant as *"based on calibration or literature"* and sets it to
0.5. Every paper in the chain reuses that same number. Recovery dominates anything cyclic, because
every rest phase is recovery. **This is E6 and it is justified straight from the source.**

**Traced (2026-10-07).** Ma et al. 2010 (Virtual and Physical Prototyping 5(3), arXiv 1010.5891)
does not measure R either. It writes recovery as dF_cem/dt = R (MVC - F_cem), with R "assumed to be
constant 2.4" min^-1, citing Liu, Brown & Yue 2002 (Biophys J 82:2344) and Wood, Fisher & Andres
1997 (Human Factors 39:83). Its fatigue rate is k = 1 min^-1.

Mapping that onto our model needs care. Ours is dV/dt = (1-V) M / C (fatiguing) and -V R / C
(recovering), so only the ratio of recovery speed to fatigue speed matters. Ma's model in the same
variables (V = 1 - F_cem/MVC) gives fatigue speed k and recovery speed R_Ma, so:

- **R = R_Ma / k = 2.4** if you keep Ma's own pair (k = 1 min^-1)
- **R = R_Ma * C = 0.33** if you pair Ma's absolute recovery speed (2.4/min = 0.04/s) with our
  fitted C = 8.24 s

The lineage's 0.5 sits at the low, pessimistic end of that range: low R means slow recovery and
more fatigue. Which end is right depends on whether recovery scales with how fast a muscle tires.
No source we have measures that for gait muscles. Phase C sensitivity: `results.md` section 8.

### Their reference implementation integrates crudely

Fixed-step, simplest possible integration method, with a warning comment in the source that the loop
must run at exactly the stated rate or the result is wrong. Their demo runs at 1 ms; their
controller runs at 10 ms, ten times coarser. Our measured error floor turns out to be exactly this.

---

## From our own runs

### The hypothesis I started with was wrong

Predicted: the frozen-switch error gets worse when movements repeat faster, because the window spans
a crossing more often.

Reality: the window *does* span crossings more often, exactly as predicted by a simple formula. But
the error stays flat. Shorter repetitions move less tiredness per crossing, so each mistake costs
less, and the two effects cancel.

The axis that actually matters is **how far ahead the controller plans**, measured against how long
the person takes to tire. Better result than the original guess, and a cleaner story.

### A confound I nearly published

First version of the repetition-speed sweep used `n = max(2, ...)` repetitions. At the slowest
setting that silently ran the simulation for 20 s while every other setting ran 10 s — twice the
tiredness exposure, so of course the differences looked larger. Fixed to equal duration before
drawing any conclusion. Numbers in results.md are the corrected ones.

**Lesson for every sweep from here: check that the thing you are not varying is actually constant.**

### Brute force was the wrong instinct

Solving the control problem at every time step took 75 s per run, so a parameter sweep took over
three minutes and repeatedly hit timeouts. But the static squat is a hold — the best assistance
level depends only on how tired the person is. Tabulating 40 solves and interpolating gave the same
answer to 0.54% in 1.7 s.

Applies to any static or slowly-varying condition. Does **not** apply to cyclic tasks, where the
answer depends on both tiredness and where you are in the cycle.

### The static squat can never demonstrate E1

Effort sits around 0.19 against a threshold of 0.05 and never crosses it. Both switch treatments
give identical answers. Gate R therefore says nothing about E1 — only the periodic trials can.

Obvious once seen, but it was not obvious in advance, and it determined which experiment had to be
built.

### Tooling friction worth remembering

- `pip` is broken on this machine (the Anaconda install). `python -m pip` works.
- Python buffers output, so long background runs appear to produce nothing. Use `python -u`.
- Writing long files through shell heredocs kept mangling backslash sequences and broke source files
  twice. Use a file-writing tool for anything long.

### OpenSim on Windows: four traps, all hit on 2026-10-02

1. **Conda `casadi` in the same env breaks Moco.** Moco bundles its own CasADi. A second copy
   from conda-forge loads first and fails inside Moco with `'get_forward' not defined for
   CallbackInternal`. Do not install casadi from conda into the OpenSim env (pip is fine,
   because its DLLs stay inside site-packages).
2. **MKL overwrites OpenSim's bundled Intel runtime.** numpy's default BLAS on Windows pulls in
   MKL, which replaces `svml_dispmd.dll` with a version missing `__svml_log2`, and IPOPT fails
   to load (`WinError 182`, reported as "Plugin 'ipopt' is not found"). Fix: create the env
   with `"libblas=*=*openblas"`. The env must also be *activated* (`micromamba run`), or the
   plugin DLLs are not on PATH.
3. **`inv.solve().getMocoSolution()` crashes Python** (access violation). The solution is a
   reference into the temporary MocoInverseSolution, so that object has to stay alive.
4. **PrescribedController + MocoInverse = infeasible**, even with zero torque prescribed. See
   decisions.md for the body-torque workaround.

### Twin bugs caught by sanity checks, not by the solver (2026-10-02)

Every one of these still reported "EXIT: Optimal Solution Found":

- **Subject scaling did nothing.** `2D_gait.osim` keeps all its forces at the model root, and
  `getForceSet()` is empty (as is `getMuscles()`). The strength and contact-stiffness loops
  iterated an empty set. Caught by asking why muscle activations ignored assistance. Fixed with
  a path-based component search plus a self-check (`twin._check_scaling`).
- **Activations not optimised.** Pelvis residuals and lumbarAct dominated the objective, so at
  tolerance 1e-3 the muscles stayed where they started. Caught by the test "p = 1 must zero the
  muscles". See decisions.md.
- **Exo delivered less torque than intended** (prescribed body-torque version). Caught by an ID
  re-solve with the exo applied. Replaced, not patched.
- **The problem changed with p** (reserves skipped under the exo), so p = 0.3 was infeasible.

Lesson for the write-up: a converged optimiser proves nothing about the model. The checks that
caught these were physical ("full assistance must unload the muscles", "scaling must change
the parameters"), and they are now in the self-checks.

### Open flags on the twin

- **Joint reserves are 7 Nm RMS unassisted** and do not shrink at tighter tolerance, even though
  no muscle exceeds 57% activation. Likely rigid-tendon fibers off their force-length plateau at
  some phases. A real limitation of this reduced model; report it. Tendon compliance would be
  the thing to try.
- **Soleus barely responds to ankle assistance** (−7% at 30% capacity; 0.062 even at p = 1 where
  other muscles reach 0.01–0.02). Gastroc and tib_ant respond normally. Unexplained. Look before
  any ankle claim goes into the paper.

### Parallel Moco workers in one directory (suspected, 1 failure in 18)

Moco writes `delete_this_to_stop_optimization_<timestamp>.txt` into the working directory and
polls for it every iteration. If the file is gone, the solve stops. One smoke task failed with
CasADi's `intermediate_callback` erroring, which is consistent with parallel workers in a shared
cwd tripping each other's files. Not proven. Each worker now runs in its own directory, and
`--retry-failed` reruns any failures.

### The laptop is the bottleneck, not the method

7.3 GB of RAM. Six parallel Moco workers plus anything else exhausts it (OpenBLAS allocation
failures). A single twin evaluation takes 67 s alone and 100–300 s with six in parallel.
Development only. The DGX does the sweeps.

---

## ExoGait plan (from 2026-10-14)

### K1: environment and the stock MocoTrack example

- **OpenSim 4.6** Windows release (`opensim-core-4.6-win.zip`, GitHub, 176 MB; it holds a second
  zip) is unpacked to `C:\OpenSim 4.6`. With MATLAB dropped (`notes/decisions.md`, 2026-10-28)
  it is only where the example scripts come from.
  Its Python bindings are built for Python 3.11 (`python311.dll`). The zip ships the example
  *scripts* but not their data: no 3D walking files, and no `referenceGRF` for the 2D example.
- **Python:** micromamba 2.9.0 in `~/micromamba` (sha256 checked), env `opensim` from the
  ONBOARDING recipe: Python 3.11.17, opensim 4.6 (opensim-org `py311np24`), numpy 2.4.6 on
  OpenBLAS. No MKL, no conda casadi.
- **MATLAB: dropped.** The college has no MATLAB licence (the MathWorks account offers only
  "Link License"). K1 is done in Python. Decision and reasons in `notes/decisions.md` (2026-10-28).
- **Stock MocoTrack runs.** `example2DWalking.py`, the tracking problem, on `models/base/`
  (the same files the example uses), with two edits: GRF tracking weight 0 (`referenceGRF` is
  not shipped, and ExoGait has no GRF anyway), and stop after tracking. Optimal in 87 IPOPT
  iterations: 34 s in IPOPT, 39 s wall (16 logical cores, 16 GB RAM). Tracking RMSE against the
  filtered reference:

  | pelvis_tilt | hip_l | hip_r | knee_l | knee_r | ankle_l | ankle_r | lumbar |
  |---|---|---|---|---|---|---|---|
  | 1.05° | 1.30° | 2.03° | 2.35° | 3.21° | 0.61° | 0.51° | 1.23° |

- CasADi prints `intermediate_callback is disfunctional in your installation`. If so, deleting
  the `delete_this_to_stop_optimization` file may not stop a solve in this build. Not tested.

### Dryad blocks scripted downloads

The file API (`/api/v2/files/{id}/download`) needs a bearer token (401). `/downloads/file_stream/`
gives 403 to scripts and an Anubis bot-check page to the in-app browser. Download by hand from
the dataset page into `data/raw/exogait/`.

### The EMG files are not on Dryad

The README says EMG is "stored in separate files", but version 449435 has 20 files: the 19
participant CSVs and README.md. **No CSV has an EMG column either** (all 19 headers checked).
EMG is not in this release. This blocks J6, K8 and H5 until the authors answer (J1 question 8).
The README gives clhost@ethz.ch and lvianello@sralab.org as contacts.

### What the raw CSVs look like (`src/exogait/checks.py`, AB68 and HL03)

- 68 named columns plus a leading unnamed index column. There are only 4 joint positions
  (1 = L hip, 2 = L knee, 3 = R hip, 4 = R knee); the backpack is a separate `BackPackAngle`,
  not a fifth joint as the README says. AB72 has the same columns but in a different order:
  **load by name, never by index.**
- **Signs match OpenSim.** Hip + = flexion: at heel strike in transparent walking the hip is at
  +20 to +34°. Knee − = flexion: −85° to −0.6°, never positive. `BackPackAngle` averages 76–86°
  and looks like an absolute trunk angle from horizontal. The hip angle is then probably
  relative to the backpack. Unconfirmed.
- `gait_cycle_left/right` are **integers** 0–99 (1% resolution). `gait_state_*` is 0–3.
- Timing: median dt is 2.99 ms. AB68 has 30,878 intervals over 4.5 ms (6.6%) and 11 gaps over
  0.1 s (rests removed, the longest 352 s). HL03 has 33 intervals with **dt ≤ 0**, and two stray
  labels, `SM_UNDEFINED2` and `transparent_UNDEFINED2`. J3 has to handle all of this.
- `UNDEFINED` rows are 60% of AB68 and 42% of HL03. Complete strides per condition are few:
  about 30 walking strides per leg, but only 4–9 on stairs (AB68).
- **Peak knee flexion per stride** (median, AB68 / HL03): walking 47–80°, ramps 37–73°,
  **stairs 83–114°**. HL03 stops at 113–114° on stairs, which looks like the X2's mechanical
  limit. Stairs therefore sit in the range where the 2D model's knee muscles are wrong (above).
- **Transparent-mode torque is not near zero.** JointTorques RMS in AB68 walking is 18–20 Nm
  (TR) vs 22–25 Nm (SM). This changes J1 question 2.
- `DesiredJointTorques` tracks `JointTorques` closely (r = 0.87–0.95, same RMS): banning it is right.
- **`JointTorquesViaGauges` is uncorrelated with `JointTorques`** (r = −0.20 to 0.02) and is
  nonzero while standing. Which column is "measured torque" is an open question for J1 (Q9).
- `InteractionForces_{i+1}` correlates with `JointTorques_i` better than `InteractionForces_i`
  does, which fits IF_1 = backpack and IF_2–5 = joints 1–4.

### K4 groundwork: knee moment arms in `2D_gait.osim`

Sign conventions: `hip_flexion` is + for flexion, `knee_angle` is − for flexion (range −120° to
10°). The reference pelvis tilt is about −15°. Right-leg knee moment arms (m; − = flexor):

| knee angle | gastroc | hamstrings | bifemsh | rect_fem | vasti |
|---|---|---|---|---|---|
| 0° | −0.025 | −0.031 | −0.023 | 0.044 | 0.043 |
| −40° | −0.014 | −0.045 | −0.041 | 0.034 | 0.030 |
| −60° | −0.009 | −0.044 | −0.045 | 0.025 | 0.023 |
| −80° | −0.004 | −0.038 | −0.044 | 0.013 | 0.014 |
| −100° | +0.001 | −0.027 | −0.037 | 0.017 | 0.016 |

This is the defect the example's header warns about: the gastroc path has no wrapping, so its
flexor moment arm shrinks with flexion and flips sign near 100°. The quadriceps arms also fall
to about 1.4 cm by 80°. Walking and ramps are usable **with a caveat**: their per-stride knee
peaks reach 70–85° (data below), where the gastroc arm is near zero and the quadriceps arms are
small. **Stairs (83–114°) go into the range where the knee muscles are wrong.** Before any stair result, fix the
paths or switch models. The `Rajagopal_2015.osim` in the zip (`OpenSenseExample/`) has **no
muscles**: it is the kinematics-only OpenSense copy. A muscled Rajagopal model has to come from
`opensim-org/opensim-models`.

### K4: the X2 model and the angle mapping (`src/exogait/x2model.py`, 2026-10-28)

- **No OpenSim bindings needed.** The micromamba `opensim` env had disappeared from `~/micromamba`
  by 2026-10-28 (`~/.conda/environments.txt` still lists it), so `x2model.py` edits the .osim as
  XML and checks it with `opensim-cmd` from the OpenSim 4.6 install, in any Python with
  numpy/pandas/scipy/matplotlib. K4's tracking trials also ran MocoStudy `.omoco` files through
  `opensim-cmd run-tool`; their stock run matched K1 within 0.3°. K5 needs the env rebuilt.
- **X2 mass is 20.7 kg**, not twin.py's generic 8.6 kg: Küçüktabak et al. 2023 (IEEE T-RO) Table II,
  backpack 10.3, thigh 2.84, shank 1.11, foot 1.25 kg per side; COMs from the CORC controller's
  `x2_params.yaml`. Model mass goes from 62.0 to 82.7 kg (+33%). Inverse dynamics (`opensim-cmd`) on
  the reference walk, X2 model minus base: pelvis_ty force +203.2 N on average, against 20.7·g =
  203.0 N, so OpenSim sees the added mass. Peak torque is 80 Nm per joint (T-RO), but the data reach
  85–89 Nm. The backpack COM is placed with the backpack axis = pelvis y axis, which is c off
  (0.25 sin|c| m, 6 cm for AB68).
- **Rotor inertia and friction are left out.** T-RO gives 1.87 kg m² apparent rotor inertia per
  joint (against 2.29 kg m² for the whole straight leg about the hip). 1.87·q̈ is 10–19 Nm RMS of
  the 16–24 Nm measured `JointTorques` (q̈ from differentiated velocity, so approximate), so
  `JointTorques` looks motor-side. K6/K7 subtract 1.87·q̈ and the Table III friction before
  comparing or replaying. Table III and CORC's yaml swap the Coulomb and viscous labels (J1).
- **Torque sign = OpenSim's.** In SM walking, `JointTorques` rises with the impedance torque
  K(eq − q) + D(eqv − q̇) at every joint (slope 0.88–1.35 AB68, 1.08–1.53 HL03), so +torque drives
  the angle +. `checks.py` asserts it. `JointTorquesViaGauges` has no consistent sign against it
  (r −0.4 to +0.4).
- **The X2 hip is measured from the backpack**, so `thigh = BackPackAngle − 90 + hip`. Checked on all
  19: in quiet standing the hip moves against the backpack (median slope −1.13) and this thigh angle
  comes out vertical (−0.02 ± 4.1°). In walking it matches the reference's pelvis_tilt + hip_flexion
  (r 0.92). The backpack's absolute level differs by site (walking BP − 90: AB +3.4°, HL −9.6°), so
  the split into pelvis and hip needs a per-participant constant c, holding the mean pelvis tilt at
  the reference's −15.06°. **c: AB −11.5 to −23.8°, HL −0.8 to −9.6° (AB68 −14.2°, HL03 −5.4°).**
  c borrows the reference subject's tilt; a calibration posture or IMU mounting angle from the
  authors would replace it (J1). Knee needs no change.
- **BackPackAngle has artefacts the gyro does not see**: smooth 20–35° excursions over 2–3 s, mostly
  at AB (`x2model.py`'s filter drops 19 of AB68's 39 clean TR + SM strides; HL 0–1.3%). They only
  touch pelvis_tilt and c, so the filter drops strides from those only, not from hip and knee. An
  excursion about one stride long looks like a ramp, which a range comparison after detrending
  misses, so the filter also compares BackPackAngle's end-start change with the integrated gyro
  (> 5° rejects). Without that, one AB68 TR stride with a +19.9° ramp (gyro +1.4°) moved c by
  0.56° and doubled the TR pelvis SD (2.3 → 4.8°).
- **The target is the mean stride**, right heel strike to right heel strike, of the clean strides of
  one participant × condition (single strides sit 3.8–4.6° RMS from it; averaging lowers the knee
  peak by 1–4°). Its end-start mismatch is removed by a ramp centred on mid-stride, so it is
  periodic and keeps its mean. Full cycle, no L/R symmetry: AB68's knee peaks are −70° R, −57° L.
- **AB68 TR walking**: 17 clean strides (2.80 ± 0.13 s), 9 gyro-confirmed for pelvis_tilt. Mapped vs
  the reference: right hip at right heel strike 42.5° (reference 38.1°); hip peaks 62–63°
  (reference 39°); knee peaks −70° R, −57° L (reference −45°); pelvis_tilt −20 to −14° (reference
  −15 ± 0.2°). HL03 TR: 51 strides, hip peaks 52–55°. Stride-to-stride SD 4–5° on hip and knee
  (HL03: 2–6° over all five); AB68 TR pelvis_tilt 2.3°, end-start mismatch 0.7°.
- **OpenSim reads the target back**: an AnalyzeTool run plays the .sto through the X2 model and returns
  the same angles to within 2e-6°, with the 10 coordinates in the expected order.
- **The self-check passes on all 19 × TR/SM walking sets.** Its mapping checks hold for every
  participant; the hip and knee ones do not depend on c:
  - right hip ahead of the left at right heel strike: at least 20°, reference 37°
  - each knee peaks in its own swing: R at 70–91%, L at 21–40%
  - pelvis_tilt stays within −40..0° (data: about −29 to −5°)
  - the mean stride is periodic with its mean kept, and its time axis is the mean stride duration

  c itself is still unchecked: c = 0 passes. Ramps and stairs give 0–15 clean strides under the
  same filters (the bout-edge rule drops 2 per pass); revisit before K5 ramps.
- **K5 tracking trial** (MocoTrack of hip and knee only, on the model's own reference, half cycle,
  through `opensim-cmd`):
  - tracking hip and knee alone gives plausible walking; leaving pelvis_tilt free costs ~1.3° on
    tilt and nothing on hip or knee;
  - control effort weight 10 (the example's) drifted into pinned bounds or a wrong gait in 3 of 7
    runs; weight 1 converged correctly 4 of 4 (160–546 iterations);
  - `MocoAverageSpeedGoal` ignores direction (one run walked backwards at 1.33 m/s); a final-value
    bound on `pelvis_tx` works. With no speed at all the model walked 21% slow with 5–7° hip bias;
  - a free ankle pins its −15° bound at push-off: widen to ±30°. A tracked generic ankle at weight
    0.1 is imposed (followed to 0.4°); use ≤ 0.01;
  - peak vertical GRF is 1.8–1.95 BW even fully tracked: a property of this contact model;
  - Moco's default mesh (0.02 s) gives 125–185 intervals on a 2.5–3.7 s X2 stride vs ~24 in K1;
    start at T/50.
- Not from `x2model.py`: the 19-participant hip-frame checks, the ID mass check and the tracking
  trial came from throwaway K4 investigation scripts. `x2model.py` asserts the mass from the .osim.

---

## Open questions

- [ ] Resolve the threshold disagreement: 0.05 in code versus 0.02% in the paper. Which did they use?
- [ ] Confirm the tiring-rate constant is on the same scale between our calibration and the demo
      code values (15-20 there, 8.24 from our fit). Units need checking before values are reused.
- [ ] Does the frozen-switch cap move if the person tires faster or slower? We fixed one tiring rate.
- [x] Get Ma et al. 2010 for published recovery-rate values (E6). Done 2026-10-07: R = 2.4
      min^-1, itself borrowed, which maps to 0.33–2.4 in our units. Phase C margin holds for
      R <= 1 and drops to 1% at 2.4 (`results.md` section 8)
- [ ] Get Liu, Brown & Yue 2002 (Biophys J) and Wood et al. 1997, Ma's sources for R, for a
      measured value. And: does recovery speed scale with fatigue speed? That decides 0.33 vs 2.4
- [ ] Check arXiv for the smoothing claim — PubMed covers that literature badly.
- [ ] Check preprint servers for scoop risk. Not possible through the connector available here.
- [ ] Email Peternel: fitted constants, the Exo-Muscle model file, and permission to include the code.

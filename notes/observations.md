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

### K5: MocoTrack reproduces the walking strides on the X2 model (`src/exogait/track.py`, 2026-11-10)

- **Env rebuilt**, since `~/micromamba` was still gone: micromamba 2.10.0 (sha256 checked), env
  `opensim` from the ONBOARDING recipe: Python 3.11.18, opensim 4.6, numpy 2.4.6 on OpenBLAS,
  scikit-learn 1.9.1. Then torch 2.14.1+cu126 by pip: `torch.cuda.is_available()` is True on
  the RTX 2050, and numpy is unchanged.
- **One solve** = one participant × condition: the X2 model tracks the mean stride's hip, knee
  and pelvis-tilt angles with its muscles and foot contact, while the exo actuators replay the
  measured joint torque. Settings and their reasons: `track.py`'s docstring and
  `notes/decisions.md` (2026-11-10).
- **A cold start is fragile; a warm start is not.** From the tracked states, one solve
  converged (HL03 SM, tracking weight 1: 157 iterations, 189 s on 16 threads). Four others,
  each with one or more settings changed, were still at an objective of 10³–10⁵ when stopped
  after 92–618 iterations, carried by reserve forces. Started from that one converged stride,
  the same problem converges in 37 iterations, and **every other participant and controller
  converged from it** (109–319 iterations). The stride is stored as
  `models/exogait/seed_stride.sto`.
- **The solver does not always land on the same solution.** Five `measured` solves were
  repeated from the same seed after a marginal change to the reference's filter. Three agreed
  within 6% on effort. HL03's first solve had stayed at the seed's own optimum (objective 1.350;
  the repeat reached 1.019, with 3% less effort). AB69 SM's repeat came back with twice the
  effort (0.392 → 0.839, objective 0.677 → 1.159): a clearly worse local solution. Hip and knee
  tracking moved by at most 0.2° between them. So tracking results are robust to this, effort
  is not, and every `measured` and `none` solve now gets a second start, the better one kept
  (`assist.py second`; table and rule in `notes/decisions.md`, 2026-11-10). The numbers below
  are after that pass.
- **Tracking weight.** At weight 1 against effort 1 (HL03 SM) the model kept its knee about 4°
  straighter through stance and its hip 3–5° short of extension, to save effort: RMSE hip
  2.5–3.3°, knee 3.6–3.8°. At weight 10: hip 1.2°, knee 0.6–0.8°, pelvis tilt 1.5°.
- **Mesh.** HL03 SM at 50 vs 100 intervals: hip and knee RMSE change by under 0.05°, pelvis by
  0.2°. Effort is 9% lower at 100 (0.483 vs 0.530) and the heel-strike force peaks are higher
  (1.58 vs 1.37 body weights). 50 is kept; effort is only compared between solves on the same
  mesh. 100 intervals cost 375 s and 0.91 GB on 16 threads, against 0.64 GB at 50.
- **All 19 participants × SM and TR walking** (mean strides of 14–64 strides, 1.9–5.6 s; 50
  intervals; 4 threads each, four or five at a time):

  | | |
  |---|---|
  | Converged | 38 of 38 (37 at tolerance 1e-3; AB75 TR at 1e-2, below) |
  | Pass every plausibility check | 34. Three miss a tracking bound; AB82 SM is excluded (stuck gauge). Both below |
  | Hip RMSE, median [range] | 0.60° [0.24–2.25] over the 34; 0.67° [0.24–4.15] over the 37 with a valid torque |
  | Knee RMSE | 0.36° [0.15–1.21]; 0.38° [0.15–2.16] over the 37 |
  | Pelvis-tilt RMSE (tracked at 0.2) | 1.92° [1.30–3.42]; 1.98° [1.30–6.60] over the 37 |
  | Reserves | at most 0.03 Nm RMS at any joint or the pelvis |
  | Exo torque as replayed vs prescribed | at most 0.97 Nm RMS (the mesh's linear interpolation) |
  | Iterations, first start | 181 [37–319] |
  | Solve time, first start | 525 s [47–982] |
  | Peak memory | 0.53–0.64 GB |

- **The three that miss a tracking bound** (hip and knee 3°, pelvis 6°), all converged:
  - HL01 SM: left hip 3.13°.
  - HL05 SM: left hip 4.15°. HL05 TR: pelvis tilt 6.6°. HL05 is the participant whose backpack
    offset c is an outlier (−0.8°, against −5 to −24° for the rest), so its mapped hips reach
    −13° of extension. The model will not extend past about −7°. This is K4's caveat showing:
    c borrows the reference subject's pelvis tilt.
- **AB82 SM is not a valid `measured` solve.** Its left-knee gauge reads a constant −12.07 Nm
  through SM walking, SM ramps and TR ramps (5 of 760 participant × condition × joint cells;
  no other channel is stuck). There is no measured torque to replay at that joint, so the solve
  is excluded here and in K6 and K7. `track.py` now refuses a constant gauge torque, and
  `checks.py` reports it. J3 has to flag it too.
- **AB75 TR** (the slowest stride, 5.6 s at 0.08–0.11 m/s) sat on its optimum from about
  iteration 180 (objective 1.0986 to four digits) without meeting the 1e-3 tolerance in 675
  iterations, and was stopped. Re-run at MocoTrack's own tolerance of 1e-2 it converges in 293
  iterations to the same objective and passes every check. Its row records `tol`.
- **The walking speed is the model's own, and it matches the data.** No speed or stride length
  is imposed, and the model walks at 0.08–0.49 m/s (median 0.25). Against the two estimates
  from K4's stride analysis, over the 34 passing solves:
  - hip travel over the planted foot: r = 0.95, mean difference −0.005 m/s, mean absolute
    difference 0.024 m/s (10%);
  - walkway length / bout time: r = 0.86, mean absolute difference 0.050 m/s (18%).

  The first version imposed a stride length from the range of the ankle-to-ankle distance. That
  estimate is too long (the model walks 0.81 of it, 0.58–0.96), and the solve sat on its bound.
- Figures: `figures/k5_all_participants.png` (tracking error and speed, all participants) and
  `figures/k5_hl03_sm_walking_tracking.png` (one solve in full). Every solve has one in
  `results/exogait/plots/`.
- **What is estimated, and how far to trust it:**
  - **Ankle:** follows a plausible stance pattern; with no cost it fluttered ±10° in swing, so
    the stock walk's ankle is a weak prior. In 10 of 37 solves it touches its −30° bound at
    toe-off.
  - **Ground reaction:** single support sits at 1.0 body weight and peaks are 1.0–1.9, but the
    load bounces between the feet for 2–4 mesh points after each heel strike (64 ms per
    interval at 50). There is no measured force to compare with.
  - **Lumbar:** not recorded, bounded to 0–20°, and it reaches a bound in 13 of 37 solves. The
    trunk actuator is priced as in the stock example (1 Nm = 1 excitation), so the trunk
    balances almost passively. Lumbar moments are not realistic.
  - **Effort:** mean activation is 0.05–0.07. The body is generic (62 kg + 20.7 kg of X2), so
    absolute effort and moments are generic too; differences between cases mean more.
- **OpenSim 4.6 traps hit:**
  - `MocoTrack` with `apply_tracked_states_to_guess` resamples the tracked states onto the guess
    grid, and for some stride durations its last time lands one floating-point digit short of
    the final time: `resample()` throws "New final time cannot be less than existing final
    time". Off when a guess is given.
  - `solver.setGuess()` before the problem is final reports every state as "not in the
    problem". `setGuessFile()` works: it is read at solve time.
  - `MocoTrack.initialize()` writes `<name>_tracked_states.sto` into the cwd, so each solve
    runs in its own folder.
  - `MocoControlGoal` has no endpoint-constraint mode, and `MocoOutputGoal` on an actuator's
    `actuation` fails with "State Cache entry was out of date at Stage Velocity". So an
    integral of a control cannot be constrained (K7).
  - Four `micromamba run` started in the same instant: one came up without the env
    (`No module named 'opensim'`). Stagger the starts.
  - Windows cannot replace a file another process has open: parallel solves must not rewrite
    the shared model file.

### K6: which torque the X2 delivers, and what the joints need (2026-11-10)

- **`JointTorquesViaGauges` is the torque at the joint; `JointTorques` is the motor's.** On
  all 19 participants, TR and SM walking, 4 joints (151 fits: all but AB82's stuck left knee
  in SM; `checks.py` asserts it): `JointTorques` − gauges = I·q̈ + Coulomb + viscous friction +
  constant, with R² 0.82–0.98 (median 0.94) and I = 1.81–2.29 kg m² (median 2.06). The X2's
  published rotor inertia is 1.87 kg m². This answers the J2 puzzle (the two columns looked
  uncorrelated): about half of the motor torque accelerates the motor's own rotor.
  - The constant runs from −6.9 to +4.4 Nm: about −3.5 Nm at the hips and +1.7 Nm at the
    knees. A gauge offset or direction-dependent friction: not separable from these data.
  - The SM impedance slope of `JointTorques` (the K4 sign check) is 0.39–1.75 across all 19
    (median 1.13). The check's first threshold of 0.5 was too tight for AB77 (0.44) and is now
    0.2: a flipped sign gives about −1.
- **Parameters:** `results/exogait/params.csv`, one row per participant. The hip offset c runs
  from −0.8 to −23.8°. Body mass and height are generic until J1b.
- **Moments from the solution, not from an ID re-solve.** `track.py k6` sums muscle tendon force
  × moment arm, the exo torque and the reserves along each K5 solution. A `MocoInverse` re-solve
  on the same kinematics (the `twin.net_moments()` pattern) left 14–34 N and 9–31 Nm RMS of
  pelvis residual (3–4% of body weight) for HL03, because the contact forces are recomputed
  from splined kinematics.
- **What the joints need vs what the X2 delivered** (TR: 19 participants, 38 legs; SM: 18
  participants, 36 legs, without AB82; median RMS over the stride, Nm; share = least-squares
  fraction of the net moment the exo supplies; r = correlation of the delivered torque with the
  net moment):

  | | net moment | model's muscles | X2 at the joint | X2 motor | exo share, median [IQR] | r, median |
  |---|---|---|---|---|---|---|
  | SM hip | 14.4 | 12.8 | 10.3 | 12.4 | 0.27 [0.20, 0.38] | 0.44 |
  | SM knee | 11.7 | 11.7 | 7.1 | 18.2 | 0.19 [0.08, 0.30] | 0.26 |
  | TR hip | 16.3 | 19.3 | 13.8 | 9.6 | 0.09 [−0.01, 0.34] | 0.25 |
  | TR knee | 14.0 | 14.5 | 8.8 | 10.5 | 0.12 [0.03, 0.25] | 0.22 |

  Figure: `figures/k6_hl03_moment_vs_torque.png` (HL03, both modes).

- **TR torque is device compensation, not assistance.** In TR the X2 delivers *more* torque at
  the hip than in SM (13.8 vs 10.3 Nm RMS; higher in TR for 34 of 36 legs), but it supplies a
  smaller share of what the joint needs and follows it less (share and r above; the share is
  higher in SM for 26 of 36 hips and 28 of 36 knees). In TR the model's muscles produce more
  moment than the joint needs in 35 of 38 hips (63 of 76 joints; 30 of 72 in SM), which means
  part of the delivered torque is being opposed. In HL03 TR it is a steady +20 Nm of hip
  flexion through right stance, while the joint's net moment stays near zero.
  - It still unloads the model: against the X2 worn unpowered (`none`), the TR torque lowers
    muscle effort by 34% (median; 14 participants, lower in all 14; K7). That fits a device
    carrying its own 20.7 kg.
  - So **TR solves are reported separately and are not used for H4** (the K5/K7 rule).
  - **Caveat:** the steady part of the hip moment depends on trunk posture and on where the
    backpack's mass sits, and neither is recorded. A 10° change in trunk lean moves the hip
    moment by about 17 Nm. The correlations are more trustworthy than the shares.

### K7: assistance cases on the mean SM stride (`src/exogait/assist.py`, 2026-11-10)

- **Four exo torques on the same tracking problem:** `none` (zero), `measured` (K5),
  `optimised` (Moco's choice under the measured torque's budget) and `ideal` (Moco's choice at
  almost no cost: an upper bound). Effort is the sum of squared muscle activations integrated
  over the stride, recomputed from each solution.
- **The budget is met by pricing.** Moco cannot constrain the integral of squared torque
  (`notes/decisions.md`, 2026-11-10). Each actuator's squared torque is priced in the effort
  goal, and a secant search adjusts the four prices until each actuator spends 90–102% of the
  measured budget. It took 3–5 solves per participant, each started from the last; the prices
  settle at 0.13–2.68. A first version scaled the `ideal` torque down to the budget and
  replayed it: that only matched `measured` (−0.7% for HL03), because `ideal` saturates at
  ±80 Nm and its scaled copy is a poor shape.
- **Second starts.** One solve per case is not enough (K5). `measured` was re-solved from the
  `none` solution and `none` from the `optimised` one, and the lower objective kept. On the 16
  SM comparisons the `measured` objective improved by more than 10% twice (AB69 −36%, AB80
  −15%) and by 3% or less otherwise; `none` by 5% or less. `optimised` has one start: when HL03
  was re-solved from a better `measured` solution its `optimised` effort fell from 0.422 to
  0.350, so a single start understates `optimised` if anything.
- **SM walking, mean strides, 16 participants, after the second starts** (HL01 and HL05 are
  left out because their `measured` solves miss the tracking bound, AB82 because of its stuck
  gauge):

  | Effort | median | range | lower in | Wilcoxon signed-rank |
  |---|---|---|---|---|
  | `measured` vs `none` | −15.9% | −29.7 to +24.1% | 14 of 16 | p = 0.0092 |
  | `optimised` vs `measured` | −33.6% | −50.3 to −26.3% | 16 of 16 | p = 3.1e-5 |
  | `optimised` vs `none` | −43.4% | −62.8 to −35.5% | 16 of 16 | p = 3.1e-5 |

  Median effort: `none` 0.474, `measured` 0.438, `optimised` 0.268. Hip and knee are tracked
  within 2.3° in every solve, and `optimised` spends 0.90–1.02 of each actuator's budget.
  Before the second starts the three medians were −14.6%, −33.0% and −42.3%.
  - **The measured SM torque does not help everyone.** It raises the model's effort for AB70
    (+8%) and AB75 (+24%, the slowest walker). Both held up under the second start.
  - `ideal` (HL03, AB68 only): −60% and −59% against `none`, spending 7–39 times the budget.
  - Figures: `figures/k7_all_participants.png`, and `figures/k7_hl03_sm_walking_assist.png` for
    the torques of one participant.
- **Smoothness.** The optimised torque's rate is 2.3 times the measured torque's (median;
  1.1–3.6), with sharp pulses at heel strike. The gain does not depend on them. Low-passed at
  3 Hz and rescaled to the measured budget, then replayed, the optimised torque is as smooth as
  the measured one and still lowers effort against it: HL03 −25% (−32% unsmoothed), AB68 −36%
  (−39%). (Rate RMS at the four actuators, Nm/s. HL03: measured 50–94, optimised 144–281,
  smoothed 51–94. AB68: 43–83, 83–169, 43–71.)
- **TR walking, 14 participants, after the second starts:** `measured` vs `none` −33.7%
  (median; −48.8 to −0.2%; lower in 14 of 14; p = 0.00012). Not an H4 result: see K6. The TR
  second starts changed little (`measured`: HL01 −5%, HL04 −2%, AB72 −1%, the rest under 0.5%;
  `none` unchanged). AB75's second start stalled as its first had and was stopped. The `none`
  solve misses the 3° hip bound for AB71 (3.35°) and AB78 (3.27°), and HL05 is out as before.
- **What this is not.** One mean stride per participant, on a generic 2D body. Effort is a
  model quantity: nothing here is checked against metabolic cost or EMG. Effort is mesh
  dependent (9% lower at 100 intervals for HL03), so only same-mesh comparisons are made. The
  budget is computed from the gauge torque with its offset left in. `none` is an X2 with no
  friction or rotor inertia, which flatters it. The `ai` case waits for K3.
- **Cost.** `none`: 46–204 iterations from the `measured` solution (2–8 minutes). `optimised`:
  3–5 such solves. A full SM comparison took 10–20 minutes per participant, three at a time, and
  the two second starts another 5–10.

### K2 with J3–J5: strides, splits and baselines on all 19 (`preprocess.py`, `split.py`, `evaluate.py`, 2026-11-10)

Kurian took J3–J5 over (`decisions.md`, 2026-11-10). All numbers below are from all 19 files.

- **Strides.** 9,697 detected (heel strike to heel strike, with at least one row in a labelled
  condition), **5,964 kept**: 220 (AB78) to 458 (AB79) per participant.

  | Dropped for | Strides |
  |---|---|
  | crossing a label change (into a turn, a transition, another pass) | 2,237 |
  | marked incomplete by the dataset (`step_complete` False) | 1,399 |
  | outlier duration (outside 0.5–1.5 of the median complete stride) | 75 |
  | sampling holes (one over 50 ms, or over 20% of samples missing) | 22 |
  | crossing a removed rest; a dt ≤ 0 inside | 0; 0 |

  - Every removed rest and every dt ≤ 0 sits among `UNDEFINED` rows, so a stride that touches
    one already fails the label rule. The two rules stay in the code.
  - **What `step_complete` False means.** Looked at on AB68, HL03, AB72, AB82 and HL05 (2,034
    candidates inside one block). It marks the first stride of most passes (9–39 per
    participant: a normal duration, one heel strike of the other leg) and the phase wraps while
    standing (0.1–0.5 of a stride long, mostly with no heel strike of the other leg). The 1,618
    strides it calls complete are real: one heel strike of the other leg in each (two in 7 of
    HL05's), and none shorter than half the median.
  - Durations of the complete strides: 1,546 of 1,618 within 0.75–1.25 of the median, 30 below
    0.75, 25 in 1.25–1.5, 17 above 1.5 (pauses, up to 2.4 times). Kept strides last 1.3–11.4 s
    (median 3.2 s; 99% under 6.4 s; the long ones are stairs).
  - Sampling holes: single dropped samples are everywhere in the AB files (6.6% of AB68's
    intervals), and holes reach 33 ms routinely. In the kept strides the worst hole is 45 ms and
    the most missing 19.7%. The 22 dropped strides are in AB76 and AB78 (11 each).
- **The clock restarts in five files.** `time` steps backwards once in AB69 (−114 s), AB72
  (−1,230 s), AB80 (−1,309 s) and AB82 (−1,347 s), and three times in AB76 (−999, −1,705,
  −109 s), each time between two `UNDEFINED` rows, and then runs over the same seconds again.
  This is what J2's "1–3 dt ≤ 0 in AB69/72/76/80/82" was. The HL files' 33 dt ≤ 0 are repeated
  time stamps. So `t` does not order a session. `split.py`'s self-check found it: 16 of AB72's
  test strides "overlapped" training strides in time. Strides and blocks are now numbered by raw
  row, each stride carries `row_start, row_end`, and the overlap check runs on rows.
- **Stuck gauge.** AB82's left-knee gauge is constant in 94 kept left strides (SM walking 36,
  SM ramps 17 + 12, TR ramps 15 + 14), as K5 found on the mean strides. It is written as NaN.
  No other channel is stuck: the smallest movement of a live gauge over a kept stride is 10 Nm
  (knee) and 19 Nm (hip), against a 0.5 Nm threshold.
- **Kept strides per condition** (both legs; minimum, median, maximum over participants):

  | | SM | TR |
  |---|---|---|
  | walk | 42, 81, 139 | 47, 71, 139 |
  | ramp up | 13, 23, 43 | 8, 20, 34 |
  | ramp down | 14, 27, 45 | 6, 24, 35 |
  | stairs up | 13, 15, 21 | 10, 15, 20 |
  | stairs down | 0, 14, 22 | 6, 12, 17 |

  AB80 has no kept stride on SM stairs down (4 detected per leg, all crossing a label change).
- **Blocks and splits.** A condition has three blocks in 132 of the 190 participant × mode ×
  controller cells, five in 35 (walking), four in 12, two in 7, one in 2 (AB79's TR ramps), seven
  in 1. A block holds 1–33 strides (median 7). So whole-block splits fall into thirds: 35.8%
  of the strides train, 31.3% val, 32.8% test, not the planned 60/20/20. Seven conditions have
  no val block; three have no personalised test (AB79's two TR ramps, AB80's SM stairs down).
  Test strides per condition (median): walk 23–26, ramps 7–8, stairs 4–5.
- **Size and time.** 134 MB for all 19 (5–11 MB each). `preprocess.py all` takes 80 s,
  `split.py` 2 s, the two baselines on the val blocks 57 s (456 fits each).
- **Baselines on the validation blocks** (full inputs; RMSE in Nm, the mean over participants,
  controllers and joints). These are not the test numbers: the test blocks wait for the final pass.

  | Torque | Model | Scheme | walk | ramp up | ramp down | stairs up | stairs down |
  |---|---|---|---|---|---|---|---|
  | gauge | phase mean | personalised | 8.0 | 8.7 | 9.1 | 8.2 | 11.0 |
  | gauge | phase mean | population | 10.1 | 9.9 | 10.6 | 9.5 | 11.5 |
  | gauge | ridge | personalised | 7.5 | 8.3 | 8.1 | 10.5 | 10.9 |
  | gauge | ridge | population | 8.8 | 9.4 | 9.3 | 11.3 | 11.7 |
  | motor | phase mean | personalised | 16.4 | 17.8 | 18.4 | 15.8 | 18.4 |
  | motor | phase mean | population | 17.8 | 18.0 | 18.5 | 15.5 | 17.3 |
  | motor | ridge | personalised | 15.4 | 15.5 | 15.9 | 14.9 | 16.0 |
  | motor | ridge | population | 15.9 | 16.0 | 16.3 | 15.1 | 16.2 |

  - Walking R² (median; hip, knee): gauge torque 0.48, 0.58 (personalised phase mean) and 0.56,
    0.60 (personalised ridge). Motor torque 0.14, 0.37 and 0.18, 0.48. nRMSE is 0.08–0.12.
  - **The motor torque is the hard target, and K6 says why.** About half of it is the rotor's
    inertia times the joint acceleration, and acceleration is not an input: the baselines see
    angle and velocity at one instant. Their hip R² is under 0.2. A model that sees acceleration
    (a derived input, or a sequence model) should do much better. That is the first thing to try
    in K3.
  - Directions on val, walking, per participant (both controllers and joints pooled), ridge on
    the gauge torque: personalised 7.7 vs population 8.8 Nm (lower in 19 of 19); with phase 7.7
    vs without 8.9 (19 of 19); with mode 7.7 vs without 7.9 (19 of 19). On the phase mean the
    mode input matters on stairs, not on walking (stairs up 8.2 vs 11.1 Nm without it), so H3's
    endpoint cannot be walking alone (J7).
  - Ridge's alpha does not matter: val RMSE is the same to 0.1% for 0.01–100.
  - Inference: 0.04–0.06 ms per stride.

### A film of the solved stride (`src/exogait/animate.py`, 2026-11-10)

- `figures/k7_hl03_sm_walking_stride.mp4` (three strides), `.gif` (one, looping) and `.png`:
  HL03's mean SM stride with the exo off, the measured torque and the optimised torque, side by
  side in real time. Muscle paths are coloured by activation; an orange wedge at each hip and knee
  motor shows the exo torque; the right hip and knee torque run underneath with a cursor.
- It draws the solutions as they are: the 103 nodes of each `.sto`, nothing smoothed. Effort is
  recomputed from each solution: 0.636, 0.516 (−19%) and 0.350 (−45%) for HL03.
- Two things the film shows that the tables do not. HL03 walks at 0.29 m/s, so the pelvis nearly
  stops once per stride (its slowest forward speed is 0.00–0.01 m/s). And the contact spheres
  sink 2.6 cm into the floor at most: the contact model's give, the same in all three cases.
- The drawn foot is rigid (the model's toe joint is welded), so its tip dips under the floor
  line at toe-off. The contact spheres do not.

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

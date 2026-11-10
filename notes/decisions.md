# Decisions

Why things are the way they are, including the ones that were reversed. When a reviewer or your
mentor asks "why did you do it that way", the answer is here.

---

## Project framing

### 2026-09-19: REALIGNED TO THE TITLE — read this first

The extension-of-Zhang framing (below) produced good validated work but drifted off three terms of
the project title: OpenSim Moco, AI-Driven, and Lower-Limb.

**Why it drifted, and it was structural rather than careless.** Zhang et al. sell *avoiding*
musculoskeletal modelling as a feature of their method. Reproducing their controller faithfully
meant inheriting that avoidance, so there was never a reason to open OpenSim. Their work is
single-joint, so nothing pushed toward hip/knee/ankle. And their only machine-learning component is
a regression we bypassed entirely by using their published numbers directly.

**The fix:** the title is the specification. The papers are component sources and validation
targets, not the frame.

- OpenSim Moco becomes the core — it produces the per-muscle forces the fatigue layer consumes
- Lower-limb means hip, knee and ankle, with muscles spanning two joints as the mechanism
- The AI becomes structurally necessary rather than decorative: fatigue-aware allocation must
  evaluate many assistance profiles, each needing a Moco solve taking minutes, inside a loop that
  must run in milliseconds. The surrogate is what closes that loop

**Nothing built so far is wasted.** The smoothed fatigue model becomes the fatigue layer's enabler,
the calibration becomes the personalisation method, and the reproduced controller becomes both the
single-joint baseline and the proof the fatigue layer is correct.

**What I got wrong:** when we pivoted to the extension framing, the original plan's learned-surrogate
component was dropped and nothing replaced it. That silently removed the AI half of the title, and I
did not flag the trade at the time. Worth remembering as a failure mode — a pivot that improves one
axis can quietly cost another.

Old guide archived at `docs/guide_v2_extension_framing.md`.

---

### Extend a published paper rather than claim independent novelty
*(superseded by the realignment above — kept because the reasoning still applies to how the papers
are used)*

The first plan assembled five known techniques into one pipeline. That is competent engineering and
an unpublishable paper — a reviewer asks what is new and the honest answer would have been "the
combination".

Anchoring to Zhang et al. and extending it is a normal, respectable way to do research, and it gives
every result a published number to be checked against.

### Validate against their published numbers, since we have no hardware

Simulation-only means we cannot validate against our own experiments. So we validate against theirs:
66.95 / 73.60 / 76.15 seconds. Turns "trust our simulation" into "our simulation reproduces a
published result to 1.7%".

### Fit the tiring-rate constant to one trial, predict the other two

`C_F` is subject-specific and unpublished, so it has to be fitted. Fitting it on the no-assistance
trial leaves the two assisted trials as genuine predictions. The fitted point proves nothing; the
other two are the test. **Do not present all three as validation.**

---

## Modelling

### Keep the simple fatigue model, do not switch to the three-compartment one

The three-compartment model (Xia and Frey-Law 2008) is more physiologically detailed. We use the
simpler one anyway, because staying in the same lineage as both anchor papers keeps every number
directly comparable to theirs. Switching models would make us incomparable and would spend the
project on model choice instead of the actual question.

Note it as an alternative. Do not spend the project on it.

### Blend the switch with an S-curve, single function, not two implementations

One function with a width parameter: zero gives the exact original, positive gives the smooth
version. No second implementation to keep in sync, and the exact case stays testable against the
authors' code.

### Reversed: fatigue does not need to live inside OpenSim

An earlier plan required writing a C++ component for OpenSim to add fatigue as a model state. That
was the single riskiest dependency in the project — a compiler toolchain that commonly defeats
people, with unhelpful error messages.

Anchoring to their controller instead means fatigue lives in our own optimisation problem. **The C++
requirement disappeared entirely.**

**This survives the realignment, and it is the key de-risking fact of the whole project.** The new
architecture is two layers: OpenSim Moco produces per-muscle forces, and our own CasADi layer carries
the fatigue states and the allocation optimisation on top. So OpenSim is used properly and centrally
— it does the musculoskeletal work — without ever needing a custom compiled component. This is also
exactly the pattern Peternel et al. 2019 used (OpenSim offline for muscle forces, their own
controller online), so there is a published precedent for the split.

### Give both controllers perfect future knowledge for the E1 comparison

To measure what the frozen switch costs, both versions get exact future torque. Otherwise the
comparison confounds two separate problems — the switch handling and the torque prediction. Torque
prediction is E5 and gets measured separately.

---

## Numerical

### Match the reference implementation's crude integration on purpose

Fixed-step simplest-method integration, and clamping, are kept so the exact case is bit-comparable
against the authors' code. A better integrator would have been more accurate but would have removed
our ability to prove the transcription is right.

The clamping is inert — the equation keeps the value in range on its own. Verified, not assumed.

### Tabulate the policy instead of solving every time step

Valid only because the static squat is a hold, so the best action depends on one slowly-changing
quantity. Validated against the full solve (0.54% apart), and the source says to quote the full-solve
number. **Does not transfer to cyclic tasks.**

### Tune the energy-versus-tiredness knob, and say so

The paper never publishes `w_r`. We set it to 0.9 so mean assistance matches their reported effort
drop. Assistance *level* is therefore fitted; the ramp *shape* and the force-limit saturation are
predictions. Stated in the source, the commit message and the notes — this is exactly the kind of
thing that looks like concealment if a reviewer finds it themselves.

### Trim the default sweeps so the checks actually run

The full sweeps take about ten minutes and kept hitting timeouts. Defaults are trimmed to a few
minutes; the full numbers are recorded in a comment. A check nobody runs is not a check.

---

## Scope changes forced by the literature

### Dropped: the tiredness observer

An early plan estimated tiredness from muscle electrical signals. Zhang et al. do exactly this. Dead
as a standalone contribution.

### Dropped: grouping muscles into natural combinations (E9)

Lambeth et al. 2025 does exactly this, with a measured computation saving. Use the technique, cite
them, drop the claim.

### Narrowed: multi-joint allocation (E2)

Fatigue-driven allocation across hip, knee and ankle exists — Lambeth 2025 and Bao 2020. Both are
for braces combining motors with electrical muscle stimulation, where the tiredness is caused by the
stimulation itself and behaves differently from ordinary walking fatigue.

**The surviving wedge is muscles that span two joints.** Searching for that specific combination
returns three papers, all from before 2006. Now E2's stated angle, and it is evidence-backed rather
than asserted.

### Promoted: E1 is now the lead contribution

Searching for "smoothing a fatigue model for use inside an optimiser" returns one hit, from 1999,
unrelated. Strongest surviving claim.

**Still provisional** — PubMed covers engineering badly, and this is exactly the kind of work that
lives on arXiv. Check before committing to the framing.

### Changed how E4 is justified

The original argument was that walking needs full physics rather than a simplified static
calculation. Then Peternel 2019 turned up citing Anderson and Pandy: for walking, the quick method
gives practically the same answer as the thorough one.

So E4 cannot be justified on accuracy of muscle force estimates. It has to be justified by the
look-ahead prediction problem instead. **Do not overclaim this — a reviewer who knows the literature
will catch it.**

---

## Practical

### Do not edit the vendored reference code

`external/PHRC/` is the validation baseline. Editing it — including fixing the known bug — destroys
its purpose. Fix things in our own code. The NOTICE file says so.

### Commit identity

Until 2026-10-02 everything went in as `kurianjose7586 / kurianjose005@gmail.com`. The first
commit went out under a different address picked up from the environment and had to be rewritten.

**Changed 2026-10-02:** with two people on the project, each commits under their own name.
Agreed with Kurian. Work goes on branches, not straight onto `main`.

---

## Pipeline build (2026-10-02)

### Gait objective: minimise the worst muscle's fatigue, not time to V_th

Under cyclic load the fatigue switch settles to an equilibrium: tiring while the muscle is on,
recovering at R = 0.5 while it is off. With the lineage's R that equilibrium sits well below
V_th = 0.8 for normal walking, so "time to V_th" is infinite and Peternel's max-min endurance
(eq. 10) is undefined. Its cyclic analogue is minimising the worst muscle's fatigue (`peak_V`).

**Side effect worth a sentence in the paper:** the equilibrium does not depend on the capacity
C at all, only on the activation pattern, R and M_th. C sets how fast the equilibrium is
approached. So the Phase C ranking does not rest on the unknown gait-muscle C. Verified on the
toy plant: C = 8.2 and C = 100 both settle at 0.58.

C is set to Zhang's fitted 8.2365 for every muscle, the only measured value we have. R stays
0.5, and that matters much more now, because R sets the equilibrium. E6 (recovery-rate
sensitivity) is promoted from supporting to necessary.

### Exoskeleton = Dembia et al.'s ideal assistive device, capacity allocated per joint

Each joint gets a torque actuator that the optimiser uses freely (effort weight 1e-3), capped at
`|tau| <= p_j * peak|tau_net_j|`. Here `p_j` is the device's capacity at joint j, and Phase C
allocates capacity under a shared budget. This is the Dembia, Silder, Uchida, Hicks, Delp (2017)
formulation, the methodological template this guide already cites, so it is citable rather
than invented.

**Reversed twice in one day, and why.**
1. First attempt: a prescribed `tau = p * tau_net(t)` through a PrescribedController. MocoInverse
   was infeasible even at p = 0.
2. Second attempt: the same prescribed torque applied as +/- body torques. An ID re-solve with
   the device at p = 1 should leave zero joint torque. It left 15% (hip, knee) and 62% (ankle)
   of the net moment, plus 3–5 Nm of noise. Cause not found. Abandoned rather than patched.
3. The ideal device is a plain CoordinateActuator, so it is exact by construction and works for
   the 3D model too.

**What changes in meaning:** `p` is no longer "fraction of torque compensated" (Zhang's p). It is
torque *capacity*, and the optimiser decides the profile. The single-joint baseline is still
the same formulation with two capacities set to zero.

### Moco objective hygiene: three rules, each learned from a wrong answer

- **Price what muscles cannot change at ~0.** The pelvis residuals and the torso actuator
  (`lumbarAct`) are fixed by the kinematics. At optimal force 1 they dominated the objective, and
  at tolerance 1e-3 the muscle activations were never actually optimised (full assistance left
  them unchanged). They now use optimal force 1000.
- **Same reserves at every p.** `ModOpAddReserves` skips coordinates that already have an
  actuator by default, so adding the exo silently removed the joint reserves and made p = 0.3
  infeasible. They are now forced on everywhere.
- **Tolerance 1e-4, not 1e-3.** At 1e-3, activations at p = 1 sat ~0.02 too high (0.035 against
  0.016 at 1e-4). The fatigue threshold M_th = 0.05 is at exactly that scale, so solver noise
  could flip fatigue and recovery modes. It is also faster after the first fix: 26 s unassisted.

### Only the musculoskeletal map is learned; fatigue is integrated exactly

The guide says D2 learns "musculoskeletal + fatigue dynamics". The fatigue ODE is known, smooth
and differentiable, so learning it would only add error. The surrogate learns
(subject, condition, p) -> activations, and the exact fatigue model runs on top. That is still
end-to-end differentiable, and it is what makes D3's state transitions trustworthy apart from
the surrogate itself.

### Subject variation without re-scaling segment lengths

D1 varies body mass, muscle strength, walking speed (time-scaled kinematics) and carried load.
It does not vary segment lengths, because the reference kinematics belong to one body.
Contact stiffness is scaled with total mass so that ground reaction scales with body weight
(the contact law is linear in stiffness). Real per-subject geometry comes with the Camargo
data (Phase A2), which is the supervisor's data-loading track.

### One Docker image for every stage

OpenSim, PyTorch and stable-baselines3 in one image, with the repo mounted rather than baked
in. This reverses the earlier "separate images" plan. One image means one build and one
`check`, and D4 needs OpenSim and the policy in the same process anyway.
---

## ExoGait plan (from 2026-10-14)

### 2026-10-28: Python only, no MATLAB

**The college has no MATLAB licence.** Kurian's MathWorks account offers only "Link License",
and there is no campus licence to link it to. The mentor's brief made MATLAB the primary
platform: Layer 2 is "MATLAB processing", and the plan assumed the Statistics & ML, Deep
Learning and Signal Processing toolboxes. Without a licence none of that runs. So the whole plan
moves to Python, for both of us.

The mentor is **informed (J1, notice 1), not asked**. There is no MATLAB option to choose
between.

**Why it costs little technically:**

- **Same API.** OpenSim/Moco's Python and MATLAB APIs are generated by SWIG from the same C++
  (MATLAB goes through the Java bindings). The classes and method names are the same:
  `example2DWalking.py` and `example2DWalking.m` set up the same problem line for line. K1
  already runs MocoTrack from Python, in 39 s.
- **Every toolbox has a free equivalent:**

  | MATLAB toolbox | Used for | Python |
  |---|---|---|
  | Statistics & ML | `fitrensemble`/`TreeBagger`, `fitrgp`, `ridge`, `signrank` | scikit-learn, `scipy.stats` |
  | Deep Learning | `lstmLayer` | PyTorch, on the RTX 2050 |
  | Signal Processing | `butter`, `filtfilt` | `scipy.signal` |

- **Nothing to port.** The rest of the repo was already Python: the twin, the sweeps and the DGX
  image.
- **The risk was already planned for.** `PROJECT_GUIDE.md` listed "MATLAB access delayed" as a
  risk, with the mitigation "everything works in Python; port last". This is that risk realised.

**What it costs:**

- **A deviation from the mentor's brief.** It is stated and explained, not hidden.
- **A title term.** The title says "Using MATLAB–OpenSim Moco", and that term is not delivered
  unless a licence appears. The 2026-09-19 lesson applies: a change that fixes one thing can
  quietly cost a title term. So the cost is stated up front, and the notice asks whether the
  registered title has to change.
- **No MATLAB code** for anyone who expected to read it. The mentor reviews Python instead.

**How the risk is contained:**

- **Every handoff and result file is MATLAB-readable:** `.osim`, `.sto` and `.csv` (and `.png`).
  Model weights (`.joblib`, `.pt`) are Python-only intermediates; their predictions are CSV.
- **A port happens only if a licence appears, and it would be small.** The Moco scripts keep
  their API names, and every input they need already opens with `readtable` or OpenSim's own
  readers.
- **No parallel MATLAB code now, and not Octave either.** OpenSim's MATLAB scripting runs through
  MATLAB's Java bridge (`configureOpenSim.m`). That is untested in Octave, and nothing needs it.

**What changed in the plan** (`docs/KURIAN_TASKS.md`, `docs/JASITH_TASKS.md`):

- **Code location.** Layer 2 is Python processing, and the code goes in one flat package,
  `src/exogait/`, instead of `matlab/`.
- **Tasks.**
  - K1 closes without MATLAB.
  - J1 question 1 becomes a notice.
  - J8 also removes MATLAB from README and PROJECT_GUIDE. The ONBOARDING edits (env recipe,
    the §8 MATLAB clause) go in with this replan.
- **One env on both machines:** the micromamba `opensim` env, plus scikit-learn and torch (the
  CUDA wheel on Kurian's machine, the CPU wheel on Jasith's).
  - torch and opensim stay in separate processes. They did work in one process in the D4 smoke
    run (2026-10-02) and in the Docker build check, but the K1 env has not been tried with
    torch, the CUDA wheel with opensim is untested, and nothing in the ExoGait plan needs both:
    they hand off through CSV and `.sto`.
- **The parked DGX/Docker pipeline** is Python, so it is usable again. It is expected for K9 at
  full scale: one ExoGait stride is about 2.9 s, so the Moco solves take minutes each.

### 2026-10-28: K4 mapping: the X2 hip is split into pelvis and hip with a per-participant c

The X2 hip encoder reads the thigh relative to the backpack, not the pelvis (checked on all 19:
`notes/observations.md`, "K4"). So `pelvis_tilt` = `BackPackAngle` − 90° + c and `hip_flexion` =
X2 hip − c, with knee unchanged. Their sum, the thigh angle, does not depend on c.

- **c per participant**, holding the mean walking pelvis tilt at the 2D reference's −15.06°.
  c = 0 puts the hip about 12° below the model's range, and one global c would carry the 13°
  AB-vs-HL backpack offset into the pelvis. A per-trial c would erase the real TR-vs-SM
  backpack shift.
- **Rejected:** a fixed hip offset (the best constant varies +3 to +16° by condition) and
  treating the backpack as the torso (pelvis tilt −28 to 0°, carrying the site offset).
- **Revisit** if the authors give a calibration posture or the IMU mounting angle (J1).

The tracking target is the **mean of clean strides**, made periodic with its mean kept, not one
stride: single strides are 3.8–4.6° RMS from the mean and their end-start mismatch is 1.4–5.5°.
K5 starts there for cost and settings, then moves to single strides for K7's per-stride cases.

### 2026-11-10: the exo torque in OpenSim is `JointTorquesViaGauges`, not `JointTorques`

`JointTorques` is the motor-side torque. `JointTorquesViaGauges` is the torque at the joint
output, which is what the links and the leg feel. Evidence, all 19 participants, TR and SM
walking, 4 joints (`checks.py` asserts it):

- `JointTorques` − gauges = I·q̈ + Coulomb + viscous friction + a constant, with R² 0.82–0.98
  (median 0.93).
- The fitted I is 1.78–2.29 kg m² (median 2.06). The published X2 rotor inertia is 1.87 kg m²
  (T-RO Table II).
- That rotor-and-friction part is about 23 Nm RMS, as large as the torque itself. This is why
  the two columns looked uncorrelated in J2.

So K5, K6 and K7 replay the mean gauge torque on the model's exo actuators. The model then
needs no rotor or friction model, since both sit on the motor side of the gauge.

- **Caveat:** the constant is not zero: hip −3.5 Nm (median; −6.9 to +2.6), knee +1.7 Nm
  (−1.8 to +13.6). It is either a gauge offset or direction-dependent friction, and the data
  cannot tell which. It is left in the replayed torque.
- **For J1 Q9 (the prediction target):** the two columns answer different questions.
  `JointTorques` is what the controller commanded the motor to do, and about half of it moves
  the motor's own rotor. The gauge torque is what reached the wearer. Q9's text now says so.

### 2026-11-10: K5 settings: tracking weight 10, loose ankle prior, speed not imposed, warm start

Tested on HL03 SM walking, mean stride, 50 mesh intervals (`notes/observations.md`, "K5"):

- **Tracking weight 10 against effort 1.** At 1 (the K4 trial's ratio) the knee ran 4° too
  straight through stance and the hip 3–5° short of extension: 2.5–3.8° RMSE. At 10 it is
  0.6–1.2°.
- **The stock walk's ankle at weight 0.01** (against effort; the J1 Q7 default). With the ankle
  fully free it fluttered ±10° in swing.
- **Speed is not imposed.** The first version forced the pelvis to advance by a stride length
  estimated from the tracked angles; the estimate was 15% long and the solve sat on its bound.
  Now the pelvis only has to move forward, and the stride length is the model's own. It then
  matches the data-based estimates (K4's stride analysis), which makes it a check, not an input.
- **Every solve starts from a stored converged stride** (`models/exogait/seed_stride.sto`, HL03
  SM). From the tracked states alone IPOPT converged once in five tries; from the seed it
  converged for every participant and controller. The seed came from that one cold run
  (tracking weight 1, no ankle prior), re-solved with the final settings.
- **Mesh:** 50 intervals per stride. At 100 the hip and knee RMSE change by under 0.05°, but
  the effort integral is 9% lower and the heel-strike force peaks are higher, so effort is
  compared only between solves on the same mesh.
- **Rejected:** OpenSim's `TabOpLowPassFilter` on the reference, in favour of a periodic 6 Hz
  low-pass (the same one the replayed torque gets; the curves stay periodic); and a per-solve
  rewrite of the model file (parallel solves collided on it).
- **Worked around:** `apply_tracked_states_to_guess` is off whenever a guess is given. MocoTrack
  resamples the tracked states onto the guess grid, and for some stride durations its own last
  time lands one floating-point digit short of the final time, which `resample()` rejects.

### 2026-11-10: K7's `optimised` case is the free optimum scaled to the measured budget

The plan gave `optimised` the measured torque's budget (per actuator, the integral of squared
torque) as a Moco endpoint constraint. Moco 4.6 cannot do that: `MocoControlGoal` has no
constraint mode, and `MocoOutputGoal` on the actuator's `actuation` output fails with a stale
cache error at Stage Velocity.

So there are two solves instead of one:

- **`ideal`:** Moco chooses the exo torque freely within ±80 Nm. It beats `measured` by
  construction, so it is reported only as an upper bound (as J1 Q5 already said).
- **`optimised`:** the `ideal` torque, scaled down per actuator until its integral of squared
  torque equals the measured one, then replayed. This is the H4 test.

It is conservative: the true optimum under the budget is at least as good as a scaled copy of
the unconstrained one. If `optimised` beats `measured`, H4 holds for that stride. If it does
not, that stride is inconclusive, not a failure of H4.

### 2026-11-10: every `measured` and `none` solve gets a second start

IPOPT does not always land on the same solution. Five `measured` solves were repeated from the
same seed after a marginal change to the reference's low-pass filter:

| | objective, first → repeat | effort, first → repeat |
|---|---|---|
| HL03 SM | 1.350 → 1.019 | 0.530 → 0.516 |
| AB68 SM | 0.628 → 0.641 | 0.341 → 0.361 |
| AB68 TR | 1.016 → 1.114 | 0.553 → 0.589 |
| AB69 SM | 0.677 → 1.159 | 0.392 → 0.839 |
| AB69 TR | 0.720 → 0.733 | 0.456 → 0.461 |

Three agree within 6% on effort. HL03's first solve had stayed at the seed's own optimum, a
poorer one. AB69 SM's repeat came back with twice the effort: a clearly worse local solution.
Tracking error barely moves between them (0.4° to 0.6° at worst), so K5's tracking results
stand, but one solve per case is not enough for an effort comparison.

**Rule:** `assist.py second` re-solves `measured` from the `none` solution and `none` from the
`optimised` solution (from `measured` where there is no `optimised`), and keeps whichever has
the lower objective. On the 16 SM comparisons the second start improved the `measured`
objective by more than 10% twice (AB69 −36%, AB80 −15%) and by 3% or less otherwise; `none`
moved by 5% or less. The medians barely moved (`optimised` vs `measured` −33.0% → −33.6%). On
the 14 TR pairs the largest change was 5%.

- **`optimised` gets one start.** Its price search is 3–5 solves, and a second search would
  double the cost. When HL03 was re-solved from a better start, its `optimised` effort fell
  further (0.422 → 0.350), so a single start understates `optimised` if anything: the
  comparison is conservative for H4.
- **Next:** a proper multi-start (several starts for every case, the best kept) before any
  effort number is reported as final. It roughly doubles K9's solve count.

### 2026-11-10: Kurian takes J3–J5; the stride, split and scoring rules

**Why.** J3, J4 and J5 had not been started, and K2, K3, K7's `ai` case and K9 all waited on
them. Kurian asked his side to do them. They are in one PR for Jasith to review. `docs/JASITH_TASKS.md`
keeps the plan as written and says what was built.

**Stride rules** (`preprocess.py`). Chosen from the data, on five participants first, then
checked on all 19 (`observations.md`, "K2"):
- **Complete strides only.** The dataset's own `step_complete` flag decides. It removes the
  first stride of a pass and the phase wraps while standing. Rejected: a duration rule alone
  (it cannot tell a first stride from a steady one), and K4's stricter filters (toe-off timing,
  bout edges, the gyro check), which are for a clean mean stride and would cost the models data.
- **Duration within 0.5–1.5 of the median complete stride** of that participant, condition and
  leg. 99% of complete strides are inside 0.70–1.50; the rest are pauses.
- **Sampling holes:** a stride goes only for a hole over 50 ms (about one phase point of a slow
  stride) or over 20% missing. Single dropped samples are everywhere and harmless at 101 points.
- **Order by raw row, not by `t`**: the clock restarts in five files.
- **A stuck gauge is NaN**, not a dropped stride: the stride's other channels are fine.
- **The other leg's gauge torque is carried, not its motor torque**: K5 replays the gauge torque.

**Splits** (`split.py`). The rule is the planned one (whole blocks, the last to test, the ones
before to val). With three blocks per condition it gives thirds, not 60/20/20. Kept: one block
each is the only whole-block split of three blocks, and the final models are refitted on train +
val (two thirds) before the test blocks are scored.

**Scoring** (`evaluate.py`).
- **Two torques, fitted separately** (`motor`, `gauge`), per J1 Q9's default. One four-output fit
  was rejected: a tree's splits would trade one torque off against the other, and AB82's NaN
  gauge rows would have to leave the motor fit too.
- **`leg` is an input**, and the phase mean is keyed on it. Each gauge channel has its own
  offset of a few Nm, so a model that cannot tell left from right carries that as error.
- **nRMSE = RMSE / the range of the measured torque** over all that participant's strides in
  that mode, both controllers, so SM and TR share a scale.
- **The test blocks are not scored yet.** Everything so far is on val. One `--test` pass scores
  every model, the baselines included, after K3's choices are made on val.
- The self-check writes to `predict/selfcheck/`: a population model depends on who is on disk,
  so a two-participant run must not overwrite the real rows.

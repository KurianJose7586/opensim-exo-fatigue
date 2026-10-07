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
  the thing to try. **Update 2026-10-07 (review):** the pooled 7 Nm hides where it is. Per
  joint, unassisted: right hip 17.3 Nm RMS, **125 Nm peak** (of a 135 Nm peak hip moment), right
  knee 8.1 RMS / 65 peak, everything else under 1 Nm. The peak is the heel-strike impact (vertical
  force 1.67x body weight from the stiff contact spheres). So the hip and knee peaks that define p
  are mostly reserve torque, and hip assistance mostly replaces reserve (17.3 -> 7.8 Nm RMS at
  p_hip = 0.4). Now reported per joint (`reserve_rms_joint`, `reserve_max_joint`).
- **Soleus barely responds to ankle assistance** (−7% at 30% capacity; 0.062 even at p = 1 where
  other muscles reach 0.01–0.02). Gastroc and tib_ant respond normally. Unexplained. Look before
  any ankle claim goes into the paper. **Mostly explained 2026-10-07 (review):** the −7% was the
  ALL-joints test (0.3, 0.3, 0.3). Ankle-only 0.3 gave −19% (−24% in the first half of the cycle,
  −5% in the second). The rest: knee assistance shifts plantarflexion from gastroc to soleus (the
  biarticular redistribution itself), and the left-side cap bug below left the second half with
  a 4.7 Nm ankle device instead of 16.9 Nm.

### Review 2026-10-07: device cap was per side, so the second half of the cycle was under-assisted

`_add_exo` capped each leg at p x that leg's OWN peak net moment over the half-cycle window. The
window is right heel strike to left heel strike, so the right leg's window holds its stance and
the left leg's holds mostly swing. Peaks: hip 135 / 30 Nm, knee 89 / 9 Nm, ankle 42 / 12 Nm
(right / left). The left leg's activations are the stitched cycle's samples 50-99, so for the
whole second half of every gait cycle the device was 3.6-9.4x weaker than p said. The limiting
muscle, iliopsoas, does most of its work there (mean activation 0.191 vs 0.102 in the first half).
Every Phase C number before this date carries it.

Fix: one cap per joint, the larger of the two sides (the full-cycle peak under the symmetry the
model already assumes). The self-check used equal fake peaks (50 Nm everywhere), so it could not
see this; it now uses unequal ones. Old results kept in `results/pre_review/`.

Same pass: the stitched cycle sampled the junction twice (`linspace` with both endpoints, so
right(t1) and left(t0), the same gait phase, were both kept). Now `endpoint=False`.

### Review 2026-10-07: the 2D model's own source says not to use it for research

OpenSim's `example2DWalking.py`, which ships `2D_gait.osim`: "Do not use this model for research.
The path of the gastroc muscle contains an error--the path does not cross the knee joint." It does
have a knee moment arm, but a wrong one: 2.5 cm at full extension, 1.8 at 29 deg, 0.9 at 57 deg
flexion (it should hold ~2 cm or grow). Gastroc is one of the three biarticular muscles the
contribution claim is about. Same file: the reference kinematics are from a predictive
simulation (Falisse et al. 2019), not measured.

Second problem, contact: the ground reaction comes from two spheres per foot driven by the
prescribed kinematics. Totals are right (mean vertical force 694 N vs 693 N body weight) and the
kinematics are symmetric to ~1.3 deg, but the load moves between heel and toe on ~1 deg
differences. Right ankle at the end of its window: −42 Nm and still rising; left ankle at the
same gait phase (start of its window): +5 Nm. The full-cycle ankle peak is 42 Nm, ~0.6 Nm/kg,
where normal push-off is ~1.5 Nm/kg. So the twin has no real push-off, and Phase C's ankle-heavy
allocations are made on an ankle that is not loaded like a real one.

Decision (with Jasith, 2026-10-07): keep the 2D model for now, fix everything else, and treat
both as blocking for any ankle or gastroc claim. Next step, no download needed: the conda
package ships Moco's `exampleEMGTracking` (3D 92 kg subject, measured kinematics, force-plate
GRF via ExternalLoads, EMG for 8 muscles, one full gait cycle 0.83-2.0 s). That removes the
contact spheres, the stitching, and gives EMG to check activations against. Its coupled knee
crashed one quick moment-arm probe (constraint assembly), so budget time for it.

### Review 2026-10-07: "coupled" is a fixed allocation

On the pre-review grid the steady-state min-max over every candidate, solved once with no
feedback, gave exactly coupled's answer (same p, same worst V) at R = 0.33, 0.5 and 1.0, and a
slightly better one at R = 2.4. In steady walking the fatigue state never changed a decision.
results.md already noted the equality ("the controller reaches the grid optimum") but not what
it means: the margin comes from the OBJECTIVE, not from fatigue feedback. Blind vs coupled is the
cleanest pair in the table (same information, different objective), and no baseline isolated the
per-muscle or biarticular information. Three ablations added to allocate.py (see results.md 9).

### Review 2026-10-07: the threshold moves the result more than R does

M_th was never varied. On the pre-review grid: margin −1.5% at M_th = 0.011, −1.9% at 0.02,
−4.8% at 0.03, −8.8% at 0.05. At the paper's literal "0.02% of MVC" (0.0002), Moco's activation
floor of 0.01 means no muscle ever recovers: every controller reaches V = 1, min-max is undefined,
and time to V = 0.8 is 1.5-2.6 minutes of normal walking. Muscles spend 33-77% of the cycle
below 0.05, so where the threshold sits decides how much recovery there is. run_phase_c.py now
prints the margin over M_th x R.

### Review 2026-10-07: D4 gave the policy information no device has

TwinEnv integrated V from the twin's own activations and the policy observed it. The twin
carries the subject's hidden (randomised) parameters, so their effect leaked into the
observation through V. Real devices cannot measure V at all. Now the policy and the Phase C
controllers observe V_est, the fatigue model integrated over the surrogate's predictions; the
true V only scores. Also in the pre-review smoke D4, the surrogate ranked coupled ahead of the
policy (0.142 vs 0.154) and the twin the reverse (0.176 vs 0.157); NOTES reported only the twin
side. D4 now checks rank agreement and reports end-of-walk V next to mean-over-walk V.

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

## Open questions

- [ ] Resolve the threshold disagreement: 0.05 in code versus 0.02% in the paper. Which did they use?
      Now the most important open constant: it moves the Phase C margin more than R does.
- [ ] Rebuild the twin on measured data (Moco exampleEMGTracking, local): fixes push-off, the
      heel-strike reserves, the stitching and the gastroc path, and gives EMG to validate against.
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

# Results

Every number produced so far, with how it was obtained and how much to trust it.
Reproduce anything here by running the script named in its section.

---

## 1. Smoothed fatigue model — `src/fatigue/model.py`

The fatigue equation has a hard switch: above a threshold the muscle tires, below it the muscle
recovers. A hard switch cannot be handled by the maths engine that picks the control action,
because at the switch point the equation has no well-defined slope. We replaced the switch with a
smooth S-shaped blend controlled by a width `k`. Smaller `k` means a sharper blend, closer to the
original.

### It reproduces the authors' own code exactly

At `k=0` our implementation is bit-for-bit identical to `external/PHRC/`. So the transcription from
the paper is verified, not assumed. This is asserted in the self-check, so it cannot silently rot.

### Convergence as the blend sharpens

```
       k    max|err|   most negative   most positive
   1e-01   2.362e-02       -2.36e-02       +1.67e-06
   1e-02   7.642e-04       -7.64e-04       +1.67e-06
   1e-03   2.594e-05       -2.59e-05       +1.98e-05
   1e-04   1.725e-05       -6.47e-06       +1.72e-05
   1e-05   1.712e-05       -6.13e-06       +1.71e-05
```

Trace: 60 s, two muscles driven by sine activations crossing the threshold, `dt=0.001`.

### The error is one-sided — matters for safety

Above the noise floor the error is **entirely negative**: the smooth version reports *less* tiredness
than the true equation. Just above the threshold it both tires more slowly and recovers faster than
it should.

**Consequence:** a controller trusting the smooth model thinks the user is fresher than they are and
**under-assists**. Erring low, not high. Negligible at usable `k` (2.6e-5 at `k=1e-3`) but this is
the first question a reviewer asks, so state it.

### The error floor is the integrator, not the smoothing

Error stops falling at about 1.7e-5. That is not a limit of the method — it is the fixed-step
integrator stepping over the exact moment of the crossing. Verified by shrinking the step:

```
      dt    floor at k=1e-6
   1e-03         1.712e-05
   1e-04         1.712e-06
   1e-05         1.494e-07
```

Clean factor-of-ten per decade. **So the blend tracks the true equation as closely as the integrator
allows, which means `k` can be chosen purely for numerical convenience — there is no accuracy being
traded away.** That is the useful line for the write-up.

---

## 2. Calibration against Zhang et al. — `src/fatigue/calibrate.py`

In a static squat the muscle effort is roughly constant and always above the threshold, so the
equation never switches and can be solved on paper. That gives a direct link between effort level
and how long until a chosen tiredness level is reached.

We fitted the one unknown constant (`C_F`, how quickly this person tires) **to their
no-assistance trial only**. The other two trials are then predictions.

```
GPR estimate: C_F = 8.2365 s  (fitted on no-assistance only)
  trial                  M    paper    model    error
  no assistance      0.198    66.95    66.95    0.0%  <- fitted
  constant 15%       0.179    73.60    74.06    0.6%
  MFAC               0.175    76.15    75.75   -0.5%
```

**Predicts both untouched trials to within 0.6%.**

Driving the model with their system's *estimated* effort beats using the raw measured electrical
signal (0.6% versus 3.0% error). That is consistent with their controller running on the estimate,
so it is a small independent check that we wired it up the way they did.

### Their own linearity assumption fails in their own data

Their equation 25 assumes effort falls in direct proportion to how much torque the brace takes over.
Their measured effort says otherwise:

```
  constant 15%     commanded 15%   delivered  9.6%   ratio 0.64
  MFAC             commanded 30%   delivered 11.6%   ratio 0.39
```

Caveat, recorded in the source: the no-assistance trial still has the brace on with a small standing
tension, and MFAC only reaches full strength late in the trial. So these are indicative, not a clean
efficiency measurement. The direction is unambiguous though.

**Why it matters:** if commanded torque converts to actual muscle relief at only about two-thirds
efficiency, then *where* you apply assistance matters more than a simple proportional model
suggests. Relevant to E2.

---

## 3. Gate R — reproducing their controller — `src/mpc/mfac.py`

Their controller rebuilt in CasADi with IPOPT, following equations 24-30: the barrier-style cost
that blows up as tiredness approaches its ceiling, plus limits on cable tension and how fast tension
may change.

**Solve time: about 5 ms against their reported 3.53 ms.** Same ballpark, so the problem we built is
about the same size as theirs.

### Plant constants

```
L_a(90 deg) = 0.0944 m      cable lever arm at a 90 degree knee bend
R_e         = 505.1         converts knee torque to muscle effort
F_max binds at p = 0.170    the force limit bites before the 30% assistance limit does
```

That last line matters: **their stated maximum assistance of 30% is never reachable.** The 180 N
cable force limit caps it at about 17%. Consistent with their Figure 7, where cable tension flattens
out at 180 N.

### Result

```
  trial              paper     sim     err   mean p  final p
  no assistance      66.95   66.94  -0.0%    0.000    0.000
  constant 15%       73.60   78.75   7.0%    0.150    0.150
  MFAC               76.15   74.88  -1.7%    0.106    0.170
```

**MFAC reproduced to 1.7%**, and it reproduces the *shape*: help starts at zero, builds as tiredness
grows, and pins at the force limit. Matches their Figure 7 tension trace.

**What is fitted versus predicted.** The paper never publishes `w_r`, the knob trading tiredness
against energy use. We tuned it to 0.9 so mean assistance matches their reported effort drop. So
the assistance *level* is fitted; the ramp *shape* and the force-limit saturation are genuine
predictions.

**The constant-15% miss is their model, not our code.** The 7% over-prediction is exactly the
linearity failure from section 2 propagating through. We implemented their equations faithfully, so
we inherit the error. Second independent confirmation of the same gap.

### A shortcut, validated

Solving the control problem at every one of 7600 time steps takes 75 s per run. But the squat is a
static hold, so after the first fraction of a second the best assistance level depends only on how
tired the person is. Tabulating 40 solves and interpolating runs in 1.7 s.

```
tabulated  t=75.29   mean p=0.1109
full MPC   t=74.88   mean p=0.1061   (7489 solves, 75 s)
difference 0.41 s (0.54%)
```

Checked, not assumed. The shortcut is 0.54% optimistic because it skips the initial ramp-in.
**Quote the full-solve number (74.88 s) in any write-up.**

---

## 4. E1 main result — what the frozen branch costs — `src/mpc/periodic.py`

Their workaround for the hard switch: pick one side of the switch based on the current instant and
hold that choice across the whole look-ahead window. Wrong whenever the window spans a crossing.

The static squat cannot show this — effort sits at 0.19 against a threshold of 0.05 and never
crosses. Their **periodic** squat does cross, twice per repetition.

Both controllers were given perfect knowledge of future torque, so the only difference is the switch
handling. Prediction error is a separate issue (that is E5).

### Their protocol, their look-ahead window

```
horizon straddles a crossing   1.8% of steps
mean |p_frozen - p_smooth|     1.04e-03
max  |p_frozen - p_smooth|     6.65e-02
```

Negligible on average. **Their workaround is sound at their settings and their published results
stand.** Saying so plainly is part of the contribution.

### How often the window spans a crossing — clean analytic result

A window spans a crossing whenever it begins within one window-length of one. Two crossings per
repetition gives

```
straddle fraction = 2 x window length / repetition period
```

Confirmed across a fifteen-fold range:

```
  period  straddle  predicted
    10.0     1.8%      2.0%
     5.0     3.6%      4.0%
     2.0     9.0%     10.0%
     1.0    18.0%     20.0%
     0.6    29.9%     33.3%
```

### But faster repetition does NOT make the error worse

This killed the original hypothesis. Error is flat or falling as repetitions speed up:

```
  period   mean|dp|   max|dp|
    10.0   4.78e-04  2.92e-02
     5.0   3.75e-04  2.70e-02
     2.0   3.51e-04  2.58e-02
     1.0   3.32e-04  2.55e-02
     0.6   3.09e-04  1.70e-02
```

More crossings, same error. **Reason:** shorter repetitions move less tiredness per crossing, so each
individual mistake costs less. The two effects cancel.

### Look-ahead window length is the axis that matters

```
  horizon  h/C_F  straddle  mean|dp|  max|dp|   dV_final
     0.10  0.012     1.8%   4.78e-04  2.92e-02  +2.18e-04
     0.50  0.061     9.7%   6.33e-03  2.14e-01  +2.21e-03
     1.00  0.121    19.6%   1.26e-02  2.15e-01  +3.04e-03
     2.00  0.243    39.7%   1.54e-02  2.17e-01  +2.99e-03
```

`h/C_F` is the window length measured against how long the person takes to tire.

- At 0.10 s (theirs): peak error 2.9% of assistance. Benign.
- At 0.50 s: peak error **21.5%** of assistance, saturating there. That is 72% of the maximum
  assistance the device can give — the controller is commanding something close to arbitrary at
  every crossing.
- Sharp transition between 0.10 s and 0.50 s.

**The headline:** freezing the switch caps the planning window at roughly `0.05 x C_F`. Below the
cap it is fine; above it, unusable. The smooth version removes the cap.

Also: the frozen version never ends up *less* tired than the smooth one, at any setting. Asserted in
the self-check.

**Why this matters for the rest of the project:** E2 needs to plan further ahead than a tenth of a
second to allocate assistance across joints over a fatigue trajectory. That is above the cap. So E1
is not a tidy-up — it is the thing that makes E2 possible.

---

## 5. Literature sweep — PubMed, 2026-09-19

Full detail in `docs/gap_analysis.md`.

| Query | Hits | Read |
|---|---|---|
| smoothing a fatigue model for use inside an optimiser | **1** (1999, unrelated) | E1 clear |
| multi-joint + fatigue + allocation | **5** | E2 narrowed |
| muscle spanning two joints + fatigue + assistance | **3**, all pre-2006 | E2 wedge holds |
| fatigue + exoskeleton + control, 2023 onward | 128 | general context |

**Coverage caveat:** PubMed indexes medical and biological literature and covers engineering venues
poorly. The E1 verdict is provisional until arXiv is checked — that is where the optimisation and
simulation-methods work lives.

**Not checked at all:** preprints. The bioRxiv connector only filters by subject area and date, with
no text search, so scoop risk is unassessed.

---

## 5. Gate A: the OpenSim twin (`src/musculoskeletal/twin.py`, 2026-10-02)

Reduced 2D model (gait10dof18musc), exo at hip/knee/ankle on both legs, 6.6 kg of device mass.
One evaluation = two MocoInverse solves: an ID-equivalent solve for net joint moments, then the
muscle solve with the assistance applied.

**Solve time: 26 s per evaluation unassisted, 42 s assisted, laptop, single process**
(after the objective fixes in decisions.md; it was 67 s before). This replaces the 90 s
placeholder in every Phase D estimate.

Ideal device with 30% capacity at every joint (final formulation, tolerance 1e-4). Mean
activation over the cycle:

```
muscle        mean a, none   mean a, 30%   change
hamstrings           0.086         0.028    -68%
bifemsh              0.042         0.024    -43%
glut_max             0.065         0.025    -62%
iliopsoas            0.146         0.066    -55%
rect_fem             0.079         0.049    -38%
vasti                0.051         0.031    -40%
gastroc              0.103         0.067    -35%
soleus               0.103         0.096     -7%
tib_ant              0.060         0.029    -51%
```

Joint reserves are 7.2 Nm RMS unassisted. Soleus barely responds. Both are open flags in
observations.md.

**The first version of this table was wrong.** Subject scaling was a no-op and the muscle
activations were never really optimised, yet the solver still reported success. That version
showed 3–30% reductions. See observations.md, "Twin bugs caught by sanity checks".

**Storage: 6 KB per evaluation** (100×9 float32 activations plus metadata, compressed). The full
100,000-solve tier is about 0.6 GB. The earlier 25–100 GB estimate assumed saving whole
trajectories.

## 6. Pipeline smoke test, end to end (2026-10-02)

`configs/smoke.yaml`: 3 subjects × 2 conditions × 3 assistance levels = 18 twin evaluations.

- **D1:** 18/18 converged, joint reserve RMS median 5.2 Nm
- **D2:** held-out-subject R² 0.65 with only 2 training subjects (wiring check, not a result).
  The toy self-check gives R² 0.999 with error/disagreement correlation 0.85, so the ensemble's
  uncertainty is informative
- **D3:** SAC trains and evaluates. 3k steps is untrained (−2% vs none); the DGX runs 300k
- **D4:** closed loop against the twin works. Policy latency **2.3 ms vs 182 s** per twin
  evaluation. In the smoke run the "coupled" controller planned through the weak surrogate
  showed **retention −0.02**: the surrogate promised 0.218 → 0.165 and the twin delivered 0.223.
  That is the surrogate-exploitation failure D4 exists to catch, caught at smoke scale.

None of these are results. They show every stage runs and hands its output to the next.

**These smoke numbers came from the pre-fix twin.** The pipeline was re-run after the fixes;
see section 7.

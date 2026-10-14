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

## Independent review (2026-10-07)

### One device cap per joint, the full-cycle peak

`p_j` caps the device at `p_j * peak|tau_net_j|`, where the peak is over the WHOLE gait cycle
and the cap is the same on both legs. The half-cycle reference means each side's moments cover
half the cycle, so the full-cycle peak is the larger of the two sides. Per-side caps made the
second half of the cycle 3.6-9.4x under-assisted (observations.md). A real motor has one torque
limit, not one per half-cycle.

### Controllers see an estimate of fatigue, not the truth

Policy and Phase C controllers observe V_est: the fatigue model integrated over the surrogate's
predicted activations, which is what a device could run on board. The twin's true V scores only.
Before, D4 fed the twin's own V back in, which leaked the hidden randomised parameters into the
observation and made "robust to hidden parameters" optimistic.

### Ablations, not more baselines

`coupled` beat the baselines but differed from each in more than one way. Three ablations
(`allocate.ABLATIONS`) each change one thing: the objective (independent_minmax), the cross-joint
redistribution knowledge (local), the fatigue feedback (static). The claim is whatever survives
them.

### Keep the 2D model for now

The model's own source says not to use it for research (gastroc path) and it has no real
push-off. Chosen with Jasith: fix everything else on it first, treat ankle and gastroc results as
blocked, and rebuild on the measured-data example (exampleEMGTracking) as the next step.

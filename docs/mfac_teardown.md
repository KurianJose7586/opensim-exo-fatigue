# Teardown — Zhang et al. (2026), Muscle Fatigue-Aware Controller for a Semi-Rigid Knee Exoskeleton

IEEE T-ASE vol. 23, 2026, pp. 44–58. Open access (CC BY-NC-ND). IIT Genoa, Exo-Muscle device.
**This is the paper we extend.** Everything below is from a full read.

---

## 1. What the system actually does

```
IMUs + iT-Shoes (6-axis FT) ──► joint state q, GRF
                                      │
                                      ▼
                        τ = -(G(q) + J_f^T·f_grf + J_b^T·f_grb)        (3)
                                      │  gravity + GRF only, NO inertia
                                      ▼
                        τ̂_kf = τ_kf - τ_d          (4)   internal knee torque
                                      │
                                      ▼
                  GPR: (τ̂_kf, θ_kf) ──► E          (17)(18)  est. activation
                                      │            trained offline on EMG (VL)
                                      ▼
                  dV/dt = (1-V)·M/C_F   if M ≥ M_th   (8)   scalar fatigue index
                          -V·R/C_F      if M < M_th
                                      │
                                      ▼
                  MPC:  min J = K^T Q K + P^T R P    (26)
                        k = 1/(V_m - V)              (27)  barrier state cost
                        s.t. 0 ≤ p ≤ p_max, 5 ≤ F ≤ F_max, |ΔF| ≤ 10
                                      │
                                      ▼
                        F_ref ──► low-level force controller (1 kHz)
```

**Key quantities:** `V` ∈ [0,1] scalar fatigue index (one muscle group). `p` = fraction of knee
torque to compensate (the control input). `E` = estimated activation. CasADi + IPOPT, 3.53 ms per
solve, 100 Hz loop.

**Device:** Exo-Muscle, tendon-driven, Bowden cable, semi-rigid chain, knee extension assist only.
Moment arm `L_a(θ_kf)` is a fitted 5th-order polynomial (5). `τ_d = F_lc · L_a(θ_kf)` (6).

---

## 2. Reported results — note how modest they are

Static squat, time for V to reach 0.8:

| Condition | Time to V=0.8 |
|---|---|
| No assistance | 66.95 s |
| Constant 15% compensation | 73.60 s |
| **MFAC** | **76.15 s** |

**MFAC beats constant assistance by only 3.5%** (76.15 vs 73.60 s). It beats no assistance by 13.7%.
The authors acknowledge this: *"the time differences in reaching the maximum fatigue level are
relatively small."*

Their real claimed win is **energy**, not endurance: MFAC power rate in cycle 1 is ~2 W vs ~10 W for
constant assistance (Fig. 10a), rising to ~13 W by cycle 8. Roughly 4× lower initial power for the
periodic squat, 3× for stair stepping.

**These are our validation targets.** Reproducing 66.95 / 73.60 / 76.15 s in simulation is the
credibility gate before any extension.

**And it is the motivation:** if fatigue-aware control barely beats constant assistance in a
single-joint quasi-static task, does the margin grow when you add multi-joint allocation and
muscle-level fatigue resolution? That is a real question with a real answer either way.

---

## 3. Their explicitly stated future work (Section IV)

Direct quotes, and what each opens up.

| # | Their words | Opening |
|---|---|---|
| **FW1** | *"standard GPR, whose computational cost increases significantly with the number of training data points… future work will explore more advanced GP methods, such as inducing point techniques, variational inference approaches, and structured kernel interpolation"* | Sparse/variational GP. Well-defined, easy to execute well |
| **FW2** | *"requires a one-time EMG-based calibration before deployment… we plan to explore generalized cross-subject models trained on data from multiple individuals"* | Cross-subject transfer. In simulation we can scale models and study this with n they cannot reach |
| **FW3** | *"we aim to extend the proposed approach to multi-degree-of-freedom (multi-DoF) exoskeletons and evaluate its performance with multiple subjects"* | **The big one.** See §5 |
| **FW4** | *"the framework has the potential to support online user tuning of the optimizer's response via the suppression factor w_r… although it has not yet been experimentally validated"* | An admitted untested capability |

---

## 4. Weaknesses they did NOT list — found by reading the methods

These are more valuable than the stated future work, because nobody else is queuing up to fix them.

### W1 — The frozen-branch hack (**the best single opening in the paper**)

Their own words, §II-D:

> *"To avoid discontinuities, the fatigue stage for each step in the prediction horizon must be
> selected before optimization and remain fixed during the process. Therefore, in this study, a
> single stage is used to construct the optimization problem for each loop. The selection of the
> fatigue stage depends on the most recent estimated E_(c)."*

The fatigue model (8) switches hard at `M_th` between decay (19) and recovery (20). That switch is
non-differentiable, so IPOPT cannot handle it inside the horizon. **Their fix is to pick one branch
from the current activation and freeze it across the entire prediction horizon.**

**Why this is exploitable:** in any cyclic task the horizon routinely straddles a transition. Their
own periodic squat and stair-stepping figures (Fig. 9, row 4) show `V` visibly rising and falling
*within* cycles — which means the branch flips *inside* the horizon they froze. The MPC is
provably optimizing the wrong dynamics for part of every cycle. In walking, with stance loading and
swing unloading every ~1 s, this gets worse.

**The fix is a real contribution:** a smooth (tanh-blended) formulation of (8) that is
differentiable across the threshold, letting the optimizer handle transitions inside the horizon.
Self-contained, laptop-sized, and directly measurable — implement both, compare.

### W2 — Quasi-static dynamics

Equation (3) is gravity + GRF only. They state the inertial terms *"are ignored"* because
*"the value of velocity and acceleration of these parts are small when the foot is in contact with
the ground."* True for squats and slow stair steps. **False for walking.** Any gait extension needs
full inverse dynamics.

### W3 — Taylor-extrapolated torque prediction, admitted as fragile

Future knee torque over the horizon comes from a second-order Taylor expansion (21) of logged
history (22)(23). They flag it themselves:

> *"the use of second-order derivatives in recursive computation may introduce instability into the
> optimal controller, particularly in the presence of rapid motions or noise from wearable
> sensors."*

They accept it only because the study is quasi-static. **For periodic gait there is a much better
predictor: gait phase.** Walking is cyclic, so future joint torque is far better predicted from
phase-indexed averages than from extrapolating derivatives. Clean, obvious improvement.

### W4 — Scalar fatigue, one muscle group, no antagonists

`V` is a single scalar for the quadriceps. They use Vastus Lateralis EMG as a proxy for VI, VL, VM
and RF together, justified by *"a minor difference in their activation index, yet… a similar
changing trend."* Hamstrings are absent entirely.

**Consequence:** no muscle-level resolution, therefore no possibility of representing — let alone
exploiting — load redistribution between synergists or antagonist co-contraction.

### W5 — Unpersonalized recovery rate

`C_F` is fitted per subject from endurance tests (10). But `R` is set to *"a conservative value of
R = 0.5 reported in [17]"* — not personalized, not fitted, not justified for this population.
**Recovery dominates cyclic tasks** (every swing phase is recovery), so this is a load-bearing
unvalidated parameter. Sensitivity analysis is cheap and nobody has done it.

### W6 — Linearity assumptions frozen over the horizon

- `R_e(c) = τ̂_kf(c)/E_(c)` (25) — a "virtual moment arm" mapping torque to activation, **linear**,
  recomputed each loop but held constant across the horizon
- `L_a(θ_kf(c))` (30) — lever arm *"assumed to remain constant throughout the optimization process…
  given the slow motion speed"*

Both break under gait-scale kinematic variation.

### W7 — Thin validation

n=3 subjects, all male, and **only S1's trained model was used** for the device experiments.
No cross-subject test of the deployed controller. GPR trained *without* the device worn, then
deployed *with* it, with transferability assumed and untested.

---

## 5. Why multi-DoF (FW3) is deeper than they make it sound

They frame it as "extend to more joints." It is not additive, because of **biarticular muscles**:

| Muscle | Crosses |
|---|---|
| Rectus femoris | hip **and** knee |
| Hamstrings (biceps femoris long head, semitend., semimem.) | hip **and** knee |
| Gastrocnemius | knee **and** ankle |

**Assistance allocation across joints is therefore not separable.** Assisting the hip changes knee
muscle loading through rectus femoris and hamstrings; assisting the ankle changes knee loading
through gastrocnemius. A per-joint scalar fatigue index cannot represent this coupling *at all* —
there is no variable in their formulation that could.

This is the deepest technically defensible content available, it is their own stated future work, and
it requires exactly the thing we have (a musculoskeletal model) and none of the things we lack
(hardware, subjects, ethics approval).

---

## 6. Convenient alignment

- They use **CasADi + IPOPT**. OpenSim Moco's fast backend is **also CasADi**. Same solver stack,
  and CasADi has MATLAB and Python interfaces — so the MPC layer ports to whichever the mentor wants.
- Paper is **open access CC BY-NC-ND** — quotable and freely buildable-on.
- Their GPR training is scikit-learn, stated in §II-C.
- Their whole pipeline runs on a laptop (i9-12900H, 3.53 ms/solve). Nothing here needs a cluster.

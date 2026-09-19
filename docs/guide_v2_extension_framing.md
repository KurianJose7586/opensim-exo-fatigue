# AI-Driven Human–Exoskeleton Digital Twin
### Personalized and Fatigue-Aware Lower-Limb Assistance Using MATLAB–OpenSim Moco

**Anchor paper:** Zhang, Jiang, Ajoudani, Tsagarakis (2026), *Muscle Fatigue-Aware Controller for a
Semi-Rigid Knee Exoskeleton*, IEEE T-ASE 23:44–58. Full teardown in
[`docs/mfac_teardown.md`](mfac_teardown.md).

**Scope:** simulation only · **Compute:** laptop-sufficient · **Status:** E1 complete, Gate R passed

---

## 1. What this project is

> Zhang et al. built a fatigue-aware exoskeleton controller for **one joint**, with a **scalar**
> fatigue index, under **quasi-static** conditions, validated on **three subjects** doing squats and
> stair steps. This project rebuilds their controller in a musculoskeletal simulation, then extends
> it along the axes they identified as future work and the ones they quietly assumed away.

We are not claiming to invent fatigue-aware assistance. We are taking a published controller and
answering the questions its authors left open — which is a normal, respectable, and highly tractable
way to do research. The technical depth comes from the extensions, not from a novelty claim.

**Central technical question:**

> Zhang et al. report that fatigue-aware control beats constant assistance by only **3.5%** on
> endurance (76.15 s vs 73.60 s). Does that margin grow when assistance is allocated across
> **multiple joints** using **muscle-level** fatigue states — and specifically, does biarticular
> coupling make the allocation problem non-trivial?

---

## 2. Validation strategy (the thing that makes simulation-only work credible)

Without hardware you cannot validate against your own experiments. So validate against **theirs.**

Zhang et al. publish exact numbers for the static squat — time for the fatigue index to reach 0.8:

| Condition | Their result | Our target |
|---|---|---|
| No assistance | 66.95 s | reproduce |
| Constant 15% compensation | 73.60 s | reproduce |
| MFAC | 76.15 s | reproduce |

Plus power-rate ratios: MFAC ≈ 4× lower initial power than constant assistance on periodic squat,
≈ 3× on stair stepping (their Fig. 10).

**Gate R:** reimplement their controller — same fatigue model (8), same MPC (26), same barrier cost
(27), same constraints — driven by a simulated squat, and land within a defensible margin of those
times. Until this passes, every extension result is unfalsifiable.

This gate is also your paper's Figure 1 and your methods-validation section. It is not overhead.

---

## 3. The extension set

Each extension is independently publishable-as-a-section and independently droppable. Ordered by
value-per-effort, not by dependency.

| ID | Extension | Origin | Depth | Effort |
|---|---|---|---|---|
| **E1** | Smooth, differentiable fatigue dynamics across the decay/recovery threshold | W1 (their hack) | High | **DONE** |
| **E2** | Continuous optimal multi-DoF allocation with biarticular coupling | FW3 | **Highest** | High |
| **E3** | Per-muscle fatigue states replacing the scalar index | W4 | High | **Low** |
| **E4** | Full dynamics + walking instead of quasi-static squats | W2 | Medium | Medium |
| **E5** | Gait-phase torque prediction replacing Taylor extrapolation | W3 | Medium | **Low** |
| **E6** | Recovery-rate identification and sensitivity analysis | W5 | Medium | **Low** |
| **E7** | Cross-subject generalization of the activation model | FW2 | Medium | Medium |
| **E8** | Sparse/variational GP replacing exact GPR | FW1 | Low | **Low** |
| ~~E9~~ | ~~Synergy-based muscle grouping~~ — **scooped**, Lambeth et al. 2025 did it. Use the technique, cite them, drop the claim | — | — | — |

**Recommended core:** E1 + E3 + E2, in that order. That is a coherent paper — *"per-muscle,
multi-joint, differentiable fatigue-aware assistance"* — with E5 and E6 as supporting sections.

> **PubMed sweep 2026-09-19 (see [`gap_analysis.md`](gap_analysis.md)):** E1 is clear — one
> irrelevant hit in the whole index. E2 is narrowed: Lambeth et al. 2025 and Bao et al. 2020 already
> do fatigue-driven multi-joint allocation, but for *hybrid FES* exoskeletons with FES-induced
> fatigue. **Biarticular coupling remains open** (3 hits, all pre-2006) and is now E2's stated wedge.
> E9 is scooped outright. **E1 is the strongest surviving novelty claim — lead with it.**

> **Read [`peternel2019_teardown.md`](peternel2019_teardown.md) before starting.** It changes E2 and
> E3 substantially: the per-muscle fatigue model already exists (published 2019, same group), and
> load redistribution between muscle groups has already been demonstrated to work. Both extensions
> get safer and better-founded; neither becomes unnecessary.

---

### E1 — Smooth fatigue dynamics *(start here)*

**What they did:** the fatigue ODE (8) switches hard at `M_th` between decay and recovery. That
discontinuity breaks gradient-based optimization, so they **freeze the branch** for the entire
prediction horizon based on the current activation.

**Why it's wrong:** in cyclic tasks the branch flips *inside* the horizon. Their own Fig. 9 shows
`V` rising and falling within cycles. The MPC optimizes the wrong dynamics for part of every cycle.
Under walking — stance loads, swing unloads, every second — it gets worse.

**What to build:** a tanh-blended formulation of (8), differentiable through the threshold, with a
smoothing parameter. Then prove it:

1. Integrate original and smoothed ODEs under identical activation traces; show convergence as the
   smoothing parameter tightens
2. Implement both MPCs; measure the cost of the frozen-branch approximation across duty cycles
3. Show where the error is worst — high transition frequency is the predicted regime

**Why start here:** pure ODE and NLP work. No OpenSim, no musculoskeletal model, no C++. Runs in
seconds. **And the discontinuity is not one paper's hack — it runs through the whole model lineage:**
Ma 2009 → Peternel 2018 → Peternel 2019 → Zhang 2026. Repairing it fixes a structural defect in a
model family spanning at least four papers. **Highest value per hour in the project.**

---

### E2 — Continuous optimal multi-DoF allocation *(the core contribution)*

They frame this as "extend to more joints." It is not additive, because of **biarticular muscles:**

| Muscle | Crosses |
|---|---|
| Rectus femoris | hip **and** knee |
| Hamstrings | hip **and** knee |
| Gastrocnemius | knee **and** ankle |

Assisting the hip changes knee muscle loading. Assisting the ankle changes knee loading. **The
allocation problem is coupled, and a per-joint scalar fatigue index has no variable capable of
representing that coupling.**

**Precedent — this is good news.** Peternel et al. 2019 (FMP2) already demonstrated that
redistributing load between muscle groups extends endurance, validated on 6 subjects. The hypothesis
is no longer speculative. But their mechanism was a **discrete threshold-triggered switch** that
changed *task geometry* — rotating the object the human works on. The gap:

| | Peternel 2019 FMP2 | E2 |
|---|---|---|
| Mechanism | change task geometry | allocate assistance torque |
| Control | discrete switch at threshold | **continuous optimal** allocation |
| Coupling | task force direction | **biarticular muscles** |

**Objective function — use theirs, don't invent one.** Peternel 2019 eq. (9)–(10) give a max-min
endurance formulation:

```
T_i = -(C_i / f_mi) · ln(1 - V_th)          per-muscle endurance time
argmax ( min_i T_i )                        maximize the weakest muscle's endurance
```

Published, citable, and directly comparable to their results.

**The experiment:** allocate a fixed assistance budget across hip/knee/ankle. Compare independent
per-joint MFAC controllers (the naive extension Zhang et al. imply) against coupled allocation using
per-muscle fatigue states. **Hypothesis:** they differ, driven by biarticular coupling. If false, you
have shown the naive extension suffices — also useful, also reportable.

Requires E3.

---

### E3 — Per-muscle fatigue states *(now low-risk)*

**This model already exists.** Peternel et al. 2019 eq. (7) is the per-muscle form:

```
dV_i/dt =  (1 - V_i)·f_mi/C_i     if f_mi ≥ f_th
          -V_i·R/C_i              if f_mi <  f_th
```

with `V_i` per muscle and `C_i` a per-muscle capacity parameter. **Zhang et al. 2026 collapsed this
to a single scalar for one muscle group — a regression in fidelity by the same research group.**

E3 is therefore not a novel modelling claim. It is *restoring the per-muscle formulation the group
already published, into the exoskeleton MPC context.* Safer to defend, faster to build.

**Grouping:** use functional groups rather than one state per muscle — see E9 for choosing them
defensibly.

**Keep the Peternel/Ma model, don't swap to Xia & Frey-Law.** Staying in this lineage keeps results
directly comparable to both anchor papers. Note Xia & Frey-Law as an alternative; don't spend the
project on it.

---

### E4 — Full dynamics and walking

Their model (3) is gravity + GRF with inertial terms *"ignored."* Fine for squats, false for gait.
Move to full OpenSim inverse dynamics and from squats to walking. This is what turns the project from
"knee exo for squatting" into "lower-limb assistance during gait," which is what the title claims.

**Motivate this carefully.** Peternel 2019 justifies static optimization by citing Anderson & Pandy:
*"Static and dynamic optimization solutions for gait are practically equivalent."* That citation is
about gait, so it undercuts any claim that full dynamics is needed for muscle-force *estimation*.
**Motivate E4 by the MPC horizon problem instead** — predicting future joint torque across a horizon
during dynamic gait, which is where the quasi-static assumption actually breaks (see E5). Do not
overclaim.

---

### E9 — Scalable muscle grouping

Peternel 2019's grouping algorithm *"goes through all possible divisions of muscle groups"* and forces
exactly two. Fine for 6 arm muscles; **combinatorially explosive for 18+ lower-limb muscles across
three joints**, and the two-group restriction is arbitrary.

Replace with principled grouping: muscle synergy extraction (NMF on activation patterns) or spectral
clustering on a coupling matrix, yielding a data-driven number of groups. Concrete, technically
substantive, and it directly enables E3.

---

### E5 — Gait-phase torque prediction *(cheap, obvious)*

They predict future joint torque over the horizon by second-order Taylor extrapolation (21), and
admit it *"may introduce instability… in the presence of rapid motions or noise."*

Walking is periodic. **Gait phase predicts future torque far better than derivative extrapolation.**
Build a phase-indexed predictor, compare horizon prediction error against their Taylor scheme. Small
effort, clean result, directly addresses an admitted weakness.

---

### E6 — Recovery rate *(cheap, rigorous)*

`C_F` is fitted per subject. `R` is *"a conservative value of R = 0.5 reported in [17]"* — not
fitted, not justified. **Recovery dominates cyclic tasks** because every swing phase is recovery.

Run a sensitivity analysis over `R`. If the controller's behaviour is sensitive to an unvalidated
constant, that is worth reporting, and it is a half-day of compute.

---

### E7 / E8 — Their stated future work

**E7 (cross-subject):** they want to drop per-subject EMG calibration. In simulation you can scale
models across anthropometry and study transfer at an `n` they cannot reach with three subjects.

**E8 (sparse GP):** they name inducing points, variational inference, structured kernel
interpolation. Well-defined, standard tooling, low risk. A safe section if you need one.

---

## 4. Stages and gates

| Stage | Work | Gate | Laptop? |
|---|---|---|---|
| **S0** | Finish screening the literature; complete [`gap_analysis.md`](gap_analysis.md) | Can state in one sentence what each extension adds beyond Zhang et al. | ✅ |
| **S1** | **E1 smoothing validation** — pure ODE, no OpenSim | Smoothed ODE converges to original; error quantified vs duty cycle | ✅ |
| **S2** | Environment: OpenSim + Moco + CasADi; run bundled examples | `exampleMocoTrack` converges | ✅ |
| **S3** | **Gate R** — reimplement MFAC, reproduce 66.95 / 73.60 / 76.15 s | Within defensible margin of published values | ✅ |
| **S4** | E3 muscle-level fatigue on the scaled model | Fatigue states track published activation patterns | ✅ |
| **S5** | E4 full dynamics + walking task | Walking simulation with fatigue accumulating sensibly | ✅ |
| **S6** | **E2 multi-DoF allocation** — the core experiment | Coupled vs independent allocation differ, or provably don't | ⚠️ |
| **S7** | E5, E6 supporting sections | — | ✅ |
| **S8** | E7 cross-subject, E8 sparse GP if time | — | ⚠️ |
| **S9** | Ablations, writing | — | ✅ |

**S1 and S2 are independent — run them in parallel.** S1 needs nothing installed.

---

## 5. Compute

Their entire system runs on a laptop: i9-12900H, **3.53 ms per MPC solve**, 100 Hz control loop.
Nothing in the anchor paper needs a cluster, and most extensions don't either.

Cluster only helps for: E7 multi-subject sweeps, E2 allocation parameter studies, any Monte Carlo
over fatigue parameters. **You are not blocked on cluster access for the core contribution.**

Write batch stages as job arrays anyway — parameterized by index, config from file, uniquely named
outputs. Retrofitting costs more than doing it now.

---

## 6. Toolchain note

Convenient alignment: **Zhang et al. use CasADi + IPOPT. OpenSim Moco's fast backend is also
CasADi.** Same solver stack throughout, and CasADi has both MATLAB and Python interfaces — so the MPC
layer ports to whichever your mentor prefers without touching the formulation.

Their GPR is scikit-learn (stated in §II-C), so E8 stays in Python regardless.

**You no longer need a C++ plugin.** The earlier plan required subclassing OpenSim components to
embed fatigue states. Anchoring to their MPC formulation means fatigue lives in *your* CasADi
optimization problem, not inside OpenSim's. That removes the single riskiest toolchain dependency
from the project.

---

## 7. Repository structure

```
capstone_project/
├── PROJECT_GUIDE.md
├── docs/
│   ├── mfac_teardown.md       # full read of the anchor paper
│   ├── peternel2019_teardown.md
│   ├── reference_implementation.md
│   ├── gap_analysis.md        # literature screening, ongoing
│   └── preregistration.md     # PLANNED: endpoints fixed before results
├── data/
│   ├── raw/ processed/
├── models/
│   ├── base/ scaled/ exo/
├── external/PHRC/             # vendored reference code, do not edit (see NOTICE)
├── src/
│   ├── fatigue/               # E1: smooth dynamics + validation  [model.py done]
│   ├── mpc/                   # MFAC reimplementation (CasADi)
│   ├── musculoskeletal/       # OpenSim/Moco pipeline
│   ├── allocation/            # E2: multi-DoF
│   ├── activation/            # GPR / sparse GP
│   └── jobs/
├── results/                   # timestamped, config-stamped, git-hash-stamped
└── figures/
```

---

## 8. Immediate next actions

1. **Start E1.** Implement fatigue model (8) and its smoothed variant; compare under identical
   activation traces. Pure Python, no installs, no OpenSim. This is a self-contained result and it
   de-risks the whole project.
2. **Install OpenSim + Moco** in parallel; get `exampleMocoTrack` converging.
3. **Finish literature screening** in `gap_analysis.md` — particularly the FES review's references,
   to see whether smooth fatigue-in-optimal-control already exists there. It may; E1's framing then
   becomes *"first applied to exoskeleton assistance control"* rather than *"first."*
4. Email the authors. The paper is open access, the work is EU-funded (SOPHIA 871237, HARIA
   101070292), and they may share the Exo-Muscle URDF or their fitted `C_F` values. Costs one email.

---

## 9. Reading list

**Anchor and its dependencies**
- Zhang, Jiang, Ajoudani, Tsagarakis (2026). IEEE T-ASE 23:44–58. *Read in full — done.*
- **Peternel, Fang, Tsagarakis, Ajoudani (2019)**, Robot. Comput.-Integr. Manuf. 58:69–79 — Zhang's
  ref **[27]**. *Read — done.* Per-muscle fatigue model, max-min endurance objective, muscle-group
  redistribution. Teardown: [`peternel2019_teardown.md`](peternel2019_teardown.md).
- **Reference implementation:** `gitlab.com/lukapeternel/PHRC` — the authors' own Python fatigue
  model, with real parameter values. **E1 validates against this, not against the paper's prose.**
  Notes and a confirmed bug: [`reference_implementation.md`](reference_implementation.md).
- **Ma, Chablat, Bennis, Zhang, Guillaume (2010)**, *A new muscle fatigue and recovery model and its
  ergonomics application in human simulation*, Virtual and Physical Prototyping 5(3):123–137 —
  Peternel 2019's ref [42], cited as the source of alternative recovery rates. **Get this for E6.**
- Peternel, Tsagarakis, Caldwell, Ajoudani (2018), Autonomous Robots 42(5):1011–1021 — Zhang's ref
  **[17]**. Nice-to-have for the calibration protocol; **no longer on the critical path**, since the
  model structure and `R = 0.5` are both confirmed in the reference code.
- Ma, Chablat, Bennis, Zhang (2009), Int. J. Ind. Ergonom. 39(1):211–220 — their ref [24], the
  dynamic fatigue model Peternel simplified.
- Zhang, Ajoudani, Tsagarakis (2021), IEEE RA-L 6(4):8514–8521 — their ref [31], the Exo-Muscle
  device paper. Source for actuator limits and device mass.

**Comparators named in the paper**
- Bergmann et al. (2025), IEEE Trans. Hum.-Mach. Syst. 55(1):10–22 — three-compartment fatigue in a
  human-in-the-loop lower-limb exo controller. **Closest alternative approach; read it.**
- Del-Ama et al. (2014), J. NeuroEng. Rehabil. 11:27 — hybrid FES-robot, torque-time integral.
- Sheng et al. (2022), IEEE/ASME Trans. Mechatron. 27(4):1854–1862 — ultrasound-based fatigue.

**Tooling**
- Dembia et al. (2020), *OpenSim Moco*, PLoS Comput Biol.
- Andersson, Gillis, Horn, Rawlings, Diehl (2019), *CasADi*, Math. Program. Comput. 11(1):1–36.

**Supporting**
- Toffoli et al. (2026), Gait & Posture 130:110613 — time-to-exhaustion nearly tripled with a passive
  exo (896 s vs 307 s); validates the endpoint and shows assistance shifts motor strategy.
- Co, Begon, Bailly, Moissenet — FES optimal control scoping review. **Mine its references** for
  fatigue-inside-optimal-control precedent.

# AI-Driven Human–Exoskeleton Digital Twin
### Personalized and Fatigue-Aware Lower-Limb Assistance Using MATLAB–OpenSim Moco

**Status:** foundation built and validated (see §4). Realigned to the title 2026-09-19.
**Scope:** simulation only · **Compute:** laptop for Phases A–C, **HPC for Phase D**

> Previous framing archived at [`docs/guide_v2_extension_framing.md`](docs/guide_v2_extension_framing.md).
> It treated the project as an extension of Zhang et al. (2026). That produced good validated work
> but drifted off three title terms — OpenSim Moco, AI, and multi-joint — because Zhang et al.
> explicitly *avoid* musculoskeletal modelling and we inherited that avoidance. This document puts
> the title back in charge. The anchor papers become component sources and validation targets, not
> the project's frame.

---

## 1. The system the title describes

```
  Camargo dataset                          subject marker + force + EMG data
          |
          v
  OPENSIM MOCO                             scaled lower-limb musculoskeletal model
  scale -> IK -> ID -> MocoInverse         + exo actuators at hip / knee / ankle
          |                                + device mass
          v
  per-muscle forces  f_i(t | assistance)   the twin's output
          |
          v
  CASADI FATIGUE + ALLOCATION LAYER        per-muscle fatigue states (Peternel 2019 eq. 7)
  smoothed dynamics (built, validated)     allocate torque across 3 joints
          |                                biarticular coupling is the mechanism
          v
  LEARNED DYNAMICS (ensemble)              surrogate of musculoskeletal + fatigue
  trained on ~10^4-10^5 Moco solves        dynamics, conditioned on the subject
          |
          v
  MODEL-BASED RL POLICY                    long-horizon fatigue management --
  millions of rollouts in the surrogate    the problem Moco cannot solve at all
          |
          v
  MATLAB orchestration                     scripting layer over the Moco side
```

**Two separate reasons the AI is load-bearing, not decorative.**

1. Fatigue-aware allocation must evaluate many candidate assistance profiles. Each changes the muscle
   forces, each needs a Moco solve taking minutes, and the loop must close in milliseconds.
2. **The long-horizon problem is one Moco cannot solve at all.** Fatigue evolves over tens of
   minutes; direct collocation over ten thousand gait cycles with muscle dynamics is infeasible, not
   slow. There is no expert trajectory to imitate. That is what forces reinforcement learning rather
   than supervised fitting.

---

## 2. How each title term is delivered

| Term | Delivered by | State |
|---|---|---|
| **OpenSim Moco** | Phase A — the musculoskeletal twin is the core, not an accessory | Not started |
| **Digital Twin** | Phase A — model scaled to a real subject, validated against their measured gait | Not started |
| **Personalized** | Phase A + B — subject scaling, and per-subject fatigue constants (method validated) | Method done, n=1 |
| **Lower-Limb** | Phase C — hip, knee **and** ankle | Not started |
| **Human–Exoskeleton** | Phase A — actuators plus device mass on the model | Partially (knee, abstract) |
| **Fatigue-Aware** | Phase B — per-muscle fatigue, differentiable | **Done and validated** |
| **AI-Driven** | Phase D — learned dynamics ensemble + model-based RL policy, on HPC | Not started |
| **MATLAB** | Phase E — scripting layer; CasADi and Moco both have MATLAB interfaces | Not started |

Re-check this table at every milestone. It is the definition of done.

---

## 3. What the anchor papers are *for*

They are no longer the frame. They are three specific things:

| Paper | Role now |
|---|---|
| **Zhang et al. 2026** | Validation target (66.95 / 73.60 / 76.15 s) and the single-joint baseline to beat. Their MPC formulation (eq. 24–30) is the controller structure we generalise |
| **Peternel et al. 2019** | Source of the per-muscle fatigue equation, the max-min endurance objective, and the OpenSim static-optimisation pipeline pattern |
| **Lambeth 2025, Bao 2020** | Closest prior art for fatigue-driven allocation — cite and distinguish, do not re-derive |

Plain-language summaries of all of these: [`notes/papers.md`](notes/papers.md).

---

## 4. What is already built — and where it fits

Nothing done so far is wasted. It all becomes the fatigue layer and the validation anchor.

| Built | New role |
|---|---|
| `src/fatigue/model.py` — smoothed fatigue dynamics, exact at k=0 | **Phase B core.** The enabler: without it the fatigue layer cannot be optimised by gradients, and the allocation horizon is capped |
| `src/fatigue/calibrate.py` — per-subject constant fitted, predicts held-out trials to 0.6% | **Phase B personalisation**, method already validated against real data |
| `src/mpc/mfac.py` — their controller in CasADi, reproduces their trial to 1.7% | **The single-joint baseline** Phase C must beat, and proof our fatigue layer is correct |
| `src/mpc/periodic.py` — frozen branch caps horizon at ~0.05·C_F | **The justification for Phase C.** Multi-joint allocation needs a long horizon; the published method cannot provide one |

That last row matters: the earlier work produced the argument for why the title's project is
necessary. Keep it in the write-up as motivation, not as a separate contribution.

---

## 5. Phases

### Phase A — The musculoskeletal digital twin · OpenSim Moco

**Restores: OpenSim Moco, Digital Twin, Personalized, Human–Exoskeleton.**

- **A1** Install OpenSim 4.5+ (Moco bundled). Get the **Python API** working now and the **MATLAB
  API** (`configureOpenSim.m`) working for Phase E. Run the bundled Moco examples unmodified.
- **A2** Camargo dataset, one subject first. Scale a lower-limb model. Start with the reduced 2D
  model — solve time is the governing constraint and you must measure it before committing.
- **A3** Inverse kinematics and inverse dynamics. Check marker error and compare joint moments to
  published normative ranges.
- **A4** `MocoInverse` or static optimisation → **per-muscle forces**. This is the twin's output and
  what the fatigue layer consumes.
- **A5** Add `CoordinateActuator`s at hip, knee, ankle. **Add the device mass** — omitting it is the
  standard way to report a benefit that does not exist. Use Zhang et al. 2021 for real limits.

**Gate A:** muscle forces for one subject's gait cycle, with and without assistance, and a recorded
solve time. **Write that solve time down — every Phase D decision depends on it.**

### Phase B — Fatigue in the twin

**Restores: Fatigue-Aware. Largely built.**

- **B1** Per-muscle fatigue states driven by Phase A muscle forces — Peternel 2019 eq. 7. Group by
  function, not one state per muscle. *Note: their released code has a confirmed `range(2)` bug that
  silently drops muscles past the second; see [`docs/reference_implementation.md`](docs/reference_implementation.md).*
- **B2** Smoothed dynamics — **done**, `src/fatigue/model.py`.
- **B3** Per-subject constants — method **done**, `src/fatigue/calibrate.py`. Extend to more subjects.
- **B4** **Validation gate:** reduce the twin to Zhang et al.'s single-joint static squat and
  reproduce 66.95 / 73.60 / 76.15 s. Already achieved in the abstract model (1.7%); repeat it
  *through the OpenSim pipeline* to prove the twin is wired correctly.

### Phase C — Fatigue-aware multi-joint assistance

**Restores: Lower-Limb Assistance. The main scientific contribution.**

- **C1** Allocate an assistance budget across hip, knee and ankle to minimise fatigue, using the
  max-min endurance objective from Peternel 2019 eq. 9–10 — published and citable, do not invent one.
- **C2** **Biarticular coupling is the mechanism and the novelty.** Rectus femoris and hamstrings
  cross hip and knee; gastrocnemius crosses knee and ankle. Assisting one joint changes another
  joint's muscle loading. A per-joint scalar fatigue index cannot represent this; per-muscle states
  can. Literature check: `biarticular AND fatigue AND assistance` returns 3 papers, all pre-2006.
- **C3** Compare against: no assistance · Zhang-style single-joint · independent per-joint
  controllers · fatigue-blind multi-joint · coupled allocation (ours).

**This needs a long planning horizon, which is exactly what the frozen-branch method cannot give —
that is what `src/mpc/periodic.py` established.**

### Phase D — Learned dynamics and a long-horizon policy

**Restores: AI-Driven. This is the compute-heavy half of the project and it runs on the HPC.**

**Why this cannot be a small supervised model.** Imitating a Moco solution is curve-fitting — inputs
in, optimiser's answer out. The genuinely hard problem is the one **Moco cannot solve at all**:
fatigue evolves over tens of minutes, and direct collocation over ten thousand gait cycles with
muscle dynamics is infeasible, not merely slow. There is no expert to imitate for the long-horizon
policy. That is what forces reinforcement learning, and RL on musculoskeletal dynamics is
notoriously sample-hungry — the reason the OpenSim RL challenges (*Learning to Run*, *AI for
Prosthetics*, *Learn to Move*) were as hard as they were.

Three stages, each HPC-scale, each answering a question that stands on its own.

---

#### D1 — Population dataset generation *(HPC, CPU, embarrassingly parallel)*

Sample virtual subjects — anthropometry, muscle parameters, fatigue constants — crossed with walking
speeds, slopes, loads and assistance profiles. Every point is a Moco solve.

| Tier | Subjects x conditions x assistance | Solves | CPU-hours at 90 s |
|---|---|---|---|
| **1** shakedown | 50 x 5 x 10 | 2,500 | ~60 |
| **2** standard | 200 x 8 x 15 | 24,000 | ~600 |
| **3** full | 500 x 10 x 20 | 100,000 | ~2,500 |

**Pick the tier once you know the queue limits.** Gate A's measured solve time replaces the 90 s
placeholder — at 30 min/solve even Tier 1 is out of reach and the model must be reduced first.

- **Warm-start from the nearest solved neighbour.** Typically 3-5x, the highest-value optimisation
  available here.
- Latin hypercube, not a grid. Grids waste samples in high dimensions.
- Checkpoint and resume. Cluster jobs get killed; this will happen to you.
- Log failures. Non-convergence maps where the solver breaks down, which is data.

*Question it answers:* how does optimal assistance vary across a population and across fatigue
states? The structure of that map is a result in its own right, before any learning.

---

#### D2 — Learned differentiable dynamics *(HPC, GPU if available)*

Train a surrogate of the coupled musculoskeletal + fatigue dynamics, conditioned on subject
parameters:

```
(subject params, state, fatigue state, assistance)  ->  next state, per-muscle forces
```

A sequence model or neural ODE over D1's trajectories — not a curve fit, and at Tier 2-3 a real
GPU training job.

**Train an ensemble (5-7 members), not a single network.** D3 needs the ensemble's disagreement to
detect where the surrogate is untrustworthy. This is not optional; see the risk below.

**Phase B's smoothed fatigue dynamics are what make this differentiable end-to-end.** The frozen
branch would block gradients through the fatigue states. That is why E1 was foundational rather than
a side quest, and it is worth saying so in the write-up.

*Question it answers:* can coupled musculoskeletal and fatigue dynamics be learned accurately enough
to substitute for simulation? A methods contribution independent of what the policy does with it.

---

#### D3 — Model-based RL for the long-horizon policy *(HPC)*

The surrogate is fast enough for millions of rollouts, which OpenSim never would be.

```
observation  gait phase, per-muscle fatigue state, subject parameters
action       assistance torque at hip, knee, ankle
reward       long-horizon endurance (Peternel 2019 eq. 10 max-min) minus energy cost
```

- Off-policy algorithm (SAC or similar) with short rollouts branched from real D1 states rather than
  long imagined ones — the MBPO pattern. Long rollouts in a learned model compound error.
- Penalise ensemble disagreement in the reward so the policy is pushed away from regions where the
  surrogate is guessing.

**THE risk here is model exploitation:** the policy finds a corner where the surrogate is wrong and
scores beautifully against a fiction. This is the standard failure mode of model-based RL and it
will look like a great result until you check it. Short branched rollouts, ensemble penalties and
D4's ground-truth validation are the mitigations — treat all three as mandatory.

*Question it answers:* does a learned policy beat the optimiser over horizons the optimiser cannot
reach, in real time, on subjects it never saw?

---

#### D4 — Validation *(non-negotiable)*

- **Against Moco where Moco can solve.** Short horizons give ground truth. If the policy disagrees
  with the optimiser there, nothing it does at long horizons is believable.
- **Held out by subject, never by random split.** Random splitting leaks subject identity and will
  flatter the result.
- **Closed-loop benefit retention.** Put the policy in the real Phase C loop and check the fatigue
  benefit survives. Low prediction error that loses the benefit is a meaningless number.
- **Surrogate disagreement during evaluation.** Report how often the policy operated in
  high-uncertainty regions. Reviewers will ask; better to have measured it.
- **Inference latency against Moco solve time.** That ratio is the headline.

---

### Phase E — MATLAB

**Restores: MATLAB.**

Moco has a MATLAB API; CasADi has a MATLAB interface. The Moco orchestration and the fatigue layer
both port. **Keep the learning in Python** — that split is standard and defensible, and the handoff
is files on disk, which both read natively.

Your mentor owns this. **Give them a date.** They are on the critical path from Phase A if you want
the MATLAB API set up alongside the Python one.

---

## 6. Compute

| Work | Laptop | HPC |
|---|---|---|
| Phase A, single subject, 2D model | ✅ | — |
| Phase B (all of it) | ✅ | — |
| Phase C development | ✅ | — |
| **D1 population dataset** | ❌ | ✅ CPU, job array, 60–2500 core-hours by tier |
| **D2 surrogate ensemble** | ❌ | ✅ GPU preferred; CPU-feasible at Tier 1 with smaller nets |
| **D3 model-based RL** | ❌ | ✅ millions of rollouts, fast only because it runs in the surrogate |
| Multi-subject 3D, uncertainty sweeps | ❌ | ✅ |

**The HPC is Kubernetes, not Slurm** — standard allocation is 8 CPU, 16 GiB, 1 GPU, NGC PyTorch
image. Batch primitive is an Indexed Job, not `sbatch --array`. At 8 cores D1 Tier 1 is ~8 hours,
Tier 2 ~3 days, Tier 3 does not fit on one pod.

Analysis, blockers and a draft request: [`docs/hpc_request.md`](docs/hpc_request.md).

**Two blockers to resolve before requesting anything:** the provided image has PyTorch but **not
OpenSim**, and the home volume is a node-local `hostPath` with unknown quota against an expected
25–100 GB of output.

**Phase A's recorded solve time determines Phase D's feasibility.** At 30 min/solve the dataset is
months; at 90 s it is a weekend. Develop on the reduced 2D model, reproduce the headline result on
3D Rajagopal, and say so plainly in the methods.

Write every batch stage as a job array from the start — parameterised by index, config from file,
uniquely named output, checkpoint and resume. Retrofitting costs more.

---

## 7. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| OpenSim install / API friction | High | Gate A1 early. It is the first thing that can stall you |
| Moco solve time makes Phase D infeasible | High | Measure at Gate A. Reduce model, reduce samples, warm-start |
| Marker set mismatch in the dataset | Medium | Attack in A2, not later |
| Surrogate does not generalise across subjects | Medium | Split by subject early so you find out at D3, not D5 |
| MATLAB access delayed | Medium | Everything works in Python; port last |
| Biarticular effect turns out negligible | Medium | That is a publishable negative result — report the mechanism |
| **Policy exploits surrogate error (D3)** | **High** | The standard model-based RL failure, and it looks like a *great* result until checked. Ensemble disagreement penalty, short branched rollouts, mandatory D4 ground-truth validation |
| Surrogate inaccurate outside training distribution | High | Ensemble uncertainty; report how often the policy ran in high-disagreement regions |
| HPC allocation smaller than assumed | Medium | Tiered D1. Drop to Tier 1, lean harder on warm-starting |

---

## 8. Immediate next actions

1. **Install OpenSim 4.5+**, Python API working, bundled Moco examples converging. Nothing in
   Phase A–D starts without this.
2. Ask your mentor to set up the **MATLAB API** in parallel — not at the end.
3. Download the Camargo dataset, inspect one subject's file formats.
4. Keep [`notes/`](notes/) current as you go.

---

## 9. Phase ↔ old E-number map

Commits and notes before 2026-09-19 use E-numbers. Mapping for readability:

| Old | Now |
|---|---|
| E1 smoothed fatigue dynamics | **B2** — done |
| E2 multi-joint allocation | **C** — core contribution |
| E3 per-muscle fatigue | **B1** |
| E4 full dynamics / walking | **A** — automatic, Moco does gait |
| E5 gait-phase torque prediction | folded into C, minor |
| E6 recovery-rate sensitivity | B3, supporting |
| E7 cross-subject generalisation | **D3** |
| E8 sparse GP | subsumed by **D** |
| E9 synergy grouping | dropped — scooped by Lambeth et al. 2025 |
| Gate R | **B4** |

---

## 10. Reading

Plain-language summaries of everything: [`notes/papers.md`](notes/papers.md).
Teardowns: [`docs/mfac_teardown.md`](docs/mfac_teardown.md),
[`docs/peternel2019_teardown.md`](docs/peternel2019_teardown.md).
Literature screening: [`docs/gap_analysis.md`](docs/gap_analysis.md).

**Essential for the phases ahead**
- Dembia, Bianco, Falisse, Hicks, Delp (2020). *OpenSim Moco.* PLoS Comput Biol. — Phase A.
- Dembia, Silder, Uchida, Hicks, Delp (2017). *Simulating ideal assistive devices…* PLoS ONE. —
  the Phase A/C methodological template.
- Peternel, Fang, Tsagarakis, Ajoudani (2019). RCIM 58:69–79. — per-muscle fatigue, max-min
  objective, OpenSim static-optimisation pattern.
- Camargo et al. (2021). J Biomech. — the dataset.
- Rajagopal et al. (2016). IEEE TBME. — the 3D model for the headline result.

**Outstanding**
- Ma et al. (2010), Virtual Phys Prototyp 5(3):123–137 — recovery-rate values (B3).
- Check **arXiv** for the smoothing claim; PubMed covers that literature badly.
- Check preprint servers for scoop risk — unassessed, the available connector has no text search.

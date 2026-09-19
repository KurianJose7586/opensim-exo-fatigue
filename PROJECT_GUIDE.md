# AI-Driven Human–Exoskeleton Digital Twin
### Personalized and Fatigue-Aware Lower-Limb Assistance Using MATLAB–OpenSim Moco

**Status:** foundation built and validated (see §4). Realigned to the title 2026-09-19.
**Scope:** simulation only · **Compute:** laptop for development, cluster for Phase D

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
  AI SURROGATE                             learns assistance <-> muscle force map,
  replaces the Moco call in the loop       so the loop runs in ms not minutes
          |
          v
  MATLAB orchestration                     scripting layer over the Moco side
```

**Read the arrow from the surrogate back into the loop carefully — that is why the AI is not
decorative.** Fatigue-aware allocation must evaluate many candidate assistance profiles. Each one
changes the muscle forces, which requires a Moco solve, which takes minutes. Real-time control needs
milliseconds. Learning that map is not an add-on; without it the control loop cannot close.

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
| **AI-Driven** | Phase D — surrogate replacing the Moco call inside the control loop | Not started |
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

### Phase D — The AI surrogate

**Restores: AI-Driven. Structurally necessary, not bolted on.**

The Phase C loop needs muscle forces for every candidate assistance profile. Each needs a Moco
solve. That cannot run in a control loop.

- **D1** Sample across subject parameters, gait speed, fatigue state and assistance profile. Run
  Moco at each point. **Warm-start from the nearest solved neighbour** — typically 3–5× faster and
  the single highest-value optimisation here. Log failures; non-convergence is data.
- **D2** Train the surrogate: assistance profile + subject + state → per-muscle forces. Small
  network; this is a regression problem, not a reason to reach for something large.
- **D3** Hold out **by subject**, never by random split — random splitting leaks subject identity
  and will flatter the result.
- **D4** **Closed-loop validation, the step that matters:** put the surrogate in the Phase C loop and
  check the fatigue benefit survives. Low prediction error that loses the benefit is meaningless.
- **D5** Report inference latency against Moco solve time. That ratio is the contribution.

*Optional depth, enabled by work already done:* because Phase B's dynamics are differentiable, the
policy can in principle be trained **through** the optimiser rather than imitating it. That is the
stronger version. Treat it as a stretch goal, not the plan.

### Phase E — MATLAB

**Restores: MATLAB.**

Moco has a MATLAB API; CasADi has a MATLAB interface. The Moco orchestration and the fatigue layer
both port. **Keep the learning in Python** — that split is standard and defensible, and the handoff
is files on disk, which both read natively.

Your mentor owns this. **Give them a date.** They are on the critical path from Phase A if you want
the MATLAB API set up alongside the Python one.

---

## 6. Compute

| Work | Laptop | Cluster |
|---|---|---|
| Phase A, single subject, 2D model | ✅ | — |
| Phase B (all of it) | ✅ | — |
| Phase C development | ✅ | — |
| Phase D dataset generation | ❌ | ✅ |
| Multi-subject, 3D model, uncertainty sweeps | ❌ | ✅ |

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

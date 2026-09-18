# Teardown — Peternel, Fang, Tsagarakis, Ajoudani (2019)
### *A Selective Muscle Fatigue Management Approach to Ergonomic Human-Robot Co-Manipulation*

RCIM 58:69–79. DOI 10.1016/j.rcim.2019.01.013. CC BY-NC-ND (TU Delft accepted manuscript).
**This is Zhang et al.'s reference [27]**, not [17]. Same lab lineage (IIT HRI²/HHCM), same authors.

**Why it matters more than expected:** it contains the **per-muscle** version of the fatigue model
that Zhang et al. 2026 collapsed to a scalar, and it contains a working demonstration of **load
redistribution between muscle groups** — the central hypothesis of our E2.

---

## 1. The model lineage (important for positioning)

```
Ma et al. 2009 [23]        dynamic muscle fatigue model, force-driven
        │
        ▼
Peternel et al. 2018 [21]  low-complexity EMG-driven version (Autonomous Robots 42(5))
        │                   ← Zhang et al.'s ref [17]. STILL NEEDED.
        ▼
Peternel et al. 2019 [27]  PER-MUSCLE, force-driven, GPR-estimated forces  ◄── THIS PAPER
        │
        ▼
Zhang et al. 2026          SCALAR, single muscle group, exoskeleton MPC
```

**Note the regression at the last step.** The group had per-muscle fatigue in 2019 and went back to
a single scalar index for the 2026 exoskeleton work. That is the gap E3 fills — and it is not a
novel modelling claim, it is *restoring fidelity the same group already demonstrated.* Much safer to
defend.

---

## 2. The per-muscle fatigue model — equation (7)

```
dV_i/dt =  (1 - V_i(t)) · f_mi(t)/C_i     if f_mi(t) ≥ f_th
          -V_i(t) · R/C_i                 if f_mi(t) <  f_th
```

- `V_i` ∈ [0,1] — fatigue index **of the i-th muscle**
- `f_mi` — estimated force of muscle i (from GPR)
- `C_i` — **per-muscle** capacity parameter, subject- and muscle-dependent
- `R` = 0.5, *"a conservative value, as in [21]"* — **same unvalidated constant Zhang et al. reuse**
- `f_th` — force threshold separating fatigue mode from recovery mode

Capacity calibration, equation (8): `C = -(f_m^ref · T) / ln(1 - 0.993)`, averaged over several
reference forces. Identical in form to Zhang et al.'s (10).

**The threshold discontinuity is here too.** It runs through the entire lineage: Ma 2009 → Peternel
2018 → Peternel 2019 → Zhang 2026. **E1 is therefore not patching one paper's hack — it repairs a
structural defect in a model family used across at least four papers.** That materially strengthens
E1's framing.

---

## 3. Endurance time — equations (9) and (10), directly reusable

Per-muscle maximum endurance time:

```
T_i(q_h, f) = -(C / f_mi(q_h, f)) · ln(1 - V_th)          (9)
```

Whole-limb endurance = the **minimum** across muscles. Their FMP1 objective:

```
argmax_{q_h} ( min_i T_i(q_h, f) )                        (10)
```

**A max-min endurance objective, already published by the group we are extending.** Use this as E2's
objective function rather than inventing one. It is defensible, comparable, and citable.

Magnitude of the effect they found: endurance time for upward polishing was **28.6 s** at the optimal
position; for downward polishing, **907.0 s**. Configuration matters enormously — far more than
Zhang et al.'s 3.5% assistance margin.

---

## 4. FMP2 — the redistribution precedent (critical for E2)

**What they do:** split muscles into two antagonistic groups; when one group's fatigue crosses a
threshold, the robot **rotates the task object** so the endpoint force direction changes and the
other group takes over. The tired group then recovers while the rested group works.

Group assignment, equations (11)–(14): a reward `γ = min(Σc₁, Σc₂) · Σ(c₁ ⊕ c₂)` balancing
within-group coherence against between-group antagonism, evaluated over activation patterns across
endpoint force directions.

**Validation (Fig. 7):** with 6 muscles (BB, AD, PM vs TB, PD, LD), fatigue in group G₁ rises to
threshold at ~45 s, the robot reconfigures, **G₁'s fatigue visibly decreases while G₂'s rises.**
Confirmed across 6 subjects; subjective ratings favourable.

### What this does to E2

**Good news:** redistribution across muscle groups to extend endurance is *demonstrated to work.*
Our central hypothesis is no longer speculative — it has a published precedent. That de-risks the
project substantially.

**The gap that remains — and it is a clean one:**

| | Peternel 2019 (FMP2) | Our E2 |
|---|---|---|
| Mechanism | Change **task geometry** (rotate object) | Allocate **assistance torque** |
| Control | **Discrete switch** at a fatigue threshold | **Continuous optimal** allocation |
| Coupling source | Task force direction | **Biarticular muscles** across joints |
| Limb | Arm, co-manipulation | Lower limb, exoskeleton, gait |
| Groups | Exhaustive combinatorial search over 6 muscles | See E9 below |

E2 is now *"continuous optimal torque allocation"* versus their *"discrete threshold-triggered task
reconfiguration."* Well-founded, clearly differentiated, and modest enough to actually finish.

---

## 5. New opening — E9: muscle grouping that scales

Their grouping algorithm *"goes through all possible divisions of muscle groups"* and picks the
highest reward. Fine for 6 arm muscles. **Combinatorially explosive for 18+ lower-limb muscles across
three joints**, and it forces exactly two groups, which is an arbitrary restriction.

**Opening:** principled, scalable grouping — muscle synergy extraction (NMF on activation patterns)
or spectral clustering on a coupling matrix, yielding a data-driven number of groups. Concrete,
technically substantive, low risk, and it directly enables E3's grouped fatigue states.

---

## 6. The OpenSim pipeline is the template for our offline stage

Their offline stage is exactly what we need to build:

- Upper-limb musculoskeletal model (Saul et al. [26]) in **OpenSim**
- **Static optimization**, equation (4): `argmin aₘᵀaₘ s.t. Jₘᵀ(Fₘ⁰aₘ) = τ_h`
- Output muscle forces → training data for GPR → online estimation

Swap the upper-limb model for a lower-limb one and this is our Stage S4 pipeline, with a published
methodological precedent to cite.

**One honest nuance for E4.** They justify static optimization over CMC/dynamic optimization by
citing Anderson & Pandy [33], *"Static and dynamic optimization solutions for gait are practically
equivalent."* That citation is **about gait**, so it partly undercuts the argument that we need full
dynamics for a walking task. E4 should therefore be motivated by the **fatigue-MPC horizon problem**
(predicting torque over a horizon during dynamic gait) rather than by muscle-force estimation
accuracy, where SO is apparently adequate. Do not overclaim this.

---

## 7. Their stated limitations

| Limitation | Note |
|---|---|
| GPR scalability — *"time-consuming and could slow down the real-time prediction capacity"* | **Same issue Zhang et al. raise in 2026.** Unsolved across both papers; they suggest Locally Weighted Regression [44] or Local GPR [45]. Strengthens E8 |
| Subject-dependent calibration required | Same as Zhang's FW2 → our E7 |
| Motion-capture precision dependence | Not our problem in simulation |
| Only position/orientation constraints considered; *"other constraints can be considered"* | Open |

**n = 6 male subjects** — better than Zhang et al.'s n = 3, still thin.

---

## 8. Still to obtain

**Peternel, Tsagarakis, Caldwell, Ajoudani (2018), *Robot adaptation to human physical fatigue in
human–robot co-manipulation*, Autonomous Robots 42(5):1011–1021.** Zhang's [17], this paper's [21].
It is the origin of the low-complexity fatigue model and of `R = 0.5`. Get it for the parameter
justification — E6 (recovery-rate sensitivity) depends on knowing where that number came from.

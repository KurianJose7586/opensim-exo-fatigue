# Gate F0 — Gap Analysis

**Purpose:** establish what nobody has done, before writing code. Becomes the paper's related-work
section. **Status:** in progress.

---

## Screening rubric

Answer these three from the abstract. Under a minute per paper.

1. **Is fatigue inside the optimizer, or evaluated after it?** — Inside = Threat. After = Context.
2. **Is fatigue lumped/scalar, or per-muscle?** — Per-muscle = Threat. Lumped = you can beat it.
3. **Single joint or multi-joint?** — Single = you extend it. Multi-joint = closer to your claim.

**Multi-joint + per-muscle + inside the optimizer = stop and read in full. That is this project.**

### Categories

| Tag | Meaning | Action |
|---|---|---|
| **THREAT** | Overlaps the core claim | Read in full. Write down exactly what it cannot do |
| **BASELINE** | Gives a method to compare against | Read methods. Implement as a comparator |
| **TOOL** | Model, parameter set, or dataset | Extract the specific thing. Don't read the rest |
| **CONTEXT** | Intro or discussion citation | Record the one-line claim. Move on |
| **NOISE** | Not relevant | Skip |

---

## Screened papers

### 1. Zhang, Jiang, Ajoudani, Tsagarakis (2026) — *Muscle Fatigue-Aware Controller for a Semi-Rigid Knee Exoskeleton*
**IEEE T-ASE 23. THREAT + BASELINE. Closest competitor found.**

| Q | Answer |
|---|---|
| Fatigue in optimizer? | **Yes** — predictive control adjusts assistance to reduce fatigue progression |
| Lumped or per-muscle? | **Lumped** — GPR estimates activation from joint state; no muscle-level resolution |
| Joints | **Single (knee)** |

**Does:** offline GPR calibration mapping EMG-derived activation ↔ joint moment/angle → EMG-free
online activation estimation from kinematics + GRF → model-based fatigue evaluation → predictive
controller. Hardware-validated. Shows power conservation at low fatigue, increasing output with
fatigue.

**Cannot do — this is the wedge:**
- **No muscle-level resolution.** A lumped activation estimate structurally cannot represent
  redundancy between synergists. The hypothesis that optimal assistance *redistributes load across
  synergists to preserve capacity* is inaccessible to this method by construction.
- **Single joint.** No multi-joint coordination problem — assisting the hip changes ankle loading;
  they never face this.
- **No muscle-property personalization.** GPR calibration is not subject-specific physiology.
- Explicitly frames avoiding musculoskeletal modelling as a *feature*, which leaves the model-based
  route entirely open.

**Consequences for this project:**
- **C3 (EMG-free fatigue observer) is scooped.** Drop as a standalone contribution.
- **C2 is partially scooped.** Fatigue-aware predictive assistance now exists.
- **C1 survives untouched** and becomes the lead contribution.
- **Implement their lumped approach as the primary baseline.** Beating published state of the art
  is far stronger than beating a strawman fixed profile.

---

### 2. Co, Begon, Bailly, Moissenet — *Optimal control driven functional electrical stimulation: A scoping review*
**TOOL + CONTEXT. Highest-value reference for F0.**

PRISMA review, 44 studies, search to Feb 2024. Half *in silico* — confirms simulation-only work
publishes in this space.

**Why it matters:** FES is not exoskeletons, but the mathematical structure is nearly identical —
fatigue limits the intervention, optimal control manages it. In FES, fatigue models are commonly
embedded as states in OC problems.

**Action required — this may change C1's novelty claim:**
Work through its reference list for papers embedding fatigue as OC state variables. If the technique
is established in FES, C1's claim shifts from *"first to embed fatigue in optimal control"* to
*"first in high-DOF musculoskeletal gait/exoskeleton control, with the specific problems that arise
there — non-smooth recruitment, state-count explosion, muscle grouping."*

Weaker claim, but defensible. A claim that collapses under review is worth nothing. **Resolve this
before committing to C1's framing.**

Its stated field gaps — no consensus on fatigue modelling, inconvenient identification protocols,
poor computational performance reporting — read as a direct invitation for C1.

---

### 3. Toffoli, Tounekti, Hakim, Cocquerez, Ben Mansour (2026) — *Muscle fatigue and postural balance reorganisation during exoskeleton-assisted load handling*
**Gait & Posture 130:110613. CONTEXT.** Upper limb, static hold, passive device. Not a competitor.

**Three things to take:**
- **Time-to-exhaustion validated as an endpoint, with magnitude:** 896 s vs 307 s, nearly tripled,
  P < 0.001. Justifies the metric choice.
- EMG median frequency decline confirmed as the fatigue indicator; MVC preserved.
- **Assistance shifted postural control to a low-complexity regime** (lower MSE, higher DFA α1).
  Evidence that exoskeletons change motor *strategy*, not just mechanics — supports the premise that
  the human is not a passive input-output system under assistance.

**Pre-empt in discussion:** this shows assistance has unintended side effects. A reviewer will ask
whether fatigue-optimal assistance degrades something unmeasured.

---

### 4. Nacarino et al. (2026) — *Mechatronic Design and Development of a Lower-Limb Exoskeleton System…*
**Bioengineering 13(6):644. NOISE, marginal TOOL.**

Device design paper, lower-tier venue. Only value: realistic actuator torque limits and device mass
for the exo model, plus a throwaway intro citation. Do not spend time on it.

---

## Current gap statement (revised after screening)

> Fatigue-aware exoskeleton control exists, but only with **lumped** fatigue estimates on **single
> joints**. Because lumped estimates cannot resolve muscle-level redundancy, no existing method can
> exploit — or even represent — redistribution of load across synergists. Whether muscle-level
> fatigue modelling inside the optimal control problem produces qualitatively different multi-joint
> assistance allocation is open.

**Still to verify before this stands:**
- [ ] FES literature — is fatigue-as-OC-state already established? (from review's references)
- [ ] Anyone embedding fatigue in **OpenSim/Moco** specifically?
- [ ] Anyone optimizing **multi-joint** assistance under fatigue?
- [ ] Forward-citations of Xia & Frey-Law (2008) — who put it inside an optimizer?
- [ ] Forward-citations of Zhang et al. (2026) — who is already building on the competitor?
- [ ] Any fatiguing-protocol gait dataset with EMG? (determines whether C3 survives in any form)

---

## Track status — SUPERSEDED

The abstract C1/C2/C3 tracks have been replaced. After a full read of Zhang et al., the project is
now framed as a **direct extension of that paper** rather than an independent novelty claim.

See [`mfac_teardown.md`](mfac_teardown.md) for the full teardown and
[`../PROJECT_GUIDE.md`](../PROJECT_GUIDE.md) for the extension set E1–E8.

Mapping from the old tracks:

| Old | Now |
|---|---|
| C1 — fatigue as differentiable states | **E1** — smoothing their frozen-branch hack. Same idea, concrete target, no C++ needed |
| C2 — long-horizon multi-joint allocation | **E2** — multi-DoF allocation with biarticular coupling. Their own stated future work (FW3) |
| C3 — EMG-free fatigue observer | **Dropped.** Zhang et al. did exactly this |

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

Everything as `kurianjose7586 / kurianjose005@gmail.com`. The first commit went out under a
different address picked up from the environment and had to be rewritten.

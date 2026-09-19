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

---

## Open questions

- [ ] Resolve the threshold disagreement: 0.05 in code versus 0.02% in the paper. Which did they use?
- [ ] Confirm the tiring-rate constant is on the same scale between our calibration and the demo
      code values (15-20 there, 8.24 from our fit). Units need checking before values are reused.
- [ ] Does the frozen-switch cap move if the person tires faster or slower? We fixed one tiring rate.
- [ ] Get Ma et al. 2010 for published recovery-rate values (E6).
- [ ] Check arXiv for the smoothing claim — PubMed covers that literature badly.
- [ ] Check preprint servers for scoop risk. Not possible through the connector available here.
- [ ] Email Peternel: fitted constants, the Exo-Muscle model file, and permission to include the code.

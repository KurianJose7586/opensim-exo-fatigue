# Faculty update 3: message (22 November 2026)

No attachment needed. Edit the greeting.

---

**Subject: Capstone update: EMG received, H5 tested**

Dear [Sir / Ma'am],

A short update since the report of 11 November.

**The EMG arrived.** The dataset's authors sent us the EMG of the five participants recorded in
Madrid (five muscles per leg), with a table that puts each recording on the exoskeleton's clock.
It is not public, so it stays on our machine and we will cite their paper.

**What we did with it**

- Built muscle-activity curves on our strides for all five participants (1,433 strides).
- Checked our simulation's muscles against it for the first time. The timing of each muscle's main
  burst is right; the shapes agree moderately (median r 0.27 to 0.61 by muscle). The real muscles
  never fully switch off between bursts; the model's do, because it finds the least-effort
  solution.
- Tested H5: we re-optimised the exoskeleton torque with the model's muscles made to follow each
  participant's EMG, under the same torque budget. The chosen torque changes, but modestly: by
  about 10% when the EMG counts as much as effort, and by 23 to 34% when the muscles must follow
  it closely. Following the EMG costs 3 to 7% more muscle effort. This is three participants (two
  others' simulations did not pass our checks), so it is descriptive, not a statistical test.

**Also done since the report:** the AI-predicted torque on the scaled bodies gives the same muscle
effort as the measured torque (−1.8%, not significant), as it did on the generic body.

**What is left:** single strides and ramps in the simulation (the DGX request still stands), and
the write-up.

Could we have 15 minutes this week?

Regards,
Kurian Jose

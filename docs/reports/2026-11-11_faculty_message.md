# Faculty update 2: message to send with the report (11 November 2026)

Attach `2026-11-11_progress_report.pdf` and `figures/k7_hl03_sm_walking_stride.mp4`. Edit the greeting.
If the 10 November message has not gone out yet, send this one instead and attach both reports.

---

**Subject: Capstone update: AI torque models done and joined to the simulation**

Dear [Sir / Ma'am],

A short update on the ExoGait work, with a report and a video of the simulation attached.

**What is new**

- The preprocessing pipeline runs on all 19 participants: 5,964 strides, split by whole passes
  into training, validation and test data.
- The torque models are trained and scored on held-out data. A personalised LSTM predicts the
  torque the exoskeleton delivers at the joint to 2.4 Nm in walking (R² 0.97 at the hip, 0.94 at
  the knee). For a person it has never seen, the error is 4.0 Nm.
- H1, H2 and H3 are supported. Personalised models beat population models in all 19
  participants. Gait phase and locomotion mode help, but only slightly once the model is strong.
- The AI torque is joined to the simulation. Replayed in the musculoskeletal model in place of
  the measured torque, it gives the same muscle effort (within 1.4%).
- We found a way to check the simulation against a measurement: the exoskeleton's footplates
  record how the load is split between the feet. The model, never shown that signal, reproduces
  it (r = 0.90).
- The earlier result stands: an optimised torque with the measured torque's budget lowers the
  model's muscle effort by 34%, in all 16 participants tested.

**What is not done**

- The simulation still uses one generic body. Each participant's height and weight are in the
  dataset's paper, and scaling the model to them is our next step.
- The simulation covers walking on mean strides. Single strides and ramps come next.
- EMG (RO5, H5): the paper says EMG was recorded for five participants, but it was not released.
  We have written to the authors.

**What we need from you**

1. If the authors do not send the EMG by 1 December, may we test H5 on the model's own muscle
   activity instead, stated as such, and report H5 on real EMG as not testable?
2. DGX time for the full evaluation: about 5,000 simulations.
3. Your view on which torque the AI model should target. We predict both the motor's torque and
   the torque at the joint, and replay the second.
4. The work is in Python because we could not get a MATLAB licence. Please tell us if the
   registered title needs a formal change.

Could we have 15 minutes this week to go through it?

Regards,
Kurian Jose

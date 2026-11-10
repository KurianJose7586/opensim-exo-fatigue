# Faculty update: message to send with the report (10 November 2026)

Attach `2026-11-10_progress_report.pdf`. Edit the greeting and anything in [brackets].

---

**Subject: Capstone update: exoskeleton digital twin, simulation side running on all 19 participants**

Dear [Sir / Ma'am],

Here is where the ExoGait work stands since the brief of 14 October. A short report with the
figures is attached.

**What is done**

- We built an OpenSim model of the Fourier X2 exoskeleton on a 2D musculoskeletal model and
  mapped the dataset's joint angles onto it. This is checked on all 19 participants.
- With OpenSim Moco the model now reproduces the walking of all 19 participants in both
  controller modes. All 38 solves converge, with a median error of 0.6° at the hip and 0.4° at
  the knee. Walking speed is not given to the model, and the speed it settles on matches the
  data (r = 0.95).
- We found that the dataset's two torque columns are different things. One is the motor's
  torque. The other is the torque delivered at the joint. About half of the motor torque only
  accelerates the motor's own rotor. We think the delivered torque is the right target for the
  AI model and would like your view.
- A first test of H4 on 16 participants. Against the exoskeleton switched off, the measured
  assistance lowers the model's muscle effort by 16% (median). An optimised torque with the
  same torque budget lowers it by a further 34%, in all 16. This is simulation on a generic
  body, so it is a result about the model, not yet about real effort, and the numbers still
  need a robustness pass.

**What is not done**

- The AI torque-prediction part (preprocessing, data splits, baseline and LSTM models) has not
  started in code. It is our next piece of work.
- The EMG part (RO5, H5) is blocked. The public dataset has no EMG files.

**What we need from you**

1. EMG data if you have access to it, or your agreement that RO5 and H5 be reported as not
   testable.
2. DGX time for the full evaluation: about 5,000 simulations, which is about a week on a laptop.
3. Your decision on which torque the AI model should predict, and on the baseline for H4. The
   report lists our defaults.
4. The work is in Python with OpenSim's Python interface, because we could not get a MATLAB
   licence. The method is unchanged and every file opens in MATLAB. Please tell us if the
   project title ("…Using MATLAB–OpenSim Moco") needs a formal change.

Could we have 15 minutes this week to go through the report?

Regards,
Kurian Jose

# Reference implementation — Peternel's PHRC repository

`https://gitlab.com/lukapeternel/PHRC.git` (clone over HTTPS; the `git@` URL needs SSH keys).
Two files: `PHRC_muscle_fatigue_model.py`, `PHRC_sawing_emg.py`. Author contact in the headers:
**l.peternel@tudelft.nl**.

**Why this matters:** E1 no longer means reimplementing a fatigue model from a paper and hoping the
interpretation is right. **You now diff your smoothed version against the authors' own code.** That
is a far stronger validation story for the paper.

---

## 1. The model as implemented

```python
if MA[i] > relax_th[i]:                       # fatigue mode
    dV[i] = (1 - V[i]) * MA[i]/CF[i]
    V[i] += dV[i] * dt
else:                                          # relaxation mode
    dV[i] = V[i] * CR[i]/CF[i]
    V[i] -= dV[i] * dt
V[i] = clip(V[i], 0.0, 1.0)
```

Matches Peternel 2019 eq. (7) and Zhang 2026 eq. (8), with `CR` ≡ `R`, `CF` ≡ `C_i`.
Confirms the model is **natively per-muscle** — arrays indexed by muscle throughout.

Docstring confirms the lineage explicitly: *"Muscle activity can be replaced by other real-time
effort variables such as muscle force from a biomechanical model as in [Peternel, et al. 2019]."*
2018 = EMG-driven, 2019 = force-driven, identical structure.

---

## 2. Real parameter values (from `PHRC_sawing_emg.py`)

```python
CF       = [20.0, 15.0]     # fatigue capacity, per muscle — differs between muscles
CR       = [0.5, 0.5]       # recovery rate — the R = 0.5 both papers cite
relax_th = [0.05, 0.05]     # relaxation threshold: 5% of MVC
MVC      = [1.0, 1.0]
dt       = 0.001            # 1 ms
```

Code comment on `CR`: *"muscle relaxation parameter based on calibration **or literature**"* — so
even the authors treat it as a borrowed default, not a measured value. **Confirms E6 is worth doing.**

### Threshold discrepancy — check this

- Code: `relax_th = 0.05` (5% MVC)
- Peternel 2019 §3.2: *"the muscle force threshold that determines the relaxation mode was set to
  0.02% of MVC for all muscles"*

These disagree, and it is **the exact threshold E1 smooths.** Resolve it before building E1, and
report the sensitivity — if controller behaviour depends strongly on a parameter stated
inconsistently between a paper and its own reference code, that is a legitimate finding.

**Also verify the `CF` scale.** The demo values (15–20) are for arm muscles in a sawing task. Zhang
et al. compute `C_F` from endurance tests via their eq. (10). Work out the units and confirm the two
are on the same scale before porting values across — do not assume.

---

## 3. Confirmed bug — `for i in range(2)` is hardcoded

```python
def fatigue(self, MA):
    for i in range(2):        # ← should be range(self.N)
```

`N` is accepted as a constructor argument and every array is sized `N`, but the update loop is
hardcoded to two muscles. **Muscles with index ≥ 2 never update and silently return zero fatigue.**

Verified:

```
N = 4, all muscles at MA = 0.5, after 5 s:
  V = [0.1175, 0.1175, 0.0, 0.0]
```

**This directly affects you.** E3 uses per-muscle fatigue across 6+ lower-limb muscle groups. Using
this class unmodified would silently drop everything past the second group, and the failure mode is
plausible-looking zeros rather than a crash.

**Fix:** `for i in range(self.N)`.

*The repository is a public demo/teaching release, not necessarily the code that produced the
published experiments. Do not infer anything about the papers' results from this. Just fix it, and
note in your methods that you corrected the released reference implementation.*

---

## 4. Other implementation notes worth carrying into E1

**Forward Euler, fixed step**, with an explicit warning in the source:
> *"It is crucial that this loop runs with the defined sample time, otherwise the integration of
> fatigue will not work properly!"*

The demo runs at `dt = 0.001`. Zhang et al.'s MPC runs at 100 Hz, so `Δt = 0.01` — **ten times
coarser.** Quantify the Euler error at MPC timestep sizes as part of E1; it is a few lines and it
strengthens the numerical-methods section.

**Clamping to [0, 1] after integration** is a second non-smoothness. The continuous ODE keeps `V` in
bounds naturally, so the clamp exists to catch Euler overshoot. Your smoothed formulation should
ideally not need it — if it does, that is informative.

**Activation is a plain normalization:** `MA = EMG / MVC`. Matches Zhang eq. (7).

---

## 5. Effect on the reading list

**You are no longer blocked on Peternel et al. 2018** (Autonomous Robots 42(5):1011–1021):

| What you wanted from it | Where it actually is |
|---|---|
| Model structure | This code — complete and unambiguous |
| `R = 0.5` value | This code (`CR`), confirmed |
| Recovery-rate alternatives for E6 | **Ma et al. 2010**, *Virtual and Physical Prototyping* 5(3):123–137 — Peternel 2019's ref [42], cited as where *"other recovery rates can be found in literature"* |

Get Ma 2010 instead. It is the actual source of recovery-rate values and it unblocks E6.

The 2018 paper remains nice-to-have for the calibration protocol and original justification, but it
is off the critical path.

**If you still want it:** TU Delft repository (where the RCIM manuscript came from), IIT's IRIS
repository, or Springer's Autonomous Robots page. Simplest route — **email him.** The address is in
the source headers, he publishes his code openly with contact details, and he may also share the
fitted `C_F` values or the experimental code.

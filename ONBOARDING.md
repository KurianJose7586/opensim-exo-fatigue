# Onboarding

For someone joining the project. Should take about an hour to get productive.

---

## 1. What this is, in sixty seconds

A powered leg brace should help you more as your muscles get tired. Working out *how much* help, at
*which joint*, moment to moment, is the problem.

We build a computer model of a specific person's legs — bones, muscles, the brace — in OpenSim.
That model tells us how hard each muscle is working. We track how tired each muscle is getting, and
use that to decide how to split assistance across the hip, knee and ankle.

The catch: working out the best assistance takes minutes of computation, and the brace needs an
answer in milliseconds. So we train a neural network to do it instantly. That is the AI half, and it
exists because the loop cannot close without it — not as decoration.

**Current state: every phase is built and smoke-tested end to end. The full-scale runs happen on
the DGX — see [`docs/RUN_ON_DGX.md`](docs/RUN_ON_DGX.md).**

---

## 2. Set up (20 minutes)

```bash
git clone https://github.com/KurianJose7586/opensim-exo-fatigue
cd opensim-exo-fatigue
python -m venv .venv
.venv/Scripts/activate          # Windows;  source .venv/bin/activate on Linux/Mac
python -m pip install -r requirements.txt
```

Check it works — all three should print tables and pass their assertions:

```bash
python src/fatigue/calibrate.py   # 0.6 s
python src/mpc/mfac.py            # 1 s
python src/fatigue/model.py       # 9 s
```

### Gotchas we have already hit

- **Use `python -m pip`, not `pip`.** Kurian's Anaconda install is broken and the bare `pip`
  launcher fails. `python -m pip` works regardless.
- **OpenSim is not pip-installable.** It gets its own conda env, Python 3.11 (the newest the
  4.6 build supports). Working recipe on Windows, with standalone micromamba, no Anaconda needed:

  ```bash
  micromamba create -n opensim -c opensim-org -c conda-forge python=3.11 opensim       "libblas=*=*openblas" numpy scipy pandas pyyaml matplotlib
  micromamba run -n opensim python -m pip install torch gymnasium stable-baselines3
  micromamba run -n opensim python src/musculoskeletal/twin.py     # Gate A, ~1-2 min
  ```

  Three traps, all hit (details in `notes/observations.md`): **use OpenBLAS**, because MKL breaks
  OpenSim's IPOPT. **Never conda-install casadi** into this env, because Moco bundles its own.
  **Run through `micromamba run`** (or an activated shell), or the solver plugins are not found.
- **Background runs look like they produce nothing** — Python buffers. Use `python -u`.
- `src/mpc/periodic.py` takes about four minutes. The other three are seconds.

---

## 3. Read in this order

| # | File | Why |
|---|---|---|
| 1 | [`README.md`](README.md) | Current status, layout |
| 2 | [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) | The plan. Sections 1–4 are the important ones |
| 3 | [`notes/papers.md`](notes/papers.md) | Every paper, each explained in plain English. **Start here if the biomechanics is unfamiliar** |
| 4 | [`notes/results.md`](notes/results.md) | Every number we have produced and how far to trust it |
| 5 | [`docs/mfac_teardown.md`](docs/mfac_teardown.md) | The paper the project is anchored to |
| 6 | [`notes/decisions.md`](notes/decisions.md) | Why things are the way they are, including reversals |

Skip the rest until you need it. [`docs/guide_v2_extension_framing.md`](docs/guide_v2_extension_framing.md)
is an **archived old plan** — do not work from it.

---

## 4. What exists and what it does

```
src/fatigue/model.py       the fatigue equation, made smooth so an optimiser can use it
src/fatigue/calibrate.py   fits the per-person "how fast do they tire" constant
src/mpc/mfac.py            a published controller, rebuilt and reproduced
src/mpc/periodic.py        measures what that published method's shortcut costs
external/PHRC/             the original authors' code. READ ONLY, see below
```

Four headline numbers, all reproducible by running the scripts:

- Our fatigue model is **bit-exact** against the original authors' released code
- One fitted constant predicts two held-out published trials to **0.6%**
- We reproduce a published IEEE experiment to **1.7%**
- The published method's shortcut caps how far ahead it can plan; past that the error reaches
  **72% of maximum assistance**

---

## 5. Rules

**Do not edit `external/PHRC/`.** It is the original authors' code, included unmodified as our
validation baseline. If you edit it — including fixing the bug it contains — we lose the ability to
prove our implementation is correct. Our code goes in `src/`. See
[`external/PHRC/NOTICE.md`](external/PHRC/NOTICE.md).

**It contains a real bug**: the fatigue loop is hardcoded to two muscles, so any muscle past the
second silently reports zero. Verified. Work around it in our code, never patch it there.

**Every script keeps a runnable self-check.** They assert their own results under `__main__`. If you
change the logic, the assertions must still pass, or be updated with a reason.

**`data/`, `results/` and `refs/` are gitignored.** Large, regenerable, or copyrighted. Force-add
small summaries if you want them versioned.

**Do not hand-edit anything in `results/`.** Regenerate it.

---

## 6. Things you could pick up

Roughly ordered by value. Nothing here is blocked on anyone else.

| Task | Notes |
|---|---|
| **Recovery rate R — find a measured value (Liu et al. 2002, Wood et al. 1997)** | Ma et al. 2010 is traced: its R is borrowed too, and maps to 0.33–2.4 in our units. The Phase C margin holds for R ≤ 1 and fades at 2.4. See `notes/observations.md`, `notes/results.md` §8 |
| **Download the Camargo dataset, inspect one subject** | Needed next regardless. Marker-set mismatch is the thing that reliably eats a week; better to find out now |
| **Check arXiv for our main novelty claim** | We searched PubMed, which covers engineering badly. The claim is *provisional* until arXiv is checked. See [`docs/gap_analysis.md`](docs/gap_analysis.md) |
| **Check preprint servers for scoop risk** | Completely unassessed — the tool we had has no text search |
| **Find two missing papers** | Ma et al. 2010 (recovery rates) and Bergmann et al. 2025. Both listed in [`notes/papers.md`](notes/papers.md) |
| **Resolve a parameter discrepancy** | A threshold is 0.05 in the authors' code but stated as 0.02% in their paper — and it is the exact threshold our method smooths. See [`notes/observations.md`](notes/observations.md) |
| **Build plots** | Everything is terminal tables right now. Four plots would make the work presentable |

---

## 7. Working on it

Commit under your own name. That was agreed with Kurian on 2026-10-02. Each person's work is
attributed to them, so check `git config user.name` / `user.email` before your first commit.
Work on a branch and merge into `main`, rather than committing to `main` directly.

**Append to [`notes/`](notes/) as you go.** Findings in `results.md`, surprises and dead ends in
`observations.md`, choices in `decisions.md`, papers in `papers.md`. It is deliberately rough. A
messy complete record beats a clean partial one, and the write-up is built from it.

---

## 8. Who to ask

**Kurian** for anything about the project. **The supervisors** control the cluster images and the
GPU allocation, and are handling the MATLAB side — the current asks are written up in
[`docs/progress_update.md`](docs/progress_update.md).

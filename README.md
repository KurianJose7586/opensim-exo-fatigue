# AI-Driven Human–Exoskeleton Digital Twin

Simulation-based extension of the muscle fatigue-aware exoskeleton controller of
Zhang et al. (2026) to multi-joint, per-muscle, differentiable fatigue dynamics.

**Start here:** [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) — research question, extension set, stages.

---

## Status

**E1 complete. Gate R passed.**

- `src/fatigue/model.py` — smoothed fatigue dynamics, exact at k=0, converging as k shrinks
- `src/fatigue/calibrate.py` — C_F fitted on one trial predicts the other two to 0.6%
- `src/mpc/mfac.py` — MFAC reimplemented in CasADi, reproduces their MFAC trial to 1.7%
- `src/mpc/periodic.py` — **E1 result:** freezing the branch is benign at their 0.1 s horizon but
  caps planning horizon near 0.05·C_F; by 0.5 s it costs 0.215 peak error in p, 72% of p_max

Next: E3 (per-muscle fatigue states).

## Layout

```
docs/       teardowns of the anchor papers, gap analysis
src/        code, one directory per extension area
models/     OpenSim models: base / scaled to subject / with exoskeleton
data/       raw datasets and processed OpenSim inputs   (gitignored)
results/    simulation outputs                          (gitignored)
figures/    plots for the paper
refs/       papers, kept locally                        (gitignored)
external/   third-party reference code (see NOTICE)
```

`src/` areas: `fatigue/` (E1) · `mpc/` (MFAC reimplementation) · `musculoskeletal/` (OpenSim
pipeline) · `allocation/` (E2) · `activation/` (GPR) · `jobs/` (batch wrappers)

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

OpenSim is **not** pip-installable — install it separately (4.5+, Moco is bundled) and add its
Python API to the environment. See the guide, Stage S2.

## Reference code

`external/PHRC/` holds the authors' fatigue-model implementation, included unmodified as the
validation baseline for E1. **Do not edit it** — our own implementations go in `src/fatigue/`,
written from the published equations.

Provenance and licensing: [`external/PHRC/NOTICE.md`](external/PHRC/NOTICE.md).
Parameter values and a confirmed `range(2)` bug:
[`docs/reference_implementation.md`](docs/reference_implementation.md).

## Key documents

| File | What it is |
|---|---|
| [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) | The plan |
| [`docs/mfac_teardown.md`](docs/mfac_teardown.md) | Anchor paper, full read |
| [`docs/peternel2019_teardown.md`](docs/peternel2019_teardown.md) | Per-muscle model + redistribution precedent |
| [`docs/reference_implementation.md`](docs/reference_implementation.md) | The authors' code, parameters, bug |
| [`docs/gap_analysis.md`](docs/gap_analysis.md) | Literature screening (ongoing) |

## Reproducibility

Every file in `results/` records the git commit and config that produced it. Do not hand-edit
results.

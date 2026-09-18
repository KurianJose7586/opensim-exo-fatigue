# AI-Driven Human–Exoskeleton Digital Twin

Simulation-based extension of the muscle fatigue-aware exoskeleton controller of
Zhang et al. (2026) to multi-joint, per-muscle, differentiable fatigue dynamics.

**Start here:** [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) — research question, extension set, stages.

---

## Status

Not started. First task is **E1** (smooth fatigue dynamics) — see the guide.

## Layout

```
docs/       teardowns of the anchor papers, gap analysis, preregistration
src/        code, one directory per extension area
models/     OpenSim models: base / scaled to subject / with exoskeleton
data/       raw datasets and processed OpenSim inputs   (gitignored)
results/    simulation outputs                          (gitignored)
figures/    plots for the paper
refs/       papers, kept locally                        (gitignored)
```

`src/` areas: `fatigue/` (E1) · `mpc/` (MFAC reimplementation) · `musculoskeletal/` (OpenSim
pipeline) · `allocation/` (E2) · `activation/` (GPR) · `jobs/` (batch wrappers)

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

OpenSim is **not** pip-installable — install it separately (4.5+, Moco is bundled) and add its
Python API to the environment. See the guide, Stage S2.

## External code — do not vendor

The authors' reference fatigue-model implementation:

```bash
git clone https://gitlab.com/lukapeternel/PHRC.git
```

**No license file, so it is not redistributable — keep it outside this repo.** It is the validation
target for E1. Note the confirmed `range(2)` bug documented in
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

# AI-Driven Human–Exoskeleton Digital Twin

A musculoskeletal digital twin in OpenSim Moco, scaled to a subject, carrying per-muscle fatigue
dynamics and a lower-limb exoskeleton, used to work out how assistance should be allocated across
hip, knee and ankle as the person tires — with a learned surrogate standing in for the expensive
simulation so the loop can close in real time.

**New here?** Start with [`ONBOARDING.md`](ONBOARDING.md) — setup, reading order, and what to pick up.
**Already up to speed?** [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) is the plan.

---

## Status

**Phase B (fatigue layer) built and validated. Phase A (the OpenSim twin) not started.**

- `src/fatigue/model.py` — smoothed fatigue dynamics, exact against the authors' own code at k=0
- `src/fatigue/calibrate.py` — per-subject constant fitted on one trial predicts two held-out
  trials to 0.6%
- `src/mpc/mfac.py` — Zhang et al.'s controller in CasADi, reproduces their trial to 1.7%.
  This is the single-joint baseline Phase C has to beat
- `src/mpc/periodic.py` — the published method caps its planning horizon at ~0.05·C_F, which is
  why multi-joint allocation needs the smoothed form

**Next: Phase A — install OpenSim, build the musculoskeletal twin.** Nothing else starts first.

## Layout

```
notes/      rough running log: findings, results, observations, decisions
docs/       teardowns of the anchor papers, gap analysis
src/        code, one directory per extension area
models/     OpenSim models: base / scaled to subject / with exoskeleton
data/       raw datasets and processed OpenSim inputs   (gitignored)
results/    simulation outputs                          (gitignored)
figures/    plots for the paper
refs/       papers, kept locally                        (gitignored)
external/   third-party reference code (see NOTICE)
```

`src/` areas: `fatigue/` (Phase B, built) · `mpc/` (published baseline, built) ·
`musculoskeletal/` (Phase A, OpenSim pipeline) · `allocation/` (Phase C, multi-joint) ·
`activation/` + `jobs/` (Phase D, learned model and batch runs)

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

Use `python -m pip`, not bare `pip`. OpenSim is **not** pip-installable — install it separately
(4.5+, Moco is bundled) and add its Python API. Not needed for anything currently in the repo.
Full setup notes and known gotchas: [`ONBOARDING.md`](ONBOARDING.md).

## Reference code

`external/PHRC/` holds the authors' fatigue-model implementation, included unmodified as our
validation baseline. **Do not edit it** — our own implementations go in `src/fatigue/`, written from
the published equations. Editing it would destroy our ability to prove those are correct.

Provenance and licensing: [`external/PHRC/NOTICE.md`](external/PHRC/NOTICE.md).
Parameter values and a confirmed `range(2)` bug:
[`docs/reference_implementation.md`](docs/reference_implementation.md).

## Key documents

| File | What it is |
|---|---|
| [`ONBOARDING.md`](ONBOARDING.md) | **Start here if you are new** |
| [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) | The plan |
| [`notes/`](notes/) | **Running log — read this when writing up** |
| [`docs/mfac_teardown.md`](docs/mfac_teardown.md) | Anchor paper, full read |
| [`docs/peternel2019_teardown.md`](docs/peternel2019_teardown.md) | Per-muscle model + redistribution precedent |
| [`docs/reference_implementation.md`](docs/reference_implementation.md) | The authors' code, parameters, bug |
| [`docs/gap_analysis.md`](docs/gap_analysis.md) | Literature screening (ongoing) |

## Reproducibility

Every file in `results/` records the git commit and config that produced it. Do not hand-edit
results.

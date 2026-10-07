# AI-Driven Human–Exoskeleton Digital Twin

A musculoskeletal digital twin in OpenSim Moco, scaled to a subject, carrying per-muscle fatigue
dynamics and a lower-limb exoskeleton, used to work out how assistance should be allocated across
hip, knee and ankle as the person tires — with a learned surrogate standing in for the expensive
simulation so the loop can close in real time.

**New here?** Start with [`ONBOARDING.md`](ONBOARDING.md) — setup, reading order, and what to pick up.
**Already up to speed?** [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) is the plan.

---

## Status

**Whole pipeline built and smoke-tested end to end (2026-10-02). What remains is DGX compute.**
Runbook for the supervisor: [`docs/RUN_ON_DGX.md`](docs/RUN_ON_DGX.md) — one image, one script.

| Phase | Code | State |
|---|---|---|
| A — OpenSim twin | `src/musculoskeletal/twin.py` | **Gate A passed.** 2D model + 3-joint exo + device mass, MocoInverse converges, 27–41 s per evaluation on a laptop. **Known limits:** the model's source says not to use it for research (gastroc path), and it has no real push-off; ankle and gastroc results are blocked until a measured-data twin (`notes/observations.md`) |
| B — fatigue | `src/fatigue/` | Validated earlier (bit-exact vs authors' code; 0.6% held-out) |
| C — allocation | `src/allocation/` | **Re-run 2026-10-07 after a device-cap fix:** coupled min-max allocation cuts worst-muscle fatigue 64% vs none, 8.6% below the best baseline, same budget; a fixed allocation, not fatigue feedback; 0–10% across the unmeasured fatigue constants (`notes/results.md` §9) |
| D1 — dataset | `src/jobs/sweep.py`, `configs/` | Resumable sharded sweep; smoke tier 18/18 converged, 6 KB per solve |
| D2 — surrogate | `src/activation/surrogate.py` | Ensemble, subject-held-out split; R² 0.999 on toy, runs on twin data |
| D3 — RL policy | `src/activation/policy.py` | SAC in the surrogate, disagreement penalty; runs end to end |
| D4 — validation | `src/activation/validate.py` | Closed loop against the twin, benefit retention, latency |
| E — MATLAB | — | Supervisor's track |

Not done, needs a person: Camargo data loading and per-subject scaling (supervisor), the B4
squat re-validation through OpenSim, the arXiv novelty check, and a *measured* recovery rate R.
R = 0.5 is traced to Ma et al. 2010, which borrows it too. The recovery threshold M_th matters
more than R: the Phase C margin goes from 0% to ~10% across the plausible range of both
(`notes/results.md` §9).

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

`src/` areas: `fatigue/` (B) · `mpc/` (published baseline) · `musculoskeletal/` (A) ·
`allocation/` (C) · `jobs/` (D1 sweeps) · `activation/` (D2–D4).
`configs/` sweep tiers · `deploy/` Kubernetes manifests · `run_pipeline.sh` every stage.

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

Use `python -m pip`, not bare `pip`. OpenSim is **not** pip-installable and needs its own
Python 3.11 conda env — exact commands and the Windows traps in [`ONBOARDING.md`](ONBOARDING.md).
On the DGX everything runs in one image: [`docs/RUN_ON_DGX.md`](docs/RUN_ON_DGX.md).

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
| [`docs/RUN_ON_DGX.md`](docs/RUN_ON_DGX.md) | **Runbook for the DGX runs** |
| [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) | The plan |
| [`notes/`](notes/) | **Running log — read this when writing up** |
| [`docs/mfac_teardown.md`](docs/mfac_teardown.md) | Anchor paper, full read |
| [`docs/peternel2019_teardown.md`](docs/peternel2019_teardown.md) | Per-muscle model + redistribution precedent |
| [`docs/reference_implementation.md`](docs/reference_implementation.md) | The authors' code, parameters, bug |
| [`docs/gap_analysis.md`](docs/gap_analysis.md) | Literature screening (ongoing) |

## Reproducibility

Every file in `results/` records the git commit and config that produced it. Do not hand-edit
results.

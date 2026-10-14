#!/usr/bin/env bash
# Every stage of the project, one command each. See docs/RUN_ON_DGX.md.
#
#   bash run_pipeline.sh check              all self-checks + one twin solve      ~12 min
#   bash run_pipeline.sh phase_c            Phase C on the twin (125 solves)      ~15 min at 64 cores
#   bash run_pipeline.sh d1 [tier]          D1 population sweep                   tier-dependent
#   bash run_pipeline.sh d2 [tier]          D2 surrogate ensemble (GPU if present)
#   bash run_pipeline.sh d3 [tier]          D3 RL policy in the surrogate
#   bash run_pipeline.sh d4 [tier]          D4 closed-loop validation against the twin
#   bash run_pipeline.sh all [tier]         phase_c, d1, d2, d3, d4 in order
#
# tier: smoke | d1_tier1 (default) | d1_tier2 | d1_tier3   -- configs/<tier>.yaml
# WORKERS (default: all cores) and STEPS (D3, default 300000) are env overrides.
# Every stage resumes where it stopped: rerun the same command after a crash.

set -euo pipefail
cd "$(dirname "$0")"
STAGE=${1:?usage: bash run_pipeline.sh <check|phase_c|d1|d2|d3|d4|all> [tier]}
TIER=${2:-d1_tier1}
W=${WORKERS:-$(nproc)}
py() { python -u "$@"; }

case "$STAGE" in
  check)                       # every self-check in src/, cheapest first
    py src/fatigue/model.py
    py src/fatigue/calibrate.py
    py src/mpc/mfac.py
    py src/allocation/allocate.py
    py src/activation/surrogate.py
    py src/activation/policy.py
    py src/mpc/periodic.py
    py src/musculoskeletal/twin.py ;;
  phase_c)
    py src/jobs/sweep.py run configs/phase_c_grid.yaml --workers "$W" --retry-failed
    py src/jobs/sweep.py collect configs/phase_c_grid.yaml
    py src/allocation/run_phase_c.py ;;
  d1)
    py src/jobs/sweep.py run "configs/$TIER.yaml" --workers "$W" --retry-failed
    py src/jobs/sweep.py collect "configs/$TIER.yaml" ;;
  d2)
    py src/activation/surrogate.py "results/$TIER.npz" ;;
  d3)
    py src/activation/policy.py "results/surrogate_$TIER.pt" --steps "${STEPS:-300000}" ;;
  d4)
    py src/activation/validate.py "results/surrogate_$TIER.pt" \
       "results/policy_surrogate_$TIER.zip" --workers "$W" ;;
  all)
    for s in phase_c d1 d2 d3 d4; do bash "$0" "$s" "$TIER"; done ;;
  *)
    echo "unknown stage: $STAGE" >&2; exit 2 ;;
esac

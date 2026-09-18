# Third-party code — not ours

The Python files in this directory were written by **Luka Peternel** and are included here
unmodified, for reference and validation only.

| | |
|---|---|
| **Author** | Luka Peternel — l.peternel@tudelft.nl |
| **Source** | https://gitlab.com/lukapeternel/PHRC |
| **Retrieved** | 2026-09-19 |
| **License** | **None stated upstream.** Copyright remains with the author |

## Associated publications

- L. Peternel, N. Tsagarakis, D. Caldwell, A. Ajoudani. *Robot adaptation to human physical fatigue
  in human–robot co-manipulation.* Autonomous Robots 42(5):1011–1021, 2018.
- L. Peternel, C. Fang, N. Tsagarakis, A. Ajoudani. *A selective muscle fatigue management approach
  to ergonomic human-robot co-manipulation.* Robotics and Computer-Integrated Manufacturing
  58:69–79, 2019.

## Rules for this directory

- **Do not edit these files.** They are the validation baseline for E1 — an unmodified reference to
  compare against. Editing them destroys their purpose.
- Our own implementations live in `src/fatigue/`, written from the published equations.
- Cite the papers above, not this code, in any write-up.

## Known defect (upstream, do not fix here)

`PHRC_muscle_fatigue_model.fatigue()` loops `for i in range(2)` while arrays are sized `N`. Muscles
at index ≥ 2 never update and silently return zero fatigue. Verified. Work around it in our own code;
see `docs/reference_implementation.md`.

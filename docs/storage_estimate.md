# Storage estimate — where the 25–100 GB comes from

**Short version:** the range is wide because it depends on two decisions not yet made — which model,
and which file format. The arithmetic below brackets it. **Replace all of this with one measurement
as soon as the first solve lands** (§4).

---

## 1. What one Moco solution actually contains

A `MocoSolution` is a table: one row per mesh point, one column per state, control and derivative.

### Reduced 2D model (`gait10dof18musc`) — 10 DOF, 18 muscles

| Group | Count |
|---|---|
| Coordinate values + speeds | 10 + 10 = 20 |
| Muscle states (activation + tendon force, 2 each) | 18 x 2 = 36 |
| Muscle excitations | 18 |
| Exo actuators (hip, knee, ankle) | 3 |
| Reserve actuators | ~10 |
| Implicit-mode derivatives | ~28 |
| Time | 1 |
| **Columns** | **~116** |

At 100 mesh points: **~11,600 numbers per solve.**

### Full 3D model (`Rajagopal2015`) — ~23 DOF, ~80 muscles

Same arithmetic gives **~393 columns**, so **~39,300 numbers per solve.**

---

## 2. Format matters more than model size

| Format | Bytes/number | 2D solve | 3D solve |
|---|---|---|---|
| `.sto` (OpenSim default, **plain text**) | ~20 | 232 KB | 786 KB |
| float64 binary (`.npy`) | 8 | 93 KB | 314 KB |
| float32 binary | 4 | 46 KB | 157 KB |
| compressed (HDF5/npz) | ~2–3 | ~30 KB | ~100 KB |

**OpenSim writes text by default, and text is roughly 8x larger than compressed binary for identical
content.** Converting on write is free and is the single biggest lever here.

---

## 3. Totals at 100,000 solves

| | `.sto` text | float64 | compressed |
|---|---|---|---|
| 2D model | 23 GB | 9 GB | **3 GB** |
| 3D model | 79 GB | 31 GB | **10 GB** |

Add roughly 50% for failed solves, solver logs, per-run metadata and the processed training set.

**So the real bracket is about 5 GB (2D, compressed) to 120 GB (3D, raw text).** The 25–100 GB
figure spans that, but only because neither decision is made yet.

### The planned case

Development runs on the 2D model; only the headline result is reproduced in 3D. So the realistic
expectation is:

- **2D sweep, compressed: ~5 GB**
- **3D headline runs (a few hundred, not 100k): ~1 GB**
- **Under 10 GB total, if written compressed.**

The 100 GB figure is the worst case — full 3D sweep written as raw text — and it is avoidable.

---

## 4. Replace this with a measurement

Everything above is arithmetic from column counts. As soon as Gate A produces one real solution:

```bash
ls -l  <one solution file>          # actual bytes per solve
```

Multiply by the planned sample count. That number beats every estimate on this page, and it takes
ten seconds.

---

## 5. What to actually tell them

Do not lead with a 100 GB figure — it invites a "no" to a problem we can engineer away.

> *"Under 10 GB if I write results compressed, which I intend to. It could reach 100 GB only if I
> ran the full sweep on the detailed model in OpenSim's default text format, and I would convert to
> compressed binary before that becomes an issue. I mainly want to know the quota so I can size the
> run to it rather than discover the limit partway through."*

That is accurate, shows the problem is understood rather than dumped on them, and makes the question
easy to answer.

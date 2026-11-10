"""J4/K2: whole-block train/val/test splits, the leakage self-check, and ALLOWED.

    python src/exogait/split.py        # every participant in data/processed/exogait; a few seconds

Writes, in data/processed/exogait/:
    splits.csv         one row per stride: participant, stride, block, split
    split_counts.csv   one row per participant x mode x controller: blocks and strides per split, personalised

Rule, per participant x mode x controller, on whole blocks in time order (a block is one
continuous pass of one condition, preprocess.py): the last blocks go to test until they hold SHARE
of the condition's strides, the ones before them to val the same way, the rest to train. Never
random strides: neighbouring strides are near copies, and left and right strides overlap in time.
    3+ blocks  train / val / test (three blocks, the usual case: one each)
    2 blocks   train / test. No val block: tuning uses the val blocks of the participant's other conditions
    1 block    train only, personalised = False: no personalised test, and out of the H1 pairs
    no stride  listed with zeros and personalised = False
Population folds are leave-one-participant-out and need no column. The fold for P trains on the
others' train blocks, tunes on their val blocks and scores P's test blocks, the strides P's
personalised model is scored on, so H1 is paired (evaluate.py). val is for tuning only.
Limit, to state with H1: a test block is a later pass of the same session and donning, not another day.

ALLOWED is what a model may see. Column by column, with reasons: docs/model_inputs.md.
"""

import numpy as np
import pandas as pd

from preprocess import CONTROLLERS, MODES, OUT

SHARE = 0.2
CELL = ["participant", "mode", "controller"]
ALLOWED = ["hip_q", "knee_q", "hip_qd", "knee_qd", "hip_q_other", "knee_q_other", "hip_qd_other", "knee_qd_other",
           "backpack_q", "backpack_qd",          # measured motion: the stride leg, the other leg, the backpack
           "phase", "gait_state", "stance_alpha",   # phase and what encodes it: offline (J1 Q4, Q11); H2's no-phase arm drops all three
           "mode",                               # H3. The true label: a deployed controller needs mode recognition
           "controller", "leg", "group"]         # which controller ran (J1 Q2), which leg, which site and device (J1 Q12)
TARGETS = {"motor": ["hip_tau", "knee_tau"], "gauge": ["hip_tau_gauge", "knee_tau_gauge"]}   # J1 Q9: both, reported apart


def assign(sizes):
    """The split of each block of one condition, in time order, from its stride counts."""
    n, i = len(sizes), len(sizes)
    lab = ["train"] * n
    for name, spare in ((("test", 2), ("val", 1)) if n > 2 else (("test", 1),)):   # spare: blocks the earlier splits still need
        got = 0
        while i > spare and got < SHARE * sum(sizes):
            i -= 1
            lab[i] = name
            got += sizes[i]
    return lab


def split(feats):
    """(splits, counts) from the stride features of every participant."""
    blocks = feats.groupby(CELL + ["block"]).size().rename("strides").reset_index()   # block numbers are in time order
    blocks["split"] = np.concatenate([assign(g.strides.tolist()) for _, g in blocks.groupby(CELL)])
    splits = feats[["participant", "stride", "block"]].merge(blocks[["participant", "block", "split"]], on=["participant", "block"])
    counts = blocks.pivot_table(index=CELL, columns="split", values="strides", aggfunc=["count", "sum"], fill_value=0)
    counts.columns = [f"{'blocks' if a == 'count' else 'strides'}_{b}" for a, b in counts.columns]
    every = pd.MultiIndex.from_product([sorted(feats.participant.unique()), MODES.values(), CONTROLLERS.values()], names=CELL)
    counts = counts.reindex(index=every, columns=[f"{a}_{b}" for a in ("blocks", "strides") for b in ("train", "val", "test")],
                            fill_value=0)
    counts["personalised"] = counts.blocks_test > 0
    return splits, counts.reset_index()


def check(feats, splits, counts):
    assert len(splits) == len(feats) and not splits.duplicated(["participant", "stride"]).any()
    assert (splits.groupby(["participant", "block"]).split.nunique() == 1).all(), "a block is in two splits"
    f = feats.merge(splits, on=["participant", "stride", "block"])
    for p, g in f.groupby("participant"):   # no test stride shares raw rows with a train or val stride, on either leg.
        a, b = g[g.split == "test"], g[g.split != "test"]   # Rows, not t: five files restart their clock (preprocess.py)
        clash = (a.row_start.to_numpy()[:, None] < b.row_end.to_numpy()) & (a.row_end.to_numpy()[:, None] > b.row_start.to_numpy())
        assert not clash.any(), f"{p}: {clash.sum()} test strides overlap train or val strides"
    ok = (counts.blocks_train > 0) & (counts.blocks_test > 0)
    assert (ok | ~counts.personalised).all() and (ok == counts.personalised).all()
    assert assign([10, 10, 10]) == ["train", "val", "test"] and assign([9, 1]) == ["train", "test"] and assign([7]) == ["train"]
    assert assign([5] * 5) == ["train"] * 3 + ["val", "test"] and assign([10, 10, 10, 1]) == ["train", "val", "test", "test"]


if __name__ == "__main__":
    feats = pd.concat((pd.read_csv(f) for f in sorted(OUT.glob("*_stride_features.csv"))), ignore_index=True)
    splits, counts = split(feats)
    check(feats, splits, counts)
    splits.to_csv(OUT / "splits.csv", index=False)
    counts.to_csv(OUT / "split_counts.csv", index=False)
    share = splits.split.value_counts(normalize=True).round(3).to_dict()
    lone = counts[~counts.personalised]
    print(f"{feats.participant.nunique()} participants, {len(splits)} strides: {share}")
    print(f"conditions without a val block: {int(((counts.blocks_val == 0) & counts.personalised).sum())}; "
          f"without a personalised test: {len(lone)} of {len(counts)}:\n{lone.to_string(index=False)}")
    print("test strides per participant x mode x controller, median over participants:\n"
          + counts.pivot_table(index="mode", columns="controller", values="strides_test", aggfunc="median").to_string())
    print("OK: every block is in exactly one split; no test stride shares raw rows with a train or val stride; every "
          "condition has a train and a test block or is listed as not personalised")

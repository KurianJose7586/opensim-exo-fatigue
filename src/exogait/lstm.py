"""K3: an LSTM over the 101-point stride, with fit/predict, so evaluate.py runs it like the sklearn models.

    python src/exogait/lstm.py       # self-check: a toy sequence, a few seconds, CPU or GPU

Unidirectional: the torque at a phase point is predicted from the stride up to that point. The
inputs are evaluate.features() of the stride rows, standardised with the training rows' mean and
SD (the two torques too). One net per fit: LSTM(HIDDEN, LAYERS) and a linear layer to hip and knee.
    fit(d, y, val=(d_val, y_val))  trains up to MAX_EPOCHS and keeps the epoch with the lowest val
                                   loss (PATIENCE epochs without a gain end it). .epochs says which
    fit(d, y, epochs=n)            trains exactly n epochs: the final refit on train + val
    fit(..., base=model)           starts from another fitted Lstm, weights and scaling: fine-tuning.
                                   This is the personalised LSTM: the participant's leave-one-out
                                   population model, fine-tuned on the participant's own blocks (from
                                   scratch there are about 30 walking strides per leg and controller).
                                   So H1 for the LSTM is that model before and after fine-tuning, on
                                   the same strides. Epoch 0 is a candidate: fine-tuning may not help
No no_phase arm (SKIP): a stride that always starts at heel strike and has 101 points tells an LSTM
its phase by position, so dropping the phase columns removes nothing. H2 runs on the per-row models.
"""

import copy

import numpy as np
import torch
from torch import nn

HIDDEN, LAYERS = 64, 2   # no dropout between the layers: with it, cuDNN crashes Python on exit here (torch 2.14.1+cu126, Windows)
BATCH, LR, LR_FINE = 64, 3e-3, 3e-4   # strides per batch; Adam's step from scratch and when fine-tuning
MAX_EPOCHS, PATIENCE = 600, 40
# HIDDEN and LR from a grid on the val blocks (64 or 128; 1e-3 or 3e-3; three folds, population, gauge torque): the four
# land within 0.1 Nm of each other (3.40-3.50 on the stopping rows), so the fastest is used: 120-134 epochs, 23 s a fit
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class Net(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.lstm = nn.LSTM(n_in, HIDDEN, LAYERS, batch_first=True)
        self.out = nn.Linear(HIDDEN, 2)

    def forward(self, x):
        self.lstm.flatten_parameters()   # a deep copy (fine-tuning, the best epoch) leaves the weights scattered
        return self.out(self.lstm(x)[0])


class Lstm:
    SKIP, ITERATIVE = ("no_phase",), True

    def __init__(self, cols, n=None, to_x=None):
        if to_x is None:
            from evaluate import features   # here, not at the top: evaluate.py imports this file
            to_x = lambda d: features(d, cols)
        self.to_x = to_x

    def _x(self, d):
        return torch.tensor(((self.to_x(d) - self.mx) / self.sx).reshape(-1, 101, len(self.mx)), dtype=torch.float32, device=DEVICE)

    def _y(self, y):
        return torch.tensor(((y - self.my) / self.sy).reshape(-1, 101, 2), dtype=torch.float32, device=DEVICE)

    def fit(self, d, y, val=None, base=None, epochs=None):
        assert (val is None) != (epochs is None), "give the val rows (early stopping) or the number of epochs, not both"
        torch.manual_seed(0)
        if base is None:
            x = self.to_x(d)
            self.mx, self.sx, self.my, self.sy = x.mean(0), x.std(0) + 1e-6, y.mean(0), y.std(0)
            self.net = Net(x.shape[1]).to(DEVICE)
        else:
            self.mx, self.sx, self.my, self.sy, self.net = base.mx, base.sx, base.my, base.sy, copy.deepcopy(base.net)
        X, Y = self._x(d), self._y(y)
        opt, loss = torch.optim.Adam(self.net.parameters(), lr=LR if base is None else LR_FINE), nn.MSELoss()
        if val is not None:
            Xv, Yv = self._x(val[0]), self._y(val[1])
            best, state, self.epochs = self._loss(Xv, Yv), copy.deepcopy(self.net.state_dict()), 0
        for epoch in range(1, (epochs if val is None else MAX_EPOCHS) + 1):
            self.net.train()
            order = torch.randperm(len(X), device=DEVICE)
            for i in range(0, len(X), BATCH):
                b = order[i:i + BATCH]
                opt.zero_grad()
                loss(self.net(X[b]), Y[b]).backward()
                opt.step()
            if val is not None:
                now = self._loss(Xv, Yv)
                if now < best:
                    best, state, self.epochs = now, copy.deepcopy(self.net.state_dict()), epoch
                elif epoch - self.epochs >= PATIENCE:
                    break
        if val is not None:
            self.net.load_state_dict(state)
        else:
            self.epochs = epochs
        return self

    def _loss(self, X, Y):
        self.net.eval()
        with torch.no_grad():
            return float(nn.functional.mse_loss(self.net(X), Y))

    def predict(self, d):
        self.net.eval()
        with torch.no_grad():
            out = torch.cat([self.net(x) for x in self._x(d).split(1024)])
        return out.reshape(-1, 2).cpu().numpy() * self.sy + self.my


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    make = lambda n: rng.normal(size=(n * 101, 3))
    # the torques depend on the past of the stride, which a per-row model cannot see: a running mean and a lag
    target = lambda x: np.c_[np.cumsum(x[:, 0].reshape(-1, 101), axis=1).ravel() / 10, np.roll(x[:, 1].reshape(-1, 101), 3, axis=1).ravel()]
    xa, xb, xc = make(200), make(60), make(60)
    m = Lstm(None, to_x=lambda x: x).fit(xa, target(xa), val=(xb, target(xb)))
    rmse = lambda model, x: float(np.sqrt(np.mean((model.predict(x) - target(x)) ** 2)))
    spread = float(target(xc).std())
    assert m.predict(xc).shape == (60 * 101, 2) and 0 < m.epochs <= MAX_EPOCHS
    assert rmse(m, xc) < 0.5 * spread, f"the LSTM did not learn the toy sequence: RMSE {rmse(m, xc):.2f} against an SD of {spread:.2f}"
    again = Lstm(None, to_x=lambda x: x).fit(xa, target(xa), epochs=m.epochs)
    assert abs(rmse(again, xc) - rmse(m, xc)) < 0.2 * spread, "the fixed-epoch refit is far from the early-stopped fit"
    fine = Lstm(None, to_x=lambda x: x).fit(xb, target(xb), val=(xc, target(xc)), base=m)
    assert rmse(fine, xc) <= rmse(m, xc) + 1e-9, "fine-tuning made the base model worse on its own val rows (epoch 0 is a candidate)"
    print(f"OK on {DEVICE}: toy RMSE {rmse(m, xc):.3f} (SD {spread:.2f}) after {m.epochs} epochs; a refit for {m.epochs} epochs gives "
          f"{rmse(again, xc):.3f}; fine-tuned from it for {fine.epochs} more: {rmse(fine, xc):.3f}")

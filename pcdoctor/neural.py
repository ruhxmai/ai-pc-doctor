"""Простая нейронная сеть — многослойный перцептрон на numpy (неделя 12).

Архитектура по умолчанию: 20 входов (признаки) → 32 ReLU → 16 ReLU → 8 softmax (неисправности).
Обучение: прямое распространение, функция потерь — перекрёстная энтропия + L2,
обратное распространение ошибки, оптимизатор Adam, мини-батчи, ранняя остановка
по валидационной выборке.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


def relu(z: np.ndarray) -> np.ndarray:
    return np.maximum(z, 0)


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


@dataclass
class History:
    loss: list[float] = field(default_factory=list)
    train_acc: list[float] = field(default_factory=list)
    val_acc: list[float] = field(default_factory=list)
    best_epoch: int = 0


class MLP:
    def __init__(self, sizes: tuple[int, ...] = (20, 32, 16, 8), l2: float = 1e-4, seed: int = 0):
        self.sizes = tuple(sizes)
        self.l2 = l2
        rng = np.random.default_rng(seed)
        # инициализация Хе — подходит для ReLU
        self.W = [rng.normal(0, np.sqrt(2 / n_in), (n_in, n_out)) for n_in, n_out in zip(sizes[:-1], sizes[1:])]
        self.b = [np.zeros(n_out) for n_out in sizes[1:]]

    @property
    def n_params(self) -> int:
        return sum(w.size + b.size for w, b in zip(self.W, self.b))

    # --- прямое и обратное распространение ---

    def forward(self, X: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
        activations = [X]
        a = X
        for i, (w, b) in enumerate(zip(self.W, self.b)):
            z = a @ w + b
            a = softmax(z) if i == len(self.W) - 1 else relu(z)
            activations.append(a)
        return a, activations

    def loss(self, X: np.ndarray, y: np.ndarray) -> float:
        probs, _ = self.forward(X)
        ce = -np.log(probs[np.arange(len(y)), y] + 1e-12).mean()
        return float(ce + 0.5 * self.l2 * sum((w ** 2).sum() for w in self.W))

    def gradients(self, X: np.ndarray, y: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
        probs, acts = self.forward(X)
        n = len(y)
        delta = probs.copy()
        delta[np.arange(n), y] -= 1  # ∂CE/∂z для softmax + перекрёстной энтропии
        delta /= n
        grad_W, grad_b = [None] * len(self.W), [None] * len(self.W)
        for i in reversed(range(len(self.W))):
            grad_W[i] = acts[i].T @ delta + self.l2 * self.W[i]
            grad_b[i] = delta.sum(axis=0)
            if i > 0:
                delta = (delta @ self.W[i].T) * (acts[i] > 0)  # производная ReLU
        return grad_W, grad_b

    # --- обучение ---

    def fit(self, X: np.ndarray, y: np.ndarray, X_val: np.ndarray | None = None, y_val: np.ndarray | None = None,
            epochs: int = 100, batch_size: int = 32, lr: float = 0.005, patience: int = 15,
            seed: int = 0, verbose: bool = False) -> History:
        X = X.astype(float)
        rng = np.random.default_rng(seed)
        params = self.W + self.b
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        beta1, beta2, eps, t = 0.9, 0.999, 1e-8, 0
        history = History()
        best_val, best_params, wait = -1.0, None, 0

        for epoch in range(1, epochs + 1):
            order = rng.permutation(len(y))
            for start in range(0, len(y), batch_size):
                idx = order[start:start + batch_size]
                gW, gb = self.gradients(X[idx], y[idx])
                t += 1
                for k, (p, g) in enumerate(zip(params, gW + gb)):  # Adam
                    m[k] = beta1 * m[k] + (1 - beta1) * g
                    v[k] = beta2 * v[k] + (1 - beta2) * g * g
                    m_hat = m[k] / (1 - beta1 ** t)
                    v_hat = v[k] / (1 - beta2 ** t)
                    p -= lr * m_hat / (np.sqrt(v_hat) + eps)

            history.loss.append(self.loss(X, y))
            history.train_acc.append(float((self.predict(X) == y).mean()))
            if X_val is not None:
                val_acc = float((self.predict(X_val) == y_val).mean())
                history.val_acc.append(val_acc)
                if val_acc > best_val:
                    best_val, wait, history.best_epoch = val_acc, 0, epoch
                    best_params = [p.copy() for p in params]
                else:
                    wait += 1
            if verbose and (epoch % 10 == 0 or epoch == 1):
                val = f"  val_acc={history.val_acc[-1]:.3f}" if history.val_acc else ""
                print(f"  эпоха {epoch:3d}  loss={history.loss[-1]:.4f}  train_acc={history.train_acc[-1]:.3f}{val}")
            if X_val is not None and wait >= patience:
                if verbose:
                    print(f"  ранняя остановка на эпохе {epoch}: точность на валидации не растёт {patience} эпох")
                break

        if best_params is not None:  # восстанавливаем лучшие веса
            for p, best in zip(params, best_params):
                p[...] = best
        return history

    # --- распознавание ---

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.forward(np.atleast_2d(X).astype(float))[0]

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)

    def save(self, path: str | Path) -> None:
        arrays = {f"W{i}": w for i, w in enumerate(self.W)} | {f"b{i}": b for i, b in enumerate(self.b)}
        np.savez(path, sizes=np.array(self.sizes), l2=np.array(self.l2), **arrays)

    @classmethod
    def load(cls, path: str | Path) -> "MLP":
        d = np.load(path)
        model = cls(tuple(int(s) for s in d["sizes"]), float(d["l2"]))
        model.W = [d[f"W{i}"] for i in range(len(model.W))]
        model.b = [d[f"b{i}"] for i in range(len(model.b))]
        return model


def ascii_curve(values: list[float], height: int = 8, width: int = 60, title: str = "") -> str:
    """Простой текстовый график кривой обучения."""
    if not values:
        return ""
    step = max(1, len(values) // width)
    pts = values[::step]
    lo, hi = min(pts), max(pts)
    span = hi - lo or 1
    rows = []
    for level in range(height, -1, -1):
        threshold = lo + span * level / height
        line = "".join("█" if v >= threshold else " " for v in pts)
        rows.append(f"{threshold:6.3f} │{line}")
    rows.append("       └" + "─" * len(pts) + f"  эпохи 1…{len(values)}")
    return (title + "\n" if title else "") + "\n".join(rows)

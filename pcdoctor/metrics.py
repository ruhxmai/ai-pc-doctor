"""Метрики качества классификации (недели 11–12)."""
from __future__ import annotations

from typing import Callable

import numpy as np


def accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float((y_true == y_pred).mean())


def top_k_accuracy(y_true: np.ndarray, proba: np.ndarray, k: int = 3) -> float:
    """Доля примеров, где верный класс входит в k самых вероятных."""
    top = np.argsort(-proba, axis=1)[:, :k]
    return float(np.mean([t in row for t, row in zip(y_true, top)]))


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> np.ndarray:
    """Строки — истинный класс, столбцы — предсказанный."""
    m = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        m[t, p] += 1
    return m


def precision_recall_f1(cm: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tp = np.diag(cm).astype(float)
    predicted = cm.sum(axis=0)
    actual = cm.sum(axis=1)
    precision = np.divide(tp, predicted, out=np.zeros_like(tp), where=predicted > 0)
    recall = np.divide(tp, actual, out=np.zeros_like(tp), where=actual > 0)
    denom = precision + recall
    f1 = np.divide(2 * precision * recall, denom, out=np.zeros_like(tp), where=denom > 0)
    return precision, recall, f1


def classification_report(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> str:
    cm = confusion_matrix(y_true, y_pred, len(labels))
    p, r, f1 = precision_recall_f1(cm)
    support = cm.sum(axis=1)
    width = max(len(l) for l in labels)
    lines = [f"{'класс':<{width}}  precision  recall    f1  support"]
    for i, label in enumerate(labels):
        lines.append(f"{label:<{width}}  {p[i]:9.3f}  {r[i]:6.3f}  {f1[i]:.3f}  {support[i]:7d}")
    lines.append(f"{'macro avg':<{width}}  {p.mean():9.3f}  {r.mean():6.3f}  {f1.mean():.3f}  {support.sum():7d}")
    lines.append(f"{'accuracy':<{width}}  {accuracy(y_true, y_pred):9.3f}")
    return "\n".join(lines)


def format_confusion(cm: np.ndarray, labels: list[str]) -> str:
    short = [l[:6] for l in labels]
    width = max(len(l) for l in labels)
    lines = [" " * (width + 2) + " ".join(f"{s:>6}" for s in short)]
    for label, row in zip(labels, cm):
        lines.append(f"{label:<{width}}  " + " ".join(f"{v:>6}" for v in row))
    return "\n".join(lines)


def cross_validate(make_model: Callable, X: np.ndarray, y: np.ndarray, k: int = 5,
                   seed: int = 0) -> list[float]:
    """k-кратная перекрёстная проверка: accuracy на каждом из k блоков."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    folds = np.array_split(idx, k)
    scores = []
    for i in range(k):
        test = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        model = make_model()
        model.fit(X[train], y[train])
        scores.append(accuracy(y[test], model.predict(X[test])))
    return scores

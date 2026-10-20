"""Вероятностная классификация неисправностей (неделя 11).

* NaiveBayes  — бернуллиевский наивный байесовский классификатор, обучаемый по датасету.
* ExpertBayes — тот же вывод по формуле Байеса, но с вероятностями, заданными экспертом
  в базе знаний (без обучения) — для сравнения «знания эксперта vs данные».
* KNN         — k ближайших соседей по расстоянию Хэмминга (базовая модель для сравнения).

Формула Байеса с предположением о независимости признаков:
    P(F | s1..sn) ∝ P(F) · Π P(si | F)^xi · (1 − P(si | F))^(1−xi)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .knowledge_base import KnowledgeBase


def _softmax_log(log_scores: np.ndarray) -> np.ndarray:
    log_scores = log_scores - log_scores.max(axis=-1, keepdims=True)
    e = np.exp(log_scores)
    return e / e.sum(axis=-1, keepdims=True)


class NaiveBayes:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha  # сглаживание Лапласа
        self.class_prior: np.ndarray | None = None
        self.feature_prob: np.ndarray | None = None  # P(признак = 1 | класс), форма (классы × признаки)

    def fit(self, X: np.ndarray, y: np.ndarray, n_classes: int | None = None) -> "NaiveBayes":
        n_classes = n_classes or int(y.max()) + 1
        counts = np.array([(y == c).sum() for c in range(n_classes)], dtype=float)
        self.class_prior = (counts + self.alpha) / (counts.sum() + self.alpha * n_classes)
        ones = np.array([X[y == c].sum(axis=0) for c in range(n_classes)], dtype=float)
        self.feature_prob = (ones + self.alpha) / (counts[:, None] + 2 * self.alpha)
        return self

    def log_scores(self, X: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
        """mask — какие признаки известны (для частичных наблюдений в диалоге)."""
        X = np.atleast_2d(X).astype(float)
        if mask is None:
            mask = np.ones_like(X)
        mask = np.atleast_2d(mask).astype(float)
        log_p, log_q = np.log(self.feature_prob), np.log(1 - self.feature_prob)
        ll = (X * mask) @ log_p.T + ((1 - X) * mask) @ log_q.T
        return ll + np.log(self.class_prior)

    def predict_proba(self, X: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
        return _softmax_log(self.log_scores(X, mask))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)

    def posterior(self, observed: dict[int, int]) -> np.ndarray:
        """Апостериорные вероятности классов по частично известным признакам {индекс: 0/1}."""
        n = self.feature_prob.shape[1]
        x, mask = np.zeros(n), np.zeros(n)
        for i, v in observed.items():
            x[i], mask[i] = v, 1
        return self.predict_proba(x, mask)[0]

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({
            "alpha": self.alpha,
            "class_prior": self.class_prior.tolist(),
            "feature_prob": self.feature_prob.tolist(),
        }, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "NaiveBayes":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        m = cls(d["alpha"])
        m.class_prior = np.array(d["class_prior"])
        m.feature_prob = np.array(d["feature_prob"])
        return m


class ExpertBayes(NaiveBayes):
    """Байесовский классификатор на вероятностях из базы знаний — обучение не требуется."""

    def __init__(self, kb: KnowledgeBase):
        super().__init__()
        self.kb = kb
        priors = np.array([kb.faults[f].prior for f in kb.fault_ids])
        self.class_prior = priors / priors.sum()
        self.feature_prob = np.array([[kb.p_symptom(f, s) for s in kb.symptom_ids] for f in kb.fault_ids])

    def fit(self, X, y, n_classes=None) -> "ExpertBayes":
        return self


class KNN:
    def __init__(self, k: int = 7):
        self.k = k

    def fit(self, X: np.ndarray, y: np.ndarray) -> "KNN":
        self.X, self.y = X.astype(np.int8), y
        self.n_classes = int(y.max()) + 1
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X).astype(np.int8)
        dist = (X[:, None, :] != self.X[None, :, :]).sum(axis=2)  # расстояние Хэмминга
        nearest = np.argsort(dist, axis=1, kind="stable")[:, :self.k]
        proba = np.zeros((len(X), self.n_classes))
        for i, idx in enumerate(nearest):
            for c in self.y[idx]:
                proba[i, c] += 1
        return proba / self.k

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.predict_proba(X).argmax(axis=1)

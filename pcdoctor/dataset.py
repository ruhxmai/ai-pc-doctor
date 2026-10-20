"""Создание датасета для обучения моделей (неделя 11).

Каждый пример — «обращение пользователя»: бинарный вектор из 20 признаков
(1 — признак наблюдается) и метка неисправности. Примеры генерируются из базы
знаний: класс выбирается с вероятностью prior, каждый признак появляется
с вероятностью P(признак | неисправность). Так моделируется неполнота и
зашумлённость описаний реальных пользователей.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .knowledge_base import DATA_DIR, KnowledgeBase

DATASET_PATH = DATA_DIR / "dataset.csv"


def generate(kb: KnowledgeBase, n_samples: int = 2000, seed: int = 42,
             min_symptoms: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Возвращает X (n × признаков, 0/1) и y (индексы неисправностей в kb.fault_ids)."""
    rng = np.random.default_rng(seed)
    faults, symptoms = kb.fault_ids, kb.symptom_ids
    priors = np.array([kb.faults[f].prior for f in faults])
    priors /= priors.sum()
    probs = np.array([[kb.p_symptom(f, s) for s in symptoms] for f in faults])

    X = np.zeros((n_samples, len(symptoms)), dtype=np.int8)
    y = rng.choice(len(faults), size=n_samples, p=priors)
    for i, cls in enumerate(y):
        while True:  # пользователь сообщает хотя бы min_symptoms признаков
            row = (rng.random(len(symptoms)) < probs[cls]).astype(np.int8)
            if row.sum() >= min_symptoms:
                break
        X[i] = row
    return X, y


def save_csv(X: np.ndarray, y: np.ndarray, kb: KnowledgeBase, path: str | Path = DATASET_PATH) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(kb.symptom_ids + ["fault"])
        for row, cls in zip(X, y):
            writer.writerow([*row.tolist(), kb.fault_ids[cls]])


def load_csv(kb: KnowledgeBase, path: str | Path = DATASET_PATH) -> tuple[np.ndarray, np.ndarray]:
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if header[:-1] != kb.symptom_ids:
            raise ValueError("Столбцы датасета не совпадают с признаками базы знаний")
        rows = list(reader)
    X = np.array([[int(v) for v in r[:-1]] for r in rows], dtype=np.int8)
    y = np.array([kb.fault_ids.index(r[-1]) for r in rows])
    return X, y


def train_test_split(X: np.ndarray, y: np.ndarray, test_size: float = 0.25,
                     seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Стратифицированное разбиение: доля каждого класса в обучающей и тестовой выборке одинакова."""
    rng = np.random.default_rng(seed)
    test_idx = []
    for cls in np.unique(y):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        test_idx.extend(idx[:int(round(len(idx) * test_size))])
    test_mask = np.zeros(len(y), dtype=bool)
    test_mask[test_idx] = True
    return X[~test_mask], X[test_mask], y[~test_mask], y[test_mask]


def describe(X: np.ndarray, y: np.ndarray, kb: KnowledgeBase) -> str:
    lines = [f"Примеров: {len(y)}, признаков: {X.shape[1]}, классов: {len(kb.fault_ids)}",
             f"Среднее число признаков в примере: {X.sum(axis=1).mean():.2f}",
             "Распределение классов:"]
    for i, f in enumerate(kb.fault_ids):
        n = int((y == i).sum())
        lines.append(f"  {kb.faults[f].name:<36} {n:>5}  {'█' * (n // 15)}")
    return "\n".join(lines)

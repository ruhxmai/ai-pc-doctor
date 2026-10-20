"""Неделя 12. Простая нейронная сеть: обучение, распознавание, оценка точности."""
import _setup  # noqa: F401

import numpy as np

from pcdoctor import dataset, metrics
from pcdoctor.classifier import NaiveBayes
from pcdoctor.knowledge_base import MODELS_DIR, KnowledgeBase
from pcdoctor.neural import MLP, ascii_curve

kb = KnowledgeBase.load()
labels = [kb.faults[f].name for f in kb.fault_ids]

X, y = dataset.load_csv(kb)
X_train, X_test, y_train, y_test = dataset.train_test_split(X, y, test_size=0.25)
X_tr, X_val, y_tr, y_val = dataset.train_test_split(X_train, y_train, test_size=0.2, seed=1)
print(f"Обучение: {len(y_tr)}, валидация: {len(y_val)}, тест: {len(y_test)}")

net = MLP((20, 32, 16, 8), l2=1e-3, seed=0)
print(f"Архитектура: {' → '.join(map(str, net.sizes))}, параметров: {net.n_params}\n")
history = net.fit(X_tr, y_tr, X_val, y_val, epochs=150, batch_size=32, lr=0.003, patience=20, verbose=True)
print(f"Лучшая эпоха по валидации: {history.best_epoch}")
MODELS_DIR.mkdir(exist_ok=True)
net.save(MODELS_DIR / "mlp.npz")

print()
print(ascii_curve(history.loss, title="Функция потерь (обучающая выборка)"))
print()
print(ascii_curve(history.val_acc, title="Точность на валидации"))

print("\n=== Оценка точности на тестовой выборке ===")
pred = net.predict(X_test)
print(metrics.classification_report(y_test, pred, labels))
print(f"Top-3 accuracy: {metrics.top_k_accuracy(y_test, net.predict_proba(X_test), 3):.3f}")
nb = NaiveBayes().fit(X_train, y_train, len(labels))
print(f"\nСравнение: нейросеть {metrics.accuracy(y_test, pred):.3f}  vs  "
      f"наивный Байес {metrics.accuracy(y_test, nb.predict(X_test)):.3f}")

print("\n=== Распознавание новых случаев ===")
cases = [
    ["no_power", "fans_not_spin"],
    ["artifacts_screen", "games_crash", "loud_fan"],
    ["popups_ads", "slow_work", "high_cpu_idle"],
    ["boot_failure", "after_update"],
    ["random_reboots", "high_temp"],
]
for case in cases:
    x = np.array([[1 if s in case else 0 for s in kb.symptom_ids]])
    proba = net.predict_proba(x)[0]
    top = np.argsort(-proba)[:2]
    print("  " + " + ".join(kb.symptoms[s].name for s in case))
    print("     → " + ";  ".join(f"{labels[i]} ({proba[i]:.0%})" for i in top))

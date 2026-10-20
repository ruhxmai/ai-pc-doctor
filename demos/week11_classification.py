"""Неделя 11. Датасет, обучение модели классификации, оценка результатов."""
import _setup  # noqa: F401

import numpy as np

from pcdoctor import dataset, metrics
from pcdoctor.classifier import KNN, ExpertBayes, NaiveBayes
from pcdoctor.knowledge_base import MODELS_DIR, ROOT_DIR, KnowledgeBase

kb = KnowledgeBase.load()
labels = [kb.faults[f].name for f in kb.fault_ids]

print("=== 1. Создание датасета ===")
X, y = dataset.generate(kb, n_samples=2000, seed=42)
dataset.save_csv(X, y, kb)
print(dataset.describe(X, y, kb))
print(f"Сохранён: {dataset.DATASET_PATH.relative_to(ROOT_DIR)}")

X_train, X_test, y_train, y_test = dataset.train_test_split(X, y, test_size=0.25)
print(f"\nОбучающая выборка: {len(y_train)}, тестовая: {len(y_test)}")

print("\n=== 2. Обучение: наивный байесовский классификатор ===")
nb = NaiveBayes(alpha=1.0).fit(X_train, y_train, n_classes=len(labels))
MODELS_DIR.mkdir(exist_ok=True)
nb.save(MODELS_DIR / "naive_bayes.json")
print("Выученные P(признак | неисправность) для «Неисправность блока питания» (топ-4):")
row = nb.feature_prob[kb.fault_ids.index("psu_failure")]
for i in np.argsort(-row)[:4]:
    print(f"  {kb.symptoms[kb.symptom_ids[i]].name:<36} {row[i]:.2f}"
          f"   (эксперт: {kb.p_symptom('psu_failure', kb.symptom_ids[i]):.2f})")

print("\n=== 3. Оценка на тестовой выборке ===")
pred = nb.predict(X_test)
print(metrics.classification_report(y_test, pred, labels))
print(f"Top-3 accuracy: {metrics.top_k_accuracy(y_test, nb.predict_proba(X_test), 3):.3f}")
print("\nМатрица ошибок (строки — истина, столбцы — прогноз):")
print(metrics.format_confusion(metrics.confusion_matrix(y_test, pred, len(labels)), kb.fault_ids))

print("\n=== 4. Сравнение моделей (5-кратная перекрёстная проверка) ===")
models = {
    "Наивный Байес (обучен на данных)": lambda: NaiveBayes(),
    "Байес на вероятностях эксперта": lambda: ExpertBayes(kb),
    "k ближайших соседей, k=7": lambda: KNN(7),
}
for name, make in models.items():
    scores = metrics.cross_validate(make, X, y, k=5)
    print(f"  {name:<34} accuracy = {np.mean(scores):.3f} ± {np.std(scores):.3f}")

print("\n=== 5. Пример: апостериорные вероятности по частичному описанию ===")
observed = {kb.symptom_ids.index("bsod"): 1, kb.symptom_ids.index("beeps"): 1,
            kb.symptom_ids.index("artifacts_screen"): 0}
print("Известно: синий экран — да, писк — да, артефакты — нет; остальное неизвестно")
post = nb.posterior(observed)
for i in np.argsort(-post)[:3]:
    print(f"  P({labels[i]}) = {post[i]:.3f}")

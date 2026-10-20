"""Неделя 7. Продукционная система и прямой вывод."""
import _setup  # noqa: F401

from pcdoctor.knowledge_base import KnowledgeBase
from pcdoctor.production import ProductionSystem

kb = KnowledgeBase.load()
ps = ProductionSystem.load()
print(f"База правил: {len(ps.rules)} продукций, стратегия разрешения конфликтов: {ps.strategy}\n")
for r in ps.rules[:4]:
    print("  ", r)
print("   ...")

symptoms = ["no_power", "burning_smell", "fans_not_spin"]
print("\nИсходные факты:", ", ".join(kb.symptoms[s].name for s in symptoms))
result = ps.run(symptoms)
print("\n--- Трассировка прямого вывода ---")
print(result.trace())
print("\nДиагнозы:", [kb.faults[d].name for d in result.diagnoses])
print("Советы:", result.advice)

print("\n--- Объяснение: как получен diag:psu_failure ---")
for f in result.why("diag:psu_failure"):
    print(f"  {f.rule}")

print("\n--- Многоуровневый вывод: два диагноза одновременно ---")
result = ps.run(["clicking_sound", "files_corrupted", "popups_ads"])
print("Диагнозы:", [kb.faults[d].name for d in result.diagnoses])
print("Факты в рабочей памяти:", ", ".join(result.memory))

print("\n--- Недостаточно данных ---")
result = ps.run(["loud_fan"])
print(result.trace())

print("\n--- Сравнение стратегий разрешения конфликтов (порядок срабатывания) ---")
for strategy in ("priority", "order", "recency"):
    r = ProductionSystem.load(strategy=strategy).run(["high_temp", "random_reboots", "burning_smell"])
    print(f"  {strategy:<9}: {' → '.join(f.rule.id for f in r.firings)}")

"""Неделя 5. Логическая модель знаний: факты, правила, логический вывод."""
import _setup  # noqa: F401

from pcdoctor.knowledge_base import DATA_DIR
from pcdoctor.logic import LogicEngine

engine = LogicEngine()
engine.consult_file(DATA_DIR / "logic_kb.pl")
print("База:", engine.stats())


def show(query: str) -> None:
    answers = engine.ask(query)
    if not answers:
        print(f"?- {query}\n   нет")
    elif answers == [{}]:
        print(f"?- {query}\n   да")
    else:
        print(f"?- {query}")
        for a in answers:
            print("   " + ", ".join(f"{k} = {v}" for k, v in a.items()))


print("\n--- Запросы к иерархии ---")
show("kind_of(hdd, device)")
show("kind_of(hdd, X)")
show("inside(cpu, X)")
show("inside(X, system_unit)")

print("\n--- Классификация неисправностей ---")
show("hardware_fault(F)")
show("software_fault(F)")

print("\n--- Диагностика: пользователь сообщил признаки ---")
for s in ("no_power", "fans_not_spin", "clicking_sound", "files_corrupted"):
    engine.add_fact(f"symptom({s})")
    print(f"   факт: symptom({s})")
show("diagnosis(F)")
show("needs_service(F)")
show("urgent(F)")

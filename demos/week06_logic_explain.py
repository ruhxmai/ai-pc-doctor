"""Неделя 6. Логический вывод с AND, OR, NOT и объяснением результата."""
import _setup  # noqa: F401

from pcdoctor.explanation import explain_proof, why_not
from pcdoctor.knowledge_base import DATA_DIR, KnowledgeBase
from pcdoctor.logic import LogicEngine

kb = KnowledgeBase.load()


def case(title: str, symptoms: list[str]) -> LogicEngine:
    engine = LogicEngine()
    engine.consult_file(DATA_DIR / "logic_kb.pl")
    for s in symptoms:
        engine.add_fact(f"symptom({s})")
    print("=" * 78)
    print(title)
    print("Признаки:", ", ".join(kb.symptoms[s].name for s in symptoms))
    answers = engine.ask("diagnosis(F)")
    print("Диагнозы:", ", ".join(kb.faults[a["F"]].name for a in answers) or "нет")
    for a in answers:
        print("\nКАК получен вывод:")
        print(explain_proof(engine.prove(f"diagnosis({a['F']})"), kb.name_of))
    return engine


# 1. OR: не включается + запах гари (вместо «вентиляторы не крутятся»)
e = case("Случай 1 — ИЛИ", ["no_power", "burning_smell"])
print("\nurgent?", e.ask("urgent(psu_failure)") != [])

# 2. NOT: артефакты на экране, но ПОСЛЕ обновления → не видеокарта, а драйвер
e = case("Случай 2 — НЕ", ["artifacts_screen", "after_update"])
print("\nПОЧЕМУ НЕТ:")
print(why_not(e, "diagnosis(gpu_failure)", kb.name_of))

# 3. Несколько диагнозов + следствия
e = case("Случай 3 — следствия диагноза", ["boot_failure", "popups_ads"])
print("\nНужна резервная копия?", "да" if e.ask("backup_data") else "нет")
print("Можно исправить самому:", [a["F"] for a in e.ask("self_repair(F)")])

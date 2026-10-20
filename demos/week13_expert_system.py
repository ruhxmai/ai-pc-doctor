"""Неделя 13. Экспертная система: база знаний + правила + механизм вывода.

Без аргументов — демонстрация; с флагом -i — консультация в диалоге с пользователем.
"""
import sys

import _setup  # noqa: F401

from pcdoctor.expert_system import ExpertSystem, format_report

es = ExpertSystem(verbose=True)
kb = es.kb

if "-i" in sys.argv:
    print("Консультация. Отвечайте: да / нет / не знаю / почему\n")
    print(format_report(es.consult(), kb))
    sys.exit()

print("=" * 80)
print("СЛУЧАЙ 1. Все признаки известны сразу")
print("=" * 80)
print(format_report(es.diagnose(["clicking_sound", "files_corrupted", "slow_work"]), kb))

print("\n" + "=" * 80)
print("СЛУЧАЙ 2. Опасная ситуация")
print("=" * 80)
print(format_report(es.diagnose(["no_power", "burning_smell"]), kb, details=False))

print("\n" + "=" * 80)
print("СЛУЧАЙ 3. Консультация: система сама задаёт вопросы")
print("Виртуальный пользователь: на самом деле перегрев процессора; отвечает «да»,")
print("если P(признак | перегрев) ≥ 0.5. На первый вопрос спрашивает «почему».")
print("=" * 80)
truth = "overheating"
asked = []


def virtual_user(question: str) -> str:
    symptom = next(s for s in kb.symptom_ids if kb.symptoms[s].question in question)
    if not asked or asked[-1] != symptom:
        asked.append(symptom)
        if len(asked) == 1:
            print(f"? {question}почему")
            return "почему"
    answer = "да" if kb.p_symptom(truth, symptom) >= 0.5 else "нет"
    print(f"? {question}{answer}")
    return answer


diag = es.consult(ask=virtual_user, present=["random_reboots"])
print(f"\nЗадано вопросов: {len(asked)}\n")
print(format_report(diag, kb, details=False))

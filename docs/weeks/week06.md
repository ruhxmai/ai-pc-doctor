# Неделя 6. AND, OR, NOT и объяснение вывода

## Задание
Расширить логический вывод. Добавить AND, OR, NOT. Реализовать объяснение полученного результата.

## Логические связки
| Связка | Запись | Семантика |
|---|---|---|
| И (AND) | `a, b` или `a and b` | должны выполниться все условия |
| ИЛИ (OR) | `a ; b` или `a or b` | достаточно одной альтернативы (перебор с возвратом) |
| НЕ (NOT) | `not a` или `\+ a` | **отрицание как неудача**: истинно, если `a` не выводится (гипотеза замкнутого мира) |

Приоритет: `not` > `,` > `;`, скобки меняют порядок. Разбор — рекурсивным спуском
(`Parser.body / and_expr / unary` в `pcdoctor/logic.py`).

Пример правил ([`data/logic_kb.pl`](../../data/logic_kb.pl)):
```prolog
diagnosis(psu_failure) :- symptom(no_power), (symptom(fans_not_spin) ; symptom(burning_smell)).
diagnosis(gpu_failure) :- symptom(artifacts_screen), not symptom(after_update).
diagnosis(malware)     :- symptom(popups_ads) ; (symptom(high_cpu_idle), symptom(slow_work)).
backup_data            :- diagnosis(disk_failure) ; diagnosis(malware) ; diagnosis(os_corruption).
self_repair(F)         :- diagnosis(F), not hardware_fault(F).
```

## Объяснение — `pcdoctor/explanation.py`
* **«Как?»** (`explain_proof`) — дерево доказательства: правило, факты, выбранная альтернатива ИЛИ,
  невыводимые утверждения для НЕ.
* **«Почему нет?»** (`why_not`) — для каждого правила с подходящей головой отмечается,
  какие условия выполнены (✔), а какие нет (✘) и почему.

```
diagnosis(psu_failure) «Неисправность блока питания» — по правилу R8: ...
├─ symptom(no_power) «Компьютер не включается» — факт
└─ ИЛИ: выполнена альтернатива 2 из 2
   └─ symptom(burning_smell) «Запах гари» — факт

diagnosis(gpu_failure) «Неисправность видеокарты» не выводится:
  правило R14: diagnosis(gpu_failure) :- symptom(artifacts_screen), not symptom(after_update).
    ✔ symptom(artifacts_screen) «Артефакты на экране»
    ✘ НЕ symptom(after_update) — но это утверждение выводится
```

## Запуск
```bash
python demos/week06_logic_explain.py
python -m unittest tests.test_logic
```

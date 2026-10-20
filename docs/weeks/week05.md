# Неделя 5. Логическая модель знаний

## Задание
Создать логическую модель знаний. Записать факты и логические правила. Реализовать логический вывод.

## Модель
Знания записаны на языке логики предикатов первого порядка (подмножество Prolog) — файл
[`data/logic_kb.pl`](../../data/logic_kb.pl).

| Предикат | Смысл | Пример |
|---|---|---|
| `is_a(X, Y)` | X является разновидностью Y | `is_a(hdd, storage).` |
| `part_of(X, Y)` | X входит в состав Y | `part_of(cpu, motherboard).` |
| `affects(F, C)` | неисправность F поражает компонент C | `affects(psu_failure, psu).` |
| `severity(F, L)` | опасность неисправности | `severity(disk_failure, high).` |
| `symptom(S)` | у пользователя наблюдается признак S (добавляется во время работы) | `symptom(no_power).` |

Правила — импликации (хорновские дизъюнкты) `голова :- условие1, условие2.`:
```prolog
kind_of(X, Z) :- is_a(X, Y), kind_of(Y, Z).          % транзитивность «является»
inside(X, Z)  :- part_of(X, Y), inside(Y, Z).         % транзитивность «входит в»
hardware_fault(F) :- affects(F, C), kind_of(C, hardware_component).
diagnosis(psu_failure) :- symptom(no_power), symptom(fans_not_spin).
urgent(F) :- diagnosis(F), severity(F, high).
```

## Механизм вывода — `pcdoctor/logic.py`
- **Парсер** текста базы знаний (лексер + рекурсивный спуск).
- **Унификация** атомов с переменными (`unify`, `walk`).
- **Обратный вывод** (SLD-резолюция, как в Prolog): чтобы доказать цель, ищем факт, совпадающий
  с ней, или правило, голова которого с ней унифицируется, и рекурсивно доказываем условия правила.
- Переменные правил переименовываются при каждом применении, глубина рекурсии ограничена.
- Каждое решение возвращается вместе с **деревом доказательства** — на неделе 6 оно используется для объяснения.

## Пример работы
```
?- inside(cpu, X)
   X = motherboard
   X = system_unit
   X = computer
?- hardware_fault(F)
   F = psu_failure, ram_failure, overheating, disk_failure, gpu_failure
факты: symptom(no_power), symptom(fans_not_spin)
?- diagnosis(F)
   F = psu_failure
?- urgent(F)
   F = psu_failure
```

## Запуск
```bash
python demos/week05_logic.py
python -m unittest tests.test_logic
```

# Неделя 8. Фреймовая модель

## Задание
Создать фреймовую модель. Описать объекты, свойства и связи. Реализовать наследование.

## Модель — [`data/frames.json`](../../data/frames.json) + `pcdoctor/frames.py`
**39 фреймов**: 20 классов-прототипов и 19 экземпляров (конфигурация «Мой компьютер» и 8 неисправностей,
которые строятся автоматически из базы знаний).

```
Сущность (entity)
├── Устройство (device)                   category, warranty_years, status, age_years*, lifetime_left*
│   ├── Компьютер (computer)
│   └── Комплектующее (hardware_component) replaceable, repair
│       ├── Блок питания, Материнская плата, Система охлаждения, Оперативная память
│       ├── Процессор (cpu)  ── is_a также heat_source
│       ├── Видеокарта (gpu) ── is_a также heat_source
│       └── Накопитель (storage) → HDD, SSD
├── Источник тепла (heat_source)          max_temp, temp_unit, current_temp (демон if_added)
├── Программное обеспечение → ОС, Драйвер
└── Неисправность → Аппаратная / Программная      repair_type, needs_service
                                                   * — вычисляется демоном if_needed
```

**Объекты** — фреймы-экземпляры: `cpu_i5_12400`, `hdd_seagate_1tb`, `gpu_rtx_3060`, …
**Свойства** — слоты: `cores`, `max_temp`, `capacity_gb`, `purchase_year`, …
**Связи** — слоты-ссылки на другие фреймы: `part_of` (входит в), `parts`, `for_device`, `component`.

## Наследование
* Значение слота ищется в самом фрейме, затем у родителей по цепочке `is_a`.
* Поддерживается **множественное наследование** (процессор — и комплектующее, и источник тепла).
  Порядок поиска — **C3-линеаризация** (как MRO в Python):
  `cpu_i5_12400 → cpu → hardware_component → device → heat_source → entity`.
* **Переопределение**: `storage.has_moving_parts = false`, но `hdd.has_moving_parts = true`.

## Присоединённые процедуры (демоны)
| Демон | Тип | Слот | Что делает |
|---|---|---|---|
| `compute_age` | if_needed | `age_years` | возраст = текущий год − год покупки |
| `compute_lifetime_left` | if_needed | `lifetime_left` | остаток ресурса = срок службы − возраст |
| `check_temperature` | if_added | `current_temp` | сравнивает с `max_temp`, меняет `status` |

```
current_temp = 104: статус «перегрев». ВНИМАНИЕ: Intel Core i5-12400F: 104 °C > допустимых 100 °C!
hdd_seagate_1tb.lifetime_left = -3   ← device (if_needed)   — ресурс диска исчерпан
```

## Запуск
```bash
python demos/week08_frames.py
python -m unittest tests.test_frames
```

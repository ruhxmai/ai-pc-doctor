"""Фреймовая модель знаний (недели 8–9).

Фрейм — структура «имя + набор слотов». Фреймы-классы (прототипы) задают значения
по умолчанию, фреймы-экземпляры описывают конкретные объекты. Отношение is_a
связывает фрейм с родителями: значение слота, не заданное во фрейме, наследуется
от родителей (поддерживается множественное наследование).

К слотам можно присоединять процедуры-демоны:
  * if_needed — вычисляет значение слота при обращении, если оно не задано;
  * if_added  — вызывается при записи значения в слот (проверка, реакция).
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .knowledge_base import DATA_DIR, KnowledgeBase

FRAMES_PATH = DATA_DIR / "frames.json"

# --- демоны -------------------------------------------------------------------

DEMONS: dict[str, Callable] = {}


def demon(name: str):
    def register(fn: Callable) -> Callable:
        DEMONS[name] = fn
        return fn
    return register


@demon("compute_age")
def compute_age(fs: "FrameSystem", frame: str):
    """if_needed: возраст устройства по году покупки."""
    year = fs.get(frame, "purchase_year")
    return None if year is None else fs.current_year - year


@demon("compute_lifetime_left")
def compute_lifetime_left(fs: "FrameSystem", frame: str):
    """if_needed: оставшийся ресурс = типичный срок службы − возраст."""
    age, lifetime = fs.get(frame, "age_years"), fs.get(frame, "typical_lifetime_years")
    return None if age is None or lifetime is None else lifetime - age


@demon("check_temperature")
def check_temperature(fs: "FrameSystem", frame: str, value):
    """if_added: при записи температуры сравниваем с допустимой и меняем статус."""
    max_temp = fs.get(frame, "max_temp")
    if max_temp is not None and value > max_temp:
        fs.frames[frame].slots["status"] = Slot("перегрев")
        return f"ВНИМАНИЕ: {fs.label(frame)}: {value} °C > допустимых {max_temp} °C — перегрев!"
    if max_temp is not None and value > max_temp - 15:
        fs.frames[frame].slots["status"] = Slot("высокая температура")
        return f"{fs.label(frame)}: {value} °C — близко к пределу ({max_temp} °C)."
    fs.frames[frame].slots["status"] = Slot("исправен")
    return None


# --- структура фрейма ---------------------------------------------------------

@dataclass
class Slot:
    value: Any = None
    if_needed: str | None = None
    if_added: str | None = None


@dataclass
class Frame:
    name: str
    label: str
    kind: str = "class"  # class | instance
    is_a: list[str] = field(default_factory=list)
    slots: dict[str, Slot] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"name": self.name, "label": self.label, "kind": self.kind, "is_a": self.is_a,
             "slots": {k: s.value for k, s in self.slots.items() if s.value is not None}}
        demons = {k: {a: getattr(s, a) for a in ("if_needed", "if_added") if getattr(s, a)}
                  for k, s in self.slots.items() if s.if_needed or s.if_added}
        if demons:
            d["demons"] = demons
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Frame":
        slots = {k: Slot(v) for k, v in d.get("slots", {}).items()}
        for k, facets in d.get("demons", {}).items():
            slot = slots.setdefault(k, Slot())
            slot.if_needed = facets.get("if_needed")
            slot.if_added = facets.get("if_added")
        return cls(d["name"], d.get("label", d["name"]), d.get("kind", "class"),
                   list(d.get("is_a", [])), slots)


class FrameSystem:
    def __init__(self, current_year: int | None = None):
        self.frames: dict[str, Frame] = {}
        self.current_year = current_year or datetime.date.today().year
        self.log: list[str] = []

    # --- загрузка ---

    def add(self, frame: Frame) -> Frame:
        for parent in frame.is_a:
            if parent not in self.frames:
                raise KeyError(f"Фрейм {frame.name}: неизвестный родитель {parent}")
        self.frames[frame.name] = frame
        return frame

    @classmethod
    def load(cls, path: str | Path = FRAMES_PATH, kb: KnowledgeBase | None = None,
             current_year: int | None = None) -> "FrameSystem":
        fs = cls(current_year)
        with open(path, encoding="utf-8") as f:
            for d in json.load(f)["frames"]:
                fs.add(Frame.from_dict(d))
        if kb is not None:
            fs.add_faults(kb)
        return fs

    def add_faults(self, kb: KnowledgeBase) -> None:
        """Фреймы-экземпляры неисправностей строятся из базы знаний."""
        for f in kb.faults.values():
            self.add(Frame(f.id, f.name, "instance", [f"{f.type}_fault"], {
                "component": Slot(f.component),
                "severity": Slot(f.severity_label),
                "symptoms": Slot(list(f.symptoms)),
                "description": Slot(f.description),
                "fix": Slot(f.fix),
                "steps": Slot(list(f.steps)),
            }))

    # --- наследование ---

    def lookup_order(self, name: str) -> list[str]:
        """Порядок поиска слотов — C3-линеаризация (как MRO в Python).

        Потомок всегда раньше предка, родители — в порядке перечисления в is_a,
        общий предок (entity) — после всех своих потомков.
        """
        seqs = [self.lookup_order(p) for p in self.frames[name].is_a] + [list(self.frames[name].is_a)]
        result = [name]
        while True:
            seqs = [s for s in seqs if s]
            if not seqs:
                return result
            for seq in seqs:
                head = seq[0]
                if not any(head in s[1:] for s in seqs):
                    break
            else:
                raise ValueError(f"Противоречивая иерархия наследования у фрейма {name}")
            result.append(head)
            for s in seqs:
                if s[0] == head:
                    del s[0]

    def ancestors(self, name: str) -> list[str]:
        return self.lookup_order(name)[1:]

    def is_a(self, name: str, cls_name: str) -> bool:
        return name == cls_name or cls_name in self.ancestors(name)

    def _find_slot(self, name: str, slot: str) -> tuple[str, Slot] | None:
        for frame_name in self.lookup_order(name):
            s = self.frames[frame_name].slots.get(slot)
            if s is not None and (s.value is not None or s.if_needed):
                return frame_name, s
        return None

    def get(self, name: str, slot: str, default=None):
        """Значение слота: собственное → if_needed-демон → унаследованное от родителей."""
        if name not in self.frames:
            raise KeyError(f"Фрейм {name} не найден")
        found = self._find_slot(name, slot)
        if found is None:
            return default
        _, s = found
        if s.value is not None:
            return s.value
        value = DEMONS[s.if_needed](self, name)
        return default if value is None else value

    def origin(self, name: str, slot: str) -> str | None:
        """Из какого фрейма берётся значение слота."""
        found = self._find_slot(name, slot)
        return found[0] if found else None

    def slot_names(self, name: str) -> list[str]:
        names: list[str] = []
        for frame_name in self.lookup_order(name):
            for s in self.frames[frame_name].slots:
                if s not in names:
                    names.append(s)
        return names

    def all_slots(self, name: str) -> dict[str, tuple[Any, str]]:
        """Все слоты фрейма (собственные и унаследованные): слот → (значение, источник)."""
        result = {}
        for slot in self.slot_names(name):
            value = self.get(name, slot)
            if value is not None:
                src = self.origin(name, slot)
                s = self.frames[src].slots[slot]
                result[slot] = (value, f"{src} (if_needed)" if s.value is None else src)
        return result

    def label(self, name: str) -> str:
        return self.frames[name].label if name in self.frames else name

    def describe(self, name: str) -> str:
        f = self.frames[name]
        kind = "экземпляр" if f.kind == "instance" else "класс"
        lines = [f"Фрейм «{f.label}» ({name}, {kind})",
                 f"  is_a: {', '.join(f.is_a) or '—'}   цепочка наследования: {' → '.join(self.lookup_order(name))}"]
        for slot, (value, src) in self.all_slots(name).items():
            if isinstance(value, list):
                value = ", ".join(map(str, value))
            mark = "" if src == name else f"   ← {src}"
            lines.append(f"  {slot:<22} = {value}{mark}")
        return "\n".join(lines)

    # --- запись значений (используется демонами if_added) ---

    def set(self, name: str, slot: str, value) -> str | None:
        """Записывает значение в собственный слот фрейма и вызывает if_added-демон."""
        if name not in self.frames:
            raise KeyError(f"Фрейм {name} не найден")
        frame = self.frames[name]
        current = frame.slots.get(slot)
        frame.slots[slot] = Slot(value, current.if_needed if current else None,
                                 current.if_added if current else None)
        found = self._find_demon(name, slot, "if_added")
        message = DEMONS[found](self, name, value) if found else None
        if message:
            self.log.append(message)
        return message

    def _find_demon(self, name: str, slot: str, facet: str) -> str | None:
        for frame_name in self.lookup_order(name):
            s = self.frames[frame_name].slots.get(slot)
            if s is not None and getattr(s, facet):
                return getattr(s, facet)
        return None

    # --- неделя 9: поиск и изменение -----------------------------------------

    def instances_of(self, cls_name: str) -> list[str]:
        """Все экземпляры класса, включая экземпляры подклассов."""
        return [n for n, f in self.frames.items() if f.kind == "instance" and self.is_a(n, cls_name)]

    def subclasses(self, cls_name: str) -> list[str]:
        return [n for n, f in self.frames.items() if f.kind == "class" and n != cls_name and self.is_a(n, cls_name)]

    def find(self, conditions: list[tuple[str, str, Any]] | str, cls_name: str | None = None,
             kind: str | None = "instance") -> list[str]:
        """Поиск фреймов по условиям на слоты (с учётом наследования и демонов).

        conditions — список (слот, оператор, значение) или строка «max_temp>90 has_moving_parts=да».
        Операторы: = != > < >= <= ~ (подстрока / элемент списка).
        """
        if isinstance(conditions, str):
            conditions = parse_conditions(conditions)
        result = []
        for name, frame in self.frames.items():
            if kind and frame.kind != kind:
                continue
            if cls_name and not self.is_a(name, cls_name):
                continue
            if all(_compare(self.get(name, slot), op, value) for slot, op, value in conditions):
                result.append(name)
        return result

    def delete_slot(self, name: str, slot: str) -> bool:
        """Удаляет собственное значение слота — после этого снова действует унаследованное."""
        s = self.frames[name].slots.get(slot)
        if s is None or s.value is None:
            return False
        if s.if_needed or s.if_added:
            s.value = None
        else:
            del self.frames[name].slots[slot]
        return True

    def create(self, name: str, parent: str, label: str | None = None, **slots) -> Frame:
        """Создаёт фрейм-экземпляр и заполняет слоты (с вызовом демонов if_added)."""
        if name in self.frames:
            raise ValueError(f"Фрейм {name} уже существует")
        frame = self.add(Frame(name, label or name, "instance", [parent]))
        for slot, value in slots.items():
            self.set(name, slot, value)
        return frame

    def delete(self, name: str) -> None:
        children = [n for n, f in self.frames.items() if name in f.is_a]
        if children:
            raise ValueError(f"Нельзя удалить {name}: от него наследуют {', '.join(children)}")
        del self.frames[name]

    def save(self, path: str | Path) -> None:
        data = {"frames": [f.to_dict() for f in self.frames.values()]}
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_value(text: str):
    """Строка → значение слота: числа, логические значения, списки через запятую."""
    low = text.strip().lower()
    if low in ("true", "да", "yes"):
        return True
    if low in ("false", "нет", "no"):
        return False
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    if "," in text:
        return [parse_value(p) for p in text.split(",") if p.strip()]
    return text.strip()


_OPS = (">=", "<=", "!=", "=", ">", "<", "~")


def parse_conditions(text: str) -> list[tuple[str, str, Any]]:
    conditions = []
    for part in text.split():
        for op in _OPS:
            if op in part:
                slot, value = part.split(op, 1)
                conditions.append((slot, op, parse_value(value)))
                break
        else:
            conditions.append((part, "exists", None))
    return conditions


def _compare(actual, op: str, expected) -> bool:
    if op == "exists":
        return actual is not None
    if actual is None:
        return False
    try:
        if op == "=":
            return actual == expected or str(actual).lower() == str(expected).lower()
        if op == "!=":
            return actual != expected
        if op == "~":
            if isinstance(actual, list):
                return expected in actual
            return str(expected).lower() in str(actual).lower()
        return {">": actual > expected, "<": actual < expected,
                ">=": actual >= expected, "<=": actual <= expected}[op]
    except TypeError:
        return False

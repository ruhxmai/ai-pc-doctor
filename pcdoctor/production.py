"""Продукционная система с прямым выводом (неделя 7).

Продукция: ЕСЛИ <условия> ТО <новые факты>.
Условия: all (И), any (ИЛИ), none (НЕ) над фактами рабочей памяти.

Цикл прямого вывода (распознавание — действие):
  1. сопоставление: найти все применимые правила (конфликтное множество, «агенда»);
  2. разрешение конфликта: выбрать одно правило по стратегии;
  3. срабатывание: добавить факты из части ТО в рабочую память;
  4. повторять, пока есть применимые правила.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .knowledge_base import DATA_DIR

RULES_PATH = DATA_DIR / "production_rules.json"
STRATEGIES = ("priority", "specificity", "recency", "order")


@dataclass
class ProductionRule:
    id: str
    name: str
    then: list[str]
    all: list[str] = field(default_factory=list)
    any: list[str] = field(default_factory=list)
    none: list[str] = field(default_factory=list)
    priority: int = 0
    message: str = ""
    order: int = 0

    def matches(self, wm: "WorkingMemory") -> bool:
        return (all(f in wm for f in self.all)
                and (not self.any or any(f in wm for f in self.any))
                and not any(f in wm for f in self.none))

    @property
    def specificity(self) -> int:
        return len(self.all) + (1 if self.any else 0) + len(self.none)

    def __str__(self) -> str:
        parts = []
        if self.all:
            parts.append(" И ".join(self.all))
        if self.any:
            parts.append("(" + " ИЛИ ".join(self.any) + ")")
        if self.none:
            parts.append(" И ".join(f"НЕ {f}" for f in self.none))
        cond = " И ".join(parts) or "ИСТИНА"
        return f"{self.id}: ЕСЛИ {cond} ТО {', '.join(self.then)}"


class WorkingMemory:
    """Рабочая память: факты с метками времени добавления (для стратегии recency)."""

    def __init__(self, facts=()):
        self._time: dict[str, int] = {}
        self._clock = 0
        for f in facts:
            self.add(f)

    def add(self, fact: str) -> bool:
        if fact in self._time:
            return False
        self._clock += 1
        self._time[fact] = self._clock
        return True

    def __contains__(self, fact: str) -> bool:
        return fact in self._time

    def __iter__(self):
        return iter(self._time)

    def __len__(self) -> int:
        return len(self._time)

    def time_of(self, fact: str) -> int:
        return self._time.get(fact, 0)

    def with_prefix(self, prefix: str) -> list[str]:
        return [f.split(":", 1)[1] for f in self._time if f.startswith(prefix + ":")]


@dataclass
class Firing:
    cycle: int
    rule: ProductionRule
    added: list[str]
    agenda: list[str]  # идентификаторы правил в конфликтном множестве


@dataclass
class InferenceResult:
    memory: WorkingMemory
    firings: list[Firing]

    def facts(self, prefix: str) -> list[str]:
        return self.memory.with_prefix(prefix)

    @property
    def diagnoses(self) -> list[str]:
        return self.facts("diag")

    @property
    def advice(self) -> list[str]:
        return self.facts("advice")

    def trace(self) -> str:
        lines = []
        for f in self.firings:
            lines.append(f"Цикл {f.cycle}. Агенда: {{{', '.join(f.agenda)}}} → срабатывает {f.rule.id} «{f.rule.name}»")
            lines.append(f"   {f.rule}")
            lines.append(f"   + {', '.join(f.added)}   {f.rule.message}")
        return "\n".join(lines)

    def why(self, fact: str) -> list[Firing]:
        """Цепочка срабатываний, которая привела к факту (объяснение «как»)."""
        by_fact = {a: f for f in self.firings for a in f.added}
        chain, stack, seen = [], [fact], set()
        while stack:
            current = stack.pop()
            firing = by_fact.get(current)
            if firing is None or firing.rule.id in seen:
                continue
            seen.add(firing.rule.id)
            chain.append(firing)
            stack.extend(f for f in firing.rule.all + firing.rule.any if f in self.memory)
        return sorted(chain, key=lambda f: f.cycle)


class ProductionSystem:
    def __init__(self, rules: list[ProductionRule], strategy: str = "priority"):
        if strategy not in STRATEGIES:
            raise ValueError(f"Неизвестная стратегия {strategy}, допустимы: {STRATEGIES}")
        self.rules = rules
        self.strategy = strategy

    @classmethod
    def load(cls, path: str | Path = RULES_PATH, strategy: str = "priority") -> "ProductionSystem":
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)["rules"]
        rules = [ProductionRule(order=i, **r) for i, r in enumerate(raw)]
        return cls(rules, strategy)

    def agenda(self, wm: WorkingMemory, fired: set[str]) -> list[ProductionRule]:
        """Конфликтное множество: применимые, ещё не срабатывавшие правила, дающие новые факты."""
        return [r for r in self.rules
                if r.id not in fired and r.matches(wm) and any(t not in wm for t in r.then)]

    def select(self, agenda: list[ProductionRule], wm: WorkingMemory) -> ProductionRule:
        """Разрешение конфликта."""
        if self.strategy == "priority":
            key = lambda r: (-r.priority, -r.specificity, r.order)
        elif self.strategy == "specificity":
            key = lambda r: (-r.specificity, r.order)
        elif self.strategy == "recency":
            key = lambda r: (-max((wm.time_of(f) for f in r.all + r.any), default=0), r.order)
        else:
            key = lambda r: r.order
        return min(agenda, key=key)

    def run(self, facts, max_cycles: int = 200) -> InferenceResult:
        """Прямой вывод от исходных фактов."""
        wm = WorkingMemory(facts)
        fired: set[str] = set()
        firings: list[Firing] = []
        for cycle in range(1, max_cycles + 1):
            agenda = self.agenda(wm, fired)
            if not agenda:
                break
            rule = self.select(agenda, wm)
            fired.add(rule.id)  # рефрактерность: правило срабатывает один раз
            added = [t for t in rule.then if wm.add(t)]
            firings.append(Firing(cycle, rule, added, [r.id for r in agenda]))
        return InferenceResult(wm, firings)

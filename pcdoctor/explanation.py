"""Объяснение результатов логического вывода (неделя 6).

* «Как?»  — дерево доказательства: какие правила и факты привели к выводу.
* «Почему нет?» — какие условия правил не выполнились.
"""
from __future__ import annotations

from typing import Callable

from .logic import And, Atom, LogicEngine, Not, Or, Proof, conjuncts, parse_query, unify

Namer = Callable[[str], str]


def _with_names(text: str, namer: Namer | None) -> str:
    """Добавляет к symptom(x)/diagnosis(x) человекочитаемое название: «Компьютер не включается»."""
    if namer is None:
        return text
    try:
        atom = parse_query(text)
    except SyntaxError:
        return text
    if isinstance(atom, Atom) and len(atom.args) == 1 and atom.pred in ("symptom", "diagnosis"):
        name = namer(atom.args[0])
        if name != atom.args[0]:
            return f"{text}  «{name}»"
    return text


def explain_proof(proof: Proof, namer: Namer | None = None) -> str:
    """Дерево доказательства в текстовом виде."""
    lines: list[str] = []

    def head(p: Proof) -> str:
        if p.kind == "fact":
            return f"{_with_names(p.goal, namer)} — факт"
        if p.kind == "rule":
            return f"{_with_names(p.goal, namer)} — по правилу {p.rule.name}: {p.rule}"
        if p.kind == "not":
            inner = p.goal.removeprefix("НЕ ")
            return f"НЕ {_with_names(inner, namer)} — не выводится (гипотеза замкнутого мира)"
        return p.goal

    def walk(p: Proof, prefix: str, last: bool, root: bool) -> None:
        connector = "" if root else ("└─ " if last else "├─ ")
        lines.append(prefix + connector + head(p))
        children = p.children
        child_prefix = prefix if root else prefix + ("   " if last else "│  ")
        for i, c in enumerate(children):
            walk(c, child_prefix, i == len(children) - 1, False)

    walk(proof, "", True, True)
    return "\n".join(lines)


def why_not(engine: LogicEngine, goal: Atom | str, namer: Namer | None = None) -> str:
    """Объясняет, почему цель НЕ выводится: для каждого правила показывает невыполненные условия."""
    if isinstance(goal, str):
        goal = parse_query(goal)
    if engine.prove(goal) is not None:
        return f"{goal} выводится — объяснение «почему нет» не требуется."
    rules = [r for r in engine.rules.get(goal.pred, []) if unify(goal, r.head, {}) is not None]
    if not rules:
        return f"{goal}: нет ни фактов, ни правил, из которых это следует."
    lines = [f"{_with_names(str(goal), namer)} не выводится:"]
    for rule in rules:
        s = unify(goal, rule.head, {})
        lines.append(f"  правило {rule.name}: {rule}")
        for cond in conjuncts(rule.body):
            cond_s = cond.substitute(s)
            found = next(engine.solve(cond_s, s), None)
            if found is not None:
                s = found[0]
                lines.append(f"    ✔ {_describe(cond_s, namer)}")
            else:
                lines.append(f"    ✘ {_describe(cond_s, namer)}{_reason(cond_s)}")
    return "\n".join(lines)


def _describe(expr, namer: Namer | None) -> str:
    if isinstance(expr, Atom):
        return _with_names(str(expr), namer)
    if isinstance(expr, Not):
        return "НЕ " + _describe(expr.item, namer)
    if isinstance(expr, Or):
        return "ИЛИ(" + " | ".join(_describe(i, namer) for i in expr.items) + ")"
    if isinstance(expr, And):
        return "И(" + ", ".join(_describe(i, namer) for i in expr.items) + ")"
    return str(expr)


def _reason(expr) -> str:
    if isinstance(expr, Not):
        return "  — но это утверждение выводится"
    if isinstance(expr, Or):
        return "  — ни одна альтернатива не выполнена"
    return "  — не установлено"

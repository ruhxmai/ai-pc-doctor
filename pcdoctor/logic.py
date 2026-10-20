"""Логическая модель знаний (недели 5–6).

Знания записываются на подмножестве языка Prolog:

    is_a(hdd, storage).                                  % факт
    kind_of(X, Z) :- is_a(X, Y), kind_of(Y, Z).          % правило (импликация)
    d(gpu) :- s(artifacts), (s(crash) ; s(no_image)), not s(after_update).

Связки: «,» или and — И; «;» или or — ИЛИ; not или \\+ — НЕ.

Переменные начинаются с заглавной буквы или «_», константы — со строчной.
Логический вывод — обратный (от цели к фактам) с унификацией переменных,
как в Prolog (SLD-резолюция).
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

Subst = dict[str, str]


def is_var(term: str) -> bool:
    return term[:1].isupper() or term[:1] == "_"


# --- выражения ---------------------------------------------------------------

@dataclass(frozen=True)
class Atom:
    """Атомарная формула: предикат(аргументы)."""
    pred: str
    args: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.pred}({', '.join(self.args)})" if self.args else self.pred

    def substitute(self, s: Subst) -> "Atom":
        return Atom(self.pred, tuple(walk(a, s) for a in self.args))

    def variables(self) -> list[str]:
        return [a for a in self.args if is_var(a)]


@dataclass(frozen=True)
class And:
    """Конъюнкция условий."""
    items: tuple

    def __str__(self) -> str:
        return ", ".join(str(i) for i in self.items)

    def substitute(self, s: Subst) -> "And":
        return And(tuple(i.substitute(s) for i in self.items))

    def variables(self) -> list[str]:
        return [v for i in self.items for v in i.variables()]


@dataclass(frozen=True)
class Or:
    """Дизъюнкция: достаточно доказать любую из альтернатив."""
    items: tuple

    def __str__(self) -> str:
        return "(" + " ; ".join(str(i) for i in self.items) + ")"

    def substitute(self, s: Subst) -> "Or":
        return Or(tuple(i.substitute(s) for i in self.items))

    def variables(self) -> list[str]:
        return [v for i in self.items for v in i.variables()]


@dataclass(frozen=True)
class Not:
    """Отрицание как неудача (negation as failure): истинно, если цель НЕ выводится.

    Соответствует гипотезе замкнутого мира: всё, что не известно и не выводится, — ложно.
    """
    item: object

    def __str__(self) -> str:
        return f"not {self.item}"

    def substitute(self, s: Subst) -> "Not":
        return Not(self.item.substitute(s))

    def variables(self) -> list[str]:
        return self.item.variables()


def conjuncts(expr) -> list:
    """Список условий верхнего уровня (для объяснения «почему нет»)."""
    return list(expr.items) if isinstance(expr, And) else [expr]


@dataclass(frozen=True)
class Rule:
    head: Atom
    body: object  # Atom | And
    name: str = ""

    def __str__(self) -> str:
        return f"{self.head} :- {self.body}."


@dataclass
class Proof:
    """Узел дерева доказательства (используется для объяснения вывода)."""
    goal: str
    kind: str  # fact | rule | and | or | not
    rule: Rule | None = None
    children: list["Proof"] = field(default_factory=list)


# --- унификация --------------------------------------------------------------

def walk(term: str, s: Subst) -> str:
    while is_var(term) and term in s:
        term = s[term]
    return term


def unify(a: Atom, b: Atom, s: Subst) -> Subst | None:
    if a.pred != b.pred or len(a.args) != len(b.args):
        return None
    s = dict(s)
    for x, y in zip(a.args, b.args):
        x, y = walk(x, s), walk(y, s)
        if x == y:
            continue
        if is_var(x):
            s[x] = y
        elif is_var(y):
            s[y] = x
        else:
            return None
    return s


# --- синтаксический разбор ---------------------------------------------------

TOKEN_RE = re.compile(r"\s*(:-|[(),.;]|\\\+|[A-Za-zА-Яа-яЁё_0-9]+)")


def tokenize(text: str) -> list[str]:
    text = re.sub(r"%[^\n]*", "", text)  # комментарии
    tokens, pos = [], 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise SyntaxError(f"Непонятный символ: {text[pos:pos + 20]!r}")
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


class Parser:
    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        tok = self.peek()
        if tok is None or (expected is not None and tok != expected):
            raise SyntaxError(f"Ожидалось {expected!r}, получено {tok!r}")
        self.pos += 1
        return tok

    def atom(self) -> Atom:
        pred = self.take()
        args = []
        if self.peek() == "(":
            self.take("(")
            args.append(self.take())
            while self.peek() == ",":
                self.take(",")
                args.append(self.take())
            self.take(")")
        return Atom(pred, tuple(args))

    # Грамматика тела правила (по убыванию приоритета: not, AND, OR):
    #   body    := and_expr ( (";" | "or") and_expr )*
    #   and_expr:= unary ( ("," | "and") unary )*
    #   unary   := ("not" | "\+") unary | "(" body ")" | atom
    def body(self):
        items = [self.and_expr()]
        while self.peek() in (";", "or"):
            self.take()
            items.append(self.and_expr())
        return items[0] if len(items) == 1 else Or(tuple(items))

    def and_expr(self):
        items = [self.unary()]
        while self.peek() in (",", "and"):
            self.take()
            items.append(self.unary())
        return items[0] if len(items) == 1 else And(tuple(items))

    def unary(self):
        tok = self.peek()
        if tok in ("not", "\\+"):
            self.take()
            return Not(self.unary())
        if tok == "(":
            self.take("(")
            expr = self.body()
            self.take(")")
            return expr
        return self.atom()

    def clauses(self) -> Iterator[Atom | Rule]:
        while self.peek() is not None:
            head = self.atom()
            if self.peek() == ":-":
                self.take(":-")
                body = self.body()
                self.take(".")
                yield Rule(head, body)
            else:
                self.take(".")
                yield head


def parse_query(text: str):
    p = Parser(text.strip().rstrip("."))
    expr = p.body()
    if p.peek() is not None:
        raise SyntaxError(f"Лишний текст в запросе: {p.peek()!r}")
    return expr


# --- машина логического вывода ----------------------------------------------

class LogicEngine:
    MAX_DEPTH = 64

    def __init__(self):
        self.facts: dict[str, list[Atom]] = {}
        self.rules: dict[str, list[Rule]] = {}
        self._counter = itertools.count(1)
        self._rule_counter = itertools.count(1)

    # --- наполнение базы ---

    def add_fact(self, fact: Atom | str) -> None:
        if isinstance(fact, str):
            fact = parse_query(fact)
        if fact.variables():
            raise ValueError(f"Факт не должен содержать переменных: {fact}")
        bucket = self.facts.setdefault(fact.pred, [])
        if fact not in bucket:
            bucket.append(fact)

    def retract(self, fact: Atom | str) -> None:
        if isinstance(fact, str):
            fact = parse_query(fact)
        bucket = self.facts.get(fact.pred, [])
        if fact in bucket:
            bucket.remove(fact)

    def add_rule(self, rule: Rule) -> None:
        if not rule.name:
            rule = Rule(rule.head, rule.body, f"R{next(self._rule_counter)}")
        self.rules.setdefault(rule.head.pred, []).append(rule)

    def consult(self, text: str) -> None:
        for clause in Parser(text).clauses():
            if isinstance(clause, Rule):
                self.add_rule(clause)
            else:
                self.add_fact(clause)

    def consult_file(self, path: str | Path) -> None:
        self.consult(Path(path).read_text(encoding="utf-8"))

    def stats(self) -> str:
        n_facts = sum(len(v) for v in self.facts.values())
        n_rules = sum(len(v) for v in self.rules.values())
        return f"Фактов: {n_facts}, правил: {n_rules}"

    # --- вывод ---

    def _rename(self, rule: Rule) -> Rule:
        """Переименование переменных правила, чтобы они не пересекались с переменными цели."""
        suffix = f"_{next(self._counter)}"
        s = {v: v + suffix for v in rule.head.variables() + rule.body.variables()}
        return Rule(rule.head.substitute(s), rule.body.substitute(s), rule.name)

    def solve(self, goal, s: Subst | None = None, depth: int = 0) -> Iterator[tuple[Subst, Proof]]:
        """Генератор всех решений цели: пары (подстановка, дерево доказательства)."""
        s = s or {}
        if depth > self.MAX_DEPTH:
            return
        if isinstance(goal, And):
            yield from self._solve_and(list(goal.items), s, depth, [])
        elif isinstance(goal, Or):
            for i, alt in enumerate(goal.items, 1):
                for s1, p in self.solve(alt, s, depth):
                    yield s1, Proof(f"ИЛИ: выполнена альтернатива {i} из {len(goal.items)}", "or",
                                    children=[p])
        elif isinstance(goal, Not):
            inner = goal.item.substitute(s)
            if next(self.solve(inner, s, depth + 1), None) is None:
                yield s, Proof(f"НЕ {inner}", "not")
        elif isinstance(goal, Atom):
            yield from self._solve_atom(goal, s, depth)
        else:
            raise TypeError(f"Неизвестный тип цели: {goal!r}")

    def _solve_and(self, goals: list, s: Subst, depth: int, proofs: list[Proof]):
        if not goals:
            yield s, Proof("И", "and", children=proofs)
            return
        first, rest = goals[0], goals[1:]
        for s1, p1 in self.solve(first, s, depth):
            yield from self._solve_and(rest, s1, depth, proofs + [p1])

    def _solve_atom(self, goal: Atom, s: Subst, depth: int):
        for fact in self.facts.get(goal.pred, []):
            s1 = unify(goal, fact, s)
            if s1 is not None:
                yield s1, Proof(str(fact), "fact")
        for rule in self.rules.get(goal.pred, []):
            r = self._rename(rule)
            s1 = unify(goal, r.head, s)
            if s1 is None:
                continue
            for s2, body_proof in self.solve(r.body, s1, depth + 1):
                children = body_proof.children if body_proof.kind == "and" else [body_proof]
                yield s2, Proof(str(goal.substitute(s2)), "rule", rule, children)

    def ask(self, query) -> list[Subst]:
        """Все ответы на запрос: список подстановок для переменных запроса."""
        if isinstance(query, str):
            query = parse_query(query)
        names = list(dict.fromkeys(query.variables()))
        answers: list[Subst] = []
        for s, _ in self.solve(query):
            answer = {v: walk(v, s) for v in names}
            if answer not in answers:
                answers.append(answer)
        return answers

    def prove(self, query) -> Proof | None:
        """Первое доказательство запроса или None, если он не выводится."""
        if isinstance(query, str):
            query = parse_query(query)
        for _, proof in self.solve(query):
            return proof
        return None

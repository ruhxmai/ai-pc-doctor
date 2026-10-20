"""Семантическая сеть предметной области (недели 4 и 10).

Узлы — понятия (компоненты, неисправности, признаки, способы устранения,
конкретные экземпляры), дуги — именованные отношения между ними.
Неделя 10: поиск связанных объектов, путей, шаблонные запросы, наследование,
распространение активации.
"""
from __future__ import annotations

from dataclasses import dataclass

from .knowledge_base import KnowledgeBase

RELATIONS = {
    "is_a": "является",
    "part_of": "входит в",
    "affects": "поражает",
    "manifests": "проявляется как",
    "fixed_by": "устраняется",
    "instance_of": "экземпляр",
}


@dataclass
class Node:
    id: str
    label: str
    type: str  # component | fault | symptom | fix | class


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str

    def __str__(self) -> str:
        return f"{self.source} —[{RELATIONS.get(self.relation, self.relation)}]→ {self.target}"


class SemanticNetwork:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._out: dict[str, list[Edge]] = {}
        self._in: dict[str, list[Edge]] = {}

    # --- построение ---------------------------------------------------------

    def add_node(self, node_id: str, label: str | None = None, type: str = "concept") -> Node:
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(node_id, label or node_id, type)
            self._out[node_id] = []
            self._in[node_id] = []
        return self.nodes[node_id]

    def add_edge(self, source: str, relation: str, target: str) -> Edge:
        for node_id in (source, target):
            if node_id not in self.nodes:
                raise KeyError(f"Узел {node_id} не найден")
        edge = Edge(source, relation, target)
        if edge not in self._out[source]:
            self.edges.append(edge)
            self._out[source].append(edge)
            self._in[target].append(edge)
        return edge

    # --- простая навигация --------------------------------------------------

    def out_edges(self, node_id: str, relation: str | None = None) -> list[Edge]:
        return [e for e in self._out.get(node_id, []) if relation is None or e.relation == relation]

    def in_edges(self, node_id: str, relation: str | None = None) -> list[Edge]:
        return [e for e in self._in.get(node_id, []) if relation is None or e.relation == relation]

    def neighbors(self, node_id: str) -> list[str]:
        result = [e.target for e in self.out_edges(node_id)] + [e.source for e in self.in_edges(node_id)]
        return list(dict.fromkeys(result))

    def label(self, node_id: str) -> str:
        return self.nodes[node_id].label if node_id in self.nodes else node_id

    def stats(self) -> str:
        by_type: dict[str, int] = {}
        for n in self.nodes.values():
            by_type[n.type] = by_type.get(n.type, 0) + 1
        by_rel: dict[str, int] = {}
        for e in self.edges:
            by_rel[e.relation] = by_rel.get(e.relation, 0) + 1
        types = ", ".join(f"{t}: {c}" for t, c in sorted(by_type.items()))
        rels = ", ".join(f"{RELATIONS.get(r, r)}: {c}" for r, c in sorted(by_rel.items()))
        return f"Узлов: {len(self.nodes)} ({types})\nДуг: {len(self.edges)} ({rels})"

    def to_mermaid(self, relations: set[str] | None = None) -> str:
        """Экспорт в Mermaid (рисуется прямо в README на GitHub)."""
        lines = ["graph LR"]
        used = set()
        for e in self.edges:
            if relations and e.relation not in relations:
                continue
            used.update((e.source, e.target))
            lines.append(f"    {e.source} -->|{RELATIONS.get(e.relation, e.relation)}| {e.target}")
        for node_id in sorted(used):
            lines.insert(1, f'    {node_id}["{self.label(node_id)}"]')
        return "\n".join(lines)

    # --- построение из базы знаний -----------------------------------------

    @classmethod
    def from_knowledge_base(cls, kb: KnowledgeBase) -> "SemanticNetwork":
        net = cls()
        for c in kb.components.values():
            net.add_node(c.id, c.name, "component")
        for c in kb.components.values():
            if c.is_a:
                net.add_edge(c.id, "is_a", c.is_a)
            if c.part_of:
                net.add_edge(c.id, "part_of", c.part_of)
        net.add_node("fault", "Неисправность", "class")
        net.add_node("hardware_fault", "Аппаратная неисправность", "class")
        net.add_node("software_fault", "Программная неисправность", "class")
        net.add_edge("hardware_fault", "is_a", "fault")
        net.add_edge("software_fault", "is_a", "fault")
        for s in kb.symptoms.values():
            net.add_node(s.id, s.name, "symptom")
        for f in kb.faults.values():
            net.add_node(f.id, f.name, "fault")
            net.add_edge(f.id, "is_a", f"{f.type}_fault")
            net.add_edge(f.id, "affects", f.component)
            for sid in f.symptoms:
                net.add_edge(f.id, "manifests", sid)
            fix_id = f"fix_{f.id}"
            net.add_node(fix_id, f.fix, "fix")
            net.add_edge(f.id, "fixed_by", fix_id)
        return net

    def add_frames(self, fs) -> None:
        """Добавляет в сеть экземпляры из фреймовой модели (конкретные комплектующие «Моего компьютера»)."""
        for name, frame in fs.frames.items():
            if frame.kind != "instance" or name in self.nodes:
                continue
            self.add_node(name, frame.label, "instance")
        for name, frame in fs.frames.items():
            if frame.kind != "instance" or self.nodes[name].type != "instance":
                continue
            for parent in frame.is_a:
                self.add_node(parent, fs.label(parent), "component")
                self.add_edge(name, "instance_of", parent)
            container = frame.slots.get("part_of")
            if container is not None and container.value in self.nodes:
                self.add_edge(name, "part_of", container.value)

    # --- неделя 10: поиск связанных объектов ---------------------------------

    def query(self, source: str | None = None, relation: str | None = None,
              target: str | None = None) -> list[Edge]:
        """Поиск по шаблону триплета (None — любое значение): query(None, 'manifests', 'bsod')."""
        if source is not None:
            candidates = self._out.get(source, [])
        elif target is not None:
            candidates = self._in.get(target, [])
        else:
            candidates = self.edges
        return [e for e in candidates
                if (source is None or e.source == source)
                and (relation is None or e.relation == relation)
                and (target is None or e.target == target)]

    def related(self, start: str, depth: int = 2, relations: set[str] | None = None,
                direction: str = "both") -> dict[str, list[Edge]]:
        """Поиск в ширину: все узлы на расстоянии ≤ depth и путь (цепочка дуг) до каждого."""
        if start not in self.nodes:
            raise KeyError(f"Узел {start} не найден")
        paths: dict[str, list[Edge]] = {start: []}
        frontier = [start]
        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for edge, other in self._steps(node, relations, direction):
                    if other not in paths:
                        paths[other] = paths[node] + [edge]
                        next_frontier.append(other)
            frontier = next_frontier
        del paths[start]
        return paths

    def _steps(self, node: str, relations: set[str] | None, direction: str):
        if direction in ("out", "both"):
            for e in self._out[node]:
                if relations is None or e.relation in relations:
                    yield e, e.target
        if direction in ("in", "both"):
            for e in self._in[node]:
                if relations is None or e.relation in relations:
                    yield e, e.source

    def find_path(self, start: str, goal: str, relations: set[str] | None = None) -> list[Edge] | None:
        """Кратчайшая цепочка связей между двумя понятиями (дуги проходятся в обе стороны)."""
        if start == goal:
            return []
        paths = {start: []}
        frontier = [start]
        while frontier:
            next_frontier = []
            for node in frontier:
                for edge, other in self._steps(node, relations, "both"):
                    if other in paths:
                        continue
                    paths[other] = paths[node] + [edge]
                    if other == goal:
                        return paths[other]
                    next_frontier.append(other)
            frontier = next_frontier
        return None

    def generalizations(self, node: str) -> list[str]:
        """Все родовые понятия узла по is_a / instance_of."""
        result, stack = [], [node]
        while stack:
            for e in self.out_edges(stack.pop()):
                if e.relation in ("is_a", "instance_of") and e.target not in result:
                    result.append(e.target)
                    stack.append(e.target)
        return result

    def inherited_edges(self, node: str, relation: str) -> list[tuple[Edge, str]]:
        """Наследование в сети: связи, полученные от родовых понятий (hdd «входит в» системный блок,
        потому что так входит любой накопитель). Возвращает (дуга, от кого унаследована)."""
        result, seen = [], set()
        for origin in [node] + self.generalizations(node):
            for e in self.out_edges(origin, relation):
                if e.target not in seen:
                    seen.add(e.target)
                    result.append((e, origin))
        return result

    def common(self, a: str, b: str, relation: str | None = None) -> list[str]:
        """Общие соседи двух узлов по исходящим дугам (например, общие признаки двух неисправностей)."""
        ta = {e.target for e in self.out_edges(a, relation)}
        return [e.target for e in self.out_edges(b, relation) if e.target in ta]

    def activate(self, seeds: list[str], steps: int = 2, decay: float = 0.5,
                 node_type: str | None = None) -> list[tuple[str, float]]:
        """Распространение активации: от исходных узлов энергия растекается по дугам с затуханием.

        Сильнее всего активируются понятия, связанные сразу с несколькими исходными узлами, —
        так по набору признаков находятся наиболее вероятные неисправности.
        """
        activation = {s: 1.0 for s in seeds if s in self.nodes}
        current = dict(activation)
        for _ in range(steps):
            spread: dict[str, float] = {}
            for node, energy in current.items():
                neighbours = self.neighbors(node)
                if not neighbours:
                    continue
                share = energy * decay / len(neighbours) ** 0.5
                for other in neighbours:
                    spread[other] = spread.get(other, 0.0) + share
            for node, energy in spread.items():
                activation[node] = activation.get(node, 0.0) + energy
            current = spread
        ranking = [(n, a) for n, a in activation.items()
                   if n not in seeds and (node_type is None or self.nodes[n].type == node_type)]
        return sorted(ranking, key=lambda x: -x[1])

    def describe(self, node: str) -> str:
        n = self.nodes[node]
        lines = [f"«{n.label}» ({node}, тип: {n.type})"]
        for e in self.out_edges(node):
            lines.append(f"  → {RELATIONS.get(e.relation, e.relation)}: {self.label(e.target)}")
        for e in self.in_edges(node):
            lines.append(f"  ← {self.label(e.source)} {RELATIONS.get(e.relation, e.relation)} это")
        return "\n".join(lines)

    def path_to_text(self, path: list[Edge]) -> str:
        if not path:
            return "(тот же узел)"
        parts = []
        for e in path:
            parts.append(f"«{self.label(e.source)}» —{RELATIONS.get(e.relation, e.relation)}→ «{self.label(e.target)}»")
        return ";  ".join(parts)

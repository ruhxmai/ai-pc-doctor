"""Семантическая сеть предметной области (неделя 4).

Узлы — понятия (компоненты, неисправности, признаки, способы устранения),
дуги — именованные отношения между ними.
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

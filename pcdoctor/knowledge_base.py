"""База знаний предметной области «Диагностика неисправностей ПК» (неделя 4).

Все остальные модули (логика, продукции, фреймы, семантическая сеть,
датасет для обучения) строятся из одного источника — data/knowledge.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
KB_PATH = DATA_DIR / "knowledge.json"

SEVERITY_LABELS = {"low": "низкая", "medium": "средняя", "high": "высокая"}
TYPE_LABELS = {"hardware": "аппаратная", "software": "программная"}


@dataclass
class Component:
    id: str
    name: str
    is_a: str | None
    part_of: str | None


@dataclass
class Symptom:
    id: str
    name: str
    question: str
    patterns: list[str]


@dataclass
class Fault:
    id: str
    name: str
    type: str
    component: str
    severity: str
    prior: float
    description: str
    fix: str
    steps: list[str]
    symptoms: dict[str, float]  # P(признак | неисправность)

    @property
    def type_label(self) -> str:
        return TYPE_LABELS.get(self.type, self.type)

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, self.severity)


class KnowledgeBase:
    """Хранилище знаний: компоненты, признаки (симптомы) и неисправности."""

    def __init__(self, domain: str, components: dict[str, Component],
                 symptoms: dict[str, Symptom], faults: dict[str, Fault],
                 default_probability: float = 0.05):
        self.domain = domain
        self.components = components
        self.symptoms = symptoms
        self.faults = faults
        self.default_probability = default_probability
        self._validate()

    @classmethod
    def load(cls, path: str | Path = KB_PATH) -> "KnowledgeBase":
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        components = {cid: Component(cid, c["name"], c["is_a"], c["part_of"])
                      for cid, c in raw["components"].items()}
        symptoms = {sid: Symptom(sid, s["name"], s["question"], list(s["patterns"]))
                    for sid, s in raw["symptoms"].items()}
        faults = {fid: Fault(fid, f["name"], f["type"], f["component"], f["severity"],
                             f["prior"], f["description"], f["fix"], list(f["steps"]),
                             dict(f["symptoms"]))
                  for fid, f in raw["faults"].items()}
        return cls(raw["domain"], components, symptoms, faults,
                   raw.get("default_symptom_probability", 0.05))

    def _validate(self) -> None:
        """Проверка целостности: все ссылки указывают на существующие объекты."""
        for c in self.components.values():
            for ref in (c.is_a, c.part_of):
                if ref is not None and ref not in self.components:
                    raise ValueError(f"Компонент {c.id}: неизвестная ссылка {ref}")
        for f in self.faults.values():
            if f.component not in self.components:
                raise ValueError(f"Неисправность {f.id}: неизвестный компонент {f.component}")
            for sid, p in f.symptoms.items():
                if sid not in self.symptoms:
                    raise ValueError(f"Неисправность {f.id}: неизвестный признак {sid}")
                if not 0.0 <= p <= 1.0:
                    raise ValueError(f"Неисправность {f.id}: вероятность {p} вне [0, 1]")

    # --- доступ к знаниям ---------------------------------------------------

    @property
    def symptom_ids(self) -> list[str]:
        return list(self.symptoms)

    @property
    def fault_ids(self) -> list[str]:
        return list(self.faults)

    def p_symptom(self, fault_id: str, symptom_id: str) -> float:
        """P(признак | неисправность); для неуказанных признаков — фоновая вероятность."""
        return self.faults[fault_id].symptoms.get(symptom_id, self.default_probability)

    def faults_with_symptom(self, symptom_id: str) -> list[Fault]:
        return [f for f in self.faults.values() if symptom_id in f.symptoms]

    def ancestors(self, component_id: str) -> list[str]:
        """Цепочка родовых понятий по отношению is_a: hdd → storage → ... → entity."""
        chain = []
        current = self.components[component_id].is_a
        while current is not None:
            chain.append(current)
            current = self.components[current].is_a
        return chain

    def containers(self, component_id: str) -> list[str]:
        """Цепочка «входит в» по отношению part_of: cpu → motherboard → system_unit → computer."""
        chain = []
        current = self.components[component_id].part_of
        while current is not None:
            chain.append(current)
            current = self.components[current].part_of
        return chain

    def name_of(self, obj_id: str) -> str:
        for table in (self.faults, self.symptoms, self.components):
            if obj_id in table:
                return table[obj_id].name
        return obj_id

    def summary(self) -> str:
        hw = sum(f.type == "hardware" for f in self.faults.values())
        links = sum(len(f.symptoms) for f in self.faults.values())
        return (f"Предметная область: {self.domain}\n"
                f"  компонентов: {len(self.components)}\n"
                f"  признаков: {len(self.symptoms)}\n"
                f"  неисправностей: {len(self.faults)} "
                f"(аппаратных {hw}, программных {len(self.faults) - hw})\n"
                f"  связей «неисправность → признак»: {links}")

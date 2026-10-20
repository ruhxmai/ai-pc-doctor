"""Экспертная система (неделя 13): база знаний + правила + механизмы вывода.

Как ставится диагноз:
  1. Логический вывод (недели 5–6): какие diagnosis(F) доказываются, с деревом доказательства.
  2. Продукционная система (неделя 7): прямой вывод диагнозов, флагов опасности и советов.
  3. Наивный Байес (неделя 11) и нейросеть (неделя 12): вероятность каждой неисправности.
  4. Итоговая уверенность — взвешенная комбинация: 0.35·Байес + 0.35·нейросеть + 0.30·правила.
  5. Фреймы (недели 8–9): какие комплектующие пользователя затронуты, их возраст и ресурс.
  6. Семантическая сеть (неделя 10): дифференциальная диагностика — какие признаки
     отличают главную гипотезу от ближайшей альтернативы.

Консультация в диалоге: следующий вопрос выбирается по максимуму ожидаемого прироста
информации (снижения энтропии апостериорного распределения).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import dataset
from .classifier import ExpertBayes, NaiveBayes
from .explanation import explain_proof
from .frames import FrameSystem
from .knowledge_base import DATA_DIR, MODELS_DIR, KnowledgeBase
from .logic import LogicEngine
from .neural import MLP
from .production import ProductionSystem
from .semantic_net import SemanticNetwork

WEIGHTS = {"bayes": 0.35, "neural": 0.35, "rules": 0.30}

ADVICE_TEXT = {
    "unplug": "Немедленно отключите компьютер от сети и не включайте до проверки!",
    "backup": "Срочно сделайте резервную копию важных данных.",
    "service": "При отсутствии опыта обратитесь в сервисный центр.",
    "self_repair": "Проблему можно устранить самостоятельно программными средствами.",
    "need_more_info": "Данных недостаточно — опишите проблему подробнее.",
}


def entropy(p: np.ndarray) -> float:
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


@dataclass
class Hypothesis:
    fault_id: str
    name: str
    confidence: float
    bayes: float
    neural: float
    by_logic: bool
    by_production: bool


@dataclass
class Diagnosis:
    present: list[str]
    absent: list[str]
    hypotheses: list[Hypothesis]
    advice: list[str]
    logic_explanations: dict[str, str] = field(default_factory=dict)
    production_chain: dict[str, list[str]] = field(default_factory=dict)
    components: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    differential: list[str] = field(default_factory=list)

    @property
    def best(self) -> Hypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None


class ExpertSystem:
    def __init__(self, kb: KnowledgeBase | None = None, verbose: bool = False):
        self.kb = kb or KnowledgeBase.load()
        self.logic = LogicEngine()
        self.logic.consult_file(DATA_DIR / "logic_kb.pl")
        self.production = ProductionSystem.load()
        self.frames = FrameSystem.load(kb=self.kb)
        self.net = SemanticNetwork.from_knowledge_base(self.kb)
        self.net.add_frames(self.frames)
        self.bayes, self.neural = self._load_models(verbose)

    def _load_models(self, verbose: bool) -> tuple[NaiveBayes, MLP]:
        """Загружает обученные модели; если их нет — обучает на датасете (несколько секунд)."""
        nb_path, mlp_path = MODELS_DIR / "naive_bayes.json", MODELS_DIR / "mlp.npz"
        if nb_path.exists() and mlp_path.exists():
            return NaiveBayes.load(nb_path), MLP.load(mlp_path)
        if verbose:
            print("Модели не найдены — обучаю на датасете...")
        if dataset.DATASET_PATH.exists():
            X, y = dataset.load_csv(self.kb)
        else:
            X, y = dataset.generate(self.kb)
        X_tr, X_val, y_tr, y_val = dataset.train_test_split(X, y, test_size=0.2)
        nb = NaiveBayes().fit(X, y, len(self.kb.faults))
        net = MLP((len(self.kb.symptoms), 32, 16, len(self.kb.faults)), l2=1e-3)
        net.fit(X_tr, y_tr, X_val, y_val, epochs=150, lr=0.003, patience=20)
        MODELS_DIR.mkdir(exist_ok=True)
        nb.save(nb_path)
        net.save(mlp_path)
        return nb, net

    # --- вероятностная часть ---

    def _observed(self, present, absent) -> dict[int, int]:
        idx = self.kb.symptom_ids.index
        return {idx(s): 1 for s in present} | {idx(s): 0 for s in absent}

    def posterior(self, present, absent=()) -> np.ndarray:
        return self.bayes.posterior(self._observed(present, absent))

    def neural_proba(self, present) -> np.ndarray:
        x = np.array([[1 if s in present else 0 for s in self.kb.symptom_ids]])
        return self.neural.predict_proba(x)[0]

    # --- диагностика ---

    def diagnose(self, present: list[str], absent: list[str] = ()) -> Diagnosis:
        present = [s for s in dict.fromkeys(present) if s in self.kb.symptoms]
        absent = [s for s in dict.fromkeys(absent) if s in self.kb.symptoms and s not in present]
        if not present:
            return Diagnosis(present, absent, [], [ADVICE_TEXT["need_more_info"]])

        # 1. логический вывод
        for s in present:
            self.logic.add_fact(f"symptom({s})")
        try:
            logic_faults = [a["F"] for a in self.logic.ask("diagnosis(F)")]
            logic_expl = {f: explain_proof(self.logic.prove(f"diagnosis({f})"), self.kb.name_of)
                          for f in logic_faults}
        finally:
            for s in present:
                self.logic.retract(f"symptom({s})")

        # 2. продукционная система
        result = self.production.run(present)
        prod_faults = result.diagnoses
        chains = {f: [str(x.rule) for x in result.why(f"diag:{f}")] for f in prod_faults}

        # 3–4. вероятности и их комбинация
        bayes = self.posterior(present, absent)
        neural = self.neural_proba(present)
        rule_faults = set(logic_faults) | set(prod_faults)
        rules = np.array([1.0 if f in rule_faults else 0.0 for f in self.kb.fault_ids])
        if rules.sum() > 0:
            rules /= rules.sum()
            combined = WEIGHTS["bayes"] * bayes + WEIGHTS["neural"] * neural + WEIGHTS["rules"] * rules
        else:
            combined = 0.5 * bayes + 0.5 * neural
        combined /= combined.sum()

        hypotheses = [Hypothesis(f, self.kb.faults[f].name, float(combined[i]), float(bayes[i]),
                                 float(neural[i]), f in logic_faults, f in prod_faults)
                      for i, f in enumerate(self.kb.fault_ids)]
        hypotheses.sort(key=lambda h: -h.confidence)
        hypotheses = [h for h in hypotheses if h.confidence >= 0.03][:4]

        diag = Diagnosis(present, absent, hypotheses,
                         [ADVICE_TEXT.get(a, a) for a in result.advice if a != "need_more_info"],
                         logic_expl, chains)
        if not diag.advice and not rule_faults:
            diag.advice.append(ADVICE_TEXT["need_more_info"])
        self._add_frame_info(diag)
        self._add_differential(diag)
        return diag

    def _add_frame_info(self, diag: Diagnosis) -> None:
        """Фреймы: конкретные комплектующие пользователя, которых касается главная гипотеза."""
        best = diag.best
        component = self.kb.faults[best.fault_id].component
        for inst in self.frames.instances_of(component):
            fs = self.frames
            info = [fs.label(inst)]
            for slot in ("power_w", "capacity_gb", "vram_gb", "version"):
                if fs.get(inst, slot) is not None:
                    info.append(f"{slot}={fs.get(inst, slot)}")
            age, left = fs.get(inst, "age_years"), fs.get(inst, "lifetime_left")
            if age is not None:
                info.append(f"возраст {age} г.")
            diag.components.append(", ".join(info))
            if left is not None and left < 0:
                diag.warnings.append(
                    f"{fs.label(inst)} старше типичного срока службы на {-left} г. — "
                    f"это повышает вероятность гипотезы «{best.name}».")

    def _add_differential(self, diag: Diagnosis) -> None:
        """Семантическая сеть: признаки, которые отличают главную гипотезу от второй."""
        if len(diag.hypotheses) < 2:
            return
        a, b = diag.hypotheses[0].fault_id, diag.hypotheses[1].fault_id
        known = set(diag.present) | set(diag.absent)
        sa = {e.target for e in self.net.out_edges(a, "manifests")} - known
        sb = {e.target for e in self.net.out_edges(b, "manifests")} - known
        for s in sorted(sa - sb, key=lambda s: -self.kb.p_symptom(a, s))[:2]:
            diag.differential.append(f"«{self.kb.symptoms[s].name}» — скорее за «{self.kb.faults[a].name}»")
        for s in sorted(sb - sa, key=lambda s: -self.kb.p_symptom(b, s))[:2]:
            diag.differential.append(f"«{self.kb.symptoms[s].name}» — скорее за «{self.kb.faults[b].name}»")

    # --- выбор вопроса ---

    def next_question(self, present, absent) -> tuple[str | None, float]:
        """Признак с максимальным ожидаемым приростом информации."""
        known = set(present) | set(absent)
        prior = self.posterior(present, absent)
        h0 = entropy(prior)
        best, best_gain = None, 0.0
        for i, s in enumerate(self.kb.symptom_ids):
            if s in known:
                continue
            p_yes = float((prior * self.bayes.feature_prob[:, i]).sum())
            h_yes = entropy(self.posterior(list(present) + [s], absent))
            h_no = entropy(self.posterior(present, list(absent) + [s]))
            gain = h0 - (p_yes * h_yes + (1 - p_yes) * h_no)
            if gain > best_gain:
                best, best_gain = s, gain
        return best, best_gain

    def why_question(self, symptom: str, present, absent) -> str:
        """Ответ на «Почему вы спрашиваете?»."""
        post = self.posterior(present, absent)
        top = np.argsort(-post)[:3]
        lines = ["Сейчас наиболее вероятны:"]
        for i in top:
            f = self.kb.fault_ids[i]
            lines.append(f"  {self.kb.faults[f].name} — {post[i]:.0%}; "
                         f"при этой неисправности признак встречается с вероятностью {self.kb.p_symptom(f, symptom):.0%}")
        lines.append("Ответ на вопрос лучше всего разделит эти гипотезы (максимальный прирост информации).")
        return "\n".join(lines)

    def consult(self, ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
                present: list[str] | None = None, max_questions: int = 10, threshold: float = 0.9) -> Diagnosis:
        """Диалог-консультация: система сама задаёт вопросы."""
        present, absent = list(present or []), []
        for _ in range(max_questions):
            post = self.posterior(present, absent)
            if present and post.max() >= threshold:
                break
            symptom, gain = self.next_question(present, absent)
            if symptom is None or gain < 0.01:
                break
            while True:
                answer = ask(f"{self.kb.symptoms[symptom].question} (да/нет/не знаю/почему) ").strip().lower()
                if answer in ("почему", "why", "?"):
                    say(self.why_question(symptom, present, absent))
                    continue
                break
            if answer in ("да", "д", "y", "yes", "+"):
                present.append(symptom)
            elif answer in ("нет", "н", "n", "no", "-"):
                absent.append(symptom)
            else:
                absent.append(symptom)  # «не знаю» — считаем, что признак не замечен
        return self.diagnose(present, absent)


def format_report(diag: Diagnosis, kb: KnowledgeBase, details: bool = True) -> str:
    lines = []
    if diag.present:
        lines.append("Признаки: " + ", ".join(kb.symptoms[s].name for s in diag.present))
    if diag.absent:
        lines.append("Отсутствуют: " + ", ".join(kb.symptoms[s].name for s in diag.absent))
    if not diag.hypotheses:
        lines.append("Не удалось определить неисправность. " + " ".join(diag.advice))
        return "\n".join(lines)

    lines.append("\nВероятные неисправности:")
    for h in diag.hypotheses:
        marks = []
        if h.by_logic:
            marks.append("логика")
        if h.by_production:
            marks.append("продукции")
        lines.append(f"  {h.confidence:6.1%}  {h.name:<34} Байес {h.bayes:4.0%} | нейросеть {h.neural:4.0%}"
                     + (f" | правила: {', '.join(marks)}" if marks else ""))

    best = kb.faults[diag.best.fault_id]
    lines.append(f"\nНаиболее вероятно: {best.name} ({best.type_label}, опасность — {best.severity_label})")
    lines.append(f"  {best.description}")
    lines.append(f"Как устранить — {best.fix.lower()}:")
    lines += [f"  {i}. {step}" for i, step in enumerate(best.steps, 1)]
    if diag.advice:
        lines.append("Рекомендации:")
        lines += [f"  • {a}" for a in diag.advice]
    if diag.components:
        lines.append("Ваши комплектующие (фреймы):")
        lines += [f"  – {c}" for c in diag.components]
    lines += [f"  ⚠ {w}" for w in diag.warnings]
    if diag.differential:
        lines.append("Чтобы уточнить диагноз, проверьте:")
        lines += [f"  ? {d}" for d in diag.differential]

    if details:
        fid = diag.best.fault_id
        if fid in diag.logic_explanations:
            lines.append("\nОбъяснение (логический вывод):")
            lines += ["  " + l for l in diag.logic_explanations[fid].splitlines()]
        if fid in diag.production_chain:
            lines.append("Объяснение (цепочка продукций):")
            lines += ["  " + r for r in diag.production_chain[fid]]
    return "\n".join(lines)

"""ИИ-помощник (неделя 14): ввод запроса → анализ → поиск решения → формирование ответа.

Анализ запроса (простая обработка естественного языка, без внешних библиотек):
  * нормализация (нижний регистр, ё → е) и токенизация;
  * разбиение на клаузы по знакам препинания и союзам — чтобы отрицание
    «запаха гари нет» не относилось к соседнему «не включается»;
  * распознавание признаков по шаблонам основ слов из базы знаний (с учётом отрицаний);
  * определение намерения (intent) по ключевым словам;
  * поиск упоминаемых сущностей (компонентов, неисправностей, признаков).
Поиск решения — экспертная система (неделя 13), фреймы и семантическая сеть.
Ответ формируется по шаблонам; помощник помнит контекст диалога и может задавать
уточняющие вопросы.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .expert_system import ExpertSystem, format_report
from .knowledge_base import lower_first

NEGATIONS = {"не", "нет", "без", "ни", "нету"}
EXIT_PHRASES = {"выход", "пока", "до свидания", "exit", "quit", "q"}
YES = {"да", "ага", "угу", "конечно", "есть", "yes", "y", "д", "+", "верно", "точно"}
NO = {"нет", "неа", "no", "n", "н", "-", "не"}
DONT_KNOW = {"не знаю", "незнаю", "хз", "не уверен", "не помню", "?"}

# Словарь сущностей для запросов «что такое …», «как починить …»
ENTITY_KEYWORDS = {
    "psu": ["блок питан", "бп", "psu"],
    "motherboard": ["материнск", "мат плат", "материнк"],
    "cpu": ["процессор", "цп", "cpu", "проц"],
    "cooler": ["кулер", "охлажден", "вентилятор"],
    "ram": ["оператив", "озу", "ram", "памят"],
    "hdd": ["жестк диск", "hdd", "винчестер", "хард"],
    "ssd": ["ssd", "твердотел", "ссд"],
    "storage": ["накопител", "диск"],
    "gpu": ["видеокарт", "видюх", "gpu", "видео карт"],
    "os": ["операцион", "windows", "виндовс", "винда", "ос"],
    "driver": ["драйвер", "дрова"],
    "psu_failure": ["неисправн блок питан", "сгорел блок питан"],
    "overheating": ["перегрев"],
    "malware": ["вирус", "вредонос", "майнер", "троян"],
    "disk_failure": ["отказ диск", "поломк диск", "умирает диск", "сломал диск"],
    "ram_failure": ["неисправн памят", "неисправн оператив"],
    "gpu_failure": ["неисправн видеокарт", "сломал видеокарт"],
    "driver_issue": ["проблем драйвер", "слетел драйвер"],
    "os_corruption": ["поврежден ос", "поврежден windows", "слетел windows", "слетела винда"],
    "bsod": ["син экран", "bsod", "экран смерт"],
}

INTENT_PATTERNS = [
    ("reset", ["сброс", "заново", "нов проблем", "другая проблем", "reset"]),
    ("help", ["помощ", "что умеешь", "что ты умеешь", "help", "команды"]),
    ("greeting", ["привет", "здравств", "добр день", "добр вечер", "хай"]),
    ("thanks", ["спасиб", "благодар"]),
    ("consult", ["диагностик", "задай вопрос", "спроси меня", "консультац", "проверь меня", "опрос"]),
    ("explain", ["объясни", "почему так", "как ты решил", "как получил", "обоснуй", "почему ты так"]),
    ("my_pc", ["мой компьютер", "мои комплектующ", "моя конфигурац", "мой пк", "что у меня стоит", "конфигурац"]),
    ("temperature", ["температур"]),
    ("how_fix", ["как починить", "как исправить", "как устранить", "как вылечить", "что делать с", "как почин",
                 "как исправ", "как убрать", "как удалить"]),
    ("causes", ["почему", "из-за чего", "из за чего", "что вызывает", "причин", "отчего", "от чего"]),
    ("what_is", ["что такое", "что это", "расскажи о", "расскажи про", "кто такой", "для чего нужен", "зачем нужен"]),
]

HELP_TEXT = """Я — PC Doctor, помощник по диагностике неисправностей компьютера. Я умею:
  • ставить диагноз по описанию: «компьютер не включается и пахнет гарью»
  • уточнять: «ещё он пищит», «синего экрана нет» (я помню, о чём мы говорили)
  • проводить опрос: «проведи диагностику» — я сам задам вопросы
  • объяснять вывод: «объясни», «почему ты так решил»
  • отвечать на вопросы: «что такое SSD», «почему появляется синий экран»,
    «как устранить перегрев», «покажи мой компьютер», «температура процессора 97»
  • «сброс» — начать с новой проблемой, «выход» — завершить"""


def normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zа-я0-9]+", normalize(text))


def split_clauses(text: str) -> list[list[str]]:
    parts = re.split(r"[.,;!?\n]+|\s(?:и|а|но|также|плюс|еще|ещё|к тому же|причем)\s", f" {normalize(text)} ")
    return [t for t in (tokenize(p) for p in parts) if t]


def stem_matches(stem: str, token: str) -> bool:
    """Отрицания и очень короткие основы («ос», «бп») сравниваются точно, остальные — как префикс слова."""
    return token == stem if stem in NEGATIONS or len(stem) <= 2 else token.startswith(stem)


def match_pattern(pattern: str, tokens: list[str]) -> int | None:
    """Позиция первого совпавшего слова, если все основы шаблона есть в клаузе."""
    positions = []
    for stem in pattern.split():
        pos = next((i for i, t in enumerate(tokens) if stem_matches(stem, t)), None)
        if pos is None:
            return None
        positions.append(pos)
    return min(positions)


@dataclass
class Analysis:
    text: str
    tokens: list[str]
    intent: str
    present: list[str] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    numbers: list[float] = field(default_factory=list)

    def __str__(self) -> str:
        return (f"[анализ] токены: {self.tokens}\n"
                f"[анализ] намерение: {self.intent}; признаки: +{self.present} −{self.absent}; "
                f"сущности: {self.entities}; числа: {self.numbers}")


class Assistant:
    MAX_QUESTIONS = 6

    def __init__(self, es: ExpertSystem | None = None):
        self.es = es or ExpertSystem()
        self.kb = self.es.kb
        self.present: list[str] = []
        self.absent: list[str] = []
        self.last_diagnosis = None
        self.pending: str | None = None  # признак, о котором задан вопрос
        self.questions = 0
        self.debug = False

    # --- анализ запроса ---

    def extract_symptoms(self, text: str) -> tuple[list[str], list[str]]:
        present, absent = [], []
        for tokens in split_clauses(text):
            for sid, symptom in self.kb.symptoms.items():
                for pattern in symptom.patterns:
                    pos = match_pattern(pattern, tokens)
                    if pos is None:
                        continue
                    has_neg_in_pattern = any(s in NEGATIONS for s in pattern.split())
                    negated = (not has_neg_in_pattern
                               and (any(t in ("нет", "нету") for t in tokens)
                                    or (pos > 0 and tokens[pos - 1] in NEGATIONS)))
                    (absent if negated else present).append(sid)
                    break
        present = list(dict.fromkeys(present))
        absent = [s for s in dict.fromkeys(absent) if s not in present]
        return present, absent

    def find_entities(self, text: str) -> list[str]:
        tokens = tokenize(text)
        found = []
        for entity, keywords in ENTITY_KEYWORDS.items():
            if any(match_pattern(k, tokens) is not None for k in keywords):
                found.append(entity)
        # более конкретные сущности важнее общих: «жёсткий диск» → hdd, а не storage
        if "hdd" in found or "ssd" in found:
            found = [e for e in found if e != "storage"]
        return found

    def detect_intent(self, text: str, present: list[str]) -> str:
        tokens = tokenize(text)
        if " ".join(tokens) in EXIT_PHRASES:
            return "exit"
        has_number = bool(re.search(r"\d", text))
        for intent, keys in INTENT_PATTERNS:
            if intent == "temperature" and not has_number:
                continue
            for k in keys:
                if (" " in k and match_pattern(k, tokens) is not None) or (" " not in k and any(t.startswith(k) for t in tokens)):
                    if intent in ("causes", "what_is", "how_fix", "temperature") or not present:
                        return intent
        return "diagnose" if present else "unknown"

    def analyze(self, text: str) -> Analysis:
        present, absent = self.extract_symptoms(text)
        intent = self.detect_intent(text, present)
        numbers = [float(n) for n in re.findall(r"\d+(?:[.,]\d+)?", text.replace(",", "."))]
        return Analysis(text, tokenize(text), intent, present, absent, self.find_entities(text), numbers)

    # --- поиск решения и формирование ответа ---

    def reply(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "Опишите, пожалуйста, что происходит с компьютером."
        if text.lower() in ("/debug", "debug"):
            self.debug = not self.debug
            return f"Режим отладки {'включён' if self.debug else 'выключен'}."
        if self.pending is not None:
            answer = self._answer_pending(text)
            if answer is not None:
                return answer
        a = self.analyze(text)
        handler = getattr(self, f"_on_{a.intent}")
        response = handler(a)
        return f"{a}\n{response}" if self.debug else response

    def _answer_pending(self, text: str) -> str | None:
        norm = normalize(text).strip(" .!")
        symptom = self.pending
        if norm in ("почему", "зачем", "почему спрашиваешь", "зачем спрашиваешь"):
            return self.es.why_question(symptom, self.present, self.absent) + \
                f"\n\n{self.kb.symptoms[symptom].question}"
        if norm in YES:
            self.present.append(symptom)
        elif norm in NO:
            self.absent.append(symptom)
        elif norm in DONT_KNOW:
            self.absent.append(symptom)
        else:
            self.pending = None  # пользователь сказал что-то другое — обрабатываем как новый запрос
            return None
        self.pending = None
        return self._diagnose_and_maybe_ask(after_answer=True)

    def _diagnose_and_maybe_ask(self, after_answer: bool = False) -> str:
        if self.present and self.questions < self.MAX_QUESTIONS:
            post = self.es.posterior(self.present, self.absent)
            if post.max() < 0.85:
                symptom, gain = self.es.next_question(self.present, self.absent)
                if symptom is not None and gain > 0.05:
                    self.pending = symptom
                    self.questions += 1
                    best = self.kb.faults[self.kb.fault_ids[post.argmax()]].name
                    lead = "Понял." if after_answer else f"Пока больше всего похоже на «{best}» ({post.max():.0%}), но нужно уточнить."
                    return f"{lead}\nВопрос {self.questions}: {self.kb.symptoms[symptom].question} (да / нет / не знаю / почему)"
        diag = self.es.diagnose(self.present, self.absent)
        self.last_diagnosis = diag
        if diag.best is None:
            return "Мне пока не хватает информации. Опишите признаки подробнее или скажите «проведи диагностику»."
        return format_report(diag, self.kb, details=False) + \
            "\n\nСкажите «объясни», чтобы увидеть ход рассуждений, или «сброс» для новой проблемы."

    def _on_diagnose(self, a: Analysis) -> str:
        for s in a.present:
            if s not in self.present:
                self.present.append(s)
            if s in self.absent:
                self.absent.remove(s)
        for s in a.absent:
            if s not in self.absent and s not in self.present:
                self.absent.append(s)
        names = ", ".join(lower_first(self.kb.symptoms[s].name) for s in a.present)
        neg = ", ".join(lower_first(self.kb.symptoms[s].name) for s in a.absent)
        heard = f"Распознал признаки: {names}." if names else ""
        if neg:
            heard += f" Учту, что нет: {neg}."
        return (heard + "\n" if heard else "") + self._diagnose_and_maybe_ask()

    def _on_consult(self, a: Analysis) -> str:
        if a.present:
            self._on_diagnose(a)
        symptom, _ = self.es.next_question(self.present, self.absent)
        if symptom is None:
            return self._diagnose_and_maybe_ask()
        self.pending = symptom
        self.questions += 1
        return (f"Хорошо, проведём диагностику. Отвечайте «да», «нет», «не знаю» или «почему».\n"
                f"Вопрос {self.questions}: {self.kb.symptoms[symptom].question}")

    def _on_explain(self, a: Analysis) -> str:
        if self.last_diagnosis is None or self.last_diagnosis.best is None:
            return "Я ещё не ставил диагноз. Опишите проблему."
        return format_report(self.last_diagnosis, self.kb, details=True)

    def _on_what_is(self, a: Analysis) -> str:
        if not a.entities:
            if a.present:
                return self._describe_symptom(a.present[0])
            return "Не знаю такого понятия. Спросите, например: «что такое блок питания» или «что такое SSD»."
        return "\n\n".join(self._describe_entity(e) for e in a.entities[:2])

    def _describe_entity(self, entity: str) -> str:
        if entity in self.kb.symptoms:
            return self._describe_symptom(entity)
        fs, net = self.es.frames, self.es.net
        if entity in self.kb.faults:
            f = self.kb.faults[entity]
            symptoms = ", ".join(lower_first(self.kb.symptoms[s].name)
                                 for s in sorted(f.symptoms, key=lambda s: -f.symptoms[s])[:4])
            return (f"{f.name} — {f.type_label} неисправность, опасность {f.severity_label}.\n"
                    f"{f.description}\nТипичные признаки: {symptoms}.\nУстранение: {lower_first(f.fix)}.")
        lines = [f"{fs.label(entity)} — {fs.get(entity, 'function', 'компонент компьютера')}."]
        chain = [fs.label(p) for p in fs.ancestors(entity) if p != "entity"]
        if chain:
            lines.append("Это разновидность: " + " → ".join(chain) + ".")
        container = self.kb.components[entity].part_of if entity in self.kb.components else None
        if container:
            lines.append(f"Входит в: {lower_first(self.kb.components[container].name)}.")
        lifetime = fs.get(entity, "typical_lifetime_years")
        if lifetime:
            lines.append(f"Типичный срок службы: {lifetime} лет.")
        faults = [e.source for e in net.in_edges(entity, "affects")]
        for parent in net.generalizations(entity):  # неисправности родового понятия (накопитель → HDD)
            faults += [e.source for e in net.in_edges(parent, "affects") if e.source not in faults]
        if faults:
            lines.append("Возможные неисправности: " + ", ".join(lower_first(self.kb.faults[f].name) for f in faults) + ".")
        mine = fs.instances_of(entity)
        if mine:
            lines.append("В вашем компьютере: " + ", ".join(fs.label(m) for m in mine) + ".")
        return "\n".join(lines)

    def _describe_symptom(self, sid: str) -> str:
        return self._causes_text(sid)

    def _causes_text(self, sid: str) -> str:
        """Семантическая сеть: какие неисправности проявляются этим признаком."""
        edges = self.es.net.query(relation="manifests", target=sid)
        if not edges:
            return f"«{self.kb.symptoms[sid].name}» не связан ни с одной известной мне неисправностью."
        post = self.es.posterior([sid])
        ranked = sorted(edges, key=lambda e: -post[self.kb.fault_ids.index(e.source)])
        lines = [f"«{self.kb.symptoms[sid].name}» может быть вызван:"]
        for e in ranked:
            p = post[self.kb.fault_ids.index(e.source)]
            lines.append(f"  • {self.kb.faults[e.source].name} — {p:.0%}")
        lines.append("Опишите другие признаки, и я уточню причину.")
        return "\n".join(lines)

    def _on_causes(self, a: Analysis) -> str:
        if a.present:
            return self._causes_text(a.present[0])
        symptoms = [e for e in a.entities if e in self.kb.symptoms]
        if symptoms:
            return self._causes_text(symptoms[0])
        if self.last_diagnosis is not None:
            return self._on_explain(a)
        return "Уточните, о каком признаке идёт речь: например, «почему компьютер сам перезагружается?»"

    def _on_how_fix(self, a: Analysis) -> str:
        faults = [e for e in a.entities if e in self.kb.faults]
        if not faults and a.present:
            self._on_diagnose(a)
            diag = self.es.diagnose(self.present, self.absent)
            self.last_diagnosis = diag
            faults = [diag.best.fault_id] if diag.best else []
        if not faults:
            component = next((e for e in a.entities if e in self.kb.components), None)
            if component:
                faults = [e.source for e in self.es.net.in_edges(component, "affects")]
        if not faults and self.last_diagnosis is not None and self.last_diagnosis.best:
            faults = [self.last_diagnosis.best.fault_id]
        if not faults:
            return "Что именно нужно исправить? Опишите проблему, например: «как убрать синий экран»."
        f = self.kb.faults[faults[0]]
        steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(f.steps, 1))
        service = "Если не уверены в своих силах — обратитесь в сервисный центр." \
            if self.es.frames.get(f.id, "needs_service") else "Это можно сделать самостоятельно."
        return f"{f.name} — {lower_first(f.fix)}:\n{steps}\n{service}"

    def _on_my_pc(self, a: Analysis) -> str:
        fs = self.es.frames
        lines = [f"{fs.label('my_pc')} (куплен в {fs.get('my_pc', 'purchase_year')} г.):"]
        for part in fs.get("my_pc", "parts") + fs.get("my_pc", "software"):
            cls = fs.label(fs.frames[part].is_a[0])
            left = fs.get(part, "lifetime_left")
            note = f", ресурс исчерпан ({-left} г. сверх нормы)" if left is not None and left < 0 else ""
            status = fs.get(part, "status")
            note += f", статус: {status}" if status and status != "исправен" else ""
            lines.append(f"  • {cls}: {fs.label(part)}{note}")
        return "\n".join(lines)

    def _on_temperature(self, a: Analysis) -> str:
        if not a.numbers:
            return "Назовите температуру, например: «температура процессора 85»."
        target = "gpu_rtx_3060" if "gpu" in a.entities else "cpu_i5_12400"
        value = a.numbers[-1]
        value = int(value) if value.is_integer() else value
        message = self.es.frames.set(target, "current_temp", value)
        status = self.es.frames.get(target, "status")
        reply = f"Записал: {self.es.frames.label(target)} — {value} °C (статус: {status})."
        if message:
            reply += f"\n{message}"
        if status == "исправен":
            return reply + "\nТемпература в норме."
        if target == "gpu_rtx_3060":
            return reply + ("\nПерегрев видеокарты вызывает артефакты и вылеты в играх. "
                            "Почистите её от пыли и проверьте вентиляторы. "
                            "Если есть артефакты или вылеты — напишите, и я проверю, не неисправна ли она.")
        if "high_temp" not in self.present:
            self.present.append("high_temp")
            reply += "\nДобавил признак «высокая температура процессора». " + self._diagnose_and_maybe_ask()
        return reply

    def _on_reset(self, a: Analysis) -> str:
        self.present, self.absent = [], []
        self.last_diagnosis, self.pending, self.questions = None, None, 0
        return "Хорошо, начнём заново. Опишите новую проблему."

    def _on_greeting(self, a: Analysis) -> str:
        return "Здравствуйте! Я PC Doctor. Опишите, что случилось с компьютером, или напишите «помощь»."

    def _on_thanks(self, a: Analysis) -> str:
        return "Пожалуйста! Если появятся новые симптомы — пишите."

    def _on_help(self, a: Analysis) -> str:
        return HELP_TEXT

    def _on_exit(self, a: Analysis) -> str:
        return "До свидания! Берегите свой компьютер."

    def _on_unknown(self, a: Analysis) -> str:
        if a.entities:
            return self._on_what_is(a)
        return ("Не совсем понял. Опишите, что происходит с компьютером "
                "(например: «шумит и сам перезагружается»), или напишите «помощь».")


def chat(assistant: Assistant | None = None) -> None:
    """Консольный чат с помощником."""
    assistant = assistant or Assistant()
    print("PC Doctor: " + assistant._on_greeting(None))
    while True:
        try:
            text = input("Вы: ")
        except EOFError:
            break
        response = assistant.reply(text)
        print("PC Doctor: " + response.replace("\n", "\n           ") + "\n")
        if assistant.analyze(text).intent == "exit" and assistant.pending is None:
            break

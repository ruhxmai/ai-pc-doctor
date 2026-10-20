"""PC Doctor — ИИ-помощник и экспертная система диагностики неисправностей ПК.

Запуск:
    python main.py                 меню со всеми модулями
    python main.py chat            чат с ИИ-помощником
    python main.py ask "текст"     один вопрос помощнику
    python main.py consult         консультация экспертной системы (вопрос — ответ)
    python main.py train           пересоздать датасет и переобучить модели
    python main.py test            запустить тесты
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

from pcdoctor import __version__  # noqa: E402
from pcdoctor.assistant import Assistant, chat  # noqa: E402
from pcdoctor.expert_system import ExpertSystem, format_report  # noqa: E402
from pcdoctor.explanation import explain_proof, why_not  # noqa: E402
from pcdoctor.frames_cli import repl as frames_repl  # noqa: E402

MENU = f"""
================================================================
  PC Doctor {__version__} — ИИ-помощник для диагностики неисправностей ПК
================================================================
  1. Чат с ИИ-помощником
  2. Консультация экспертной системы (система задаёт вопросы)
  3. Логический вывод: запросы к базе знаний
  4. Продукционная система: прямой вывод
  5. Фреймы: просмотр, поиск, изменение свойств
  6. Семантическая сеть: поиск связанных объектов
  7. Машинное обучение: переобучить и оценить модели
  8. Сведения о базе знаний
  0. Выход"""


def read(prompt: str) -> str | None:
    try:
        return input(prompt).strip()
    except EOFError:
        return None


def logic_repl(es: ExpertSystem) -> None:
    engine, kb = es.logic, es.kb
    print("Логический вывод. Команды:\n"
          "  ?- запрос            например: ?- inside(cpu, X)   или   ?- diagnosis(F)\n"
          "  + факт / - факт      добавить / удалить факт: + symptom(no_power)\n"
          "  как <цель>           дерево доказательства: как diagnosis(psu_failure)\n"
          "  почему нет <цель>    почему цель не выводится\n"
          "  факты                текущие признаки;  выход")
    while (line := read("логика> ")) not in (None, "выход", "exit"):
        try:
            if line.startswith("?-"):
                answers = engine.ask(line[2:].strip())
                if not answers:
                    print("  нет")
                elif answers == [{}]:
                    print("  да")
                for a in answers:
                    if a:
                        print("  " + ", ".join(f"{k} = {v}" for k, v in a.items()))
            elif line.startswith("+"):
                engine.add_fact(line[1:].strip().rstrip("."))
                print("  добавлено")
            elif line.startswith("-"):
                engine.retract(line[1:].strip().rstrip("."))
                print("  удалено")
            elif line.startswith("как "):
                proof = engine.prove(line[4:].strip())
                print(explain_proof(proof, kb.name_of) if proof else "  не выводится")
            elif line.startswith("почему нет "):
                print(why_not(engine, line[len("почему нет "):].strip(), kb.name_of))
            elif line == "факты":
                print("  " + (", ".join(str(f) for f in engine.facts.get("symptom", [])) or "признаков нет"))
            elif line:
                print("  Неизвестная команда")
        except (SyntaxError, ValueError, KeyError) as e:
            print(f"  Ошибка: {e}")
    engine.facts.pop("symptom", None)


def production_repl(es: ExpertSystem) -> None:
    kb = es.kb
    print("Продукционная система. Введите идентификаторы признаков через пробел.")
    print("Признаки: " + ", ".join(kb.symptom_ids))
    while (line := read("продукции> ")) not in (None, "выход", "exit", ""):
        facts = [s for s in line.replace(",", " ").split() if s in kb.symptoms]
        unknown = [s for s in line.replace(",", " ").split() if s not in kb.symptoms]
        if unknown:
            print(f"  Неизвестные признаки пропущены: {', '.join(unknown)}")
        result = es.production.run(facts)
        print(result.trace())
        print("Диагнозы:", ", ".join(kb.faults[d].name for d in result.diagnoses) or "нет")


def semantic_repl(es: ExpertSystem) -> None:
    net = es.net
    print("Семантическая сеть. Команды:\n"
          "  узел <id>                     описание узла и его связей\n"
          "  связанные <id> [глубина]      поиск связанных объектов (в ширину)\n"
          "  путь <id1> <id2>              кратчайшая цепочка связей\n"
          "  запрос <s|?> <отношение|?> <t|?>  шаблон триплета, например: запрос ? manifests bsod\n"
          "  активация <id> <id> ...       распространение активации → неисправности\n"
          "  найти <слово>                 поиск узлов по названию;  выход\n"
          "Отношения: is_a, part_of, affects, manifests, fixed_by, instance_of")
    while (line := read("сеть> ")) not in (None, "выход", "exit"):
        parts = line.split()
        if not parts:
            continue
        cmd, args = parts[0], parts[1:]
        try:
            if cmd == "узел":
                print(net.describe(args[0]))
            elif cmd == "связанные":
                depth = int(args[1]) if len(args) > 1 else 1
                for node, path in net.related(args[0], depth).items():
                    print(f"  [{len(path)}] {net.label(node):<36} {net.path_to_text(path)}")
            elif cmd == "путь":
                path = net.find_path(args[0], args[1])
                print("  " + (net.path_to_text(path) if path is not None else "связи нет"))
            elif cmd == "запрос":
                s, r, t = [None if x == "?" else x for x in (args + ["?"] * 3)[:3]]
                for e in net.query(s, r, t):
                    print(f"  {net.label(e.source)} —[{e.relation}]→ {net.label(e.target)}")
            elif cmd == "активация":
                for node, score in net.activate(args, node_type="fault")[:5]:
                    print(f"  {score:.3f}  {net.label(node)}")
            elif cmd == "найти":
                word = " ".join(args).lower()
                for n in net.nodes.values():
                    if word in n.label.lower() or word in n.id:
                        print(f"  {n.id:<24} {n.label} ({n.type})")
            else:
                print("  Неизвестная команда")
        except (KeyError, IndexError, ValueError) as e:
            print(f"  Ошибка: {e}")


def train(verbose: bool = True) -> None:
    """Пересоздаёт датасет, обучает наивный Байес и нейросеть, сохраняет модели и печатает метрики."""
    from pcdoctor import dataset, metrics
    from pcdoctor.classifier import NaiveBayes
    from pcdoctor.knowledge_base import MODELS_DIR, KnowledgeBase
    from pcdoctor.neural import MLP

    kb = KnowledgeBase.load()
    labels = [kb.faults[f].name for f in kb.fault_ids]
    X, y = dataset.generate(kb, n_samples=2000, seed=42)
    dataset.save_csv(X, y, kb)
    X_train, X_test, y_train, y_test = dataset.train_test_split(X, y, test_size=0.25)
    X_tr, X_val, y_tr, y_val = dataset.train_test_split(X_train, y_train, test_size=0.2, seed=1)

    nb = NaiveBayes().fit(X_train, y_train, len(labels))
    net = MLP((len(kb.symptoms), 32, 16, len(labels)), l2=1e-3, seed=0)
    net.fit(X_tr, y_tr, X_val, y_val, epochs=150, lr=0.003, patience=20, verbose=verbose)
    MODELS_DIR.mkdir(exist_ok=True)
    nb.save(MODELS_DIR / "naive_bayes.json")
    net.save(MODELS_DIR / "mlp.npz")
    if verbose:
        for name, model in (("Наивный Байес", nb), ("Нейросеть", net)):
            pred = model.predict(X_test)
            print(f"\n{name}: accuracy = {metrics.accuracy(y_test, pred):.3f}, "
                  f"top-3 = {metrics.top_k_accuracy(y_test, model.predict_proba(X_test)):.3f}")
        print("\nОтчёт нейросети:")
        print(metrics.classification_report(y_test, net.predict(X_test), labels))
        print(f"\nДатасет: {dataset.DATASET_PATH}\nМодели: {MODELS_DIR}")


def run_tests() -> int:
    import unittest
    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


def menu() -> None:
    print("Загрузка базы знаний и моделей...")
    es = ExpertSystem(verbose=True)
    assistant = Assistant(es)
    while True:
        print(MENU)
        choice = read("Выберите пункт: ")
        if choice in (None, "0"):
            print("До свидания!")
            return
        if choice == "1":
            print("Чат. Напишите «помощь», чтобы узнать возможности, «выход» — вернуться в меню.")
            chat(assistant)
        elif choice == "2":
            print("Отвечайте: да / нет / не знаю / почему\n")
            print("\n" + format_report(es.consult(), es.kb))
        elif choice == "3":
            logic_repl(es)
        elif choice == "4":
            production_repl(es)
        elif choice == "5":
            frames_repl(es.frames)
        elif choice == "6":
            semantic_repl(es)
        elif choice == "7":
            train()
            es = ExpertSystem()
            assistant = Assistant(es)
        elif choice == "8":
            print(es.kb.summary())
            print(es.logic.stats())
            print(f"Продукций: {len(es.production.rules)}")
            print(f"Фреймов: {len(es.frames.frames)}")
            print(es.net.stats())


def main(argv: list[str]) -> int:
    if not argv:
        menu()
        return 0
    cmd = argv[0]
    if cmd == "chat":
        chat()
    elif cmd == "ask":
        print(Assistant().reply(" ".join(argv[1:])))
    elif cmd == "consult":
        es = ExpertSystem(verbose=True)
        print(format_report(es.consult(), es.kb))
    elif cmd == "train":
        train()
    elif cmd == "test":
        return run_tests()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Интерактивная программа для работы с фреймами (неделя 9)."""
from __future__ import annotations

from .frames import FrameSystem, parse_value

HELP = """Команды:
  list [класс]                 — экземпляры (всех или класса с подклассами)
  classes                      — дерево классов
  show <фрейм>                 — все слоты фрейма с указанием, откуда они унаследованы
  get <фрейм> <слот>           — значение слота
  find [класс:<имя>] <условия> — поиск, например: find класс:storage capacity_gb>=500
                                 операторы: = != > < >= <= ~ ; без оператора — «слот задан»
  set <фрейм> <слот> <значение> — изменить свойство (срабатывают демоны if_added)
  del <фрейм> <слот>           — удалить собственное значение слота (вернётся унаследованное)
  new <имя> <класс> [метка]    — создать экземпляр
  save <файл.json>             — сохранить фреймы в файл
  help, exit"""


def class_tree(fs: FrameSystem, root: str = "entity") -> str:
    lines: list[str] = []

    def walk(name: str, depth: int) -> None:
        lines.append("  " + "   " * depth + f"{fs.label(name)} ({name})")
        for child, f in fs.frames.items():
            if f.kind == "class" and f.is_a and f.is_a[0] == name:
                walk(child, depth + 1)

    walk(root, 0)
    return "\n".join(lines)


def run_command(fs: FrameSystem, line: str) -> str:
    parts = line.split()
    if not parts:
        return ""
    cmd, args = parts[0].lower(), parts[1:]
    try:
        if cmd == "help":
            return HELP
        if cmd == "list":
            names = (fs.instances_of(args[0]) if args
                     else [n for n, f in fs.frames.items() if f.kind == "instance"])
            return "\n".join(f"  {n:<24} {fs.label(n):<34} ({fs.frames[n].is_a[0]})" for n in names) or "пусто"
        if cmd == "classes":
            return class_tree(fs)
        if cmd == "show":
            return fs.describe(args[0])
        if cmd == "get":
            value = fs.get(args[0], args[1])
            src = fs.origin(args[0], args[1])
            inherited = f"   (унаследовано от {src})" if src and src != args[0] else ""
            return f"{args[0]}.{args[1]} = {value}{inherited}"
        if cmd == "find":
            cls_name, conds = None, []
            for a in args:
                if a.startswith(("класс:", "class:")):
                    cls_name = a.split(":", 1)[1]
                else:
                    conds.append(a)
            names = fs.find(" ".join(conds), cls_name)
            return f"Найдено: {len(names)}\n" + "\n".join(f"  {n:<24} {fs.label(n)}" for n in names)
        if cmd == "set":
            old = fs.get(args[0], args[1])
            msg = fs.set(args[0], args[1], parse_value(" ".join(args[2:])))
            out = f"{args[0]}.{args[1]}: {old} → {fs.get(args[0], args[1])}"
            return out + (f"\n  демон: {msg}" if msg else "")
        if cmd == "del":
            if fs.delete_slot(args[0], args[1]):
                return (f"Удалено. Теперь {args[1]} = {fs.get(args[0], args[1])} "
                        f"(от {fs.origin(args[0], args[1])})")
            return "У фрейма нет собственного значения этого слота"
        if cmd == "new":
            fs.create(args[0], args[1], " ".join(args[2:]) or None)
            return f"Создан экземпляр {args[0]} класса {args[1]}"
        if cmd == "save":
            fs.save(args[0])
            return f"Сохранено в {args[0]}"
        return f"Неизвестная команда {cmd!r}. help — список команд"
    except (KeyError, IndexError, ValueError) as e:
        return f"Ошибка: {e}"


def repl(fs: FrameSystem) -> None:
    print("Работа с фреймами. help — список команд, exit — выход.")
    while True:
        try:
            line = input("фреймы> ").strip()
        except EOFError:
            break
        if line.lower() in ("exit", "quit", "выход"):
            break
        print(run_command(fs, line))

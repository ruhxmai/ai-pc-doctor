"""Неделя 8. Фреймовая модель: объекты, свойства, связи, наследование."""
import _setup  # noqa: F401

from pcdoctor.frames import FrameSystem
from pcdoctor.knowledge_base import KnowledgeBase

fs = FrameSystem.load(kb=KnowledgeBase.load(), current_year=2026)
classes = [f for f in fs.frames.values() if f.kind == "class"]
print(f"Фреймов: {len(fs.frames)} (классов {len(classes)}, экземпляров {len(fs.frames) - len(classes)})\n")

print("--- Иерархия классов ---")


def tree(name: str, indent: int = 0) -> None:
    f = fs.frames[name]
    print("   " * indent + f"{f.label} ({name})")
    for child in fs.frames.values():
        if child.kind == "class" and name in child.is_a and child.is_a[0] == name:
            tree(child.name, indent + 1)


tree("entity")

print("\n--- Простое наследование: HDD → storage → hardware_component → device ---")
print(fs.describe("hdd_seagate_1tb"))

print("\n--- Множественное наследование: cpu is_a [hardware_component, heat_source] ---")
print(fs.describe("cpu_i5_12400"))

print("\n--- Связи между фреймами (слот part_of) ---")
for part in fs.get("my_pc", "parts"):
    print(f"  {fs.label(part):<32} входит в → {fs.label(fs.get(part, 'part_of'))}")

print("\n--- Демон if_added: запись текущей температуры ---")
for t in (60, 88, 104):
    msg = fs.set("cpu_i5_12400", "current_temp", t)
    print(f"  current_temp = {t}: статус «{fs.get('cpu_i5_12400', 'status')}». {msg or ''}")

print("\n--- Фрейм неисправности (построен из базы знаний) ---")
print(fs.describe("disk_failure"))

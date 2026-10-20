"""Неделя 10. Семантическая сеть: узлы, связи, поиск связанных объектов."""
import _setup  # noqa: F401

from pcdoctor.frames import FrameSystem
from pcdoctor.knowledge_base import KnowledgeBase
from pcdoctor.semantic_net import SemanticNetwork

kb = KnowledgeBase.load()
net = SemanticNetwork.from_knowledge_base(kb)
net.add_frames(FrameSystem.load(kb=kb, current_year=2026))
print(net.stats())

print("\n--- 1. Описание узла (все входящие и исходящие связи) ---")
print(net.describe("hdd_seagate_1tb"))

print("\n--- 2. Шаблонный запрос: какие неисправности проявляются синим экраном? (?, manifests, bsod) ---")
for e in net.query(relation="manifests", target="bsod"):
    print("  ", net.label(e.source))

print("\n--- 3. Связанные объекты: всё в радиусе 2 от «Перегрев процессора» ---")
for node, path in net.related("overheating", depth=2, relations={"affects", "part_of", "fixed_by", "is_a"},
                              direction="out").items():
    print(f"  [{len(path)}] {net.label(node):<34} {net.path_to_text(path)}")

print("\n--- 4. Путь между понятиями: как связаны «Щелчки диска» и «Мой компьютер»? ---")
path = net.find_path("clicking_sound", "my_pc")
print("  ", net.path_to_text(path))

print("\n--- 5. Наследование в сети: куда «входит» жёсткий диск Seagate? ---")
for edge, origin in net.inherited_edges("hdd_seagate_1tb", "part_of"):
    via = "" if origin == "hdd_seagate_1tb" else f"  (унаследовано от «{net.label(origin)}»)"
    print(f"   входит в «{net.label(edge.target)}»{via}")
print("   родовые понятия:", " → ".join(net.label(g) for g in net.generalizations("hdd_seagate_1tb")))

print("\n--- 6. Общие признаки неисправности ОЗУ и видеокарты ---")
print("  ", [net.label(s) for s in net.common("ram_failure", "gpu_failure", "manifests")])

print("\n--- 7. Распространение активации: признаки → вероятные неисправности ---")
seeds = ["artifacts_screen", "games_crash", "loud_fan"]
print("   признаки:", ", ".join(net.label(s) for s in seeds))
for node, score in net.activate(seeds, node_type="fault")[:4]:
    print(f"   {score:.3f}  {net.label(node)}")

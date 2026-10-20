"""Неделя 4. База знаний и семантическая сеть."""
import _setup  # noqa: F401

from pcdoctor.knowledge_base import KnowledgeBase, ROOT_DIR
from pcdoctor.semantic_net import SemanticNetwork

kb = KnowledgeBase.load()
print("=== База знаний ===")
print(kb.summary())

print("\nНеисправности:")
for f in kb.faults.values():
    print(f"  {f.id:<14} {f.name} [{f.type_label}, опасность {f.severity_label}]")

print("\nИерархия «является» для HDD:", " → ".join(["hdd", *kb.ancestors("hdd")]))
print("Иерархия «входит в» для CPU:", " → ".join(["cpu", *kb.containers("cpu")]))

net = SemanticNetwork.from_knowledge_base(kb)
print("\n=== Семантическая сеть ===")
print(net.stats())
print("\nСвязи узла psu_failure:")
for e in net.out_edges("psu_failure"):
    print("  ", e, f"({net.label(e.target)})")

out = ROOT_DIR / "docs" / "semantic_net.md"
out.write_text("# Семантическая сеть (фрагмент: иерархия компонентов)\n\n```mermaid\n"
               + net.to_mermaid({"is_a", "part_of"}) + "\n```\n", encoding="utf-8")
print(f"\nДиаграмма сохранена: {out.relative_to(ROOT_DIR)}")

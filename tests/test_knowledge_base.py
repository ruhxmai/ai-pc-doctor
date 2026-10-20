import unittest

from pcdoctor.knowledge_base import KnowledgeBase
from pcdoctor.semantic_net import SemanticNetwork


class KnowledgeBaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase.load()

    def test_loaded(self):
        self.assertEqual(len(self.kb.faults), 8)
        self.assertEqual(len(self.kb.symptoms), 20)

    def test_probabilities(self):
        self.assertAlmostEqual(self.kb.p_symptom("psu_failure", "no_power"), 0.85)
        self.assertAlmostEqual(self.kb.p_symptom("psu_failure", "popups_ads"), 0.05)

    def test_hierarchy(self):
        self.assertEqual(self.kb.ancestors("hdd"), ["storage", "hardware_component", "device", "entity"])
        self.assertEqual(self.kb.containers("cpu"), ["motherboard", "system_unit", "computer"])

    def test_semantic_net_built(self):
        net = SemanticNetwork.from_knowledge_base(self.kb)
        targets = {e.target for e in net.out_edges("psu_failure", "manifests")}
        self.assertIn("no_power", targets)
        self.assertIn("psu", [e.target for e in net.out_edges("psu_failure", "affects")])


if __name__ == "__main__":
    unittest.main()


class SemanticSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pcdoctor.frames import FrameSystem
        kb = KnowledgeBase.load()
        cls.net = SemanticNetwork.from_knowledge_base(kb)
        cls.net.add_frames(FrameSystem.load(kb=kb, current_year=2026))

    def test_query(self):
        sources = {e.source for e in self.net.query(relation="manifests", target="bsod")}
        self.assertEqual(sources, {"ram_failure", "disk_failure", "gpu_failure", "driver_issue", "os_corruption"})

    def test_related(self):
        related = self.net.related("overheating", depth=2, relations={"affects", "part_of"})
        self.assertIn("cooler", related)
        self.assertIn("system_unit", related)
        self.assertEqual(len(related["system_unit"]), 2)

    def test_path(self):
        path = self.net.find_path("clicking_sound", "my_pc")
        self.assertIsNotNone(path)
        self.assertEqual(path[0].source, "disk_failure")

    def test_inheritance(self):
        targets = {e.target for e, _ in self.net.inherited_edges("hdd_seagate_1tb", "part_of")}
        self.assertEqual(targets, {"my_pc", "system_unit"})

    def test_activation(self):
        top = self.net.activate(["artifacts_screen", "games_crash"], node_type="fault")[0][0]
        self.assertEqual(top, "gpu_failure")

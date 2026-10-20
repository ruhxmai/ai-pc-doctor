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

import unittest

from pcdoctor.production import ProductionSystem


class ProductionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ps = ProductionSystem.load()

    def test_chain(self):
        r = self.ps.run(["no_power", "fans_not_spin"])
        self.assertEqual(r.diagnoses, ["psu_failure"])
        self.assertIn("area:power", r.memory)
        self.assertIn("service", r.advice)

    def test_negation(self):
        r = self.ps.run(["artifacts_screen", "after_update"])
        self.assertNotIn("gpu_failure", r.diagnoses)
        self.assertIn("driver_issue", r.diagnoses)

    def test_priority_danger_first(self):
        r = self.ps.run(["no_power", "burning_smell"])
        self.assertEqual(r.firings[0].rule.id, "S1")
        self.assertIn("unplug", r.advice)

    def test_need_more_info(self):
        r = self.ps.run(["loud_fan"])
        self.assertEqual(r.diagnoses, [])
        self.assertIn("need_more_info", r.advice)

    def test_refractoriness(self):
        r = self.ps.run(["no_power", "fans_not_spin"])
        ids = [f.rule.id for f in r.firings]
        self.assertEqual(len(ids), len(set(ids)))

    def test_why(self):
        r = self.ps.run(["no_power", "fans_not_spin"])
        self.assertEqual([f.rule.id for f in r.why("diag:psu_failure")], ["A1", "D1"])


if __name__ == "__main__":
    unittest.main()

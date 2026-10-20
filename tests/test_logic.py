import unittest

from pcdoctor.knowledge_base import DATA_DIR
from pcdoctor.logic import Atom, LogicEngine, parse_query, unify


class LogicTest(unittest.TestCase):
    def setUp(self):
        self.engine = LogicEngine()
        self.engine.consult_file(DATA_DIR / "logic_kb.pl")

    def test_unify(self):
        s = unify(Atom("p", ("X", "b")), Atom("p", ("a", "Y")), {})
        self.assertEqual(s, {"X": "a", "Y": "b"})
        self.assertIsNone(unify(Atom("p", ("a",)), Atom("p", ("b",)), {}))

    def test_transitive(self):
        self.assertTrue(self.engine.ask("kind_of(hdd, device)"))
        parents = [a["X"] for a in self.engine.ask("inside(cpu, X)")]
        self.assertEqual(parents, ["motherboard", "system_unit", "computer"])

    def test_classification(self):
        hw = {a["F"] for a in self.engine.ask("hardware_fault(F)")}
        self.assertEqual(hw, {"psu_failure", "ram_failure", "overheating", "disk_failure", "gpu_failure"})

    def test_diagnosis(self):
        self.engine.add_fact("symptom(no_power)")
        self.engine.add_fact("symptom(fans_not_spin)")
        self.assertEqual(self.engine.ask("diagnosis(F)"), [{"F": "psu_failure"}])
        self.assertEqual(self.engine.ask("urgent(F)"), [{"F": "psu_failure"}])

    def test_no_diagnosis_without_facts(self):
        self.assertEqual(self.engine.ask("diagnosis(F)"), [])

    def test_parse(self):
        self.assertEqual(str(parse_query("p(X), q(X, a)")), "p(X), q(X, a)")


if __name__ == "__main__":
    unittest.main()


class LogicOperatorsTest(unittest.TestCase):
    def setUp(self):
        self.engine = LogicEngine()
        self.engine.consult_file(DATA_DIR / "logic_kb.pl")

    def diagnose(self, *symptoms):
        for s in symptoms:
            self.engine.add_fact(f"symptom({s})")
        return {a["F"] for a in self.engine.ask("diagnosis(F)")}

    def test_or(self):
        self.assertIn("psu_failure", self.diagnose("no_power", "burning_smell"))

    def test_not_blocks(self):
        result = self.diagnose("artifacts_screen", "after_update")
        self.assertNotIn("gpu_failure", result)
        self.assertIn("driver_issue", result)

    def test_not_allows(self):
        self.assertIn("gpu_failure", self.diagnose("artifacts_screen"))

    def test_parse_operators(self):
        from pcdoctor.logic import And, Not, Or
        q = parse_query("a, (b ; c), not d")
        self.assertIsInstance(q, And)
        self.assertIsInstance(q.items[1], Or)
        self.assertIsInstance(q.items[2], Not)

    def test_explanation(self):
        from pcdoctor.explanation import explain_proof, why_not
        self.diagnose("no_power", "fans_not_spin")
        text = explain_proof(self.engine.prove("diagnosis(psu_failure)"))
        self.assertIn("symptom(no_power) — факт", text)
        self.assertIn("ИЛИ", text)
        self.assertIn("✘", why_not(self.engine, "diagnosis(ram_failure)"))

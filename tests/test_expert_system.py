import unittest

from pcdoctor.expert_system import ExpertSystem, format_report


class ExpertSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.es = ExpertSystem()

    def test_diagnose(self):
        d = self.es.diagnose(["no_power", "fans_not_spin"])
        self.assertEqual(d.best.fault_id, "psu_failure")
        self.assertTrue(d.best.by_logic and d.best.by_production)
        self.assertGreater(d.best.confidence, 0.8)
        self.assertAlmostEqual(sum(h.confidence for h in self.es.diagnose(["bsod"]).hypotheses), 1, delta=0.2)

    def test_logic_facts_cleaned(self):
        self.es.diagnose(["popups_ads"])
        self.assertEqual(self.es.logic.ask("symptom(X)"), [])

    def test_frames_warning(self):
        d = self.es.diagnose(["clicking_sound", "files_corrupted"])
        self.assertTrue(any("Seagate" in w for w in d.warnings))

    def test_empty(self):
        d = self.es.diagnose([])
        self.assertIsNone(d.best)
        self.assertIn("Не удалось", format_report(d, self.es.kb))

    def test_next_question_informative(self):
        symptom, gain = self.es.next_question([], [])
        self.assertIsNotNone(symptom)
        self.assertGreater(gain, 0.3)

    def test_consult(self):
        kb = self.es.kb
        truth = "gpu_failure"

        def user(question):
            s = next(s for s in kb.symptom_ids if kb.symptoms[s].question in question)
            return "да" if kb.p_symptom(truth, s) >= 0.5 else "нет"

        d = self.es.consult(ask=user, say=lambda _: None)
        self.assertEqual(d.best.fault_id, truth)


if __name__ == "__main__":
    unittest.main()

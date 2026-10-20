import unittest

from pcdoctor.assistant import Assistant, split_clauses
from pcdoctor.expert_system import ExpertSystem

# фраза → (ожидаемые признаки, ожидаемые отсутствующие признаки)
NLU_CASES = [
    ("компьютер не включается", {"no_power"}, set()),
    ("Комп не запускается и пахнет гарью", {"no_power", "burning_smell"}, set()),
    ("кулеры не крутятся, запаха гари нет", {"fans_not_spin"}, {"burning_smell"}),
    ("при включении пищит и вылетает синий экран", {"beeps", "bsod"}, set()),
    ("ноут сильно греется и шумит", {"high_temp", "loud_fan"}, set()),
    ("диск щёлкает, файлы пропадают", {"clicking_sound", "files_corrupted"}, set()),
    ("на экране полосы и артефакты, игры вылетают", {"artifacts_screen", "games_crash"}, set()),
    ("везде реклама, браузер тормозит", {"popups_ads", "slow_work"}, set()),
    ("после обновления пропал звук", {"after_update", "device_not_working"}, set()),
    ("винда не загружается", {"boot_failure"}, set()),
    ("иногда зависает, синего экрана нет", {"freezes"}, {"bsod"}),
    ("комп не шумит, но сам перезагружается", {"random_reboots"}, {"loud_fan"}),
    ("нет изображения на мониторе", {"no_image"}, set()),
    ("процессор загружен на 100 процентов без причины", {"high_cpu_idle"}, set()),
]


class AssistantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.es = ExpertSystem()

    def setUp(self):
        self.a = Assistant(self.es)

    def test_split_clauses(self):
        self.assertEqual(split_clauses("не включается, запаха нет и шумит"),
                         [["не", "включается"], ["запаха", "нет"], ["шумит"]])

    def test_symptom_extraction(self):
        for text, present, absent in NLU_CASES:
            with self.subTest(text=text):
                p, a = self.a.extract_symptoms(text)
                self.assertEqual(set(p), present)
                self.assertEqual(set(a), absent)

    def test_intents(self):
        cases = {
            "привет": "greeting", "что такое SSD": "what_is", "как устранить перегрев": "how_fix",
            "почему появляется синий экран": "causes", "проведи диагностику": "consult",
            "покажи мой компьютер": "my_pc", "температура процессора 90": "temperature",
            "объясни": "explain", "сброс": "reset", "пока": "exit", "помощь": "help",
            "монитор не показывает": "diagnose", "абракадабра": "unknown",
        }
        for text, intent in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.a.analyze(text).intent, intent)

    def test_entities(self):
        self.assertEqual(self.a.find_entities("что такое жёсткий диск"), ["hdd"])
        self.assertIn("ssd", self.a.find_entities("расскажи про ssd"))
        self.assertNotIn("os", self.a.find_entities("особенно сильно"))

    def test_dialog_context(self):
        r = self.a.reply("компьютер не включается")
        self.assertIn("Вопрос", r)
        r = self.a.reply("да")
        self.assertIn("блока питания", r)
        self.assertIn("fans_not_spin", self.a.present)

    def test_consult_flow(self):
        self.assertIn("Вопрос 1", self.a.reply("проведи диагностику"))
        self.assertIn("наиболее вероятны", self.a.reply("почему"))

    def test_answers(self):
        self.assertIn("SSD", self.a.reply("что такое ssd"))
        self.assertIn("Неисправность оперативной памяти", self.a.reply("почему появляется синий экран?"))
        self.assertIn("антивирус", self.a.reply("как удалить вирус"))
        self.assertIn("перегрев", self.a.reply("температура видеокарты 99"))


if __name__ == "__main__":
    unittest.main()

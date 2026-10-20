import unittest

from pcdoctor.frames import FrameSystem
from pcdoctor.knowledge_base import KnowledgeBase


class FramesTest(unittest.TestCase):
    def setUp(self):
        self.fs = FrameSystem.load(kb=KnowledgeBase.load(), current_year=2026)

    def test_own_slot(self):
        self.assertEqual(self.fs.get("hdd_seagate_1tb", "rpm"), 7200)

    def test_inheritance_override(self):
        self.assertTrue(self.fs.get("hdd_seagate_1tb", "has_moving_parts"))   # из hdd
        self.assertFalse(self.fs.get("ssd_samsung_970", "has_moving_parts"))  # из storage
        self.assertEqual(self.fs.origin("ssd_samsung_970", "has_moving_parts"), "storage")

    def test_multiple_inheritance(self):
        self.assertEqual(self.fs.get("cpu_i5_12400", "temp_unit"), "°C")  # из heat_source
        self.assertEqual(self.fs.get("cpu_i5_12400", "max_temp"), 100)    # своё значение
        self.assertTrue(self.fs.is_a("gpu_rtx_3060", "heat_source"))

    def test_if_needed(self):
        self.assertEqual(self.fs.get("hdd_seagate_1tb", "age_years"), 8)
        self.assertEqual(self.fs.get("hdd_seagate_1tb", "lifetime_left"), -3)

    def test_if_added(self):
        msg = self.fs.set("gpu_rtx_3060", "current_temp", 99)
        self.assertIn("перегрев", msg)
        self.assertEqual(self.fs.get("gpu_rtx_3060", "status"), "перегрев")

    def test_fault_frames(self):
        self.assertTrue(self.fs.get("disk_failure", "needs_service"))
        self.assertFalse(self.fs.get("malware", "needs_service"))


if __name__ == "__main__":
    unittest.main()


class FrameProgramTest(unittest.TestCase):
    def setUp(self):
        self.fs = FrameSystem.load(kb=KnowledgeBase.load(), current_year=2026)

    def test_find(self):
        self.assertEqual(self.fs.find("has_moving_parts=да"), ["hdd_seagate_1tb"])
        self.assertEqual(set(self.fs.find("max_temp>=95", "heat_source")), {"cpu_i5_12400"})
        self.assertIn("ram_failure", self.fs.find("symptoms~bsod", "fault"))

    def test_instances_of(self):
        self.assertEqual(set(self.fs.instances_of("storage")), {"hdd_seagate_1tb", "ssd_samsung_970"})

    def test_modify_and_delete(self):
        self.fs.set("ssd_samsung_970", "typical_lifetime_years", 12)
        self.assertEqual(self.fs.get("ssd_samsung_970", "typical_lifetime_years"), 12)
        self.fs.delete_slot("ssd_samsung_970", "typical_lifetime_years")
        self.assertEqual(self.fs.get("ssd_samsung_970", "typical_lifetime_years"), 8)

    def test_create(self):
        self.fs.create("ssd_new", "ssd", "Новый SSD", capacity_gb=1000, purchase_year=2026)
        self.assertEqual(self.fs.get("ssd_new", "age_years"), 0)
        self.assertIn("ssd_new", self.fs.find("capacity_gb>=1000"))

    def test_save_load(self):
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "f.json")
        self.fs.set("cpu_i5_12400", "cores", 8)
        self.fs.save(path)
        loaded = FrameSystem.load(path, current_year=2026)
        self.assertEqual(loaded.get("cpu_i5_12400", "cores"), 8)
        self.assertEqual(loaded.get("hdd_seagate_1tb", "age_years"), 8)

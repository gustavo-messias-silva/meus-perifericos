import os
import unittest
from pathlib import Path

from perifericos.prefs import load, save, set_autostart


class PrefsTests(unittest.TestCase):
    def setUp(self):
        self.config = Path(self.id().replace(".", "_") + "-config.yaml")
        self.desktop = Path(self.id().replace(".", "_") + "-autostart.desktop")
        os.environ["PERIFERICOS_CONFIG"] = str(self.config)
        os.environ["PERIFERICOS_AUTOSTART"] = str(self.desktop)

    def tearDown(self):
        self.config.unlink(missing_ok=True)
        self.desktop.unlink(missing_ok=True)
        os.environ.pop("PERIFERICOS_CONFIG", None)
        os.environ.pop("PERIFERICOS_AUTOSTART", None)

    def test_autostart_roundtrip(self):
        self.assertFalse(load()["autostart"])
        set_autostart(True)
        self.assertTrue(load()["autostart"])
        text = self.desktop.read_text()
        self.assertIn("--restore", text)
        self.assertIn("X-GNOME-Autostart-enabled=true", text)
        set_autostart(False)
        self.assertFalse(self.desktop.exists())
        self.assertFalse(load()["autostart"])

    def test_save_keeps_only_known_keys(self):
        save({"autostart": True, "extra": "não"})
        self.assertEqual(load()["autostart"], False)
        stored = self.config.read_text()
        self.assertNotIn("extra", stored)


if __name__ == "__main__":
    unittest.main()

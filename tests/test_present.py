"""Apresentação dos ajustes, sem falar com o hardware."""

import unittest

from perifericos.present import (
    KIND_CHOICE,
    KIND_MAP_CHOICE,
    KIND_RANGE,
    KIND_TOGGLE,
    battery_phrase,
    describe_setting,
    known_from_config,
    merge_offline,
    option_label,
)


class _Choices(list):
    pass


class _Setting:
    def __init__(self, name, kind, value, choices=None, bounds=None, choice_map=None, label="", description=""):
        self.name = name
        self.kind = kind
        self.label = label or name
        self.description = description
        self.display = True
        self._value = value
        self._choices = choices
        self._bounds = bounds
        self._validator = type("V", (), {"choices": choice_map, "min_value": None, "max_value": None})()

    def read(self, cached=True):
        return self._value

    @property
    def choices(self):
        return self._choices

    @property
    def range(self):
        return self._bounds


class PresentTests(unittest.TestCase):
    def test_report_rate_uses_hertz(self):
        self.assertEqual(option_label("1ms"), "1000 Hz · 1 ms")
        self.assertEqual(option_label("Disabled"), "Desativado")
        self.assertEqual(option_label("Profile 2"), "Perfil 2")

    def test_choice_and_range(self):
        rate = describe_setting(
            _Setting(
                "report_rate_extended",
                KIND_CHOICE,
                3,
                choices=[type("N", (), {"__int__": lambda self: 3, "__str__": lambda self: "1ms"})()],
            )
        )
        self.assertEqual(rate["title"], "Taxa de atualização")
        self.assertEqual(rate["group"], "pointer")
        self.assertEqual(rate["options"][0]["label"], "1000 Hz · 1 ms")

        actuation = describe_setting(_Setting("analog-button-tuning_actuation-0", KIND_RANGE, 5, bounds=(1, 10)))
        self.assertEqual(actuation["kind"], "range")
        self.assertEqual(actuation["group"], "buttons")
        self.assertEqual((actuation["min"], actuation["max"]), (1, 10))

    def test_dpi_map_fields(self):
        x = type("N", (), {"__int__": lambda self: 0, "__str__": lambda self: "X"})()
        y = type("N", (), {"__int__": lambda self: 1, "__str__": lambda self: "Y"})()
        dpi_800 = type("N", (), {"__int__": lambda self: 800, "__str__": lambda self: "800"})()
        dpi_1600 = type("N", (), {"__int__": lambda self: 1600, "__str__": lambda self: "1600"})()
        setting = _Setting(
            "dpi_extended",
            KIND_MAP_CHOICE,
            {x: 800, y: 1600},
            choice_map={x: [dpi_800, dpi_1600], y: [dpi_800, dpi_1600]},
        )
        described = describe_setting(setting)
        self.assertEqual(described["kind"], "map")
        self.assertEqual(described["fields"][0]["title"], "Eixo X")
        self.assertEqual(described["fields"][0]["value"], 800)
        self.assertEqual(described["fields"][1]["value"], 1600)
        self.assertEqual(len(described["fields"][0]["options"]), 2)

    def test_toggle(self):
        described = describe_setting(_Setting("headset-mic-snr", KIND_TOGGLE, True))
        self.assertEqual(described["kind"], "toggle")
        self.assertEqual(described["group"], "audio")
        self.assertTrue(described["value"])

    def test_offline_merge_skips_connected_serial(self):
        known = known_from_config(
            [
                "1.1.20",
                {"_NAME": "PRO X 2 LIGHTSPEED", "_wpid": "0AF7", "_serial": "2428"},
                {"_NAME": "PRO X 2 LIGHTSPEED"},
                {"_NAME": "PRO X2 SUPERSTRIKE", "_wpid": "40BD", "_serial": "B347"},
            ]
        )
        self.assertEqual(len(known), 2)
        live = [{"name": "PRO X2 SUPERSTRIKE", "wpid": "40BD", "serial": "B347", "online": True, "settings": []}]
        merged = merge_offline(live, known)
        self.assertEqual([item["name"] for item in merged], ["PRO X2 SUPERSTRIKE", "PRO X 2 LIGHTSPEED"])
        self.assertFalse(merged[1]["online"])

    def test_battery_phrase(self):
        self.assertEqual(battery_phrase(91, "DISCHARGING"), "91% · em uso")
        self.assertEqual(battery_phrase(None, None), "Bateria indisponível")


if __name__ == "__main__":
    unittest.main()

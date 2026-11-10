import importlib.util
from pathlib import Path
import unittest
import tomllib

spec = importlib.util.spec_from_file_location("repair", Path(__file__).with_name("repair-owner-image-hand.py"))
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)

class InstalledHandRepairTests(unittest.TestCase):
    def test_preserves_installed_pins_and_custom_owner_context(self):
        text = (Path(__file__).parent / "hands/stax/HAND.toml").read_text()
        text = text.replace('model = "default"', 'model = "google/gemma-4-26b-a4b-it"').replace('provider = "default"', 'provider = "openrouter"')
        text = text.replace("WHO YOU ARE TALKING TO", "CUSTOM INSTALLED OWNER CONTEXT — KEEP THIS\nWHO YOU ARE TALKING TO")
        before = tomllib.loads(text)
        output = repair.repair(text)
        after = tomllib.loads(output)
        self.assertIn("CUSTOM INSTALLED OWNER CONTEXT — KEEP THIS", after["agent"]["system_prompt"])
        self.assertEqual(before["agent"]["model"], after["agent"]["model"])
        self.assertEqual(before["agent"]["provider"], after["agent"]["provider"])
        self.assertTrue(after["agent"]["owner_facing"])
        self.assertIn("hand_activate", after["tools"])
        self.assertEqual(output, repair.repair(output))

    def test_adds_missing_owner_opt_in_without_repinning(self):
        text = (Path(__file__).parent / "hands/stax/HAND.toml").read_text().replace("owner_facing = true\n", "")
        after = tomllib.loads(repair.repair(text))
        self.assertTrue(after["agent"]["owner_facing"])
        self.assertEqual(after["agent"]["model"], "default")

    def test_rejects_a_different_hand(self):
        with self.assertRaisesRegex(ValueError, "only accepts"):
            repair.repair('id="style"\ntools=[]\n[agent]\nsystem_prompt="""test"""')

    def test_prompt_merge_preserves_installed_text_verbatim(self):
        current = "Shawn owns Fargo Tattoo. Keep these custom instructions.\n"
        merged = repair.merge_prompt(current)
        self.assertTrue(merged.startswith(current))
        self.assertEqual(merged, repair.merge_prompt(merged))

if __name__ == "__main__":
    unittest.main()

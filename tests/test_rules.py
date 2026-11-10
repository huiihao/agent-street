import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.engine.daily_routine import DailyRoutine
from backend.engine.rules import RuleBook, RuleValidationError
from backend.mbti.personas import PERSONA_DEFINITIONS


class RuleBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "interaction_rules.json"
        self.rules = RuleBook(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_file_uses_rule_defaults(self):
        self.assertFalse(self.path.exists())
        self.assertAlmostEqual(self.rules.get("conversation.chance"), 0.30)
        self.assertEqual(self.rules.get("conversation.max_per_tick"), 2)
        self.assertEqual(
            self.rules.get("routines.thinking")[0],
            ["home", 2],
        )
        self.assertTrue(self.rules.get("conversation.templates.greetings"))

    def test_partial_update_persists_and_reloads(self):
        self.rules.update({
            "conversation": {"chance": 0.18},
            "agents": {
                "INTJ": {
                    "conversation": {"chance": 0.05},
                    "trading": {"buy_threshold": 0.20},
                },
            },
        })
        self.assertTrue(self.path.exists())
        self.assertAlmostEqual(self.rules.get("conversation.chance"), 0.18)
        self.assertAlmostEqual(self.rules.for_agent("INTJ", "conversation.chance"), 0.05)
        self.assertAlmostEqual(self.rules.for_agent("INTJ", "trading.buy_threshold"), 0.20)
        self.assertAlmostEqual(self.rules.for_agent("ENFP", "conversation.chance"), 0.18)

        reloaded = RuleBook(self.path)
        self.assertAlmostEqual(reloaded.get("conversation.chance"), 0.18)
        self.assertAlmostEqual(reloaded.for_agent("INTJ", "conversation.chance"), 0.05)

    def test_invalid_api_value_is_rejected_without_writing(self):
        with self.assertRaises(RuleValidationError):
            self.rules.update({"conversation": {"chance": "not-a-number"}})
        self.assertAlmostEqual(self.rules.get("conversation.chance"), 0.30)

    def test_templates_are_validated_and_deep_copied(self):
        self.rules.update({
            "conversation": {
                "templates": {"greetings": ["Hello {symbol}"]},
            },
        })
        snapshot = self.rules.snapshot()
        snapshot["conversation"]["templates"]["greetings"].append("mutated")
        self.assertEqual(
            self.rules.get("conversation.templates.greetings"),
            ["Hello {symbol}"],
        )

    def test_reset_restores_defaults_and_removes_file(self):
        self.rules.update({"conversation": {"chance": 0.01}})
        self.assertTrue(self.path.exists())
        self.rules.reset()
        self.assertFalse(self.path.exists())
        self.assertAlmostEqual(self.rules.get("conversation.chance"), 0.30)

    def test_explicit_environment_override_wins(self):
        self.path.write_text(json.dumps({"conversation": {"chance": 0.2}}), encoding="utf-8")
        with patch.dict(os.environ, {"CONVERSATION_CHANCE": "0.01"}):
            rules = RuleBook(self.path)
            self.assertAlmostEqual(rules.get("conversation.chance"), 0.01)

    def test_routine_rule_substitutes_home_and_applies_to_new_routine(self):
        self.rules.update({
            "routines": {"thinking": [["home", 1], ["cafe", 2]]},
        })
        traits = PERSONA_DEFINITIONS["INTJ"]["traits"]
        routine = DailyRoutine("INTJ", traits, self.rules)
        self.assertEqual(routine.schedule, [("home_ne", 1), ("cafe", 2)])


if __name__ == "__main__":
    unittest.main()
